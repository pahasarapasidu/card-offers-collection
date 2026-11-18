"""Card Offers Collection scraper — collects credit card offers from Sri Lankan banks.

Run:  python scraper/scrape.py
Writes all offers to data/offers.json, which the app reads.

To add a bank: create scraper/banks/<bank>.py with a fetch_offers() function
that returns a list of offer dicts, then add it to BANKS below.
"""

import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from banks import boc, combank, dfcc, hnb, ndb, ntb, peoples, sampath, seylan
from dates import end_date

# Offers end on Sri Lanka dates, while GitHub's servers run on UTC.
SL_TIME = dt.timezone(dt.timedelta(hours=5, minutes=30))

BANKS = [
    ("Sampath Bank", sampath.fetch_offers),
    ("Commercial Bank", combank.fetch_offers),
    ("HNB", hnb.fetch_offers),
    ("Seylan Bank", seylan.fetch_offers),
    ("Nations Trust", ntb.fetch_offers),
    ("BOC", boc.fetch_offers),
    ("NDB", ndb.fetch_offers),
    ("Peoples Bank", peoples.fetch_offers),
    ("DFCC", dfcc.fetch_offers),
]

OUTPUT = Path(__file__).parent.parent / "data" / "offers.json"

# Every bank names its categories differently ("Dining" vs "Food &
# Restaurants"), so map them onto one shared set for the app's filter chips.
CANONICAL_CATEGORY = {
    "dining": "Dining",
    "food & restaurants": "Dining",
    "hotel": "Hotels",
    "hotels": "Hotels",
    "leisure": "Hotels",
    "travel": "Travel",
    "travel and leisure": "Travel",
    "travel & leisure": "Travel",
    "online": "Online",
    "online shopping": "Online",
    "supermarkets": "Supermarkets",
    "super markets": "Supermarkets",
    "shopping": "Shopping",
    "fashion": "Fashion",
    "clothing & accessories": "Fashion",
    "electronics & furniture": "Electronics & Furniture",
    "electronics": "Electronics & Furniture",
    "household": "Electronics & Furniture",
    "health and insurance": "Health",
    "health & beauty": "Health",
    "hospitals": "Health",
    "jewellery": "Jewellery",
    "education": "Education",
    "autocare": "Auto",
    "automobile": "Auto",
    "seasonal offers": "Seasonal",
    "premium offers": "Premium",
    "priority circle": "Premium",
    "the club": "Premium",
    "club elite": "Premium",
    "visa offers": "Other",
    "mastercard offers": "Other",
    "lifestyle": "Lifestyle",
    "wellness": "Health",
    "jewelry": "Jewellery",
    "online deals": "Online",
    "solar solutions": "Other",
    "other": "Other",
}


def normalize_category(label):
    return CANONICAL_CATEGORY.get((label or "").strip().lower(), "Other")


def load_previous():
    """Offers from the last successful run, grouped by bank."""
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except Exception:
        return {}
    by_bank = {}
    for o in old.get("offers", []):
        by_bank.setdefault(o["bank"], []).append(o)
    return by_bank


def main():
    previous = load_previous()
    all_offers = []
    errors = []
    for bank_name, fetch in BANKS:
        print(f"Fetching {bank_name} offers...", flush=True)
        try:
            offers = fetch()
            if not offers:
                raise RuntimeError("no offers found (site layout may have changed)")
            for o in offers:
                o["category"] = normalize_category(o["category"])
            print(f"  -> {len(offers)} offers")
            all_offers.extend(offers)
        except Exception as exc:
            # A site being down for a day shouldn't wipe that bank from the
            # app, so fall back to the offers from the last good run.
            kept = previous.get(bank_name, [])
            print(f"  !! FAILED: {exc} (keeping {len(kept)} previous offers)")
            errors.append(f"{bank_name}: {exc}")
            all_offers.extend(kept)

    # Record each offer's end date in one clean format (YYYY-MM-DD) for the
    # apps, and drop offers that have already ended.
    today = dt.datetime.now(SL_TIME).date()
    live = []
    for o in all_offers:
        end = end_date(o.get("period"), today)
        o["end_date"] = end.isoformat() if end else ""
        if end is None or end >= today:
            live.append(o)
    print(f"\nDropped {len(all_offers) - len(live)} expired offers")
    all_offers = live

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "offer_count": len(all_offers),
        "banks": sorted({o["bank"] for o in all_offers}),
        "offers": all_offers,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print(f"\nSaved {len(all_offers)} offers to {OUTPUT}")
    if errors:
        print("Errors:", *errors, sep="\n  ")
        if os.environ.get("GITHUB_ACTIONS"):
            # Shows as a yellow warning on the GitHub run without failing it,
            # so the data from the banks that did work still gets published.
            for e in errors:
                print(f"::warning title=Bank scrape failed::{e}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()

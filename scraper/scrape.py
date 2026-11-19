"""Credit Card Offers LK scraper — collects credit card offers from Sri Lankan banks.

Run:  python scraper/scrape.py
Writes all offers to data/offers.json, which the app reads.

To add a bank: create scraper/banks/<bank>.py with a fetch_offers() function
that returns a list of offer dicts, then add it to BANKS below.
"""

import datetime as dt
import json
import urllib.parse
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from banks import boc, combank, dfcc, hnb, ndb, ntb, peoples, sampath, seylan
from dates import end_date
from dedupe import merge_duplicates

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
    "health": "Health",
    "healthcare": "Health",
    "health beauty": "Health",
    "auto": "Auto",
    "supermarket": "Supermarkets",
    "zero plans": "Instalment Plans",
    "installments": "Instalment Plans",
    "premium card offers": "Premium",
    "private banking": "Premium",
}

# When a bank gives no useful category, guess one from the offer's words.
# First match wins, so more specific groups come first.
KEYWORD_CATEGORY = [
    ("Health", r"hospital|\bin-?(door )?patients?\b"),  # before Hotels: "room rates for in-patients"
    ("Instalment Plans", r"\b0\s*% (interest|installment|instalment)|easy payment|installment plan|instalment plan|\bipp\b|\bepp\b|\becip\b"),
    ("Hotels", r"hotel|resort|villa|bungalow|\bspa\b|lodge|\binn\b|retreat|cabana|glamping|suites?\b|stay\b|half[- ]board|full[- ]board|rack rates?|room (rates?|bookings?)|bed (and|&) breakfast|accommodation|\bnights?\b"),
    ("Travel", r"airline|airways|\bflight|travels?\b|tours?\b|holiday|duty free|airport|lounge"),
    ("Dining", r"restaurant|cafe|café|pizza|burger|\bkfc\b|dining|bakery|kitchen|grill|buffet|dine\b|food\b|bistro|\bpub\b|coffee|tea\b|cake|dessert"),
    ("Supermarkets", r"supermarket|keells|cargills|food city|glomark|\barpico super|laugfs super|spar\b"),
    ("Fashion", r"fashion|clothing|apparel|saree|textile|boutique|shoe|footwear|\bodel\b|nolimit|cotton collection|kelly felder|\bwear\b"),
    ("Jewellery", r"jewel|\bvogue\b"),  # not "gold": Visa Gold is a card
    ("Electronics & Furniture", r"electronic|mobile phone|smartphone|laptop|computer|\btv\b|appliance|furniture|singer|abans|damro|softlogic|singhagiri|\bapple\b|samsung"),
    ("Health", r"hospital|clinic|medical|pharmacy|health|dental|optical|optician|salon|beauty|wellness|ayurved|fitness|\bgym\b|channel"),
    ("Auto", r"tyre|\btire|vehicle|motor|\bauto|car care|fuel|service station|battery|toyota|honda"),
    ("Education", r"school|educat|universit|college|campus|tuition|course|institute|academy|\bexam"),
    ("Online", r"online|\.lk\b|\.com\b|daraz|app\b|e-?commerce|website|pickme|uber"),
]


def guess_category(o):
    text = " ".join(o.get(k) or "" for k in ("merchant", "description", "discount")).lower()
    for label, rx in KEYWORD_CATEGORY:
        if re.search(rx, text):
            return label
    return "Other"


# Bank labels that lump several kinds of offer together: use the label only
# when the offer's own words don't say what it is.
MIXED_CATEGORIES = {"travel and leisure", "travel & leisure", "leisure", "lifestyle",
                    "seasonal offers", "premium offers", "visa offers", "mastercard offers"}

UNMAPPED = {}  # bank category labels not in CANONICAL_CATEGORY -> count


def normalize_category(label):
    key = (label or "").strip().lower()
    if key not in CANONICAL_CATEGORY:
        UNMAPPED[key] = UNMAPPED.get(key, 0) + 1
    return CANONICAL_CATEGORY.get(key, "Other")


# Some bank pages are saved with the wrong text encoding, so "’" arrives as
# "â€™". Re-decode those, and drop leftover replacement characters.
MOJIBAKE = re.compile("[ÂÃâ][\u0080-¿Œ-ƒˆ-˜–-™]")


def clean_url(url):
    """Turn "&amp;" back into "&" and encode spaces, so links work everywhere."""
    if not url:
        return url
    # Only "&amp;" and numeric codes: a real "&copy=" query must stay as is.
    url = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), url.strip().replace("&amp;", "&"))
    return urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=%~")


def clean_text(s):
    if not isinstance(s, str) or not s:
        return s
    for _ in range(3):  # some text was mangled twice
        if not MOJIBAKE.search(s):
            break
        try:
            s = s.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
    s = s.replace("�", "")
    s = re.sub("(Ã‚)?Â(?=[\\s\\W]|$)", "", s)  # stray "Â" / "Ã‚Â"
    return re.sub(r"[ \t]{2,}", " ", s).strip()


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
                for k, v in o.items():
                    if k in ("image_url", "source_url"):
                        o[k] = clean_url(v)
                    elif isinstance(v, str):
                        o[k] = clean_text(v)
                raw_cat = (o["category"] or "").strip().lower()
                o["category"] = normalize_category(o["category"])
                if o["category"] == "Other":
                    o["category"] = guess_category(o)
                elif raw_cat in MIXED_CATEGORIES:
                    # e.g. BOC's "Travel and Leisure" is mostly hotels
                    guess = guess_category(o)
                    if guess != "Other":
                        o["category"] = guess
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
    if UNMAPPED:
        print("Categories shown as 'Other':",
              ", ".join(f"{k or '(none)'} x{n}" for k, n in sorted(UNMAPPED.items(), key=lambda x: -x[1])))
    all_offers = merge_duplicates(live)
    print(f"Merged {len(live) - len(all_offers)} duplicate listings")

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

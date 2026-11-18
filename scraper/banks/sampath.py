"""Scraper for Sampath Bank credit card offers.

Sampath's offers site (https://www.sampath.lk/sampath-cards/credit-card-offer)
loads its data from a JSON API. The API only answers when the request carries
the same custom headers the website sends: `locale: en` and `platform: web`.
"""

import html
import json
import re
import urllib.request

BASE = "https://www.sampath.lk/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (CardOffersCollection/0.1; personal offer aggregator)",
    "Accept": "application/json",
    "locale": "en",
    "platform": "web",
}
PAGE_SIZE = 50


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _strip_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)  # &amp; &reg; &#39; etc.
    return re.sub(r"\s+", " ", text).strip()


def _detect_card_types(text):
    """Guess which card networks an offer applies to from its description."""
    t = text.lower()
    cards = set()
    if "mastercard" in t or "master card" in t:
        cards.add("mastercard")
    if "visa" in t:
        cards.add("visa")
    if "american express" in t or "amex" in t:
        cards.add("amex")
    if "debit" in t:
        cards.add("debit")
    if "credit" in t:
        cards.add("credit")
    return sorted(cards)


def fetch_offers():
    """Return a list of normalized offers from every enabled category."""
    categories = [c for c in _get(f"{BASE}/offer-catergories") if c.get("enable")]
    offers = []
    seen_ids = set()

    for cat in categories:
        value, label = cat["value"], cat["label"]
        page = 1
        while True:
            data = _get(
                f"{BASE}/card-promotions?category={value}"
                f"&page_number={page}&size={PAGE_SIZE}"
            )
            items = data.get("data", [])
            for item in items:
                uid = f"sampath-{item['id']}"
                if uid in seen_ids:  # same offer can appear in two categories
                    continue
                seen_ids.add(uid)
                description = _strip_html(item.get("description"))
                offers.append({
                    "id": uid,
                    "bank": "Sampath Bank",
                    "merchant": _strip_html(item.get("company_name")),
                    "discount": _strip_html(item.get("discount")),
                    "description": description,
                    "category": label,
                    "city": (item.get("city") or "").strip(),
                    "period": _strip_html(item.get("promotion_period")),
                    "card_types": _detect_card_types(description),
                    "details": _strip_html(item.get("promotion_details")),
                    "terms": _strip_html(item.get("terms_and_conditions")),
                    "image_url": item.get("image_url") or "",
                    "source_url": "https://www.sampath.lk/sampath-cards/credit-card-offer",
                    "updated_at": item.get("updated_at") or "",
                })
            total = data.get("total", 0)
            if page * PAGE_SIZE >= total or not items:
                break
            page += 1

    return offers

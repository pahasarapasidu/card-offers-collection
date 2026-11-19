"""Scraper for Sampath Bank credit card offers.

Sampath's offers site (https://www.sampath.lk/sampath-cards/credit-card-offer)
loads its data from a JSON API. The API only answers when the request carries
the same custom headers the website sends: `locale: en` and `platform: web`.
"""

import datetime
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
    if re.search(r"\bmastercard\b", t) or re.search(r"\bmaster card\b", t):
        cards.add("mastercard")
    if re.search(r"\bvisa\b", t):
        cards.add("visa")
    if re.search(r"\bamerican express\b", t) or re.search(r"\bamex\b", t):
        cards.add("amex")
    if re.search(r"\bdebit\b", t):
        cards.add("debit")
    if re.search(r"\bcredit\b", t):
        cards.add("credit")
    return sorted(cards)


def _value(item, key):
    """A field's text; the API writes missing values as the string "None"."""
    text = _strip_html(item.get(key))
    return "" if text in ("None", "null") else text


SL_TIME = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _date(ms):
    """API timestamps are milliseconds since 1970; return a Sri Lanka date."""
    try:
        return datetime.datetime.fromtimestamp(int(ms) / 1000, SL_TIME).date()
    except (TypeError, ValueError, OSError):
        return None


def _period(item):
    text = _strip_html(item.get("promotion_period"))
    if text:
        return text
    start, end = _date(item.get("display_on")), _date(item.get("expire_on"))
    if start and end:
        return f"{start} to {end}"
    return f"Valid until {end}" if end else ""


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
                description = _value(item, "description")
                offers.append({
                    "id": uid,
                    "bank": "Sampath Bank",
                    "merchant": _value(item, "company_name"),
                    # "discount" is always empty in the API; the badge text
                    # lives in "short_discount" (e.g. "20% Discount").
                    "discount": _value(item, "short_discount") or _value(item, "discount"),
                    "description": description,
                    "category": label,
                    "city": (item.get("city") or "").strip(),
                    "period": _period(item),
                    "card_types": _detect_card_types(description),
                    "details": _value(item, "promotion_details"),
                    "terms": _value(item, "terms_and_conditions"),
                    "image_url": item.get("image_url") or "",
                    "source_url": "https://www.sampath.lk/sampath-cards/credit-card-offer",
                    "updated_at": item.get("updated_at") or "",
                })
            total = data.get("total", 0)
            if page * PAGE_SIZE >= total or not items:
                break
            page += 1

    return offers

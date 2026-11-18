"""Scraper for NDB Bank card offers.

https://www.ndbbank.com/cards/card-offers is server-rendered. Each offer is
a <div class="card offer-card"> inside an <a href="/cards/card-offers/
offer-details/<id>"> with a banner image, a merchant logo, a title (h5),
the merchant name, a card-type line ("Credit cards") and a validity date.
"""

import html
import re
import urllib.request

URL = "https://www.ndbbank.com/cards/card-offers"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

OFFER_RE = re.compile(
    r'<a href="/cards/card-offers/offer-details/(?P<id>\d+)"[^>]*>\s*'
    r'<div class="card offer-card[^"]*">.*?'
    r'<img src="(?P<img>[^"]*)"[^>]*class="card-img-top"[^>]*/>.*?'
    r'<h5 class="card-title ndbcolor">(?P<title>.*?)</h5>\s*'
    r'<p class="card-title">(?P<merchant>.*?)</p>\s*'
    r'<p class="text-muted[^"]*">(?P<cardline>.*?)</p>.*?'
    r'<p class="offer-date[^"]*">(?P<period>.*?)</p>',
    re.DOTALL,
)


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _detect_card_types(title, cardline):
    t = f"{title} {cardline}".lower()
    cards = set()
    if "mastercard" in t:
        cards.add("mastercard")
    if "visa" in t:
        cards.add("visa")
    if "amex" in t or "american express" in t:
        cards.add("amex")
    if "debit" in t:
        cards.add("debit")
    if "credit" in t:
        cards.add("credit")
    return sorted(cards)


def _discount_from_text(text):
    m = re.search(r"(up to\s+)?\d{1,3}\s*%(\s*(off|discount|savings?))?", text, re.I)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


# NDB's listing has no category labels, so guess one from the offer text.
CATEGORY_HINTS = [
    ("Dining", ["restaurant", "dining", "dine", "cafe", "pizza", "buffet", "bistro"]),
    ("Hotels", ["hotel", "resort", "villa", "stay", "room"]),
    ("Supermarkets", ["supermarket", "food city", "keells", "glomark", "spar"]),
    ("Fashion", ["fashion", "clothing", "wear", "apparel", "saree", "salon"]),
    ("Electronics & Furniture", ["electronics", "furniture", "appliance", "singer", "abans", "damro"]),
    ("Jewellery", ["jewel", "gems", "diamond", "gold"]),
    ("Health", ["hospital", "pharmacy", "wellness", "spa", "medical", "optical"]),
    ("Travel", ["travel", "air", "flight", "tour", "taxi"]),
    ("Education", ["education", "campus", "school", "course"]),
    ("Online", ["online", "daraz", ".lk", "delivery"]),
    ("Auto", ["auto", "tyre", "vehicle", "car "]),
]


def _guess_category(text):
    t = text.lower()
    for label, words in CATEGORY_HINTS:
        if any(w in t for w in words):
            return label
    return "Other"


def fetch_offers():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = resp.read().decode("utf-8", "replace")

    offers = []
    seen = set()
    for m in OFFER_RE.finditer(page):
        uid = f"ndb-{m.group('id')}"
        if uid in seen:
            continue
        seen.add(uid)

        title = _clean(m.group("title"))
        merchant = _clean(m.group("merchant"))
        period = _clean(m.group("period"))
        offers.append({
            "id": uid,
            "bank": "NDB",
            "merchant": merchant or title,
            "discount": _discount_from_text(title),
            "description": title,
            "category": _guess_category(f"{title} {merchant}"),
            "city": "",
            "period": period,
            "card_types": _detect_card_types(title, _clean(m.group("cardline"))),
            "details": "",
            "terms": "",
            "image_url": m.group("img").strip(),
            "source_url": f"https://www.ndbbank.com/cards/card-offers/offer-details/{m.group('id')}",
            "updated_at": "",
        })
    return offers

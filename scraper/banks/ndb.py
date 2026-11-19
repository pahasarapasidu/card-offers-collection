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
    if re.search(r"\bmastercard\b", t):
        cards.add("mastercard")
    if re.search(r"\bvisa\b", t):
        cards.add("visa")
    if re.search(r"\bamex\b", t) or re.search(r"\bamerican express\b", t):
        cards.add("amex")
    if re.search(r"\bdebit\b", t):
        cards.add("debit")
    if re.search(r"\bcredit\b", t):
        cards.add("credit")
    return sorted(cards)


def _discount_from_text(text):
    m = re.search(r"(up to\s+)?\d{1,3}\s*%(\s*(off|discount|savings?))?", text, re.I)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


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
            # NDB gives no categories; scrape.py's shared guesser fills it in.
            "category": "Other",
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

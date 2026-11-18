"""Scraper for Commercial Bank (ComBank) card offers.

https://www.combank.lk/rewards-promotions renders every offer directly in the
page HTML (no JSON API), so we parse the HTML. Each offer is an
<a class="reward ..."> block containing an image, a discount tag, a category,
a title and a validity line.
"""

import html
import re
import urllib.request

URL = "https://www.combank.lk/rewards-promotions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

OFFER_RE = re.compile(
    r'<a class="reward[^"]*"\s+href="(?P<href>[^"]+)">\s*'
    r'<div class="reward-image" style="background-image: url\(\'(?P<img>[^\']*)\'\)"></div>'
    r'(?P<body>.*?)</a>',
    re.DOTALL,
)
TAG_RE = re.compile(r'<div class="offer-tag[^"]*">(.*?)</div>', re.DOTALL)
CATEGORY_RE = re.compile(r'<p class="category">(.*?)</p>', re.DOTALL)
TITLE_RE = re.compile(r"<h3>(.*?)</h3>", re.DOTALL)
DATE_RE = re.compile(r'<p class="valid-date">(.*?)</p>', re.DOTALL)


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _detect_card_types(text):
    t = text.lower()
    cards = set()
    if "mastercard" in t:
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
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = resp.read().decode("utf-8", "replace")

    offers = []
    for n, m in enumerate(OFFER_RE.finditer(page)):
        body = m.group("body")
        title = _clean((TITLE_RE.search(body) or [None, ""])[1] if TITLE_RE.search(body) else "")
        tag = _clean(TAG_RE.search(body).group(1)) if TAG_RE.search(body) else ""
        category = _clean(CATEGORY_RE.search(body).group(1)) if CATEGORY_RE.search(body) else "Other"
        period = _clean(DATE_RE.search(body).group(1)) if DATE_RE.search(body) else ""

        href = m.group("href")
        # Stable id from the offer's own URL slug
        slug = href.rstrip("/").rsplit("/", 1)[-1][:80] or f"n{n}"
        offers.append({
            "id": f"combank-{slug}",
            "bank": "Commercial Bank",
            "merchant": title,
            "discount": tag,
            "description": title,
            "category": category,
            "city": "",
            "period": period,
            "card_types": _detect_card_types(title),
            "details": "",
            "terms": "",
            "image_url": m.group("img"),
            "source_url": href,
            "updated_at": "",
        })
    return offers

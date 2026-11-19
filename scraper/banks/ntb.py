"""Scraper for Nations Trust Bank (NTB) card promotions.

https://www.nationstrust.com/promotions is server-rendered. Each offer sits
in a <div class="... grid-item <category>"> block holding a promo-box with
an image, a category tag, merchant (h6), discount (h5), validity (small)
and a Learn More link. NTB issues American Express cards in Sri Lanka.
"""

import html
import re
import urllib.request

URL = "https://www.nationstrust.com/promotions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

BOX_RE = re.compile(
    r'class="[^"]*grid-item\s+(?P<cat>[a-z0-9-]+)">\s*'
    r'<div class="promo-box">.*?'
    r'<img src="(?P<img>[^"]*)"[^>]*>.*?'
    r'(?:<h6>(?P<merchant>.*?)</h6>\s*)?'
    r'<h5>(?P<discount>.*?)</h5>.*?'
    r"<small>(?P<period>.*?)</small>\s*"
    r'<a href="(?P<href>[^"]+)"',
    re.DOTALL,
)

CATEGORY_LABELS = {
    "dining": "Dining",
    "clothing": "Fashion",
    "regional-offers": "Travel",
    "hotels-resorts": "Hotels",
    "homecare-electronics": "Electronics & Furniture",
    "online": "Online",
    "supermarket": "Supermarkets",
    "health-beauty": "Health",
    "jewellery": "Jewellery",
    "education": "Education",
    "automobile": "Auto",
    "leisure": "Travel",
    "lifestyle": "Lifestyle",
}


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_offers():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = resp.read().decode("utf-8", "replace")

    offers = []
    seen = set()
    for m in BOX_RE.finditer(page):
        href = m.group("href")
        slug = href.rstrip("/").rsplit("/", 1)[-1][:80]
        uid = f"ntb-{slug}"
        if uid in seen:
            continue
        seen.add(uid)

        # Boxes with no validity date aren't offers: they're town landing
        # pages ("Exclusive offers in Kandy") and the general T&C page.
        if not _clean(m.group("period")):
            continue

        cat_slug = m.group("cat")
        merchant = _clean(m.group("merchant"))
        discount = _clean(m.group("discount"))

        offers.append({
            "id": uid,
            "bank": "Nations Trust",
            "merchant": merchant or discount,
            "discount": discount,
            "description": f"{discount} at {merchant}" if merchant else discount,
            "category": CATEGORY_LABELS.get(cat_slug, cat_slug.replace("-", " ").title()),
            "city": "",
            "period": _clean(m.group("period")),
            # NTB is Sri Lanka's American Express issuer; most offers apply
            # to Amex and their Visa/Mastercard range alike, and the listing
            # doesn't say which, so leave it open (= applies to all).
            "card_types": [],
            "details": "",
            "terms": "",
            "image_url": m.group("img"),
            "source_url": href,
            "updated_at": "",
        })
    return offers

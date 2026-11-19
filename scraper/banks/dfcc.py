"""Scraper for DFCC Bank credit card offers.

The index page https://www.dfcc.lk/credit-card-offers links to one
server-rendered Next.js page per category (e.g. /dining-promotion-credit).
Each offer is a cardOfferItem block with an image, a description
(cardOfferText), a validity line (cardOfferValid), a percentage box and a
Read More link. DFCC also services former Standard Chartered cards.
"""

import html
import re
import urllib.request

SITE = "https://www.dfcc.lk/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

CATEGORIES = {
    "dining-promotion-credit": "Dining",
    "online-promotion": "Online",
    "0-easy-payment-plans-promotion": "Other",
    "clothing-and-retail": "Fashion",
    "hotels-credit": "Hotels",
    "home-appliances-promotion-2": "Electronics & Furniture",
    "gifts-and-watches": "Shopping",
    "health-and-wellness": "Health",
    "kids-and-baby": "Shopping",
    "opticians-promotion": "Health",
    "jewellery": "Jewellery",
    "travel-promotion": "Travel",
    "autocare-promotion": "Auto",
    "visa-offers": "Other",
    "mastercard-offers": "Other",
    "other-credit": "Other",
}

ITEM_RE = re.compile(r'<div class="cardOfferItem')
IMG_RE = re.compile(r'class="offerMainImage"[^>]*src="([^"]*)"')
TEXT_RE = re.compile(r'<p class="cardOfferText">(.*?)</p>', re.DOTALL)
VALID_RE = re.compile(r'<p class="cardOfferValid">(.*?)</p>', re.DOTALL)
HREF_RE = re.compile(r'<a href="(/cards/cards-promotions/[^"]+)"')
PCT_RE = re.compile(r'<div class="Offerpercentage"><p>(.*?)</p>', re.DOTALL)


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _detect_card_types(text):
    t = text.lower()
    cards = set()
    if re.search(r"\bmastercard\b", t):
        cards.add("mastercard")
    if re.search(r"\bvisa\b", t):
        cards.add("visa")
    if re.search(r"\bdebit\b", t):
        cards.add("debit")
    if re.search(r"\bcredit\b", t):
        cards.add("credit")
    return sorted(cards)


def _merchant_from_text(text):
    """The description usually reads '... at <Merchant>. Offer valid on ...'."""
    first = text.split(". Offer valid")[0]
    m = re.search(r"\bat\s+(.+)$", first)
    return m.group(1).strip(" .") if m else first[:60]


def fetch_offers():
    offers = []
    seen = set()
    failed = 0
    for slug, label in CATEGORIES.items():
        try:
            req = urllib.request.Request(SITE + slug, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as resp:
                page = resp.read().decode("utf-8", "replace")
        except Exception:
            failed += 1  # a page may be missing; too many means the site is down
            continue

        starts = [m.start() for m in ITEM_RE.finditer(page)]
        for n, start in enumerate(starts):
            end = starts[n + 1] if n + 1 < len(starts) else len(page)
            seg = page[start:end]

            def find(rx):
                f = rx.search(seg)
                return _clean(f.group(1)) if f else ""

            href = find(HREF_RE)
            desc = find(TEXT_RE)
            if not desc:
                continue
            uid = "dfcc-" + (href.rsplit("/", 1)[-1] if href else re.sub(r"\W+", "-", desc[:50]).lower())
            if uid in seen:
                continue
            seen.add(uid)

            offers.append({
                "id": uid,
                "bank": "DFCC",
                "merchant": _merchant_from_text(desc),
                "discount": find(PCT_RE),
                "description": desc,
                "category": label,
                "city": "",
                "period": find(VALID_RE),
                "card_types": _detect_card_types(desc),
                "details": "",
                "terms": "",
                "image_url": find(IMG_RE),
                "source_url": "https://www.dfcc.lk" + href if href else SITE + slug,
                "updated_at": "",
            })
    pages = len(CATEGORIES)
    if failed > pages // 4:
        # Better to keep yesterday's offers (scrape.py falls back) than
        # to publish a list with whole categories silently missing.
        raise RuntimeError(f"{failed} of {pages} category pages failed to load")
    if failed:
        print(f"  (skipped {failed} of {pages} category pages)")
    return offers

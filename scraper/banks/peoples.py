"""Scraper for People's Bank card offers.

https://www.peoplesbank.lk/special-offers/ links to WordPress category pages
(https://www.peoplesbank.lk/promotion-category/<slug>/?cardType=credit_card
or debit_card). Each category page holds <article class="offer-card"> blocks
with a discount badge, an image, the merchant name and a validity range.
Offers are deduped by their promotion URL.
"""

import html
import re
import urllib.request

BASE = "https://www.peoplesbank.lk/promotion-category/{slug}/?cardType={card}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

CATEGORIES = {
    "leisure": "Hotels",
    "restaurants": "Dining",
    "clothing": "Fashion",
    "online-stores": "Online",
    "home-care-electronics": "Electronics & Furniture",
    "supermarkets": "Supermarkets",
    "jewellers": "Jewellery",
    "wellness": "Health",
    "auto-mobile": "Auto",
    "travel": "Travel",
    "book-store": "Education",
    "others": "Other",
}
CARD_TYPES = ["credit_card", "debit_card"]

# Split into one segment per <article>, then pull fields per segment
# (a trailing optional group after a lazy .*? never matches).
ARTICLE_RE = re.compile(r'<article class="offer-card"', re.DOTALL)
BADGE_RE = re.compile(r'<div class="discount-badge">(.*?)</div>', re.DOTALL)
HREF_RE = re.compile(r'<a href="([^"]+)"')
IMG_RE = re.compile(r'<img src="([^"]*)"')
NAME_RE = re.compile(r'<div class="promo-short fw-medium">(.*?)</div>', re.DOTALL)
PERIOD_RE = re.compile(r'<span class="fw-medium valid-date">(.*?)</span>', re.DOTALL)


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def fetch_offers():
    offers = []
    seen = set()
    # People's Bank publishes the same deal twice, once per card type, on
    # separate pages. Merge those into one offer valid for both.
    by_deal = {}
    for slug, label in CATEGORIES.items():
        for card in CARD_TYPES:
            url = BASE.format(slug=slug, card=card)
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=60) as resp:
                    page = resp.read().decode("utf-8", "replace")
            except Exception:
                continue  # a category/cardType combo may not exist

            starts = [a.start() for a in ARTICLE_RE.finditer(page)]
            for n, start in enumerate(starts):
                end = starts[n + 1] if n + 1 < len(starts) else len(page)
                seg = page[start:end]

                href_m = HREF_RE.search(seg)
                name_m = NAME_RE.search(seg)
                if not href_m or not name_m:
                    continue
                href = href_m.group(1)
                if href in seen:
                    continue
                seen.add(href)

                def find(rx):
                    f = rx.search(seg)
                    return _clean(f.group(1)) if f else ""

                badge = find(BADGE_RE)
                name = _clean(name_m.group(1))
                period = find(PERIOD_RE)
                card_type = "credit" if card == "credit_card" else "debit"

                key = (name.lower(), badge, period)
                twin = by_deal.get(key)
                if twin:
                    if card_type not in twin["card_types"]:
                        twin["card_types"] = sorted(twin["card_types"] + [card_type])
                        twin["description"] = (
                            f"{badge + ' off at ' if badge else ''}{name} "
                            "with Peoples Bank credit & debit cards"
                        )
                    continue

                slug_id = href.rstrip("/").rsplit("/", 1)[-1][:80]
                offer = {
                    "id": f"peoples-{slug_id}",
                    "bank": "Peoples Bank",
                    "merchant": name,
                    "discount": f"{badge} off" if badge else "",
                    "description": f"{badge + ' off at ' if badge else ''}{name} with Peoples Bank {card_type} cards",
                    "category": label,
                    "city": "",
                    "period": period,
                    "card_types": [card_type],
                    "details": "",
                    "terms": "",
                    "image_url": find(IMG_RE) and IMG_RE.search(seg).group(1),
                    "source_url": href,
                    "updated_at": "",
                }
                by_deal[key] = offer
                offers.append(offer)
    return offers

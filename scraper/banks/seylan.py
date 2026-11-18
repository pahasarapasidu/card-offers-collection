"""Scraper for Seylan Bank card promotions.

https://www.seylan.lk/promotions is one huge server-rendered page (~7 MB)
holding every offer as a bootstrap card. Each card has an image, a title,
a short description, a READ MORE link, and a Google-Calendar link whose
`dates=YYYYMMDD/YYYYMMDD` parameter carries the promotion period.

The READ MORE URL often encodes a category:
  https://www.seylan.lk/promotions/cards/<category>/<merchant-slug>
"""

import html
import re
import urllib.request

URL = "https://www.seylan.lk/promotions"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

CARD_RE = re.compile(
    r'<img class="new-promotion-img card-img-top" src="(?P<img>[^"]*)"[^>]*>.*?'
    r'<h5 class="card-title new-promotion-title"[^>]*>(?P<title>.*?)</h5>\s*'
    r'<p class="new-promotion-text new-promotion-dis">(?P<desc>.*?)</p>.*?'
    r'<a href="(?P<href>[^"]+)" class="btn new-promotion-btn">',
    re.DOTALL,
)
# The calendar link appears shortly before each card's image.
CAL_RE = re.compile(r"dates=(\d{8})/(\d{8})")
CAT_RE = re.compile(r"seylan\.lk/promotions/cards/([^/]+)/")

# Map Seylan's URL slugs to readable category labels.
SLUG_LABELS = {
    "supermarket": "Supermarkets",
    "style": "Fashion",
    "shoes-accessories": "Fashion",
    "kiddies": "Shopping",
    "gadgets": "Electronics & Furniture",
    "health": "Health",
    "eye-care": "Health",
    "local-travel": "Travel",
    "overseas-travel": "Travel",
    "dining": "Dining",
    "restaurants": "Dining",
    "lifestyle": "Lifestyle",
    "jewellery": "Jewellery",
    "education": "Education",
    "automobile": "Auto",
    "home-garden": "Electronics & Furniture",
    "online": "Online",
}


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
    if "amex" in t or "american express" in t:
        cards.add("amex")
    if "debit" in t:
        cards.add("debit")
    if "credit" in t:
        cards.add("credit")
    return sorted(cards)


def _discount_from_text(text):
    m = re.search(r"(up to\s+)?\d{1,3}\s*%(\s*(off|discount))?", text, re.I)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def _fmt_date(d):  # 20261130 -> 2026-11-30
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"


def fetch_offers():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        page = resp.read().decode("utf-8", "replace")

    offers = []
    seen = set()
    last_end = 0
    for m in CARD_RE.finditer(page):
        href = m.group("href")
        if href in seen:
            continue
        seen.add(href)

        # Seylan's template leaks broken attribute text into the <h5> tag
        # (e.g. '?name=".$result->slug}}">PEARL BAY'), so keep only what
        # comes after the last '">'.
        raw_title = m.group("title")
        if '">' in raw_title:
            raw_title = raw_title.rsplit('">', 1)[-1]
        title = _clean(raw_title)
        desc = _clean(m.group("desc"))

        # Period: nearest calendar link between the previous card and this one.
        cal = CAL_RE.search(page, last_end, m.start())
        period = ""
        if cal:
            period = f"{_fmt_date(cal.group(1))} to {_fmt_date(cal.group(2))}"
        last_end = m.end()

        cat_m = CAT_RE.search(href)
        category = SLUG_LABELS.get(cat_m.group(1), cat_m.group(1).replace("-", " ").title()) if cat_m else "Other"

        slug = href.rstrip("/").rsplit("/", 1)[-1][:80]
        offers.append({
            "id": f"seylan-{slug}",
            "bank": "Seylan Bank",
            "merchant": title,
            "discount": _discount_from_text(desc),
            "description": desc,
            "category": category,
            "city": "",
            "period": period,
            "card_types": _detect_card_types(desc),
            "details": "",
            "terms": "",
            "image_url": m.group("img"),
            "source_url": href,
            "updated_at": "",
        })
    return offers

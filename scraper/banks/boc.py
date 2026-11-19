"""Scraper for Bank of Ceylon (BOC) card offers.

https://www.boc.lk/personal-banking/card-offers is server-rendered. Each
offer is an <a href=".../card-offers/<category>/<slug>/product"> block with
a discount panel, a logo image, the merchant name (h4), a location, a short
description and an expiration date. The same offer can appear both in the
"exclusive offers" slider and the main grid, so we dedupe by URL.
"""

import html
import re
import urllib.request

URL = "https://www.boc.lk/personal-banking/card-offers"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CardOffersCollection/0.1",
    "Accept": "text/html",
}

# Split the page into one segment per offer link, then pull each field out
# of its segment separately (optional fields at the end of one big regex
# never match, because the lazy .*? before them wins).
LINK_RE = re.compile(
    r'<a href="(?P<href>https://www\.boc\.lk/personal-banking/card-offers/'
    r'(?P<cat>[^/"]+)/[^/"]+/product)"'
)
TAG_RE = re.compile(r'<div class="offer">(.*?)</div>', re.DOTALL)
IMG_RE = re.compile(r'<img class="offer-logo" src="([^"]*)"')
NAME_RE = re.compile(r"<h4>(.*?)</h4>", re.DOTALL)
LOC_RE = re.compile(r'<p class="location-name">(.*?)</p>', re.DOTALL)
DESC_RE = re.compile(r'<div class="description">(.*?)</div>', re.DOTALL)
EXP_RE = re.compile(r"Expiration date\s*:?\s*</td>\s*<td>(.*?)</td>", re.DOTALL)


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


def fetch_offers():
    req = urllib.request.Request(URL, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        page = resp.read().decode("utf-8", "replace")

    matches = list(LINK_RE.finditer(page))
    offers = []
    seen = set()
    for n, m in enumerate(matches):
        href = m.group("href")
        if href in seen:
            continue
        seen.add(href)

        # This offer's segment runs until the next offer link (or page end).
        end = matches[n + 1].start() if n + 1 < len(matches) else len(page)
        seg = page[m.start():end]

        def find(rx):
            f = rx.search(seg)
            return _clean(f.group(1)) if f else ""

        desc = find(DESC_RE)
        exp = find(EXP_RE)
        slug = href.rstrip("/").rsplit("/", 2)[-2][:80]
        offers.append({
            "id": f"boc-{slug}",
            "bank": "BOC",
            "merchant": find(NAME_RE),
            "discount": find(TAG_RE).replace("* ", "*"),
            "description": desc,
            "category": m.group("cat").replace("-", " ").title(),
            "city": find(LOC_RE),
            "period": f"Until {exp}" if exp else "",
            "card_types": _detect_card_types(desc),
            "details": "",
            "terms": "",
            "image_url": (IMG_RE.search(seg) or [None, ""])[1] if IMG_RE.search(seg) else "",
            "source_url": href,
            "updated_at": "",
        })
    return offers

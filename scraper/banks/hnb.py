"""Scraper for HNB (Hatton National Bank) card promotions.

HNB's site (https://www.hnb.lk/card-promotion) is a React app backed by an
open JSON API at https://venus.hnb.lk/api. Useful endpoints:
  get_all_card_promotion_categories      -> category list
  get_all_web_card_promos?cat=<id>&page=&limit=  -> offers per category
Offer images live under https://assets.hnb.lk/atdi/<thumb>.
"""

import datetime
import html
import json
import re
import urllib.parse
import urllib.request

API = "https://venus.hnb.lk/api"
IMG_BASE = "https://assets.hnb.lk/atdi/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (CardOffersCollection/0.1; personal offer aggregator)",
    "Accept": "application/json",
}
PAGE_SIZE = 100


def _get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _detect_card_types(title, card_type):
    t = title.lower()
    cards = set()
    if card_type:
        # "credit", "debit" or "credit/debit"
        cards.update(p.strip() for p in card_type.lower().split("/") if p.strip())
    if "mastercard" in t:
        cards.add("mastercard")
    if "visa" in t:
        cards.add("visa")
    if "amex" in t or "american express" in t:
        cards.add("amex")
    return sorted(cards)


def _discount_from_title(title):
    m = re.search(r"(up to\s+)?\d{1,3}\s*%(\s*(off|discount))?", title, re.I)
    return re.sub(r"\s+", " ", m.group(0)).strip() if m else ""


def fetch_offers():
    cats = _get(f"{API}/get_all_card_promotion_categories")["data"]
    today = datetime.date.today().isoformat()

    offers = []
    seen = set()
    for cat in cats:
        cat_id, label = cat["id"], cat["category"]
        page = 1
        while True:
            data = _get(
                f"{API}/get_all_web_card_promos"
                f"?cat={cat_id}&page={page}&limit={PAGE_SIZE}"
            )
            items = data.get("data", [])
            for item in items:
                uid = f"hnb-{item['id']}"
                if uid in seen:
                    continue
                seen.add(uid)

                # Skip offers that have already ended.
                to_date = (item.get("to") or "").strip()
                if to_date and to_date < today:
                    continue

                title = _clean(item.get("title"))
                thumb = (item.get("thumb") or "").strip()
                period = ""
                if to_date:
                    period = f"{item.get('valid', 'Valid Until')} {to_date}".strip()

                offers.append({
                    "id": uid,
                    "bank": "HNB",
                    "merchant": _clean(item.get("merchant")) or title,
                    "discount": _discount_from_title(title),
                    "description": title,
                    "category": label,
                    "city": "",
                    "period": period,
                    "card_types": _detect_card_types(title, item.get("cardType")),
                    "details": "",
                    "terms": "",
                    "image_url": IMG_BASE + urllib.parse.quote(thumb) if thumb else "",
                    "source_url": f"https://www.hnb.lk/personal/promotions/card-promotion/card-offers?id={item['id']}",
                    "updated_at": "",
                })
            total_pages = data.get("totalPages", 1)
            if page >= total_pages or not items:
                break
            page += 1

    return offers

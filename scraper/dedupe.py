"""Merge offers a bank lists more than once under slightly different names.

Banks often post the same deal twice: once per category page ("Hotels" and
"Dining"), or once for the shop and once for its website ("Street 82" and
"www.street82.lk"). Two offers count as the same deal when they come from the
same bank, have the same discount and end date, the merchant names match once
web-address parts and company suffixes are removed, and either the picture or
the description is the same.
"""

import re


def _name(m):
    m = (m or "").lower()
    m = re.sub(r"https?://", "", m)
    m = re.sub(r"^www\.", "", m)
    m = re.sub(r"\.(lk|com|net|org|co)(\.[a-z]{2})?\b", "", m)
    m = re.sub(r"\s+with\s+\w+\s+[^|]*\bcards?\b.*$", "", m)  # "X with DFCC Mastercard Credit Card"
    m = re.sub(r"\s+(for|on)\s+(bills?|purchases?|spend)\b.*$", "", m)  # "X for bills above Rs. 5,000"
    m = re.sub(r"\b(outlets?|stores?|showrooms?|branches)\b", "", m)
    m = re.sub(r"\(?\b(pvt|private|ltd|limited|plc)\b\)?\.?", "", m)
    return re.sub(r"[^a-z0-9]", "", m)


def _pct(o):
    m = re.search(r"(\d{1,3})\s*%", (o.get("discount") or "") + " " + (o.get("description") or ""))
    return m.group(1) if m else re.sub(r"\W", "", (o.get("discount") or "").lower())


def _desc(o):
    """Description with the merchant's own name (and credit/debit) taken out."""
    text = (o.get("description") or "").lower()
    for part in (o.get("merchant") or "").lower().split():
        text = text.replace(part, "")
    text = re.sub(r"\b(credit|debit|and)\b|&", "", text)
    text = re.sub(r"\binstall?ments?( plans?)?\b", "installment", text)
    return re.sub(r"[^a-z0-9%]", "", text)


def _core(o):
    """The headline deal: "25% off on selected items + 6 months..." -> "25% off on selected items"."""
    text = (o.get("description") or "").lower()
    text = re.split(r"\s\+\s|\s+at\s|\s+with\s|\.\s", text)[0]
    return re.sub(r"[^a-z0-9%]", "", text)


def merge_key(o):
    return (o["bank"], _name(o["merchant"]), _pct(o), o.get("end_date") or o.get("period"))


def _same_deal(a, b):
    # Shop logos are reused across different deals, so a matching picture
    # only counts when the headline deal matches too.
    da, db = _desc(a), _desc(b)
    if da and da == db:
        return True
    same_image = a.get("image_url") and a.get("image_url") == b.get("image_url")
    return bool(same_image) and len(_core(a)) >= 8 and _core(a) == _core(b)


def _better(a, b):
    """Prefer the copy with the more readable name and more information."""
    def score(o):
        m = o.get("merchant") or ""
        return (not re.search(r"www\.|\.lk\b|\.com\b", m, re.I),
                len(o.get("description") or ""),
                o.get("category") != "Other",
                len(o.get("details") or "") + len(o.get("terms") or ""))
    return a if score(a) >= score(b) else b


def merge_duplicates(offers):
    kept = []
    by_key = {}
    for o in offers:
        k = merge_key(o)
        if not k[1]:
            kept.append(o)
            continue
        for i in by_key.get(k, []):
            if _same_deal(kept[i], o):
                winner = _better(kept[i], o)
                loser = o if winner is kept[i] else kept[i]
                winner["card_types"] = sorted(set(winner.get("card_types") or []) | set(loser.get("card_types") or []))
                if not winner.get("image_url"):
                    winner["image_url"] = loser.get("image_url", "")
                kept[i] = winner
                break
        else:
            by_key.setdefault(k, []).append(len(kept))
            kept.append(o)
    return kept

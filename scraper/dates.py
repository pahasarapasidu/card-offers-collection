"""Work out when an offer ends from the free-text period each bank writes.

Banks write dates in many ways, e.g.
  "2026-09-07 to 2026-11-30"            (HNB, Seylan, Sampath)
  "Until 30 Nov 2026"                   (BOC)
  "Till December 31, 2026"              (People's)
  "Valid from 09 October to 31 December2026"
  "Valid on 19 and 20th December"       (no year)
  "... every month till December 2026"  (month only)
end_date() returns the latest date mentioned, as a datetime.date, or None.
"""

import calendar
import datetime as dt
import re

MONTHS = {}
for _i, _name in enumerate(calendar.month_name):
    if _name:
        MONTHS[_name.lower()] = _i
        MONTHS[_name[:3].lower()] = _i
MONTHS["sept"] = 9

_MON = r"(january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sept|sep|oct|nov|dec)(?![a-z])\.?"
_DAY = r"(\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?:,?\s*(\d{4}))?"

ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DAY_MONTH = re.compile(r"\b" + _DAY + r"\s*(?:of\s+)?" + _MON + _YEAR, re.I)
MONTH_DAY = re.compile(r"\b" + _MON + r"\s*" + _DAY + r"\b" + _YEAR, re.I)
MONTH_YEAR = re.compile(r"\b" + _MON + r"\s*(\d{4})", re.I)
ANY_YEAR = re.compile(r"\b(20\d{2})\b")


def _make(year, month, day):
    try:
        return dt.date(year, month, day)
    except ValueError:
        return None


def end_date(period, today=None):
    if not period:
        return None
    today = today or dt.date.today()
    text = period.replace(" ", " ")
    found = []      # dates with an explicit year
    yearless = []   # (month, day) pairs

    for y, m, d in ISO.findall(text):
        found.append(_make(int(y), int(m), int(d)))

    used = []  # spans already turned into a day+month date
    for rx, order in ((DAY_MONTH, "dm"), (MONTH_DAY, "md")):
        for m in rx.finditer(text):
            if any(a <= m.start() < b for a, b in used):
                continue
            used.append(m.span())
            if order == "dm":
                day, mon, year = m.group(1), m.group(2), m.group(3)
            else:
                mon, day, year = m.group(1), m.group(2), m.group(3)
            month = MONTHS[mon.lower().rstrip(".")]
            if year:
                found.append(_make(int(year), month, int(day)))
            else:
                yearless.append((month, int(day)))

    # "till December 2026" with no day -> last day of that month
    for m in MONTH_YEAR.finditer(text):
        if any(a <= m.start() < b for a, b in used):
            continue
        year, month = int(m.group(2)), MONTHS[m.group(1).lower().rstrip(".")]
        found.append(_make(year, month, calendar.monthrange(year, month)[1]))

    if yearless:
        years = [int(y) for y in ANY_YEAR.findall(text)]
        for month, day in yearless:
            year = max(years) if years else today.year
            d = _make(year, month, day)
            # No year written and the date looks long gone: it means next year.
            if d and not years and (today - d).days > 180:
                d = _make(year + 1, month, day)
            found.append(d)

    found = [d for d in found if d]
    return max(found) if found else None


if __name__ == "__main__":
    samples = [
        "2026-09-07 to 2026-11-30", "Until 30 Nov 2026", "Till December 31, 2026",
        "From December 8, 2026 to December 9, 2026",
        "Till December 30, 2026 ((Excluding 24th & 25th December))",
        "Valid from 09 October to 31 December2026", "Valid on 19 and 20th December",
        "Valid on 28 & 29 November and 23 of December 2026",
        "Valid from 1 Dec 2026 to 15 Jan 2027",
        "Offer valid from 20th to 30th of every month till December 2026",
        "Valid every Thursday from 01st Aug 2026 to 31st Jan 2027",
        "Offer valid till 31st December 2026", "21st & 22nd November",
        "20th - Month end in Every month 2026", "",
    ]
    for s in samples:
        print(f"{str(end_date(s, dt.date(2026, 11, 18))):>10}  <- {s}")

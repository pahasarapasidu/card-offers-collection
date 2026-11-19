"""Automated checks for Credit Card Offers LK.

Run from the project folder:   python -m unittest discover tests -v

Part 1 tests the scraper's helper logic on known examples.
Part 2 checks the real data file (data/offers.json) for problems that
users would notice: expired offers, duplicates, broken text, bad links.
"""

import datetime as dt
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scraper"))

from dates import end_date                       # noqa: E402
from dedupe import merge_duplicates, merge_key   # noqa: E402
from scrape import clean_text, clean_url, guess_category, CANONICAL_CATEGORY, SL_TIME  # noqa: E402

TODAY = dt.date(2026, 11, 18)


def offer(**kw):
    base = dict(id="x", bank="DFCC", merchant="", discount="", description="", category="Other",
                city="", period="", card_types=[], details="", terms="", image_url="",
                source_url="https://example.lk", updated_at="", end_date="2026-12-24")
    base.update(kw)
    return base


# ----------------------------------------------------------------- part 1
class TestDates(unittest.TestCase):
    CASES = {
        "2026-09-07 to 2026-11-30": "2026-11-30",
        "Until 30 Nov 2026": "2026-11-30",
        "Till December 31, 2026": "2026-12-31",
        "From December 8, 2026 to December 9, 2026": "2026-12-09",
        "Till December 30, 2026 ((Excluding 24th & 25th December))": "2026-12-30",
        "Valid from 09 October to 31 December2026": "2026-12-31",
        "Valid on 19 and 20th December": "2026-12-20",
        "Valid on 28 & 29 November and 23 of December 2026": "2026-12-23",
        "Valid from 1 Dec 2026 to 15 Jan 2027": "2027-01-15",
        "Offer valid from 20th to 30th of every month till December 2026": "2026-12-31",
        "Valid every Thursday from 01st Aug 2026 to 31st Jan 2027": "2027-01-31",
        "Offer valid till 31st December 2026": "2026-12-31",
        "Valid On (3rd Wednesday) 2026-11-18": "2026-11-18",
        "Valid till 15th January": "2027-01-15",   # no year, already past this year -> next year
        "From 15 November 2026 to 15 January": "2027-01-15",
        "28 December to 5 January 2027": "2027-01-05",
        "20th - Month end in Every month 2026": "2026-12-31",
        "Valid till 31/12/2026": "2026-12-31",
        "Valid from 01.11.2026 to 15.01.2027": "2027-01-15",
    }

    def test_new_year_rollover(self):
        # In January, "December" without a year means the December just gone.
        jan = dt.date(2027, 1, 5)
        self.assertEqual(str(end_date("Valid on 19 and 20th December", jan)), "2026-12-20")
        self.assertEqual(str(end_date("Valid from 01 November to 31 December", jan)), "2026-12-31")
        self.assertEqual(str(end_date("Valid till 15th January", jan)), "2027-01-15")

    def test_known_formats(self):
        for text, want in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(str(end_date(text, TODAY)), want)

    def test_no_date(self):
        for text in ["", None, "Valid every weekend"]:
            with self.subTest(text=text):
                self.assertIsNone(end_date(text, TODAY))


class TestCleanText(unittest.TestCase):
    def test_repairs_mangled_text(self):
        self.assertEqual(clean_text("GunasekaraÃ¢â‚¬â„¢s"), "Gunasekara’s")
        self.assertEqual(clean_text("Gunasekaraâ€™s"), "Gunasekara’s")
        self.assertEqual(clean_text("Motor CompanyÃ‚Â (Pvt) Ltd"), "Motor Company (Pvt) Ltd")

    def test_leaves_good_text_alone(self):
        for s in ["Café Kandy – 20% off", "Normal text", "Flöör & Décor"]:
            self.assertEqual(clean_text(s), s)


class TestCleanUrl(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(clean_url("https://x.lk/uploads/dilly-&amp;-carlo.jpg"), "https://x.lk/uploads/dilly-&-carlo.jpg")
        self.assertEqual(clean_url("https://x.lk/uploads/SOFTLOGIC MAX.jpg"), "https://x.lk/uploads/SOFTLOGIC%20MAX.jpg")
        self.assertEqual(clean_url("https://x.lk/a%20b.jpg?x=1&y=2"), "https://x.lk/a%20b.jpg?x=1&y=2")  # no double-encoding


class TestCategories(unittest.TestCase):
    def test_guesses(self):
        cases = {
            "Hotels": offer(merchant="Swiss Belhotel International", description="Up to 35% on stays & dining"),
            "Dining": offer(merchant="Pizza Hut", description="50% off on total bill"),
            "Instalment Plans": offer(merchant="Green Solar", description="Up to 48 Months 0% Easy Payment Plans"),
            "Supermarkets": offer(merchant="Keells", description="30% off every Saturday"),
            "Other": offer(merchant="Visa Gold", description="Special offer for Visa Gold cards"),
        }
        for want, o in cases.items():
            with self.subTest(want=want):
                self.assertEqual(guess_category(o), want)


class TestDedupe(unittest.TestCase):
    def test_shop_and_website_merge(self):
        a = offer(id="a", merchant="www.street82.lk", discount="15%",
                  description="15% Savings at www.street82.lk. Offer valid on DFCC Credit Cards", image_url="https://i/s.jpg")
        b = offer(id="b", merchant="Street 82", discount="15%",
                  description="15% Savings at Street 82. Offer valid on DFCC Credit Cards", image_url="https://i/s.jpg")
        out = merge_duplicates([a, b])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["merchant"], "Street 82")   # readable name wins

    def test_different_discounts_stay(self):
        a = offer(id="a", bank="Peoples Bank", merchant="Fashion Bug", description="25% off at Fashion Bug with credit cards")
        b = offer(id="b", bank="Peoples Bank", merchant="Fashion Bug", description="20% off at Fashion Bug with debit cards")
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_different_deals_same_logo_stay(self):
        a = offer(id="a", bank="HNB", merchant="United Motors Lanka PLC", image_url="https://i/u.png",
                  description="Up to 06 months 0% installments at United Motors")
        b = offer(id="b", bank="HNB", merchant="United Motors Lanka PLC", image_url="https://i/u.png",
                  description="Special discounts for Selected Repairs and Detailing + Up to 06 months 0% installments")
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_different_banks_stay(self):
        a = offer(id="a", bank="Seylan Bank", merchant="STREET 82", description="15% Off with your Seylan Cards")
        b = offer(id="b", bank="DFCC", merchant="Street 82", description="15% Off with your Seylan Cards")
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_fuller_description_kept(self):
        a = offer(id="a", bank="HNB", merchant="Dinapala Group", image_url="https://i/d.jpg", card_types=["credit"],
                  description="25% off on selected items at Dinapala Group")
        b = offer(id="b", bank="HNB", merchant="Dinapala Group", image_url="https://i/d.jpg", card_types=["credit", "visa"],
                  description="25% off on selected items + Up to 06 months installments at Dinapala Group")
        out = merge_duplicates([a, b])
        self.assertEqual(len(out), 1)
        self.assertIn("installments", out[0]["description"])
        self.assertEqual(out[0]["card_types"], ["credit", "visa"])

    def test_credit_and_debit_versions_stay_apart(self):
        # The credit-card deal adds 0% instalments that debit cards don't get.
        a = offer(id="a", bank="HNB", merchant="Dinapala Group", image_url="https://i/d.jpg", card_types=["debit"],
                  description="25% off on selected items at Dinapala Group")
        b = offer(id="b", bank="HNB", merchant="Dinapala Group", image_url="https://i/d.jpg", card_types=["credit"],
                  description="25% off on selected items + Up to 06 months installments at Dinapala Group")
        self.assertEqual(len(merge_duplicates([a, b])), 2)

    def test_card_words_need_whole_words(self):
        from banks import sampath
        self.assertEqual(sampath._detect_card_types("Visaga Fashion and Aramex"), [])
        self.assertEqual(sampath._detect_card_types("Sampath Visa Credit Cards"), ["credit", "visa"])


# ----------------------------------------------------------------- part 2
DATA = json.loads((ROOT / "data" / "offers.json").read_text(encoding="utf-8"))
OFFERS = DATA["offers"]
FIELDS = ["id", "bank", "merchant", "discount", "description", "category", "city", "period",
          "card_types", "details", "terms", "image_url", "source_url", "updated_at", "end_date"]
CATEGORIES = set(CANONICAL_CATEGORY.values()) | {"Instalment Plans", "Other"}
CARD_TYPES = {"visa", "mastercard", "amex", "credit", "debit"}
BANKS = {"Sampath Bank", "Commercial Bank", "HNB", "Seylan Bank", "Nations Trust", "BOC", "NDB", "Peoples Bank", "DFCC"}
JUNK = re.compile(r"<[a-z/][^>]*>|&[a-z]+;|&#\d+;|\{\{|\}\}|�|Ã|â€|Â[\s\W]")


class TestData(unittest.TestCase):
    def problems(self, check):
        bad = [o["id"] for o in OFFERS if check(o)]
        return f"{len(bad)} offers, e.g. {bad[:5]}" if bad else ""

    def test_file_summary(self):
        self.assertEqual(DATA["offer_count"], len(OFFERS))
        self.assertEqual(set(DATA["banks"]), {o["bank"] for o in OFFERS})
        self.assertEqual({o["bank"] for o in OFFERS}, BANKS, "a bank is missing")
        self.assertGreater(len(OFFERS), 1500)

    def test_every_bank_has_enough_offers(self):
        counts = {b: sum(o["bank"] == b for o in OFFERS) for b in BANKS}
        for bank, n in counts.items():
            with self.subTest(bank=bank):
                self.assertGreaterEqual(n, 20, f"{bank} only has {n} offers")

    def test_all_fields_present(self):
        self.assertFalse(self.problems(lambda o: any(k not in o for k in FIELDS)))

    def test_unique_ids(self):
        ids = [o["id"] for o in OFFERS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_expired_offers(self):
        generated = dt.datetime.fromisoformat(DATA["generated_at"].replace("Z", "+00:00")).astimezone(SL_TIME).date()
        self.assertFalse(self.problems(lambda o: o["end_date"] and o["end_date"] < generated.isoformat()))

    def test_end_date_matches_period(self):
        self.assertFalse(self.problems(
            lambda o: not re.fullmatch(r"(\d{4}-\d{2}-\d{2})?", o["end_date"])))
        self.assertFalse(self.problems(lambda o: o["period"] and not o["end_date"] and end_date(o["period"])))

    def test_most_offers_have_end_date(self):
        missing = sum(not o["end_date"] for o in OFFERS)
        self.assertLess(missing / len(OFFERS), 0.05)

    def test_names_present(self):
        self.assertFalse(self.problems(lambda o: not o["merchant"].strip()))
        self.assertFalse(self.problems(lambda o: not o["description"].strip()))

    def test_no_broken_text(self):
        self.assertFalse(self.problems(
            lambda o: any(JUNK.search(o[k] or "") for k in ("merchant", "discount", "description", "period", "city"))))

    def test_valid_categories(self):
        self.assertFalse(self.problems(lambda o: o["category"] not in CATEGORIES))
        other = sum(o["category"] == "Other" for o in OFFERS) / len(OFFERS)
        self.assertLess(other, 0.12, f"{other:.0%} of offers are in 'Other'")

    def test_valid_card_types(self):
        self.assertFalse(self.problems(lambda o: not set(o["card_types"]) <= CARD_TYPES))

    def test_links(self):
        self.assertFalse(self.problems(lambda o: not o["source_url"].startswith("https://")))
        self.assertFalse(self.problems(lambda o: o["image_url"] and not o["image_url"].startswith("https://")))
        self.assertFalse(self.problems(
            lambda o: any(re.search(r"\s|&amp;|&#\d+;", o[k]) for k in ("image_url", "source_url"))))
        with_image = sum(bool(o["image_url"]) for o in OFFERS) / len(OFFERS)
        self.assertGreater(with_image, 0.95)

    def test_no_duplicates_left(self):
        again = merge_duplicates([dict(o) for o in OFFERS])
        self.assertEqual(len(again), len(OFFERS), "merge_duplicates would still merge offers")

    def test_discount_numbers_sane(self):
        self.assertFalse(self.problems(
            lambda o: any(int(p) > 100 for p in re.findall(r"(\d{1,3})\s*%", o["discount"]))))

    def test_mobile_copy_matches(self):
        mobile = json.loads((ROOT / "mobile" / "assets" / "offers.json").read_text(encoding="utf-8"))
        self.assertEqual(mobile["generated_at"], DATA["generated_at"], "run update-offers.bat / copy data to mobile/assets")


if __name__ == "__main__":
    unittest.main()

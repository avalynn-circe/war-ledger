import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from pipeline.extract import airforce, deepstate, generalstaff, news, rumod
from pipeline.fold import fold
from pipeline.sources import rss, telegram

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures"

SRC = {
    "kpszsu": {"id": "kpszsu", "name": "Air Force of Ukraine", "side": "ua_official", "kind": "telegram", "lang": "uk"},
    "generalstaff": {"id": "generalstaff", "name": "General Staff", "side": "ua_official", "kind": "telegram", "lang": "uk"},
    "mod_russia": {"id": "mod_russia", "name": "Russian MoD", "side": "ru_official", "kind": "telegram", "lang": "ru"},
    "deepstate": {"id": "deepstate", "name": "DeepState", "side": "osint", "kind": "telegram", "lang": "uk"},
    "kyivindependent": {"id": "kyivindependent", "name": "The Kyiv Independent", "side": "media", "kind": "rss", "lang": "en"},
    "militarnyi": {"id": "militarnyi", "name": "Militarnyi", "side": "media", "kind": "rss", "lang": "en"},
    "ukrinform": {"id": "ukrinform", "name": "Ukrinform", "side": "media", "kind": "rss", "lang": "en"},
}


def posts(name):
    return telegram.parse((FIX / f"{name}.html").read_text(encoding="utf-8"))


def items(name):
    return rss.parse((FIX / f"{name}.xml").read_text(encoding="utf-8"))


class TelegramParse(unittest.TestCase):
    def test_posts_and_dates(self):
        ps = posts("kpszsu")
        self.assertEqual(len(ps), 3)
        self.assertEqual(ps[1].url, "https://t.me/kpszsu/35012")
        self.assertEqual(ps[1].dt.isoformat(), "2026-10-26T07:12:00+00:00")
        self.assertIn("\n", ps[1].text)


class AirForce(unittest.TestCase):
    def setUp(self):
        evs = [e for p in posts("kpszsu") for e in airforce.extract(p, SRC["kpszsu"])]
        self.assertEqual(len(evs), 2, "the daily summary post must not produce an entry")
        self.e, self.e2 = evs

    def test_counts(self):
        c = self.e.counts
        self.assertEqual(c["launched"], 105)
        self.assertEqual(c["shahed_of_which"], 60)
        self.assertEqual(c["intercepted"], 90)
        self.assertEqual(c["impacts"], 15)
        self.assertEqual(c["impact_locations"], 9)
        self.assertEqual(c["debris_locations"], 2)

    def test_weapons(self):
        w = {x["name"]: x for x in self.e.weapons}
        self.assertEqual(w[airforce.SHAHED]["launched"], 101)
        self.assertEqual(w[airforce.SHAHED]["intercepted"], 90)
        self.assertEqual(w[airforce.SHAHED]["impacts"], 11)
        self.assertEqual(w["Iskander-M ballistic missile"]["launched"], 4)
        self.assertEqual(w["Iskander-M ballistic missile"]["impacts"], 4)

    def test_date_time_places(self):
        self.assertEqual(self.e.date, "2026-10-26")
        self.assertEqual(self.e.time, "09:00")
        self.assertEqual(self.e.locations, ["Kursk", "Millerovo", "Oryol", "Shatalovo", "Primorsko-Akhtarsk", "Hvardiiske (Crimea)"])
        self.assertEqual(self.e.extraction, "structured")


    def test_headline_format_2026(self):
        """The real 27 October 2026 post: headline line, missiles named without a count,
        a stated total of targets, impact locations without per-weapon counts."""
        e = self.e2
        self.assertEqual(e.date, "2026-10-27")
        self.assertEqual(e.time, "09:00")
        self.assertEqual(e.counts["launched"], 280)
        self.assertEqual(e.counts["jet_powered_shahed"], 69)
        self.assertEqual(e.counts["intercepted"], 257)
        self.assertEqual(e.counts["jet_powered_shahed_intercepted"], 56)
        self.assertEqual(e.counts["impact_locations"], 25)
        self.assertEqual(e.counts["debris_locations"], 16)
        self.assertNotIn("impacts", e.counts)
        w = {x["name"]: x for x in e.weapons}
        self.assertEqual(w[airforce.SHAHED], {"name": airforce.SHAHED, "launched": 280, "intercepted": 255})
        self.assertEqual(w["Iskander-M/S-400 ballistic missile"], {"name": "Iskander-M/S-400 ballistic missile", "intercepted": 2})
        self.assertEqual(e.locations, ["Oryol", "Millerovo", "Kursk", "Shatalovo", "Primorsko-Akhtarsk", "Donetsk (occupied)", "Hvardiiske (Crimea)"])
        self.assertEqual(e.detail, "Main direction of the strike: Kyiv")


class GeneralStaff(unittest.TestCase):
    def setUp(self):
        self.evs = [e for p in posts("generalstaff") for e in generalstaff.extract(p, SRC["generalstaff"])]

    def test_losses(self):
        e = next(e for e in self.evs if e.category == "losses_claimed")
        rows = {b["label"]: b for b in e.breakdown}
        self.assertEqual(rows["personnel"], {"label": "personnel", "count": 1137180, "delta": 1000})
        self.assertEqual(rows["tanks"]["count"], 11290)
        self.assertEqual(rows["UAVs (operational-tactical)"]["delta"], 300)
        self.assertEqual(len(e.breakdown), 14)
        self.assertEqual(e.date, "2026-10-26")

    def test_operational_real_2026(self):
        """The real 27 October 2026 morning report."""
        e = next(e for e in self.evs if e.counts.get("clashes") == 196)
        self.assertEqual(e.counts["missile_strikes"], 1)
        self.assertEqual(e.counts["air_strikes"], 72)
        self.assertEqual(e.counts["guided_bombs"], 247)
        self.assertEqual(e.counts["kamikaze_drones"], 9679)
        self.assertEqual(e.counts["shellings"], 2518)
        self.assertEqual(e.counts["mlrs_shellings"], 12)
        self.assertEqual(e.counts["concentration_areas_struck"], 3)
        self.assertEqual(e.counts["settlements_shelled"], 25)
        self.assertEqual(e.action, "past 24 hours to 08:00, as reported")
        self.assertEqual(len(e.locations), 2)
        self.assertTrue(e.locations[0].startswith("Sumy oblast: Безсалівка, Кореньок"))
        self.assertTrue(e.locations[1].startswith("Chernihiv oblast: Гута-Студенецька"))
        self.assertEqual(e.detail, "Air strikes on: Кореньок")

    def test_daily_losses_sentence(self):
        e = next(e for e in self.evs if e.category == "losses_claimed" and e.date == "2026-10-27")
        rows = {b["label"]: b["delta"] for b in e.breakdown}
        self.assertEqual(rows, {
            "personnel": 1400, "artillery systems": 21, "multiple rocket launchers": 2, "air defence systems": 1,
            "ground robotic systems": 7, "UAVs": 1794, "vehicles and fuel tankers": 232, "special equipment": 1,
        })

    def test_operational(self):
        e = next(e for e in self.evs if e.counts.get("clashes") == 180)
        self.assertEqual(e.counts["missile_strikes"], 2)
        self.assertEqual(e.counts["air_strikes"], 55)
        self.assertEqual(e.counts["guided_bombs"], 112)
        self.assertEqual(e.counts["kamikaze_drones"], 5040)
        self.assertEqual(e.counts["shellings"], 4290)
        self.assertEqual(e.counts["mlrs_shellings"], 96)
        self.assertEqual(e.counts["concentration_areas_struck"], 10)
        self.assertEqual(e.time, "08:00")


class RuMod(unittest.TestCase):
    def setUp(self):
        self.evs = [e for p in posts("mod_russia") for e in rumod.extract(p, SRC["mod_russia"])]

    def test_intercepts(self):
        e = next(e for e in self.evs if e.category == "strikes_in_russia")
        self.assertEqual(e.counts["intercepted_claimed"], 93)
        self.assertEqual(sum(b["count"] for b in e.breakdown), 93)
        self.assertEqual(e.breakdown[0], {"label": "Bryansk oblast", "count": 23})
        self.assertIn("Black Sea", e.locations)
        self.assertIn("overnight", e.action)

    def test_region_list_without_counts(self):
        e = next(e for e in self.evs if e.counts.get("intercepted_claimed") == 222)
        self.assertEqual(e.breakdown, [])
        self.assertEqual(len(e.locations), 13)
        self.assertEqual(e.locations[0], "Novgorod oblast")
        self.assertIn("Krasnodar krai", e.locations)
        self.assertIn("Crimea", e.locations)

    def test_midday_summary_claimed_ukrainian_losses(self):
        e = next(e for e in self.evs if e.category == "losses_claimed")
        self.assertEqual(e.actor, "Russia (MoD)")
        rows = {b["label"]: b["delta"] for b in e.breakdown}
        self.assertEqual(rows, {"personnel": 555, "tanks": 1, "armoured fighting vehicles": 3, "vehicles": 23,
                                "artillery systems": 4, "electronic warfare stations": 2})

    def test_strike_and_capture_claims(self):
        strike = next(e for e in self.evs if e.category == "air_attack")
        self.assertIn("Shahed/Geran-2 strike UAV", [w["name"] for w in strike.weapons])
        caps = [e for e in self.evs if e.category == "front_line"]
        self.assertEqual(caps[0].locations, ["Новониколаевка"])


class DeepState(unittest.TestCase):
    def test_changes(self):
        evs = [e for p in posts("deepstate") for e in deepstate.extract(p, SRC["deepstate"])]
        by = {(e.date, e.action): e.locations for e in evs}
        # 21:40 UTC on 25 October is 23:40 Kyiv time, so the first post is dated 25 October.
        self.assertEqual(by[("2026-10-25", "occupied")], ["Новомиколаївку"])
        self.assertEqual(by[("2026-10-25", "advanced near")], ["Полтавки", "Іванівки", "Степногірська"])
        self.assertEqual(by[("2026-10-26", "advanced near")], ["Торецька"])
        self.assertEqual(by[("2026-10-26", "liberated")], ["Кіндратівкою"])


class News(unittest.TestCase):
    def test_classification(self):
        got = {i.title: news.classify(i.title, i.summary) for i in items("militarnyi")}
        self.assertEqual(got["Russians stretch anti-drone netting over 12 km of road near Bakhmut"], "field_adaptation")
        self.assertEqual(got["Ukraine receives new Patriot battery from Germany"], "weapons_deliveries")
        self.assertEqual(got["Ukrainian naval drones strike Russian patrol boat near Novorossiysk"], "naval")
        self.assertEqual(got["Drones hit Ryazan oil refinery, fire reported"], "strikes_in_russia")
        self.assertEqual(got["Russian forces advance near Pokrovsk, DeepState reports"], "front_line")
        self.assertIsNone(got["Militarnyi weekly digest: subscribe to our newsletter"])
        ki = {i.title: news.classify(i.title, i.summary) for i in items("kyivindependent")}
        self.assertEqual(ki["Ukraine shoots down 90 of 105 Russian drones and missiles overnight, Air Force says"], "air_attack")
        self.assertEqual(ki["Russian attack on Kharkiv energy facility cuts power to 30,000 customers"], "infrastructure")
        self.assertIsNone(ki["Parliament passes 2027 budget in first reading"])

    def test_entities(self):
        e = news.extract(items("militarnyi")[0], SRC["militarnyi"])[0]
        self.assertIn("Anti-drone netting", [w["name"] for w in e.weapons])
        self.assertIn("Bakhmut", e.locations)
        self.assertEqual(e.extraction, "rules")


class Fold(unittest.TestCase):
    def test_media_folds_into_structured(self):
        evs = [e for p in posts("kpszsu") for e in airforce.extract(p, SRC["kpszsu"])]
        evs += [e for p in posts("generalstaff") for e in generalstaff.extract(p, SRC["generalstaff"])]
        for name in ("kyivindependent", "ukrinform"):
            evs += [e for i in items(name) for e in news.extract(i, SRC[name])]
        out = fold(evs)
        air = [e for e in out if e.category == "air_attack" and e.date == "2026-10-26"]
        self.assertEqual(len(air), 1)
        self.assertEqual({r["name"] for r in air[0].also_reported_by}, {"The Kyiv Independent", "Ukrinform"})
        losses = [e for e in out if e.category == "losses_claimed" and e.date == "2026-10-26"]
        self.assertEqual(len(losses), 1)
        self.assertEqual([r["name"] for r in losses[0].also_reported_by], ["Ukrinform"])


class EndToEnd(unittest.TestCase):
    def test_offline_run_renders_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, site = pathlib.Path(tmp, "data"), pathlib.Path(tmp, "site")
            cmd = [sys.executable, "-m", "pipeline.run", "--offline", str(FIX), "--data", str(data), "--site", str(site), "--max-age-days", "100000"]
            proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertTrue((data / "2026-10-26.json").exists())
            self.assertTrue((data / "2026-10-25.json").exists())
            index = (site / "index.html").read_text(encoding="utf-8")
            self.assertIn("Strike UAVs launched", index)
            self.assertIn(">280<", index)
            self.assertIn("Sumy oblast: Безсалівка", index)
            self.assertIn('<details class="cat" id="air_attack" data-cat="air_attack">', index)
            self.assertIn('id="toggles"', index)
            self.assertIn('class="cal-box" data-date="2026-10-27"', index)
            self.assertIn("TUESDAY", index)
            self.assertIn('class="spark"', index)
            self.assertIn("Reported by Russia", index)
            self.assertIn(">555<", index)
            wire_page = (site / "wire.html").read_text(encoding="utf-8")
            self.assertIn('data-cat="air_attack"', wire_page)
            self.assertIn('data-days=', wire_page)
            self.assertIn('id="wire-more"', wire_page)
            self.assertIn('data-day="2026-10-27"', wire_page)
            self.assertTrue((site / "wire-data" / "2026-10-26.html").exists())
            self.assertFalse((site / "wire-2026-10-26.html").exists())
            self.assertTrue((site / "ledger.js").exists())
            evs27 = json.loads((data / "2026-10-27.json").read_text(encoding="utf-8"))["events"]
            self.assertTrue(all(e.get("published") for e in evs27))
            self.assertIn("280 launched · 257 intercepted", wire_page)
            self.assertTrue((data / "raw" / "kpszsu" / "2026-10-27.jsonl").exists())
            day26 = (site / "2026-10-26.html").read_text(encoding="utf-8")
            self.assertIn(">105<", day26)
            self.assertIn("Field adaptations", day26)
            self.assertTrue((site / "archive.html").exists())
            self.assertTrue((site / "events.csv").exists())
            days = json.loads((site / "events.json").read_text(encoding="utf-8"))["days"]
            self.assertEqual(days[0]["date"], "2026-10-27")
            # Running twice must not duplicate entries.
            n = len(days[0]["events"])
            subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
            again = json.loads((data / "2026-10-27.json").read_text(encoding="utf-8"))["events"]
            self.assertEqual(len(again), n)


if __name__ == "__main__":
    unittest.main()

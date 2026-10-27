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
        self.assertEqual(len(ps), 2)
        self.assertEqual(ps[1].url, "https://t.me/kpszsu/35012")
        self.assertEqual(ps[1].dt.isoformat(), "2026-10-26T07:12:00+00:00")
        self.assertIn("\n", ps[1].text)


class AirForce(unittest.TestCase):
    def setUp(self):
        evs = [e for p in posts("kpszsu") for e in airforce.extract(p, SRC["kpszsu"])]
        self.assertEqual(len(evs), 1, "the daily summary post must not produce an entry")
        self.e = evs[0]

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

    def test_operational(self):
        e = next(e for e in self.evs if e.category == "front_activity")
        self.assertEqual(e.counts["clashes"], 180)
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

    def test_strike_and_capture_claims(self):
        strike = next(e for e in self.evs if e.category == "air_attack")
        self.assertIn("Shahed/Geran-2 strike UAV", [w["name"] for w in strike.weapons])
        cap = next(e for e in self.evs if e.category == "front_line")
        self.assertEqual(cap.locations, ["Новониколаевка"])


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
        air = [e for e in out if e.category == "air_attack"]
        self.assertEqual(len(air), 1)
        self.assertEqual({r["name"] for r in air[0].also_reported_by}, {"The Kyiv Independent", "Ukrinform"})
        losses = [e for e in out if e.category == "losses_claimed"]
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
            self.assertIn("105 launched · 90 intercepted · 15 impacts", index)
            self.assertIn("Field adaptations", index)
            self.assertTrue((site / "archive.html").exists())
            self.assertTrue((site / "events.csv").exists())
            days = json.loads((site / "events.json").read_text(encoding="utf-8"))["days"]
            self.assertEqual(days[0]["date"], "2026-10-26")
            # Running twice must not duplicate entries.
            n = len(days[0]["events"])
            subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
            again = json.loads((data / "2026-10-26.json").read_text(encoding="utf-8"))["events"]
            self.assertEqual(len(again), n)


if __name__ == "__main__":
    unittest.main()

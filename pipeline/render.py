"""Render the static site from the day files.

Each day page has three layers: a 30-day strip for navigation, the returns
sheet (the same rows every day, one column per side, a 14-day sparkline per
row), and the entries grouped by category in sections closed by default.
"""
from __future__ import annotations

import csv
import json
import pathlib
import shutil
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import geo
from .extract.common import CATEGORIES, CATEGORY_LABELS, SIDE_LABELS

TEMPLATES = pathlib.Path(__file__).parent / "templates"

COUNT_LABELS = {
    "launched": "launched",
    "intercepted": "intercepted",
    "impacts": "impacts recorded",
    "impact_locations": "impact locations",
    "debris_locations": "debris fall locations",
    "shahed_of_which": "of which Shahed",
    "jet_powered_shahed": "of which jet-powered",
    "jet_powered_shahed_intercepted": "jet-powered intercepted",
    "lost_from_radar": "lost from radar",
    "clashes": "combat clashes",
    "missile_strikes": "missile strikes",
    "air_strikes": "air strikes",
    "missiles_used": "missiles used",
    "guided_bombs": "guided aerial bombs dropped",
    "kamikaze_drones": "kamikaze drones used",
    "shellings": "shellings",
    "mlrs_shellings": "of which MLRS",
    "settlements_shelled": "settlements shelled",
    "intercepted_claimed": "UAVs intercepted, as claimed",
    "concentration_areas_struck": "concentration areas struck, as claimed",
}
SHORT_SOURCE = {"kpszsu": "Air Force", "generalstaff": "General Staff", "mod_russia": "MoD", "deepstate": "DeepState", "astra": "ASTRA",
                "oryx_russia": "Oryx", "oryx_ukraine": "Oryx", "gov_belgorod": "Governor", "gov_bryansk": "Governor", "gov_kursk": "Governor", "gov_rostov": "Governor"}

STRIP_DAYS = 30
SPARK_DAYS = 14


# ---------------------------------------------------------------- selection helpers

def _structured(events: list[dict], source: str, category: str | None = None) -> list[dict]:
    return [
        e for e in events
        if e["source_id"] == source and e["extraction"] == "structured" and (category is None or e["category"] == category)
    ]


def _cell(value, event: dict | None, note: str | None = None) -> dict | None:
    if value is None or event is None:
        return None
    return {"value": value, "source": note or SHORT_SOURCE.get(event["source_id"], event["source_name"]), "url": event["source_url"], "id": event["source_id"]}


def _sum_counts(evs: list[dict], key: str) -> tuple[int | None, dict | None]:
    hits = [e for e in evs if key in e["counts"]]
    if not hits:
        return None, None
    return sum(e["counts"][key] for e in hits), hits[0]


def _max_counts(evs: list[dict], key: str) -> tuple[int | None, dict | None]:
    hits = [e for e in evs if key in e["counts"]]
    if not hits:
        return None, None
    best = max(hits, key=lambda e: e["counts"][key])
    return best["counts"][key], best


def _weapon_sum(evs: list[dict], uav: bool, key: str) -> tuple[int | None, dict | None]:
    total, hit = 0, None
    for e in evs:
        for w in e["weapons"]:
            if ("UAV" in w["name"]) == uav and key in w:
                total += w[key]
                hit = hit or e
    return (total, hit) if hit else (None, None)


def _delta(evs: list[dict], label: str) -> tuple[int | None, dict | None]:
    best: tuple[int | None, dict | None] = (None, None)
    for e in evs:
        for b in e["breakdown"]:
            if b["label"] == label and "delta" in b and (best[0] is None or b["delta"] > best[0]):
                best = (b["delta"], e)
    return best


def _places(evs: list[dict]) -> tuple[int | None, dict | None]:
    if not evs:
        return None, None
    return sum(len(e["locations"]) for e in evs), evs[0]


# ---------------------------------------------------------------- the returns sheet

def _oryx_cell(events: list[dict], prev: list[dict], target: str):
    today = [e for e in _structured(events, f"oryx_{target.lower()}", "losses_claimed") if "total" in e["counts"]]
    if not today:
        return None, None
    total = today[0]["counts"]["total"]
    before = [e for e in _structured(prev or [], f"oryx_{target.lower()}", "losses_claimed") if "total" in e["counts"]]
    if before:
        return f"{total:,} (+{total - before[0]['counts']['total']:,})", today[0]
    return f"{total:,}", today[0]


def _governor_cells(events: list[dict]):
    gov = [e for e in events if e["source_id"].startswith("gov_") and e["counts"]]
    if not gov:
        return (None, None), (None, None)
    killed = sum(e["counts"].get("killed", 0) for e in gov)
    injured = sum(e["counts"].get("injured", 0) for e in gov)
    shot = sum(e["counts"].get("uav_shot_down", 0) for e in gov)
    casualties = (f"{killed} killed · {injured} injured", gov[0]) if (killed or injured) else (None, None)
    drones = (shot, gov[0]) if shot else (None, None)
    return casualties, drones


def returns(events: list[dict], prev: list[dict] | None = None) -> list[dict]:
    """The fixed rows of the daily returns sheet, grouped, with a cell per side."""
    casualties, gov_drones = _governor_cells(events)
    af = _structured(events, "kpszsu", "air_attack")
    gs_day = [e for e in _structured(events, "generalstaff", "front_activity") if (e.get("action") or "").startswith("past 24")]
    gs_loss = _structured(events, "generalstaff", "losses_claimed")
    mod_loss = _structured(events, "mod_russia", "losses_claimed")
    mod_air = _structured(events, "mod_russia", "strikes_in_russia")
    mod_taken = _structured(events, "mod_russia", "front_line")
    ds_taken = [e for e in _structured(events, "deepstate", "front_line") if e["action"] == "occupied"]
    ds_retaken = [e for e in _structured(events, "deepstate", "front_line") if e["action"] == "liberated"]

    missiles = _weapon_sum(af, False, "launched")
    if missiles[0] is None and any("UAV" not in w["name"] for e in af for w in e["weapons"]):
        names = sorted({w["name"] for e in af for w in e["weapons"] if "UAV" not in w["name"]})
        missiles = (", ".join(n.replace(" ballistic missile", "").replace(" cruise missile", "") for n in names) + " (count not stated)", af[0])
    direction = next(((e["detail"].split(": ", 1)[1], e) for e in af if (e.get("detail") or "").startswith("Main direction")), (None, None))

    groups = [
        ("Air war on Ukraine, overnight", [
            ("uav_launched", "Strike UAVs launched", _weapon_sum(af, True, "launched"), (None, None)),
            ("missiles_launched", "Missiles launched", missiles, (None, None)),
            ("intercepted", "Targets intercepted", _sum_counts(af, "intercepted"), (None, None)),
            ("impact_locations", "Impact locations", _sum_counts(af, "impact_locations"), (None, None)),
            ("direction", "Main direction", direction, (None, None)),
        ]),
        ("Air war on Russia", [
            ("intercepted_over_russia", "UAVs intercepted over Russia", (None, None), _sum_counts(mod_air, "intercepted_claimed")),
            ("gov_drones", "UAVs shot down, per regional governors", (None, None), gov_drones),
            ("gov_casualties", "Killed and injured, per regional governors", (None, None), casualties),
        ]),
        ("Front, past 24 hours", [
            ("clashes", "Combat clashes", _max_counts(gs_day, "clashes"), (None, None)),
            ("guided_bombs", "Guided aerial bombs", _max_counts(gs_day, "guided_bombs"), (None, None)),
            ("kamikaze_drones", "Kamikaze drones used", _max_counts(gs_day, "kamikaze_drones"), (None, None)),
            ("shellings", "Shellings", _max_counts(gs_day, "shellings"), (None, None)),
            ("settlements_shelled", "Settlements shelled", _max_counts(gs_day, "settlements_shelled"), (None, None)),
            ("taken", "Settlements taken", _places(ds_taken), _places(mod_taken)),
            ("retaken", "Settlements retaken", _places(ds_retaken), (None, None)),
        ]),
        ("Enemy losses in 24 hours, as each side claims", [
            ("loss_personnel", "Personnel", _delta(gs_loss, "personnel"), _delta(mod_loss, "personnel")),
            ("loss_tanks", "Tanks", _delta(gs_loss, "tanks"), _delta(mod_loss, "tanks")),
            ("loss_afv", "Armoured fighting vehicles", _delta(gs_loss, "armoured fighting vehicles"), _delta(mod_loss, "armoured fighting vehicles")),
            ("loss_artillery", "Artillery systems", _delta(gs_loss, "artillery systems"), _delta(mod_loss, "artillery systems")),
            ("loss_uav", "UAVs", _delta(gs_loss, "UAVs"), _delta(mod_loss, "UAVs")),
            ("loss_vehicles", "Vehicles", _delta(gs_loss, "vehicles and fuel tankers"), _delta(mod_loss, "vehicles")),
            ("oryx", "Equipment, visually confirmed (Oryx), cumulative", _oryx_cell(events, prev, "Russia"), _oryx_cell(events, prev, "Ukraine")),
        ]),
    ]
    out = []
    for label, rows in groups:
        out.append({"label": label, "rows": [
            {"key": key, "label": lab, "ua": _cell(*ua), "ru": _cell(*ru)} for key, lab, ua, ru in rows
        ]})
    return out


def _flat(sheet: list[dict]) -> dict[str, dict]:
    return {r["key"]: r for g in sheet for r in g["rows"]}


def _numeric(cell: dict | None) -> int | None:
    return cell["value"] if cell and isinstance(cell["value"], int) else None


def sparkline(points: list[int | None], width: int = 84, height: int = 20) -> str:
    """A single thin line over the last days; gaps where a day has no figure."""
    vals = [v for v in points if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = 0, max(vals) or 1
    pad = 2
    step = (width - 2 * pad) / (len(points) - 1)
    def xy(i: int, v: int) -> str:
        x = pad + i * step
        y = height - pad - (v - lo) / (hi - lo or 1) * (height - 2 * pad)
        return f"{x:.1f},{y:.1f}"
    segments, current = [], []
    for i, v in enumerate(points):
        if v is None:
            if current:
                segments.append(current)
            current = []
        else:
            current.append(xy(i, v))
    if current:
        segments.append(current)
    paths = "".join(
        f'<polyline points="{" ".join(seg)}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        if len(seg) > 1 else f'<circle cx="{seg[0].split(",")[0]}" cy="{seg[0].split(",")[1]}" r="1.5" fill="currentColor"/>'
        for seg in segments
    )
    last_i = max(i for i, v in enumerate(points) if v is not None)
    lx, ly = xy(last_i, points[last_i]).split(",")
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img">'
        f'{paths}<circle cx="{lx}" cy="{ly}" r="2.5" fill="currentColor"/></svg>'
    )


def _date_range(end: str, n: int) -> list[str]:
    last = date.fromisoformat(end)
    return [(last - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


# ---------------------------------------------------------------- page assembly

def group(events: list[dict]) -> list[dict]:
    out = []
    rows = headline_rows(events)
    for key, label in CATEGORIES:
        evs = [e for e in rows if e["category"] == key]
        if evs:
            sources = []
            for e in evs:
                if e["source_name"] not in sources:
                    sources.append(e["source_name"])
            out.append({"key": key, "label": label, "events": evs, "sources": sources})
    return out


WIRE_KEYS = ["launched", "intercepted", "impact_locations", "clashes", "guided_bombs", "kamikaze_drones", "shellings", "settlements_shelled", "intercepted_claimed"]


def wire_line(e: dict) -> str:
    """One-line digest of a structured entry's main figures."""
    return " · ".join(f"{_fmt(e['counts'][k])} {COUNT_LABELS.get(k, k)}" for k in WIRE_KEYS if k in e["counts"])


KYIV = ZoneInfo("Europe/Kyiv")


def _report_card(parts: list[dict]) -> dict:
    """One wire row for the General Staff operational report: its activity
    counts, the day's claimed losses, shelled settlements and air strikes."""
    fa = next((e for e in parts if e["category"] == "front_activity"), None)
    loss = next((e for e in parts if e["category"] == "losses_claimed"), None)
    base = fa or loss
    card = dict(base)
    card.update({
        "card": True, "category": "front_activity",
        "title": "General Staff operational report",
        "summary": wire_line(fa) if fa else "",
        "counts_list": [{"label": COUNT_LABELS.get(k, k.replace("_", " ")), "v": _fmt(v)} for k, v in (fa or {}).get("counts", {}).items()],
        "losses": (loss or {}).get("breakdown", []),
        "shelled": (fa or {}).get("locations", []),
        "shelled_en": (fa or {}).get("locations_en"),
        "air": (fa or {}).get("detail"),
        "air_en": (fa or {}).get("detail_en"),
        "also_reported_by": [r for e in parts for r in e["also_reported_by"]],
    })
    return card


def wire(events: list[dict]) -> list[dict]:
    """A day's entries newest first, by the source post's own timestamp."""
    rows = []
    by_report: dict[str, list[dict]] = {}
    for e in events:
        if e["source_id"] == "generalstaff" and e["category"] in ("front_activity", "losses_claimed") and e["extraction"] == "structured":
            by_report.setdefault(e["source_url"], []).append(e)
    merged = [_report_card(parts) for parts in by_report.values()]
    skip = {e["id"] for parts in by_report.values() for e in parts}
    for e in [x for x in events if x["id"] not in skip] + merged:
        r = dict(e)
        r["line"] = wire_line(e) if e["extraction"] == "structured" else ""
        pub = e.get("published")
        if pub:
            r["clock"] = datetime.fromisoformat(pub).astimezone(KYIV).strftime("%H:%M")
            r["sort"] = pub
        else:
            r["clock"] = e.get("time") or "––:––"
            r["sort"] = ""
        rows.append(r)
    return sorted(rows, key=lambda r: (r["sort"], r["clock"]), reverse=True)


def _longdate(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.day} {dt:%B %Y}"


FACT_ROWS = [
    # (sheet key, side, label)
    ("uav_launched", "ua", "Strike UAVs launched at Ukraine"),
    ("intercepted", "ua", "Targets intercepted"),
    ("impact_locations", "ua", "Impact locations"),
    ("intercepted_over_russia", "ru", "UAVs intercepted over Russia, claimed"),
    ("clashes", "ua", "Combat clashes"),
    ("guided_bombs", "ua", "Guided aerial bombs"),
    ("kamikaze_drones", "ua", "Kamikaze drones used"),
    ("loss_personnel", "ua", "Russian personnel losses, claimed"),
]


def facts(flat: dict[str, dict], spark_for) -> list[dict]:
    """The day's figures as tiles, from the returns sheet."""
    out = []
    launched = _numeric(flat["uav_launched"]["ua"])
    for key, side, label in FACT_ROWS:
        cell = flat[key][side]
        value = cell["value"] if cell else None
        tile = {
            "key": key, "label": label, "value": _fmt(value) if value is not None else None,
            "source": cell["source"] if cell else "", "url": cell["url"] if cell else "", "src": cell["id"] if cell else None,
            "bar": None, "bar_note": "", "second": "", "spark": spark_for(key, side) if cell else "",
        }
        if key == "intercepted" and launched and isinstance(value, int):
            tile["bar"] = min(100, round(100 * value / launched))
            tile["bar_note"] = f"{tile['bar']}% of launched"
        if key == "loss_personnel":
            if isinstance(value, int):
                tile["value"] = f"+{value:,}"
            other = flat[key]["ru"]
            if other:
                tile["second"] = f"Ukrainian +{other['value']:,}, claimed by {other['source']}"
        out.append(tile)
    return out


def _split_group(text: str) -> dict:
    oblast, _, names = text.partition(": ")
    if not names:
        return {"oblast": "", "names": [t.strip() for t in text.split(",") if t.strip()]}
    return {"oblast": oblast, "names": [t.strip() for t in names.split(",") if t.strip()]}


def where(events: list[dict]) -> list[dict]:
    """Place cards: launch directions and target, settlements shelled, regions over Russia."""
    cards = []
    af = _structured(events, "kpszsu", "air_attack")
    if af and (af[0]["locations"] or af[0].get("detail")):
        detail = af[0].get("detail") or ""
        target = detail.split(": ", 1)[1] if ": " in detail else "not stated"
        cards.append({"kind": "arrow", "label": "Overnight attack: launch directions and main target", "places": af[0]["locations"], "target": target, "source": "Air Force of Ukraine", "src": "kpszsu"})
    gs = [e for e in _structured(events, "generalstaff", "front_activity") if e["locations"]]
    if gs:
        groups = [_split_group(g) for g in (gs[0].get("locations_en") or gs[0]["locations"])]
        air = gs[0].get("detail_en") or gs[0].get("detail")
        cards.append({"kind": "groups", "label": "Settlements shelled, past 24 hours", "groups": groups, "note": air, "source": "General Staff of the Armed Forces of Ukraine", "src": "generalstaff"})
    mod = [e for e in _structured(events, "mod_russia", "strikes_in_russia") if e["locations"]]
    if mod:
        regions = []
        for e in mod:
            for r in e["locations"]:
                if r not in regions:
                    regions.append(r)
        cards.append({"kind": "list", "label": "UAVs intercepted over Russia: regions named", "places": regions, "source": "Ministry of Defence of Russia, as claimed", "src": "mod_russia"})
    return cards


def headline_rows(events: list[dict]) -> list[dict]:
    rows = []
    for e in events:
        r = dict(e)
        r["line"] = wire_line(e) if e["extraction"] == "structured" else ""
        pub = e.get("published")
        r["clock"] = datetime.fromisoformat(pub).astimezone(KYIV).strftime("%H:%M") if pub else (e.get("time") or "––:––")
        r["short"] = CHIP_NAME.get(e["source_id"], e["source_name"])
        rows.append(r)
    return rows


def _cal(d: str, dates: list[str], i: int, prefix: str) -> dict:
    return {
        "date": d, "long": _longdate(d), "weekday": date.fromisoformat(d).strftime("%A").upper(),
        "prev": dates[i + 1] if i + 1 < len(dates) else None, "next": dates[i - 1] if i > 0 else None, "prefix": prefix,
    }


CHIP_NAME = {
    "kpszsu": "Air Force UA", "generalstaff": "General Staff UA", "mod_russia": "MoD Russia", "deepstate": "DeepState",
    "militarnyi": "Militarnyi", "kyivindependent": "Kyiv Independent", "ukrinform": "Ukrinform", "defence_express": "Defense Express",
    "gov_belgorod": "Gov. Belgorod", "gov_bryansk": "Gov. Bryansk", "gov_kursk": "Gov. Kursk", "gov_rostov": "Gov. Rostov",
    "astra": "ASTRA", "oryx_russia": "Oryx RU losses", "oryx_ukraine": "Oryx UA losses",
}


def _srcs(evs: list[dict], sources: list[dict]) -> list[dict]:
    return [
        {"id": src["id"], "chip": CHIP_NAME.get(src["id"], src["name"]), "side": src["side"], "n": sum(1 for e in evs if e["source_id"] == src["id"])}
        for src in sources
    ]


def _cats(evs: list[dict]) -> list[dict]:
    return [{"key": k, "label": label, "n": sum(1 for e in evs if e["category"] == k)} for k, label in CATEGORIES]


def _fmt(v) -> str:
    return f"{v:,}" if isinstance(v, int) else str(v)


def render(site_dir: pathlib.Path, days: dict[str, list[dict]], sources: list[dict]) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    env.filters["countlabel"] = lambda k: COUNT_LABELS.get(k, k.replace("_", " "))
    env.filters["side"] = lambda s: SIDE_LABELS.get(s, s)
    env.filters["longdate"] = _longdate
    env.filters["fmt"] = _fmt
    env.filters["catlabel"] = lambda k: CATEGORY_LABELS.get(k, k)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    base_ctx = {"sources": sources, "generated_at": generated}

    dates = sorted(days, reverse=True)
    sheets = {d: _flat(returns(days[d], days[dates[i + 1]] if i + 1 < len(dates) else None)) for i, d in enumerate(dates)}
    latest = dates[0] if dates else date.today().isoformat()

    def series(key: str, end: str, n: int, side: str = "ua") -> list[int | None]:
        return [_numeric(sheets[d][key][side]) if d in sheets else None for d in _date_range(end, n)]

    strip_dates = _date_range(latest, STRIP_DAYS)
    strip_vals = series("uav_launched", latest, STRIP_DAYS)
    strip_max = max((v for v in strip_vals if v), default=0) or 1

    def strip_for(current: str) -> list[dict]:
        return [
            {"date": d, "value": v, "pct": round(100 * v / strip_max) if v else 0, "has_page": d in days, "current": d == current}
            for d, v in zip(strip_dates, strip_vals)
        ]

    day_tpl = env.get_template("day.html")
    for i, d in enumerate(dates):
        evs = days[d]
        sheet = returns(evs, days[dates[i + 1]] if i + 1 < len(dates) else None)
        for g in sheet:
            for r in g["rows"]:
                side = "ua" if r["ua"] and isinstance(r["ua"]["value"], int) else ("ru" if r["ru"] and isinstance(r["ru"]["value"], int) else None)
                r["spark"] = sparkline(series(r["key"], d, SPARK_DAYS, side)) if side else ""
        flat = _flat(sheet)
        html = day_tpl.render(
            title=f"{_longdate(d)} · The Ukraine War Ledger",
            nav="day",
            day={"date": d, "groups": group(evs), "n": len(evs)},
            sheet=sheet,
            facts=facts(flat, lambda key, side: sparkline(series(key, d, SPARK_DAYS, side))),
            map_svg=geo.render_map(evs),
            where=[w for w in where(evs) if w["kind"] == "groups"],
            cats=_cats(evs),
            srcs=_srcs(evs, sources),
            cal=_cal(d, dates, i, ""),
            **base_ctx,
        )
        (site_dir / f"{d}.html").write_text(html, encoding="utf-8")
        if i == 0:
            (site_dir / "index.html").write_text(html, encoding="utf-8")
    frag_tpl = env.get_template("wire_rows.html")
    frag_dir = site_dir / "wire-data"
    frag_dir.mkdir(exist_ok=True)
    for stale in site_dir.glob("wire-????-??-??.html"):
        stale.unlink()
    fragments = {d: frag_tpl.render(date=d, long=_longdate(d), rows=wire(days[d])) for d in dates}
    for d, html in fragments.items():
        (frag_dir / f"{d}.html").write_text(html, encoding="utf-8")
    first = dates[0] if dates else None
    (site_dir / "wire.html").write_text(
        env.get_template("wire.html").render(
            title="Wire · The Ukraine War Ledger",
            nav="wire",
            body_class="wire",
            first_rows=fragments[first] if first else "",
            first_count=len(days[first]) if first else 0,
            earlier=dates[1:],
            cats=_cats(days[first]) if first else _cats([]),
            srcs=_srcs(days[first] if first else [], sources),
            **base_ctx,
        ),
        encoding="utf-8",
    )

    if not dates:
        (site_dir / "index.html").write_text(
            day_tpl.render(title="The Ukraine War Ledger", nav="day", day={"date": latest, "groups": [], "n": 0}, sheet=returns([]), facts=facts(_flat(returns([])), lambda k, s: ""), map_svg=None, where=[], cats=_cats([]), srcs=_srcs([], sources), cal=_cal(latest, [latest], 0, ""), **base_ctx),
            encoding="utf-8",
        )

    columns = [
        ("uav_launched", "ua", "UAVs launched"), ("intercepted", "ua", "Intercepted"), ("impact_locations", "ua", "Impact locations"),
        ("clashes", "ua", "Clashes"), ("guided_bombs", "ua", "Guided bombs"), ("settlements_shelled", "ua", "Settlements shelled"),
        ("taken", "ua", "Taken (DeepState)"), ("intercepted_over_russia", "ru", "UAVs over Russia (MoD)"),
        ("loss_personnel", "ua", "Russian personnel (GS)"), ("loss_personnel", "ru", "Ukrainian personnel (MoD)"),
    ]
    archive_rows = []
    for d in dates:
        archive_rows.append({"date": d, "n": len(days[d]), "cells": [_numeric(sheets[d][k][side]) for k, side, _ in columns]})
    (site_dir / "archive.html").write_text(
        env.get_template("archive.html").render(title="Archive · The Ukraine War Ledger", nav="archive", columns=[c[2] for c in columns], rows=archive_rows, **base_ctx),
        encoding="utf-8",
    )

    (site_dir / "events.json").write_text(
        json.dumps({"generated_at": generated, "days": [{"date": d, "events": days[d]} for d in dates]}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    with (site_dir / "events.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "time", "category", "source", "side", "actor", "target", "action", "weapons", "counts", "locations", "quote", "url"])
        for d in dates:
            for e in days[d]:
                w.writerow([
                    e["date"], e.get("time") or "", e["category"], e["source_name"], e["source_side"],
                    e.get("actor") or "", e.get("target") or "", e.get("action") or "",
                    "; ".join(x["name"] for x in e["weapons"]), json.dumps(e["counts"], ensure_ascii=False),
                    "; ".join(e["locations"]), e["quote"], e["source_url"],
                ])
    shutil.copy(TEMPLATES / "style.css", site_dir / "style.css")
    shutil.copy(TEMPLATES / "ledger.js", site_dir / "ledger.js")

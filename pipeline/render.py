"""Render the static site from the day files."""
from __future__ import annotations

import csv
import json
import pathlib
import shutil
from datetime import date, datetime, timezone

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .extract.common import CATEGORIES, SIDE_LABELS

TEMPLATES = pathlib.Path(__file__).parent / "templates"

COUNT_LABELS = {
    "launched": "launched",
    "intercepted": "intercepted",
    "impacts": "impacts recorded",
    "impact_locations": "impact locations",
    "debris_locations": "debris fall locations",
    "shahed_of_which": "of which Shahed",
    "lost_from_radar": "lost from radar",
    "clashes": "combat clashes",
    "missile_strikes": "missile strikes",
    "air_strikes": "air strikes",
    "missiles_used": "missiles used",
    "guided_bombs": "guided aerial bombs dropped",
    "kamikaze_drones": "kamikaze drones used",
    "shellings": "shellings",
    "mlrs_shellings": "of which MLRS",
    "intercepted_claimed": "UAVs intercepted, as claimed",
    "concentration_areas_struck": "concentration areas struck, as claimed",
}


def group(events: list[dict]) -> list[dict]:
    out = []
    for key, label in CATEGORIES:
        evs = [e for e in events if e["category"] == key]
        if evs:
            out.append({"key": key, "label": label, "events": evs})
    return out


def headline(events: list[dict]) -> list[dict]:
    rows: list[dict] = []
    air = [e for e in events if e["category"] == "air_attack" and e["extraction"] == "structured" and e["counts"]]
    if air:
        launched = sum(e["counts"].get("launched", 0) for e in air)
        intercepted = sum(e["counts"].get("intercepted", 0) for e in air)
        impacts = sum(e["counts"].get("impacts", 0) for e in air)
        rows.append({"label": "Air attack on Ukraine (Air Force)", "value": f"{launched} launched · {intercepted} intercepted · {impacts} impacts"})
    clashes = sum(e["counts"].get("clashes", 0) for e in events if e["category"] == "front_activity")
    if clashes:
        rows.append({"label": "Combat clashes (General Staff)", "value": str(clashes)})
    ru = sum(e["counts"].get("intercepted_claimed", 0) for e in events if e["category"] == "strikes_in_russia")
    if ru:
        rows.append({"label": "UAVs over Russia, intercepted as claimed (Russian MoD)", "value": str(ru)})
    front = [e for e in events if e["category"] == "front_line" and e["source_id"] == "deepstate"]
    if front:
        tally = {}
        for e in front:
            tally[e["action"]] = tally.get(e["action"], 0) + len(e["locations"])
        rows.append({"label": "Front line (DeepState)", "value": " · ".join(f"{v} {k}" for k, v in tally.items())})
    losses = [e for e in events if e["category"] == "losses_claimed" and e["breakdown"]]
    if losses:
        want = {"personnel", "tanks", "artillery systems"}
        parts = [f"+{b['delta']:,} {b['label']}" for b in losses[0]["breakdown"] if b["label"] in want]
        if parts:
            rows.append({"label": "Russian losses in 24 h, as claimed (General Staff)", "value": " · ".join(parts)})
    return rows


def _longdate(d: str) -> str:
    dt = date.fromisoformat(d)
    return f"{dt.day} {dt:%B %Y}"


def render(site_dir: pathlib.Path, days: dict[str, list[dict]], sources: list[dict]) -> None:
    site_dir.mkdir(parents=True, exist_ok=True)
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))
    env.filters["countlabel"] = lambda k: COUNT_LABELS.get(k, k.replace("_", " "))
    env.filters["side"] = lambda s: SIDE_LABELS.get(s, s)
    env.filters["longdate"] = _longdate
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    base_ctx = {"sources": sources, "generated_at": generated}

    dates = sorted(days, reverse=True)
    day_tpl = env.get_template("day.html")
    for i, d in enumerate(dates):
        evs = days[d]
        html = day_tpl.render(
            title=f"{_longdate(d)} · The Ukraine War Ledger",
            day={"date": d, "groups": group(evs), "headline": headline(evs), "n": len(evs)},
            prev=dates[i + 1] if i + 1 < len(dates) else None,
            next=dates[i - 1] if i > 0 else None,
            **base_ctx,
        )
        (site_dir / f"{d}.html").write_text(html, encoding="utf-8")
        if i == 0:
            (site_dir / "index.html").write_text(html, encoding="utf-8")
    if not dates:
        (site_dir / "index.html").write_text(
            day_tpl.render(title="The Ukraine War Ledger", day={"date": date.today().isoformat(), "groups": [], "headline": [], "n": 0}, prev=None, next=None, **base_ctx),
            encoding="utf-8",
        )

    archive = [{"date": d, "n": len(days[d]), "headline": headline(days[d])} for d in dates]
    (site_dir / "archive.html").write_text(
        env.get_template("archive.html").render(title="Archive · The Ukraine War Ledger", days=archive, **base_ctx), encoding="utf-8"
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

"""Day files under data/: one JSON file per Kyiv date, merged by entry id."""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone

from .extract.common import CATEGORY_ORDER, Event


def _path(data_dir: pathlib.Path, day: str) -> pathlib.Path:
    return data_dir / f"{day}.json"


def load_day(data_dir: pathlib.Path, day: str) -> list[dict]:
    p = _path(data_dir, day)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("events", [])


def _sort_key(e: dict) -> tuple:
    return (CATEGORY_ORDER.get(e["category"], 99), 0 if e["extraction"] == "structured" else 1, e.get("time") or "", e["source_name"])


def merge_day(data_dir: pathlib.Path, day: str, events: list[Event]) -> list[dict]:
    data_dir.mkdir(parents=True, exist_ok=True)
    existing = {e["id"]: e for e in load_day(data_dir, day)}
    for ev in events:
        d = ev.to_dict()
        if d["id"] in existing:
            old = existing[d["id"]]
            urls = {r["url"] for r in old.get("also_reported_by", [])}
            for r in d["also_reported_by"]:
                if r["url"] not in urls:
                    old.setdefault("also_reported_by", []).append(r)
            # Structured figures can grow during the day (the Air Force updates its tally).
            if d["extraction"] == "structured":
                old["counts"], old["weapons"], old["breakdown"] = d["counts"], d["weapons"], d["breakdown"]
                old["time"] = d["time"] or old.get("time")
        else:
            existing[d["id"]] = d
    merged = sorted(existing.values(), key=_sort_key)
    payload = {"date": day, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "events": merged}
    _path(data_dir, day).write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    return merged


def load_all(data_dir: pathlib.Path) -> dict[str, list[dict]]:
    days: dict[str, list[dict]] = {}
    if not data_dir.exists():
        return days
    for p in sorted(data_dir.glob("????-??-??.json")):
        days[p.stem] = json.loads(p.read_text(encoding="utf-8")).get("events", [])
    return days


def write_index(data_dir: pathlib.Path, days: dict[str, list[dict]]) -> None:
    index = [{"date": d, "entries": len(evs)} for d, evs in sorted(days.items(), reverse=True)]
    (data_dir / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")

"""Manual corrections from overrides.yaml, applied after extraction.

Three actions: suppress an entry, correct fields on it, or fold it into
another entry as "also reported by". Every applied override is kept for the
Corrections page, and an override whose entry no longer appears is listed
there as unmatched, so a stale rule is visible rather than silent.
"""
from __future__ import annotations

import logging
import pathlib

import yaml

from .extract.common import Event

log = logging.getLogger(__name__)
ACTIONS = ("suppress", "correct", "duplicate_of")


def load(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = data.get("overrides") or []
    out = []
    for r in rules:
        if not isinstance(r, dict) or r.get("action") not in ACTIONS or not r.get("id"):
            log.warning("override skipped, malformed: %r", r)
            continue
        out.append(r)
    return out


def apply(events: list[Event], rules: list[dict]) -> tuple[list[Event], list[dict]]:
    """Return (events after overrides, report rows for the Corrections page)."""
    by_id = {e.id: e for e in events}
    drop: set[str] = set()
    report: list[dict] = []
    for r in rules:
        row = {"id": r["id"], "action": r["action"], "reason": r.get("reason", ""), "added": str(r.get("added", "")), "matched": r["id"] in by_id}
        e = by_id.get(r["id"])
        if e is not None:
            row.update({"date": e.date, "source_name": e.source_name, "source_url": e.source_url, "quote": (e.quote_en or e.quote)[:140]})
            if r["action"] == "suppress":
                drop.add(e.id)
            elif r["action"] == "correct":
                for key, value in (r.get("fields") or {}).items():
                    if key in ("id", "source_id", "source_url"):
                        continue
                    if key == "counts" and isinstance(value, dict):
                        e.counts = {**e.counts, **value}
                    elif hasattr(e, key):
                        setattr(e, key, value)
                e.corrected = r.get("reason") or "corrected"
            elif r["action"] == "duplicate_of":
                target = by_id.get(str(r.get("target", "")))
                row["target"] = r.get("target")
                if target is None or target.id == e.id:
                    row["matched"] = False
                else:
                    target.also_reported_by.append({"name": e.source_name, "url": e.source_url, "quote": e.quote})
                    drop.add(e.id)
        report.append(row)
    return [e for e in events if e.id not in drop], report

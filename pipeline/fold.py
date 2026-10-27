"""Collapse entries that report the same thing.

Two passes:
1. Identical headlines on the same day and category keep the first copy and
   list the others under also_reported_by.
2. A rules-based entry whose numbers match a structured entry of the same day
   and category (two or more shared numbers) is folded into that entry.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .extract.common import Event

_NUM = re.compile(r"\d[\d,  ]*\d|\d")


def _numbers_in_text(text: str) -> set[int]:
    out: set[int] = set()
    for raw in _NUM.findall(text):
        try:
            n = int(re.sub(r"[,  ]", "", raw))
        except ValueError:
            continue
        if n >= 2 and not (1990 <= n <= 2100):
            out.add(n)
    return out


def _numbers_in_structure(e: Event) -> set[int]:
    out: set[int] = set()
    for v in e.counts.values():
        if isinstance(v, int):
            out.add(v)
    for w in e.weapons:
        for k, v in w.items():
            if k != "name" and isinstance(v, int):
                out.add(v)
    for b in e.breakdown:
        for k in ("count", "delta"):
            if isinstance(b.get(k), int):
                out.add(b[k])
    return {n for n in out if n >= 2}


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def fold(events: list[Event]) -> list[Event]:
    kept: list[Event] = []
    seen: dict[tuple, Event] = {}
    for e in events:
        key = (e.date, e.category, _norm(e.quote))
        if key in seen:
            seen[key].also_reported_by.append({"name": e.source_name, "url": e.source_url})
            continue
        seen[key] = e
        kept.append(e)

    structured = defaultdict(list)
    for e in kept:
        if e.extraction == "structured":
            structured[(e.date, e.category)].append(e)

    out: list[Event] = []
    for e in kept:
        if e.extraction == "structured":
            out.append(e)
            continue
        nums = _numbers_in_text(f"{e.quote} {e.detail or ''}")
        host = None
        for s in structured.get((e.date, e.category), []):
            if len(nums & _numbers_in_structure(s)) >= 2:
                host = s
                break
        if host is not None:
            host.also_reported_by.append({"name": e.source_name, "url": e.source_url, "quote": e.quote})
        else:
            out.append(e)
    return out

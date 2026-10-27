"""Oryx: visually confirmed equipment losses, cumulative, per category."""
from __future__ import annotations

import re

from ..sources.telegram import Post
from .common import Event, kyiv_date, source_fields, to_int

TOTAL = re.compile(r"^(Russia|Ukraine)\s*[-–—]\s*([\d,]+)(?:,\s*of which:?\s*(.*))?$", re.I)
CATEGORY = re.compile(r"^(.+?)\s*\(([\d,]+),\s*of which:?\s*(.*)\)\s*$", re.I)
PART = re.compile(r"(destroyed|damaged|abandoned|captured)\s*:?\s*([\d,]+)", re.I)


def extract(post: Post, source: dict) -> list[Event]:
    total = None
    parts: dict = {}
    rows: list[dict] = []
    for line in post.text.splitlines():
        m = TOTAL.match(line.strip())
        if m and total is None:
            total = to_int(m.group(2))
            parts = {k.lower(): to_int(v) for k, v in PART.findall(m.group(3) or "")}
            continue
        m = CATEGORY.match(line.strip())
        if m:
            rows.append({"label": m.group(1).strip(), "count": to_int(m.group(2))})
    if total is None and not rows:
        return []
    counts = {"total": total} if total is not None else {}
    counts.update(parts)
    return [
        Event(
            date=kyiv_date(post.dt),
            category="losses_claimed",
            actor="Oryx",
            target=source.get("target", ""),
            action="visually confirmed equipment losses, cumulative",
            counts=counts,
            breakdown=rows,
            quote=post.text.splitlines()[0][:300],
            lang="en",
            extraction="structured",
            source_url=post.url,
            **source_fields(source),
        )
    ]

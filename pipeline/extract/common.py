"""Shared event model and helpers."""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

KYIV = ZoneInfo("Europe/Kyiv")

# (key, label) in display order.
CATEGORIES = [
    ("air_attack", "Air attacks on Ukraine"),
    ("strikes_in_russia", "Strikes in Russia and occupied territory"),
    ("front_line", "Front line changes"),
    ("front_activity", "Front activity"),
    ("losses_claimed", "Claimed losses"),
    ("air_defense", "Air defence"),
    ("field_adaptation", "Field adaptations"),
    ("weapons_deliveries", "Weapons and deliveries"),
    ("naval", "Naval"),
    ("infrastructure", "Infrastructure"),
]
CATEGORY_LABELS = dict(CATEGORIES)
CATEGORY_ORDER = {key: i for i, (key, _) in enumerate(CATEGORIES)}

SIDE_LABELS = {
    "ua_official": "Ukrainian official",
    "ru_official": "Russian official",
    "osint": "OSINT",
    "media": "Media",
}


@dataclass
class Event:
    date: str
    category: str
    source_id: str
    source_name: str
    source_side: str
    source_url: str
    quote: str
    time: str | None = None
    actor: str | None = None
    target: str | None = None
    action: str | None = None
    detail: str | None = None
    weapons: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    breakdown: list[dict] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    lang: str = "en"
    extraction: str = "rules"  # "structured" or "rules"
    also_reported_by: list[dict] = field(default_factory=list)
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raw = "|".join([self.source_id, self.source_url, self.category, self.quote[:200]])
            self.id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        return asdict(self)


def kyiv_date(dt: datetime) -> str:
    return dt.astimezone(KYIV).date().isoformat()


def to_int(s: str) -> int:
    return int(re.sub(r"[\s ,]", "", s))


def first_sentence(text: str, limit: int = 320) -> str:
    text = " ".join(text.split())
    m = re.search(r"^(.+?[.!?])(\s|$)", text)
    s = m.group(1) if m else text
    if len(s) > limit:
        s = s[: limit - 1].rstrip() + "…"
    return s


def source_fields(source: dict) -> dict:
    return {
        "source_id": source["id"],
        "source_name": source["name"],
        "source_side": source["side"],
    }

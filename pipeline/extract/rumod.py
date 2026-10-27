"""Ministry of Defence of Russia (t.me/mod_russia): interception claims,
strike claims and claimed captures of settlements."""
from __future__ import annotations

import re

from ..sources.telegram import Post
from .common import Event, first_sentence, kyiv_date, source_fields
from .lexicon import find_weapons, translit_region

INTERCEPT = re.compile(
    r"(?:перехвачен\w*\s+и\s+уничтожен\w*|уничтожен\w*\s+и\s+перехвачен\w*|уничтожен\w*|перехвачен\w*)"
    r"\s+(\d+)\s+(?:украинск\w+\s+)?(?:беспилотн\w+|бпла|бвс)",
    re.I,
)
REGION = re.compile(r"(\d+)\s*[–—-]\s*над\s+(?:территори\w+|акватори\w+)\s+([^,;.\n]+)")
WINDOW = re.compile(r"с\s+(\d{1,2}[:.]\d{2})\s+(?:мск\s+)?до\s+(\d{1,2}[:.]\d{2})")
CAPTURED = re.compile(
    r"освобо\w+\s+населенн\w+\s+пункт\w*\s+([А-ЯЁ][^\s,.;]+(?:\s(?![А-ЯЁ][^\s,.;]+\s+област)[А-ЯЁ][^\s,.;]+)?)"
)
STRIKE = re.compile(r"групповой\s+удар|массированный\s+удар|нанес\w*\s+удар", re.I)


def extract(post: Post, source: dict) -> list[Event]:
    text = post.text
    events: list[Event] = []
    common = dict(
        date=kyiv_date(post.dt),
        quote=first_sentence(text),
        lang="ru",
        source_url=post.url,
        **source_fields(source),
    )

    m = INTERCEPT.search(text)
    if m:
        regions = [(translit_region(r), int(n)) for n, r in REGION.findall(text)]
        window = "overnight" if "прошедшей ночи" in text.lower() else None
        w = WINDOW.search(text)
        if w:
            window = f"{w.group(1).replace('.', ':')} to {w.group(2).replace('.', ':')} MSK"
        events.append(
            Event(
                category="strikes_in_russia",
                actor="Ukraine",
                target="Russia",
                action="UAVs intercepted, as claimed" + (f" ({window})" if window else ""),
                counts={"intercepted_claimed": int(m.group(1))},
                breakdown=[{"label": r, "count": n} for r, n in regions],
                locations=[r for r, _ in regions],
                extraction="structured",
                **common,
            )
        )

    for name in CAPTURED.findall(text):
        events.append(
            Event(
                category="front_line",
                actor="Russia",
                target="Ukraine",
                action="settlement captured, as claimed",
                locations=[name],
                extraction="structured",
                **common,
            )
        )

    if not events and STRIKE.search(text):
        events.append(
            Event(
                category="air_attack",
                actor="Russia",
                target="Ukraine",
                action="strike, as claimed",
                weapons=[{"name": n} for n in find_weapons(text)],
                extraction="rules",
                **common,
            )
        )
    return events

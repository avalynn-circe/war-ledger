"""Russian regional governors (Belgorod, Bryansk, Kursk, Rostov) on Telegram:
attacks on their regions, with casualties and drones shot down as stated."""
from __future__ import annotations

import re

from ..sources.telegram import Post
from .common import KYIV, Event, first_sentence, kyiv_date, source_fields
from .lexicon import find_weapons
from .rumod import _ru_words_to_digits

TRIGGER = re.compile(r"бпла|беспилотн|дрон|обстрел|ракет|атак[аиуе]|сбит|прилет|fpv", re.I)
KILLED = re.compile(r"погиб(?:ли|ла|ло|)\s+(\d+)|(\d+)\s+(?:человек[а]?\s+|мирн\w+\s+жител\w+\s+)?погиб", re.I)
INJURED = re.compile(r"(?:ранен[ыоа]?|пострадал[иао]?)\s+(\d+)|(\d+)\s+(?:человек[а]?\s+|мирн\w+\s+жител\w+\s+)?(?:ранен|пострадал)", re.I)
SHOT_DOWN = re.compile(r"(?:сбит[ыоа]?|уничтожен[ыоа]?|подавлен[ыоа]?|перехвачен[ыоа]?)\s+(\d+)\s+(?:беспилотн|бпла|дрон)|(\d+)\s+(?:беспилотник\w*|бпла|дрон\w*)\s+(?:сбит|уничтожен|подавлен)", re.I)


def _first_int(rx: re.Pattern, text: str) -> int | None:
    m = rx.search(text)
    if not m:
        return None
    return int(next(g for g in m.groups() if g))


def extract(post: Post, source: dict) -> list[Event]:
    if not TRIGGER.search(post.text):
        return []
    text = _ru_words_to_digits(post.text)
    counts: dict = {}
    for key, rx in (("killed", KILLED), ("injured", INJURED), ("uav_shot_down", SHOT_DOWN)):
        n = _first_int(rx, text)
        if n is not None:
            counts[key] = n
    return [
        Event(
            date=kyiv_date(post.dt),
            time=post.dt.astimezone(KYIV).strftime("%H:%M"),
            category="strikes_in_russia",
            actor="Ukraine",
            target="Russia",
            action="attack on the region, as reported by the governor",
            counts=counts,
            weapons=[{"name": n} for n in find_weapons(post.text)],
            locations=[source.get("region", "")] if source.get("region") else [],
            quote=first_sentence(post.text),
            lang="ru",
            extraction="rules",
            source_url=post.url,
            **source_fields(source),
        )
    ]

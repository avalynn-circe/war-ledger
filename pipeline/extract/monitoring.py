"""Independent monitoring channels (ASTRA): strikes and their effects, as
reported, labelled unconfirmed. Direction comes from the first place named."""
from __future__ import annotations

import re

from ..sources.telegram import Post
from .common import KYIV, Event, first_sentence, kyiv_date, source_fields
from .lexicon import find_places, find_weapons

TRIGGER = re.compile(r"удар|взрыв|пожар|атак[аиуе]|бпла|дрон|поражен|горит|нпз|аэродром|ракет|прилет|сбит|обстрел", re.I)


def extract(post: Post, source: dict) -> list[Event]:
    if not TRIGGER.search(post.text):
        return []
    places = find_places(post.text)
    if not places:
        return []
    side = places[0][1]
    if side == "ru":
        category, actor, target = "strikes_in_russia", "Ukraine", "Russia"
    elif side == "ua":
        category, actor, target = "air_attack", "Russia", "Ukraine"
    else:
        return []
    return [
        Event(
            date=kyiv_date(post.dt),
            time=post.dt.astimezone(KYIV).strftime("%H:%M"),
            category=category,
            actor=actor,
            target=target,
            action="as reported, unconfirmed",
            weapons=[{"name": n} for n in find_weapons(post.text)],
            locations=[name for name, _ in places][:6],
            quote=first_sentence(post.text),
            lang="ru",
            extraction="rules",
            source_url=post.url,
            **source_fields(source),
        )
    ]

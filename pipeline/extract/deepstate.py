"""DeepState (t.me/DeepStateUA): map update posts naming front line changes."""
from __future__ import annotations

import re

from ..sources.telegram import Post
from .common import Event, first_sentence, kyiv_date, source_fields

OCCUPIED = re.compile(r"[Вв]орог\s+окупував\s+(.+?)(?=\s+(?:та|і|й)\s+просунувся|[.;]|$)")
ADVANCED = re.compile(r"просунувся\s+(?:поблизу|біля|в\s+районі|у\s+районі|в|у|на)\s+(.+?)(?=[.;]|$)")
LIBERATED = re.compile(
    r"(?:Сили\s+[Оо]борони|ЗСУ|Сили\s+[Оо]борони\s+України)\s+"
    r"(?:звільнили|відновили\s+контроль\s+над|зачистили|відкинули\s+ворога\s+з)\s+(.+?)(?=[.;]|$)"
)


def _split(names: str) -> list[str]:
    parts = re.split(r",\s*|\s+та\s+|\s+і\s+|\s+й\s+", names.strip())
    return [p.strip(" .") for p in parts if p.strip(" .")]


def extract(post: Post, source: dict) -> list[Event]:
    text = " ".join(post.text.split())
    events: list[Event] = []
    common = dict(
        date=kyiv_date(post.dt),
        category="front_line",
        quote=first_sentence(post.text),
        lang="uk",
        extraction="structured",
        source_url=post.url,
        **source_fields(source),
    )
    for action, rx, actor, target in [
        ("occupied", OCCUPIED, "Russia", "Ukraine"),
        ("advanced near", ADVANCED, "Russia", "Ukraine"),
        ("liberated", LIBERATED, "Ukraine", "Russia"),
    ]:
        names: list[str] = []
        for m in rx.finditer(text):
            names.extend(_split(m.group(1)))
        if names:
            events.append(Event(actor=actor, target=target, action=action, locations=names, **common))
    return events

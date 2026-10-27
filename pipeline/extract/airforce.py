"""Air Force of Ukraine (t.me/kpszsu): overnight air attack reports.

A typical post reads (Ukrainian):

    У ніч на 26 жовтня (з 18:00 25 жовтня) противник атакував 101-м ударним
    БпЛА типу Shahed, Гербера та дронами інших типів з напрямків: Курськ,
    Міллерово ... та 4-ма балістичними ракетами «Іскандер-М» ...
    Станом на 09:00 протиповітряною обороною збито/подавлено 90 ворожих БпЛА ...
    Зафіксовано влучання 4 балістичних ракет та 11 ударних БпЛА на 9 локаціях,
    а також падіння уламків на 2 локаціях.

The extractor splits each paragraph at its numbers and classifies the words
that follow each number.
"""
from __future__ import annotations

import re
from datetime import date

from ..sources.telegram import Post
from .common import KYIV, Event, first_sentence, kyiv_date, source_fields
from .lexicon import translit_place, translit_weapon_name

UK_MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4, "травня": 5, "червня": 6,
    "липня": 7, "серпня": 8, "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
NUM_CHUNK = re.compile(r"(\d+)(?:-[а-яіїє]{1,3})?\s+([^0-9]*)")
QUOTED = re.compile(r"[«\"“]([^»\"”]+)[»\"”]")
SHAHED = "Shahed/Gerbera-type strike UAV"


def _named(chunk: str) -> str | None:
    names = QUOTED.findall(chunk)
    return translit_weapon_name(names[0]) if names else None


def classify_chunk(chunk: str) -> str | None:
    """Return a weapon name, a marker starting with "__", or None."""
    c = chunk.lower()
    if "засоб" in c and "повітряного нападу" in c:
        return "__total__"
    if "із них" in c or "з них" in c:
        return "__of_which__"
    if "локац" in c:
        return "__locations__"
    name = _named(chunk)
    if "аеробаліст" in c:
        return f"{name} aeroballistic missile" if name else "Kh-47M2 Kinzhal aeroballistic missile"
    if "баліст" in c:
        return f"{name} ballistic missile" if name else "ballistic missile"
    if "крилат" in c:
        return f"{name} cruise missile" if name else "cruise missile"
    if "керован" in c and "авіаційн" in c:
        return f"{name} guided air-launched missile" if name else "guided air-launched missile"
    if "зенітн" in c and "ракет" in c:
        return "S-300/S-400 surface-to-air missile"
    if "протикорабельн" in c or "онікс" in c:
        return "P-800 Onyx anti-ship missile"
    if "циркон" in c:
        return "3M22 Zircon missile"
    if "розвідувальн" in c and ("бпла" in c or "дрон" in c):
        return "reconnaissance UAV"
    if "бпла" in c or "шахед" in c or "shahed" in c or "дрон" in c:
        return SHAHED
    if "ракет" in c:
        return f"{name} missile" if name else "missile"
    return None


def chunks(text: str) -> list[tuple[int, str | None]]:
    return [(int(m.group(1)), classify_chunk(m.group(2))) for m in NUM_CHUNK.finditer(text)]


def _after(text: str, marker: str) -> str:
    i = text.lower().find(marker)
    return text[i:] if i >= 0 else ""


def extract(post: Post, source: dict) -> list[Event]:
    text = post.text
    low = text.lower()
    if "атакував" not in low or not ("бпла" in low or "ракет" in low):
        return []

    paras = [p.strip() for p in text.split("\n") if p.strip()]
    launched_p = next((p for p in paras if "атакував" in p.lower()), "")
    down_p = next((p for p in paras if "збито" in p.lower()), "")
    hit_p = next((p for p in paras if "влучання" in p.lower()), "")

    weapons: dict[str, dict] = {}
    counts: dict = {}

    def add(name: str, key: str, n: int) -> None:
        # "4 балістичних ракет" in the impact line refers to the named
        # "Іскандер-М" missiles of the launch line: merge generic into named.
        if name not in weapons:
            for existing in weapons:
                if existing.endswith(name) or name.endswith(existing):
                    name = existing
                    break
        w = weapons.setdefault(name, {"name": name})
        w[key] = w.get(key, 0) + n

    launched_clean = re.sub(r"\([^)]*\)", "", launched_p)
    lp = _after(launched_clean, "атакував")
    total = None
    launched_sum = 0
    for n, kind in chunks(lp):
        if kind == "__total__":
            total = n
        elif kind == "__of_which__":
            counts["shahed_of_which"] = n
        elif kind and not kind.startswith("__"):
            add(kind, "launched", n)
            launched_sum += n
    counts["launched"] = total if total is not None else launched_sum

    if down_p:
        dp = _after(down_p, "збито")
        dp_main = re.split(r"локаційно\s+втрачен", dp)[0]
        intercepted = 0
        for n, kind in chunks(dp_main):
            if kind and not kind.startswith("__"):
                add(kind, "intercepted", n)
                intercepted += n
        counts["intercepted"] = intercepted
        m = re.search(r"локаційно\s+втрачен\w*\s+(\d+)", down_p)
        if m:
            counts["lost_from_radar"] = int(m.group(1))

    if hit_p:
        debris = re.search(r"падіння\s+уламків\s+на\s+(\d+)\s+локац", hit_p)
        hp = re.split(r"падіння\s+уламків", _after(hit_p, "влучання"))[0]
        impacts = 0
        for n, kind in chunks(hp):
            if kind == "__locations__":
                counts["impact_locations"] = n
            elif kind and not kind.startswith("__"):
                add(kind, "impacts", n)
                impacts += n
        counts["impacts"] = impacts
        if debris:
            counts["debris_locations"] = int(debris.group(1))

    day = kyiv_date(post.dt)
    m = re.search(r"[Уу]\s+ніч\s+на\s+(\d{1,2})\s+([а-яіїє]+)", text)
    if m and m.group(2) in UK_MONTHS:
        try:
            day = date(post.dt.astimezone(KYIV).year, UK_MONTHS[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            pass
    m = re.search(r"[Сс]таном\s+на\s+(\d{1,2}:\d{2})", text)
    time = m.group(1) if m else None

    locations: list[str] = []
    m = re.search(r"з\s+напрямк\w*:\s*(.+?)(?:(?<!\bм)\.|;|,\s*близько|$)", lp, re.S)
    if m:
        for part in m.group(1).split(","):
            place = translit_place(part)
            if place and place not in locations:
                locations.append(place)

    return [
        Event(
            date=day,
            time=time,
            category="air_attack",
            actor="Russia",
            target="Ukraine",
            action="air attack",
            weapons=list(weapons.values()),
            counts=counts,
            locations=locations,
            quote=first_sentence(text),
            lang="uk",
            extraction="structured",
            source_url=post.url,
            **source_fields(source),
        )
    ]

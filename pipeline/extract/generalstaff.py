"""General Staff of the Armed Forces of Ukraine (t.me/GeneralStaffZSU).

Two post types are read: the cumulative "enemy losses" table and the
operational report with the number of combat clashes and enemy strikes.
"""
from __future__ import annotations

import re
from datetime import date

from ..sources.telegram import Post
from .common import Event, first_sentence, kyiv_date, source_fields, to_int

LOSS_LINE = re.compile(
    r"^\s*(.+?)\s*[‒–—\-]\s*(?:близько\s+)?(\d[\d\s ]*?)\s*\(\s*\+?\s*(\d[\d\s ]*?)\s*\)",
    re.M,
)
PERIOD = re.compile(r"з\s+(\d{2}\.\d{2}\.\d{2,4})\s+по\s+(\d{2}\.\d{2}\.\d{2,4})")

# The operational report writes small numbers as words: "одного ракетного та
# 48 авіаційних ударів, застосувавши дві ракети".
NUMBER_WORDS = {
    1: r"одн(?:ого|у|ієї|ин|а|е)", 2: r"дв(?:а|і|ох)", 3: r"тр(?:и|ьох)", 4: r"чотир(?:и|ьох)",
    5: r"п'ят(?:ь|и)", 6: r"шіст(?:ь|и)", 7: r"с(?:і|е)м(?:и|ь)?", 8: r"вісім|восьми", 9: r"дев'ят(?:ь|и)",
    10: r"десят(?:ь|и)", 11: r"одинадцят(?:ь|и)", 12: r"дванадцят(?:ь|и)", 13: r"тринадцят(?:ь|и)",
    14: r"чотирнадцят(?:ь|и)", 15: r"п'ятнадцят(?:ь|и)", 16: r"шістнадцят(?:ь|и)", 17: r"сімнадцят(?:ь|и)",
    18: r"вісімнадцят(?:ь|и)", 19: r"дев'ятнадцят(?:ь|и)", 20: r"двадцят(?:ь|и)",
}
_NUMBER_WORDS = [(re.compile(rf"\b(?:{pat})\b", re.I), str(n)) for n, pat in sorted(NUMBER_WORDS.items(), reverse=True)]


def words_to_digits(text: str) -> str:
    for rx, digit in _NUMBER_WORDS:
        text = rx.sub(digit, text)
    return text


LABELS = [
    ("особового складу", "personnel"),
    ("танків", "tanks"),
    ("бойових броньованих", "armoured fighting vehicles"),
    ("артилерійських", "artillery systems"),
    ("рсзв", "multiple rocket launchers"),
    ("засоби ппо", "air defence systems"),
    ("засобів ппо", "air defence systems"),
    ("літаків", "aircraft"),
    ("гелікоптерів", "helicopters"),
    ("бпла", "UAVs (operational-tactical)"),
    ("крилаті ракети", "cruise missiles"),
    ("крилатих ракет", "cruise missiles"),
    ("кораблі", "ships / boats"),
    ("кораблів", "ships / boats"),
    ("підводні", "submarines"),
    ("підводних", "submarines"),
    ("автомобільної", "vehicles and fuel tankers"),
    ("автомобільна", "vehicles and fuel tankers"),
    ("спеціальна", "special equipment"),
    ("спеціальної", "special equipment"),
]

OP_PATTERNS = {
    "clashes": r"(\d[\d\s ]*)\s+бойов\w+\s+зіткнен",
    "missiles_used": r"застосував\w*\s+(\d[\d\s ]*)\s+ракет",
    "guided_bombs": r"(\d[\d\s ]*)\s+(?:керован\w+\s+авіа\w*\s*бомб\w*|КАБ\w*)",
    "air_strikes": r"(\d[\d\s ]*)\s+авіаційн\w+\s+удар",
    "missile_strikes": r"(\d[\d\s ]*)\s+ракетн\w+\s+удар",
    "kamikaze_drones": r"(\d[\d\s ]*)\s+дрон\w*-камікадзе",
    "shellings": r"(\d[\d\s ]*)\s+обстріл",
    "mlrs_shellings": r"(\d[\d\s ]*)\s*[‒–—\-]\s*(?:із|з)\s+реактивн",
    "concentration_areas_struck": r"(\d[\d\s ]*)\s+район\w*\s+зосередження",
}
STRIKES = re.compile(r"(\d[\d\s ]*)\s+ракетн\w+(?:\s+удар\w*)?\s+та\s+(\d[\d\s ]*)\s+авіаційн\w+\s+удар")


def _label(uk: str) -> str:
    low = uk.lower()
    for stem, en in LABELS:
        if low.startswith(stem):
            return en
    return uk.strip()


def _parse_dmy(s: str) -> str | None:
    d, m, y = s.split(".")
    year = int(y) + 2000 if len(y) == 2 else int(y)
    try:
        return date(year, int(m), int(d)).isoformat()
    except ValueError:
        return None


def _losses(post: Post, source: dict) -> list[Event]:
    rows = []
    for label, total, delta in LOSS_LINE.findall(post.text):
        rows.append({"label": _label(label), "count": to_int(total), "delta": to_int(delta)})
    if len(rows) < 5:
        return []
    day = kyiv_date(post.dt)
    action = "cumulative Russian losses, as claimed"
    m = PERIOD.search(post.text)
    if m:
        day = _parse_dmy(m.group(2)) or day
        action = f"cumulative Russian losses {m.group(1)} to {m.group(2)}, as claimed"
    return [
        Event(
            date=day,
            category="losses_claimed",
            actor="Ukraine (General Staff)",
            target="Russia",
            action=action,
            breakdown=rows,
            quote=first_sentence(post.text),
            lang="uk",
            extraction="structured",
            source_url=post.url,
            **source_fields(source),
        )
    ]


def _operational(post: Post, source: dict) -> list[Event]:
    text = words_to_digits(post.text)
    counts: dict = {}
    for key, pat in OP_PATTERNS.items():
        m = re.search(pat, text)
        if m:
            counts[key] = to_int(m.group(1))
    m = STRIKES.search(text)
    if m:
        counts["missile_strikes"] = to_int(m.group(1))
        counts["air_strikes"] = to_int(m.group(2))
    if "clashes" not in counts:
        return []
    m = re.search(r"[Сс]таном\s+на\s+(\d{1,2}[:.]\d{2})", text)
    return [
        Event(
            date=kyiv_date(post.dt),
            time=m.group(1).replace(".", ":") if m else None,
            category="front_activity",
            actor="Russia",
            target="Ukraine",
            action="past 24 hours, as reported",
            counts=counts,
            quote=first_sentence(text),
            lang="uk",
            extraction="structured",
            source_url=post.url,
            **source_fields(source),
        )
    ]


def extract(post: Post, source: dict) -> list[Event]:
    low = post.text.lower()
    if "втрати" in low and "особового складу" in low:
        return _losses(post, source)
    if "бойових зіткнень" in low or "бойових зіткнення" in low:
        return _operational(post, source)
    return []

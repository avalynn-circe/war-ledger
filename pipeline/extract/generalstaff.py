"""General Staff of the Armed Forces of Ukraine (t.me/GeneralStaffZSU).

Two post types are read: the cumulative "enemy losses" table and the
operational report with the number of combat clashes and enemy strikes.
"""
from __future__ import annotations

import re
from datetime import date

from ..sources.telegram import Post
from .common import Event, first_sentence, kyiv_date, source_fields, to_int
from .lexicon import find_places

LOSS_LINE = re.compile(
    r"^\s*(.+?)\s*[‒–—\-]\s*(?:близько\s+)?(\d[\d\s\u00a0]*?)\s*\(\s*\+?\s*(\d[\d\s\u00a0]*?)\s*\)",
    re.M,
)
PERIOD = re.compile(r"з\s+(\d{2}\.\d{2}\.\d{2,4})\s+по\s+(\d{2}\.\d{2}\.\d{2,4})")

# The operational report writes small numbers as words: "одного ракетного та
# 48 авіаційних ударів, застосувавши дві ракети".
NUMBER_WORDS = {
    1: r"один|одн(?:ого|у|ієї|ій|а|е)|одиницю", 2: r"дв(?:а|і|ох)", 3: r"тр(?:и|ьох)", 4: r"чотир(?:и|ьох)",
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
    "clashes": r"(\d[\d\s\u00a0]*)\s+бойов\w+\s+зіткнен",
    "missiles_used": r"застосував\w*\s+(\d[\d\s\u00a0]*)\s+ракет",
    "guided_bombs": r"(\d[\d\s\u00a0]*)\s+(?:керован\w+\s+авіа\w*\s*бомб\w*|КАБ\w*)",
    "air_strikes": r"(\d[\d\s\u00a0]*)\s+авіаційн\w+\s+удар",
    "missile_strikes": r"(\d[\d\s\u00a0]*)\s+ракетн\w+\s+удар",
    "kamikaze_drones": r"(\d[\d\s\u00a0]*)\s+дрон\w*-камікадзе",
    "shellings": r"(\d[\d\s\u00a0]*)\s+обстріл",
    "mlrs_shellings": r"(\d[\d\s\u00a0]*)\s*[‒–—\-]\s*(?:із|з)\s+(?:застосуванням\s+)?(?:РСЗВ|реактивн)",
    "concentration_areas_struck": r"(\d[\d\s\u00a0]*)\s+район\w*\s+(?:зосередження|скупчення)",
}
STRIKES = re.compile(r"(\d[\d\s\u00a0]*)\s+ракетн\w+(?:\s+удар\w*)?\s+та\s+(\d[\d\s\u00a0]*)\s+авіаційн\w+\s+удар")


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


DAILY_LOSS_HEAD = re.compile(r"втрати\s+російських\s+загарбників\s+склали\s+(\d[\d\s\u00a0]*)\s+осіб")
NEUTRALISED = re.compile(r"[Тт]акож\s+знешкоджено\s+(.+?)(?:\.|$)", re.S)
LOSS_CLASSES = [
    ("танк", "tanks"), ("броньован", "armoured fighting vehicles"), ("артилерійськ", "artillery systems"),
    ("реактивн", "multiple rocket launchers"), ("ппо", "air defence systems"), ("протиповітрян", "air defence systems"),
    ("робототехнічн", "ground robotic systems"), ("безпілотн", "UAVs"), ("автомобільн", "vehicles and fuel tankers"),
    ("спеціальн", "special equipment"), ("літак", "aircraft"), ("гелікоптер", "helicopters"),
    ("крилат", "cruise missiles"), ("корабл", "ships / boats"), ("катер", "ships / boats"),
]
SHELLED = [
    re.compile(r"[Оо]бстрілів[^.]*?зазнали\s+населені\s+пункти\s+(.+?)\.", re.S),
    re.compile(r"(?:[Пп]ід\s+обстрілами\s+опинилися|[Оо]бстрілів\s+зазнали)\s+(.+?)\.", re.S),
]
AIR_STRUCK = re.compile(r"[Аа]віа(?:ційн\w+\s+)?удар\w*\s+зазна\w+\s+(?:райони\s+)?населен\w+\s+пункт\w*\s+(.+?)\.", re.S)
OBLAST_SUFFIX = re.compile(r"\s+([А-ЯІЇЄ][\w'’-]+(?:ої|ьої))\s+област[іи]\s*$")


def _place_groups(listing: str, context: str = "") -> tuple[list[str], int]:
    """Turn "A, B та C Сумської області; D, E Чернігівської області" into
    ["Sumy oblast: A, B, C", "Chernihiv oblast: D, E"] and the name count."""
    groups: list[str] = []
    total = 0
    for segment in re.split(r";\s*", listing.strip()):
        oblast = None
        m = OBLAST_SUFFIX.search(segment)
        if m:
            found = find_places(m.group(1))
            oblast = found[0][0] if found else m.group(1)
            segment = segment[: m.start()]
        elif context:
            found = find_places(context)
            oblast = found[0][0] if found else None
        names = [n.strip() for n in re.split(r",\s*|\s+та\s+|\s+і\s+", segment) if n.strip()]
        if not names:
            continue
        total += len(names)
        label = f"{oblast} oblast" if oblast and not oblast.endswith("oblast") else oblast
        groups.append((f"{label}: " if label else "") + ", ".join(names))
    return groups, total


def _daily_losses(post: Post, source: dict) -> list[Event]:
    text = words_to_digits(post.text)
    m = DAILY_LOSS_HEAD.search(text)
    if not m:
        return []
    rows = [{"label": "personnel", "delta": to_int(m.group(1))}]
    n = NEUTRALISED.search(text)
    if n:
        for num, chunk in re.findall(r"(\d+)\s+([^\d]+)", n.group(1)):
            low = chunk.lower()
            label = next((en for stem, en in LOSS_CLASSES if stem in low), None)
            if label:
                rows.append({"label": label, "delta": int(num)})
    return [
        Event(
            date=kyiv_date(post.dt),
            category="losses_claimed",
            actor="Ukraine (General Staff)",
            target="Russia",
            action="Russian losses in the past 24 hours, as claimed",
            breakdown=rows,
            quote=first_sentence(m.group(0)),
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
    time = m.group(1).replace(".", ":") if m else None
    low = text.lower()
    if "від початку" in low and "доби" in low and "минулої доби" not in low:
        action = f"since 00:00, as of {time}" if time else "since 00:00, as reported"
    else:
        action = f"past 24 hours to {time}, as reported" if time else "past 24 hours, as reported"

    locations: list[str] = []
    shelled = 0
    for rx in SHELLED:
        for sm in rx.finditer(post.text):
            context = post.text[max(0, sm.start() - 60) : sm.start()]
            groups, n = _place_groups(sm.group(1), context)
            locations.extend(g for g in groups if g not in locations)
            shelled += n
    if shelled:
        counts["settlements_shelled"] = shelled
    detail = None
    am = AIR_STRUCK.search(post.text)
    if am:
        groups, _ = _place_groups(am.group(1))
        detail = "Air strikes on: " + "; ".join(groups)

    return [
        Event(
            date=kyiv_date(post.dt),
            time=time,
            category="front_activity",
            actor="Russia",
            target="Ukraine",
            action=action,
            detail=detail,
            locations=locations,
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
    events: list[Event] = []
    if "втрати" in low and "особового складу" in low:
        events += _losses(post, source)
    if "зіткнен" in low:
        events += _operational(post, source)
    events += _daily_losses(post, source)
    return events

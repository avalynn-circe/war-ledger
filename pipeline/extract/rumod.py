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
REGION_LIST = re.compile(r"над\s+(?:территори\w+|акватори\w+)\s+(.+?)(?:\.|$)", re.S)
WINDOW = re.compile(r"с\s+(\d{1,2}[:.]\d{2})\s+(?:мск\s+)?до\s+(\d{1,2}[:.]\d{2})")
CAPTURED = re.compile(
    r"освобо\w+\s+населенн\w+\s+пункт\w*\s+([А-ЯЁ][^\s,.;]+(?:\s(?![А-ЯЁ][^\s,.;]+\s+област)[А-ЯЁ][^\s,.;]+)?)"
)
STRIKE = re.compile(r"групповой\s+удар|массированный\s+удар|нанес\w*\s+удар", re.I)

# The midday summary lists, per group of forces, "Потери противника составили
# до 230 военнослужащих, танк, две боевые бронированные машины ...".
RU_NUMBER_WORDS = {
    1: r"один|одна|одно|одного|одну", 2: r"два|две|двух", 3: r"тр(?:и|ех|ёх)", 4: r"четыре|четырех|четырёх",
    5: r"пять|пяти", 6: r"шесть|шести", 7: r"семь|семи", 8: r"восемь|восьми", 9: r"девять|девяти", 10: r"десять|десяти",
    11: r"одиннадцат(?:ь|и)", 12: r"двенадцат(?:ь|и)", 15: r"пятнадцат(?:ь|и)", 20: r"двадцат(?:ь|и)",
}
_RU_WORDS = [(re.compile(rf"\b(?:{pat})\b", re.I), str(n)) for n, pat in sorted(RU_NUMBER_WORDS.items(), reverse=True)]
UA_LOSS_SENTENCE = re.compile(r"[Пп]отери\s+(?:противника|ВСУ)\s+составили\s+(.+?)(?:\.|$)", re.S)
UA_PERSONNEL = re.compile(r"до\s+(\d[\d\s]*)\s+военнослужащ")
RU_LOSS_CLASSES = [
    (r"танк", "tanks"), (r"бронирован", "armoured fighting vehicles"), (r"орудий|орудия|орудие|гаубиц|артиллер", "artillery systems"),
    (r"рсзо|реактивн", "multiple rocket launchers"), (r"рэб", "electronic warfare stations"), (r"склад", "depots"),
    (r"автомоб", "vehicles"), (r"бпла|беспилотн", "UAVs"), (r"пво|зенитн", "air defence systems"),
]
# A bare singular noun in the list means one: ", танк," or ", боевая бронированная машина,"
BARE_ONE = re.compile(r"(?:^|,|\bи)\s*(танк|боевая\s+бронированная\s+машина|автомобиль|орудие[^,]*|станция\s+РЭБ|склад[^,]*)(?=,|\s+и\b|$)")


def _ru_words_to_digits(text: str) -> str:
    for rx, digit in _RU_WORDS:
        text = rx.sub(digit, text)
    return text


def _ua_losses(post: Post, source: dict) -> list[Event]:
    sentences = UA_LOSS_SENTENCE.findall(post.text)
    if not sentences:
        return []
    totals: dict[str, int] = {}
    for raw in sentences:
        sent = _ru_words_to_digits(raw)
        pm = UA_PERSONNEL.search(sent)
        if pm:
            totals["personnel"] = totals.get("personnel", 0) + int(re.sub(r"\s", "", pm.group(1)))
            sent = sent[pm.end():]
        for num, chunk in re.findall(r"(\d+)\s+([^\d,]+?)(?=,|\s+и\s|$)", sent):
            low = chunk.lower()
            label = next((en for pat, en in RU_LOSS_CLASSES if re.search(pat, low)), None)
            if label:
                totals[label] = totals.get(label, 0) + int(num)
        for bare in BARE_ONE.findall(sent):
            low = bare.lower()
            label = next((en for pat, en in RU_LOSS_CLASSES if re.search(pat, low)), None)
            if label:
                totals[label] = totals.get(label, 0) + 1
    if "personnel" not in totals:
        return []
    return [
        Event(
            date=kyiv_date(post.dt),
            category="losses_claimed",
            actor="Russia (MoD)",
            target="Ukraine",
            action="Ukrainian losses in the past 24 hours, as claimed",
            breakdown=[{"label": k, "delta": v} for k, v in totals.items()],
            quote=first_sentence(post.text),
            lang="ru",
            extraction="structured",
            source_url=post.url,
            **source_fields(source),
        )
    ]


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
        locations = [r for r, _ in regions]
        if not regions:
            lm = REGION_LIST.search(text)
            if lm:
                for part in re.split(r",\s*|\s+и\s+|\s+а\s+также\s+", lm.group(1)):
                    name = translit_region(part)
                    if name and name not in locations:
                        locations.append(name)
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
                locations=locations,
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

    events += _ua_losses(post, source)

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

"""Keyword classifier for news feed items.

Each item is scored against a rule list per category. Title hits count double.
Items that match no category are dropped. This is a heuristic: entries it
produces are marked extraction="rules" and keep the headline verbatim.
"""
from __future__ import annotations

import re

from ..sources.rss import Item
from .common import KYIV, Event, first_sentence, kyiv_date, source_fields
from .lexicon import find_places, find_weapons

RULES: dict[str, list[str]] = {
    "air_attack": [
        r"russian? (?:missile|drone|air|aerial|combined|overnight|mass(?:ive)?)s? (?:attack|strike|assault)",
        r"shahed|iskander|kinzhal|kalibr|oreshnik|glide bomb|\bkab\b",
        r"shot down|downs?\b|intercept",
        r"overnight attack|air[- ]raid",
        r"russia (?:launche[sd]|fire[sd]|attack(?:s|ed)|strikes|struck|hits?|pounds?)",
        r"ballistic missile|cruise missile",
        r"air force (?:says|reports)",
    ],
    "strikes_in_russia": [
        r"refinery|oil depot|oil terminal|ammunition depot|arsenal",
        r"ukrainian drones? (?:hit|strike|struck|attack|target)",
        r"ukraine (?:strikes|hits|struck|attacked|targets)",
        r"drones? (?:over|hit|struck|attack\w*|target\w*) .*(?:bryansk|belgorod|kursk|moscow|crimea|rostov|voronezh|ryazan|saratov|samara|tatarstan|novorossiysk|tuapse)",
        r"russian (?:defen[cs]e|air) ministry (?:says|claims|reports)",
        r"russia (?:says|claims) .*(?:drones|uavs)",
        r"explosions? (?:reported )?in (?:occupied|crimea|russia)",
        r"airfield|air ?base",
        r"\bhur\b|\bsbu\b|special operations forces|unmanned systems forces",
    ],
    "front_line": [
        r"\bcaptur(?:e|ed|es)\b|\bseiz(?:e|ed|es)\b",
        r"liberat|retake|retook|regain",
        r"\badvanc(?:e|ed|es|ing)\b|gains? ground|pushe[sd] (?:back|forward)",
        r"deepstate|\bisw\b|front ?line|line of contact",
        r"pokrovsk|kupiansk|kostiantynivka|huliaipole|siversk|\blyman\b|vovchansk|toretsk|myrnohrad|dobropillia|chasiv yar|zaporizhzhia direction|donetsk direction",
        r"\bvillage\b|settlement",
    ],
    "air_defense": [
        r"patriot|iris-?t|nasams|samp/?t|gepard|skynex|hawk",
        r"air defen[cs]e (?:system|battery|unit|batteries)",
        r"interceptor",
        r"anti-aircraft|surface-to-air",
    ],
    "field_adaptation": [
        r"\bnet(?:s|ting)\b|anti-drone net|\bmesh\b",
        r"cope cage|turtle tank|\bcage\b|screen armou?r",
        r"camouflag|decoy",
        r"fibre?-?optic|fiber-?optic",
        r"electronic warfare|\bew\b|jamm",
        r"fortif|dragon'?s teeth|trench|dugout|bunker",
        r"tunnel|pipeline (?:infiltrat|crawl)",
        r"motorcycle|motorbike|\bbuggy|buggies|\bgolf cart|\bscooter",
        r"logistics corridor|supply route|supply line",
        r"protective (?:screen|structure|cover)|shelter",
    ],
    "weapons_deliveries": [
        r"deliver(?:s|ed|y|ies|ing)?\b",
        r"aid package|military aid|security assistance|\bpackage\b",
        r"receive[sd]?\b|hand(?:ed|s) over|transfer(?:s|red)?\b",
        r"\bcontract\b|\bprocure|\bpurchase",
        r"\bproduc(?:e|es|ed|tion|ing)\b|\bmanufactur",
        r"\bbatch\b|first (?:units|systems)",
        r"f-?16|mirage|gripen|atacms|taurus|storm shadow|himars|abrams|leopard|bradley|caesar|archer|\bpzh\b",
        r"ramstein|\bpurl\b|\bnato\b .*(?:weapons|systems)",
        r"ammunition|artillery (?:shells|rounds)|155 ?mm",
    ],
    "naval": [
        r"black sea|sea of azov",
        r"\bnaval\b|\bnavy\b|\bfleet\b",
        r"warship|frigate|corvette|submarine|landing ship|patrol boat|missile carrier|tanker",
        r"magura|sea baby|sea drone|naval drone|unmanned surface",
        r"novorossiysk|sevastopol|tuapse|\bport\b",
    ],
    "infrastructure": [
        r"power (?:plant|grid|station|outage|supply|line)",
        r"substation|transformer",
        r"blackout|without (?:power|electricity|heat|water)",
        r"energy (?:infrastructure|facilit|system|sector)",
        r"ukrenergo|\bdtek\b|naftogaz",
        r"gas (?:production|facilit|storage|compressor|infrastructure)",
        r"heating|water supply",
        r"railway|rail (?:station|hub|junction|line)|\btrain\b",
        r"\bbridge\b|\bdam\b",
        r"thermal power|hydroelectric|nuclear (?:plant|power)",
    ],
    "losses_claimed": [
        r"\blosses\b|\bloses\b|\blost\b",
        r"oryx",
        r"destroyed .*(?:tanks?|artillery|armou?red|vehicles)",
        r"general staff",
        r"casualt|killed|wounded",
    ],
}
_RULES = {cat: [re.compile(p, re.I) for p in pats] for cat, pats in RULES.items()}

# A secondary gate for categories whose verbs are common in civilian news.
GATES = {
    "weapons_deliveries": re.compile(
        r"weapon|missile|drone|ammunition|shells?|aircraft|jet|fighter|tank|vehicle|air defen|system|package|aid|rounds|artillery|howitzer",
        re.I,
    ),
    "losses_claimed": re.compile(r"troops|soldiers|personnel|tanks?|artillery|vehicles|equipment|aircraft|general staff|oryx", re.I),
    "infrastructure": re.compile(r"attack|strike|struck|hit|drone|missile|shell|damage|destroy|outage|blackout|without", re.I),
}

# Tie-break order when categories score equal.
PRIORITY = [
    "field_adaptation", "weapons_deliveries", "air_defense", "naval", "infrastructure",
    "front_line", "strikes_in_russia", "air_attack", "losses_claimed",
]
DIRECTION = {
    "air_attack": ("Russia", "Ukraine"),
    "strikes_in_russia": ("Ukraine", "Russia"),
    "front_activity": ("Russia", "Ukraine"),
}


def classify(title: str, summary: str) -> str | None:
    scores: dict[str, int] = {}
    title_hit: set[str] = set()
    for cat, rules in _RULES.items():
        score = 0
        for rx in rules:
            if rx.search(title):
                score += 2
                title_hit.add(cat)
            elif rx.search(summary):
                score += 1
        gate = GATES.get(cat)
        if score and gate and not gate.search(title + " " + summary):
            score = 0
        if score:
            scores[cat] = score
    if not scores:
        return None

    # A delivery verb in the headline makes the item about the delivery, not
    # about the air defence system being delivered.
    if "weapons_deliveries" in title_hit and "air_defense" in scores:
        scores["weapons_deliveries"] = max(scores["weapons_deliveries"], scores["air_defense"] + 1)

    # Direction cue between the two strike categories.
    if "air_attack" in scores and "strikes_in_russia" in scores:
        sides = [side for _, side in find_places(title + " " + summary)]
        if sides:
            if sides[0] == "ru":
                scores["air_attack"] = 0
            elif sides[0] == "ua":
                scores["strikes_in_russia"] = 0
        scores = {k: v for k, v in scores.items() if v}

    best = max(scores.values())
    for cat in PRIORITY:
        if scores.get(cat) == best:
            return cat
    return None


def extract(item: Item, source: dict) -> list[Event]:
    category = classify(item.title, item.summary)
    if not category:
        return []
    text = f"{item.title} {item.summary}"
    actor, target = DIRECTION.get(category, (None, None))
    return [
        Event(
            date=kyiv_date(item.dt),
            time=item.dt.astimezone(KYIV).strftime("%H:%M"),
            category=category,
            actor=actor,
            target=target,
            quote=item.title,
            detail=first_sentence(item.summary) if item.summary else None,
            weapons=[{"name": n} for n in find_weapons(text)],
            locations=[name for name, _ in find_places(text)],
            lang=source.get("lang", "en"),
            extraction="rules",
            source_url=item.url,
            **source_fields(source),
        )
    ]

"""Weapon and place lexicons shared by the extractors (English, Ukrainian, Russian)."""
from __future__ import annotations

import re

# (canonical name, pattern). Patterns are matched case-insensitively.
WEAPONS: list[tuple[str, str]] = [
    ("Shahed/Geran-2 strike UAV", r"shahed|шахед|геран|gerbera|гербер"),
    ("Iskander-M ballistic missile", r"iskander-?m|іскандер-?м|искандер-?м|\biskander\b"),
    ("Iskander-K cruise missile", r"iskander-?k|іскандер-?к|искандер-?к"),
    ("KN-23 ballistic missile", r"kn-?2[34]"),
    ("Kh-47M2 Kinzhal aeroballistic missile", r"kinzhal|кинжал|кинджал|kh-?47"),
    ("Kalibr cruise missile", r"kalibr|калібр|калибр"),
    ("Kh-101/Kh-555 cruise missile", r"kh-?101|kh-?555|х-?101|х-?555"),
    ("Kh-59/Kh-69 guided missile", r"kh-?59|kh-?69|х-?59|х-?69"),
    ("Kh-22/Kh-32 cruise missile", r"kh-?22|kh-?32|х-?22|х-?32"),
    ("Kh-31/Kh-35 missile", r"kh-?31|kh-?35|х-?31|х-?35"),
    ("3M22 Zircon missile", r"zircon|tsirkon|циркон"),
    ("Oreshnik ballistic missile", r"oreshnik|орєшнік|орешник"),
    ("P-800 Onyx anti-ship missile", r"\bonyx\b|oniks|онікс|оникс"),
    ("S-300/S-400 missile", r"\bs-?300\b|\bs-?400\b|с-?300|с-?400"),
    ("Guided aerial bomb (KAB/FAB)", r"\bkab\b|\bfab-?\d*\b|glide bomb|guided (?:aerial |air )?bomb|\bкаб\b|авіабомб|авиабомб|умпк|\bumpk\b"),
    ("FPV drone", r"\bfpv\b|фпв"),
    ("Fibre-optic drone", r"fibre?-?optic|fiber-?optic|оптоволок"),
    ("Lancet loitering munition", r"lancet|ланцет"),
    ("Molniya UAV", r"molniya|молния|молнія"),
    ("Reconnaissance UAV (Orlan/Zala/Supercam)", r"\borlan\b|орлан|\bzala\b|зала|supercam|суперкам"),
    ("Patriot", r"patriot|петріот|патріот|пэтриот"),
    ("IRIS-T", r"iris-?t"),
    ("NASAMS", r"nasams"),
    ("SAMP/T", r"samp/?t|\baster\b"),
    ("Gepard", r"gepard"),
    ("Interceptor drone", r"interceptor drone|drone interceptor|interceptor uav|дрон\w*-перехоплювач|перехоплювач|\bsting\b"),
    ("F-16", r"\bf-?16s?\b"),
    ("Mirage 2000", r"mirage"),
    ("Gripen", r"gripen"),
    ("ATACMS", r"atacms"),
    ("Storm Shadow/SCALP", r"storm shadow|\bscalp\b"),
    ("Taurus", r"\btaurus\b"),
    ("HIMARS/GMLRS", r"himars|gmlrs"),
    ("Neptune cruise missile", r"neptune|нептун"),
    ("Flamingo FP-5 cruise missile", r"flamingo|\bfp-?5\b|фламінго"),
    ("Palianytsia/Peklo/Ruta drone-missile", r"palianytsia|паляниц|\bpeklo\b|пекло|\bruta\b|\bрута\b"),
    ("Long-range strike UAV (Liutyi/Bober/A-22)", r"liutyi|лютий|\bbober\b|бобер|\ba-?22\b|aeroprakt|an-?196"),
    ("Naval drone (Magura/Sea Baby)", r"magura|магура|sea baby|naval drone|sea drone|морськ\w+ дрон|unmanned surface"),
    ("Abrams", r"\babrams\b"),
    ("Leopard", r"\bleopard\b"),
    ("Bradley", r"\bbradley\b"),
    ("T-62/72/80/90 tank", r"\bt-?(?:62|72|80|90)\w*\b"),
    ("Anti-drone netting", r"\bnet(?:s|ting)?\b|\bmesh\b|сітк|сетк"),
    ("Cope cage / turtle armour", r"cope cage|turtle tank|cage armou?r|anti-drone (?:cage|screen|armou?r)|козир|клітк"),
    ("Electronic warfare", r"\bew\b|electronic warfare|jammer|jamming|\bреб\b|глушил"),
    ("Mines", r"\bmines?\b|minefield|мінуван|minelay"),
]
_WEAPON_RES = [(name, re.compile(pat, re.I)) for name, pat in WEAPONS]

# (canonical name, pattern, side) where side is "ua" or "ru".
PLACES: list[tuple[str, str, str]] = [
    ("Kyiv", r"\bkyiv|київ|киев", "ua"),
    ("Kharkiv", r"kharkiv|харків|харьков", "ua"),
    ("Odesa", r"\bodesa|\bodessa|одес", "ua"),
    ("Dnipro", r"\bdnipro\b|дніпро\b|днепр\b", "ua"),
    ("Dnipropetrovsk oblast", r"dnipropetrovsk|дніпропетровськ", "ua"),
    ("Zaporizhzhia", r"zaporizhzhia|zaporizhia|zaporizhzhya|запоріж|запорож", "ua"),
    ("Donetsk oblast", r"donetsk|донецьк|донецк", "ua"),
    ("Luhansk oblast", r"luhansk|луганськ|луганск", "ua"),
    ("Kherson", r"kherson|херсон", "ua"),
    ("Mykolaiv", r"mykolaiv|миколаїв|николаев", "ua"),
    ("Sumy", r"\bsumy\b|\bсум(?:и|ська|щин)", "ua"),
    ("Chernihiv", r"chernihiv|черніг", "ua"),
    ("Poltava", r"poltava|полтав", "ua"),
    ("Cherkasy", r"cherkasy|черкас", "ua"),
    ("Kirovohrad oblast", r"kirovohrad|kropyvnytskyi|кіровоград|кропивниц", "ua"),
    ("Vinnytsia", r"vinnytsia|вінниц", "ua"),
    ("Zhytomyr", r"zhytomyr|житомир", "ua"),
    ("Rivne", r"\brivne\b|рівн", "ua"),
    ("Volyn", r"\bvolyn\b|\blutsk\b|волин|луцьк", "ua"),
    ("Lviv", r"\blviv\b|львів|львов", "ua"),
    ("Ternopil", r"ternopil|терноп", "ua"),
    ("Khmelnytskyi", r"khmelnytsk|хмельниц", "ua"),
    ("Chernivtsi", r"chernivtsi|чернівц", "ua"),
    ("Ivano-Frankivsk", r"ivano-frankivsk|івано-франк", "ua"),
    ("Zakarpattia", r"zakarpattia|uzhhorod|закарпат|ужгород", "ua"),
    ("Crimea", r"crimea|\bкрим|крым|sevastopol|севастопол", "ru"),
    ("Pokrovsk", r"pokrovsk|покровськ", "ua"),
    ("Kupiansk", r"kupiansk|куп'янськ", "ua"),
    ("Kramatorsk", r"kramatorsk|краматорськ", "ua"),
    ("Sloviansk", r"sloviansk|слов'янськ", "ua"),
    ("Kostiantynivka", r"kostiantynivka|костянтинівк", "ua"),
    ("Huliaipole", r"huliaipole|гуляйпол", "ua"),
    ("Siversk", r"siversk|сіверськ", "ua"),
    ("Lyman", r"\blyman\b|\bлиман", "ua"),
    ("Vovchansk", r"vovchansk|вовчанськ", "ua"),
    ("Toretsk", r"toretsk|торецьк", "ua"),
    ("Myrnohrad", r"myrnohrad|мирноград", "ua"),
    ("Dobropillia", r"dobropillia|добропілл", "ua"),
    ("Chasiv Yar", r"chasiv yar|часів яр", "ua"),
    ("Kryvyi Rih", r"kryvyi rih|кривий ріг", "ua"),
    ("Nikopol", r"nikopol|нікопол", "ua"),
    ("Pavlohrad", r"pavlohrad|павлоград", "ua"),
    ("Bakhmut", r"bakhmut|бахмут", "ua"),
    ("Izium", r"\bizium\b|ізюм", "ua"),
    ("Bryansk oblast", r"bryansk|брянськ|брянск", "ru"),
    ("Belgorod oblast", r"belgorod|бєлгород|белгород", "ru"),
    ("Kursk oblast", r"\bkursk|курськ|курск", "ru"),
    ("Voronezh oblast", r"voronezh|воронеж", "ru"),
    ("Rostov oblast", r"\brostov|ростов", "ru"),
    ("Krasnodar krai", r"krasnodar|краснодар", "ru"),
    ("Moscow", r"moscow|москв|москов", "ru"),
    ("Tula oblast", r"\btula\b|\bтул(?:а|ьск)", "ru"),
    ("Kaluga oblast", r"kaluga|калуг|калуж", "ru"),
    ("Oryol oblast", r"\boryol\b|\borel\b|\bорел\b|орлов", "ru"),
    ("Smolensk oblast", r"smolensk|смолен", "ru"),
    ("Lipetsk oblast", r"lipetsk|липец", "ru"),
    ("Tambov oblast", r"tambov|тамбов", "ru"),
    ("Ryazan oblast", r"ryazan|рязан", "ru"),
    ("Volgograd oblast", r"volgograd|волгоград", "ru"),
    ("Saratov oblast", r"saratov|\bengels\b|саратов|енгельс|энгельс", "ru"),
    ("Samara oblast", r"\bsamara\b|syzran|novokuibyshevsk|самар|сызран", "ru"),
    ("Nizhny Novgorod oblast", r"nizhny novgorod|нижегород|кстово", "ru"),
    ("Leningrad oblast", r"leningrad|ust-luga|\bprimorsk\b|ленинград|усть-луг", "ru"),
    ("St Petersburg", r"petersburg|петербург", "ru"),
    ("Tver oblast", r"\btver\b|\bтвер", "ru"),
    ("Yaroslavl oblast", r"yaroslavl|ярослав", "ru"),
    ("Perm krai", r"\bperm\b|\bперм", "ru"),
    ("Bashkortostan", r"bashkortostan|\bufa\b|башкорт|\bуфа\b", "ru"),
    ("Tatarstan", r"tatarstan|yelabuga|\bkazan\b|татарстан|елабуг|казан", "ru"),
    ("Stavropol krai", r"stavropol|ставропол", "ru"),
    ("Astrakhan oblast", r"astrakhan|астрахан", "ru"),
    ("Dagestan", r"dagestan|дагестан", "ru"),
    ("Novorossiysk", r"novorossiysk|новоросс", "ru"),
    ("Tuapse", r"tuapse|туапсе", "ru"),
    ("Taganrog", r"taganrog|таганрог", "ru"),
    ("Yeysk", r"\byeysk\b|\byeisk\b|єйськ|\bейск", "ru"),
    ("Black Sea", r"black sea|чорн\w* мор|черн\w* мор", "sea"),
    ("Sea of Azov", r"sea of azov|azov sea|азовськ|азовск", "sea"),
    ("Caspian Sea", r"caspian|каспій|каспий", "sea"),
]
_PLACE_RES = [(name, re.compile(pat, re.I), side) for name, pat, side in PLACES]


def find_weapons(text: str) -> list[str]:
    found: list[str] = []
    for name, rx in _WEAPON_RES:
        if rx.search(text) and name not in found:
            found.append(name)
    return found


def find_places(text: str) -> list[tuple[str, str]]:
    """Return [(name, side)] in order of first appearance."""
    hits: list[tuple[int, str, str]] = []
    for name, rx, side in _PLACE_RES:
        m = rx.search(text)
        if m:
            hits.append((m.start(), name, side))
    hits.sort()
    out: list[tuple[str, str]] = []
    for _, name, side in hits:
        if name not in [n for n, _ in out]:
            out.append((name, side))
    return out


# Launch directions as the Air Force of Ukraine spells them.
PLACE_UK_EN = {
    "курськ": "Kursk",
    "міллерово": "Millerovo",
    "орел": "Oryol",
    "шаталово": "Shatalovo",
    "приморсько-ахтарськ": "Primorsko-Akhtarsk",
    "брянськ": "Bryansk",
    "гвардійське": "Hvardiiske (Crimea)",
    "чауда": "Cape Chauda (Crimea)",
    "балаклава": "Balaklava (Crimea)",
    "донецьк": "Donetsk (occupied)",
    "єйськ": "Yeysk",
    "таганрог": "Taganrog",
    "ростов": "Rostov",
    "тамбов": "Tambov",
    "воронеж": "Voronezh",
    "саратов": "Saratov",
    "енгельс": "Engels",
    "халіно": "Khalino",
    "навля": "Navlya",
    "каспійське море": "Caspian Sea",
    "чорне море": "Black Sea",
    "азовське море": "Sea of Azov",
    "брянська область": "Bryansk oblast",
    "курська область": "Kursk oblast",
}

_PLACE_SUFFIX = re.compile(
    r"\s*[–—-]\s*(рф|росія|тот\s+крим\w*|тимчасово\s+окупован\w+\s+крим\w*|крим)\s*$", re.I
)


def translit_place(raw: str) -> str | None:
    s = _PLACE_SUFFIX.sub("", raw.strip(" .;")).strip()
    s = re.sub(r"^(м\.|с\.|смт)\s*", "", s, flags=re.I)
    if not s:
        return None
    return PLACE_UK_EN.get(s.lower(), s)


# Russian region names as the Russian MoD spells them, by stem.
RU_REGION: list[tuple[str, str]] = [
    ("брянск", "Bryansk oblast"), ("белгород", "Belgorod oblast"), ("курск", "Kursk oblast"),
    ("воронеж", "Voronezh oblast"), ("ростов", "Rostov oblast"), ("краснодар", "Krasnodar krai"),
    ("москов", "Moscow oblast"), ("москв", "Moscow"), ("тул", "Tula oblast"),
    ("калуж", "Kaluga oblast"), ("орлов", "Oryol oblast"), ("смолен", "Smolensk oblast"),
    ("липец", "Lipetsk oblast"), ("тамбов", "Tambov oblast"), ("рязан", "Ryazan oblast"),
    ("волгоград", "Volgograd oblast"), ("саратов", "Saratov oblast"), ("самар", "Samara oblast"),
    ("нижегород", "Nizhny Novgorod oblast"), ("ленинград", "Leningrad oblast"),
    ("новгород", "Novgorod oblast"), ("твер", "Tver oblast"), ("ярослав", "Yaroslavl oblast"),
    ("пенз", "Penza oblast"), ("ульянов", "Ulyanovsk oblast"), ("татарстан", "Tatarstan"),
    ("башкорт", "Bashkortostan"), ("ставрополь", "Stavropol krai"), ("астрахан", "Astrakhan oblast"),
    ("крым", "Crimea"), ("азовск", "Sea of Azov"), ("черного моря", "Black Sea"),
    ("чёрного моря", "Black Sea"), ("каспийск", "Caspian Sea"), ("псков", "Pskov oblast"),
    ("владимир", "Vladimir oblast"), ("иванов", "Ivanovo oblast"), ("костром", "Kostroma oblast"),
    ("мурман", "Murmansk oblast"), ("карел", "Karelia"), ("удмурт", "Udmurtia"),
    ("мордов", "Mordovia"), ("чуваш", "Chuvashia"), ("марий", "Mari El"), ("перм", "Perm krai"),
    ("оренбург", "Orenburg oblast"), ("свердлов", "Sverdlovsk oblast"), ("тюмен", "Tyumen oblast"),
    ("калинингр", "Kaliningrad oblast"), ("калмык", "Kalmykia"), ("дагестан", "Dagestan"),
    ("адыге", "Adygea"), ("запорож", "Zaporizhzhia oblast (occupied)"),
    ("херсон", "Kherson oblast (occupied)"), ("донецк", "Donetsk oblast (occupied)"),
    ("луганск", "Luhansk oblast (occupied)"),
]


def translit_region(raw: str) -> str:
    low = raw.lower()
    for stem, name in RU_REGION:
        if stem in low:
            return name
    return raw.strip()


_WEAPON_NAME_MAP = [
    ("Іскандер", "Iskander"), ("Искандер", "Iskander"), ("Калібр", "Kalibr"), ("Калибр", "Kalibr"),
    ("Кинджал", "Kinzhal"), ("Кинжал", "Kinzhal"), ("Онікс", "Onyx"), ("Циркон", "Zircon"),
    ("Орєшнік", "Oreshnik"), ("Герань", "Geran"), ("Гербера", "Gerbera"), ("шахеди", "Shahed"),
    ("Шахед", "Shahed"), ("Х-", "Kh-"), ("-М", "-M"), ("-К", "-K"), ("С-", "S-"),
]


def translit_weapon_name(raw: str) -> str:
    s = raw.strip()
    for src, dst in _WEAPON_NAME_MAP:
        s = s.replace(src, dst)
    return s

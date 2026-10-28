"""A schematic map: coarse country outlines and pins at approximate places.

Outlines come from Natural Earth at 1:110m (public domain), far too coarse
to show towns or roads, which is the point. Pins sit at approximate oblast
or city positions from the table below.
"""
from __future__ import annotations

import json
import math
import pathlib
from html import escape

LAND = json.loads((pathlib.Path(__file__).parent / "templates" / "map-land.json").read_text(encoding="utf-8"))

# Approximate (lat, lon) for the canonical place names the extractors produce.
COORDS: dict[str, tuple[float, float]] = {
    # Ukraine
    "Kyiv": (50.45, 30.52), "Kharkiv": (49.99, 36.23), "Odesa": (46.48, 30.73), "Dnipro": (48.46, 35.04),
    "Dnipropetrovsk oblast": (48.5, 35.0), "Zaporizhzhia": (47.84, 35.14), "Donetsk oblast": (48.0, 37.8),
    "Luhansk oblast": (48.8, 39.0), "Kherson": (46.64, 32.61), "Mykolaiv": (46.97, 32.0), "Sumy": (50.9, 34.8),
    "Chernihiv": (51.5, 31.3), "Poltava": (49.59, 34.55), "Cherkasy": (49.44, 32.06), "Kirovohrad oblast": (48.5, 32.26),
    "Vinnytsia": (49.23, 28.47), "Zhytomyr": (50.25, 28.66), "Rivne": (50.62, 26.25), "Volyn": (50.75, 25.33),
    "Lviv": (49.84, 24.03), "Ternopil": (49.55, 25.6), "Khmelnytskyi": (49.42, 27.0), "Chernivtsi": (48.29, 25.93),
    "Ivano-Frankivsk": (48.92, 24.71), "Zakarpattia": (48.62, 22.3), "Crimea": (45.3, 34.4),
    "Pokrovsk": (48.28, 37.18), "Kupiansk": (49.71, 37.6), "Kramatorsk": (48.72, 37.55), "Sloviansk": (48.85, 37.6),
    "Kostiantynivka": (48.53, 37.71), "Huliaipole": (47.66, 36.26), "Siversk": (48.87, 38.1), "Lyman": (48.99, 37.8),
    "Vovchansk": (50.29, 36.94), "Toretsk": (48.39, 37.85), "Myrnohrad": (48.29, 37.27), "Dobropillia": (48.47, 37.08),
    "Chasiv Yar": (48.59, 37.84), "Kryvyi Rih": (47.91, 33.39), "Nikopol": (47.57, 34.4), "Pavlohrad": (48.52, 35.87),
    "Bakhmut": (48.59, 38.0), "Izium": (49.21, 37.25), "Sumy oblast": (50.9, 34.8), "Chernihiv oblast": (51.5, 31.3),
    "Kharkiv oblast": (49.9, 36.5), "Kyiv oblast": (50.3, 30.5), "Odesa oblast": (46.8, 30.3), "Zaporizhzhia oblast": (47.6, 35.3),
    "Kherson oblast": (46.6, 33.0), "Mykolaiv oblast": (47.2, 32.0), "Poltava oblast": (49.6, 34.3), "Donetsk (occupied)": (48.0, 37.8),
    "Zaporizhzhia oblast (occupied)": (47.2, 35.6), "Kherson oblast (occupied)": (46.4, 33.5), "Donetsk oblast (occupied)": (47.8, 37.9),
    "Luhansk oblast (occupied)": (48.6, 39.2),
    # Russia and seas
    "Bryansk oblast": (53.0, 33.5), "Bryansk": (53.25, 34.37), "Belgorod oblast": (50.7, 36.9), "Kursk oblast": (51.7, 36.2),
    "Kursk": (51.73, 36.19), "Voronezh oblast": (51.2, 39.7), "Voronezh": (51.66, 39.2), "Rostov oblast": (47.6, 40.5),
    "Rostov": (47.23, 39.7), "Krasnodar krai": (45.1, 39.3), "Moscow": (55.75, 37.62), "Moscow oblast": (55.6, 37.5),
    "Tula oblast": (54.0, 37.5), "Kaluga oblast": (54.4, 35.5), "Oryol oblast": (52.8, 36.3), "Oryol": (52.97, 36.07),
    "Smolensk oblast": (54.8, 32.9), "Lipetsk oblast": (52.6, 39.4), "Tambov oblast": (52.7, 41.4), "Tambov": (52.72, 41.45),
    "Ryazan oblast": (54.4, 40.3), "Volgograd oblast": (49.5, 44.5), "Saratov oblast": (51.6, 46.5), "Saratov": (51.53, 46.0),
    "Engels": (51.5, 46.1), "Samara oblast": (53.3, 50.4), "Nizhny Novgorod oblast": (56.1, 44.2), "Leningrad oblast": (59.9, 31.0),
    "St Petersburg": (59.93, 30.3), "Tver oblast": (57.0, 34.5), "Yaroslavl oblast": (57.8, 39.5), "Novgorod oblast": (58.3, 32.5),
    "Penza oblast": (53.2, 44.5), "Ulyanovsk oblast": (54.1, 48.0), "Tatarstan": (55.5, 51.0), "Bashkortostan": (54.2, 56.0),
    "Stavropol krai": (45.0, 43.5), "Astrakhan oblast": (46.9, 47.9), "Dagestan": (42.9, 47.0), "Kalmykia": (46.3, 45.3),
    "Adygea": (44.6, 40.1), "Pskov oblast": (57.3, 29.0), "Vladimir oblast": (56.2, 40.5), "Ivanovo oblast": (57.0, 41.5),
    "Kostroma oblast": (58.0, 42.5), "Mordovia": (54.3, 44.5), "Chuvashia": (55.5, 47.0), "Mari El": (56.6, 47.9),
    "Udmurtia": (57.0, 53.0), "Kaliningrad oblast": (54.7, 21.0), "Novorossiysk": (44.72, 37.77), "Tuapse": (44.1, 39.08),
    "Taganrog": (47.21, 38.93), "Yeysk": (46.71, 38.27), "Millerovo": (48.92, 40.4), "Shatalovo": (54.4, 32.5),
    "Primorsko-Akhtarsk": (46.05, 38.17), "Hvardiiske (Crimea)": (45.12, 34.02), "Cape Chauda (Crimea)": (45.0, 35.83),
    "Balaklava (Crimea)": (44.5, 33.6), "Khalino": (51.75, 36.3), "Navlya": (52.83, 34.5),
    "Black Sea": (43.5, 33.5), "Sea of Azov": (46.1, 36.6), "Caspian Sea": (43.0, 49.0),
}

LON0, LON1, LAT0, LAT1 = 22.0, 48.0, 43.5, 57.5
W = 640
K = math.cos(math.radians(50.0))
H = round(W * (LAT1 - LAT0) / ((LON1 - LON0) * K))


def project(lat: float, lon: float) -> tuple[float, float] | None:
    if not (LON0 <= lon <= LON1 and LAT0 <= lat <= LAT1):
        return None
    x = (lon - LON0) / (LON1 - LON0) * W
    y = (LAT1 - lat) / (LAT1 - LAT0) * H
    return round(x, 1), round(y, 1)


def _land_paths() -> str:
    out = []
    for f in LAND["features"]:
        for poly in f["geometry"]["coordinates"]:
            pts = []
            for lon, lat in poly[0]:
                x = (lon - LON0) / (LON1 - LON0) * W
                y = (LAT1 - lat) / (LAT1 - LAT0) * H
                pts.append(f"{x:.1f},{y:.1f}")
            cls = "ua" if f["properties"]["name"] == "Ukraine" else "land"
            out.append(f'<path class="{cls}" d="M{" L".join(pts)} Z"/>')
    return "".join(out)


def _collect(events: list[dict]) -> dict:
    """Pins by kind: {kind: {name: [notes]}}."""
    pins: dict[str, dict[str, list[str]]] = {"launch": {}, "target": {}, "shelled": {}, "claimed": {}, "other": {}}
    for e in events:
        src, cat, kind_struct = e["source_id"], e["category"], e["extraction"] == "structured"
        if src == "kpszsu" and kind_struct:
            for name in e["locations"]:
                pins["launch"].setdefault(name, []).append("launch direction (Air Force of Ukraine)")
            detail = e.get("detail") or ""
            if detail.startswith("Main direction"):
                for name in detail.split(": ", 1)[1].split(", "):
                    pins["target"].setdefault(name.strip(), []).append("main direction of the overnight attack (Air Force of Ukraine)")
        elif src == "generalstaff" and cat == "front_activity" and kind_struct:
            for g in e["locations"]:
                oblast, _, names = g.partition(": ")
                n = len([x for x in names.split(",") if x.strip()]) if names else 1
                pins["shelled"].setdefault(oblast if names else g, []).append(f"{n} settlements shelled (General Staff)")
        elif src == "mod_russia" and cat == "strikes_in_russia" and kind_struct:
            for name in e["locations"]:
                pins["claimed"].setdefault(name, []).append("UAVs intercepted, as claimed (Russian MoD)")
        else:
            for name in e["locations"][:1]:
                label = e.get("quote_en") or e["quote"]
                pins["other"].setdefault(name, []).append(f"{label[:90]} ({e['source_name']})")
    return pins


def render_map(events: list[dict]) -> str | None:
    pins = _collect(events)
    if not any(pins[k] for k in pins):
        return None
    parts = [f'<svg class="map" viewBox="0 0 {W} {H}" role="img" aria-label="Schematic map of the day\'s places">']
    parts.append(f'<rect class="sea" x="0" y="0" width="{W}" height="{H}"/>')
    parts.append(_land_paths())

    def pt(name: str):
        c = COORDS.get(name)
        return project(*c) if c else None

    targets = [pt(n) for n in pins["target"] if pt(n)]
    for name in pins["launch"]:
        p = pt(name)
        if p and targets:
            for t in targets:
                parts.append(f'<line class="route" x1="{p[0]}" y1="{p[1]}" x2="{t[0]}" y2="{t[1]}"/>')
    order = [("other", 3.5), ("claimed", 4.5), ("shelled", 6), ("launch", 5), ("target", 7)]
    for kind, r in order:
        for name, notes in pins[kind].items():
            p = pt(name)
            if not p:
                continue
            title = escape(name + ": " + "; ".join(dict.fromkeys(notes)))
            parts.append(f'<g class="pin {kind}"><circle cx="{p[0]}" cy="{p[1]}" r="{r}"><title>{title}</title></circle>')
            if kind in ("target", "launch", "shelled"):
                label = name.replace(" (Crimea)", "").replace(" (occupied)", "")
                if kind == "shelled":
                    label = f"{label.replace(' oblast', '')} · {sum(int(n.split()[0]) for n in notes)}"
                parts.append(f'<text x="{p[0] + r + 3}" y="{p[1] + 4}">{escape(label)}</text>')
            parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)

"""Collect, extract, store and render.

    python -m pipeline.run                      live fetch, data/ and site/ in the current directory
    python -m pipeline.run --offline fixtures   read recorded pages instead of the network
"""
from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta

import yaml

from . import render, store
from .extract import airforce, deepstate, generalstaff, news, rumod
from .extract.common import Event, kyiv_date
from .fetch import Fetcher
from .fold import fold
from .sources import rss, telegram

log = logging.getLogger("inventory")

EXTRACTORS = {
    "airforce": airforce.extract,
    "generalstaff": generalstaff.extract,
    "rumod": rumod.extract,
    "deepstate": deepstate.extract,
    "news": news.extract,
}


def load_sources(path: pathlib.Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [s for s in data["sources"] if s.get("enabled", True)]


def archive_raw(raw_dir: pathlib.Path, source: dict, units: list) -> None:
    """Keep the source text of every post or item, one JSON line each, per Kyiv
    date. A post seen again with changed text replaces its earlier record, so
    an edited tally is kept in its latest form. Extractors are re-run over
    this archive on every run, so a parser fix applies to past days too."""
    out = raw_dir / source["id"]
    out.mkdir(parents=True, exist_ok=True)
    by_day: dict[str, list[dict]] = defaultdict(list)
    for u in units:
        rec = {"id": u.id, "url": u.url, "dt": u.dt.isoformat()}
        if hasattr(u, "text"):
            rec["text"] = u.text
        else:
            rec["title"], rec["summary"] = u.title, u.summary
        by_day[kyiv_date(u.dt)].append(rec)
    for day, recs in by_day.items():
        path = out / f"{day}.jsonl"
        kept: dict[str, dict] = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    kept[rec["id"]] = rec
        for rec in recs:
            kept[rec["id"]] = rec
        path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in kept.values()), encoding="utf-8")


def load_raw(raw_dir: pathlib.Path, sources: list[dict], since: str) -> list[tuple[dict, object]]:
    """Return (source, unit) pairs for every archived record dated on or after `since`."""
    by_id = {s["id"]: s for s in sources}
    out: list[tuple[dict, object]] = []
    if not raw_dir.exists():
        return out
    for sdir in sorted(raw_dir.iterdir()):
        source = by_id.get(sdir.name)
        if source is None:
            continue
        for path in sorted(sdir.glob("????-??-??.jsonl")):
            if path.stem < since:
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                rec = json.loads(line)
                dt = datetime.fromisoformat(rec["dt"])
                if "text" in rec:
                    unit: object = telegram.Post(rec["id"], rec["url"], dt, rec["text"])
                else:
                    unit = rss.Item(rec["id"], rec["url"], dt, rec["title"], rec["summary"])
                out.append((source, unit))
    return out


def parse_units(source: dict, body: str, fetcher: Fetcher, status: dict[str, str]) -> list:
    if source["kind"] == "telegram":
        return telegram.parse(body)
    units = rss.parse(body)
    if not units:
        # The URL may be an HTML page that advertises its feed in <link rel="alternate">.
        alt = rss.discover(body, source["url"])
        if alt and alt != source["url"]:
            log.info("%s: no entries at %s, trying advertised feed %s", source["id"], source["url"], alt)
            alt_body = fetcher.get({**source, "url": alt})
            if alt_body:
                units = rss.parse(alt_body)
                status[source["id"] + " (feed)"] = alt
    return units


def collect(sources: list[dict], fetcher: Fetcher, raw_dir: pathlib.Path | None = None) -> tuple[list[Event], dict[str, str]]:
    events: list[Event] = []
    status: dict[str, str] = {}
    for s in sources:
        body = fetcher.get(s)
        if body is None:
            status[s["id"]] = "fetch failed"
            continue
        try:
            units = parse_units(s, body, fetcher, status)
            if raw_dir is not None:
                archive_raw(raw_dir, s, units)
            extract = EXTRACTORS[s["extractor"]]
            found = [e for u in units for e in extract(u, s)]
        except Exception as exc:  # one bad source must not stop the run
            log.exception("%s: parse failed", s["id"])
            status[s["id"]] = f"parse failed: {exc}"
            continue
        status[s["id"]] = f"{len(units)} items, {len(found)} entries"
        events.extend(found)
    return events, status


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sources", default="sources.yaml")
    ap.add_argument("--offline", metavar="DIR", help="read <DIR>/<source id>.(html|xml) instead of fetching")
    ap.add_argument("--data", default="data", help="directory of per-day JSON files")
    ap.add_argument("--site", default="site", help="output directory for the rendered site")
    ap.add_argument("--max-age-days", type=int, default=10, help="ignore entries dated earlier than this many days ago")
    ap.add_argument("--no-render", action="store_true")
    ap.add_argument("--no-raw", action="store_true", help="do not archive source text under <data>/raw/")
    ap.add_argument("--rebuild-only", action="store_true", help="skip fetching; re-extract <data>/raw/ and render")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    sources = load_sources(pathlib.Path(args.sources))
    data_dir = pathlib.Path(args.data)
    events: list[Event] = []
    if args.rebuild_only:
        args.no_raw = False
    else:
        events, status = collect(sources, Fetcher(args.offline), None if args.no_raw else data_dir / "raw")
        for sid, line in status.items():
            log.info("%-16s %s", sid, line)
        if all(v.startswith(("fetch failed", "parse failed")) for k, v in status.items() if not k.endswith("(feed)")):
            log.error("every source failed")
            return 1

    cutoff = (date.today() - timedelta(days=args.max_age_days)).isoformat()
    by_day: dict[str, list[Event]] = defaultdict(list)
    if args.no_raw:
        for e in fold(events):
            if e.date >= cutoff:
                by_day[e.date].append(e)
        for day, evs in sorted(by_day.items()):
            merged = store.merge_day(data_dir, day, evs)
            log.info("%s: %d new, %d stored", day, len(evs), len(merged))
    else:
        # Re-extract every archived post since the cutoff, so parser fixes
        # reach past days and dropped rules no longer leave stale entries.
        pairs = load_raw(data_dir / "raw", sources, cutoff)
        raw_days = {kyiv_date(u.dt) for _, u in pairs}
        extracted = [e for src, u in pairs for e in EXTRACTORS[src["extractor"]](u, src)]
        for e in fold(extracted):
            if e.date >= cutoff:
                by_day[e.date].append(e)
        for day in sorted(raw_days | set(by_day)):
            if day < cutoff:
                continue
            rows = store.write_day(data_dir, day, by_day.get(day, []))
            log.info("%s: %d entries", day, len(rows))

    days = store.load_all(data_dir)
    store.write_index(data_dir, days)
    if not args.no_render:
        render.render(pathlib.Path(args.site), days, sources)
        log.info("site rendered: %d day(s)", len(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())

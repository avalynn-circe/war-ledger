"""Collect, extract, store and render.

    python -m pipeline.run                      live fetch, data/ and site/ in the current directory
    python -m pipeline.run --offline fixtures   read recorded pages instead of the network
"""
from __future__ import annotations

import argparse
import logging
import pathlib
import sys
from collections import defaultdict
from datetime import date, timedelta

import yaml

from . import render, store
from .extract import airforce, deepstate, generalstaff, news, rumod
from .extract.common import Event
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


def collect(sources: list[dict], fetcher: Fetcher) -> tuple[list[Event], dict[str, str]]:
    events: list[Event] = []
    status: dict[str, str] = {}
    for s in sources:
        body = fetcher.get(s)
        if body is None:
            status[s["id"]] = "fetch failed"
            continue
        try:
            units = telegram.parse(body) if s["kind"] == "telegram" else rss.parse(body)
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
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    sources = load_sources(pathlib.Path(args.sources))
    events, status = collect(sources, Fetcher(args.offline))
    for sid, line in status.items():
        log.info("%-16s %s", sid, line)
    if all(v.startswith(("fetch failed", "parse failed")) for v in status.values()):
        log.error("every source failed")
        return 1

    cutoff = (date.today() - timedelta(days=args.max_age_days)).isoformat()
    events = [e for e in fold(events) if e.date >= cutoff]

    data_dir = pathlib.Path(args.data)
    by_day: dict[str, list[Event]] = defaultdict(list)
    for e in events:
        by_day[e.date].append(e)
    for day, evs in sorted(by_day.items()):
        merged = store.merge_day(data_dir, day, evs)
        log.info("%s: %d new, %d stored", day, len(evs), len(merged))

    days = store.load_all(data_dir)
    store.write_index(data_dir, days)
    if not args.no_render:
        render.render(pathlib.Path(args.site), days, sources)
        log.info("site rendered: %d day(s)", len(days))
    return 0


if __name__ == "__main__":
    sys.exit(main())

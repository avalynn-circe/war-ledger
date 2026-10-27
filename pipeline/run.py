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
from datetime import date, timedelta

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
    date, so extractors can be improved and re-run without refetching."""
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
        seen: set[str] = set()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    seen.add(json.loads(line)["id"])
        with path.open("a", encoding="utf-8") as fh:
            for rec in recs:
                if rec["id"] not in seen:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    seen.add(rec["id"])


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
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    sources = load_sources(pathlib.Path(args.sources))
    data_dir = pathlib.Path(args.data)
    events, status = collect(sources, Fetcher(args.offline), None if args.no_raw else data_dir / "raw")
    for sid, line in status.items():
        log.info("%-16s %s", sid, line)
    if all(v.startswith(("fetch failed", "parse failed")) for k, v in status.items() if not k.endswith("(feed)")):
        log.error("every source failed")
        return 1

    cutoff = (date.today() - timedelta(days=args.max_age_days)).isoformat()
    events = [e for e in fold(events) if e.date >= cutoff]

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

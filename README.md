# The Ukraine War Ledger

A static website that records, day by day, what each side reported in Russia's war on Ukraine: air attacks
and what was launched and intercepted, strikes inside Russia, front line
changes, claimed losses, new air defence, field adaptations such as anti-drone
netting, weapons deliveries, naval and infrastructure events. Every entry
carries the count or the verbatim headline from its source and a link to it.
The site adds no commentary.

## How it works

```
sources.yaml  ->  fetch  ->  parse  ->  extract  ->  fold  ->  data/YYYY-MM-DD.json  ->  site/
```

1. **Fetch.** `pipeline/fetch.py` downloads each source listed in
   `sources.yaml`. A failed source is logged and skipped.
2. **Parse.** Telegram channels are read through their public web preview
   (`https://t.me/s/<channel>`), feeds through `feedparser`.
3. **Extract.** One extractor per source type turns posts into entries:
   - `airforce`: the Air Force of Ukraine overnight report. Launched, intercepted
     and impact counts per weapon type, launch directions, time of the tally.
   - `generalstaff`: the General Staff losses table (14 items with daily
     deltas) and the operational report (clashes, strikes, bombs, drones,
     shellings).
   - `rumod`: Russian MoD interception claims by region, strike claims and
     claimed captures.
   - `deepstate`: DeepState map updates (occupied, advanced near, liberated).
   - `news`: a keyword classifier for media feeds. It assigns one of ten
     categories, picks out weapon and place names, and keeps the headline.
     Items that match no category are dropped.
4. **Fold.** `pipeline/fold.py` merges duplicates. A headline whose numbers
   match a structured entry of the same day and category (for example a news
   story that repeats the Air Force figures) is attached to that entry as
   "also reported by".
5. **Store.** `pipeline/store.py` writes one JSON file per Kyiv date and
   merges by entry id, so a second run in the same day updates rather than
   duplicates.
6. **Render.** `pipeline/render.py` writes `site/`: one page per day,
   `index.html` for the latest day, `archive.html`, `events.json`, `events.csv`.

Entries carry `extraction: structured` when a purpose-built parser produced the
numbers, and `extraction: rules` when the keyword classifier did.

## Run it

```bash
pip install -r requirements-dev.txt
python -m pytest -q                              # extractor tests against fixtures/
python -m pipeline.run --offline fixtures        # build data/ and site/ from the fixtures
python -m pipeline.run                           # live fetch
python -m http.server -d site 8000               # view at http://localhost:8000
```

`.github/workflows/inventory.yml` runs the live collection twice a day, commits
`data/` and `site/`, and deploys `site/` to GitHub Pages. Enable Pages with
source "GitHub Actions" in the repository settings once.

## Sources

| Source | Side | Kind | Extractor |
|---|---|---|---|
| Air Force of Ukraine | Ukrainian official | Telegram | structured |
| General Staff of the Armed Forces of Ukraine | Ukrainian official | Telegram | structured |
| Ministry of Defence of Russia | Russian official | Telegram | structured |
| DeepState | OSINT | Telegram | structured |
| Militarnyi | Media | RSS | rules |
| The Kyiv Independent | Media | RSS | rules |
| Ukrinform | Media | RSS | rules |
| Defense Express | Media | RSS | rules (disabled until the feed URL is confirmed) |

Feeds marked `verified: false` in `sources.yaml` were added from documentation
and have not yet been fetched live. The first live run reports each one as
items found or fetch failed.

To add a source, append an entry to `sources.yaml`. A Telegram channel or RSS
feed with the `news` extractor needs no code. A new structured source needs an
extractor module in `pipeline/extract/` and a line in `EXTRACTORS` in
`pipeline/run.py`.

## Data shape

```json
{
  "date": "2026-10-26",
  "time": "09:00",
  "category": "air_attack",
  "actor": "Russia",
  "target": "Ukraine",
  "action": "air attack",
  "weapons": [{"name": "Shahed/Gerbera-type strike UAV", "launched": 101, "intercepted": 90, "impacts": 11}],
  "counts": {"launched": 105, "intercepted": 90, "impacts": 15, "impact_locations": 9},
  "locations": ["Kursk", "Millerovo"],
  "quote": "У ніч на 26 жовтня ...",
  "source_name": "Air Force of Ukraine",
  "source_url": "https://t.me/kpszsu/35012",
  "extraction": "structured",
  "also_reported_by": [{"name": "Ukrinform", "url": "..."}]
}
```

## Limits

- Figures are each source's claims. The site does not reconcile Ukrainian and
  Russian numbers or check them against third parties.
- The news classifier is keyword based. Expect some misfiled headlines; the
  source link is always one click away.
- Telegram previews show about twenty recent posts, so a run that is skipped
  for several days loses older posts.
- Place names from DeepState and the Russian MoD stay in the original
  language and grammatical case.

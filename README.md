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
   - `governor`: Russian regional governors. Attacks on the region with the
     killed, injured and drones-shot-down counts they state.
   - `monitoring`: independent channels such as ASTRA. Direction comes from
     the first place named; entries carry an "unconfirmed" chip.
   - `oryx`: the Oryx loss pages. Cumulative totals per category; the returns
     sheet shows the change since the previous day.
   - `news`: a keyword classifier for media feeds. It assigns one of ten
     categories, picks out weapon and place names, and keeps the headline.
     Items that match no category are dropped.
4. **Fold.** `pipeline/fold.py` merges duplicates. A headline whose numbers
   match a structured entry of the same day and category (for example a news
   story that repeats the Air Force figures) is attached to that entry as
   "also reported by".
5. **Store.** `pipeline/store.py` writes one JSON file per Kyiv date and
   merges by entry id, so a second run in the same day updates the entry
   without duplicating it. The source text of every post and feed item is
   kept under `data/raw/<source>/<date>.jsonl`, so an extractor can be
   improved and re-run against past days without refetching.
6. **Render.** `pipeline/render.py` writes `site/`: one page per day,
   `index.html` for the latest day, `archive.html`, `events.json`, `events.csv`.

## The day page

Figures first, then places, then headlines.

1. **Fact tiles.** Eight figures as large numbers, each naming its source,
   with a 14-day line: UAVs launched and intercepted (with the intercepted
   share as a bar), impact locations, UAVs Russia claims over its territory,
   clashes, guided bombs, kamikaze drones, and claimed personnel losses from
   each side. A tile with nothing reported shows a dot.
2. **Where.** Launch directions with an arrow to the main target, settlements
   shelled as chips grouped by oblast, and the regions Russia names for its
   interceptions.
3. **Headlines by category.** One line per entry: time, text, source. Open a
   line for its detail, counts, places, original text and link.
4. **Full returns sheet.** The complete two-column sheet, the same rows every
   day, behind a disclosure at the bottom.

The **wire** (`wire.html`) is one continuous feed, newest first, ordered by
each source post's own timestamp: time, category, entry, source. The page
holds the newest day and fetches earlier days from `wire-data/` as the
reader scrolls. Two toggle rows in the header, categories and sources, apply to the
wire and the day pages alike; an entry shows only when both its category and
its source are on, and the choice is remembered in the browser.

The archive page is a table of days with the returns-sheet figures as
columns. Click a heading to sort.

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

`.github/workflows/inventory.yml` runs the live collection every two hours, commits
`data/` and `site/`, and deploys `site/` to GitHub Pages. One manual step:
in the repository settings, under Pages, set the source to "GitHub Actions".
The workflow token cannot do that itself.

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
| Governors of Belgorod, Bryansk, Kursk and Rostov oblasts | Russian official, regional | Telegram | rules with counts |
| ASTRA | Independent monitoring, shown as unconfirmed | Telegram | rules |
| Oryx, Russian and Ukrainian equipment losses | OSINT, visually confirmed | HTML | structured |

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

## Translation

With an `ANTHROPIC_API_KEY` secret set on the repository, the pipeline
translates Cyrillic excerpts (quotes, details and settlement names) into
English once and keeps them in `data/translations.json`. Pages show the
English with the original a click away. Without the key the originals are
shown, and any cached translations still apply.

## Limits

- Figures are each source's claims. The site does not reconcile Ukrainian and
  Russian numbers or check them against third parties.
- The news classifier is keyword based. Expect some misfiled headlines; the
  source link is always one click away.
- Telegram previews show about twenty recent posts, so a run that is skipped
  for several days loses older posts.
- Place names from DeepState and the Russian MoD stay in the original
  language and grammatical case.

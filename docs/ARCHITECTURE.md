# Architecture

## Current state (as of Phase 0)
```
scout.py                  CLI (rich UI, menu, orchestration; ~1170 lines, monolithic)
app/scrapers/
  fetch.py                tiered fetch: http -> stealth -> browser (Scrapling), legacy httpx
  ai.py                   optional LLM extraction (ScrapeGraphAI), uses fetch() for pages
  stealth.py, utils.py    proxy / UA helpers
  instagram|tiktok|pinterest|youtube|linktree   platform scrapers (partly on fetch())
  github|linkedin|twitch  platform scrapers (still direct httpx)
  enrichment.py           email discovery, SMTP verification, confidence scoring
```

## Target design
```
CLI / (later) API
      |
  Pipeline  discover -> scrape -> enrich -> score -> export
      |
  Scraper (per platform or generic)
      |  Tier 1 selectors -> Tier 2 Scrapling adaptive -> Tier 3 LLM  (+ selector cache)
      |
  fetch()   http -> stealth -> browser
```

Principles:
- Everything fetches through `fetch()`; no scraper talks to the network directly.
- LLM use is optional and last-resort, to control cost and keep the tool usable offline.
- One lead schema shared by all scrapers and the exporter.
- `scout.py` shrinks to UI only; logic moves into `app/`.

## Open design questions
- Where the selector cache lives (SQLite vs JSON) -> D-003
- How discovery finds candidates without official search APIs -> Phase 3

## Phase 1 design: self-healing extraction (`app/healing/`)

Each platform keeps its existing parser (tier 1). When it returns nothing or an invalid lead, `heal()` walks the ladder and stops at the first valid result:

| Tier | Source | Cost |
|---|---|---|
| 1 `primary` | the platform's own parser (regex / embedded JSON) | free |
| 2 `generic` | structured data on the page: JSON-LD, OpenGraph, `<meta>` | free |
| 3 `learned` | CSS selectors previously learned for this platform (SQLite) | free |
| 4 `llm` | ScrapeGraphAI extraction (`ai.py`), only if `SCOUT_LLM` is set | paid/slow |

Learning: when tier 4 succeeds, `induce` locates each returned value in the DOM and derives a CSS selector for it. Selectors are stored per `(platform, field)` and become tier 3 on the next run, so the LLM is paid for once per layout change, not once per lead.

Modules:
- `schema.py`: `Lead` fields, `normalize()`, `is_valid()`
- `cache.py`: SQLite store (selectors + per-run tier stats), default `~/.openscrapper/healing.db` (override `OPENSCRAPPER_HOME`)
- `generic.py`: tier 2 extractors (stdlib only)
- `induce.py`: value -> CSS selector
- `engine.py`: `heal()` orchestration and stats
- CLI: a "Scraper health" screen showing which tier served each platform recently

Validity rule: a lead is valid if it has a username or full name, `follower_count` is a non-negative int, and any email is well formed.

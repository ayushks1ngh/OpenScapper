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

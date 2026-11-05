# Roadmap

Status: `[ ]` todo, `[~]` in progress, `[x]` done. Each phase ships only when its exit criteria pass.

## Phase 0: Foundation (current)
Goal: clean base, honest attribution, tests to build on.
- [x] Scrapling fetch engine (`app/scrapers/fetch.py`, tiered http/stealth/browser)
- [x] ScrapeGraphAI layer (`app/scrapers/ai.py`, optional, off by default)
- [x] Credits section in README
- [x] Commit the current uncommitted work on a feature branch (`phase-0-foundation`)
- [x] Pick name and rename (banner, README, update checker, entry point -> `openscrapper.py`) (D-001)
- [x] Add pytest + tests for fetch tier escalation (`tests/test_fetch.py`, 11 tests)
- [x] Tests for enrichment (`tests/test_enrichment.py`; found and fixed a WhatsApp-link regex bug)
- [x] CI (lint + tests) in `.github/workflows/ci.yml`
- [x] HTML scrapers on `fetch()` (instagram, tiktok, pinterest, youtube, linktree). github/twitch/linkedin stay on their API clients (D-006)
**Exit:** all HTML-based platforms fetch via `fetch()`; tests green in CI; no references to the old name/update URL.

## Phase 1: Self-healing scrapers (flagship) ✅ done 2026-11-05
Goal: a scraper that survives layout changes.
- [x] Lead schema + validity rules (`app/healing/schema.py`); design in ARCHITECTURE.md
- [ ] Tier 1: platform primary parser (existing)
- [x] Tier 2: generic structured data (JSON-LD / OpenGraph) (`generic.py`)
- [x] Tier 3: learned selectors applied from cache
- [x] Tier 4: LLM fallback + `heal()` orchestration (`engine.py`)
- [x] Selector/stat cache (`app/healing/cache.py`, SQLite)
- [x] Selector induction + replay: derive CSS selectors from known values (`induce.py`)
- [x] Health report: which scrapers healed, which tier served each lead (menu 13, `report.py`)
- [x] Convert Instagram, TikTok, Pinterest, YouTube first (the flakiest)
**Exit:** break a selector on purpose; run still returns a correct lead and the cache is updated. Covered by a test using saved HTML fixtures.

## Phase 2: Any-URL leads
- [x] `python openscrapper.py lead <url>` and menu 14 return a normalized lead for any page
- [x] Platform detection (`app/lead/detect.py`); generic extractor for unknown sites (`app/lead/any_url.py`)
- [x] Shared lead schema (added `phone`, `socials`). Company/role/location still TODO (LLM tier only)
**Exit:** 10 varied non-platform URLs yield usable leads. (Needs a manual run against live sites; unit tests cover the logic with fixtures.)

## Phase 3: Natural-language prospecting
- [x] Query parser -> search plan (`app/prospect/query.py`, rule based; an LLM parser for messy phrasing is a later add-on)
- [x] Discovery step (`app/prospect/discover.py`, search-engine HTML + `site:` filters)
- [x] Pipeline: discover -> scrape -> enrich -> rank -> export (`pipeline.py`, CLI `find "<query>"`, menu 15)
**Exit:** "yoga studio owners in Austin" returns a ranked CSV end to end. (Logic is unit tested with fakes; needs a live run on a networked machine. Search engines may rate-limit; discovery is pluggable.)

## Phase 4: Lead quality ✅ done 2026-11-05
- [x] Cross-platform identity matching (`app/quality/identity.py`, noisy-or evidence with reasons)
- [x] Dedupe and merge (`merge.py`; wired into the prospecting pipeline)
- [x] Scoring model v2 (`scoring.py`: email, phone, audience, cross-platform presence, profile, business signal). Recency not included: we do not collect post dates yet
- [x] Explainable score (`score_explain` column in CSV)
**Exit:** measured precision on a hand-labelled sample set. Met on a 30-pair set: precision 1.00, recall 0.86 (`tests/test_quality_identity_eval.py`). Caveat: pairs were written by us, so this guards regressions but is not real-world accuracy; grow the set from real runs.

## Phase 5: Production hardening
- [x] Config system (`app/config.py`: OPENSCRAPPER_* with SCOUT_* fallback, `.env` loader/writer) (D-005 done)
- [x] Rate limiting + retries (`app/ratelimit.py`: per-host throttle, jittered backoff on 429/5xx). Proxy rotation unchanged (random pick per request)
- [x] Logging: rotating file at `~/.openscrapper/logs/`, JSON lines option (`OPENSCRAPPER_LOG_JSON`), secrets redacted (`app/logsetup.py`)
- [x] Packaging: `pyproject.toml`, `openscrapper` console script, extras `browser`/`ai`/`dev`; verified in a clean venv. Versioned releases: pending your decision on the version number (see PROGRESS)
- [x] Usage guide (`docs/USAGE.md`); no separate docs site planned
**Exit:** fresh machine install to first CSV in under 5 minutes; tagged v1.0.

## Later (unscheduled)
Web dashboard, CRM export (HubSpot etc.), team features, scheduled runs.

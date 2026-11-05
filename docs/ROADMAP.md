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

## Phase 1: Self-healing scrapers (flagship)
Goal: a scraper that survives layout changes.
- [ ] Define a `Scraper` interface: `selectors`, `schema`, `parse(page)`
- [ ] Tier 1: CSS selectors (fast path)
- [ ] Tier 2: Scrapling adaptive relocation when selectors miss
- [ ] Tier 3: LLM extraction fallback (`ai.py`)
- [ ] Selector cache: persist LLM-found fixes, reuse next run
- [ ] Health report: which scrapers healed, which tier served each lead
- [ ] Convert Instagram, TikTok, Pinterest, YouTube first (the flakiest)
**Exit:** break a selector on purpose; run still returns a correct lead and the cache is updated. Covered by a test using saved HTML fixtures.

## Phase 2: Any-URL leads
- [ ] `scout lead <url>` returns a normalized lead for any page
- [ ] Platform detection; generic extractor for unknown sites
- [ ] Shared lead schema (name, company, role, emails, phones, socials, location, source)
**Exit:** 10 varied non-platform URLs yield usable leads.

## Phase 3: Natural-language prospecting
- [ ] Query parser (LLM) -> search plan (platforms, keywords, filters)
- [ ] Discovery step (search/list pages -> candidate profile URLs)
- [ ] Pipeline: discover -> scrape -> enrich -> score -> export
**Exit:** "yoga studio owners in Austin" returns a ranked CSV end to end.

## Phase 4: Lead quality
- [ ] Cross-platform identity matching (same person on multiple sites)
- [ ] Dedupe and merge
- [ ] Scoring model v2 (email verification, source agreement, completeness, recency)
- [ ] Explainable score (why this lead got 82%)
**Exit:** measured precision on a hand-labelled sample set.

## Phase 5: Production hardening
- [ ] Config system (single settings file, env overrides)
- [ ] Rate limiting, retries, proxy rotation policy
- [ ] Structured logging and error reporting
- [ ] Packaging (pip install, entry point), versioned releases
- [ ] Docs site / usage guide
**Exit:** fresh machine install to first CSV in under 5 minutes; tagged v1.0.

## Later (unscheduled)
Web dashboard, CRM export (HubSpot etc.), team features, scheduled runs.

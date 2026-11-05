# Progress log

Newest first. One entry per work session: what changed, what's next, blockers.

## 2026-11-05
- Logging (rotating file, redaction), packaging (`pip install .` verified in a clean venv, `openscrapper` command, `.env` resolved to the checkout or `~/.openscrapper`), CLI moved into `cli()`. 165 tests.
- **Open decision for the owner:** `app.__version__` is still `1.3.1` (inherited from Scout). The roadmap said v1.0; releasing 1.0.0 would look like a downgrade and the update checker compares against GitHub releases. Suggest 2.0.0 for the first OpenScrapper release.
- Phase 5 started: config layer (new env names, legacy fallback), per-host throttle + retry/backoff in `fetch()`. 158 tests. Remaining: structured logging, packaging (pyproject + entry point), install docs, v1.0 tag (needs your OK).
- **Phase 4 complete.** Identity matching, merge, explainable scoring, wired into `find`. Eval on 30 hand-written pairs: precision 1.00, recall 0.86 (two misses are accepted weak-evidence cases). 146 tests.
- **Next:** Phase 5 (config, rate limiting, logging, packaging, release).
- Phase 3 built: `app/prospect/` (query, discover, pipeline), CLI `find "<query>" [--limit N]` and menu 15. 116 tests. **No live run yet** (sandbox has no network/browser), so the Phase 3 exit criterion stays open.
- Fixed a thread race in pipeline stats (counters now locked).
- Phase 2 built: `app/lead/` (detect, any_url), CLI `lead <url>` + menu 14, `phone` in schema. 92 tests. **Not yet verified against live sites** (no network checks run), so the Phase 2 exit criterion stays open.
- **Phase 1 complete.** Scraper Health screen (menu 13). Exit criteria covered by `test_scraper_healing.py` (broken layout still yields a lead) and `test_healing_engine.py` (LLM once, then learned selectors, cache updated). 64 tests.
- **Next:** Phase 2, any-URL leads (`lead <url>`, platform detection, generic extractor).
- Wired `heal()` into youtube/tiktok/pinterest/instagram; primary results keep platform fields. 60 tests pass. Remaining in Phase 1: health report in the CLI, broken-selector exit test across platforms.
- Phase 1 core built and pushed: `app/healing/` (schema, cache, generic, induce, engine). 56 tests pass. Remaining in Phase 1: wire `heal()` into youtube/tiktok/pinterest/instagram, health screen in CLI.
- Added `tests/test_enrichment.py` (20 tests; 31 total pass). Found and fixed a bug: WhatsApp `wa.me/` numbers were never extracted.
- Decided API scrapers (github/twitch/linkedin) stay off `fetch()` (D-006). **Phase 0 complete** pending the GitHub repo rename.
- **Next:** Phase 1, starting with the `Scraper` interface design. Pausing for user review of the design before building (large change).
- Added `tests/test_fetch.py` (11 passing) and GitHub Actions CI (pytest on 3.10/3.12, ruff syntax-error lint).
- Name decided: OpenScrapper (D-001). Renamed entry point, banner, README, update checker. LICENSE keeps original Scout notice plus ours.
- Created branch `phase-0-foundation`, committed Phase 0 work.
- **Next:** pytest + tests for `fetch()` escalation, then CI, then migrate github/linkedin/twitch onto `fetch()`.
- **Blockers:** GitHub repo still named `OpenScapper`; rename it manually.

## 2026-11-04
- Defined vision, 5-phase roadmap, architecture and decision log (these docs).
- Existing uncommitted work found: `fetch.py` (Scrapling tiers), `ai.py` (ScrapeGraphAI), scraper edits, new requirements.
- README Credits section added.
- **Next:** commit Phase 0 work on a branch, decide the name (D-001), add tests.
- **Blockers:** project name.

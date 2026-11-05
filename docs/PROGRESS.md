# Progress log

Newest first. One entry per work session: what changed, what's next, blockers.

## 2026-11-05
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

# Decision log

Format: ID, date, status, decision, why, alternatives.

## D-001: Project name (2026-11-05)
- Status: accepted
- Decision: **OpenScrapper**. Entry point is `openscrapper.py`; update checker and links point to `ayushks1ngh/OpenScapper`.
- Note: the GitHub repo is spelled `OpenScapper` (one "r" fewer). Rename the repo to `OpenScrapper` on GitHub, then update the URLs (grep `OpenScapper`).
- Follow-up D-005: `SCOUT_*` env vars kept for now to avoid breaking existing `.env` files.

## D-002: Attribution (2026-11-04)
- Status: accepted
- Decision: keep the original MIT copyright notice in `LICENSE`, credit Scout, Scrapling and ScrapeGraphAI in README and `docs/CREDITS.md`. Differentiate through real new functionality, not by hiding lineage.
- Why: MIT requires retaining the notice; honesty; real differentiation is stronger anyway.

## D-003: Selector cache storage (2026-11-05)
- Status: accepted
- Decision: SQLite at `~/.openscrapper/healing.db` (`OPENSCRAPPER_HOME` overrides). Stores learned selectors and per-run tier stats.
- Why: needs queries for the health report and safe concurrent writes from worker threads.

## D-004: LLM is optional (2026-11-04)
- Status: accepted
- Decision: all LLM features stay off unless `SCOUT_LLM` is set; core pipeline works without it.
- Why: cost, privacy, offline use.

## D-006: API-based scrapers stay off fetch() (2026-11-05)
- Status: accepted
- github (REST JSON), twitch (GraphQL POST), linkedin (cookie session) are not HTML scraping and have no anti-bot problem worth a browser tier; `fetch()` is GET-only.
- Revisit if a POST/session mode is added to `fetch()` (likely needed for Phase 1 healing of linkedin).

## D-005: Env var prefix (2026-11-05)
- Status: open
- Keep `SCOUT_*` for now. Later: accept `OPENSCRAPPER_*` first, fall back to `SCOUT_*`, deprecate in v1.0.

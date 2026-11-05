# Usage guide

## Install
```
pip install .                 # core
pip install ".[browser]"      # real-browser tiers (Cloudflare-style blocks)
pip install ".[ai]"           # LLM extraction fallback
```
Settings live in a `.env` file (see `.env.example`). A source checkout uses its own `.env`; an installed copy uses `./.env` if present, otherwise `~/.openscrapper/.env`. Override with `OPENSCRAPPER_ENV=/path/to/file`.

## Commands
| Command | What it does |
|---|---|
| `openscrapper` | Interactive menu |
| `openscrapper find "<query>" [--limit N]` | Describe the leads you want; writes a ranked `prospects_*.csv` |
| `openscrapper lead <url>` | Normalized lead (JSON) from a profile link or any page |
| `openscrapper --verbose` | Debug logging to the console and the log file |

### Writing a `find` query
Plain English works: `yoga studio owners in Austin with 5k+ followers on instagram`.
Recognised parts: platforms (`instagram`, `tiktok`, `youtube`, `linkedin`, `github`, `twitch`, `pinterest`, `linktree`, plus `ig`/`yt`), a location after `in`/`near`/`based in`, and follower ranges (`5k+`, `over 2.5k`, `under 50k`, `between 5k and 50k`, `1m+ subscribers`). Everything else is treated as what to search for. With no platform named, Instagram, TikTok and YouTube are searched.

### Reading the CSV
`quality_score` (0-100) ranks leads; `score_explain` lists every point and why. A lead found on several platforms is merged into one row (`platforms`, `total_reach`). A `?` or `followers_unknown=True` means the follower count could not be read, so the range filter was not applied to that lead.

## How scraping stays alive
Each platform scraper tries its own parser first. If the page layout changed, the lead is recovered from JSON-LD/OpenGraph data, then from selectors learned earlier, then (if `OPENSCRAPPER_LLM` is set) from an LLM, which also teaches the next run new selectors. Menu item 13 (Scraper Health) shows which tier served each platform.

## Settings
| Variable | Default | Meaning |
|---|---|---|
| `OPENSCRAPPER_PROXY` / `_PROXY_FILE` / `_FREE_PROXY` | none | Proxy options |
| `OPENSCRAPPER_ENGINE` | `auto` | `auto`, `http`, `stealth`, `browser`, `legacy` |
| `OPENSCRAPPER_HOST_DELAY` | `0.3` | Seconds between requests to one host |
| `OPENSCRAPPER_RETRIES` | `2` | Backoff retries on HTTP 429/5xx |
| `OPENSCRAPPER_LLM`, `_LLM_KEY`, `_LLM_URL` | off | LLM fallback |
| `OPENSCRAPPER_LOG_JSON` | off | JSON-lines log file |
| `OPENSCRAPPER_HOME` | `~/.openscrapper` | Cache and logs |
Old `SCOUT_*` names still work.

## Files it writes
`~/.openscrapper/healing.db` (learned selectors, tier stats), `~/.openscrapper/logs/openscrapper.log` (rotating, secrets redacted), `prospects_*.csv` and `*_export_*.csv` in the current directory.

## Limits to know about
- Discovery uses a search engine's HTML results; it can be rate-limited or blocked.
- LinkedIn needs your own `li_at` cookie; GitHub's API allows 60 requests/hour without a token.
- Scraping can break a site's terms of service. Respect them and applicable privacy law when contacting people.

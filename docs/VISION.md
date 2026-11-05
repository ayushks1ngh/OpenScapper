# Vision

> Working name: **OpenScapper** (TBD, see DECISIONS D-001). Still shown as "Scout" in the CLI until renamed.

## One line
A lead-generation tool whose scrapers repair themselves, so it keeps working when sites change.

## Who it's for
Appointment setters and outbound sales people who need verified contact data from social platforms and arbitrary websites.

## Why it's different
Existing tools each solve one slice:
- **Scout**: lead pipeline (8 platforms, SMTP-verified email, confidence score), but scrapers are brittle.
- **Scrapling**: anti-bot fetching and adaptive selectors, but no lead logic.
- **ScrapeGraphAI**: LLM extraction from any page, but slow/costly if used for everything.

Our edge is the combination of the three plus original logic:
1. **Self-healing scrapers**: fast selectors -> adaptive relocate -> LLM fallback -> cache the fix.
2. **Any-URL leads**: paste any page, get a normalized lead.
3. **Natural-language prospecting**: describe the lead you want, get a ranked list.
4. **Lead quality scoring**: our own cross-platform identity matching, dedupe and scoring.

## Non-goals (for now)
- Hosted SaaS / web dashboard (post-v1)
- Bypassing authentication or scraping private data
- Being a general-purpose scraping framework

"""
AI extraction layer (ScrapeGraphAI), optional and off by default.

Enable by setting SCOUT_LLM in .env (or Settings > AI):

    SCOUT_LLM=ollama/llama3.2            local, free (needs Ollama running)
    SCOUT_LLM=openai/gpt-4o-mini         hosted (needs SCOUT_LLM_KEY)
    SCOUT_LLM=anthropic/claude-haiku-5-5 hosted (needs SCOUT_LLM_KEY)
    SCOUT_LLM_KEY=...                    API key for hosted providers
    SCOUT_LLM_URL=http://localhost:11434 optional base URL (Ollama / proxies)

Pages are fetched with OpenScrapper's own anti-block engine (fetch.py), then handed
to ScrapeGraphAI as a local HTML file, so extraction works on pages a plain
ScrapeGraphAI fetch would be blocked on.
"""

import logging
import os
import tempfile
from typing import Dict, Optional

from app.scrapers.fetch import fetch

logger = logging.getLogger(__name__)

CONTACT_PROMPT = (
    "Extract contact details for the person or business this page is about. "
    "Return JSON with keys: name, company, role, email, phone, location, "
    "social_links (list of URLs). Use null for anything not on the page. "
    "Never invent values."
)


def llm_name() -> str:
    return os.environ.get('SCOUT_LLM', '').strip()


def ai_enabled() -> bool:
    return bool(llm_name())


def _config() -> Dict:
    model = llm_name()
    llm = {'model': model, 'temperature': 0}
    key = os.environ.get('SCOUT_LLM_KEY', '').strip()
    url = os.environ.get('SCOUT_LLM_URL', '').strip()
    if key:
        llm['api_key'] = key
    if url:
        llm['base_url'] = url
    if model.startswith('ollama/'):
        llm.setdefault('base_url', 'http://localhost:11434')
        llm['format'] = 'json'
        llm['model_tokens'] = 8192
    return {'llm': llm, 'verbose': False, 'headless': True}


def ai_extract(url: str, prompt: str = CONTACT_PROMPT) -> Optional[Dict]:
    """Fetch `url` and extract what `prompt` asks for. None if AI is off or it fails."""
    if not ai_enabled():
        return None
    try:
        from scrapegraphai.graphs import SmartScraperGraph
    except ImportError:
        logger.debug("scrapegraphai not installed")
        return None

    res = fetch(url)
    if not res or not res.ok:
        return None

    tmp = tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8')
    try:
        tmp.write(res.text)
        tmp.close()
        graph = SmartScraperGraph(prompt=prompt, source=tmp.name, config=_config())
        out = graph.run()
        return out if isinstance(out, dict) else None
    except Exception as e:
        logger.debug(f"AI extraction failed for {url}: {str(e).splitlines()[0][:150]}")
        return None
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass


def ai_enrich_website(url: str) -> Dict:
    """Contact details from a lead's website via the LLM. Empty dict if unavailable."""
    data = ai_extract(url) or {}
    content = data.get('content') if isinstance(data.get('content'), dict) else data
    clean = {}
    for k in ('name', 'company', 'role', 'email', 'phone', 'location'):
        v = content.get(k) if isinstance(content, dict) else None
        if isinstance(v, str) and v.strip() and v.strip().lower() not in ('null', 'none', 'n/a'):
            clean[k] = v.strip()
    return clean

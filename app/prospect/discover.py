"""Find candidate profile URLs for a SearchPlan via a search engine's HTML results page."""

import html as _html
import logging
import re
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from app.lead.detect import Detected, detect
from app.prospect.query import SearchPlan

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://html.duckduckgo.com/html/?q={q}&s={offset}'
PAGE_SIZE = 30

# site: filter per platform, narrowed to profile-shaped paths where the site allows it
SITE_FILTERS = {
    'instagram': 'site:instagram.com',
    'tiktok': 'site:tiktok.com/@',
    'youtube': 'site:youtube.com/@',
    'linkedin': 'site:linkedin.com/in',
    'github': 'site:github.com',
    'twitch': 'site:twitch.tv',
    'pinterest': 'site:pinterest.com',
    'linktree': 'site:linktr.ee',
}

_HREF = re.compile(r'<a[^>]+href="([^"]+)"', re.IGNORECASE)


def _unwrap(href: str) -> str:
    """DuckDuckGo wraps results as //duckduckgo.com/l/?uddg=<encoded-url>."""
    href = _html.unescape(href)
    if 'uddg=' in href:
        qs = parse_qs(urlparse('https:' + href if href.startswith('//') else href).query)
        if qs.get('uddg'):
            return unquote(qs['uddg'][0])
    return href


def parse_results(html: str) -> List[str]:
    urls, seen = [], set()
    for href in _HREF.findall(html or ''):
        url = _unwrap(href)
        if url.startswith('http') and 'duckduckgo.com' not in url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def build_query(plan: SearchPlan, platform: str) -> str:
    return f"{SITE_FILTERS.get(platform, '')} {plan.search_text()}".strip()


def search(query: str, pages: int = 1, fetcher: Optional[Callable] = None) -> List[str]:
    if fetcher is None:
        from app.scrapers.fetch import fetch as fetcher
    out: List[str] = []
    for i in range(pages):
        res = fetcher(SEARCH_URL.format(q=quote_plus(query), offset=i * PAGE_SIZE))
        if not res or not res.ok:
            logger.debug(f"search blocked or empty for {query!r} (page {i})")
            break
        found = parse_results(res.text)
        if not found:
            break
        out.extend(u for u in found if u not in out)
    return out


def discover(plan: SearchPlan, per_platform: int = 10, pages: int = 1,
             fetcher: Optional[Callable] = None) -> Dict[str, List[Detected]]:
    """{platform: [Detected...]}, only URLs that look like real profiles, deduped."""
    result: Dict[str, List[Detected]] = {}
    for platform in plan.platforms:
        seen, picked = set(), []
        for url in search(build_query(plan, platform), pages=pages, fetcher=fetcher):
            d = detect(url)
            if not d or d.platform != platform:
                continue
            key = (d.platform, d.identifier.lower())
            if key in seen:
                continue
            seen.add(key)
            picked.append(d)
            if len(picked) >= per_platform:
                break
        result[platform] = picked
    return result

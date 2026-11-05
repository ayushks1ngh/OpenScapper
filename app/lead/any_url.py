"""lead_from_url(): known profile URLs use the platform scraper; any other page gets generic extraction."""

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from app.healing import generic
from app.healing.engine import default_llm, heal
from app.healing.schema import is_valid, normalize
from app.lead.detect import detect

_HREF = re.compile(r'href=["\'](https?://[^"\'#\s]+)["\']', re.IGNORECASE)
_MAILTO = re.compile(r'href=["\']mailto:([^"\'?\s]+)', re.IGNORECASE)


@dataclass
class LeadResult:
    lead: Optional[Dict[str, Any]]
    source: str  # platform name, or 'web'
    tier: str    # primary | generic | learned | llm | none


def _platform_scraper(platform: str) -> Optional[Callable[[str], Optional[Dict]]]:
    from app import scrapers as s
    return {
        'instagram': s.scrape_instagram, 'tiktok': s.scrape_tiktok, 'linkedin': s.scrape_linkedin,
        'github': s.scrape_github, 'youtube': s.scrape_youtube, 'twitch': s.scrape_twitch,
        'linktree': s.scrape_linktree, 'pinterest': s.scrape_pinterest,
    }.get(platform)


def social_links(html: str) -> Dict[str, str]:
    """{platform: url} for every recognised profile link on the page (first one per platform)."""
    found: Dict[str, str] = {}
    for url in _HREF.findall(html or ''):
        d = detect(url)
        if d and d.platform not in found:
            found[d.platform] = url
    return found


def web_primary(html: str, url: str) -> Optional[Dict[str, Any]]:
    """Parser for arbitrary pages: structured data + contact details found in the markup."""
    from app.scrapers.enrichment import LeadEnricher
    lead = generic.extract(html, 'web', url)
    contact = LeadEnricher()._extract_from_text(html)
    mailto = _MAILTO.findall(html or '')
    lead['email'] = lead['email'] or (mailto[0].lower() if mailto else '') or contact['email'] or ''
    lead['phone'] = lead['phone'] or contact['phone'] or ''
    socials = social_links(html)
    lead['socials'] = socials
    for link in socials.values():
        if link not in lead['links']:
            lead['links'].append(link)
    return lead if is_valid(lead) else None


def lead_from_url(url: str, llm: Optional[Callable] = default_llm,
                  fetcher: Optional[Callable] = None) -> LeadResult:
    url = url.strip()
    if '://' not in url:
        url = 'https://' + url

    d = detect(url)
    if d:
        scraper = _platform_scraper(d.platform)
        lead = scraper(d.identifier) if scraper else None
        if lead:
            lead.setdefault('profile_url', d.url)
            return LeadResult(lead, d.platform, 'primary')
        # the platform scraper came up empty; fall through to generic extraction of the page itself

    if fetcher is None:
        from app.scrapers.fetch import fetch as fetcher
    res = fetcher(url)
    if not res or not res.ok:
        return LeadResult(None, d.platform if d else 'web', 'none')

    healed = heal('web', url, res.text, primary=lambda h: web_primary(h, url), llm=llm)
    lead = healed.lead
    if lead is not None:
        lead = {**lead, 'socials': lead.get('socials') or social_links(res.text)}
        lead.setdefault('profile_url', url)
        lead['profile_url'] = lead['profile_url'] or url
    return LeadResult(lead, d.platform if d else 'web', healed.tier)

"""heal(): walk the extraction ladder and stop at the first valid lead."""

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from app.healing import generic, induce
from app.healing.cache import Cache
from app.healing.schema import is_valid, normalize

logger = logging.getLogger(__name__)

PROFILE_PROMPT = (
    "Extract the public profile on this page. Return JSON with keys: username, full_name, "
    "bio, email, follower_count (integer), website, links (list of URLs). "
    "Use null for anything not on the page. Never invent values."
)

_cache: Optional[Cache] = None


def get_cache() -> Cache:
    global _cache
    if _cache is None:
        _cache = Cache()
    return _cache


@dataclass
class HealResult:
    lead: Optional[Dict[str, Any]]
    tier: str  # primary | generic | learned | llm | none

    @property
    def healed(self) -> bool:
        return self.tier not in ('primary', 'none')


def default_llm(url: str) -> Optional[Dict[str, Any]]:
    from app.scrapers.ai import ai_enabled, ai_extract
    if not ai_enabled():
        return None
    out = ai_extract(url, PROFILE_PROMPT)
    if isinstance(out, dict) and isinstance(out.get('content'), dict):
        out = out['content']
    return out if isinstance(out, dict) else None


def _learned(platform: str, html: str, url: str, cache: Cache) -> Optional[Dict[str, Any]]:
    sels = cache.selectors(platform)
    if not sels:
        return None
    try:
        got = induce.apply_selectors(html, sels)
    except ImportError:
        return None
    for field in sels:
        cache.record_selector_result(platform, field, field in got)
    if not got:
        return None
    got.setdefault('profile_url', url)
    return normalize(got, platform)


def _learn(platform: str, html: str, lead: Dict[str, Any], cache: Cache):
    try:
        for field, spec in induce.induce(html, lead).items():
            cache.save_selector(platform, field, spec['selector'], spec['attr'])
    except ImportError:
        logger.debug("scrapling not installed; cannot learn selectors")
    except Exception as e:
        logger.debug(f"selector induction failed for {platform}: {e}")


def heal(platform: str, url: str, html: str,
         primary: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
         llm: Optional[Callable[[str], Optional[Dict[str, Any]]]] = default_llm,
         cache: Optional[Cache] = None) -> HealResult:
    cache = cache or get_cache()
    result: Optional[HealResult] = None

    if primary:
        try:
            lead = normalize(primary(html), platform)
        except Exception as e:
            logger.debug(f"{platform} primary parser raised {e!r}")
            lead = None
        if is_valid(lead):
            result = HealResult(lead, 'primary')
        else:
            cache.record_run(platform, 'primary', False)

    if result is None:
        lead = generic.extract(html, platform, url)
        if is_valid(lead):
            result = HealResult(lead, 'generic')

    if result is None:
        lead = _learned(platform, html, url, cache)
        if is_valid(lead):
            result = HealResult(lead, 'learned')

    if result is None and llm:
        try:
            lead = normalize(llm(url), platform)
        except Exception as e:
            logger.debug(f"{platform} llm tier raised {e!r}")
            lead = None
        if is_valid(lead):
            lead['profile_url'] = lead['profile_url'] or url
            _learn(platform, html, lead, cache)
            result = HealResult(lead, 'llm')

    if result is None:
        result = HealResult(None, 'none')
    cache.record_run(platform, result.tier, result.lead is not None)
    if result.healed:
        logger.info(f"{platform}: healed via {result.tier} tier")
    return result

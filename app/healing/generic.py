"""Tier 2: structured data most profile pages carry (JSON-LD, OpenGraph, meta). Stdlib only."""

import html as _html
import json
import re
from typing import Any, Dict, Iterator, List

from app.healing.schema import normalize

_LD = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
                 re.DOTALL | re.IGNORECASE)
_META = re.compile(r'<meta\b([^>]*)>', re.IGNORECASE)
_ATTR = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_PERSON_TYPES = {'person', 'organization', 'localbusiness', 'profilepage'}


def _meta_tags(page: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for m in _META.finditer(page):
        attrs = {k.lower(): _html.unescape(a or b) for k, a, b in _ATTR.findall(m.group(1))}
        key = attrs.get('property') or attrs.get('name')
        if key and 'content' in attrs and key.lower() not in out:
            out[key.lower()] = attrs['content']
    return out


def _walk(node: Any) -> Iterator[Dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _json_ld_entities(page: str) -> List[Dict[str, Any]]:
    found = []
    for raw in _LD.findall(page):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        for node in _walk(data):
            t = node.get('@type')
            types = {x.lower() for x in (t if isinstance(t, list) else [t]) if isinstance(x, str)}
            if types & _PERSON_TYPES:
                found.append(node)
    return found


def _follower_count(entity: Dict[str, Any]) -> int:
    stats = entity.get('interactionStatistic') or []
    for s in stats if isinstance(stats, list) else [stats]:
        if isinstance(s, dict) and 'follow' in str(s.get('interactionType', '')).lower():
            return s.get('userInteractionCount') or 0
    return 0


def extract(page: str, platform: str = '', url: str = '') -> Dict[str, Any]:
    """Best-effort lead from JSON-LD then OpenGraph/meta. Returns a normalized dict (maybe invalid)."""
    if not page:
        return normalize({}, platform)
    meta = _meta_tags(page)
    ent = (_json_ld_entities(page) or [{}])[0]

    same_as = ent.get('sameAs') or []
    links = [same_as] if isinstance(same_as, str) else [x for x in same_as if isinstance(x, str)]
    site = ent.get('url') if isinstance(ent.get('url'), str) else ''

    title = ent.get('name') or meta.get('og:title') or meta.get('twitter:title') or ''
    title = re.sub(r'\s*[\|\-–]\s*(YouTube|TikTok|Instagram|Pinterest|Twitch)\b.*$', '', str(title), flags=re.I)

    return normalize({
        'full_name': title,
        'username': ent.get('alternateName') or '',
        'bio': ent.get('description') or meta.get('og:description') or meta.get('description') or '',
        'email': ent.get('email') or '',
        'follower_count': _follower_count(ent),
        'website': site if site and site != url else '',
        'links': links,
        'profile_url': meta.get('og:url') or url,
    }, platform)

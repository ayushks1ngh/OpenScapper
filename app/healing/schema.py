"""Lead schema, normalization and validity checks shared by every extraction tier."""

import re
from typing import Any, Dict, List, Optional

FIELDS = ('username', 'full_name', 'bio', 'email', 'follower_count',
          'website', 'links', 'platform', 'profile_url')

_EMAIL = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
_NULLS = {'', 'null', 'none', 'n/a', 'na', 'undefined'}


def _clean_str(v: Any) -> str:
    if v is None:
        return ''
    s = str(v).strip()
    return '' if s.lower() in _NULLS else s


def _clean_int(v: Any) -> int:
    if isinstance(v, bool):
        return 0
    if isinstance(v, (int, float)):
        return max(int(v), 0)
    digits = re.sub(r'[^\d]', '', _clean_str(v))
    return int(digits) if digits else 0


def normalize(raw: Optional[Dict[str, Any]], platform: str = '') -> Dict[str, Any]:
    """Coerce a loose dict into the lead shape. Unknown keys are dropped."""
    raw = raw or {}
    links: List[str] = []
    for item in raw.get('links') or []:
        s = _clean_str(item)
        if s and s not in links:
            links.append(s)
    lead = {
        'username': _clean_str(raw.get('username')).lstrip('@'),
        'full_name': _clean_str(raw.get('full_name')),
        'bio': _clean_str(raw.get('bio')),
        'email': _clean_str(raw.get('email')).lower(),
        'follower_count': _clean_int(raw.get('follower_count')),
        'website': _clean_str(raw.get('website')),
        'links': links,
        'platform': _clean_str(raw.get('platform')) or platform,
        'profile_url': _clean_str(raw.get('profile_url')),
    }
    if not lead['website'] and links:
        lead['website'] = links[0]
    return lead


def is_valid(lead: Optional[Dict[str, Any]]) -> bool:
    if not lead:
        return False
    if not (lead.get('username') or lead.get('full_name')):
        return False
    count = lead.get('follower_count', 0)
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        return False
    email = lead.get('email')
    if email and not _EMAIL.match(email):
        return False
    return True

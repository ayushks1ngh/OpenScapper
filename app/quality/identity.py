"""Decide whether two lead dicts describe the same person, and say why.

Evidence is combined as independent probabilities (noisy-or): 1 - prod(1 - weight).
No single weak signal reaches THRESHOLD on its own, so a common name or username never merges
two strangers; strong signals (shared email/phone, a link between the two profiles) do.
"""

import difflib
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.lead.detect import detect

THRESHOLD = 0.8

# domains that say nothing about identity: socials and link aggregators
SHARED_DOMAINS = {
    'instagram.com', 'tiktok.com', 'youtube.com', 'linkedin.com', 'github.com', 'twitch.tv',
    'pinterest.com', 'linktr.ee', 'beacons.ai', 'bit.ly', 'facebook.com', 'twitter.com', 'x.com',
    'wa.me', 'gmail.com', 'calendly.com', 'stan.store', 'carrd.co',
}
GENERIC_LOCALS = {'info', 'hello', 'contact', 'admin', 'support', 'sales', 'office', 'team', 'mail', 'hi'}

W_EMAIL, W_EMAIL_GENERIC, W_PHONE = 0.85, 0.5, 0.85
W_CROSS_LINK, W_DOMAIN = 0.9, 0.5
W_USERNAME_EQ, W_USERNAME_SIM, W_NAME_EQ = 0.65, 0.35, 0.45


def _fold(s: str) -> str:
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(c for c in s if not unicodedata.combining(c)).lower()


def norm_name(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', _fold(name))


def norm_username(u: str) -> str:
    return re.sub(r'[^a-z0-9]', '', _fold(u))


def norm_phone(p: str) -> str:
    digits = re.sub(r'\D', '', p or '')
    return digits[-10:] if len(digits) >= 10 else ''


def domain_of(url: str) -> str:
    if not url:
        return ''
    if '://' not in url:
        url = 'https://' + url
    try:
        host = (urlparse(url).hostname or '').lower()
    except ValueError:
        return ''
    host = host[4:] if host.startswith('www.') else host
    return '' if host in SHARED_DOMAINS or not host else host


def _profile_refs(lead: Dict[str, Any]) -> set:
    """(platform, identifier) pairs this lead links out to."""
    refs = set()
    for url in list(lead.get('links') or []) + list((lead.get('socials') or {}).values()) \
            + [lead.get('website') or '']:
        d = detect(url) if url else None
        if d:
            refs.add((d.platform, norm_username(d.identifier)))
    return refs


def _self_ref(lead: Dict[str, Any]) -> Optional[Tuple[str, str]]:
    platform, user = lead.get('platform'), norm_username(lead.get('username') or '')
    return (platform, user) if platform and user else None


def match(a: Dict[str, Any], b: Dict[str, Any]) -> Tuple[float, List[str]]:
    """Return (probability they are the same person, human-readable reasons)."""
    weights: List[float] = []
    reasons: List[str] = []

    def add(w: float, why: str):
        weights.append(w)
        reasons.append(why)

    ea, eb = (a.get('email') or '').lower(), (b.get('email') or '').lower()
    if ea and ea == eb:
        local = ea.split('@')[0]
        add(W_EMAIL_GENERIC if local in GENERIC_LOCALS else W_EMAIL, f'same email {ea}')

    pa, pb = norm_phone(a.get('phone') or ''), norm_phone(b.get('phone') or '')
    if pa and pa == pb:
        add(W_PHONE, 'same phone number')

    sa, sb = _self_ref(a), _self_ref(b)
    if (sb and sb in _profile_refs(a)) or (sa and sa in _profile_refs(b)):
        add(W_CROSS_LINK, 'one profile links to the other')

    da, db = domain_of(a.get('website') or ''), domain_of(b.get('website') or '')
    if da and da == db:
        add(W_DOMAIN, f'same website {da}')

    ua, ub = norm_username(a.get('username') or ''), norm_username(b.get('username') or '')
    if len(ua) >= 5 and len(ub) >= 5:
        if ua == ub:
            add(W_USERNAME_EQ, f'same username "{ua}"')
        elif difflib.SequenceMatcher(None, ua, ub).ratio() >= 0.88:
            add(W_USERNAME_SIM, f'similar usernames "{ua}" / "{ub}"')

    na, nb = norm_name(a.get('full_name') or ''), norm_name(b.get('full_name') or '')
    if len(na) >= 6 and na == nb:
        add(W_NAME_EQ, 'same full name')

    p = 1.0
    for w in weights:
        p *= (1 - w)
    return round(1 - p, 3), reasons


def same_person(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    return match(a, b)[0] >= THRESHOLD

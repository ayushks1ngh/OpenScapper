"""Explainable lead score (0-100). Every point comes with a reason, so the number can be trusted or argued with."""

from typing import Any, Dict, List, Tuple

from app.quality.identity import GENERIC_LOCALS

INTENT_WORDS = ('coach', 'consultant', 'ceo', 'founder', 'owner', 'entrepreneur', 'agency', 'director',
                'manager', 'studio', 'clinic', 'business', 'booking', 'inquiries', 'enquiries', 'dm for')

Item = Tuple[str, int, str]  # (label, points, why)


def _email(lead: Dict[str, Any]) -> Item:
    email = (lead.get('email') or '').lower()
    if not email:
        return ('Email', 0, 'no email found')
    generic = email.split('@')[0] in GENERIC_LOCALS
    if lead.get('email_verified'):
        return ('Email', 20 if generic else 30, 'verified inbox' + (' (shared address, e.g. info@)' if generic else ''))
    if lead.get('email_source') == 'smtp_guess':
        return ('Email', 8, 'pattern-guessed, not confirmed')
    return ('Email', 15 if not generic else 10, 'found on the page, not verified')


def _phone(lead: Dict[str, Any]) -> Item:
    return ('Phone', 15, 'phone number found') if lead.get('phone') else ('Phone', 0, 'no phone found')


def _audience(lead: Dict[str, Any]) -> Item:
    n = lead.get('follower_count') or 0
    if n == 0:
        return ('Audience', 0, 'follower count unknown')
    if 5_000 <= n <= 50_000:
        return ('Audience', 15, f'{n:,} followers: established but still reachable')
    if 1_000 <= n <= 100_000:
        return ('Audience', 10, f'{n:,} followers')
    if n > 100_000:
        return ('Audience', 5, f'{n:,} followers: large accounts rarely answer cold outreach')
    return ('Audience', 4, f'{n:,} followers: small audience')


def _presence(lead: Dict[str, Any]) -> Item:
    platforms = lead.get('platforms') or ([lead['platform']] if lead.get('platform') else [])
    extra = max(len(platforms) - 1, 0)
    if not extra:
        return ('Presence', 0, 'seen on one platform')
    return ('Presence', min(extra * 5, 15), f'confirmed on {len(platforms)} platforms: ' + ', '.join(platforms))


def _complete(lead: Dict[str, Any]) -> Item:
    have = [k for k in ('full_name', 'bio', 'website') if lead.get(k)]
    pts = {0: 0, 1: 3, 2: 7, 3: 10}[len(have)]
    return ('Profile', pts, f"has {', '.join(have)}" if have else 'bare profile')


def _intent(lead: Dict[str, Any]) -> Item:
    bio = (lead.get('bio') or '').lower()
    hits = [w for w in INTENT_WORDS if w in bio]
    if not hits:
        return ('Business signal', 0, 'bio gives no business signal')
    return ('Business signal', min(5 + 2 * (len(hits) - 1), 10), 'bio mentions ' + ', '.join(hits[:3]))


def _trust(lead: Dict[str, Any]) -> Item:
    return ('Verified account', 5, 'platform-verified') if lead.get('is_verified') else ('Verified account', 0, 'not platform-verified')


CHECKS = (_email, _phone, _audience, _presence, _complete, _intent, _trust)


def score(lead: Dict[str, Any]) -> Tuple[int, List[Item]]:
    items = [check(lead) for check in CHECKS]
    return min(sum(p for _, p, _ in items), 100), items


def explain(items: List[Item]) -> str:
    return '; '.join(f'{label} +{pts} ({why})' for label, pts, why in items if pts)


def apply(lead: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with quality_score and a one-line score_explain."""
    total, items = score(lead)
    out = dict(lead)
    out['quality_score'] = total
    out['score_explain'] = explain(items) or 'no positive signals'
    return out

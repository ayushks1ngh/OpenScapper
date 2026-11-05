"""Cluster leads that are the same person and merge each cluster into one lead."""

from typing import Any, Dict, List

from app.quality.identity import same_person


class _DSU:
    def __init__(self, n: int):
        self.p = list(range(n))

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int):
        self.p[self.find(a)] = self.find(b)


def cluster(leads: List[Dict[str, Any]]) -> List[List[int]]:
    """Index groups; leads are linked when `same_person` holds pairwise (transitive)."""
    dsu = _DSU(len(leads))
    for i in range(len(leads)):
        for j in range(i + 1, len(leads)):
            if same_person(leads[i], leads[j]):
                dsu.union(i, j)
    groups: Dict[int, List[int]] = {}
    for i in range(len(leads)):
        groups.setdefault(dsu.find(i), []).append(i)
    return sorted(groups.values(), key=lambda g: g[0])


def _source(lead: Dict[str, Any]) -> Dict[str, Any]:
    return {'platform': lead.get('platform', ''), 'username': lead.get('username', ''),
            'profile_url': lead.get('profile_url', ''), 'follower_count': lead.get('follower_count', 0) or 0}


def merge(group: List[Dict[str, Any]]) -> Dict[str, Any]:
    """One lead from several. The biggest audience is the primary record; gaps are filled from the rest."""
    ordered = sorted(group, key=lambda l: -(l.get('follower_count') or 0))
    out = dict(ordered[0])

    for other in ordered[1:]:
        for key, value in other.items():
            if key in ('links', 'socials') or key in out and out[key] not in (None, '', 0, False, [], {}):
                continue
            if value not in (None, '', [], {}):
                out[key] = value

    verified = [l for l in ordered if l.get('email') and l.get('email_verified')]
    if verified:
        out['email'], out['email_verified'] = verified[0]['email'], True

    bios = [l.get('bio') or '' for l in ordered]
    out['bio'] = max(bios, key=len)

    links: List[str] = []
    for l in ordered:
        for link in l.get('links') or []:
            if link and link not in links:
                links.append(link)
    out['links'] = links
    socials: Dict[str, Any] = {}
    for l in reversed(ordered):
        socials.update(l.get('socials') or {})
    out['socials'] = socials

    out['follower_count'] = max((l.get('follower_count') or 0) for l in ordered)
    out['total_reach'] = sum((l.get('follower_count') or 0) for l in ordered)
    out['sources'] = [_source(l) for l in ordered]
    out['platforms'] = sorted({l.get('platform') for l in ordered if l.get('platform')})
    return out


def dedupe(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [merge([leads[i] for i in g]) if len(g) > 1 else _single(leads[g[0]]) for g in cluster(leads)]


def _single(lead: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(lead)
    out['sources'] = [_source(lead)]
    out['platforms'] = [lead['platform']] if lead.get('platform') else []
    out['total_reach'] = lead.get('follower_count') or 0
    return out

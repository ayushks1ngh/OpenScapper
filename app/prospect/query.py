"""Turn "yoga studio owners in Austin with 5k+ followers on instagram" into a SearchPlan.

Rule based, so it works offline and is predictable. Anything it can't read is left in `terms`.
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional

PLATFORM_WORDS = {
    'instagram': 'instagram', 'insta': 'instagram', 'ig': 'instagram',
    'tiktok': 'tiktok', 'youtube': 'youtube', 'yt': 'youtube', 'linkedin': 'linkedin',
    'github': 'github', 'twitch': 'twitch', 'pinterest': 'pinterest', 'linktree': 'linktree',
}
DEFAULT_PLATFORMS = ['instagram', 'tiktok', 'youtube']

_NUM = r'(\d[\d,]*(?:\.\d+)?)\s*([kKmM]?)'
_UNIT = r'(?:followers?|subscribers?|subs)'
_LOC_STOP = {'with', 'who', 'that', 'and', 'on', 'having', 'has', 'have', 'over', 'under', 'above',
             'below', 'at', 'for', 'using', 'by', 'from', 'than', 'between', 'more', 'less'}
_FILLER = {'find', 'me', 'get', 'give', 'show', 'list', 'of', 'a', 'an', 'the', 'some', 'all', 'any',
           'leads', 'lead', 'profiles', 'profile', 'accounts', 'account', 'people', 'who', 'are', 'is',
           'with', 'on', 'for', 'please', 'looking', 'i', 'want', 'need', 'to', 'and', 'that', 'have', 'has',
           'followers', 'follower', 'subs', 'subscribers', 'over', 'under', 'at', 'least', 'most', 'more',
           'less', 'than', 'between', 'about', 'around'}


@dataclass
class SearchPlan:
    terms: str = ''
    location: str = ''
    platforms: List[str] = field(default_factory=lambda: list(DEFAULT_PLATFORMS))
    min_followers: Optional[int] = None
    max_followers: Optional[int] = None
    raw: str = ''

    def search_text(self) -> str:
        return ' '.join(x for x in (self.terms, self.location) if x)


def _to_int(num: str, suffix: str) -> int:
    n = float(num.replace(',', ''))
    mult = {'k': 1_000, 'm': 1_000_000}.get(suffix.lower(), 1)
    return int(n * mult)


def _followers(text: str):
    """Returns (min, max, text_without_the_clause)."""
    m = re.search(rf'between\s+{_NUM}\s*(?:and|-|to)\s*{_NUM}\s*{_UNIT}?', text, re.I)
    if m:
        a, b = _to_int(m.group(1), m.group(2)), _to_int(m.group(3), m.group(4))
        return min(a, b), max(a, b), text.replace(m.group(0), ' ')
    m = re.search(rf'{_NUM}\s*(?:-|to)\s*{_NUM}\s*{_UNIT}', text, re.I)
    if m:
        a, b = _to_int(m.group(1), m.group(2)), _to_int(m.group(3), m.group(4))
        return min(a, b), max(a, b), text.replace(m.group(0), ' ')
    m = re.search(rf'(under|less than|below|max(?:imum)?|at most|up to)\s+{_NUM}\s*{_UNIT}?', text, re.I)
    if m:
        return None, _to_int(m.group(2), m.group(3)), text.replace(m.group(0), ' ')
    m = re.search(rf'(?:(over|more than|above|at least|min(?:imum)?)\s+)?{_NUM}\s*(\+)?\s*{_UNIT}', text, re.I)
    if m:
        return _to_int(m.group(2), m.group(3)), None, text.replace(m.group(0), ' ')
    return None, None, text


def _location(text: str):
    """Words after 'in/near/based in' up to a stop word. Returns (location, text_without_it)."""
    m = re.search(r'\b(?:based in|located in|near|in)\s+((?:[\w.\'-]+,?\s*){1,4})', text, re.I)
    if not m:
        return '', text
    words, consumed = [], 0
    for tok in m.group(1).split():
        bare = tok.strip(',').lower()
        if bare in _LOC_STOP or bare in PLATFORM_WORDS or bare.isdigit():
            break
        words.append(tok.strip(','))
        consumed += 1
        if tok.endswith(',') and consumed >= 1 and len(words) >= 2:
            break
    if not words:
        return '', text
    loc = ' '.join(words)
    # remove the whole matched phrase (keyword + the location words)
    phrase = re.escape(m.group(0)[:m.group(0).lower().index(words[0].lower())]) + r'\s*' + r'[,\s]*'.join(
        re.escape(w) for w in words) + r',?'
    cleaned = re.sub(phrase, ' ', text, count=1, flags=re.I)
    return loc, cleaned


def parse_query(text: str) -> SearchPlan:
    plan = SearchPlan(raw=text.strip())
    work = ' ' + plan.raw + ' '

    plats = []
    for word in re.findall(r"[A-Za-z]+", work):
        p = PLATFORM_WORDS.get(word.lower())
        if p and p not in plats:
            plats.append(p)
    if plats:
        plan.platforms = plats

    plan.min_followers, plan.max_followers, work = _followers(work)
    plan.location, work = _location(work)

    kept = []
    for tok in re.findall(r"[A-Za-z0-9&'/-]+", work):
        low = tok.lower()
        if low in PLATFORM_WORDS or low in _FILLER:
            continue
        kept.append(tok)
    plan.terms = ' '.join(kept)
    return plan

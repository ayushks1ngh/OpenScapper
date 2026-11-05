"""Learn CSS selectors from known-good values, and replay them on later pages (tier 3)."""

import re
from typing import Any, Dict, List, Optional

TEXT_FIELDS = ('full_name', 'username', 'bio')
LINK_FIELDS = ('website',)
MAX_DEPTH = 3
_STABLE_CLASS = re.compile(r'^[a-zA-Z][a-zA-Z-]{2,24}$')  # skips hashed/utility-looking classes


def _page(html: str):
    from scrapling import Selector
    return Selector(html)


def _text(el) -> str:
    return re.sub(r'\s+', ' ', el.get_all_text(strip=True) or '').strip()


def _descriptor(el) -> str:
    tag = el.tag
    attrib = el.attrib or {}
    eid = attrib.get('id', '')
    if eid and _STABLE_CLASS.match(eid):
        return f'{tag}#{eid}'
    classes = [c for c in (attrib.get('class') or '').split() if _STABLE_CLASS.match(c)][:2]
    return tag + ''.join(f'.{c}' for c in classes)


def _candidates(el) -> List[str]:
    chain, node = [], el
    for _ in range(MAX_DEPTH + 1):
        if node is None or not getattr(node, 'tag', None) or node.tag in ('html', 'body'):
            break
        chain.append(_descriptor(node))
        node = node.parent
    out = []
    for n in range(1, len(chain) + 1):
        out.append(' > '.join(reversed(chain[:n])))
    return out


def _read(el, attr: str) -> str:
    return (el.attrib or {}).get(attr, '') if attr else _text(el)


def _matches(value: str, got: str, loose: bool) -> bool:
    if not got:
        return False
    if loose:  # long text such as a bio: allow the page to truncate or pad it
        return value[:40] == got[:40] or value in got
    return got == value


def _find(page, value: str, attr: str, loose: bool) -> Optional[str]:
    tag_filter = 'a' if attr == 'href' else '*'
    for el in page.css(tag_filter):
        if not _matches(value, _read(el, attr), loose):
            continue
        # prefer the most specific element whose own reading matches, then the shortest selector that finds it
        for cand in _candidates(el):
            try:
                hits = page.css(cand)
            except Exception:
                continue
            if hits and _matches(value, _read(hits[0], attr), loose):
                return cand
    return None


def induce(html: str, lead: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """Return {field: {'selector', 'attr'}} for every lead value we can locate in `html`."""
    page = _page(html)
    found: Dict[str, Dict[str, str]] = {}
    for field in TEXT_FIELDS:
        value = str(lead.get(field) or '').strip()
        if len(value) >= 3:
            sel = _find(page, value, '', loose=(field == 'bio'))
            if sel:
                found[field] = {'selector': sel, 'attr': ''}
    for field in LINK_FIELDS:
        value = str(lead.get(field) or '').strip()
        if value:
            sel = _find(page, value, 'href', loose=False)
            if sel:
                found[field] = {'selector': sel, 'attr': 'href'}
    return found


def apply_selectors(html: str, selectors: Dict[str, Dict[str, str]]) -> Dict[str, str]:
    """Run learned selectors. Only fields that produced a value are returned."""
    page = _page(html)
    out: Dict[str, str] = {}
    for field, spec in selectors.items():
        try:
            hits = page.css(spec['selector'])
        except Exception:
            continue
        if hits:
            val = _read(hits[0], spec.get('attr', ''))
            if val:
                out[field] = val
    return out

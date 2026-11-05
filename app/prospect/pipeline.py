"""discover -> scrape -> enrich -> filter -> rank -> export."""

import csv
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from app.lead.detect import Detected
from app.prospect.discover import discover as _discover
from app.prospect.query import SearchPlan
from app.quality import scoring
from app.quality.merge import dedupe

logger = logging.getLogger(__name__)

CSV_FIELDS = ['quality_score', 'score_explain', 'platform', 'platforms', 'username', 'full_name', 'email',
              'email_verified', 'phone', 'follower_count', 'total_reach', 'website', 'bio', 'profile_url',
              'followers_unknown', 'lead_score']


def _default_scrape(d: Detected) -> Optional[Dict[str, Any]]:
    from app.lead.any_url import lead_from_url
    return lead_from_url(d.url).lead


def _default_enrich(lead: Dict[str, Any]) -> Dict[str, Any]:
    from app.scrapers.enrichment import enrich_lead
    return enrich_lead(lead)


def in_range(lead: Dict[str, Any], plan: SearchPlan) -> bool:
    """Out-of-range counts are dropped; an unknown count (0) is kept and flagged by the caller."""
    n = lead.get('follower_count') or 0
    if n == 0:
        return True
    if plan.min_followers is not None and n < plan.min_followers:
        return False
    if plan.max_followers is not None and n > plan.max_followers:
        return False
    return True


def rank(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(leads, key=lambda l: (-(l.get('quality_score', l.get('lead_score')) or 0),
                                        -(l.get('follower_count') or 0), l.get('username') or ''))


def run(plan: SearchPlan, per_platform: int = 10, workers: int = 3,
        discover_fn: Callable[..., Dict[str, List[Detected]]] = _discover,
        scrape_fn: Callable[[Detected], Optional[Dict[str, Any]]] = _default_scrape,
        enrich_fn: Callable[[Dict[str, Any]], Dict[str, Any]] = _default_enrich,
        on_progress: Optional[Callable[[str, int, int], None]] = None) -> Dict[str, Any]:
    """Returns {'leads': ranked list, 'stats': {...}}. Individual failures never abort the run."""
    found = discover_fn(plan, per_platform=per_platform)
    candidates = [d for ds in found.values() for d in ds]
    stats = {'discovered': len(candidates), 'scraped': 0, 'enriched': 0, 'filtered_out': 0, 'failed': 0,
             'merged': 0}
    if on_progress:
        on_progress('discovered', 0, len(candidates))

    lock = threading.Lock()

    def bump(key: str):
        with lock:
            stats[key] += 1

    def work(d: Detected) -> Optional[Dict[str, Any]]:
        try:
            lead = scrape_fn(d)
        except Exception as e:
            logger.debug(f"scrape failed for {d.url}: {e}")
            return None
        if not lead:
            return None
        bump('scraped')
        if not in_range(lead, plan):
            bump('filtered_out')
            return {'_dropped': True}
        try:
            lead = enrich_fn(dict(lead))
            bump('enriched')
        except Exception as e:
            logger.debug(f"enrich failed for {d.url}: {e}")
        lead['followers_unknown'] = not (lead.get('follower_count') or 0)
        lead.setdefault('platform', d.platform)
        return lead

    leads: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        for i, res in enumerate(pool.map(work, candidates), 1):
            if res is None:
                stats['failed'] += 1
            elif not res.get('_dropped'):
                leads.append(res)
            if on_progress:
                on_progress('scraping', i, len(candidates))

    unique = dedupe(leads)
    stats['merged'] = len(leads) - len(unique)
    return {'leads': rank([scoring.apply(l) for l in unique]), 'stats': stats}


def export_csv(leads: List[Dict[str, Any]], path: Optional[str] = None) -> str:
    path = path or f"prospects_{time.strftime('%Y%m%d_%H%M%S')}.csv"
    with open(Path(path), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        for lead in leads:
            row = dict(lead)
            row['platforms'] = ', '.join(lead.get('platforms') or [])
            w.writerow(row)
    return str(path)

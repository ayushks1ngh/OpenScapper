"""Turn raw tier stats into a per-platform health summary for the CLI."""

from typing import Dict, List

HEALING_TIERS = ('generic', 'learned', 'llm')


def summarize(stats: List[Dict]) -> List[Dict]:
    """stats: rows from Cache.stats(). One summary row per platform, worst health first."""
    plat: Dict[str, Dict] = {}
    for row in stats:
        p = plat.setdefault(row['platform'], {'platform': row['platform'], 'served': 0, 'primary': 0,
                                              'healed': 0, 'failed': 0, 'tiers': {}})
        tier, ok, runs = row['tier'], row['ok'], row['runs']
        if tier == 'none':
            p['failed'] += runs
        elif ok:
            p['served'] += ok
            p['tiers'][tier] = p['tiers'].get(tier, 0) + ok
            if tier == 'primary':
                p['primary'] += ok
            elif tier in HEALING_TIERS:
                p['healed'] += ok

    out = []
    for p in plat.values():
        total = p['served'] + p['failed']
        p['total'] = total
        p['primary_rate'] = round(100 * p['primary'] / total) if total else 0
        if total == 0:
            p['status'] = 'idle'
        elif p['failed'] and p['failed'] >= p['served']:
            p['status'] = 'broken'
        elif p['primary_rate'] < 60:
            p['status'] = 'healing'
        else:
            p['status'] = 'healthy'
        out.append(p)

    order = {'broken': 0, 'healing': 1, 'healthy': 2, 'idle': 3}
    return sorted(out, key=lambda r: (order[r['status']], r['platform']))

import csv

from app.lead.detect import Detected
from app.prospect import pipeline
from app.prospect.query import SearchPlan


def det(name, platform='instagram'):
    return Detected(platform, name, f'https://{platform}.com/{name}')


def discover_fn(plan, per_platform=10):
    return {'instagram': [det('a'), det('b'), det('c'), det('d'), det('e')]}


LEADS = {
    'a': {'username': 'a', 'follower_count': 6000, 'full_name': 'A'},
    'b': {'username': 'b', 'follower_count': 100, 'full_name': 'B'},          # below min
    'c': {'username': 'c', 'follower_count': 0, 'full_name': 'C'},            # unknown
    'd': None,                                                                # scrape returned nothing
    'e': {'username': 'e', 'follower_count': 9000, 'full_name': 'E'},
}


def scrape(d):
    if d.identifier == 'x':
        raise RuntimeError('boom')
    return LEADS[d.identifier]


def enrich(lead):
    lead['lead_score'] = {'a': 40, 'c': 40, 'e': 90}[lead['username']]
    return lead


def test_full_run_filters_ranks_and_counts():
    out = pipeline.run(SearchPlan(min_followers=5000), discover_fn=discover_fn,
                       scrape_fn=scrape, enrich_fn=enrich)
    users = [l['username'] for l in out['leads']]
    assert users == ['e', 'a', 'c']  # score desc, then followers desc; b filtered, d failed
    assert out['stats'] == {'discovered': 5, 'scraped': 4, 'enriched': 3, 'filtered_out': 1, 'failed': 1,
                          'merged': 0}
    c = next(l for l in out['leads'] if l['username'] == 'c')
    assert c['followers_unknown'] is True


def test_errors_in_scrape_and_enrich_do_not_abort():
    def d_fn(plan, per_platform=10):
        return {'instagram': [det('x'), det('a')]}

    def bad_enrich(lead):
        raise ValueError('smtp down')

    out = pipeline.run(SearchPlan(), discover_fn=d_fn, scrape_fn=scrape, enrich_fn=bad_enrich)
    assert [l['username'] for l in out['leads']] == ['a']
    assert out['stats']['failed'] == 1 and out['stats']['enriched'] == 0


def test_max_followers_and_progress_callback():
    seen = []
    out = pipeline.run(SearchPlan(max_followers=7000), discover_fn=discover_fn, scrape_fn=scrape,
                       enrich_fn=enrich, on_progress=lambda stage, i, n: seen.append((stage, i, n)))
    assert 'e' not in [l['username'] for l in out['leads']]
    assert seen[0] == ('discovered', 0, 5) and seen[-1] == ('scraping', 5, 5)


def test_export_csv(tmp_path):
    p = pipeline.export_csv([{'username': 'a', 'lead_score': 50, 'follower_count': 10, 'junk': 1,
                              'email_verified': True}], str(tmp_path / 'o.csv'))
    rows = list(csv.DictReader(open(p, encoding='utf-8')))
    assert rows[0]['username'] == 'a' and rows[0]['lead_score'] == '50'
    assert rows[0]['email_verified'] == 'True'
    assert 'junk' not in rows[0]


def test_same_person_on_two_platforms_is_merged_and_scored():
    def d_fn(plan, per_platform=10):
        return {'instagram': [det('janedoe')], 'youtube': [det('janedoe', 'youtube')]}

    pool = {('instagram', 'janedoe'): {'platform': 'instagram', 'username': 'janedoe', 'full_name': 'Jane Doe',
                                       'follower_count': 8000, 'bio': 'Founder'},
            ('youtube', 'janedoe'): {'platform': 'youtube', 'username': 'janedoe', 'full_name': 'Jane Doe',
                                     'follower_count': 20000, 'email': 'jane@janedoe.com'}}
    out = pipeline.run(SearchPlan(), discover_fn=d_fn, scrape_fn=lambda d: dict(pool[(d.platform, d.identifier)]),
                       enrich_fn=lambda l: l)
    assert len(out['leads']) == 1 and out['stats']['merged'] == 1
    lead = out['leads'][0]
    assert lead['platforms'] == ['instagram', 'youtube'] and lead['total_reach'] == 28000
    assert lead['quality_score'] > 0 and 'Presence +5' in lead['score_explain']


def test_csv_includes_score_columns(tmp_path):
    p = pipeline.export_csv([{'username': 'a', 'quality_score': 61, 'score_explain': 'Phone +15 (x)',
                              'platforms': ['instagram', 'youtube']}], str(tmp_path / 'o.csv'))
    row = next(csv.DictReader(open(p, encoding='utf-8')))
    assert row['quality_score'] == '61' and row['platforms'] == 'instagram, youtube'
    assert row['score_explain'].startswith('Phone')

"""TikTok scraper end to end with a fake fetch: healthy page vs. a changed layout."""
import json

import pytest

from app.healing import engine
from app.scrapers import tiktok
from app.scrapers.fetch import FetchResult

DATA = {'__DEFAULT_SCOPE__': {'webapp.user-detail': {'userInfo': {
    'user': {'uniqueId': 'jane', 'nickname': 'Jane Doe', 'signature': 'Reach me jane@acme.io',
             'verified': True},
    'stats': {'followerCount': 5000, 'followingCount': 10, 'heartCount': 99, 'videoCount': 7}}}}}

GOOD = ('<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" type="application/json">'
        + json.dumps(DATA) + '</script></html>' + 'x' * 400)
# TikTok renamed the data script: the primary parser can no longer find it
CHANGED = ('<html><head><meta property="og:title" content="Jane Doe (@jane) | TikTok">'
           '<meta property="og:description" content="Reach me jane@acme.io"></head></html>' + 'x' * 400)


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENSCRAPPER_HOME', str(tmp_path))
    monkeypatch.delenv('SCOUT_LLM', raising=False)
    monkeypatch.setattr(engine, '_cache', None)
    yield
    if engine._cache:
        engine._cache.close()


def fake(html, status=200):
    return lambda url, **kw: FetchResult(url=url, status=status, text=html, engine='http')


def test_healthy_page_keeps_all_platform_fields(monkeypatch):
    monkeypatch.setattr(tiktok, 'fetch_get', fake(GOOD))
    p = tiktok.scrape_tiktok_profile('jane')
    assert p['username'] == 'jane' and p['follower_count'] == 5000
    assert p['is_verified'] is True and p['likes_count'] == 99 and p['email'] == 'jane@acme.io'
    assert engine.get_cache().stats()[0]['tier'] == 'primary'


def test_changed_layout_is_healed_instead_of_failing(monkeypatch):
    monkeypatch.setattr(tiktok, 'fetch_get', fake(CHANGED))
    p = tiktok.scrape_tiktok_profile('jane')
    assert p is not None and p['full_name'].startswith('Jane Doe')
    tiers = {s['tier']: s for s in engine.get_cache().stats()}
    assert tiers['primary']['ok'] == 0 and tiers['generic']['ok'] == 1


def test_http_error_returns_none(monkeypatch):
    monkeypatch.setattr(tiktok, 'fetch_get', fake('', status=500))
    assert tiktok.scrape_tiktok_profile('jane') is None


def test_login_wall_is_not_turned_into_a_lead(monkeypatch):
    wall = '<meta property="og:title" content="Login | TikTok">' + 'x' * 400
    monkeypatch.setattr(tiktok, 'fetch_get', fake(wall))
    assert tiktok.scrape_tiktok_profile('jane') is None

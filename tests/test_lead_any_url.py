import pytest

from app.healing import engine
from app.lead import any_url
from app.scrapers.fetch import FetchResult

PAGE = '''<html><head><title>Acme Studio</title>
<meta property="og:title" content="Jane Doe | Acme Studio">
<meta property="og:description" content="Brand coach in Austin">
<script type="application/ld+json">{"@type":"Person","name":"Jane Doe","email":"hello@acme.io"}</script>
</head><body><a href="mailto:book@acme.io">Book</a> Call (555) 123-4567
<a href="https://www.instagram.com/janedoe/">IG</a>
<a href="https://github.com/janedoe/repo">repo</a>
<a href="https://www.youtube.com/@JaneDoe">YT</a> ''' + 'x' * 300 + '</body></html>'


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv('OPENSCRAPPER_HOME', str(tmp_path))
    monkeypatch.setattr(engine, '_cache', None)
    yield
    if engine._cache:
        engine._cache.close()


def fetcher_for(html, status=200):
    return lambda url, **kw: FetchResult(url=url, status=status, text=html, engine='http')


def test_social_links_skip_non_profiles():
    s = any_url.social_links(PAGE)
    assert set(s) == {'instagram', 'youtube'}  # the github repo link is not a profile


def test_unknown_site_becomes_a_lead():
    r = any_url.lead_from_url('https://acme.io/about', llm=None, fetcher=fetcher_for(PAGE))
    assert r.source == 'web' and r.tier == 'primary'
    lead = r.lead
    assert lead['full_name'] == 'Jane Doe'
    assert lead['email'] == 'hello@acme.io'  # structured data beats mailto
    assert lead['phone'] == '(555) 123-4567'
    assert lead['socials']['instagram'].endswith('/janedoe/')
    assert lead['profile_url']


def test_mailto_used_when_no_structured_email():
    page = PAGE.replace('"email":"hello@acme.io"', '"x":1')
    r = any_url.lead_from_url('acme.io', llm=None, fetcher=fetcher_for(page))
    assert r.lead['email'] == 'book@acme.io'


def test_known_platform_uses_its_scraper(monkeypatch):
    monkeypatch.setattr(any_url, '_platform_scraper',
                        lambda p: (lambda ident: {'username': ident, 'platform': p, 'full_name': 'J'}))
    r = any_url.lead_from_url('https://www.tiktok.com/@jane', llm=None)
    assert r.source == 'tiktok' and r.lead['username'] == 'jane'
    assert r.lead['profile_url'] == 'https://www.tiktok.com/@jane'


def test_platform_scraper_failure_falls_back_to_page(monkeypatch):
    monkeypatch.setattr(any_url, '_platform_scraper', lambda p: (lambda ident: None))
    r = any_url.lead_from_url('https://www.tiktok.com/@jane', llm=None, fetcher=fetcher_for(PAGE))
    assert r.source == 'tiktok' and r.lead and r.lead['full_name'] == 'Jane Doe'


def test_blocked_or_empty_page_gives_none():
    r = any_url.lead_from_url('https://acme.io', llm=None, fetcher=fetcher_for('', status=403))
    assert r.lead is None and r.tier == 'none'
    r = any_url.lead_from_url('https://acme.io', llm=None, fetcher=lambda u, **k: None)
    assert r.lead is None


def test_page_without_any_person_data_is_rejected():
    r = any_url.lead_from_url('https://acme.io', llm=None,
                              fetcher=fetcher_for('<html><body>' + 'lorem ' * 100 + '</body></html>'))
    assert r.lead is None

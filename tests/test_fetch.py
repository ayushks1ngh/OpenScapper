"""fetch() tier escalation, using fake runners (no network, no Scrapling needed)."""
import pytest

from app.scrapers import fetch as F

GOOD = '<html>' + 'x' * 500 + '</html>'
BLOCKED = '<html>Just a moment... cf-chl</html>' + 'x' * 400


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    F._disabled.clear()
    monkeypatch.delenv('SCOUT_ENGINE', raising=False)
    calls = []

    def make(name, fn):
        def runner(url, timeout, headers):
            calls.append(name)
            return fn()
        return runner

    def install(**tiers):
        for name, fn in tiers.items():
            monkeypatch.setitem(F._RUNNERS, name, make(name, fn))
        return calls

    return install


def test_first_tier_wins(reset):
    calls = reset(http=lambda: (200, GOOD))
    r = F.fetch('example.com')
    assert r.ok and r.engine == 'http' and calls == ['http']
    assert r.url == 'https://example.com'


def test_escalates_on_block(reset):
    calls = reset(http=lambda: (403, ''), stealth=lambda: (200, GOOD))
    r = F.fetch('https://example.com')
    assert r.engine == 'stealth' and calls == ['http', 'stealth']


def test_escalates_on_challenge_page_with_200(reset):
    calls = reset(http=lambda: (200, BLOCKED), stealth=lambda: (200, GOOD))
    assert F.fetch('https://example.com').engine == 'stealth'


def test_404_not_escalated(reset):
    calls = reset(http=lambda: (404, ''), stealth=lambda: (200, GOOD))
    r = F.fetch('https://example.com/nope')
    assert r.status == 404 and calls == ['http']


def test_import_error_disables_tier(reset):
    def boom():
        raise ImportError('no scrapling')
    calls = reset(http=boom, stealth=boom, browser=lambda: (200, GOOD))
    assert F.fetch('https://a.com').engine == 'browser'
    assert {'http', 'stealth'} <= F._disabled
    calls.clear()
    F.fetch('https://b.com')
    assert calls == ['browser']  # disabled tiers skipped on later calls


def test_all_fail_returns_last_blocked_result(reset):
    reset(http=lambda: (403, ''), stealth=lambda: (403, ''), browser=lambda: (503, ''))
    r = F.fetch('https://example.com')
    assert r.status == 503 and not r.ok


def test_all_raise_returns_none(reset):
    def boom():
        raise RuntimeError('net down')
    reset(http=boom, stealth=boom, browser=boom)
    assert F.fetch('https://example.com') is None


def test_min_tier_skips_cheaper(reset):
    calls = reset(http=lambda: (200, GOOD), stealth=lambda: (200, GOOD))
    F.fetch('https://example.com', min_tier='stealth')
    assert calls == ['stealth']


def test_explicit_mode_and_env(reset, monkeypatch):
    calls = reset(legacy=lambda: (200, GOOD), http=lambda: (200, GOOD))
    F.fetch('https://example.com', mode='legacy')
    monkeypatch.setenv('SCOUT_ENGINE', 'legacy')
    F.fetch('https://example.com')
    assert calls == ['legacy', 'legacy']


def test_invalid_env_falls_back_to_auto(monkeypatch):
    monkeypatch.setenv('SCOUT_ENGINE', 'bogus')
    assert F.engine_mode() == 'auto'


def test_get_raises_when_all_tiers_fail(reset):
    import requests

    def boom():
        raise RuntimeError('x')
    reset(http=boom, stealth=boom, browser=boom)
    with pytest.raises(requests.exceptions.ConnectionError):
        F.get('https://example.com')

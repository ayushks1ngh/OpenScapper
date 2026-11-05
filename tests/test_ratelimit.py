from app import ratelimit
from app.scrapers import fetch as F

GOOD = '<html>' + 'x' * 500 + '</html>'


def test_backoff_grows_and_is_capped():
    d = [ratelimit.backoff_delay(i, base=1, cap=8, jitter=0) for i in range(1, 7)]
    assert d == [1, 2, 4, 8, 8, 8]
    assert 0.75 <= ratelimit.backoff_delay(1, jitter=0.25) <= 1.25


def test_throttle_spaces_requests_per_host(monkeypatch):
    now = [100.0]
    slept = []
    monkeypatch.setattr(ratelimit, '_clock', lambda: now[0])
    monkeypatch.setattr(ratelimit, 'sleep', slept.append)
    t = ratelimit.HostThrottle(min_interval=2.0)
    assert t.wait('a.com') == 0
    assert t.wait('a.com') == 2.0           # second hit must wait the full interval
    assert t.wait('b.com') == 0             # other hosts are independent
    now[0] += 10
    assert t.wait('a.com') == 0             # enough time has passed
    assert slept == [2.0]


def test_throttle_disabled_when_interval_zero():
    assert ratelimit.HostThrottle(0).wait('a.com') == 0.0
    assert ratelimit.HostThrottle(5).wait('') == 0.0


def runner(statuses, calls):
    it = iter(statuses)

    def r(url, timeout, headers):
        calls.append(url)
        status = next(it)
        return status, GOOD if status == 200 else ''
    return r


def test_fetch_retries_429_then_succeeds(monkeypatch, fast_network_politeness):
    F._disabled.clear()
    calls = []
    monkeypatch.setitem(F._RUNNERS, 'http', runner([429, 429, 200], calls))
    res = F.fetch('https://example.com', mode='http')
    assert res.ok and len(calls) == 3
    assert len(fast_network_politeness) == 2          # two backoff sleeps


def test_retries_are_bounded_then_escalate(monkeypatch):
    F._disabled.clear()
    http_calls, stealth_calls = [], []
    monkeypatch.setenv('OPENSCRAPPER_RETRIES', '1')
    monkeypatch.setitem(F._RUNNERS, 'http', runner([503, 503, 503], http_calls))
    monkeypatch.setitem(F._RUNNERS, 'stealth', runner([200], stealth_calls))
    res = F.fetch('https://example.com')
    assert len(http_calls) == 2 and res.engine == 'stealth'


def test_403_is_not_retried_on_same_tier(monkeypatch):
    F._disabled.clear()
    calls = []
    monkeypatch.setitem(F._RUNNERS, 'http', runner([403], calls))
    monkeypatch.setitem(F._RUNNERS, 'stealth', runner([200], []))
    F.fetch('https://example.com')
    assert len(calls) == 1

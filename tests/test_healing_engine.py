import pytest

pytest.importorskip('scrapling')

from app.healing import engine  # noqa: E402
from app.healing.cache import Cache  # noqa: E402

PAGE_A = ('<html><body><h1 class="chan-title">Jane Doe</h1>'
          '<p class="about-text">I coach founders on pricing.</p></body></html>')
PAGE_B = PAGE_A.replace('Jane Doe', 'John Roe').replace('I coach founders on pricing.', 'Agency workshops here.')
URL = 'https://example.com/@jane'


@pytest.fixture
def cache(tmp_path):
    c = Cache(str(tmp_path / 'h.db'))
    yield c
    c.close()


def good_primary(html):
    return {'username': 'jane', 'full_name': 'Jane Doe'}


def test_primary_wins(cache):
    r = engine.heal('site', URL, PAGE_A, primary=good_primary, llm=None, cache=cache)
    assert r.tier == 'primary' and not r.healed and r.lead['username'] == 'jane'


def test_generic_catches_broken_primary(cache):
    page = '<meta property="og:title" content="Jane Doe">'
    r = engine.heal('site', URL, page, primary=lambda h: None, llm=None, cache=cache)
    assert r.tier == 'generic' and r.healed and r.lead['full_name'] == 'Jane Doe'
    runs = {(s['tier']): s for s in cache.stats()}
    assert runs['primary']['ok'] == 0 and runs['generic']['ok'] == 1


def test_primary_exception_is_contained(cache):
    def boom(h):
        raise RuntimeError('selector changed')
    r = engine.heal('site', URL, '<meta property="og:title" content="J D">', primary=boom, llm=None, cache=cache)
    assert r.tier == 'generic'


def test_llm_then_learned_selectors_avoid_second_llm_call(cache):
    calls = []

    def fake_llm(url):
        calls.append(url)
        return {'full_name': 'Jane Doe', 'bio': 'I coach founders on pricing.'}

    first = engine.heal('site', URL, PAGE_A, primary=lambda h: None, llm=fake_llm, cache=cache)
    assert first.tier == 'llm' and len(calls) == 1
    assert 'full_name' in cache.selectors('site')

    second = engine.heal('site', URL + '2', PAGE_B, primary=lambda h: None, llm=fake_llm, cache=cache)
    assert second.tier == 'learned' and len(calls) == 1  # LLM not called again
    assert second.lead['full_name'] == 'John Roe'
    assert second.lead['bio'] == 'Agency workshops here.'


def test_nothing_works_returns_none(cache):
    r = engine.heal('site', URL, '<html></html>', primary=lambda h: None, llm=lambda u: None, cache=cache)
    assert r.lead is None and r.tier == 'none'
    assert {s['tier'] for s in cache.stats()} == {'primary', 'none'}


def test_invalid_llm_output_is_rejected(cache):
    r = engine.heal('site', URL, '<html></html>', llm=lambda u: {'email': 'bad'}, cache=cache)
    assert r.tier == 'none'

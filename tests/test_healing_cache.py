import pytest

from app.healing.cache import MAX_MISSES, Cache


@pytest.fixture
def cache(tmp_path):
    c = Cache(str(tmp_path / 'h.db'))
    yield c
    c.close()


def test_save_and_load_selectors(cache):
    cache.save_selector('youtube', 'full_name', 'h1.title', '')
    cache.save_selector('youtube', 'website', 'a.site', 'href')
    got = cache.selectors('youtube')
    assert got['full_name'] == {'selector': 'h1.title', 'attr': ''}
    assert got['website']['attr'] == 'href'
    assert cache.selectors('tiktok') == {}


def test_save_overwrites_and_resets_counters(cache):
    cache.save_selector('p', 'f', 'a')
    cache.record_selector_result('p', 'f', False)
    cache.save_selector('p', 'f', 'b')
    assert cache.selectors('p')['f']['selector'] == 'b'
    for _ in range(MAX_MISSES - 1):
        cache.record_selector_result('p', 'f', False)
    assert 'f' in cache.selectors('p')  # reset by the overwrite, not yet dropped


def test_selector_dropped_after_repeated_misses(cache):
    cache.save_selector('p', 'f', 'a')
    for _ in range(MAX_MISSES):
        cache.record_selector_result('p', 'f', False)
    assert cache.selectors('p') == {}


def test_hits_keep_selector(cache):
    cache.save_selector('p', 'f', 'a')
    for _ in range(10):
        cache.record_selector_result('p', 'f', True)
    assert 'f' in cache.selectors('p')


def test_stats(cache):
    cache.record_run('youtube', 'primary', True)
    cache.record_run('youtube', 'primary', False)
    cache.record_run('youtube', 'llm', True)
    s = {(r['platform'], r['tier']): r for r in cache.stats()}
    assert s[('youtube', 'primary')]['runs'] == 2 and s[('youtube', 'primary')]['ok'] == 1
    assert s[('youtube', 'llm')]['ok'] == 1
    assert cache.stats(since_seconds=-1) == []


def test_persists_across_connections(tmp_path):
    p = str(tmp_path / 'x.db')
    a = Cache(p); a.save_selector('p', 'f', 's'); a.close()
    b = Cache(p)
    assert b.selectors('p')['f']['selector'] == 's'
    b.close()

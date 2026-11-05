import pytest

from app.prospect.query import DEFAULT_PLATFORMS, parse_query


def test_full_sentence():
    p = parse_query('Find yoga studio owners in Austin with 5k+ followers on instagram')
    assert p.terms == 'yoga studio owners'
    assert p.location == 'Austin'
    assert p.platforms == ['instagram']
    assert p.min_followers == 5000 and p.max_followers is None


def test_default_platforms_and_no_location():
    p = parse_query('fitness coaches')
    assert p.terms == 'fitness coaches'
    assert p.platforms == DEFAULT_PLATFORMS
    assert p.location == '' and p.min_followers is None


def test_multiple_platforms_and_aliases():
    assert parse_query('chefs on ig and tiktok').platforms == ['instagram', 'tiktok']


@pytest.mark.parametrize('text,lo,hi', [
    ('barbers with 10k followers', 10000, None),
    ('barbers over 2.5k followers', 2500, None),
    ('barbers under 50k followers', None, 50000),
    ('barbers between 5k and 50k followers', 5000, 50000),
    ('barbers 5k-50k followers', 5000, 50000),
    ('barbers at least 1,200 followers', 1200, None),
    ('creators with 1m+ subscribers', 1_000_000, None),
])
def test_follower_ranges(text, lo, hi):
    p = parse_query(text)
    assert (p.min_followers, p.max_followers) == (lo, hi)
    assert p.terms == 'barbers' or p.terms == 'creators'


def test_multiword_location():
    p = parse_query('dentists in San Francisco with over 3k followers')
    assert p.location == 'San Francisco' and p.terms == 'dentists' and p.min_followers == 3000


def test_location_with_country_and_search_text():
    p = parse_query('photographers based in Berlin, Germany')
    assert p.location.startswith('Berlin')
    assert 'photographers' in p.search_text() and 'Berlin' in p.search_text()


def test_empty():
    p = parse_query('')
    assert p.terms == '' and p.platforms == DEFAULT_PLATFORMS

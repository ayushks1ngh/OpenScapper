"""Pure-logic tests for LeadEnricher (no network)."""
import pytest

from app.scrapers.enrichment import LeadEnricher


@pytest.fixture
def e():
    return LeadEnricher()


@pytest.mark.parametrize('email,ok', [
    ('jane@acme.io', True),
    ('jane@example.com', False),
    ('x@sentry.io', False),
    ('logo@2x.png', False),
    ('hello@wixpress.com', False),
])
def test_is_valid_email(e, email, ok):
    assert e._is_valid_email(email) is ok


def test_extract_email_skips_blacklisted_and_takes_first_valid(e):
    r = e._extract_from_text('a@example.com b@acme.io c@other.io')
    assert r['email'] == 'b@acme.io'


def test_extract_empty(e):
    assert e._extract_from_text('') == {'email': None, 'phone': None}


@pytest.mark.parametrize('html,expected', [
    ('<a href="tel:+1 555-123-4567">call</a>', '+1 555-123-4567'),
    ('<a href="https://wa.me/15551234567">wa</a>', '+15551234567'),
    ('<p>Call (555) 123-4567 today</p>', '(555) 123-4567'),
    ('<script>var x="(555) 123-4567"</script><p>none</p>', None),
    ('<p>no numbers</p>', None),
])
def test_extract_phone(e, html, expected):
    assert e._extract_phone_from_text(html) == expected


@pytest.mark.parametrize('local,pattern', [
    ('jane.doe', 'first.last'),
    ('j.doe', 'f.last'),
    ('jane', 'first'),
    ('jd123', None),
])
def test_detect_pattern(e, local, pattern):
    assert e._detect_pattern(local) == pattern


def test_apply_pattern(e):
    assert e._apply_pattern('first.last', 'jane', 'doe', 'acme.io') == 'jane.doe@acme.io'
    assert e._apply_pattern('flast', 'jane', 'doe', 'acme.io') == 'jdoe@acme.io'
    assert e._apply_pattern('bogus', 'jane', 'doe', 'acme.io') is None


@pytest.mark.parametrize('site,domain', [
    ('https://www.acme.io/about', 'acme.io'),
    ('acme.io', 'acme.io'),
])
def test_extract_domain(e, site, domain):
    assert e._extract_domain(site) == domain


def test_lead_score_bounds_and_components(e):
    assert e._calculate_lead_score({}) == 0
    full = {'email': 'a@b.io', 'email_source': 'hunter.io', 'phone': '1', 'is_verified': True,
            'follower_count': 10000, 'website': 'b.io', 'bio': 'Founder'}
    assert e._calculate_lead_score(full) == 100  # capped
    assert e._calculate_lead_score({'email': 'a@b.io'}) == 30
    assert e._calculate_lead_score({'follower_count': 10}) == 5

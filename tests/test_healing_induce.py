import pytest

pytest.importorskip('scrapling')

from app.healing.induce import apply_selectors, induce  # noqa: E402

OLD = '''<html><body><div class="header"><h1 class="channel-title">Jane Doe</h1>
<span id="handle">janedoe</span></div>
<p class="about-text">I coach founders on pricing and sales.</p>
<div class="links"><a class="site-link" href="https://janedoe.com">my site</a></div></body></html>'''

# same data, site redesigned: different tags, classes and nesting
NEW_SAME_LAYOUT = OLD.replace('Jane Doe', 'John Roe').replace('janedoe', 'johnroe')\
    .replace('I coach founders on pricing and sales.', 'I run workshops for agencies today.')
LEAD = {'full_name': 'Jane Doe', 'username': 'janedoe',
        'bio': 'I coach founders on pricing and sales.', 'website': 'https://janedoe.com'}


def test_induce_finds_selectors_for_each_field():
    sel = induce(OLD, LEAD)
    assert set(sel) == {'full_name', 'username', 'bio', 'website'}
    assert sel['website']['attr'] == 'href'
    assert sel['username']['selector'].endswith('#handle')


def test_learned_selectors_replay_on_other_profiles_with_same_layout():
    sel = induce(OLD, LEAD)
    got = apply_selectors(NEW_SAME_LAYOUT, sel)
    assert got['full_name'] == 'John Roe'
    assert got['username'] == 'johnroe'
    assert got['bio'].startswith('I run workshops')
    assert got['website'] == 'https://johnroe.com'


def test_selectors_miss_after_redesign():
    sel = induce(OLD, LEAD)
    redesigned = '<html><body><section><h2>Jane Doe</h2></section></body></html>'
    assert apply_selectors(redesigned, sel) == {}


def test_missing_values_are_skipped():
    sel = induce(OLD, {'full_name': 'Nobody Here', 'username': ''})
    assert sel == {}


def test_invalid_selector_is_ignored():
    assert apply_selectors(OLD, {'x': {'selector': '[[bad', 'attr': ''}}) == {}

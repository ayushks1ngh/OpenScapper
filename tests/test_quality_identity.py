import pytest

from app.quality.identity import domain_of, match, norm_name, norm_phone, same_person


def L(**kw):
    return kw


def test_normalizers():
    assert norm_name('  José  García ') == 'josegarcia'
    assert norm_phone('+1 (555) 123-4567') == '5551234567'
    assert norm_phone('12345') == ''
    assert domain_of('https://www.janedoe.com/about') == 'janedoe.com'
    assert domain_of('https://instagram.com/jane') == ''   # socials say nothing about identity
    assert domain_of('') == ''


def test_shared_email_merges():
    a = L(platform='instagram', username='jane', email='jane@acme.io')
    b = L(platform='youtube', username='janedoe_yt', email='JANE@acme.io')
    p, why = match(a, b)
    assert p >= 0.8 and any('email' in w for w in why)


def test_generic_email_alone_is_not_enough():
    a = L(email='info@acme.io', platform='instagram', username='acmestudio')
    b = L(email='info@acme.io', platform='tiktok', username='someoneelse')
    assert not same_person(a, b)


def test_shared_phone_merges():
    assert same_person(L(phone='+1 555-123-4567'), L(phone='(555) 123 4567'))


def test_profile_link_between_leads_merges():
    a = L(platform='instagram', username='janedoe', links=['https://www.youtube.com/@JaneDoeStudio'])
    b = L(platform='youtube', username='JaneDoeStudio')
    p, why = match(a, b)
    assert p >= 0.9 and 'links' in why[0]


def test_same_username_and_name_merge_but_neither_alone():
    a = L(platform='instagram', username='janedoe', full_name='Jane Doe')
    b = L(platform='tiktok', username='jane.doe', full_name='Jane Doe')
    assert same_person(a, b)
    assert not same_person(L(username='janedoe', full_name='X Y'), L(username='janedoe', full_name='P Q'))
    assert not same_person(L(username='a1', full_name='Jane Doe'), L(username='b2', full_name='Jane Doe'))


def test_same_website_plus_username_merge_website_alone_does_not():
    a = L(website='https://janedoe.com', username='janedoe')
    assert same_person(a, L(website='http://www.janedoe.com/x', username='janedoe'))
    assert not same_person(L(website='https://janedoe.com'), L(website='https://janedoe.com/'))


def test_strangers_with_short_common_usernames_do_not_merge():
    assert not same_person(L(username='john', full_name='John'), L(username='john', full_name='John'))


def test_empty_leads():
    assert match({}, {}) == (0.0, [])


@pytest.mark.parametrize('a,b', [
    (L(website='https://linktr.ee/jane'), L(website='https://linktr.ee/jane')),
    (L(website='https://gmail.com'), L(website='https://gmail.com')),
])
def test_aggregator_domains_ignored(a, b):
    assert match(a, b)[0] == 0.0

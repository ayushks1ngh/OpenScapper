import json

from app.healing.generic import extract
from app.healing.schema import is_valid

LD = {'@context': 'https://schema.org', '@type': 'Person', 'name': 'Jane Doe',
      'alternateName': '@janedoe', 'description': 'Coach', 'email': 'JANE@acme.io',
      'url': 'https://janedoe.com', 'sameAs': ['https://x.com/jane', 'https://t.co/j'],
      'interactionStatistic': {'@type': 'InteractionCounter',
                               'interactionType': 'https://schema.org/FollowAction',
                               'userInteractionCount': 4200}}


def page_with_ld(data):
    return f'<html><head><script type="application/ld+json">{json.dumps(data)}</script></head></html>'


def test_json_ld_person():
    lead = extract(page_with_ld(LD), 'youtube', 'https://youtube.com/@janedoe')
    assert lead['full_name'] == 'Jane Doe'
    assert lead['username'] == 'janedoe'
    assert lead['email'] == 'jane@acme.io'
    assert lead['follower_count'] == 4200
    assert lead['website'] == 'https://janedoe.com'
    assert lead['links'] == ['https://x.com/jane', 'https://t.co/j']
    assert is_valid(lead)


def test_json_ld_nested_in_graph():
    lead = extract(page_with_ld({'@graph': [{'@type': 'WebSite'}, LD]}))
    assert lead['full_name'] == 'Jane Doe'


def test_bad_json_ld_falls_back_to_opengraph():
    page = ('<script type="application/ld+json">{oops</script>'
            '<meta property="og:title" content="Jane Doe | TikTok">'
            "<meta property='og:description' content='Hi &amp; welcome'>"
            '<meta property="og:url" content="https://tiktok.com/@jane">')
    lead = extract(page, 'tiktok')
    assert lead['full_name'] == 'Jane Doe'
    assert lead['bio'] == 'Hi & welcome'
    assert lead['profile_url'] == 'https://tiktok.com/@jane'
    assert is_valid(lead)


def test_attribute_order_and_plain_description_meta():
    lead = extract('<meta content="Plain bio" name="description"><meta content="N" property="og:title">')
    assert lead['bio'] == 'Plain bio' and lead['full_name'] == 'N'


def test_empty_and_unstructured_pages_are_invalid():
    assert not is_valid(extract(''))
    assert not is_valid(extract('<html><body>hello</body></html>'))

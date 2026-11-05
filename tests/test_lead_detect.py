import pytest

from app.lead.detect import detect


@pytest.mark.parametrize('url,platform,ident', [
    ('https://www.instagram.com/janedoe/', 'instagram', 'janedoe'),
    ('instagram.com/jane.doe', 'instagram', 'jane.doe'),
    ('https://www.tiktok.com/@jane_doe?lang=en', 'tiktok', 'jane_doe'),
    ('https://www.linkedin.com/in/jane-doe-123/', 'linkedin', 'jane-doe-123'),
    ('https://github.com/janedoe', 'github', 'janedoe'),
    ('https://www.youtube.com/@JaneDoe', 'youtube', '@JaneDoe'),
    ('https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv', 'youtube', 'UCabcdefghijklmnopqrstuv'),
    ('https://www.youtube.com/c/JaneDoe', 'youtube', 'JaneDoe'),
    ('https://www.twitch.tv/janedoe', 'twitch', 'janedoe'),
    ('https://linktr.ee/janedoe', 'linktree', 'janedoe'),
    ('https://www.pinterest.com/janedoe/', 'pinterest', 'janedoe'),
    ('https://www.pinterest.co.uk/janedoe/', 'pinterest', 'janedoe'),
])
def test_profile_urls(url, platform, ident):
    d = detect(url)
    assert d and d.platform == platform and d.identifier == ident


@pytest.mark.parametrize('url', [
    'https://www.instagram.com/p/Cabc123/',
    'https://www.instagram.com/explore/',
    'https://github.com/janedoe/repo',
    'https://github.com/orgs',
    'https://example.com/janedoe',
    'https://notinstagram.com/janedoe',
    'https://www.youtube.com/watch?v=abc',
    '', 'not a url at all',
])
def test_non_profiles(url):
    assert detect(url) is None

from app.quality.merge import cluster, dedupe, merge


def ig():
    return {'platform': 'instagram', 'username': 'janedoe', 'full_name': 'Jane Doe', 'follower_count': 8000,
            'bio': 'Coach', 'profile_url': 'https://instagram.com/janedoe', 'email': '',
            'links': ['https://janedoe.com'], 'website': 'https://janedoe.com'}


def yt():
    return {'platform': 'youtube', 'username': 'janedoe', 'full_name': 'Jane Doe', 'follower_count': 30000,
            'bio': 'Coach for founders, weekly videos on pricing', 'email': 'jane@janedoe.com',
            'email_verified': True, 'phone': '555-123-4567', 'links': ['https://janedoe.com', 'https://x.com/j'],
            'profile_url': 'https://youtube.com/@janedoe'}


def other():
    return {'platform': 'tiktok', 'username': 'bobsbarbers', 'full_name': 'Bob Smith', 'follower_count': 500}


def test_cluster_groups_same_person_only():
    assert cluster([ig(), other(), yt()]) == [[0, 2], [1]]


def test_merge_keeps_biggest_audience_as_primary_and_fills_gaps():
    m = merge([ig(), yt()])
    assert m['platform'] == 'youtube' and m['follower_count'] == 30000 and m['total_reach'] == 38000
    assert m['email'] == 'jane@janedoe.com' and m['email_verified'] is True
    assert m['phone'] == '555-123-4567'
    assert m['bio'].startswith('Coach for founders')
    assert m['links'] == ['https://janedoe.com', 'https://x.com/j']
    assert m['platforms'] == ['instagram', 'youtube']
    assert {s['platform'] for s in m['sources']} == {'instagram', 'youtube'}


def test_merge_prefers_verified_email_over_primary_unverified():
    a, b = yt(), ig()
    a['email'], a['email_verified'] = 'guess@janedoe.com', False
    b['email'], b['email_verified'] = 'real@janedoe.com', True
    assert merge([a, b])['email'] == 'real@janedoe.com'


def test_dedupe_counts_and_singletons():
    out = dedupe([ig(), other(), yt(), ig()])  # exact duplicate ig too
    assert len(out) == 2
    single = next(l for l in out if l['username'] == 'bobsbarbers')
    assert single['platforms'] == ['tiktok'] and single['total_reach'] == 500
    merged = next(l for l in out if l['username'] == 'janedoe')
    assert len(merged['sources']) == 3


def test_transitive_clustering():
    a = {'platform': 'instagram', 'username': 'janedoe', 'email': 'j@x.io'}
    b = {'platform': 'tiktok', 'username': 'other_handle', 'email': 'j@x.io', 'phone': '555 123 4567'}
    c = {'platform': 'youtube', 'username': 'third_handle', 'phone': '(555) 123-4567'}
    assert cluster([a, b, c]) == [[0, 1, 2]]


def test_empty():
    assert dedupe([]) == []

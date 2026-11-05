from app.healing.schema import is_valid, normalize


def test_normalize_cleans_values():
    n = normalize({'username': '@jane', 'full_name': ' Jane ', 'email': 'JANE@Acme.IO',
                   'follower_count': '12,400', 'bio': 'null', 'links': ['a.io', 'a.io', None],
                   'junk': 1}, platform='youtube')
    assert n['username'] == 'jane'
    assert n['full_name'] == 'Jane'
    assert n['email'] == 'jane@acme.io'
    assert n['follower_count'] == 12400
    assert n['bio'] == ''
    assert n['links'] == ['a.io']
    assert n['website'] == 'a.io'
    assert n['platform'] == 'youtube'
    assert 'junk' not in n


def test_normalize_handles_none_and_bad_numbers():
    assert normalize(None)['follower_count'] == 0
    assert normalize({'follower_count': True})['follower_count'] == 0
    assert normalize({'follower_count': -5})['follower_count'] == 0


def test_is_valid():
    assert is_valid(normalize({'username': 'jane'}))
    assert is_valid(normalize({'full_name': 'Jane Doe'}))
    assert not is_valid(None)
    assert not is_valid(normalize({}))
    assert not is_valid(normalize({'username': 'j', 'email': 'not-an-email'}))
    assert not is_valid({'username': 'j', 'follower_count': -1})

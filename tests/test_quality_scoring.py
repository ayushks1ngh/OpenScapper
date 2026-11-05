from app.quality.scoring import apply, explain, score


def test_empty_lead_scores_zero_with_reasons():
    total, items = score({})
    assert total == 0
    assert all(p == 0 for _, p, _ in items)
    assert apply({})['score_explain'] == 'no positive signals'


def test_verified_email_beats_found_beats_guessed():
    v = score({'email': 'jane@acme.io', 'email_verified': True})[0]
    f = score({'email': 'jane@acme.io'})[0]
    g = score({'email': 'jane@acme.io', 'email_source': 'smtp_guess'})[0]
    assert v > f > g > 0


def test_generic_inbox_is_worth_less():
    assert score({'email': 'info@acme.io', 'email_verified': True})[0] < \
        score({'email': 'jane@acme.io', 'email_verified': True})[0]


def test_audience_sweet_spot():
    assert score({'follower_count': 10_000})[0] == 15
    assert score({'follower_count': 2_000})[0] == 10
    assert score({'follower_count': 500_000})[0] == 5
    assert score({'follower_count': 50})[0] == 4
    assert score({'follower_count': 0})[0] == 0


def test_cross_platform_presence_is_rewarded_and_capped():
    assert score({'platforms': ['instagram']})[0] == 0
    assert score({'platforms': ['instagram', 'youtube']})[0] == 5
    assert score({'platforms': list('abcdefgh')})[0] == 15


def test_business_signal_from_bio():
    def signal(bio):
        return next(p for label, p, _ in score({'bio': bio})[1] if label == 'Business signal')
    assert signal('Founder') == 5
    assert 5 < signal('Founder and agency owner, DM for bookings') <= 10
    assert signal('I love dogs') == 0


def test_total_capped_at_100_and_explanation_lists_only_points():
    lead = {'email': 'jane@acme.io', 'email_verified': True, 'phone': '555', 'follower_count': 10_000,
            'platforms': list('abcdefgh'), 'full_name': 'J', 'bio': 'Founder agency owner coach studio',
            'website': 'x.io', 'is_verified': True}
    total, items = score(lead)
    assert total == 100
    text = explain(items)
    assert 'Email +30 (verified inbox)' in text and 'Phone +15' in text
    assert 'no phone' not in text


def test_apply_does_not_mutate_input():
    lead = {'email': 'a@b.io'}
    out = apply(lead)
    assert 'quality_score' in out and 'quality_score' not in lead

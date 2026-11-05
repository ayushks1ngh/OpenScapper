from app.healing.report import summarize


def row(platform, tier, runs, ok):
    return {'platform': platform, 'tier': tier, 'runs': runs, 'ok': ok}


def test_healthy_platform():
    s = summarize([row('youtube', 'primary', 10, 10)])[0]
    assert s['status'] == 'healthy' and s['primary_rate'] == 100 and s['healed'] == 0


def test_healing_platform_when_primary_mostly_fails():
    s = summarize([row('tiktok', 'primary', 10, 2), row('tiktok', 'generic', 8, 6),
                   row('tiktok', 'llm', 2, 2)])[0]
    assert s['status'] == 'healing'
    assert s['served'] == 10 and s['healed'] == 8 and s['primary_rate'] == 20


def test_broken_platform_and_sorting():
    out = summarize([row('youtube', 'primary', 5, 5),
                     row('instagram', 'primary', 5, 0), row('instagram', 'none', 5, 0)])
    assert [r['platform'] for r in out] == ['instagram', 'youtube']
    assert out[0]['status'] == 'broken' and out[0]['failed'] == 5


def test_empty():
    assert summarize([]) == []

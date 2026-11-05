from urllib.parse import quote

from app.prospect.discover import build_query, discover, parse_results, search
from app.prospect.query import SearchPlan
from app.scrapers.fetch import FetchResult


def ddg(*urls):
    links = ''.join(f'<a class="result__a" href="//duckduckgo.com/l/?uddg={quote(u, safe="")}&amp;rut=abc">x</a>'
                    for u in urls)
    return f'<html><body>{links}<a href="/html/?q=next">more</a>' + 'x' * 300 + '</body></html>'


def fake_fetcher(html, calls=None):
    def f(url, **kw):
        if calls is not None:
            calls.append(url)
        return FetchResult(url=url, status=200, text=html, engine='http')
    return f


def test_parse_results_unwraps_and_dedupes():
    html = ddg('https://www.instagram.com/janedoe/', 'https://www.instagram.com/janedoe/',
               'https://example.com/a?b=1')
    assert parse_results(html) == ['https://www.instagram.com/janedoe/', 'https://example.com/a?b=1']


def test_parse_results_ignores_internal_links_and_empty():
    assert parse_results('<a href="/html/?q=x">n</a>') == []
    assert parse_results('') == []


def test_build_query():
    plan = SearchPlan(terms='yoga studio owners', location='Austin')
    assert build_query(plan, 'instagram') == 'site:instagram.com yoga studio owners Austin'
    assert build_query(plan, 'tiktok').startswith('site:tiktok.com/@')


def test_search_stops_on_blocked_page():
    f = lambda url, **kw: FetchResult(url=url, status=403, text='', engine='http')  # noqa: E731
    assert search('x', pages=3, fetcher=f) == []


def test_search_paginates():
    calls = []
    search('yoga austin', pages=2, fetcher=fake_fetcher(ddg('https://a.com/1'), calls))
    assert len(calls) == 2 and 's=0' in calls[0] and 's=30' in calls[1]
    assert 'yoga+austin' in calls[0]


def test_discover_keeps_only_profiles_of_the_requested_platform():
    html = ddg('https://www.instagram.com/janedoe/', 'https://www.instagram.com/p/Cabc/',
               'https://www.instagram.com/JANEDOE', 'https://www.instagram.com/bob/',
               'https://www.tiktok.com/@jane', 'https://blog.example.com/best-yoga')
    plan = SearchPlan(terms='yoga', platforms=['instagram'])
    out = discover(plan, per_platform=10, fetcher=fake_fetcher(html))
    assert [d.identifier for d in out['instagram']] == ['janedoe', 'bob']


def test_discover_respects_limit_per_platform():
    html = ddg(*[f'https://www.instagram.com/user{i}/' for i in range(10)])
    out = discover(SearchPlan(platforms=['instagram']), per_platform=3, fetcher=fake_fetcher(html))
    assert len(out['instagram']) == 3

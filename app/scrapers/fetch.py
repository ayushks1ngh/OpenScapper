"""
Unified fetch engine.

One entry point, `fetch(url)`, that escalates through tiers until a page comes
back clean:

    http     Scrapling Fetcher      fast, impersonates a real browser's TLS/headers
    stealth  Scrapling StealthyFetcher   real browser, anti-bot/Cloudflare handling
    browser  plain Playwright       fallback when the stealth browser can't launch

Choose with OPENSCRAPPER_ENGINE (legacy SCOUT_ENGINE also works) (or the `mode=` argument):
    auto (default) | http | stealth | browser | legacy

`legacy` uses plain httpx (the old behaviour). Tiers that fail to start are
disabled for the rest of the session so one broken browser doesn't slow every
request. Every result exposes `.page`, a Scrapling Selector, for CSS/XPath.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from urllib.parse import urlparse

from app import ratelimit
from app.config import env, number
from app.scrapers.stealth import get_httpx_proxy, random_user_agent

logger = logging.getLogger(__name__)

TIERS = ('http', 'stealth', 'browser')
RETRY_STATUSES = {429, 500, 502, 503, 504}
_disabled = set()

BLOCK_STATUSES = {401, 403, 429, 503}
BLOCK_MARKERS = (
    'just a moment', 'attention required', 'cf-chl', 'challenge-platform',
    'verify you are human', 'captcha', 'access denied', 'unusual traffic',
)


@dataclass
class FetchResult:
    url: str
    status: int
    text: str
    engine: str

    @property
    def status_code(self) -> int:  # requests-style alias
        return self.status

    @property
    def ok(self) -> bool:
        return self.status == 200 and bool(self.text)

    @property
    def page(self):
        """Scrapling Selector over the HTML (css/xpath/get_all_text...)."""
        from scrapling import Selector
        return Selector(self.text, url=self.url)


def _looks_blocked(status: int, text: str) -> bool:
    if status in BLOCK_STATUSES:
        return True
    if not text or len(text) < 300:
        return status != 404
    head = text[:6000].lower()
    return any(m in head for m in BLOCK_MARKERS) and len(text) < 40000


def _quiet():
    # scrapling resets its logger on import, so silence it after importing
    logging.getLogger('scrapling').setLevel(logging.WARNING)


def _http(url, timeout, headers):
    from scrapling.fetchers import Fetcher
    _quiet()
    kw = dict(timeout=timeout, impersonate='chrome', stealthy_headers=True, follow_redirects=True)
    proxy = get_httpx_proxy()
    if proxy:
        kw['proxy'] = proxy
    if headers:
        kw['headers'] = headers
    p = Fetcher.get(url, **kw)
    return p.status, str(p.html_content)


def _stealth(url, timeout, headers):
    from scrapling.fetchers import StealthyFetcher
    _quiet()
    kw = dict(headless=True, network_idle=True, timeout=timeout * 1000)
    proxy = get_httpx_proxy()
    if proxy:
        kw['proxy'] = proxy
    p = StealthyFetcher.fetch(url, **kw)
    return p.status, str(p.html_content)


def _browser(url, timeout, headers):
    from playwright.sync_api import sync_playwright
    proxy = get_httpx_proxy()
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, proxy={'server': proxy} if proxy else None)
        try:
            ctx = b.new_context(user_agent=(headers or {}).get('User-Agent') or random_user_agent())
            pg = ctx.new_page()
            resp = pg.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
            try:
                pg.wait_for_load_state('networkidle', timeout=5000)
            except Exception:
                pass
            return (resp.status if resp else 0), pg.content()
        finally:
            b.close()


def _legacy(url, timeout, headers):
    import httpx
    h = {'User-Agent': random_user_agent()}
    h.update(headers or {})
    r = httpx.get(url, timeout=timeout, headers=h, follow_redirects=True, proxy=get_httpx_proxy())
    return r.status_code, r.text


_RUNNERS = {'http': _http, 'stealth': _stealth, 'browser': _browser, 'legacy': _legacy}


def engine_mode() -> str:
    mode = env('ENGINE', 'auto').strip().lower()
    return mode if mode in ('auto', *TIERS, 'legacy') else 'auto'


_throttle = ratelimit.HostThrottle()


def _run_tier(tier, url, timeout, headers):
    """One tier, politely: wait for the host, retry rate-limit/server errors with backoff."""
    _throttle.min_interval = number('HOST_DELAY', 0.3)
    retries = int(number('RETRIES', 2))
    host = urlparse(url).hostname or ''
    attempt = 0
    while True:
        _throttle.wait(host)
        status, text = _RUNNERS[tier](url, timeout, headers)
        if status not in RETRY_STATUSES or attempt >= retries:
            return status, text
        attempt += 1
        delay = ratelimit.backoff_delay(attempt)
        logger.debug(f"{tier} got HTTP {status} from {host}; retry {attempt}/{retries} in {delay:.1f}s")
        ratelimit.sleep(delay)


def fetch(url: str, mode: Optional[str] = None, timeout: int = 20,
          headers: Optional[dict] = None, min_tier: Optional[str] = None) -> Optional[FetchResult]:
    """Fetch `url`, escalating tiers in auto mode. Returns None if nothing worked.

    A 404 is returned as-is (not escalated) so callers can treat it as "not found".
    `min_tier` skips cheaper tiers, for sites known to need a browser.
    """
    if not url.startswith('http'):
        url = 'https://' + url
    mode = (mode or engine_mode()).lower()

    if mode == 'auto':
        ladder = list(TIERS)
        if min_tier in TIERS:
            ladder = ladder[ladder.index(min_tier):]
    else:
        ladder = [mode]

    last = None
    for tier in ladder:
        if tier in _disabled:
            continue
        try:
            status, text = _run_tier(tier, url, timeout, headers)
        except ImportError as e:
            logger.debug(f"{tier} tier unavailable ({e}); disabling")
            _disabled.add(tier)
            continue
        except Exception as e:
            logger.debug(f"{tier} tier failed for {url}: {str(e).splitlines()[0][:120]}")
            if tier in ('stealth', 'browser') and 'launch' in str(e).lower():
                _disabled.add(tier)
            continue

        result = FetchResult(url=url, status=status, text=text or '', engine=tier)
        last = result
        if status == 404 or not _looks_blocked(status, text):
            return result
        logger.debug(f"{tier} tier blocked on {url} (HTTP {status}); escalating")

    return last


def get(url: str, headers: Optional[dict] = None, cookies: Optional[dict] = None,
        timeout: int = 20, **kw) -> FetchResult:
    """Drop-in for requests.get on HTML pages: raises RequestException if every tier fails."""
    import requests
    h = dict(headers or {})
    if cookies:
        h['Cookie'] = '; '.join(f'{k}={v}' for k, v in cookies.items())
    res = fetch(url, headers=h, timeout=timeout, **kw)
    if res is None:
        raise requests.exceptions.ConnectionError(f'all fetch tiers failed for {url}')
    return res

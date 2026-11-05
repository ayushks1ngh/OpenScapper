"""Recognise which platform a URL belongs to and pull out the account identifier."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

_SEG = r'([A-Za-z0-9._-]+)'

# (platform, host regex, path regex whose group 1 is the identifier)
_RULES = [
    ('instagram', r'(^|\.)instagram\.com$', rf'^/{_SEG}/?$'),
    ('tiktok', r'(^|\.)tiktok\.com$', r'^/@([A-Za-z0-9._-]+)'),
    ('linkedin', r'(^|\.)linkedin\.com$', rf'^/in/{_SEG}'),
    ('github', r'(^|\.)github\.com$', rf'^/{_SEG}/?$'),
    ('youtube', r'(^|\.)youtube\.com$', r'^/(@[A-Za-z0-9._-]+|channel/UC[\w-]{22}|(?:c|user)/[A-Za-z0-9._-]+)'),
    ('twitch', r'(^|\.)twitch\.tv$', rf'^/{_SEG}/?$'),
    ('linktree', r'(^|\.)linktr\.ee$', rf'^/{_SEG}/?$'),
    ('pinterest', r'(^|\.)pinterest\.[a-z.]+$', rf'^/{_SEG}/?$'),
]

# first path segments that are site features, not accounts
_RESERVED = {'p', 'reel', 'reels', 'explore', 'accounts', 'about', 'login', 'signup', 'directory',
             'topics', 'marketplace', 'orgs', 'features', 'pricing', 'settings', 'search', 'pin',
             'videos', 'directory', 'downloads', 'jobs', 'turbo', 'privacy', 'help', 'legal'}


@dataclass(frozen=True)
class Detected:
    platform: str
    identifier: str
    url: str


def detect(url: str) -> Optional[Detected]:
    """Return the platform/account for a profile URL, or None for any other page."""
    if not url:
        return None
    url = url.strip()
    if '://' not in url:
        url = 'https://' + url
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or '').lower()
    path = parsed.path or '/'
    for platform, host_re, path_re in _RULES:
        if not re.search(host_re, host):
            continue
        m = re.match(path_re, path)
        if not m:
            continue
        ident = m.group(1)
        if platform != 'tiktok' and platform != 'youtube' and ident.lower() in _RESERVED:
            continue
        if platform == 'youtube' and '/' in ident:
            ident = ident.split('/', 1)[1]  # channel/UC.. or c/name -> id/name
        return Detected(platform, ident, url)
    return None

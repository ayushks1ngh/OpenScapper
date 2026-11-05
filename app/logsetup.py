"""Logging: quiet console, persistent rotating log file (optionally JSON lines), secrets redacted."""

import json
import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from app import config

_OURS = '_openscrapper_handler'
_REDACTIONS = [
    (re.compile(r'(://)[^/@\s:]+:[^/@\s]+@'), r'\1***@'),                       # proxy / url credentials
    (re.compile(r'(li_at=)[^;\s]+', re.I), r'\1***'),                           # LinkedIn cookie
    (re.compile(r'((?:api[_-]?key|token|password|secret)["\']?\s*[:=]\s*["\']?)[^\s"\',&]+', re.I), r'\1***'),
]
_NOISY = ('httpx', 'httpcore', 'urllib3', 'scrapling', 'playwright', 'asyncio')


def redact(text: str) -> str:
    for pattern, repl in _REDACTIONS:
        text = pattern.sub(repl, text)
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {'ts': self.formatTime(record, '%Y-%m-%dT%H:%M:%S'), 'level': record.levelname,
               'logger': record.name, 'msg': record.getMessage()}
        if record.exc_info:
            out['exc'] = redact(self.formatException(record.exc_info))
        return json.dumps(out, ensure_ascii=False)


def log_path() -> Path:
    d = config.home() / 'logs'
    d.mkdir(parents=True, exist_ok=True)
    return d / 'openscrapper.log'


def setup_logging(verbose: bool = False, log_file: Optional[Path] = None,
                  json_lines: Optional[bool] = None) -> Optional[Path]:
    """Configure the root logger. Safe to call repeatedly. Returns the log file path, or None if unavailable."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, _OURS, False):
            root.removeHandler(h)
            h.close()

    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for name in _NOISY:
        logging.getLogger(name).setLevel(logging.WARNING)

    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter('%(name)s: %(message)s'))
    console.addFilter(RedactingFilter())
    setattr(console, _OURS, True)
    root.addHandler(console)

    path = None
    try:
        path = Path(log_file) if log_file else log_path()
        fh = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding='utf-8')
        use_json = config.flag('LOG_JSON') if json_lines is None else json_lines
        fh.setFormatter(JsonFormatter() if use_json else
                        logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        fh.setLevel(logging.DEBUG if verbose else logging.INFO)
        fh.addFilter(RedactingFilter())
        setattr(fh, _OURS, True)
        root.addHandler(fh)
    except OSError:
        path = None  # read-only home etc.: console logging still works
    return path

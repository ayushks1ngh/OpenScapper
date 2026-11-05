"""SQLite store for learned selectors and per-run tier stats."""

import sqlite3
import threading
import time
from typing import Dict, List, Optional

from app.config import home


_SCHEMA = """
CREATE TABLE IF NOT EXISTS selectors (
    platform TEXT NOT NULL,
    field    TEXT NOT NULL,
    selector TEXT NOT NULL,
    attr     TEXT NOT NULL DEFAULT '',
    hits     INTEGER NOT NULL DEFAULT 0,
    misses   INTEGER NOT NULL DEFAULT 0,
    updated  REAL NOT NULL,
    PRIMARY KEY (platform, field)
);
CREATE TABLE IF NOT EXISTS runs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    platform TEXT NOT NULL,
    tier     TEXT NOT NULL,
    ok       INTEGER NOT NULL,
    ts       REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS runs_platform_ts ON runs (platform, ts);
"""

# A learned selector that keeps missing is dropped so a fresh one can be learned.
MAX_MISSES = 3


class Cache:
    def __init__(self, path: Optional[str] = None):
        self.path = str(path or home() / 'healing.db')
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.executescript(_SCHEMA)

    def close(self):
        self._db.close()

    # selectors -------------------------------------------------------------
    def save_selector(self, platform: str, field: str, selector: str, attr: str = ''):
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO selectors (platform, field, selector, attr, updated) VALUES (?,?,?,?,?) "
                "ON CONFLICT(platform, field) DO UPDATE SET selector=excluded.selector, "
                "attr=excluded.attr, hits=0, misses=0, updated=excluded.updated",
                (platform, field, selector, attr, time.time()))

    def selectors(self, platform: str) -> Dict[str, Dict[str, str]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT field, selector, attr FROM selectors WHERE platform=?", (platform,)).fetchall()
        return {f: {'selector': s, 'attr': a} for f, s, a in rows}

    def record_selector_result(self, platform: str, field: str, hit: bool):
        col = 'hits' if hit else 'misses'
        with self._lock, self._db:
            self._db.execute(
                f"UPDATE selectors SET {col}={col}+1 WHERE platform=? AND field=?", (platform, field))
            self._db.execute(
                "DELETE FROM selectors WHERE platform=? AND field=? AND misses>=?",
                (platform, field, MAX_MISSES))

    # run stats -------------------------------------------------------------
    def record_run(self, platform: str, tier: str, ok: bool):
        with self._lock, self._db:
            self._db.execute("INSERT INTO runs (platform, tier, ok, ts) VALUES (?,?,?,?)",
                             (platform, tier, int(ok), time.time()))

    def stats(self, since_seconds: float = 7 * 86400) -> List[Dict]:
        """Per platform+tier: attempts and successes within the window."""
        cutoff = time.time() - since_seconds
        with self._lock:
            rows = self._db.execute(
                "SELECT platform, tier, COUNT(*), SUM(ok) FROM runs WHERE ts>=? "
                "GROUP BY platform, tier ORDER BY platform, tier", (cutoff,)).fetchall()
        return [{'platform': p, 'tier': t, 'runs': n, 'ok': int(o or 0)} for p, t, n, o in rows]

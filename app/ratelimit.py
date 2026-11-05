"""Per-host politeness: a minimum gap between requests to one host, and jittered exponential backoff."""

import random
import threading
import time
from typing import Callable, Dict

sleep: Callable[[float], None] = time.sleep  # swapped out in tests
_clock: Callable[[], float] = time.monotonic


class HostThrottle:
    """Allows one request per `min_interval` seconds per host, across threads."""

    def __init__(self, min_interval: float = 0.0):
        self.min_interval = min_interval
        self._next: Dict[str, float] = {}
        self._lock = threading.Lock()

    def wait(self, host: str) -> float:
        """Block until `host` may be hit again. Returns the time slept."""
        if self.min_interval <= 0 or not host:
            return 0.0
        with self._lock:
            now = _clock()
            ready = max(self._next.get(host, 0.0), now)
            self._next[host] = ready + self.min_interval
            delay = ready - now
        if delay > 0:
            sleep(delay)
        return max(delay, 0.0)


def backoff_delay(attempt: int, base: float = 1.0, cap: float = 30.0, jitter: float = 0.25) -> float:
    """Delay before retry number `attempt` (1-based): base * 2^(attempt-1), capped, +/- jitter."""
    raw = min(cap, base * (2 ** (attempt - 1)))
    return max(0.0, raw * (1 + random.uniform(-jitter, jitter)))

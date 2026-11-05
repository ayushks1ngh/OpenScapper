import pytest

from app import ratelimit


@pytest.fixture(autouse=True)
def fast_network_politeness(monkeypatch):
    """Tests never sleep: no host throttle, and backoff sleeps are recorded instead of waited."""
    monkeypatch.setenv('OPENSCRAPPER_HOST_DELAY', '0')
    slept = []
    monkeypatch.setattr(ratelimit, 'sleep', slept.append)
    return slept

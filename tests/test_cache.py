import time
from backend.services.cache import TTLCache


def test_cache_miss_returns_none():
    cache = TTLCache()
    assert cache.get("missing") is None


def test_cache_hit_returns_value():
    cache = TTLCache()
    cache.set("k", {"cpu": 42}, ttl=10)
    assert cache.get("k") == {"cpu": 42}


def test_cache_expires_after_ttl(monkeypatch):
    cache = TTLCache()
    fake_time = [100.0]
    monkeypatch.setattr("backend.services.cache.time.monotonic", lambda: fake_time[0])
    cache.set("k", "value", ttl=5)
    assert cache.get("k") == "value"
    fake_time[0] = 106.0
    assert cache.get("k") is None


def test_cache_evicts_expired_on_get():
    cache = TTLCache()
    cache.set("k", "v", ttl=0.01)
    time.sleep(0.02)
    assert cache.get("k") is None
    assert "k" not in cache._store

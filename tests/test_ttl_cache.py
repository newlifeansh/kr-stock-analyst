from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import time

from app.services.ttl_cache import TTLCache


def test_ttl_cache_get_or_set_deduplicates_concurrent_misses():
    cache = TTLCache()
    barrier = Barrier(8)
    calls = 0
    calls_lock = Lock()

    def factory():
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.05)
        return {"value": calls}

    def worker():
        barrier.wait()
        return cache.get_or_set("hot-key", 60, factory)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: worker(), range(8)))

    assert calls == 1
    assert all(result == {"value": 1} for result in results)
    assert cache.get("hot-key") == {"value": 1}

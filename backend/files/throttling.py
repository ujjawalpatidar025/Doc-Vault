import math
import time

from django.conf import settings
from django.core.cache import cache
from rest_framework.throttling import BaseThrottle


def _now():
    """Indirection so tests can control the clock without patching time.time globally."""
    return time.time()


class UserCallRateThrottle(BaseThrottle):
    """
    Per-user API call limit: at most RATE_LIMIT_CALLS calls per
    RATE_LIMIT_WINDOW_SECONDS (default 2 calls per second).

    Uses a sliding-window counter: two integer counters per user (the current and
    the previous fixed window), with the previous one weighted by how much of it
    still overlaps the sliding window. That avoids the 2x burst a plain fixed window
    allows at window boundaries, at O(1) memory and two atomic cache ops per call.

    Counters live in Django's cache. The default LocMemCache is per process, which
    is correct for the single gunicorn worker this project runs. With several
    workers or hosts, point CACHES at Redis so all of them share one counter.
    """

    cache = cache
    key_prefix = 'ratelimit'

    def __init__(self):
        self._wait = None

    def allow_request(self, request, view):
        user_id = getattr(request.user, 'user_id', None)
        if user_id is None:
            return True

        limit = settings.RATE_LIMIT_CALLS
        window = settings.RATE_LIMIT_WINDOW_SECONDS
        now = _now()
        current_window = math.floor(now / window)
        elapsed_fraction = (now - current_window * window) / window

        current_key = f'{self.key_prefix}:{user_id}:{current_window}'
        previous_key = f'{self.key_prefix}:{user_id}:{current_window - 1}'

        # add() is a no-op if the key exists; incr() is atomic in LocMem/Redis/Memcached.
        self.cache.add(current_key, 0, timeout=window * 2 + 1)
        try:
            current_count = self.cache.incr(current_key)
        except ValueError:  # key expired between add() and incr()
            self.cache.set(current_key, 1, timeout=window * 2 + 1)
            current_count = 1
        previous_count = self.cache.get(previous_key, 0)

        estimated = previous_count * (1 - elapsed_fraction) + current_count
        if estimated > limit:
            # Rejected calls should not use up the allowance.
            try:
                self.cache.decr(current_key)
            except ValueError:
                pass
            self._wait = max(window * (1 - elapsed_fraction), 0.0)
            return False
        return True

    def wait(self):
        return self._wait

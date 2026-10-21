"""Small in-process sliding-window rate limiter.

Per-process only: with several workers/instances each keeps its own counts. Put a shared limiter
(e.g. Redis) or your host's edge rate limiting in front if you scale out.
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from typing import Callable, Sequence, Tuple


class RateLimiter:
    def __init__(self, rules: Sequence[Tuple[int, float]], clock: Callable[[], float] = time.monotonic):
        self.rules, self.clock = list(rules), clock
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str) -> Tuple[bool, int]:
        """Record an attempt. Returns (allowed, retry_after_seconds)."""
        now, horizon = self.clock(), max(w for _, w in self.rules)
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > horizon:
                q.popleft()
            retry = 0.0
            for limit, window in self.rules:
                recent = [t for t in q if now - t <= window]
                if len(recent) >= limit:
                    retry = max(retry, recent[0] + window - now)
            if retry > 0:
                return False, max(1, math.ceil(retry))
            q.append(now)
            if len(self._hits) > 10_000:  # opportunistic cleanup of idle keys
                for k in [k for k, v in self._hits.items() if not v or now - v[-1] > horizon]:
                    del self._hits[k]
            return True, 0

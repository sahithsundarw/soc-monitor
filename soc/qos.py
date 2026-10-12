"""Token bucket traffic policing per sensor.

Concept: QoS rate limiting with a token bucket (Forouzan Ch. 24). Tokens drip into a
bucket at a fixed rate up to its size; each frame spends one token. Short bursts
are allowed while tokens remain, but a sender that keeps exceeding the rate finds
the bucket empty and its excess frames are dropped.
"""

import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from typing import Any

logger = logging.getLogger("soc.qos")

TIMELINE_SECONDS = 60

FloodCallback = Callable[[str, int], None]


class TokenBucket:
    """One bucket: ``rate`` tokens per second, holding at most ``size`` tokens."""

    def __init__(self, rate: float, size: int, now: float) -> None:
        """Start with a full bucket."""
        self.rate = rate
        self.size = size
        self.tokens = float(size)
        self._last = now

    def allow(self, now: float) -> bool:
        """Refill for the time that passed, then spend a token if there is one."""
        elapsed = max(0.0, now - self._last)
        self.tokens = min(self.size, self.tokens + elapsed * self.rate)
        self._last = now
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


class TrafficPolicer:
    """Token buckets for every sensor, drop counters and a per-second timeline."""

    def __init__(
        self,
        qos_config: dict[str, Any],
        on_flood: FloodCallback,
        now: float | None = None,
    ) -> None:
        """Create the buckets from the ``qos`` section of config.json."""
        start = time.time() if now is None else now
        self._lock = threading.Lock()
        self._buckets = {
            sensor: TokenBucket(entry["rate"], entry["bucket_size"], start)
            for sensor, entry in qos_config["buckets"].items()
        }
        self._flood_threshold = qos_config["flood_drops_threshold"]
        self._flood_window_s = qos_config["flood_window_s"]
        self._on_flood = on_flood
        self._drop_times: dict[str, deque[float]] = defaultdict(deque)
        self._totals = {
            sensor: {"allowed": 0, "dropped": 0} for sensor in self._buckets
        }
        self._timeline: dict[int, dict[str, int]] = {}

    def allow(self, sensor: str, now: float | None = None) -> bool:
        """Police one frame from ``sensor``; False means it is dropped."""
        now = time.time() if now is None else now
        bucket = self._buckets.get(sensor)
        if bucket is None:
            # Fail closed: a sender with no configured bucket could otherwise
            # bypass rate limiting just by putting a new id in its header.
            logger.info("Token bucket dropped a frame from unknown sender %s", sensor)
            return False
        with self._lock:
            allowed = bucket.allow(now)
            outcome = "allowed" if allowed else "dropped"
            self._totals[sensor][outcome] += 1
            second = self._timeline.setdefault(int(now), {"allowed": 0, "dropped": 0})
            second[outcome] += 1
            self._forget_old_seconds(int(now))
            drops = 0 if allowed else self._count_drop(sensor, now)
        if drops >= self._flood_threshold:
            self._on_flood(sensor, drops)
        return allowed

    def _count_drop(self, sensor: str, now: float) -> int:
        """Record a drop and return how many drops fall inside the flood window."""
        times = self._drop_times[sensor]
        times.append(now)
        while times and times[0] < now - self._flood_window_s:
            times.popleft()
        return len(times)

    def _forget_old_seconds(self, current: int) -> None:
        """Keep only the last TIMELINE_SECONDS seconds of the timeline."""
        for second in [s for s in self._timeline if s <= current - TIMELINE_SECONDS]:
            del self._timeline[second]

    def totals(self) -> dict[str, dict[str, int]]:
        """Allowed and dropped frames per sensor since start-up."""
        with self._lock:
            return {sensor: dict(values) for sensor, values in self._totals.items()}

    def timeline(self, now: float | None = None) -> list[dict[str, int]]:
        """Allowed vs dropped for each of the last 60 seconds (oldest first)."""
        current = int(time.time() if now is None else now)
        with self._lock:
            return [
                {
                    "t": second,
                    **self._timeline.get(second, {"allowed": 0, "dropped": 0}),
                }
                for second in range(current - TIMELINE_SECONDS + 1, current + 1)
            ]

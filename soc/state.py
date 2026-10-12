"""Thread-safe shared state that the collector writes and the dashboard reads.

Concept: shared monitoring counters. Many receive threads update the same numbers
at once, so every change happens under a lock; readers get copies.
"""

import threading
import time
from collections import deque
from typing import Any

FRAME_COUNTERS = ("good", "corrupted", "retransmitted", "lost")
UNKNOWN_SENDER = "unknown"
RECENT_EVENT_LIMIT = 50
TIMELINE_SECONDS = 60
TREND_SERIES = ("good", "corrupted", "retransmitted", "alerts", "firewall_blocks")


class PerSecondTimeline:
    """How many times each named thing happened in each of the last 60 seconds.

    Used for the dashboard's charts and sparklines: counts are grouped by whole
    second and seconds older than the window are forgotten.
    """

    def __init__(self, names: tuple[str, ...], seconds: int = TIMELINE_SECONDS) -> None:
        """Track the series in ``names`` over a window of ``seconds``."""
        self._names = names
        self._seconds = seconds
        self._lock = threading.Lock()
        self._buckets: dict[int, dict[str, int]] = {}

    def add(self, name: str, amount: int = 1, now: float | None = None) -> None:
        """Count ``amount`` occurrences of ``name`` in the current second."""
        current = int(time.time() if now is None else now)
        with self._lock:
            bucket = self._buckets.setdefault(current, dict.fromkeys(self._names, 0))
            bucket[name] += amount
            oldest_kept = current - self._seconds + 1
            for second in [s for s in self._buckets if s < oldest_kept]:
                del self._buckets[second]

    def window(self, now: float | None = None) -> list[dict[str, int]]:
        """One entry per second of the window, oldest first: {"t": ..., name: n}."""
        current = int(time.time() if now is None else now)
        empty = dict.fromkeys(self._names, 0)
        with self._lock:
            return [
                {"t": second, **self._buckets.get(second, empty)}
                for second in range(current - self._seconds + 1, current + 1)
            ]

    def series(self, name: str, now: float | None = None) -> list[int]:
        """Just the per-second values of one series, oldest first."""
        return [entry[name] for entry in self.window(now)]


class SocState:
    """Per-sensor frame counters split by UDP/TCP, plus the latest events."""

    def __init__(self, sensor_ids: list[str]) -> None:
        """Create zeroed counters for every sensor and for unreadable frames."""
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, dict[str, int]]] = {}
        for sender in [*sensor_ids, UNKNOWN_SENDER]:
            self._counts[sender] = self._empty_counts()
        self._events: deque[dict[str, Any]] = deque(maxlen=RECENT_EVENT_LIMIT)
        self.timeline = PerSecondTimeline(TREND_SERIES)

    @staticmethod
    def _empty_counts() -> dict[str, dict[str, int]]:
        """Zero for each counter, for each protocol."""
        return {proto: dict.fromkeys(FRAME_COUNTERS, 0) for proto in ("udp", "tcp")}

    def count(self, sender: str, protocol: str, counter: str, amount: int = 1) -> None:
        """Add ``amount`` to one counter; unknown senders share one bucket."""
        with self._lock:
            bucket = self._counts.get(sender, self._counts[UNKNOWN_SENDER])
            bucket[protocol][counter] += amount
        if counter in TREND_SERIES:
            self.timeline.add(counter, amount)

    def mark(self, name: str, amount: int = 1) -> None:
        """Record something that is not a frame counter (alerts, firewall blocks)."""
        self.timeline.add(name, amount)

    def trends(self, now: float | None = None) -> dict[str, list[int]]:
        """Per-second history of every trend series over the last 60 seconds."""
        window = self.timeline.window(now)
        return {name: [entry[name] for entry in window] for name in TREND_SERIES}

    def counts(self) -> dict[str, dict[str, dict[str, int]]]:
        """Copy of all counters: sender -> protocol -> counter -> value."""
        with self._lock:
            return {
                sender: {proto: dict(values) for proto, values in by_proto.items()}
                for sender, by_proto in self._counts.items()
            }

    def totals(self) -> dict[str, int]:
        """Each counter summed over all senders and both protocols."""
        totals = dict.fromkeys(FRAME_COUNTERS, 0)
        for by_proto in self.counts().values():
            for values in by_proto.values():
                for counter, value in values.items():
                    totals[counter] += value
        return totals

    def protocol_totals(self) -> dict[str, int]:
        """Good frames received over UDP and over TCP."""
        totals = {"udp": 0, "tcp": 0}
        for by_proto in self.counts().values():
            for proto, values in by_proto.items():
                totals[proto] += values["good"]
        return totals

    def add_event(self, record: dict[str, Any]) -> None:
        """Remember a received event (newest first) for the Packet Inspector."""
        with self._lock:
            self._events.appendleft(record)

    def recent_events(self) -> list[dict[str, Any]]:
        """The latest received events, newest first."""
        with self._lock:
            return list(self._events)

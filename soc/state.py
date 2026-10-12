"""Thread-safe shared state that the collector writes and the dashboard reads.

Concept: shared monitoring counters. Many receive threads update the same numbers
at once, so every change happens under a lock; readers get copies.
"""

import threading
from collections import deque
from typing import Any

FRAME_COUNTERS = ("good", "corrupted", "retransmitted", "lost")
UNKNOWN_SENDER = "unknown"
RECENT_EVENT_LIMIT = 50


class SocState:
    """Per-sensor frame counters split by UDP/TCP, plus the latest events."""

    def __init__(self, sensor_ids: list[str]) -> None:
        """Create zeroed counters for every sensor and for unreadable frames."""
        self._lock = threading.Lock()
        self._counts: dict[str, dict[str, dict[str, int]]] = {}
        for sender in [*sensor_ids, UNKNOWN_SENDER]:
            self._counts[sender] = self._empty_counts()
        self._events: deque[dict[str, Any]] = deque(maxlen=RECENT_EVENT_LIMIT)

    @staticmethod
    def _empty_counts() -> dict[str, dict[str, int]]:
        """Zero for each counter, for each protocol."""
        return {proto: dict.fromkeys(FRAME_COUNTERS, 0) for proto in ("udp", "tcp")}

    def count(self, sender: str, protocol: str, counter: str, amount: int = 1) -> None:
        """Add ``amount`` to one counter; unknown senders share one bucket."""
        with self._lock:
            bucket = self._counts.get(sender, self._counts[UNKNOWN_SENDER])
            bucket[protocol][counter] += amount

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

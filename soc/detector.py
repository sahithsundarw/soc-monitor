"""Attack detection rules and the alert store.

Concept: intrusion detection with sliding time windows. Each rule counts related
events (same source IP, same link) inside a recent time window and raises an alert
with a severity when a threshold is crossed. Alerts are appended to
logs/alerts.jsonl, one JSON object per line.
"""

import json
import logging
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("soc.detector")

SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ALERT_COOLDOWN_S = 30.0  # the same rule and source raise at most one alert per 30 s
RECENT_ALERT_LIMIT = 100


@dataclass(frozen=True)
class Alert:
    """One detection result shown on the dashboard and written to alerts.jsonl."""

    ts: float
    severity: str
    rule: str
    title: str
    detail: str
    source: str


class AlertStore:
    """Keeps recent alerts, appends each to a JSONL file and notifies listeners."""

    def __init__(self, path: Path | None) -> None:
        """``path`` is the JSONL file; None keeps alerts in memory only."""
        self._path = path
        self._lock = threading.Lock()
        self._alerts: deque[Alert] = deque(maxlen=RECENT_ALERT_LIMIT)
        self._total = 0
        self._listeners: list[Callable[[Alert], None]] = []
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def subscribe(self, listener: Callable[[Alert], None]) -> None:
        """Call ``listener(alert)`` for every new alert (e.g. the mailer)."""
        self._listeners.append(listener)

    def add(self, alert: Alert) -> None:
        """Store, persist and announce one alert."""
        with self._lock:
            self._alerts.appendleft(alert)
            self._total += 1
            if self._path is not None:
                with self._path.open("a", encoding="utf-8") as log_file:
                    log_file.write(json.dumps(asdict(alert)) + "\n")
        logger.warning("[%s] %s: %s", alert.severity, alert.title, alert.detail)
        for listener in self._listeners:
            listener(alert)

    def recent(self) -> list[dict[str, Any]]:
        """Latest alerts as dictionaries, newest first."""
        with self._lock:
            return [asdict(alert) for alert in self._alerts]

    @property
    def total(self) -> int:
        """Number of alerts raised since start-up."""
        with self._lock:
            return self._total


class SlidingWindow:
    """Timestamps per key, forgetting those older than ``window_s``."""

    def __init__(self, window_s: float) -> None:
        """Create an empty window of the given length in seconds."""
        self.window_s = window_s
        self._times: dict[str, deque[float]] = defaultdict(deque)

    def add(self, key: str, now: float) -> int:
        """Record one occurrence for ``key``; return how many are in the window."""
        times = self._times[key]
        times.append(now)
        while times and times[0] < now - self.window_s:
            times.popleft()
        return len(times)


class Detector:
    """The five SOC detection rules plus helpers other components call."""

    def __init__(
        self, config: dict[str, Any], alert_sink: Callable[[Alert], None]
    ) -> None:
        """Read thresholds from the ``detector`` section of the config."""
        rules = config["detector"]
        self.rules = rules
        self.known_hosts = set(config["known_hosts"])
        self._sink = alert_sink
        self._lock = threading.Lock()
        self._last_raised: dict[tuple[str, str], float] = {}
        self._failed_logins = SlidingWindow(rules["brute_force_window_s"])
        self._crc_failures = SlidingWindow(rules["crc_fail_window_s"])
        self._ports: dict[str, deque[tuple[float, int]]] = defaultdict(deque)
        self._beacons: dict[str, deque[float]] = defaultdict(deque)

    def raise_alert(
        self,
        rule: str,
        severity: str,
        source: str,
        title: str,
        detail: str,
        now: float | None = None,
    ) -> bool:
        """Send an alert unless the same rule fired for the same source recently."""
        now = time.time() if now is None else now
        with self._lock:
            last = self._last_raised.get((rule, source))
            if last is not None and now - last < ALERT_COOLDOWN_S:
                return False
            self._last_raised[(rule, source)] = now
        self._sink(Alert(round(now, 3), severity, rule, title, detail, source))
        return True

    def process_event(self, event: dict[str, Any]) -> None:
        """Run every event-based rule on one received event."""
        with self._lock:
            checks = [
                self._check_unknown_host(event),
                self._check_brute_force(event),
                self._check_port_scan(event),
                self._check_beacon(event),
            ]
        for found in checks:
            if found is not None:
                self.raise_alert(*found, now=event["ts"])

    def _check_unknown_host(self, event: dict[str, Any]) -> tuple[str, ...] | None:
        """An event from an IP that is not listed in config.json."""
        src_ip = event["src_ip"]
        if src_ip in self.known_hosts:
            return None
        return (
            "unknown_host",
            "MEDIUM",
            src_ip,
            "Unknown host",
            f"Event from {src_ip}, which is not a known host (seen by {event['sensor']})",
        )

    def _check_brute_force(self, event: dict[str, Any]) -> tuple[str, ...] | None:
        """N or more failed logins from one IP inside the window."""
        if event["type"] != "failed_login":
            return None
        src_ip = event["src_ip"]
        count = self._failed_logins.add(src_ip, event["ts"])
        if count < self.rules["brute_force_attempts"]:
            return None
        return (
            "brute_force",
            "HIGH",
            src_ip,
            "Brute-force login",
            f"{count} failed logins for '{event.get('user', '?')}' from {src_ip} "
            f"within {self.rules['brute_force_window_s']} s",
        )

    def _check_port_scan(self, event: dict[str, Any]) -> tuple[str, ...] | None:
        """N or more distinct destination ports from one IP inside the window."""
        if event["type"] != "port_probe":
            return None
        src_ip, now = event["src_ip"], event["ts"]
        probes = self._ports[src_ip]
        probes.append((now, event["dst_port"]))
        while probes and probes[0][0] < now - self.rules["port_scan_window_s"]:
            probes.popleft()
        distinct = len({port for _, port in probes})
        if distinct < self.rules["port_scan_ports"]:
            return None
        return (
            "port_scan",
            "HIGH",
            src_ip,
            "Port scan",
            f"{src_ip} probed {distinct} ports within {self.rules['port_scan_window_s']} s",
        )

    def _check_beacon(self, event: dict[str, Any]) -> tuple[str, ...] | None:
        """Beacons from one host to one destination at a near-constant interval."""
        if event["type"] != "beacon":
            return None
        pair = f"{event['src_ip']}->{event['dst_ip']}"
        times = self._beacons[pair]
        times.append(event["ts"])
        needed = self.rules["beacon_min_count"]
        while len(times) > needed:
            times.popleft()
        if len(times) < needed:
            return None
        gaps = [later - earlier for earlier, later in zip(times, list(times)[1:])]
        if max(gaps) - min(gaps) > self.rules["beacon_jitter_s"]:
            return None  # irregular timing: probably normal traffic
        return (
            "malware_c2",
            "CRITICAL",
            pair,
            "Malware C2 beacon",
            f"{event['src_ip']} contacts {event['dst_ip']} every "
            f"{sum(gaps) / len(gaps):.1f} s ({needed} beacons)",
        )

    def record_crc_failure(self, link: str, now: float | None = None) -> None:
        """Count a CRC failure on a link; many in a short time suggests tampering."""
        now = time.time() if now is None else now
        with self._lock:
            count = self._crc_failures.add(link, now)
        if count >= self.rules["crc_fail_threshold"]:
            self.raise_alert(
                "link_integrity",
                "MEDIUM",
                link,
                "Link tampering or noise",
                f"{count} CRC failures on frames arriving via {link} "
                f"within {self.rules['crc_fail_window_s']} s",
                now,
            )

    def report_flooding(self, sensor: str, drops: int, window_s: float) -> None:
        """Called by the token bucket when a sensor keeps exceeding its rate."""
        self.raise_alert(
            "flooding",
            "HIGH",
            sensor,
            "Flooding",
            f"{sensor} exceeded its token bucket rate: {drops} frames dropped "
            f"within {window_s} s",
        )

    def report_firewall_block(self, src_ip: str, reason: str) -> None:
        """Called by the collector when the firewall blocks a source."""
        self.raise_alert(
            "firewall_block",
            "LOW",
            src_ip,
            "Firewall block",
            f"Traffic from {src_ip} blocked ({reason})",
        )

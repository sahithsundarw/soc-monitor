"""Tests for the detection rules and the alert store."""

import json
import tempfile
import unittest
from pathlib import Path

from config_loader import load_config
from soc.detector import ALERT_COOLDOWN_S, Alert, AlertStore, Detector

KNOWN_IP = "192.168.1.55"


def event(event_type: str, ts: float, src_ip: str = KNOWN_IP, **fields) -> dict:
    """A minimal event as a sensor would send it."""
    return {
        "ts": ts,
        "sensor": "auth01",
        "type": event_type,
        "src_ip": src_ip,
        **fields,
    }


class DetectorTest(unittest.TestCase):
    """Each rule fires at its threshold and not before."""

    def setUp(self) -> None:
        self.alerts: list[Alert] = []
        self.detector = Detector(load_config(), self.alerts.append)

    def rules(self) -> list[str]:
        return [alert.rule for alert in self.alerts]

    def test_brute_force_after_five_failures(self) -> None:
        for second in range(4):
            self.detector.process_event(
                event("failed_login", 100 + second, user="root")
            )
        self.assertEqual(self.rules(), [])
        self.detector.process_event(event("failed_login", 105, user="root"))
        self.assertEqual(self.rules(), ["brute_force"])
        self.assertEqual(self.alerts[0].severity, "HIGH")

    def test_failures_outside_window_do_not_count(self) -> None:
        for minute in range(6):
            self.detector.process_event(event("failed_login", 100 + minute * 61))
        self.assertEqual(self.rules(), [])

    def test_port_scan_needs_ten_distinct_ports(self) -> None:
        for _ in range(12):
            self.detector.process_event(event("port_probe", 100.0, dst_port=22))
        self.assertEqual(self.rules(), [])
        for port in range(10):
            self.detector.process_event(
                event("port_probe", 100.1, dst_port=1000 + port)
            )
        self.assertEqual(self.rules(), ["port_scan"])

    def test_unknown_host(self) -> None:
        self.detector.process_event(event("http_request", 100, src_ip="8.8.4.4"))
        self.assertEqual(self.rules(), ["unknown_host"])
        self.assertEqual(self.alerts[0].severity, "MEDIUM")

    def test_regular_beacons_are_c2(self) -> None:
        for n in range(4):
            self.detector.process_event(
                event("beacon", 100 + n * 2.0, dst_ip="9.9.9.9")
            )
        self.assertIn("malware_c2", self.rules())
        self.assertEqual(self.alerts[-1].severity, "CRITICAL")

    def test_irregular_beacons_are_ignored(self) -> None:
        for ts in (100, 101, 105, 106):
            self.detector.process_event(event("beacon", ts, dst_ip="9.9.9.9"))
        self.assertNotIn("malware_c2", self.rules())

    def test_crc_failures_on_one_link(self) -> None:
        for n in range(5):
            self.detector.record_crc_failure("R2-SOC", now=100 + n)
        self.assertEqual(self.rules(), ["link_integrity"])
        self.assertEqual(self.alerts[0].source, "R2-SOC")

    def test_cooldown_suppresses_repeats(self) -> None:
        for n in range(20):
            self.detector.process_event(event("failed_login", 100 + n))
        self.assertEqual(self.rules(), ["brute_force"])
        self.detector.process_event(event("failed_login", 120 + ALERT_COOLDOWN_S))
        self.assertEqual(self.rules(), ["brute_force", "brute_force"])


class AlertStoreTest(unittest.TestCase):
    """Persistence and listeners."""

    def test_writes_jsonl_and_notifies(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "alerts.jsonl"
            store = AlertStore(path)
            heard: list[Alert] = []
            store.subscribe(heard.append)
            alert = Alert(
                1.0, "HIGH", "brute_force", "Brute-force login", "x", KNOWN_IP
            )
            store.add(alert)
            store.add(alert)
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(lines[0])["rule"], "brute_force")
        self.assertEqual(len(lines), 2)
        self.assertEqual(len(heard), 2)
        self.assertEqual(store.total, 2)


if __name__ == "__main__":
    unittest.main()

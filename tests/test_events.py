"""Tests for event generators and shared state."""

import random
import unittest

from soc.events import (
    BRUTE_FORCE_ATTEMPTS,
    PORT_SCAN_PORTS,
    EventFactory,
    priority_of,
)
from soc.state import SocState

KNOWN = ["192.168.1.20", "192.168.1.21"]


class EventFactoryTest(unittest.TestCase):
    """Normal and attack events."""

    def setUp(self) -> None:
        self.factory = EventFactory("auth01", "auth_server", KNOWN, random.Random(1))

    def test_ids_are_unique(self) -> None:
        ids = {self.factory.normal()["id"] for _ in range(20)}
        self.assertEqual(len(ids), 20)

    def test_normal_events_are_routine_and_from_known_hosts(self) -> None:
        for _ in range(20):
            event = self.factory.normal()
            self.assertIn(event["src_ip"], KNOWN)
            self.assertEqual(priority_of(event), 0)

    def test_brute_force_burst(self) -> None:
        events = self.factory.failed_logins()
        self.assertEqual(len(events), BRUTE_FORCE_ATTEMPTS)
        self.assertEqual({e["src_ip"] for e in events}, {"192.168.1.55"})
        self.assertEqual(priority_of(events[0]), 1)

    def test_port_scan_uses_distinct_ports(self) -> None:
        ports = [e["dst_port"] for e in self.factory.port_scan()]
        self.assertEqual(sorted(set(ports)), sorted(PORT_SCAN_PORTS))

    def test_beacon_is_critical(self) -> None:
        self.assertEqual(priority_of(self.factory.beacon()), 2)


class SocStateTest(unittest.TestCase):
    """Counters and recent events."""

    def setUp(self) -> None:
        self.state = SocState(["S1", "S2"])

    def test_counts_and_totals(self) -> None:
        self.state.count("S1", "udp", "good", 3)
        self.state.count("S2", "tcp", "good")
        self.state.count("S1", "tcp", "corrupted")
        self.assertEqual(self.state.totals()["good"], 4)
        self.assertEqual(self.state.protocol_totals(), {"udp": 3, "tcp": 1})
        self.assertEqual(self.state.counts()["S1"]["tcp"]["corrupted"], 1)

    def test_unknown_sender_goes_to_shared_bucket(self) -> None:
        self.state.count("X9", "udp", "corrupted")
        self.assertEqual(self.state.counts()["unknown"]["udp"]["corrupted"], 1)

    def test_recent_events_newest_first(self) -> None:
        self.state.add_event({"id": 1})
        self.state.add_event({"id": 2})
        self.assertEqual([e["id"] for e in self.state.recent_events()], [2, 1])


if __name__ == "__main__":
    unittest.main()

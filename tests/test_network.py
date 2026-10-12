"""End-to-end tests: real UDP/TCP frames through routers to the collector."""

import logging
import socket
import threading
import time
import unittest

from network.transport import FrameServer, send_tcp
from soc.system import SocSystem
from tests.helpers import make_test_config


def wait_until(condition, timeout_s: float = 5.0) -> bool:
    """Poll ``condition()`` until it is true or the timeout passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


class TransportTest(unittest.TestCase):
    """FrameServer receives one frame per datagram and per TCP connection."""

    def test_udp_and_tcp_delivery(self) -> None:
        received: list[tuple[bytes, str]] = []
        done = threading.Event()

        def handler(data: bytes, protocol: str) -> None:
            received.append((data, protocol))
            if len(received) == 2:
                done.set()

        server = FrameServer("test", "127.0.0.1", 39999, handler)
        server.start()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp:
                udp.sendto(b"hello-udp", ("127.0.0.1", 39999))
            send_tcp(b"hello-tcp", ("127.0.0.1", 39999))
            self.assertTrue(done.wait(3))
        finally:
            server.stop()
        self.assertEqual(
            sorted(received), [(b"hello-tcp", "tcp"), (b"hello-udp", "udp")]
        )


class NetworkTest(unittest.TestCase):
    """Sensors, routers and collector running together on shifted ports."""

    def setUp(self) -> None:
        logging.disable(logging.WARNING)  # noise tests log many expected warnings
        self.system = SocSystem(make_test_config(), alerts_file=None)
        self.system.start()

    def tearDown(self) -> None:
        self.system.stop()
        logging.disable(logging.NOTSET)

    def test_routine_event_arrives_over_udp(self) -> None:
        sensor = self.system.sensors["S1"]
        self.assertTrue(sensor.send_event(sensor.factory.normal()))
        record = self.system.state.recent_events()[0]
        self.assertEqual(record["protocol"], "udp")
        self.assertEqual(record["path"], ["S1", "R2", "SOC"])
        self.assertEqual(record["hops"], 1)  # one router decremented the TTL

    def test_high_priority_event_arrives_over_tcp(self) -> None:
        sensor = self.system.sensors["S3"]
        self.assertTrue(sensor.send_event(sensor.factory.failed_logins()[0]))
        self.assertEqual(self.system.state.protocol_totals()["tcp"], 1)

    def test_failed_link_reroutes_and_still_delivers(self) -> None:
        self.system.topology.fail_link("R2", "SOC")
        sensor = self.system.sensors["S1"]
        self.assertTrue(sensor.send_event(sensor.factory.normal()))
        self.assertEqual(
            self.system.state.recent_events()[0]["path"], ["S1", "R2", "R4", "SOC"]
        )

    def test_noise_causes_corruption_and_retransmission(self) -> None:
        self.system.settings.set_error_rate(0.15)
        sensor = self.system.sensors["S2"]
        for _ in range(10):
            sensor.send_event(sensor.factory.normal())
        totals = self.system.state.totals()
        self.assertGreater(totals["retransmitted"], 0)
        self.assertGreater(totals["good"], 0)

    def test_every_framing_and_crc_combination_works_live(self) -> None:
        sensor = self.system.sensors["S1"]
        for method in ("character", "bit"):
            for crc_type in ("CRC-12", "CRC-16", "CRC-CCITT"):
                self.system.settings.set_method(method)
                self.system.settings.set_crc_type(crc_type)
                with self.subTest(method=method, crc=crc_type):
                    self.assertTrue(sensor.send_event(sensor.factory.normal()))

    def alert_rules(self) -> set[str]:
        """Rules of every alert raised so far."""
        return {alert["rule"] for alert in self.system.alerts.recent()}

    def test_flood_is_policed_and_raises_flooding_alert(self) -> None:
        self.system.sensors["S1"].flood(60)
        self.assertTrue(wait_until(lambda: "flooding" in self.alert_rules()))
        totals = self.system.policer.totals()["S1"]
        self.assertGreater(totals["dropped"], 20)
        self.assertLessEqual(totals["allowed"], 15)

    def test_spoofed_source_is_blocked_by_firewall(self) -> None:
        self.system.sensors["S1"].flood(5, spoof_ip="203.0.113.66")
        self.assertTrue(
            wait_until(lambda: self.system.firewall.stats()["blocked"] == 5)
        )
        self.assertIn("firewall_block", self.alert_rules())
        self.assertEqual(self.system.state.totals()["good"], 0)

    def test_brute_force_attack_raises_high_alert(self) -> None:
        self.system.sensors["S3"].launch("brute_force").join(timeout=10)
        self.assertIn("brute_force", self.alert_rules())
        alert = next(
            a for a in self.system.alerts.recent() if a["rule"] == "brute_force"
        )
        self.assertEqual(alert["severity"], "HIGH")

    def test_port_scan_raises_scan_and_unknown_host_alerts(self) -> None:
        self.system.sensors["S2"].launch("port_scan").join(timeout=10)
        self.assertTrue({"port_scan", "unknown_host"} <= self.alert_rules())


if __name__ == "__main__":
    unittest.main()

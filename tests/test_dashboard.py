"""Tests for the Flask dashboard: page, JSON API and Packet Inspector."""

import unittest
from dataclasses import asdict
from typing import Any

from dashboard.app import create_app
from dashboard.inspector import crc_hex, describe_layers
from datalink.frame import Frame, FrameFormat, Header, encode_frame
from soc.system import SocSystem
from tests.helpers import make_test_config

DASHBOARD_TEST_OFFSET = 31000


class DashboardTestCase(unittest.TestCase):
    """A dashboard over a built-but-not-started system (sockets bound, no traffic)."""

    def setUp(self) -> None:
        self.system = SocSystem(
            make_test_config(DASHBOARD_TEST_OFFSET), alerts_file=None
        )
        self.client = create_app(self.system).test_client()

    def tearDown(self) -> None:
        self.system.stop()

    def get_data(self, path: str) -> Any:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertIsNone(body["error"])
        return body["data"]

    def post(self, path: str, payload: Any) -> tuple[int, dict[str, Any]]:
        response = self.client.post(path, json=payload)
        return response.status_code, response.get_json()


class PageTest(DashboardTestCase):
    """The HTML page and its local static files."""

    def test_index_shows_title_and_tabs(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        for text in (b"SOC Monitor", b"Packet Inspector", b"Route from S1"):
            self.assertIn(text, response.data)

    def test_static_files_are_local(self) -> None:
        for path in ("/static/style.css", "/static/app.js"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertNotIn(b"http", self.client.get("/").data.split(b"<body>")[0])


class StatusApiTest(DashboardTestCase):
    """GET endpoints."""

    def test_status_shape(self) -> None:
        data = self.get_data("/api/status")
        self.assertFalse(data["running"])
        self.assertEqual(
            set(data["tiles"]),
            {"events", "alerts", "corrupted", "retransmissions", "firewall_blocks"},
        )
        self.assertEqual(len(data["qos"]["timeline"]), 60)
        self.assertEqual(data["routes"]["S1"]["path"], ["S1", "R2", "SOC"])

    def test_topology_has_tables_for_every_router(self) -> None:
        data = self.get_data("/api/topology")
        self.assertEqual(set(data["tables"]), {"R1", "R2", "R3", "R4"})
        self.assertEqual(data["tables"]["R2"]["SOC"], "SOC")
        self.assertEqual(len(data["nodes"]), 8)

    def test_events_empty_then_unknown_event_is_400(self) -> None:
        self.assertEqual(self.get_data("/api/events"), [])
        response = self.client.get("/api/events/nope-1")
        self.assertEqual(response.status_code, 400)
        self.assertIn("nope-1", response.get_json()["error"])


class ControlApiTest(DashboardTestCase):
    """POST endpoints: success and failure paths."""

    def test_fail_and_restore_link_changes_route(self) -> None:
        status, _ = self.post("/api/links/fail", {"a": "R2", "b": "SOC"})
        self.assertEqual(status, 200)
        self.assertEqual(
            self.get_data("/api/status")["routes"]["S1"]["path"],
            ["S1", "R2", "R4", "SOC"],
        )
        self.post("/api/links/restore", {"a": "R2", "b": "SOC"})
        self.assertEqual(
            self.get_data("/api/status")["routes"]["S1"]["path"], ["S1", "R2", "SOC"]
        )

    def test_unknown_link_is_400(self) -> None:
        status, body = self.post("/api/links/fail", {"a": "R1", "b": "SOC"})
        self.assertEqual(status, 400)
        self.assertIn("No link", body["error"])

    def test_bad_link_action_is_400(self) -> None:
        status, _ = self.post("/api/links/explode", {"a": "R2", "b": "SOC"})
        self.assertEqual(status, 400)

    def test_noise(self) -> None:
        self.assertEqual(self.post("/api/noise", {"error_rate": 0.2})[0], 200)
        self.assertEqual(self.system.settings.error_rate, 0.2)
        self.assertEqual(self.post("/api/noise", {"error_rate": 3})[0], 400)
        self.assertEqual(self.post("/api/noise", {})[0], 400)

    def test_switch_framing_and_crc(self) -> None:
        status, body = self.post(
            "/api/settings", {"method": "character", "crc_type": "CRC-12"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["data"], {"method": "character", "crc_type": "CRC-12"})
        self.assertEqual(self.post("/api/settings", {"crc_type": "CRC-7"})[0], 400)

    def test_attack_validation(self) -> None:
        self.assertEqual(self.post("/api/attack", {"attack": "nuke"})[0], 400)
        status, _ = self.post("/api/attack", {"attack": "port_scan", "sensor": "S9"})
        self.assertEqual(status, 400)

    def test_flood_validation(self) -> None:
        self.assertEqual(self.post("/api/flood", {"sensor": "R1"})[0], 400)

    def test_non_object_body_is_400(self) -> None:
        status, body = self.post("/api/noise", [1, 2])
        self.assertEqual(status, 400)
        self.assertIn("JSON object", body["error"])


class ServiceApiTest(DashboardTestCase):
    """Reports, emails and diagnostics endpoints (services not started)."""

    def test_reports_without_ftp_server_is_503(self) -> None:
        response = self.client.get("/api/reports")
        self.assertEqual(response.status_code, 503)
        self.assertIn("FTP", response.get_json()["error"])

    def test_inbox_starts_empty(self) -> None:
        self.assertEqual(self.get_data("/api/emails"), [])

    def test_diagnostics_lists_whitelist_and_targets(self) -> None:
        data = self.get_data("/api/diagnostics")
        self.assertEqual(
            [c["id"] for c in data["commands"]],
            ["ping", "traceroute", "netstat", "ipconfig", "arp"],
        )
        self.assertEqual(data["targets"][0]["ip"], "127.0.0.1")

    def test_diagnostics_rejects_unlisted_command_and_target(self) -> None:
        status, _ = self.post(
            "/api/diagnostics", {"command": "rm", "target": "127.0.0.1"}
        )
        self.assertEqual(status, 400)
        status, _ = self.post(
            "/api/diagnostics", {"command": "ping", "target": "8.8.8.8"}
        )
        self.assertEqual(status, 400)


class InspectorTest(unittest.TestCase):
    """Layer breakdown of a received event."""

    def record(self, method: str) -> dict[str, Any]:
        header = Header("S1", "SOC", "192.168.1.10", "10.0.0.1", 1, "DATA", 15, 0)
        payload = {"id": "fw01-1", "type": "http_request", "src_ip": "192.168.1.20"}
        frame_format = FrameFormat(method, "CRC-12", 0x7E, 0x7D, "01111110")
        wire = encode_frame(Frame(header, payload), frame_format).wire
        return {
            "id": "fw01-1",
            "payload": payload,
            "protocol": "udp",
            "src_port": 9101,
            "dst_port": 9300,
            "header": asdict(header),
            "hops": 1,
            "path": ["S1", "R2", "SOC"],
            "method": method,
            "crc_type": "CRC-12",
            "wire_hex": wire.hex(),
        }

    def test_layers_rebuild_the_received_frame(self) -> None:
        for method in ("character", "bit"):
            layers = describe_layers(self.record(method))
            self.assertTrue(layers["datalink"]["matches_received"])
            self.assertEqual(layers["network"]["path"], ["S1", "R2", "SOC"])
            self.assertEqual(layers["transport"]["protocol"], "UDP")
            self.assertTrue(layers["datalink"]["wire_hex"].startswith("7e"))
            self.assertEqual(len(layers["datalink"]["crc_bits"]), 12)

    def test_crc_hex_width(self) -> None:
        self.assertEqual(crc_hex("000000000001", 12), "001")
        self.assertEqual(crc_hex("1" * 16, 16), "ffff")


if __name__ == "__main__":
    unittest.main()

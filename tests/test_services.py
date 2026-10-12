"""Tests for the FTP archive, the alert mailer and the diagnostics whitelist."""

import ftplib
import json
import tempfile
import time
import unittest
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

from services.diagnostics import (
    DiagnosticsError,
    candidates,
    filter_netstat,
    run_diagnostic,
    trim,
)
from services.ftp_archive import (
    FtpArchiveServer,
    generate_and_upload,
    generate_report,
    list_files,
)
from services.mailer import AlertMailer, Inbox, MailServer
from soc.detector import Alert
from tests.helpers import make_test_config

SERVICE_TEST_OFFSET = 32000


def write_alerts(path: Path, alerts: list[Alert]) -> None:
    """Write alerts as JSONL, the way AlertStore does."""
    with path.open("w", encoding="utf-8") as alerts_file:
        for alert in alerts:
            alerts_file.write(json.dumps(asdict(alert)) + "\n")


TODAY_ALERT = Alert(
    time.time(),
    "HIGH",
    "brute_force",
    "Brute-force login",
    "8 failures",
    "192.168.1.55",
)
OLD_ALERT = Alert(
    datetime(2020, 1, 1).timestamp(),
    "LOW",
    "firewall_block",
    "Firewall block",
    "x",
    "1.2.3.4",
)


class ReportTest(unittest.TestCase):
    """Daily summary in .txt and .csv."""

    def test_report_contains_only_todays_alerts(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            alerts_file = Path(folder) / "alerts.jsonl"
            write_alerts(alerts_file, [TODAY_ALERT, OLD_ALERT])
            txt_path, csv_path = generate_report(
                date.today(), alerts_file, Path(folder)
            )
            text = txt_path.read_text(encoding="utf-8")
            rows = csv_path.read_text(encoding="utf-8").splitlines()
        self.assertIn("Total alerts: 1", text)
        self.assertIn("Brute-force login", text)
        self.assertNotIn("Firewall block:", text)
        self.assertEqual(len(rows), 2)  # header + one alert

    def test_report_without_alert_file(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            txt_path, _ = generate_report(date.today(), None, Path(folder))
            self.assertIn("Total alerts: 0", txt_path.read_text(encoding="utf-8"))


class FtpTest(unittest.TestCase):
    """Upload with ftplib to the pyftpdlib server and list the files."""

    def test_upload_and_list(self) -> None:
        config = make_test_config(SERVICE_TEST_OFFSET)["services"]["ftp"]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "ftp_root"
            server = FtpArchiveServer(config, root)
            server.start()
            try:
                uploaded = generate_and_upload(config, None, Path(folder) / "reports")
                listing = list_files(config)
            finally:
                server.stop()
            self.assertEqual(len(uploaded), 2)
            self.assertEqual({entry["name"] for entry in listing}, set(uploaded))
            self.assertTrue((root / uploaded[0]).exists())

    def test_wrong_password_is_refused(self) -> None:
        config = make_test_config(SERVICE_TEST_OFFSET)["services"]["ftp"]
        with tempfile.TemporaryDirectory() as folder:
            server = FtpArchiveServer(config, Path(folder))
            server.start()
            try:
                with self.assertRaises(ftplib.error_perm):
                    list_files({**config, "password": "wrong"})
            finally:
                server.stop()


class MailerTest(unittest.TestCase):
    """HIGH/CRITICAL alerts arrive in the local inbox; LOW ones are not sent."""

    def test_only_serious_alerts_are_emailed(self) -> None:
        config = make_test_config(SERVICE_TEST_OFFSET)["services"]["smtp"]
        inbox = Inbox()
        server = MailServer(config, inbox)
        mailer = AlertMailer(config)
        server.start()
        mailer.start()
        try:
            mailer.on_alert(OLD_ALERT)
            mailer.on_alert(TODAY_ALERT)
            deadline = time.monotonic() + 5
            while not inbox.messages() and time.monotonic() < deadline:
                time.sleep(0.05)
        finally:
            mailer.stop()
            server.stop()
        messages = inbox.messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["subject"], "[HIGH] Brute-force login")
        self.assertIn("192.168.1.55", messages[0]["body"])
        self.assertEqual(messages[0]["recipient"], config["recipient"])


class DiagnosticsTest(unittest.TestCase):
    """Whitelist, OS-specific commands and output handling."""

    def setUp(self) -> None:
        self.config = make_test_config(SERVICE_TEST_OFFSET)

    def test_os_specific_commands(self) -> None:
        self.assertEqual(
            candidates("ping", "127.0.0.1", True)[0], ["ping", "-n", "4", "127.0.0.1"]
        )
        self.assertEqual(
            candidates("ping", "127.0.0.1", False)[0], ["ping", "-c", "4", "127.0.0.1"]
        )
        self.assertEqual(candidates("traceroute", "127.0.0.1", True)[0][0], "tracert")
        self.assertEqual(candidates("ipconfig", "", False)[0], ["ifconfig"])

    def test_unknown_command_rejected(self) -> None:
        with self.assertRaises(DiagnosticsError):
            run_diagnostic("rm", "127.0.0.1", self.config)

    def test_target_must_come_from_config(self) -> None:
        with self.assertRaises(DiagnosticsError):
            run_diagnostic("ping", "127.0.0.1; whoami", self.config)

    def test_ping_localhost_runs(self) -> None:
        result = run_diagnostic("ping", "127.0.0.1", self.config)
        self.assertIn("127.0.0.1", result["output"])
        self.assertTrue(result["command"].startswith("ping"))

    def test_netstat_filter_keeps_project_ports(self) -> None:
        output = (
            "  Proto  Local Address   Foreign Address  State\n"
            "  TCP    127.0.0.1:9300  0.0.0.0:0        LISTENING\n"
            "  TCP    127.0.0.1:445   0.0.0.0:0        LISTENING\n"
        )
        kept = filter_netstat(output, {9300})
        self.assertIn("9300", kept)
        self.assertNotIn(":445", kept)

    def test_trim_long_output(self) -> None:
        trimmed = trim("\n".join(str(n) for n in range(500)))
        self.assertIn("more lines", trimmed)


if __name__ == "__main__":
    unittest.main()

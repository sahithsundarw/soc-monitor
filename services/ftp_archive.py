"""FTP archive: a local FTP server plus a daily alert report uploaded with ftplib.

Concept: configuring an FTP server for file sharing (Lab Week 13). FTP uses a
control connection for commands (USER, PASS, STOR, MLSD) and a separate data
connection for each file transfer or directory listing.
"""

import csv
import ftplib
import json
import logging
import threading
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer

from config_loader import PROJECT_ROOT, load_config

logger = logging.getLogger("services.ftp")

FTP_ROOT = PROJECT_ROOT / "ftp_root"
REPORTS_DIR = PROJECT_ROOT / "reports"
ALERTS_FILE = PROJECT_ROOT / "logs" / "alerts.jsonl"
FTP_TIMEOUT_S = 10
SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")


class ArchiveHandler(FTPHandler):
    """FTP command handler (one per client connection) with our banner."""

    banner = "SOC Monitor FTP archive"


class FtpArchiveServer:
    """pyftpdlib server with one user whose home is ./ftp_root."""

    def __init__(self, ftp_config: dict[str, Any], root: Path = FTP_ROOT) -> None:
        """Read host, port and credentials from the ``services.ftp`` config."""
        self.config = ftp_config
        self.root = root
        self._server: FTPServer | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Bind the control port and serve in a background thread."""
        self.root.mkdir(parents=True, exist_ok=True)
        authorizer = DummyAuthorizer()
        # e=cd l=list r=download a=append w=upload; no delete or rename rights.
        authorizer.add_user(
            self.config["user"], self.config["password"], str(self.root), perm="elraw"
        )
        ArchiveHandler.authorizer = authorizer
        address = (self.config["host"], self.config["port"])
        self._server = FTPServer(address, ArchiveHandler)
        self._thread = threading.Thread(target=self._serve, name="ftp", daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        """Poll the server's IO loop in short steps so stop() is quick."""
        assert self._server is not None
        logger.info("FTP archive listening on %s:%s", *self._server.address)
        while not self._stop.is_set():
            self._server.ioloop.loop(timeout=0.5, blocking=False)
        self._server.close_all()

    def stop(self) -> None:
        """Stop serving and close every FTP connection."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)


def read_alerts(alerts_file: Path | None, day: date) -> list[dict[str, Any]]:
    """Alerts from logs/alerts.jsonl that were raised on ``day`` (local time)."""
    if alerts_file is None or not alerts_file.exists():
        return []
    alerts = []
    with alerts_file.open(encoding="utf-8") as lines:
        for line in lines:
            if not line.strip():
                continue
            alert = json.loads(line)
            if datetime.fromtimestamp(alert["ts"]).date() == day:
                alerts.append(alert)
    return alerts


def summary_text(alerts: list[dict[str, Any]], day: date) -> str:
    """Human-readable daily summary: counts by severity and rule, then each alert."""
    by_severity = Counter(alert["severity"] for alert in alerts)
    by_rule = Counter(alert["title"] for alert in alerts)
    lines = [f"SOC Monitor alert summary for {day.isoformat()}", ""]
    lines.append(f"Total alerts: {len(alerts)}")
    for severity in SEVERITY_ORDER:
        lines.append(f"  {severity:<9} {by_severity.get(severity, 0)}")
    lines.append("")
    lines.append("By rule:")
    for title, count in by_rule.most_common():
        lines.append(f"  {title:<26} {count}")
    lines.append("")
    lines.append("Alerts:")
    for alert in alerts:
        clock = datetime.fromtimestamp(alert["ts"]).strftime("%H:%M:%S")
        lines.append(
            f"  {clock}  {alert['severity']:<9} {alert['title']}: {alert['detail']}"
        )
    if not alerts:
        lines.append("  none")
    return "\n".join(lines) + "\n"


def generate_report(
    day: date | None = None,
    alerts_file: Path | None = ALERTS_FILE,
    reports_dir: Path = REPORTS_DIR,
) -> list[Path]:
    """Write reports/alerts_<day>.txt and .csv; return both paths."""
    day = day or date.today()
    alerts = read_alerts(alerts_file, day)
    reports_dir.mkdir(parents=True, exist_ok=True)
    txt_path = reports_dir / f"alerts_{day.isoformat()}.txt"
    csv_path = reports_dir / f"alerts_{day.isoformat()}.csv"
    txt_path.write_text(summary_text(alerts, day), encoding="utf-8")
    fields = ["time", "severity", "rule", "title", "source", "detail"]
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        for alert in alerts:
            row = {key: alert[key] for key in fields[1:]}
            row["time"] = datetime.fromtimestamp(alert["ts"]).isoformat(
                timespec="seconds"
            )
            writer.writerow(row)
    logger.info(
        "Report written: %s, %s (%d alerts)", txt_path.name, csv_path.name, len(alerts)
    )
    return [txt_path, csv_path]


def connect(ftp_config: dict[str, Any]) -> ftplib.FTP:
    """Open the control connection and log in (USER/PASS)."""
    ftp = ftplib.FTP(timeout=FTP_TIMEOUT_S)
    try:
        ftp.connect(ftp_config["host"], ftp_config["port"])
        ftp.login(ftp_config["user"], ftp_config["password"])
    except (OSError, EOFError, ftplib.Error):
        ftp.close()  # don't leak the control socket when login fails
        raise
    return ftp


def upload_files(paths: list[Path], ftp_config: dict[str, Any]) -> list[str]:
    """Upload each file with STOR over a fresh data connection; return the names."""
    with connect(ftp_config) as ftp:
        for path in paths:
            with path.open("rb") as source:
                ftp.storbinary(f"STOR {path.name}", source)
            logger.info("Uploaded %s via FTP", path.name)
    return [path.name for path in paths]


def list_files(ftp_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Directory listing from the server (MLSD), newest first."""
    files = []
    with connect(ftp_config) as ftp:
        for name, facts in ftp.mlsd(facts=["type", "size", "modify"]):
            if facts.get("type") != "file" or name.startswith("."):
                continue  # skip folders and hidden files such as .gitkeep
            # MLSD reports times in UTC; show them in the PC's local time.
            utc_time = datetime.strptime(facts["modify"][:14], "%Y%m%d%H%M%S")
            modified = utc_time.replace(tzinfo=timezone.utc).astimezone()
            files.append(
                {
                    "name": name,
                    "size": int(facts.get("size", 0)),
                    "modified": modified.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    return sorted(files, key=lambda entry: entry["modified"], reverse=True)


def generate_and_upload(
    ftp_config: dict[str, Any],
    alerts_file: Path | None = ALERTS_FILE,
    reports_dir: Path = REPORTS_DIR,
) -> list[str]:
    """The dashboard's "Generate & upload report" action."""
    paths = generate_report(alerts_file=alerts_file, reports_dir=reports_dir)
    return upload_files(paths, ftp_config)


def run_demo() -> None:
    """Start the FTP server, upload today's report and list the archive."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    ftp_config = load_config()["services"]["ftp"]
    server = FtpArchiveServer(ftp_config)
    server.start()
    try:
        print("Uploaded:", ", ".join(generate_and_upload(ftp_config)))
        for entry in list_files(ftp_config):
            print(
                f"  {entry['name']:<28} {entry['size']:>7} bytes  {entry['modified']}"
            )
    finally:
        server.stop()


if __name__ == "__main__":
    run_demo()

"""Builds and wires every component of the SOC Monitor from one config.

Concept: putting the layers together. One topology and one set of link settings are
shared by all nodes, so a link failure or a switch of framing method affects the
whole simulated network at once.

Only nodes whose ``host_ip`` belongs to this PC are started, so the same config.json
runs on one PC (everything on 127.0.0.1) or is split across two lab PCs. The
services (FTP, SMTP, dashboard) run on the PC that hosts the SOC.
"""

import logging
from pathlib import Path
from typing import Any

from config_loader import PROJECT_ROOT
from datalink.frame import FrameFormat, LinkSettings
from network.router import Router
from network.routing import shortest_path
from network.topology import Topology
from network.transport import is_local_address
from services.ftp_archive import FtpArchiveServer
from services.mailer import AlertMailer, Inbox, MailServer
from soc.collector import Collector
from soc.detector import AlertStore, Detector
from soc.firewall import Firewall
from soc.qos import TrafficPolicer
from soc.sensor import Sensor
from soc.state import SocState

logger = logging.getLogger("soc.system")

ALERTS_FILE = PROJECT_ROOT / "logs" / "alerts.jsonl"


class SocSystem:
    """All nodes of the simulated network plus the shared state they update."""

    def __init__(
        self, config: dict[str, Any], alerts_file: Path | None = ALERTS_FILE
    ) -> None:
        """Create (but do not start) every node described in the config."""
        self.config = config
        self.topology = Topology(config)
        self.settings = LinkSettings(
            FrameFormat.from_config(config["datalink"]),
            config["datalink"]["noise_error_rate"],
        )
        nodes = config["nodes"]
        self.sensor_ids = sorted(n for n, v in nodes.items() if v["role"] == "sensor")
        self.router_ids = sorted(n for n, v in nodes.items() if v["role"] == "router")
        self.collector_id = next(
            n for n, v in nodes.items() if v["role"] == "collector"
        )
        self.state = SocState(self.sensor_ids)
        self.alerts_file = alerts_file
        self.alerts = AlertStore(alerts_file)
        self.detector = Detector(config, self.alerts.add)
        self.firewall = Firewall(config["firewall"])
        flood_window = config["qos"]["flood_window_s"]
        self.policer = TrafficPolicer(
            config["qos"],
            lambda sensor, drops: self.detector.report_flooding(
                sensor, drops, flood_window
            ),
        )
        self.local_ids = {
            node_id
            for node_id, node in nodes.items()
            if is_local_address(node["host_ip"])
        }
        self.collector: Collector | None = None
        if self.collector_id in self.local_ids:
            self.collector = Collector(
                self.collector_id,
                config,
                self.topology,
                self.settings,
                self.state,
                self.firewall,
                self.policer,
                self.detector,
            )
        self.routers = {
            rid: Router(rid, config, self.topology, self.settings)
            for rid in self.router_ids
            if rid in self.local_ids
        }
        self.sensors = {
            sid: Sensor(sid, config, self.topology, self.settings, self.state)
            for sid in self.sensor_ids
            if sid in self.local_ids
        }
        services = config["services"]
        self.inbox = Inbox()
        self.mail_server = MailServer(services["smtp"], self.inbox)
        self.mailer = AlertMailer(services["smtp"])
        self.alerts.subscribe(self.mailer.on_alert)
        self.ftp_server = FtpArchiveServer(services["ftp"])
        self.running = False
        self._services_started = False

    @property
    def hosts_soc(self) -> bool:
        """True if the SOC collector (and so the services) runs on this PC."""
        return self.collector is not None

    def local_nodes(self) -> list[Any]:
        """Nodes started on this PC: collector, routers, then sensors."""
        nodes: list[Any] = [self.collector] if self.collector is not None else []
        return [*nodes, *self.routers.values(), *self.sensors.values()]

    def start(self) -> None:
        """Start the services, then the collector, routers and finally sensors."""
        if self.hosts_soc:
            self.mail_server.start()
            self.mailer.start()
            self.ftp_server.start()
            self._services_started = True
        for node in self.local_nodes():
            node.start()
        self.running = True
        logger.info("SOC system started with nodes %s", sorted(self.local_ids))

    def stop(self) -> None:
        """Stop in reverse order so no node sends to one that is already gone."""
        self.running = False
        for node in reversed(self.local_nodes()):
            node.stop()
        if self._services_started:
            self.mailer.stop()
            self.mail_server.stop()
            self.ftp_server.stop()
        logger.info("SOC system stopped")

    def routes(self) -> dict[str, dict[str, Any]]:
        """Current path and cost from every sensor to the SOC."""
        result: dict[str, dict[str, Any]] = {}
        for sensor_id in self.sensor_ids:
            path, cost = shortest_path(self.topology, sensor_id, self.collector_id)
            result[sensor_id] = {"path": path, "cost": cost if path else None}
        return result

    def services(self) -> list[tuple[str, str, int]]:
        """(name, host, port) for every service and node on this PC, for the banner."""
        rows: list[tuple[str, str, int]] = []
        if self.hosts_soc:
            services = self.config["services"]
            rows.append(
                ("FTP archive", services["ftp"]["host"], services["ftp"]["port"])
            )
            rows.append(
                ("SMTP mail server", services["smtp"]["host"], services["smtp"]["port"])
            )
        for node_id in [self.collector_id, *self.router_ids, *self.sensor_ids]:
            if node_id not in self.local_ids:
                continue
            node = self.config["nodes"][node_id]
            label = f"{node_id} {node['role']}"
            if node["role"] == "sensor":
                label = f"{node_id} sensor ({node['name']})"
            rows.append((label, node["host_ip"], node["port"]))
        return rows

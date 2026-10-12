"""Builds and wires every component of the SOC Monitor from one config.

Concept: putting the layers together. One topology and one set of link settings are
shared by all nodes, so a link failure or a switch of framing method affects the
whole simulated network at once.
"""

import logging
from pathlib import Path
from typing import Any

from config_loader import PROJECT_ROOT
from datalink.frame import FrameFormat, LinkSettings
from network.router import Router
from network.routing import shortest_path
from network.topology import Topology
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
        }
        self.sensors = {
            sid: Sensor(sid, config, self.topology, self.settings, self.state)
            for sid in self.sensor_ids
        }
        self.running = False

    def start(self) -> None:
        """Start the collector first, then routers, then sensors."""
        self.collector.start()
        for router in self.routers.values():
            router.start()
        for sensor in self.sensors.values():
            sensor.start()
        self.running = True
        logger.info("SOC system started")

    def stop(self) -> None:
        """Stop in reverse order so no node sends to one that is already gone."""
        self.running = False
        for sensor in self.sensors.values():
            sensor.stop()
        for router in self.routers.values():
            router.stop()
        self.collector.stop()
        logger.info("SOC system stopped")

    def routes(self) -> dict[str, dict[str, Any]]:
        """Current path and cost from every sensor to the SOC."""
        result: dict[str, dict[str, Any]] = {}
        for sensor_id in self.sensor_ids:
            path, cost = shortest_path(self.topology, sensor_id, self.collector_id)
            result[sensor_id] = {"path": path, "cost": cost if path else None}
        return result

    def services(self) -> list[tuple[str, str, int]]:
        """(name, host, port) for every node, for the startup banner."""
        rows: list[tuple[str, str, int]] = []
        for node_id in [self.collector_id, *self.router_ids, *self.sensor_ids]:
            node = self.config["nodes"][node_id]
            label = f"{node_id} {node['role']}"
            if node["role"] == "sensor":
                label = f"{node_id} sensor ({node['name']})"
            rows.append((label, node["host_ip"], node["port"]))
        return rows

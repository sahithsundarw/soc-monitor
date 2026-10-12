"""Base class for every simulated node: sensors, routers and the SOC collector.

Concept: hop-by-hop forwarding (Lab Week 12). A node never sends straight to the
final destination; it looks up the next hop in its forwarding table (built with
Dijkstra from the current topology) and hands the frame to that neighbour over a
link that may add noise.
"""

import logging
import random
import threading
from typing import Any

from datalink.frame import LinkSettings
from network.routing import build_forwarding_table
from network.topology import Topology
from network.transport import Address, FrameServer, send_tcp

logger = logging.getLogger("network.node")


class Node:
    """A network node with its own UDP/TCP port and a cached forwarding table."""

    def __init__(
        self,
        node_id: str,
        config: dict[str, Any],
        topology: Topology,
        settings: LinkSettings,
        rng: random.Random | None = None,
    ) -> None:
        """Bind the node's port (from config) and prepare its forwarding table."""
        self.node_id = node_id
        self.config = config
        self.info = config["nodes"][node_id]
        self.topology = topology
        self.settings = settings
        self.rng = rng or random.Random()
        self._table: dict[str, str] = {}
        self._table_version = -1
        self._table_lock = threading.Lock()
        self.server = FrameServer(
            node_id, self.info["host_ip"], self.info["port"], self.handle_frame
        )

    def start(self) -> None:
        """Start listening for frames."""
        self.server.start()

    def stop(self) -> None:
        """Stop listening and close the sockets."""
        self.server.stop()

    def handle_frame(self, wire: bytes, protocol: str) -> None:
        """Process one received frame; each node type overrides this."""
        raise NotImplementedError

    def address_of(self, node_id: str) -> Address:
        """Real (host_ip, port) of another node, from config.json."""
        node = self.config["nodes"][node_id]
        return node["host_ip"], node["port"]

    def sim_ip_of(self, node_id: str) -> str:
        """Logical IPv4 address of another node, as written in frame headers."""
        return self.config["nodes"][node_id]["sim_ip"]

    def next_hop(self, destination: str) -> str | None:
        """Look up the next hop, rebuilding the table if the topology changed."""
        with self._table_lock:
            version = self.topology.version
            if version != self._table_version:
                self._table = build_forwarding_table(self.topology, self.node_id)
                self._table_version = version
                logger.info("%s rebuilt its forwarding table", self.node_id)
            return self._table.get(destination)

    def transmit(self, wire: bytes, protocol: str, destination: str) -> bool:
        """Send a frame one hop towards ``destination``; False if it was dropped."""
        neighbor = self.next_hop(destination)
        if neighbor is None:
            logger.warning(
                "%s: no route to %s, frame dropped", self.node_id, destination
            )
            return False
        wire, damaged = self.settings.add_noise(wire, self.rng)
        if damaged:
            logger.info("Noise damaged a frame on link %s-%s", self.node_id, neighbor)
        try:
            if protocol == "udp":
                self.server.send_udp(wire, self.address_of(neighbor))
            else:
                send_tcp(wire, self.address_of(neighbor))
        except OSError as error:
            logger.warning(
                "%s: %s send to %s failed: %s", self.node_id, protocol, neighbor, error
            )
            return False
        return True

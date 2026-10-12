"""Weighted undirected network graph built from config.json.

Concept: a network topology modelled as a graph (Lab Week 14). Nodes are hosts and
routers, edges are links that carry a cost (the routing metric). Links can fail,
recover or change cost, which is why routers must recompute their routes.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("network.topology")

LinkKey = tuple[str, str]


@dataclass
class Link:
    """One bidirectional link: its cost and whether it is currently working."""

    cost: int
    up: bool = True


def link_key(a: str, b: str) -> LinkKey:
    """Return an order-independent key so (A, B) and (B, A) name the same link."""
    return (a, b) if a <= b else (b, a)


class Topology:
    """The network graph. Safe to share between router threads and the dashboard."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Build the graph from the ``nodes`` and ``links`` sections of the config."""
        self._lock = threading.Lock()
        self._roles = {
            node_id: node["role"] for node_id, node in config["nodes"].items()
        }
        self._links: dict[LinkKey, Link] = {}
        for entry in config["links"]:
            self._add_link(entry["a"], entry["b"], entry["cost"])

    def _add_link(self, a: str, b: str, cost: int) -> None:
        """Validate and store one link from the config."""
        for node_id in (a, b):
            if node_id not in self._roles:
                raise ValueError(f"Link {a}-{b} uses unknown node {node_id}")
        self._check_cost(cost)
        self._links[link_key(a, b)] = Link(cost=cost)

    @staticmethod
    def _check_cost(cost: int) -> None:
        """Reject link costs that Dijkstra cannot handle."""
        if cost <= 0:
            raise ValueError(f"Link cost must be positive, got {cost}")

    def _get_link(self, a: str, b: str) -> Link:
        """Look up a link or explain which one is missing."""
        try:
            return self._links[link_key(a, b)]
        except KeyError:
            raise ValueError(f"No link between {a} and {b}") from None

    def node_ids(self) -> list[str]:
        """Return all node ids in alphabetical order."""
        return sorted(self._roles)

    def can_forward(self, node_id: str) -> bool:
        """Only routers forward other nodes' traffic; hosts are leaves."""
        return self._roles[node_id] == "router"

    def neighbors(self, node_id: str) -> list[tuple[str, int]]:
        """Return (neighbor, cost) for every working link of ``node_id``."""
        found: list[tuple[str, int]] = []
        with self._lock:
            for (a, b), link in self._links.items():
                if not link.up:
                    continue
                if a == node_id:
                    found.append((b, link.cost))
                elif b == node_id:
                    found.append((a, link.cost))
        return sorted(found)

    def is_link_up(self, a: str, b: str) -> bool:
        """Return True if the link between ``a`` and ``b`` is working."""
        with self._lock:
            return self._get_link(a, b).up

    def fail_link(self, a: str, b: str) -> None:
        """Take a link down, as if the cable were cut."""
        with self._lock:
            self._get_link(a, b).up = False
        logger.info("Link %s-%s failed", a, b)

    def restore_link(self, a: str, b: str) -> None:
        """Bring a failed link back up."""
        with self._lock:
            self._get_link(a, b).up = True
        logger.info("Link %s-%s restored", a, b)

    def set_cost(self, a: str, b: str, cost: int) -> None:
        """Change a link's cost, e.g. to model congestion."""
        self._check_cost(cost)
        with self._lock:
            self._get_link(a, b).cost = cost
        logger.info("Link %s-%s cost set to %d", a, b, cost)

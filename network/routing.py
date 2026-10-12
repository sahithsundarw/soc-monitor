"""Shortest-path routing with Dijkstra's algorithm and forwarding tables.

Concept: link-state routing (Lab Week 14). Each router knows the whole topology,
runs Dijkstra to find the cheapest path to every destination, and keeps only the
first hop of each path as its forwarding table.
"""

import heapq
import math

from config_loader import load_config
from network.topology import Topology


def dijkstra(
    topology: Topology, source: str
) -> tuple[dict[str, float], dict[str, str]]:
    """Run Dijkstra from ``source``.

    Returns ``(distance, previous)``: the cheapest cost to every node, and for each
    reached node the node just before it on its cheapest path.
    """
    distance = {node_id: math.inf for node_id in topology.node_ids()}
    if source not in distance:
        raise ValueError(f"Unknown node {source}")
    previous: dict[str, str] = {}
    distance[source] = 0
    queue: list[tuple[float, str]] = [(0, source)]
    finished: set[str] = set()

    while queue:
        cost_so_far, current = heapq.heappop(queue)
        if current in finished:
            continue  # stale queue entry; a cheaper one was already processed
        finished.add(current)
        # Hosts are leaves: a path may end or start at one but never pass through.
        if current != source and not topology.can_forward(current):
            continue
        for neighbor, link_cost in topology.neighbors(current):
            new_cost = cost_so_far + link_cost
            if new_cost < distance[neighbor]:
                distance[neighbor] = new_cost
                previous[neighbor] = current
                heapq.heappush(queue, (new_cost, neighbor))

    return distance, previous


def rebuild_path(previous: dict[str, str], source: str, destination: str) -> list[str]:
    """Walk the ``previous`` links backwards to list the path source -> destination."""
    path = [destination]
    while path[-1] != source:
        path.append(previous[path[-1]])
    path.reverse()
    return path


def shortest_path(
    topology: Topology, source: str, destination: str
) -> tuple[list[str], float]:
    """Return ``(path, cost)``; an unreachable destination gives ``([], inf)``."""
    distance, previous = dijkstra(topology, source)
    if destination not in distance:
        raise ValueError(f"Unknown node {destination}")
    if distance[destination] == math.inf:
        return [], math.inf
    return rebuild_path(previous, source, destination), distance[destination]


def build_forwarding_table(topology: Topology, node: str) -> dict[str, str]:
    """Map each reachable destination to the next hop ``node`` should use."""
    distance, previous = dijkstra(topology, node)
    table: dict[str, str] = {}
    for destination, cost in distance.items():
        if destination == node or cost == math.inf:
            continue
        table[destination] = rebuild_path(previous, node, destination)[1]
    return table


def format_route(path: list[str], cost: float) -> str:
    """Return a printable route such as ``S1 -> R2 -> SOC (cost 2)``."""
    if not path:
        return "no route"
    return f"{' -> '.join(path)} (cost {cost})"


def print_forwarding_tables(topology: Topology) -> None:
    """Print every router's next hop per destination as an aligned grid."""
    destinations = topology.node_ids()
    print("  " + "".join(f"{name:>6}" for name in ["router"] + destinations))
    for router in destinations:
        if not topology.can_forward(router):
            continue
        table = build_forwarding_table(topology, router)
        row = "".join(f"{table.get(dest, '-'):>6}" for dest in destinations)
        print(f"  {router:>6}{row}")


def run_demo() -> None:
    """Show a route and forwarding tables, fail a link, and show them again."""
    topology = Topology(load_config())

    print("Before failure")
    print("  Route S1 -> SOC:", format_route(*shortest_path(topology, "S1", "SOC")))
    print_forwarding_tables(topology)

    print("\nFailing link R2-SOC")
    topology.fail_link("R2", "SOC")
    print("  Route S1 -> SOC:", format_route(*shortest_path(topology, "S1", "SOC")))
    print_forwarding_tables(topology)


if __name__ == "__main__":
    run_demo()

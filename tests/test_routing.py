"""Tests for Dijkstra routing and forwarding tables."""

import math
import unittest

from config_loader import load_config
from network.routing import build_forwarding_table, shortest_path
from network.topology import Topology


class ShortestPathTest(unittest.TestCase):
    """Dijkstra route selection, including failures and cost changes."""

    def setUp(self) -> None:
        self.topology = Topology(load_config())

    def test_default_route_s1_to_soc(self) -> None:
        path, cost = shortest_path(self.topology, "S1", "SOC")
        self.assertEqual(path, ["S1", "R2", "SOC"])
        self.assertEqual(cost, 2)

    def test_route_to_self_is_just_the_node(self) -> None:
        self.assertEqual(shortest_path(self.topology, "R1", "R1"), (["R1"], 0))

    def test_failed_link_reroutes_traffic(self) -> None:
        self.topology.fail_link("R2", "SOC")
        path, cost = shortest_path(self.topology, "S1", "SOC")
        self.assertEqual(path, ["S1", "R2", "R4", "SOC"])
        self.assertEqual(cost, 5)

    def test_restored_link_brings_back_original_route(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.topology.restore_link("R2", "SOC")
        path, _ = shortest_path(self.topology, "S1", "SOC")
        self.assertEqual(path, ["S1", "R2", "SOC"])

    def test_cost_change_moves_the_route(self) -> None:
        self.topology.set_cost("R2", "SOC", 10)
        path, cost = shortest_path(self.topology, "S1", "SOC")
        self.assertEqual(path, ["S1", "R2", "R4", "SOC"])
        self.assertEqual(cost, 5)

    def test_unreachable_destination(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.topology.fail_link("R4", "SOC")
        self.assertEqual(shortest_path(self.topology, "S1", "SOC"), ([], math.inf))

    def test_unknown_node_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            shortest_path(self.topology, "S1", "R9")

    def test_paths_never_pass_through_the_collector(self) -> None:
        self.topology.fail_link("R2", "R4")
        path, cost = shortest_path(self.topology, "R2", "R4")
        self.assertEqual(path, ["R2", "R1", "R3", "R4"])
        self.assertEqual(cost, 5)

    def test_paths_never_pass_through_a_sensor(self) -> None:
        self.topology.fail_link("R1", "R2")
        path, cost = shortest_path(self.topology, "R1", "R2")
        self.assertNotIn("S1", path)
        self.assertEqual(cost, 5)


class ForwardingTableTest(unittest.TestCase):
    """Next-hop tables derived from the shortest paths."""

    def setUp(self) -> None:
        self.topology = Topology(load_config())

    def test_next_hops_toward_soc(self) -> None:
        expected = {"R1": "R2", "R2": "SOC", "R3": "R4", "R4": "SOC"}
        for router, next_hop in expected.items():
            with self.subTest(router=router):
                table = build_forwarding_table(self.topology, router)
                self.assertEqual(table["SOC"], next_hop)

    def test_table_excludes_the_node_itself(self) -> None:
        self.assertNotIn("R1", build_forwarding_table(self.topology, "R1"))

    def test_table_covers_every_other_node(self) -> None:
        table = build_forwarding_table(self.topology, "R1")
        self.assertEqual(set(table), set(self.topology.node_ids()) - {"R1"})

    def test_failure_updates_the_tables(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.assertEqual(build_forwarding_table(self.topology, "R2")["SOC"], "R4")
        # R1 -> R3 -> R4 -> SOC costs 5; going via R2 would now cost 6.
        self.assertEqual(build_forwarding_table(self.topology, "R1")["SOC"], "R3")

    def test_unreachable_destination_is_left_out(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.topology.fail_link("R4", "SOC")
        table = build_forwarding_table(self.topology, "R1")
        self.assertNotIn("SOC", table)


if __name__ == "__main__":
    unittest.main()

"""Tests for the weighted network graph."""

import unittest

from config_loader import load_config
from network.topology import Topology


class TopologyTest(unittest.TestCase):
    """Link state, costs and validation."""

    def setUp(self) -> None:
        self.topology = Topology(load_config())

    def test_neighbors_lists_working_links_sorted(self) -> None:
        self.assertEqual(self.topology.neighbors("S1"), [("R1", 3), ("R2", 1)])

    def test_links_work_in_both_directions(self) -> None:
        self.assertIn(("S1", 1), self.topology.neighbors("R2"))

    def test_fail_link_removes_it_from_both_ends(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.assertFalse(self.topology.is_link_up("SOC", "R2"))
        self.assertNotIn("SOC", [n for n, _ in self.topology.neighbors("R2")])
        self.assertNotIn("R2", [n for n, _ in self.topology.neighbors("SOC")])

    def test_restore_link_brings_it_back(self) -> None:
        self.topology.fail_link("R2", "SOC")
        self.topology.restore_link("SOC", "R2")
        self.assertTrue(self.topology.is_link_up("R2", "SOC"))
        self.assertIn(("SOC", 1), self.topology.neighbors("R2"))

    def test_set_cost_changes_the_link(self) -> None:
        self.topology.set_cost("R2", "SOC", 7)
        self.assertIn(("SOC", 7), self.topology.neighbors("R2"))

    def test_set_cost_survives_fail_and_restore(self) -> None:
        self.topology.set_cost("R2", "SOC", 7)
        self.topology.fail_link("R2", "SOC")
        self.topology.restore_link("R2", "SOC")
        self.assertIn(("SOC", 7), self.topology.neighbors("R2"))

    def test_unknown_link_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.topology.fail_link("S1", "SOC")

    def test_non_positive_cost_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.topology.set_cost("R2", "SOC", 0)

    def test_only_routers_forward(self) -> None:
        self.assertTrue(self.topology.can_forward("R1"))
        self.assertFalse(self.topology.can_forward("S1"))
        self.assertFalse(self.topology.can_forward("SOC"))

    def test_config_link_to_unknown_node_is_rejected(self) -> None:
        config = load_config()
        config["links"].append({"a": "S1", "b": "R9", "cost": 1})
        with self.assertRaises(ValueError):
            Topology(config)


if __name__ == "__main__":
    unittest.main()

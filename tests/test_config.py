"""Tests that config.json describes a valid, self-consistent network."""

import ipaddress
import unittest

from config_loader import load_config

REQUIRED_NODES = {"S1", "S2", "S3", "R1", "R2", "R3", "R4", "SOC"}


class ConfigTest(unittest.TestCase):
    """Sanity checks on the default config.json."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config()
        cls.nodes = cls.config["nodes"]

    def test_required_nodes_present(self) -> None:
        self.assertTrue(REQUIRED_NODES.issubset(self.nodes))

    def test_node_addresses_are_valid_ipv4(self) -> None:
        for node_id, node in self.nodes.items():
            with self.subTest(node=node_id):
                ipaddress.IPv4Address(node["host_ip"])
                ipaddress.IPv4Address(node["sim_ip"])

    def test_ports_unique_per_host(self) -> None:
        endpoints = [(node["host_ip"], node["port"]) for node in self.nodes.values()]
        self.assertEqual(len(endpoints), len(set(endpoints)))

    def test_links_reference_known_nodes_with_positive_cost(self) -> None:
        for link in self.config["links"]:
            with self.subTest(link=link):
                self.assertIn(link["a"], self.nodes)
                self.assertIn(link["b"], self.nodes)
                self.assertGreater(link["cost"], 0)

    def test_firewall_subnets_parse(self) -> None:
        for rule in self.config["firewall"]["rules"]:
            if rule["src"] != "any":
                with self.subTest(rule=rule):
                    ipaddress.ip_network(rule["src"])

    def test_every_sensor_has_token_bucket(self) -> None:
        sensors = {nid for nid, node in self.nodes.items() if node["role"] == "sensor"}
        self.assertEqual(sensors, set(self.config["qos"]["buckets"]))


if __name__ == "__main__":
    unittest.main()

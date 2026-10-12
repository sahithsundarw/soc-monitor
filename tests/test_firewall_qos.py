"""Tests for the ACL firewall and the token bucket policer."""

import unittest

from config_loader import load_config
from soc.firewall import Firewall
from soc.qos import TokenBucket, TrafficPolicer


class FirewallTest(unittest.TestCase):
    """First match wins; default policy otherwise."""

    def setUp(self) -> None:
        self.firewall = Firewall(load_config()["firewall"])

    def test_denied_subnet(self) -> None:
        allowed, reason = self.firewall.decide("203.0.113.66", 9300, "udp")
        self.assertFalse(allowed)
        self.assertIn("rule 1", reason)

    def test_port_and_protocol_rule(self) -> None:
        self.assertFalse(self.firewall.decide("192.168.1.10", 23, "tcp")[0])
        self.assertTrue(self.firewall.decide("192.168.1.10", 23, "udp")[0])

    def test_allowed_subnet(self) -> None:
        self.assertTrue(self.firewall.decide("192.168.1.10", 9300, "udp")[0])

    def test_first_match_wins(self) -> None:
        firewall = Firewall(
            {
                "default_policy": "deny",
                "rules": [
                    {
                        "action": "allow",
                        "src": "10.0.0.5/32",
                        "dst_port": "any",
                        "protocol": "any",
                    },
                    {
                        "action": "deny",
                        "src": "10.0.0.0/8",
                        "dst_port": "any",
                        "protocol": "any",
                    },
                ],
            }
        )
        self.assertTrue(firewall.decide("10.0.0.5", 1, "tcp")[0])
        self.assertFalse(firewall.decide("10.0.0.6", 1, "tcp")[0])

    def test_default_policy(self) -> None:
        firewall = Firewall({"default_policy": "deny", "rules": []})
        allowed, reason = firewall.decide("1.2.3.4", 80, "tcp")
        self.assertFalse(allowed)
        self.assertIn("default", reason)

    def test_blocks_are_counted(self) -> None:
        self.firewall.check("203.0.113.66", 9300, "udp", 1.0)
        self.firewall.check("203.0.113.66", 9300, "udp", 2.0)
        self.firewall.check("192.168.1.10", 9300, "udp", 3.0)
        stats = self.firewall.stats()
        self.assertEqual((stats["blocked"], stats["allowed"]), (2, 1))
        self.assertEqual(stats["blocked_by_source"], {"203.0.113.66": 2})

    def test_invalid_rule_action(self) -> None:
        with self.assertRaises(ValueError):
            Firewall(
                {
                    "default_policy": "allow",
                    "rules": [
                        {
                            "action": "maybe",
                            "src": "any",
                            "dst_port": "any",
                            "protocol": "any",
                        }
                    ],
                }
            )


class TokenBucketTest(unittest.TestCase):
    """Bursts up to the bucket size, then the fill rate."""

    def test_burst_then_rate(self) -> None:
        bucket = TokenBucket(rate=5, size=10, now=0.0)
        self.assertEqual(sum(bucket.allow(0.0) for _ in range(15)), 10)
        self.assertFalse(bucket.allow(0.1))
        self.assertTrue(bucket.allow(0.3))  # 0.3 s at 5 tokens/s refilled 1.5 tokens

    def test_never_exceeds_size(self) -> None:
        bucket = TokenBucket(rate=5, size=10, now=0.0)
        self.assertEqual(sum(bucket.allow(1000.0) for _ in range(20)), 10)


class PolicerTest(unittest.TestCase):
    """Per-sensor policing, flood callback and timeline."""

    def setUp(self) -> None:
        self.floods: list[tuple[str, int]] = []
        self.policer = TrafficPolicer(
            load_config()["qos"], lambda s, d: self.floods.append((s, d)), now=0.0
        )

    def test_flood_raises_callback(self) -> None:
        for _ in range(40):
            self.policer.allow("S1", now=1.0)
        self.assertEqual(self.policer.totals()["S1"], {"allowed": 10, "dropped": 30})
        self.assertEqual(self.floods[0], ("S1", 20))

    def test_other_sensors_unaffected(self) -> None:
        for _ in range(40):
            self.policer.allow("S1", now=1.0)
        self.assertTrue(self.policer.allow("S2", now=1.0))

    def test_unknown_sender_is_dropped(self) -> None:
        self.assertFalse(self.policer.allow("EXT", now=1.0))

    def test_timeline_has_sixty_seconds(self) -> None:
        self.policer.allow("S1", now=100.2)
        timeline = self.policer.timeline(now=100.9)
        self.assertEqual(len(timeline), 60)
        self.assertEqual(timeline[-1], {"t": 100, "allowed": 1, "dropped": 0})
        self.assertEqual(timeline[0]["allowed"], 0)


if __name__ == "__main__":
    unittest.main()

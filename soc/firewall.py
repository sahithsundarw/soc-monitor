"""Packet-filtering firewall at the SOC entrance.

Concept: an access control list (ACL). Rules are checked in order and the first rule
that matches decides (allow or deny); if none matches, the default policy applies.
Rules match on source IP or subnet, destination port and protocol.
"""

import ipaddress
import logging
import threading
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("soc.firewall")

RECENT_BLOCK_LIMIT = 20
ANY = "any"

IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class Rule:
    """One ACL line. ``None`` in a field means "any"."""

    action: str
    src: IPNetwork | None
    dst_port: int | None
    protocol: str | None

    @classmethod
    def from_config(cls, entry: dict[str, Any]) -> "Rule":
        """Parse one rule from config.json."""
        if entry["action"] not in ("allow", "deny"):
            raise ValueError(f"Rule action must be allow or deny: {entry}")
        src = None if entry["src"] == ANY else ipaddress.ip_network(entry["src"])
        port = None if entry["dst_port"] == ANY else int(entry["dst_port"])
        protocol = None if entry["protocol"] == ANY else entry["protocol"].lower()
        return cls(entry["action"], src, port, protocol)

    def matches(self, src_ip: str, dst_port: int, protocol: str) -> bool:
        """True if every field of the rule matches the packet."""
        if self.protocol is not None and self.protocol != protocol:
            return False
        if self.dst_port is not None and self.dst_port != dst_port:
            return False
        if self.src is None:
            return True
        try:
            return ipaddress.ip_address(src_ip) in self.src
        except ValueError:
            return False  # not an IP address at all: only "any" rules match

    def describe(self) -> str:
        """Readable form, e.g. "deny src 203.0.113.0/24 port any proto any"."""
        src = str(self.src) if self.src else ANY
        port = str(self.dst_port) if self.dst_port is not None else ANY
        return f"{self.action} src {src} port {port} proto {self.protocol or ANY}"


class Firewall:
    """Ordered ACL with counters of what it blocked."""

    def __init__(self, firewall_config: dict[str, Any]) -> None:
        """Load the rules and default policy from the ``firewall`` config section."""
        self.default_policy = firewall_config["default_policy"]
        self.rules = [Rule.from_config(entry) for entry in firewall_config["rules"]]
        self._lock = threading.Lock()
        self._allowed = 0
        self._blocked_by_source: Counter[str] = Counter()
        self._recent: deque[dict[str, Any]] = deque(maxlen=RECENT_BLOCK_LIMIT)

    def decide(self, src_ip: str, dst_port: int, protocol: str) -> tuple[bool, str]:
        """First match wins. Returns (allowed, reason)."""
        for number, rule in enumerate(self.rules, start=1):
            if rule.matches(src_ip, dst_port, protocol):
                return rule.action == "allow", f"rule {number}: {rule.describe()}"
        return self.default_policy == "allow", f"default policy: {self.default_policy}"

    def check(
        self, src_ip: str, dst_port: int, protocol: str, now: float
    ) -> tuple[bool, str]:
        """Decide, count and log one packet. Returns (allowed, reason)."""
        allowed, reason = self.decide(src_ip, dst_port, protocol)
        with self._lock:
            if allowed:
                self._allowed += 1
                return True, reason
            self._blocked_by_source[src_ip] += 1
            self._recent.appendleft(
                {
                    "ts": round(now, 3),
                    "src_ip": src_ip,
                    "protocol": protocol,
                    "reason": reason,
                }
            )
        logger.info("Firewall blocked %s %s (%s)", protocol, src_ip, reason)
        return False, reason

    def stats(self) -> dict[str, Any]:
        """Totals, blocks per source and the latest blocked packets."""
        with self._lock:
            return {
                "allowed": self._allowed,
                "blocked": sum(self._blocked_by_source.values()),
                "blocked_by_source": dict(self._blocked_by_source),
                "recent": list(self._recent),
                "rules": [rule.describe() for rule in self.rules],
                "default_policy": self.default_policy,
            }

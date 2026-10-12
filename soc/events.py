"""Security event generators for the simulated sensors.

Concept: application-layer telemetry. Sensors report what they see as small JSON
events. Normal traffic is routine; attack mode produces bursts (failed SSH logins,
a port scan, malware beacons) that the SOC detector should recognise.
"""

import itertools
import random
import time
from typing import Any

from datalink.frame import PRIORITY_CRITICAL, PRIORITY_HIGH, PRIORITY_NORMAL

Event = dict[str, Any]

EVENT_PRIORITY = {
    "connection_allowed": PRIORITY_NORMAL,
    "http_request": PRIORITY_NORMAL,
    "dns_query": PRIORITY_NORMAL,
    "login_success": PRIORITY_NORMAL,
    "failed_login": PRIORITY_HIGH,
    "port_probe": PRIORITY_HIGH,
    "beacon": PRIORITY_CRITICAL,
}

NORMAL_TYPES_BY_KIND = {
    "firewall": ["connection_allowed", "http_request"],
    "ids": ["dns_query", "http_request"],
    "auth_server": ["login_success"],
}

COMMON_PORTS = [22, 53, 80, 443, 3389, 8080]
USERS = ["alice", "bob", "carol", "dave"]

BRUTE_FORCE_IP = "192.168.1.55"
BRUTE_FORCE_USER = "root"
BRUTE_FORCE_ATTEMPTS = 8
PORT_SCAN_IP = "198.51.100.23"
PORT_SCAN_PORTS = list(range(20, 36))
BEACON_HOST = "192.168.1.21"
BEACON_C2 = "198.51.100.77"
BEACON_COUNT = 6
BEACON_INTERVAL_S = 1.0


def priority_of(event: Event) -> int:
    """Frame priority for an event: 0 normal, 1 high, 2 critical."""
    return EVENT_PRIORITY.get(event["type"], PRIORITY_NORMAL)


class EventFactory:
    """Builds events for one sensor, each with a unique id."""

    def __init__(
        self,
        sensor_name: str,
        kind: str,
        known_hosts: list[str],
        rng: random.Random | None = None,
    ) -> None:
        """``kind`` is firewall, ids or auth_server; ``known_hosts`` are local IPs."""
        self.sensor_name = sensor_name
        self.kind = kind
        self.known_hosts = known_hosts
        self.rng = rng or random.Random()
        self._counter = itertools.count(1)

    def make(self, event_type: str, src_ip: str, **fields: Any) -> Event:
        """Build one event dictionary with a timestamp and a unique id."""
        event: Event = {
            "id": f"{self.sensor_name}-{next(self._counter)}",
            "ts": round(time.time(), 3),
            "sensor": self.sensor_name,
            "type": event_type,
            "src_ip": src_ip,
        }
        event.update(fields)
        return event

    def normal(self) -> Event:
        """One routine event typical for this kind of sensor."""
        event_type = self.rng.choice(NORMAL_TYPES_BY_KIND[self.kind])
        src_ip = self.rng.choice(self.known_hosts)
        if event_type == "login_success":
            return self.make(
                event_type, src_ip, user=self.rng.choice(USERS), dst_port=22
            )
        return self.make(event_type, src_ip, dst_port=self.rng.choice(COMMON_PORTS))

    def failed_logins(self) -> list[Event]:
        """Attack burst: repeated failed SSH logins for root from one IP."""
        return [
            self.make(
                "failed_login", BRUTE_FORCE_IP, user=BRUTE_FORCE_USER, dst_port=22
            )
            for _ in range(BRUTE_FORCE_ATTEMPTS)
        ]

    def port_scan(self) -> list[Event]:
        """Attack burst: one IP probing many different ports."""
        return [
            self.make("port_probe", PORT_SCAN_IP, dst_port=port)
            for port in PORT_SCAN_PORTS
        ]

    def beacon(self) -> Event:
        """One malware beacon: an infected host calling its C2 server."""
        return self.make("beacon", BEACON_HOST, dst_ip=BEACON_C2, dst_port=443)

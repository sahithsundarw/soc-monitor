"""SOC collector: receive frames, check integrity, ACK/NAK, and record events.

Concept: the receiving end of the data link (Lab Week 12). For every frame the
collector finds the flags, destuffs, splits, verifies the CRC and parses. A damaged
frame raises an integrity warning and is NAKed so the sensor retransmits. A good
frame then passes the firewall and the token bucket, is ACKed (Stop-and-Wait ARQ)
and its event goes to the detector. Blocked and policed frames are dropped
silently, as a real firewall would, so they are never ACKed.
"""

import logging
import random
import time
from dataclasses import asdict
from typing import Any

from datalink.arq import StopAndWaitReceiver, make_ack, make_nak
from datalink.frame import (
    Frame,
    FrameError,
    Header,
    LinkSettings,
    decode_frame,
    encode_frame,
)
from network.node import Node
from network.routing import shortest_path
from network.topology import Topology
from soc.detector import Detector
from soc.firewall import Firewall
from soc.qos import TrafficPolicer
from soc.state import UNKNOWN_SENDER, SocState

logger = logging.getLogger("soc.collector")


class Collector(Node):
    """The SOC node: TCP and UDP servers on the collector's port."""

    def __init__(
        self,
        node_id: str,
        config: dict[str, Any],
        topology: Topology,
        settings: LinkSettings,
        state: SocState,
        firewall: Firewall,
        policer: TrafficPolicer,
        detector: Detector,
        rng: random.Random | None = None,
    ) -> None:
        """Prepare duplicate detection and remember which nodes are sensors."""
        super().__init__(node_id, config, topology, settings, rng)
        self.state = state
        self.firewall = firewall
        self.policer = policer
        self.detector = detector
        self.receiver = StopAndWaitReceiver()
        self.sensor_ids = [
            nid for nid, node in config["nodes"].items() if node["role"] == "sensor"
        ]

    def current_route(self, sensor_id: str) -> list[str]:
        """Path that frames from ``sensor_id`` take right now (empty if cut off)."""
        path, _ = shortest_path(self.topology, sensor_id, self.node_id)
        return path

    def arrival_link(self, sensor_id: str) -> str:
        """Name of the last link on the sensor's route, e.g. "R2-SOC"."""
        path = self.current_route(sensor_id) if sensor_id in self.sensor_ids else []
        return f"{path[-2]}-{self.node_id}" if len(path) >= 2 else UNKNOWN_SENDER

    def handle_frame(self, wire: bytes, protocol: str) -> None:
        """Run one received frame through the receive pipeline."""
        try:
            received = decode_frame(wire, self.settings.frame_format)
        except FrameError as error:
            self.state.count(UNKNOWN_SENDER, protocol, "corrupted")
            logger.warning("Integrity alert: frame could not be delimited (%s)", error)
            return
        if not received.crc_ok:
            self.on_corrupted(received.header, protocol)
            return
        frame = received.frame
        if frame is None or frame.header.frame_type != "DATA":
            return
        self.on_data(frame, protocol, wire)

    def on_corrupted(self, header: Header | None, protocol: str) -> None:
        """CRC failed: count it, log an integrity alert and NAK if we know the sender."""
        sender = header.src_id if header else UNKNOWN_SENDER
        self.state.count(sender, protocol, "corrupted")
        self.detector.record_crc_failure(self.arrival_link(sender))
        if header is None or header.frame_type != "DATA":
            logger.warning(
                "Integrity alert: CRC failed, sender unknown, no NAK possible"
            )
            return
        logger.warning(
            "Integrity alert: CRC failed on frame from %s seq=%d, sending NAK",
            sender,
            header.seq_no,
        )
        self.reply(make_nak(header, self.default_ttl), protocol)

    def passes_entrance(self, header: Header, protocol: str) -> bool:
        """Firewall first (by source IP, port, protocol), then the token bucket."""
        now = time.time()
        allowed, reason = self.firewall.check(
            header.src_ip, self.info["port"], protocol, now
        )
        if not allowed:
            self.detector.report_firewall_block(header.src_ip, reason)
            return False
        if not self.policer.allow(header.src_id, now):
            logger.info("Token bucket dropped a frame from %s", header.src_id)
            return False
        return True

    def on_data(self, frame: Frame, protocol: str, wire: bytes) -> None:
        """Good DATA frame: police it, ACK it, then process it unless duplicate."""
        header = frame.header
        if not self.passes_entrance(header, protocol):
            return
        self.reply(make_ack(frame, self.default_ttl), protocol)
        if not self.receiver.is_new(frame):
            logger.info(
                "Duplicate seq=%d from %s re-ACKed, not processed",
                header.seq_no,
                header.src_id,
            )
            return
        self.state.count(header.src_id, protocol, "good")
        self.state.add_event(self.event_record(frame, protocol, wire))
        self.detector.process_event(frame.payload)

    @property
    def default_ttl(self) -> int:
        """TTL for frames the collector originates (ACK/NAK)."""
        return self.config["datalink"]["default_ttl"]

    def reply(self, frame: Frame, protocol: str) -> None:
        """Send an ACK/NAK back towards the sensor over the same protocol."""
        wire = encode_frame(frame, self.settings.frame_format).wire
        self.transmit(wire, protocol, frame.header.dst_id)

    def event_record(self, frame: Frame, protocol: str, wire: bytes) -> dict[str, Any]:
        """Everything the Packet Inspector needs to show this event layer by layer."""
        header = frame.header
        frame_format = self.settings.frame_format
        sensor_port = self.config["nodes"].get(header.src_id, {}).get("port")
        return {
            "id": frame.payload.get("id"),
            "received_at": round(time.time(), 3),
            "payload": frame.payload,
            "protocol": protocol,
            "src_port": sensor_port,
            "dst_port": self.info["port"],
            "header": asdict(header),
            "hops": self.default_ttl - header.ttl,
            "path": (
                self.current_route(header.src_id)
                if header.src_id in self.sensor_ids
                else []
            ),
            "method": frame_format.method,
            "crc_type": frame_format.crc_type,
            "wire_hex": wire.hex(),
        }

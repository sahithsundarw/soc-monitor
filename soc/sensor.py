"""Sensor: turn security events into frames and send them towards the SOC.

Concept: an end host on the network (Lab Week 12). Each sensor runs on its own port,
sends routine events over UDP and HIGH/CRITICAL events over TCP, and uses
Stop-and-Wait ARQ so that every event is acknowledged or retransmitted.
"""

import logging
import random
import threading
import time
from typing import Any

from datalink.arq import StopAndWaitSender
from datalink.frame import (
    PRIORITY_NORMAL,
    Frame,
    FrameError,
    Header,
    LinkSettings,
    decode_frame,
    encode_frame,
)
from network.node import Node
from network.topology import Topology
from soc.events import BEACON_COUNT, BEACON_INTERVAL_S, Event, EventFactory, priority_of
from soc.state import SocState

logger = logging.getLogger("soc.sensor")

COLLECTOR_ID = "SOC"
ATTACKS = ("brute_force", "port_scan", "beacon")


def protocol_for(priority: int) -> str:
    """Routine events use UDP; HIGH/CRITICAL events need TCP's reliable delivery."""
    return "udp" if priority == PRIORITY_NORMAL else "tcp"


class Sensor(Node):
    """A security sensor (firewall, IDS or auth server) that reports to the SOC."""

    def __init__(
        self,
        node_id: str,
        config: dict[str, Any],
        topology: Topology,
        settings: LinkSettings,
        state: SocState,
        rng: random.Random | None = None,
    ) -> None:
        """Set up the event factory and the Stop-and-Wait sender."""
        super().__init__(node_id, config, topology, settings, rng)
        self.state = state
        self.factory = EventFactory(
            self.info["name"], self.info["kind"], config["known_hosts"], self.rng
        )
        self.arq = StopAndWaitSender(
            node_id,
            self._send_frame,
            config["arq"]["timeout_s"],
            config["arq"]["max_retries"],
        )
        self.interval_s = config["sensors"]["event_interval_s"]
        self._send_lock = threading.Lock()  # Stop-and-Wait: one frame at a time
        self._stop = threading.Event()
        self._loop: threading.Thread | None = None

    def start(self) -> None:
        """Start listening for ACK/NAKs and generating routine events."""
        super().start()
        self._loop = threading.Thread(
            target=self._event_loop, name=f"{self.node_id}-events", daemon=True
        )
        self._loop.start()

    def stop(self) -> None:
        """Stop generating events, then close the sockets."""
        self._stop.set()
        if self._loop is not None:
            self._loop.join(timeout=5)
        super().stop()

    def _event_loop(self) -> None:
        """Send one routine event roughly every ``interval_s`` seconds."""
        while not self._stop.wait(self.interval_s * self.rng.uniform(0.5, 1.5)):
            self.send_event(self.factory.normal())

    def build_frame(self, event: Event, seq_no: int = 0, src_ip: str = "") -> Frame:
        """Wrap an event in a DATA frame addressed to the SOC."""
        header = Header(
            src_id=self.node_id,
            dst_id=COLLECTOR_ID,
            src_ip=src_ip or self.info["sim_ip"],
            dst_ip=self.sim_ip_of(COLLECTOR_ID),
            seq_no=seq_no,
            frame_type="DATA",
            ttl=self.config["datalink"]["default_ttl"],
            priority=priority_of(event),
        )
        return Frame(header, event)

    def _send_frame(self, frame: Frame) -> None:
        """Encode a frame with the current link settings and send it one hop."""
        wire = encode_frame(frame, self.settings.frame_format).wire
        self.transmit(wire, protocol_for(frame.header.priority), COLLECTOR_ID)

    def send_event(self, event: Event) -> bool:
        """Send one event reliably with Stop-and-Wait; True if it was ACKed."""
        frame = self.build_frame(event)
        protocol = protocol_for(frame.header.priority)
        with self._send_lock:
            result = self.arq.send(frame)
        if result.retransmissions:
            self.state.count(
                self.node_id, protocol, "retransmitted", result.retransmissions
            )
        if not result.delivered:
            self.state.count(self.node_id, protocol, "lost")
        return result.delivered

    def launch(self, attack: str) -> threading.Thread:
        """Start an attack burst in the background and return its thread."""
        if attack not in ATTACKS:
            raise ValueError(f"Unknown attack {attack!r}")
        thread = threading.Thread(
            target=self._run_attack,
            args=(attack,),
            name=f"{self.node_id}-{attack}",
            daemon=True,
        )
        thread.start()
        return thread

    def _run_attack(self, attack: str) -> None:
        """Send the events of one attack burst through ARQ."""
        logger.info("%s launching %s", self.node_id, attack)
        if attack == "brute_force":
            events = self.factory.failed_logins()
        elif attack == "port_scan":
            events = self.factory.port_scan()
        else:
            for _ in range(BEACON_COUNT):
                self.send_event(self.factory.beacon())
                time.sleep(BEACON_INTERVAL_S)
            return
        for event in events:
            self.send_event(event)

    def flood(self, count: int, spoof_ip: str = "") -> None:
        """Misbehave on purpose: blast ``count`` frames with no ARQ waiting.

        A flooding sensor ignores Stop-and-Wait, which is exactly what the SOC's
        token bucket is there to police. With ``spoof_ip`` the frames carry a forged
        source address, which the SOC firewall should block.
        """
        logger.info(
            "%s flooding %d frames (spoofed source: %s)",
            self.node_id,
            count,
            spoof_ip or "no",
        )
        for index in range(count):
            frame = self.build_frame(self.factory.normal(), index % 2, spoof_ip)
            self._send_frame(frame)

    def handle_frame(self, wire: bytes, protocol: str) -> None:
        """Pass intact ACK/NAK frames addressed to this sensor to the ARQ sender."""
        try:
            received = decode_frame(wire, self.settings.frame_format)
        except FrameError:
            logger.info("%s ignored an undelimitable reply", self.node_id)
            return
        if not received.crc_ok or received.frame is None:
            logger.info("%s ignored a damaged reply; ARQ will time out", self.node_id)
            return
        header = received.frame.header
        if header.dst_id == self.node_id and header.frame_type in ("ACK", "NAK"):
            self.arq.on_reply(received.frame)

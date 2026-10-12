"""Stop-and-Wait ARQ between each sensor and the SOC collector.

Concept: automatic repeat request (Lab Week 12, Forouzan Ch. 11). The sender keeps
one frame outstanding, numbered 0 or 1. It waits for an ACK; a NAK or a timeout
makes it retransmit the same frame, up to a retry limit. The receiver ACKs good
frames, NAKs damaged ones, and recognises a retransmitted duplicate so the event is
not processed twice.
"""

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from datalink.frame import Frame, Header

logger = logging.getLogger("datalink.arq")

Transmit = Callable[[Frame], None]


@dataclass(frozen=True)
class SendResult:
    """Outcome of sending one frame: delivered or lost, and how many resends."""

    delivered: bool
    retransmissions: int


def reply_header(data_header: Header, frame_type: str, ttl: int) -> Header:
    """Header for an ACK/NAK: addresses swapped, same sequence number and priority."""
    return Header(
        src_id=data_header.dst_id,
        dst_id=data_header.src_id,
        src_ip=data_header.dst_ip,
        dst_ip=data_header.src_ip,
        seq_no=data_header.seq_no,
        frame_type=frame_type,
        ttl=ttl,
        priority=data_header.priority,
    )


def make_ack(data_frame: Frame, ttl: int) -> Frame:
    """ACK n acknowledges data frame n; it also names the event it confirms."""
    header = reply_header(data_frame.header, "ACK", ttl)
    return Frame(header, {"ack_for": data_frame.payload.get("id")})


def make_nak(data_header: Header, ttl: int) -> Frame:
    """NAK n asks the sender to retransmit frame n (its payload was damaged)."""
    return Frame(reply_header(data_header, "NAK", ttl), {})


class StopAndWaitSender:
    """Sender side: one outstanding frame, alternating sequence numbers 0 and 1."""

    def __init__(
        self, name: str, transmit: Transmit, timeout_s: float, max_retries: int
    ) -> None:
        """``transmit(frame)`` puts a frame on the network; replies come back via
        :meth:`on_reply`."""
        self.name = name
        self._transmit = transmit
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self._seq_no = 0
        self._replies: queue.Queue[Frame] = queue.Queue()

    @property
    def seq_no(self) -> int:
        """Sequence number the next new frame will carry."""
        return self._seq_no

    def on_reply(self, frame: Frame) -> None:
        """Called by the receive thread for every intact ACK/NAK addressed to us."""
        self._replies.put(frame)

    def send(self, frame: Frame) -> SendResult:
        """Send ``frame`` and block until it is ACKed or the retries run out."""
        frame = replace(frame, header=replace(frame.header, seq_no=self._seq_no))
        event_id = frame.payload.get("id")
        self._drain_old_replies()
        retransmissions = 0
        while True:
            self._transmit(frame)
            label = "Retransmit" if retransmissions else "Send"
            logger.info(
                "%s %s frame seq=%d id=%s", self.name, label, self._seq_no, event_id
            )
            verdict = self._wait_for_reply(event_id)
            if verdict == "ACK":
                logger.info("%s got ACK seq=%d", self.name, self._seq_no)
                self._seq_no = 1 - self._seq_no
                return SendResult(delivered=True, retransmissions=retransmissions)
            if verdict == "NAK":
                logger.info("%s got NAK seq=%d", self.name, self._seq_no)
            else:
                logger.info("%s timeout waiting for seq=%d", self.name, self._seq_no)
            if retransmissions == self._max_retries:
                logger.warning(
                    "%s gave up on seq=%d id=%s", self.name, self._seq_no, event_id
                )
                self._seq_no = 1 - self._seq_no  # move on to the next frame
                return SendResult(delivered=False, retransmissions=retransmissions)
            retransmissions += 1

    def _drain_old_replies(self) -> None:
        """Discard late replies to earlier frames before starting a new one."""
        while not self._replies.empty():
            self._replies.get_nowait()

    def _wait_for_reply(self, event_id: Any) -> str:
        """Wait up to the timeout for a matching ACK/NAK; return "ACK", "NAK" or
        "TIMEOUT". Replies for other sequence numbers or events are ignored."""
        deadline = time.monotonic() + self._timeout_s
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "TIMEOUT"
            try:
                reply = self._replies.get(timeout=remaining)
            except queue.Empty:
                return "TIMEOUT"
            if reply.header.seq_no != self._seq_no:
                continue
            if reply.header.frame_type == "NAK":
                return "NAK"
            if reply.payload.get("ack_for") == event_id:
                return "ACK"


class StopAndWaitReceiver:
    """Receiver side: remembers the last accepted frame from each sender."""

    def __init__(self) -> None:
        """Start with no history for any sender."""
        self._lock = threading.Lock()
        self._last: dict[str, tuple[int, str]] = {}

    def is_new(self, frame: Frame) -> bool:
        """True for a new frame; False for a retransmitted copy of the last one.

        A retransmission is an exact copy, so it has the same sequence number and the
        same payload as the frame accepted before it. It must still be ACKed (the
        first ACK was probably lost) but not processed again.
        """
        sender = frame.header.src_id
        fingerprint = (frame.header.seq_no, repr(sorted(frame.payload.items())))
        with self._lock:
            if self._last.get(sender) == fingerprint:
                return False
            self._last[sender] = fingerprint
            return True

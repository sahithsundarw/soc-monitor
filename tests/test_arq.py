"""Tests for Stop-and-Wait ARQ (sender and receiver) without real sockets."""

import threading
import unittest

from datalink.arq import StopAndWaitReceiver, StopAndWaitSender, make_ack, make_nak
from datalink.frame import Frame, Header

HEADER = Header("S1", "SOC", "192.168.1.10", "10.0.0.1", 0, "DATA", 16, 0)


def data_frame(event_id: str) -> Frame:
    """A DATA frame carrying a minimal event."""
    return Frame(HEADER, {"id": event_id})


class FakeLink:
    """Records sent frames and answers each one according to a script."""

    def __init__(self, script: list[str]) -> None:
        self.script = script  # "ACK", "NAK", "STRAY" or "DROP" per transmission
        self.sent: list[Frame] = []
        self.sender: StopAndWaitSender | None = None

    def transmit(self, frame: Frame) -> None:
        self.sent.append(frame)
        action = self.script.pop(0) if self.script else "DROP"
        assert self.sender is not None
        if action == "ACK":
            reply = make_ack(frame, 16)
        elif action == "NAK":
            reply = make_nak(frame.header, 16)
        elif action == "STRAY":
            reply = make_ack(data_frame("some-other-event"), 16)
        else:
            return
        threading.Timer(0.01, self.sender.on_reply, args=(reply,)).start()


def make_sender(
    script: list[str], max_retries: int = 3
) -> tuple[StopAndWaitSender, FakeLink]:
    """A sender wired to a scripted fake link with a short timeout."""
    link = FakeLink(script)
    sender = StopAndWaitSender(
        "S1", link.transmit, timeout_s=0.1, max_retries=max_retries
    )
    link.sender = sender
    return sender, link


class SenderTest(unittest.TestCase):
    """ACK, NAK, timeout and retry limit."""

    def test_ack_delivers_and_toggles_sequence(self) -> None:
        sender, link = make_sender(["ACK", "ACK"])
        self.assertTrue(sender.send(data_frame("a")).delivered)
        self.assertEqual(sender.seq_no, 1)
        sender.send(data_frame("b"))
        self.assertEqual([f.header.seq_no for f in link.sent], [0, 1])

    def test_nak_triggers_retransmission_of_same_frame(self) -> None:
        sender, link = make_sender(["NAK", "ACK"])
        result = sender.send(data_frame("a"))
        self.assertTrue(result.delivered)
        self.assertEqual(result.retransmissions, 1)
        self.assertEqual(link.sent[0], link.sent[1])

    def test_timeout_triggers_retransmission(self) -> None:
        sender, _ = make_sender(["DROP", "ACK"])
        result = sender.send(data_frame("a"))
        self.assertEqual((result.delivered, result.retransmissions), (True, 1))

    def test_gives_up_after_max_retries(self) -> None:
        sender, link = make_sender([], max_retries=2)
        result = sender.send(data_frame("a"))
        self.assertFalse(result.delivered)
        self.assertEqual(len(link.sent), 3)  # first try + 2 retransmissions
        self.assertEqual(sender.seq_no, 1)

    def test_ack_for_other_event_is_ignored(self) -> None:
        sender, _ = make_sender(["STRAY", "ACK"])
        result = sender.send(data_frame("a"))
        self.assertEqual((result.delivered, result.retransmissions), (True, 1))


class ReceiverTest(unittest.TestCase):
    """Duplicate detection."""

    def test_retransmitted_copy_is_a_duplicate(self) -> None:
        receiver = StopAndWaitReceiver()
        self.assertTrue(receiver.is_new(data_frame("a")))
        self.assertFalse(receiver.is_new(data_frame("a")))

    def test_new_payload_with_same_seq_is_new(self) -> None:
        receiver = StopAndWaitReceiver()
        receiver.is_new(data_frame("a"))
        self.assertTrue(receiver.is_new(data_frame("b")))

    def test_reply_swaps_addresses(self) -> None:
        ack = make_ack(data_frame("a"), 16)
        self.assertEqual((ack.header.src_id, ack.header.dst_id), ("SOC", "S1"))
        self.assertEqual(ack.payload, {"ack_for": "a"})


if __name__ == "__main__":
    unittest.main()

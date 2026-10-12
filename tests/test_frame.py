"""Tests for frame encoding, decoding and live link settings."""

import random
import unittest

from datalink.crc import CRC_POLYNOMIALS
from datalink.frame import (
    Frame,
    FrameError,
    FrameFormat,
    Header,
    LinkSettings,
    corrupt_wire,
    decode_frame,
    encode_frame,
)
from datalink.framing import FRAMING_METHODS

HEADER = Header("S1", "SOC", "192.168.1.10", "10.0.0.1", 1, "DATA", 16, 2)
PAYLOAD = {"sensor": "fw01", "type": "failed_login", "note": "has | and ~ and }"}


def make_format(method: str, crc_type: str) -> FrameFormat:
    """Return a format with the default flag patterns."""
    return FrameFormat(method, crc_type, 0x7E, 0x7D, "01111110")


class FrameRoundTripTest(unittest.TestCase):
    """Every method/CRC combination decodes what it encodes."""

    def test_round_trip_all_formats(self) -> None:
        for method in FRAMING_METHODS:
            for crc_type in CRC_POLYNOMIALS:
                with self.subTest(method=method, crc=crc_type):
                    frame_format = make_format(method, crc_type)
                    wire = encode_frame(Frame(HEADER, PAYLOAD), frame_format).wire
                    received = decode_frame(wire, frame_format)
                    self.assertTrue(received.crc_ok)
                    self.assertEqual(received.frame, Frame(HEADER, PAYLOAD))

    def test_encoded_stages_are_consistent(self) -> None:
        encoded = encode_frame(Frame(HEADER, PAYLOAD), make_format("bit", "CRC-12"))
        self.assertEqual(len(encoded.crc_bits), 12)
        self.assertTrue(encoded.data.startswith(b"S1|SOC|192.168.1.10|10.0.0.1|1|"))
        self.assertEqual(encoded.body[: len(encoded.data)], encoded.data)


class CorruptionTest(unittest.TestCase):
    """A corrupted frame must fail CRC (or fail to delimit at all)."""

    def test_corrupted_frames_never_pass(self) -> None:
        rng = random.Random(8)
        for method in FRAMING_METHODS:
            for crc_type in CRC_POLYNOMIALS:
                frame_format = make_format(method, crc_type)
                wire = encode_frame(Frame(HEADER, PAYLOAD), frame_format).wire
                for _ in range(30):
                    damaged = corrupt_wire(wire, frame_format, 2, rng)
                    try:
                        self.assertFalse(decode_frame(damaged, frame_format).crc_ok)
                    except FrameError:
                        pass  # damage broke the framing itself: also rejected

    def test_corrupted_payload_keeps_header_for_nak(self) -> None:
        frame_format = make_format("character", "CRC-16")
        encoded = encode_frame(Frame(HEADER, PAYLOAD), frame_format)
        wire = bytearray(encoded.wire)
        wire[-5] ^= 0x01  # flip one bit near the end of the payload
        received = decode_frame(bytes(wire), frame_format)
        self.assertFalse(received.crc_ok)
        self.assertEqual(received.header, HEADER)
        self.assertIsNone(received.frame)

    def test_garbage_raises_frame_error(self) -> None:
        with self.assertRaises(FrameError):
            decode_frame(b"no flags here", make_format("character", "CRC-16"))


class LinkSettingsTest(unittest.TestCase):
    """Switching method, CRC and noise at run time."""

    def setUp(self) -> None:
        self.settings = LinkSettings(make_format("bit", "CRC-16"))

    def test_switch_method_and_crc(self) -> None:
        self.settings.set_method("character")
        self.settings.set_crc_type("CRC-CCITT")
        self.assertEqual(self.settings.frame_format.method, "character")
        self.assertEqual(self.settings.frame_format.crc_type, "CRC-CCITT")

    def test_rejects_bad_values(self) -> None:
        with self.assertRaises(ValueError):
            self.settings.set_method("morse")
        with self.assertRaises(ValueError):
            self.settings.set_crc_type("CRC-99")
        with self.assertRaises(ValueError):
            self.settings.set_error_rate(1.5)

    def test_from_config(self) -> None:
        frame_format = FrameFormat.from_config(
            {
                "framing_method": "bit",
                "crc_type": "CRC-12",
                "flag_byte": "0x7E",
                "esc_byte": "0x7D",
                "bit_flag": "01111110",
            }
        )
        self.assertEqual(frame_format.flag_byte, 0x7E)
        self.assertEqual(frame_format.crc_type, "CRC-12")


if __name__ == "__main__":
    unittest.main()

"""Tests for character stuffing and bit stuffing."""

import random
import unittest

from datalink.framing import (
    BIT_FLAG,
    ESC_BYTE,
    FLAG_BYTE,
    FramingError,
    add_bit_flags,
    add_byte_flags,
    bit_destuff,
    bit_stuff,
    bit_stuffing_overhead,
    bits_to_bytes,
    byte_destuff,
    byte_stuff,
    byte_stuffing_overhead,
    bytes_to_bits,
    remove_bit_flags,
    remove_byte_flags,
)


class BitConversionTest(unittest.TestCase):
    """bytes <-> '0'/'1' string conversion."""

    def test_round_trip(self) -> None:
        data = bytes(range(256))
        self.assertEqual(bits_to_bytes(bytes_to_bits(data)), data)

    def test_rejects_partial_byte(self) -> None:
        with self.assertRaises(FramingError):
            bits_to_bytes("1010")


class ByteStuffingTest(unittest.TestCase):
    """Character (byte) stuffing with FLAG and ESC."""

    def test_flag_and_esc_are_escaped(self) -> None:
        data = bytes([0x41, FLAG_BYTE, ESC_BYTE])
        self.assertEqual(
            byte_stuff(data), bytes([0x41, ESC_BYTE, FLAG_BYTE, ESC_BYTE, ESC_BYTE])
        )

    def test_round_trip_random_data(self) -> None:
        rng = random.Random(1)
        for _ in range(200):
            data = rng.randbytes(rng.randint(0, 64))
            self.assertEqual(byte_destuff(byte_stuff(data)), data)

    def test_framed_round_trip(self) -> None:
        data = b"payload with ~ and } inside"
        self.assertEqual(remove_byte_flags(add_byte_flags(data)), data)

    def test_stuffed_body_has_no_bare_flag(self) -> None:
        framed = add_byte_flags(bytes([FLAG_BYTE] * 5))
        inner = byte_stuff(bytes([FLAG_BYTE] * 5))
        self.assertEqual(framed, bytes([FLAG_BYTE]) + inner + bytes([FLAG_BYTE]))

    def test_missing_closing_flag(self) -> None:
        with self.assertRaises(FramingError):
            remove_byte_flags(bytes([FLAG_BYTE]) + b"abc")

    def test_lone_esc_is_an_error(self) -> None:
        with self.assertRaises(FramingError):
            byte_destuff(bytes([0x41, ESC_BYTE]))


class BitStuffingTest(unittest.TestCase):
    """Bit stuffing with the 01111110 flag."""

    def test_zero_inserted_after_five_ones(self) -> None:
        self.assertEqual(bit_stuff("0111111"), "01111101")
        self.assertEqual(bit_stuff("11111"), "111110")

    def test_round_trip_random_bits(self) -> None:
        rng = random.Random(2)
        for _ in range(200):
            bits = "".join(rng.choice("01") for _ in range(rng.randint(0, 120)))
            self.assertEqual(bit_destuff(bit_stuff(bits)), bits)

    def test_stuffed_data_never_contains_the_flag(self) -> None:
        stuffed = bit_stuff("1" * 40)
        self.assertNotIn(BIT_FLAG, stuffed)
        self.assertNotIn("111111", stuffed)

    def test_framed_round_trip(self) -> None:
        rng = random.Random(3)
        for _ in range(100):
            data = rng.randbytes(rng.randint(1, 64))
            self.assertEqual(remove_bit_flags(add_bit_flags(data)), data)

    def test_framed_output_is_whole_bytes_starting_with_flag(self) -> None:
        framed = add_bit_flags(b"\xff\xff")
        self.assertEqual(framed[0], 0x7E)

    def test_six_ones_inside_frame_is_an_error(self) -> None:
        with self.assertRaises(FramingError):
            bit_destuff("0111111")


class OverheadTest(unittest.TestCase):
    """Stuffing overhead percentages."""

    def test_no_special_patterns_no_overhead(self) -> None:
        self.assertEqual(byte_stuffing_overhead(b"abc"), 0.0)
        self.assertEqual(bit_stuffing_overhead(b"\x00\x00"), 0.0)

    def test_worst_case_byte_overhead_is_100_percent(self) -> None:
        self.assertEqual(byte_stuffing_overhead(bytes([FLAG_BYTE] * 4)), 100.0)

    def test_all_ones_bit_overhead_is_20_percent(self) -> None:
        self.assertAlmostEqual(bit_stuffing_overhead(b"\xff" * 5), 20.0)


if __name__ == "__main__":
    unittest.main()

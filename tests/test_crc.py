"""Tests for CRC-12, CRC-16 and CRC-CCITT."""

import random
import unittest

from datalink.crc import (
    CRC_POLYNOMIALS,
    append_crc,
    compute_crc,
    crc_degree,
    inject_burst,
    inject_errors,
    mod2_divide,
    verify_crc,
)


class Mod2DivisionTest(unittest.TestCase):
    """Binary polynomial division."""

    def test_textbook_example(self) -> None:
        # Forouzan's example: data 1001 with generator 1011 gives remainder 110.
        self.assertEqual(mod2_divide("1001000", "1011"), "110")

    def test_generators_have_expected_degree(self) -> None:
        self.assertEqual(crc_degree("CRC-12"), 12)
        self.assertEqual(crc_degree("CRC-16"), 16)
        self.assertEqual(crc_degree("CRC-CCITT"), 16)

    def test_unknown_crc_type(self) -> None:
        with self.assertRaises(ValueError):
            compute_crc("1010", "CRC-99")


class CrcDetectionTest(unittest.TestCase):
    """Valid codewords pass, corrupted ones fail."""

    def setUp(self) -> None:
        self.rng = random.Random(4)
        self.data = "".join(self.rng.choice("01") for _ in range(400))

    def test_intact_codeword_passes(self) -> None:
        for crc_type in CRC_POLYNOMIALS:
            with self.subTest(crc=crc_type):
                self.assertTrue(verify_crc(append_crc(self.data, crc_type), crc_type))

    def test_remainder_length_matches_degree(self) -> None:
        for crc_type in CRC_POLYNOMIALS:
            remainder = compute_crc(self.data, crc_type)
            self.assertEqual(len(remainder), crc_degree(crc_type))

    def test_single_and_double_bit_errors_detected(self) -> None:
        for crc_type in CRC_POLYNOMIALS:
            codeword = append_crc(self.data, crc_type)
            for n in (1, 2, 3):
                with self.subTest(crc=crc_type, bits=n):
                    damaged = inject_errors(codeword, n, self.rng)
                    self.assertFalse(verify_crc(damaged, crc_type))

    def test_short_bursts_always_detected(self) -> None:
        for crc_type in CRC_POLYNOMIALS:
            codeword = append_crc(self.data, crc_type)
            for _ in range(50):
                damaged = inject_burst(codeword, crc_degree(crc_type), self.rng)
                self.assertFalse(verify_crc(damaged, crc_type))


class ErrorInjectionTest(unittest.TestCase):
    """inject_errors flips exactly n bits."""

    def test_flips_exact_count(self) -> None:
        bits = "0" * 100
        damaged = inject_errors(bits, 7, random.Random(5))
        self.assertEqual(damaged.count("1"), 7)
        self.assertEqual(len(damaged), 100)

    def test_burst_flips_its_end_bits(self) -> None:
        damaged = inject_burst("0" * 10, 10, random.Random(6))
        self.assertEqual(damaged[0], "1")
        self.assertEqual(damaged[-1], "1")


if __name__ == "__main__":
    unittest.main()

"""Tests for the CRC / stuffing experiment helpers."""

import csv
import random
import tempfile
import unittest
from pathlib import Path

from datalink.experiment import overhead_row, random_event, write_csv


class ExperimentTest(unittest.TestCase):
    """Overhead rows and CSV output."""

    def test_overhead_row_fields(self) -> None:
        row = overhead_row("sample", "character", [bytes([0x7E, 0x41])])
        self.assertEqual(row["avg_bits_before"], 16)
        self.assertEqual(row["avg_bits_after"], 24)
        self.assertEqual(row["overhead_pct"], 50.0)

    def test_event_payload_is_json_text(self) -> None:
        event = random_event(random.Random(1))
        self.assertTrue(event.startswith(b"{") and event.endswith(b"}"))

    def test_write_csv(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "out.csv"
            write_csv(path, [{"a": 1, "b": 2}])
            with path.open(encoding="utf-8") as csv_file:
                self.assertEqual(list(csv.DictReader(csv_file)), [{"a": "1", "b": "2"}])


if __name__ == "__main__":
    unittest.main()

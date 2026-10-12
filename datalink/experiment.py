"""Experiment: CRC detection rates and stuffing overhead on 1000 random frames.

Concept: comparing error-detection codes (Lab Week 10) and framing methods
(Lab Week 9) by measurement. Results are written as CSV files to results/.

Run with: python -m datalink.experiment
"""

import csv
import json
import logging
import random
from collections.abc import Callable
from pathlib import Path

from config_loader import PROJECT_ROOT
from datalink.crc import (
    CRC_POLYNOMIALS,
    append_crc,
    inject_burst,
    inject_errors,
    verify_crc,
)
from datalink.framing import bit_stuff, byte_stuff, bytes_to_bits

FRAME_COUNT = 1000
RESULTS_DIR = PROJECT_ROOT / "results"
CRC_CSV = "crc_detection.csv"
OVERHEAD_CSV = "stuffing_overhead.csv"

logger = logging.getLogger("datalink.experiment")

ErrorPattern = Callable[[str, random.Random], str]

ERROR_PATTERNS: dict[str, ErrorPattern] = {
    "1-bit error": lambda bits, rng: inject_errors(bits, 1, rng),
    "2-bit error": lambda bits, rng: inject_errors(bits, 2, rng),
    "3-bit error": lambda bits, rng: inject_errors(bits, 3, rng),
    "burst of 12": lambda bits, rng: inject_burst(bits, 12, rng),
    "burst of 24": lambda bits, rng: inject_burst(bits, 24, rng),
}


def random_frame(rng: random.Random) -> bytes:
    """Random bytes the size of a typical event frame (40-160 bytes)."""
    return rng.randbytes(rng.randint(40, 160))


def random_event(rng: random.Random) -> bytes:
    """A realistic event payload: compact JSON text, as the sensors send."""
    event = {
        "ts": round(rng.uniform(1.7e9, 1.8e9), 3),
        "sensor": rng.choice(["fw01", "ids01", "auth01"]),
        "type": rng.choice(["failed_login", "port_probe", "http_request"]),
        "src_ip": f"192.168.1.{rng.randint(2, 254)}",
        "dst_port": rng.randint(1, 65535),
    }
    return json.dumps(event, separators=(",", ":")).encode()


def crc_detection_rows(rng: random.Random) -> list[dict[str, object]]:
    """For each CRC and error pattern, count how many damaged frames are caught."""
    frames = [bytes_to_bits(random_frame(rng)) for _ in range(FRAME_COUNT)]
    rows: list[dict[str, object]] = []
    for crc_type in CRC_POLYNOMIALS:
        codewords = [append_crc(bits, crc_type) for bits in frames]
        for pattern_name, damage in ERROR_PATTERNS.items():
            detected = sum(
                not verify_crc(damage(codeword, rng), crc_type)
                for codeword in codewords
            )
            rows.append(
                {
                    "crc_type": crc_type,
                    "error_pattern": pattern_name,
                    "frames": FRAME_COUNT,
                    "detected": detected,
                    "detection_rate_pct": round(detected / FRAME_COUNT * 100, 2),
                }
            )
    return rows


def overhead_row(kind: str, method: str, samples: list[bytes]) -> dict[str, object]:
    """Average size before and after stuffing for one data kind and method."""
    before = sum(len(data) * 8 for data in samples)
    if method == "character":
        after = sum(len(byte_stuff(data)) * 8 for data in samples)
    else:
        after = sum(len(bit_stuff(bytes_to_bits(data))) for data in samples)
    return {
        "data_kind": kind,
        "method": method,
        "frames": len(samples),
        "avg_bits_before": round(before / len(samples), 1),
        "avg_bits_after": round(after / len(samples), 1),
        "overhead_pct": round((after - before) / before * 100, 3),
    }


def overhead_rows(rng: random.Random) -> list[dict[str, object]]:
    """Compare character vs bit stuffing on random bytes and on event JSON."""
    data_sets = {
        "random bytes": [random_frame(rng) for _ in range(FRAME_COUNT)],
        "event JSON": [random_event(rng) for _ in range(FRAME_COUNT)],
    }
    return [
        overhead_row(kind, method, samples)
        for kind, samples in data_sets.items()
        for method in ("character", "bit")
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    """Write ``rows`` (all with the same keys) to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_experiment(results_dir: Path = RESULTS_DIR, seed: int = 2026) -> None:
    """Run both experiments, print a summary and save the CSV files."""
    rng = random.Random(seed)
    crc_rows = crc_detection_rows(rng)
    stuffing_rows = overhead_rows(rng)
    write_csv(results_dir / CRC_CSV, crc_rows)
    write_csv(results_dir / OVERHEAD_CSV, stuffing_rows)

    print(f"CRC detection over {FRAME_COUNT} frames per pattern")
    for row in crc_rows:
        print(
            f"  {row['crc_type']:<10} {row['error_pattern']:<12}"
            f" {row['detection_rate_pct']:>7}%"
        )
    print("Stuffing overhead")
    for row in stuffing_rows:
        print(f"  {row['data_kind']:<13} {row['method']:<10} {row['overhead_pct']:>7}%")
    logger.info("Results saved to %s", results_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
    run_experiment()

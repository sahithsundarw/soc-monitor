"""Cyclic redundancy check (CRC) on bit strings by binary polynomial division.

Concept: error detection (Lab Week 10, Forouzan Ch. 10). The sender divides the data
(with r zeros appended) by a generator polynomial using XOR instead of subtraction
and sends the r-bit remainder. The receiver divides data + remainder by the same
generator; a non-zero remainder means the frame was damaged.

No lab source file was provided, so this is a simple textbook-style implementation.
"""

import random

CRC_POLYNOMIALS = {
    "CRC-12": "1100000001111",  # x^12 + x^11 + x^3 + x^2 + x + 1
    "CRC-16": "11000000000000101",  # x^16 + x^15 + x^2 + 1
    "CRC-CCITT": "10001000000100001",  # x^16 + x^12 + x^5 + 1
}


def generator_for(crc_type: str) -> str:
    """Return the generator polynomial bits for ``crc_type``."""
    try:
        return CRC_POLYNOMIALS[crc_type]
    except KeyError:
        raise ValueError(f"Unknown CRC type {crc_type!r}") from None


def crc_degree(crc_type: str) -> int:
    """Number of check bits the CRC adds (the degree of the generator)."""
    return len(generator_for(crc_type)) - 1


def mod2_divide(dividend: str, divisor: str) -> str:
    """Binary long division where subtraction is XOR; return the remainder bits."""
    bits = list(dividend)
    degree = len(divisor) - 1
    for position in range(len(bits) - degree):
        if bits[position] == "0":
            continue  # leading 0: the quotient bit is 0, nothing to subtract
        for offset, divisor_bit in enumerate(divisor):
            current = bits[position + offset]
            bits[position + offset] = "0" if current == divisor_bit else "1"
    return "".join(bits[-degree:])


def compute_crc(data_bits: str, crc_type: str) -> str:
    """Sender side: append r zeros to the data and return the division remainder."""
    generator = generator_for(crc_type)
    return mod2_divide(data_bits + "0" * crc_degree(crc_type), generator)


def append_crc(data_bits: str, crc_type: str) -> str:
    """Return the codeword: the data followed by its CRC remainder."""
    return data_bits + compute_crc(data_bits, crc_type)


def verify_crc(codeword_bits: str, crc_type: str) -> bool:
    """Receiver side: the codeword is accepted only if the remainder is all zeros."""
    return "1" not in mod2_divide(codeword_bits, generator_for(crc_type))


def flip_bit(bit: str) -> str:
    """Return the opposite bit."""
    return "1" if bit == "0" else "0"


def inject_errors(bits: str, n: int, rng: random.Random | None = None) -> str:
    """Flip ``n`` different, randomly chosen bits to simulate line noise."""
    rng = rng or random.Random()
    damaged = list(bits)
    for position in rng.sample(range(len(bits)), n):
        damaged[position] = flip_bit(damaged[position])
    return "".join(damaged)


def inject_burst(bits: str, length: int, rng: random.Random | None = None) -> str:
    """Corrupt a burst of ``length`` bits: both ends flipped, the middle random."""
    rng = rng or random.Random()
    start = rng.randrange(len(bits) - length + 1)
    damaged = list(bits)
    for offset in range(length):
        at_edge = offset in (0, length - 1)
        if at_edge or rng.random() < 0.5:
            damaged[start + offset] = flip_bit(damaged[start + offset])
    return "".join(damaged)


def run_demo() -> None:
    """Compute each CRC for a short message and show a corrupted copy failing."""
    data = "11010011101100"
    rng = random.Random(1)
    print(f"Data bits: {data}")
    for crc_type in CRC_POLYNOMIALS:
        codeword = append_crc(data, crc_type)
        damaged = inject_errors(codeword, 2, rng)
        print(f"{crc_type:<10} CRC {compute_crc(data, crc_type)}")
        print(f"{'':<10} intact accepted: {verify_crc(codeword, crc_type)}")
        print(f"{'':<10} 2-bit error accepted: {verify_crc(damaged, crc_type)}")


if __name__ == "__main__":
    run_demo()

"""Data link framing with character (byte) stuffing and bit stuffing.

Concept: framing (Lab Week 9, Forouzan Ch. 11). A receiver finds where a frame starts
and ends by looking for a flag. Stuffing guarantees the flag pattern never appears
inside the data, so the flag is unambiguous.

No lab source file was provided, so this is a simple textbook-style implementation.
"""

FLAG_BYTE = 0x7E
ESC_BYTE = 0x7D
BIT_FLAG = "01111110"
FRAMING_METHODS = ("character", "bit")


class FramingError(ValueError):
    """Raised when a received frame cannot be delimited or destuffed."""


def bytes_to_bits(data: bytes) -> str:
    """Turn bytes into a string of '0'/'1' characters, 8 per byte."""
    return "".join(format(byte, "08b") for byte in data)


def bits_to_bytes(bits: str) -> bytes:
    """Turn a '0'/'1' string (length a multiple of 8) back into bytes."""
    if len(bits) % 8 != 0:
        raise FramingError(f"{len(bits)} bits is not a whole number of bytes")
    return bytes(int(bits[i : i + 8], 2) for i in range(0, len(bits), 8))


def byte_stuff(data: bytes, flag: int = FLAG_BYTE, esc: int = ESC_BYTE) -> bytes:
    """Character stuffing, Forouzan Ch. 11: put ESC before every FLAG or ESC byte."""
    stuffed = bytearray()
    for byte in data:
        if byte in (flag, esc):
            stuffed.append(esc)
        stuffed.append(byte)
    return bytes(stuffed)


def byte_destuff(data: bytes, flag: int = FLAG_BYTE, esc: int = ESC_BYTE) -> bytes:
    """Undo character stuffing: drop each ESC and keep the byte after it as data."""
    original = bytearray()
    escaped = False
    for byte in data:
        if escaped:
            original.append(byte)
            escaped = False
        elif byte == esc:
            escaped = True
        elif byte == flag:
            raise FramingError("Unescaped FLAG byte inside the frame")
        else:
            original.append(byte)
    if escaped:
        raise FramingError("Frame ends with a lone ESC byte")
    return bytes(original)


def bit_stuff(bits: str) -> str:
    """Bit stuffing, Forouzan Ch. 11: insert a 0 after every five consecutive 1s."""
    stuffed: list[str] = []
    ones_in_a_row = 0
    for bit in bits:
        stuffed.append(bit)
        if bit == "1":
            ones_in_a_row += 1
            if ones_in_a_row == 5:
                stuffed.append("0")
                ones_in_a_row = 0
        else:
            ones_in_a_row = 0
    return "".join(stuffed)


def bit_destuff(bits: str) -> str:
    """Undo bit stuffing: remove the 0 that follows every five consecutive 1s."""
    original: list[str] = []
    ones_in_a_row = 0
    next_is_stuffed = False
    for bit in bits:
        if next_is_stuffed:
            # The sender always inserted a 0 here; a 1 means six 1s, i.e. damage.
            if bit != "0":
                raise FramingError("Six consecutive 1s inside the frame")
            next_is_stuffed = False
            ones_in_a_row = 0
            continue
        original.append(bit)
        if bit == "1":
            ones_in_a_row += 1
            next_is_stuffed = ones_in_a_row == 5
        else:
            ones_in_a_row = 0
    return "".join(original)


def add_byte_flags(body: bytes, flag: int = FLAG_BYTE, esc: int = ESC_BYTE) -> bytes:
    """Build FLAG | stuffed body | FLAG for character-oriented framing."""
    return bytes([flag]) + byte_stuff(body, flag, esc) + bytes([flag])


def remove_byte_flags(raw: bytes, flag: int = FLAG_BYTE, esc: int = ESC_BYTE) -> bytes:
    """Find the opening and closing FLAG bytes, then destuff what lies between."""
    start = raw.find(bytes([flag]))
    if start == -1:
        raise FramingError("No opening FLAG byte found")
    index = start + 1
    while index < len(raw):
        if raw[index] == esc:
            index += 2  # skip the escaped byte, it is data even if it equals FLAG
        elif raw[index] == flag:
            return byte_destuff(raw[start + 1 : index], flag, esc)
        else:
            index += 1
    raise FramingError("No closing FLAG byte found")


def add_bit_flags(body: bytes, flag_bits: str = BIT_FLAG) -> bytes:
    """Build flag | stuffed bits | flag, padded with 0s to a whole number of bytes.

    Sockets carry bytes, so the padding after the closing flag is needed to send a
    bit-oriented frame; the receiver ignores everything after the closing flag.
    """
    frame_bits = flag_bits + bit_stuff(bytes_to_bits(body)) + flag_bits
    padding = "0" * (-len(frame_bits) % 8)
    return bits_to_bytes(frame_bits + padding)


def remove_bit_flags(raw: bytes, flag_bits: str = BIT_FLAG) -> bytes:
    """Find the two flags in the bit stream, then destuff the bits between them."""
    bits = bytes_to_bits(raw)
    start = bits.find(flag_bits)
    if start == -1:
        raise FramingError("No opening flag found")
    body_start = start + len(flag_bits)
    # After stuffing the data never holds six 1s, so the next flag is the closing one.
    end = bits.find(flag_bits, body_start)
    if end == -1:
        raise FramingError("No closing flag found")
    return bits_to_bytes(bit_destuff(bits[body_start:end]))


def add_flags(body: bytes, method: str, flag: int, esc: int, flag_bits: str) -> bytes:
    """Frame ``body`` with the chosen method ("character" or "bit")."""
    if method == "character":
        return add_byte_flags(body, flag, esc)
    if method == "bit":
        return add_bit_flags(body, flag_bits)
    raise ValueError(f"Unknown framing method {method!r}")


def remove_flags(raw: bytes, method: str, flag: int, esc: int, flag_bits: str) -> bytes:
    """Recover the body of a frame built by :func:`add_flags`."""
    if method == "character":
        return remove_byte_flags(raw, flag, esc)
    if method == "bit":
        return remove_bit_flags(raw, flag_bits)
    raise ValueError(f"Unknown framing method {method!r}")


def stuffing_overhead(original_size: int, stuffed_size: int) -> float:
    """Percentage of extra size added by stuffing (same units for both sizes)."""
    if original_size == 0:
        return 0.0
    return (stuffed_size - original_size) / original_size * 100


def byte_stuffing_overhead(data: bytes) -> float:
    """Overhead % of character stuffing on ``data``, measured in bytes."""
    return stuffing_overhead(len(data), len(byte_stuff(data)))


def bit_stuffing_overhead(data: bytes) -> float:
    """Overhead % of bit stuffing on ``data``, measured in bits."""
    bits = bytes_to_bits(data)
    return stuffing_overhead(len(bits), len(bit_stuff(bits)))


def run_demo() -> None:
    """Stuff and destuff a sample that contains the flag patterns."""
    sample = b"A~B}C\x7e"
    print("Character stuffing")
    print("  data   :", sample.hex(" "))
    print("  stuffed:", byte_stuff(sample).hex(" "))
    print(f"  overhead: {byte_stuffing_overhead(sample):.1f}%")
    bits = "0111111101111110"
    print("Bit stuffing")
    print("  data   :", bits)
    print("  stuffed:", bit_stuff(bits))
    print("  back   :", bit_destuff(bit_stuff(bits)))


if __name__ == "__main__":
    run_demo()

"""Frame format: FLAG | HEADER | PAYLOAD | CRC | FLAG.

Concept: a data link frame (Forouzan Ch. 11). The header carries addressing and
control fields, the payload carries the event, and the CRC lets the receiver detect
damage. The CRC is computed over HEADER+PAYLOAD before stuffing; stuffing then
applies to everything between the two flags.

Receiver order: find flags -> destuff -> split -> verify CRC -> parse.
"""

import json
import random
import threading
from dataclasses import asdict, dataclass, replace
from typing import Any

from datalink.crc import compute_crc, crc_degree, inject_errors, verify_crc
from datalink.framing import (
    FRAMING_METHODS,
    FramingError,
    add_flags,
    bits_to_bytes,
    bytes_to_bits,
    remove_flags,
)

FRAME_TYPES = ("DATA", "ACK", "NAK")
PRIORITY_NORMAL = 0
PRIORITY_HIGH = 1
PRIORITY_CRITICAL = 2
SEPARATOR = b"|"
HEADER_FIELD_COUNT = 8
CRC_FIELD_BITS = 16  # CRC-12 is padded with leading zeros to fill two bytes


@dataclass(frozen=True)
class Header:
    """Frame header fields, in the order they are written on the wire."""

    src_id: str
    dst_id: str
    src_ip: str
    dst_ip: str
    seq_no: int
    frame_type: str
    ttl: int
    priority: int


@dataclass(frozen=True)
class Frame:
    """A header plus the JSON payload it carries."""

    header: Header
    payload: dict[str, Any]


@dataclass(frozen=True)
class FrameFormat:
    """How frames are encoded: framing method, CRC type and the flag patterns."""

    method: str
    crc_type: str
    flag_byte: int
    esc_byte: int
    bit_flag: str

    @classmethod
    def from_config(cls, datalink: dict[str, Any]) -> "FrameFormat":
        """Read the ``datalink`` section of config.json."""
        return cls(
            method=datalink["framing_method"],
            crc_type=datalink["crc_type"],
            flag_byte=int(datalink["flag_byte"], 16),
            esc_byte=int(datalink["esc_byte"], 16),
            bit_flag=datalink["bit_flag"],
        )


@dataclass(frozen=True)
class EncodedFrame:
    """Every stage of encoding, kept so the Packet Inspector can show them."""

    data: bytes  # HEADER + PAYLOAD
    crc_bits: str  # the CRC remainder (12 or 16 bits)
    body: bytes  # data + CRC field, before stuffing
    wire: bytes  # flags + stuffed body, as sent on the socket


@dataclass(frozen=True)
class ReceivedFrame:
    """Result of decoding: the header (if readable), the frame and the CRC verdict."""

    header: Header | None
    frame: Frame | None
    crc_ok: bool


class FrameError(ValueError):
    """Raised when a frame cannot be delimited, destuffed or split."""


class LinkSettings:
    """Live, thread-safe link settings that the dashboard can switch at run time."""

    def __init__(self, frame_format: FrameFormat, error_rate: float = 0.0) -> None:
        """Start with the format and noise level from the config."""
        self._lock = threading.Lock()
        self._format = frame_format
        self._error_rate = error_rate

    @property
    def frame_format(self) -> FrameFormat:
        """The frame format in use right now."""
        with self._lock:
            return self._format

    @property
    def error_rate(self) -> float:
        """Probability (0..1) that a frame is damaged on each link it crosses."""
        with self._lock:
            return self._error_rate

    def set_method(self, method: str) -> None:
        """Switch between character and bit stuffing."""
        if method not in FRAMING_METHODS:
            raise ValueError(f"Unknown framing method {method!r}")
        with self._lock:
            self._format = replace(self._format, method=method)

    def set_crc_type(self, crc_type: str) -> None:
        """Switch the CRC polynomial."""
        crc_degree(crc_type)  # raises ValueError for an unknown type
        with self._lock:
            self._format = replace(self._format, crc_type=crc_type)

    def set_error_rate(self, error_rate: float) -> None:
        """Set the per-link frame error probability."""
        if not 0.0 <= error_rate <= 1.0:
            raise ValueError("Error rate must be between 0 and 1")
        with self._lock:
            self._error_rate = error_rate


def encode_header(header: Header) -> bytes:
    """Write the header as text fields, each followed by '|'."""
    fields = [str(value) for value in asdict(header).values()]
    return SEPARATOR.join(field.encode("ascii") for field in fields) + SEPARATOR


def encode_payload(payload: dict[str, Any]) -> bytes:
    """Write the payload as compact JSON with sorted keys."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def crc_field(data: bytes, crc_type: str) -> tuple[str, bytes]:
    """Compute the CRC of ``data``; return the remainder and its 2-byte field."""
    remainder = compute_crc(bytes_to_bits(data), crc_type)
    return remainder, bits_to_bytes(remainder.zfill(CRC_FIELD_BITS))


def encode_frame(frame: Frame, frame_format: FrameFormat) -> EncodedFrame:
    """Build the frame stage by stage: data, CRC, body, then flags and stuffing."""
    data = encode_header(frame.header) + encode_payload(frame.payload)
    remainder, field = crc_field(data, frame_format.crc_type)
    body = data + field
    wire = add_flags(
        body,
        frame_format.method,
        frame_format.flag_byte,
        frame_format.esc_byte,
        frame_format.bit_flag,
    )
    return EncodedFrame(data=data, crc_bits=remainder, body=body, wire=wire)


def parse_header(fields: list[bytes]) -> Header:
    """Turn the eight header fields into a :class:`Header`."""
    text = [field.decode("ascii") for field in fields]
    header = Header(
        src_id=text[0],
        dst_id=text[1],
        src_ip=text[2],
        dst_ip=text[3],
        seq_no=int(text[4]),
        frame_type=text[5],
        ttl=int(text[6]),
        priority=int(text[7]),
    )
    if header.frame_type not in FRAME_TYPES:
        raise ValueError(f"Unknown frame type {header.frame_type!r}")
    return header


def split_data(data: bytes) -> tuple[Header | None, bytes]:
    """Split HEADER from PAYLOAD; the header is None if it is unreadable."""
    parts = data.split(SEPARATOR, HEADER_FIELD_COUNT)
    if len(parts) <= HEADER_FIELD_COUNT:
        return None, b""
    try:
        return parse_header(parts[:HEADER_FIELD_COUNT]), parts[HEADER_FIELD_COUNT]
    except (UnicodeDecodeError, ValueError):
        return None, b""


def check_crc(data: bytes, field: bytes, crc_type: str) -> bool:
    """Divide data + received CRC by the generator; also require zero padding bits."""
    field_bits = bytes_to_bits(field)
    degree = crc_degree(crc_type)
    padding, remainder = field_bits[:-degree], field_bits[-degree:]
    if "1" in padding:
        return False
    return verify_crc(bytes_to_bits(data) + remainder, crc_type)


def decode_frame(wire: bytes, frame_format: FrameFormat) -> ReceivedFrame:
    """Find flags, destuff, split, verify the CRC and parse the payload.

    Raises :class:`FrameError` if the frame cannot even be delimited. A frame that is
    delimited but damaged comes back with ``crc_ok=False`` and, when the header is
    still readable, its header so the receiver knows whom to NAK.
    """
    try:
        body = remove_flags(
            wire,
            frame_format.method,
            frame_format.flag_byte,
            frame_format.esc_byte,
            frame_format.bit_flag,
        )
    except FramingError as error:
        raise FrameError(str(error)) from error
    field_bytes = CRC_FIELD_BITS // 8
    if len(body) <= field_bytes:
        raise FrameError("Frame too short to hold a CRC")
    data, field = body[:-field_bytes], body[-field_bytes:]
    header, payload_bytes = split_data(data)
    if not check_crc(data, field, frame_format.crc_type):
        return ReceivedFrame(header=header, frame=None, crc_ok=False)
    if header is None:
        raise FrameError("CRC passed but the header is malformed")
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FrameError(f"Payload is not valid JSON: {error}") from error
    return ReceivedFrame(header=header, frame=Frame(header, payload), crc_ok=True)


def corrupt_wire(
    wire: bytes, frame_format: FrameFormat, n_bits: int, rng: random.Random
) -> bytes:
    """Simulate line noise: flip ``n_bits`` random bits between the two flags.

    The flags are left intact so the receiver can still delimit the frame and the
    damage is caught by the CRC, which is what the demo sets out to show.
    """
    bits = bytes_to_bits(wire)
    if frame_format.method == "bit":
        opening = len(frame_format.bit_flag)
        closing = bits.rfind(frame_format.bit_flag)  # padding 0s follow the flag
    else:
        opening = 8
        closing = len(bits) - 8  # the closing FLAG is the last byte
    inner = bits[opening:closing]
    damaged = inject_errors(inner, min(n_bits, len(inner)), rng)
    return bits_to_bytes(bits[:opening] + damaged + bits[closing:])


def run_demo() -> None:
    """Encode one event frame with each method and show it being checked."""
    header = Header("S1", "SOC", "192.168.1.10", "10.0.0.1", 0, "DATA", 16, 1)
    frame = Frame(header, {"sensor": "fw01", "type": "failed_login", "user": "root"})
    rng = random.Random(7)
    for method in FRAMING_METHODS:
        frame_format = FrameFormat(method, "CRC-16", 0x7E, 0x7D, "01111110")
        encoded = encode_frame(frame, frame_format)
        damaged = corrupt_wire(encoded.wire, frame_format, 2, rng)
        print(f"{method} framing, CRC-16 remainder {encoded.crc_bits}")
        print(f"  wire ({len(encoded.wire)} bytes): {encoded.wire[:24].hex(' ')} ...")
        print(f"  intact frame CRC ok : {decode_frame(encoded.wire, frame_format).crc_ok}")
        try:
            verdict = decode_frame(damaged, frame_format).crc_ok
        except FrameError as error:
            verdict = f"rejected while delimiting ({error})"
        print(f"  damaged frame CRC ok: {verdict}")


if __name__ == "__main__":
    run_demo()

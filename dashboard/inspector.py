"""Packet Inspector: show one received event at every layer of the stack.

Concept: encapsulation. The same event is the payload of a transport segment, which
travels inside a network packet, which is carried in a data link frame. Rebuilding
the frame from what the collector received shows each layer's fields.
"""

import json
from typing import Any

from datalink.crc import crc_degree
from datalink.frame import Frame, FrameFormat, Header, encode_frame, encode_header
from datalink.framing import BIT_FLAG, ESC_BYTE, FLAG_BYTE, bytes_to_bits

TRANSPORT_NOTES = {
    "udp": "Connectionless datagram: no handshake, no delivery guarantee.",
    "tcp": "Connection set up per hop (three-way handshake), reliable byte stream.",
}


def to_hex(data: bytes) -> str:
    """Bytes as spaced hex pairs, e.g. "7e 53 31"."""
    return data.hex(" ")


def to_binary(data: bytes) -> str:
    """Bytes as spaced 8-bit groups."""
    bits = bytes_to_bits(data)
    return " ".join(bits[i : i + 8] for i in range(0, len(bits), 8))


def crc_hex(crc_bits: str, degree: int) -> str:
    """CRC remainder in hex, one digit per 4 bits (CRC-12 -> 3 digits)."""
    digits = (degree + 3) // 4
    return format(int(crc_bits, 2), f"0{digits}x")


def describe_layers(record: dict[str, Any]) -> dict[str, Any]:
    """Break one collector event record into application/transport/network/link."""
    header = Header(**record["header"])
    frame_format = FrameFormat(
        record["method"], record["crc_type"], FLAG_BYTE, ESC_BYTE, BIT_FLAG
    )
    encoded = encode_frame(Frame(header, record["payload"]), frame_format)
    stuffing_bytes = len(encoded.wire) - len(encoded.body) - 2
    return {
        "id": record["id"],
        "application": {
            "json": json.dumps(record["payload"], indent=2, sort_keys=True),
        },
        "transport": {
            "protocol": record["protocol"].upper(),
            "src_port": record["src_port"],
            "dst_port": record["dst_port"],
            "note": TRANSPORT_NOTES[record["protocol"]],
        },
        "network": {
            "src_ip": header.src_ip,
            "dst_ip": header.dst_ip,
            "ttl": header.ttl,
            "hops": record["hops"],
            "path": record["path"],
            "priority": header.priority,
        },
        "datalink": {
            "method": record["method"],
            "crc_type": record["crc_type"],
            "header_text": encode_header(header).decode("ascii"),
            "seq_no": header.seq_no,
            "frame_type": header.frame_type,
            "crc_bits": encoded.crc_bits,
            "crc_hex": crc_hex(encoded.crc_bits, crc_degree(record["crc_type"])),
            "body_bytes": len(encoded.body),
            "wire_bytes": len(encoded.wire),
            "stuffing_overhead_bytes": max(stuffing_bytes, 0),
            "wire_hex": to_hex(encoded.wire),
            "wire_binary": to_binary(encoded.wire),
            "matches_received": encoded.wire.hex() == record["wire_hex"],
        },
    }

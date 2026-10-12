"""Router: receive a frame, decrement its TTL and forward it to the next hop.

Concept: store-and-forward routing (Lab Week 12). Each router reads the destination
from the frame header, looks up the next hop in its Dijkstra forwarding table and
forwards the frame. TTL stops frames from circulating forever. Because the TTL is
inside the CRC-protected header, the router recomputes the CRC after changing it,
just as an IP router recomputes the header checksum.
"""

import logging
from dataclasses import replace

from datalink.frame import FrameError, decode_frame, encode_frame
from network.node import Node

logger = logging.getLogger("network.router")


class Router(Node):
    """A forwarding node. Only frames with a readable header can be routed."""

    def handle_frame(self, wire: bytes, protocol: str) -> None:
        """Forward one frame towards the destination in its header."""
        frame_format = self.settings.frame_format
        try:
            received = decode_frame(wire, frame_format)
        except FrameError as error:
            logger.info("%s dropped an undelimitable frame: %s", self.node_id, error)
            return
        header = received.header
        if header is None:
            logger.info("%s dropped a frame with an unreadable header", self.node_id)
            return
        if received.crc_ok and received.frame is not None:
            if header.ttl <= 1:
                logger.warning(
                    "%s dropped a frame from %s: TTL expired",
                    self.node_id,
                    header.src_id,
                )
                return
            shorter_ttl = replace(header, ttl=header.ttl - 1)
            outgoing = replace(received.frame, header=shorter_ttl)
            wire = encode_frame(outgoing, frame_format).wire
        else:
            # Never recompute the CRC over damaged data: that would hide the damage.
            logger.info("%s forwards a damaged frame unchanged", self.node_id)
        neighbor = self.next_hop(header.dst_id)
        logger.info(
            "Hop %s -> %s  %s %s->%s seq=%d ttl=%d",
            self.node_id,
            neighbor,
            header.frame_type,
            header.src_id,
            header.dst_id,
            header.seq_no,
            header.ttl,
        )
        self.transmit(wire, protocol, header.dst_id)

"""UDP and TCP frame servers and senders used by every node.

Concept: the transport layer (Lab Week 12). UDP sends independent datagrams with no
connection and no delivery guarantee; TCP sets up a connection first and delivers a
reliable byte stream. Here each TCP connection carries exactly one frame, so the
receiver knows the frame has ended when the sender closes the connection.
"""

import logging
import socket
import threading
from collections.abc import Callable

PROTOCOLS = ("udp", "tcp")
MAX_DATAGRAM = 65507
POLL_INTERVAL_S = 0.5  # how often blocking calls wake up to check for shutdown
TCP_TIMEOUT_S = 2.0

logger = logging.getLogger("network.transport")

Address = tuple[str, int]
FrameHandler = Callable[[bytes, str], None]


class FrameServer:
    """Listen for frames on one UDP port and one TCP port with the same number."""

    def __init__(self, name: str, host: str, port: int, handler: FrameHandler) -> None:
        """Bind both sockets; ``handler(frame_bytes, protocol)`` gets every frame."""
        self.name = name
        self.address: Address = (host, port)
        self._handler = handler
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._udp.bind(self.address)
        self._udp.settimeout(POLL_INTERVAL_S)
        self._tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._tcp.bind(self.address)
        self._tcp.listen(32)
        self._tcp.settimeout(POLL_INTERVAL_S)

    def start(self) -> None:
        """Start the UDP and TCP receive loops in background threads."""
        for target in (self._udp_loop, self._tcp_loop):
            thread = threading.Thread(
                target=target, name=f"{self.name}-{target.__name__}", daemon=True
            )
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        """Stop both loops and close the sockets."""
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2)
        self._udp.close()
        self._tcp.close()

    def send_udp(self, data: bytes, address: Address) -> None:
        """Send one datagram from this node's own UDP port."""
        self._udp.sendto(data, address)

    def _deliver(self, data: bytes, protocol: str) -> None:
        """Pass a frame to the handler without letting one bad frame kill the loop."""
        try:
            self._handler(data, protocol)
        except Exception:
            logger.exception("%s failed to handle a %s frame", self.name, protocol)

    def _udp_loop(self) -> None:
        """Receive datagrams until stopped; each datagram is one frame."""
        while not self._stop.is_set():
            try:
                data, _ = self._udp.recvfrom(MAX_DATAGRAM)
            except socket.timeout:
                continue
            except ConnectionResetError:
                # Windows reports an earlier datagram to a closed port this way.
                continue
            except OSError:
                break  # socket closed during shutdown
            self._deliver(data, "udp")

    def _tcp_loop(self) -> None:
        """Accept connections until stopped; each one is read in its own thread."""
        while not self._stop.is_set():
            try:
                connection, _ = self._tcp.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._read_connection, args=(connection,), daemon=True
            ).start()

    def _read_connection(self, connection: socket.socket) -> None:
        """Read one frame: everything the peer sends until it closes."""
        chunks: list[bytes] = []
        with connection:
            connection.settimeout(TCP_TIMEOUT_S)
            try:
                chunk = connection.recv(4096)
                while chunk:  # an empty read means the sender closed the connection
                    chunks.append(chunk)
                    chunk = connection.recv(4096)
            except OSError as error:
                logger.warning("%s: TCP read failed: %s", self.name, error)
                return
        if chunks:
            self._deliver(b"".join(chunks), "tcp")


def send_tcp(data: bytes, address: Address) -> None:
    """Open a TCP connection (three-way handshake), send one frame, close it."""
    with socket.create_connection(address, timeout=TCP_TIMEOUT_S) as connection:
        connection.sendall(data)

"""Network diagnostics: run a fixed whitelist of OS networking commands.

Concept: basic networking commands (Lab Week 11). ping tests reachability (ICMP
echo), traceroute/tracert lists the routers on the way, netstat shows open sockets,
ipconfig/ifconfig shows interface addresses and arp -a shows the IP-to-MAC cache.
Only whitelisted commands run, against targets from config.json; nothing typed by
a user is ever passed to the shell.
"""

import logging
import platform
import subprocess
from dataclasses import dataclass
from typing import Any

from config_loader import load_config

logger = logging.getLogger("services.diagnostics")

MAX_OUTPUT_LINES = 200


@dataclass(frozen=True)
class CommandSpec:
    """One whitelisted command: candidate argument lists for Windows and Linux.

    Several candidates per OS let a newer tool stand in when an older one is not
    installed (e.g. ``ip addr`` when ``ifconfig`` is missing). ``{target}`` is
    replaced by an IP from the config.
    """

    label: str
    summary: str
    windows: tuple[tuple[str, ...], ...]
    posix: tuple[tuple[str, ...], ...]
    needs_target: bool


COMMANDS = {
    "ping": CommandSpec(
        "Ping",
        "ICMP echo: is the target reachable, and how fast?",
        (("ping", "-n", "4", "{target}"),),
        (("ping", "-c", "4", "{target}"),),
        True,
    ),
    "traceroute": CommandSpec(
        "Traceroute",
        "Lists every router hop on the way to the target.",
        (("tracert", "-d", "-h", "8", "-w", "500", "{target}"),),
        (
            ("traceroute", "-n", "-m", "8", "-w", "1", "{target}"),
            ("tracepath", "-n", "{target}"),
        ),
        True,
    ),
    "netstat": CommandSpec(
        "Netstat (SOC Monitor ports)",
        "Open UDP and TCP sockets on this project's ports.",
        (("netstat", "-an"),),
        (("netstat", "-an"), ("ss", "-tuan")),
        False,
    ),
    "ipconfig": CommandSpec(
        "Interface config",
        "IP addresses and masks of this PC's interfaces.",
        (("ipconfig",),),
        (("ifconfig",), ("ip", "addr")),
        False,
    ),
    "arp": CommandSpec(
        "ARP table",
        "IP-to-MAC address cache for the local network.",
        (("arp", "-a"),),
        (("arp", "-a"), ("ip", "neigh")),
        False,
    ),
}


class DiagnosticsError(ValueError):
    """Raised for a command or target that is not on the whitelist."""


def is_windows() -> bool:
    """True on Windows, where the command names and flags differ."""
    return platform.system() == "Windows"


def allowed_targets(config: dict[str, Any]) -> list[dict[str, str]]:
    """Targets offered in the dashboard dropdown, from ``diagnostics.targets``."""
    return list(config["diagnostics"]["targets"])


def project_ports(config: dict[str, Any]) -> set[int]:
    """Every port the SOC Monitor listens on, for filtering netstat output."""
    ports = {node["port"] for node in config["nodes"].values()}
    ports.update(service["port"] for service in config["services"].values())
    return ports


def candidates(command_id: str, target: str, windows: bool) -> list[list[str]]:
    """Argument lists to try for ``command_id``, with the target filled in."""
    spec = COMMANDS[command_id]
    options = spec.windows if windows else spec.posix
    return [[target if arg == "{target}" else arg for arg in args] for args in options]


def filter_netstat(output: str, ports: set[int]) -> str:
    """Keep the heading lines and the sockets that use one of our ports."""
    kept = []
    for line in output.splitlines():
        words = line.split()
        if any(word.endswith(f":{port}") for word in words for port in ports):
            kept.append(line)
        elif "Proto" in line or "Netid" in line:
            kept.append(line)
    return "\n".join(kept) if kept else "No sockets found on the SOC Monitor ports."


def trim(output: str) -> str:
    """Limit very long output so the terminal card stays readable."""
    lines = output.strip().splitlines()
    if len(lines) <= MAX_OUTPUT_LINES:
        return "\n".join(lines)
    hidden = len(lines) - MAX_OUTPUT_LINES
    return "\n".join(lines[:MAX_OUTPUT_LINES] + [f"... {hidden} more lines"])


def run_diagnostic(
    command_id: str, target: str, config: dict[str, Any], windows: bool | None = None
) -> dict[str, Any]:
    """Run one whitelisted command and return its command line and output."""
    if command_id not in COMMANDS:
        raise DiagnosticsError(f"Unknown command {command_id!r}")
    if target not in {entry["ip"] for entry in allowed_targets(config)}:
        raise DiagnosticsError(f"Target {target!r} is not listed in config.json")
    windows = is_windows() if windows is None else windows
    timeout_s = config["diagnostics"]["timeout_s"]
    for args in candidates(command_id, target, windows):
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout_s,
                check=False,
            )
        except FileNotFoundError:
            continue  # this tool is not installed; try the next candidate
        except subprocess.TimeoutExpired as error:
            partial = error.stdout or ""
            if isinstance(partial, bytes):
                partial = partial.decode(errors="replace")
            return {
                "command": " ".join(args),
                "output": trim(partial) + f"\n\nStopped after {timeout_s} s timeout.",
                "returncode": None,
            }
        output = result.stdout + result.stderr
        if command_id == "netstat":
            output = filter_netstat(output, project_ports(config))
        logger.info("Diagnostics ran: %s (exit %s)", " ".join(args), result.returncode)
        return {
            "command": " ".join(args),
            "output": trim(output),
            "returncode": result.returncode,
        }
    raise DiagnosticsError(f"{COMMANDS[command_id].label} is not installed on this PC")


def run_demo() -> None:
    """Ping localhost and show the SOC Monitor's sockets."""
    config = load_config()
    for command_id in ("ping", "netstat"):
        result = run_diagnostic(command_id, "127.0.0.1", config)
        print(f"$ {result['command']}\n{result['output']}\n")


if __name__ == "__main__":
    run_demo()

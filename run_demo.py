"""Start the whole SOC Monitor with one command; Ctrl+C stops everything.

Concept: a complete small network on one PC. Sensors, routers and the SOC collector
each listen on their own port from config.json and exchange real UDP/TCP frames.

Run with: python run_demo.py [--noise 0.1] [--verbose]
"""

import argparse
import logging
import time
from pathlib import Path

from config_loader import PROJECT_ROOT, load_config
from network.routing import format_route
from soc.system import SocSystem

LOG_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)-18s  %(message)s"
LOG_FILE = PROJECT_ROOT / "logs" / "soc-monitor.log"


def setup_logging(verbose: bool, log_file: Path = LOG_FILE) -> None:
    """Log everything to logs/soc-monitor.log; the console shows warnings only
    unless ``verbose`` is set."""
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO if verbose else logging.WARNING)
    for handler in (file_handler, console):
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console])


def print_banner(system: SocSystem) -> None:
    """Short banner, one aligned line per service, then the current routes."""
    print("SOC Monitor  -  secure framing and auto-rerouting")
    print("-" * 52)
    for name, host, port in system.services():
        print(f"  {name:<26} {host:>15}:{port}")
    print("-" * 52)
    for sensor_id, route in system.routes().items():
        print(f"  route {sensor_id:<4} {format_route(route['path'], route['cost'])}")
    print("Press Ctrl+C to stop.")


def parse_args() -> argparse.Namespace:
    """Command-line options."""
    parser = argparse.ArgumentParser(description="Run the SOC Monitor demo")
    parser.add_argument(
        "--noise", type=float, default=None, help="initial frame error rate (0-1)"
    )
    parser.add_argument(
        "--verbose", action="store_true", help="show every hop and ARQ step"
    )
    return parser.parse_args()


def main() -> None:
    """Build, start, wait for Ctrl+C, stop."""
    args = parse_args()
    setup_logging(args.verbose)
    system = SocSystem(load_config())
    if args.noise is not None:
        system.settings.set_error_rate(args.noise)
    system.start()
    print_banner(system)
    try:
        while True:
            time.sleep(1)  # sleep (unlike a bare wait) is interruptible on Windows
    except KeyboardInterrupt:
        print("\nShutting down ...")
    finally:
        system.stop()
        print("All services stopped.")


if __name__ == "__main__":
    main()

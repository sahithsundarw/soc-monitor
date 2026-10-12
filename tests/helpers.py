"""Shared test helpers: a config whose ports do not clash with a running demo."""

from typing import Any

from config_loader import load_config

TEST_PORT_OFFSET = 30000


def make_test_config(port_offset: int = TEST_PORT_OFFSET) -> dict[str, Any]:
    """Default config with every node port shifted and sensors kept quiet."""
    config = load_config()
    for node in config["nodes"].values():
        node["port"] += port_offset
    config["sensors"]["event_interval_s"] = 3600  # tests send events explicitly
    config["arq"]["timeout_s"] = 0.3
    return config

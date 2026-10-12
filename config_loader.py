"""Load the shared config.json used by every module.

Concept: one configuration file describes the whole network (node addresses, ports,
link costs, protocol settings), so the system can move from one PC to two lab PCs
by editing a single file.
"""

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Read and parse config.json (or the file at ``path``) into a dictionary."""
    config_path = path or DEFAULT_CONFIG_PATH
    with config_path.open(encoding="utf-8") as config_file:
        return json.load(config_file)

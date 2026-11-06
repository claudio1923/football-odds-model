"""Configuration loading."""
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"

REQUIRED_PATH_KEYS = ("raw", "interim", "processed", "reports", "manifest")
REQUIRED_KEYS = ("paths", "random_seed", "data_source")


def load_config(path=None) -> dict:
    """Load the YAML config; resolve all paths to absolute paths under the project root.

    Raises KeyError if a required key is missing.
    """
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    with open(cfg_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}

    for key in REQUIRED_KEYS:
        if key not in cfg:
            raise KeyError(f"Missing required config key: {key}")
    paths = cfg["paths"]
    if not isinstance(paths, dict):
        raise KeyError("Config key 'paths' must be a mapping")
    for key in REQUIRED_PATH_KEYS:
        if key not in paths:
            raise KeyError(f"Missing required config path key: paths.{key}")

    cfg["paths"] = {k: (PROJECT_ROOT / Path(v)).resolve() for k, v in paths.items()}
    return cfg

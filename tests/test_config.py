from pathlib import Path

import pytest
import yaml

from fbmodel.config import load_config

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PATH_KEYS = ["raw", "interim", "processed", "reports", "manifest"]


def _write_yaml(path, data):
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _valid():
    return {
        "paths": {k: f"data/{k}" for k in PATH_KEYS},
        "random_seed": 42,
        "data_source": "test",
    }


def test_paths_are_absolute_under_project_root():
    cfg = load_config()
    for key in PATH_KEYS:
        p = cfg["paths"][key]
        assert isinstance(p, Path)
        assert p.is_absolute()
        p.relative_to(PROJECT_ROOT)


def test_required_keys_present():
    cfg = load_config()
    for key in ("paths", "random_seed", "data_source"):
        assert key in cfg


@pytest.mark.parametrize("missing", ["paths", "random_seed", "data_source"])
def test_missing_top_level_key_raises(tmp_path, missing):
    data = _valid()
    del data[missing]
    cfg_path = _write_yaml(tmp_path / "config.yaml", data)
    with pytest.raises(KeyError):
        load_config(cfg_path)


@pytest.mark.parametrize("missing", PATH_KEYS)
def test_missing_paths_key_raises(tmp_path, missing):
    data = _valid()
    del data["paths"][missing]
    cfg_path = _write_yaml(tmp_path / "config.yaml", data)
    with pytest.raises(KeyError):
        load_config(cfg_path)

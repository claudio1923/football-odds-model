"""Guards protecting the raw data area."""
import hashlib
import os
import stat
from pathlib import Path

from fbmodel.config import load_config

_CHUNK = 1024 * 1024


def _raw_dir() -> Path:
    return load_config()["paths"]["raw"]


def safe_write_path(path, raw_dir=None) -> Path:
    """Return the resolved path; raise if it lies inside the raw data directory."""
    target = Path(path).resolve()
    raw = Path(raw_dir).resolve() if raw_dir is not None else _raw_dir()
    if target == raw or raw in target.parents:
        raise PermissionError(f"Refusing to write inside raw data area: {target}")
    return target


def make_read_only(path) -> None:
    os.chmod(path, stat.S_IREAD)


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_raw_manifest(manifest_path) -> None:
    """Manifest lines: '<sha256>  <relative path>' (relative to the manifest's folder).

    Raises FileNotFoundError for a missing file and ValueError on a hash mismatch.
    """
    manifest = Path(manifest_path)
    base = manifest.parent
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected, rel = line.split(None, 1)
        f = base / rel.strip()
        if not f.is_file():
            raise FileNotFoundError(f"Listed in manifest but missing: {f}")
        if sha256_file(f) != expected:
            raise ValueError(f"SHA-256 mismatch: {f}")

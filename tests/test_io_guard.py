import os
import stat

import pytest

from fbmodel.io_guard import (
    make_read_only,
    safe_write_path,
    sha256_file,
    verify_raw_manifest,
)
import hashlib


@pytest.fixture
def data_dirs(tmp_path):
    raw = tmp_path / "data" / "raw"
    processed = tmp_path / "data" / "processed"
    raw.mkdir(parents=True)
    processed.mkdir(parents=True)
    return raw, processed


def test_safe_write_path_rejects_raw(data_dirs):
    raw, _ = data_dirs
    with pytest.raises(PermissionError):
        safe_write_path(raw / "x.csv", raw_dir=raw)


def test_safe_write_path_rejects_dotdot_into_raw(data_dirs):
    raw, processed = data_dirs
    sneaky = processed / ".." / "raw" / "x.csv"
    with pytest.raises(PermissionError):
        safe_write_path(sneaky, raw_dir=raw)


def test_safe_write_path_accepts_processed(data_dirs):
    raw, processed = data_dirs
    target = processed / "out.csv"
    result = safe_write_path(target, raw_dir=raw)
    assert result == target.resolve()


def test_make_read_only_blocks_writes(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hello")
    make_read_only(f)
    try:
        with pytest.raises(PermissionError):
            open(f, "w")
    finally:
        os.chmod(f, stat.S_IWRITE)


def test_sha256_file(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    assert sha256_file(f) == hashlib.sha256(b"abc").hexdigest()


def _make_manifest(tmp_path, content=b"some,data\n1,2\n"):
    f = tmp_path / "raw.csv"
    f.write_bytes(content)
    manifest = tmp_path / "MANIFEST.sha256"
    manifest.write_text(f"{sha256_file(f)}  raw.csv\n", encoding="utf-8")
    return f, manifest


def test_verify_manifest_intact(tmp_path):
    _, manifest = _make_manifest(tmp_path)
    verify_raw_manifest(manifest)


def test_verify_manifest_detects_changed_byte(tmp_path):
    f, manifest = _make_manifest(tmp_path)
    os.chmod(f, stat.S_IWRITE)
    data = bytearray(f.read_bytes())
    data[0] ^= 0x01
    f.write_bytes(bytes(data))
    with pytest.raises(ValueError):
        verify_raw_manifest(manifest)


def test_verify_manifest_missing_file(tmp_path):
    f, manifest = _make_manifest(tmp_path)
    f.unlink()
    with pytest.raises(FileNotFoundError):
        verify_raw_manifest(manifest)

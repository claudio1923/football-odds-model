import hashlib
import os
import stat

import pandas as pd
import pytest

from fbmodel.data.download import add_raw_file, build_targets, download_all
from fbmodel.io_guard import verify_raw_manifest


def _ds():
    return {
        "base_url": "https://example.test",
        "main_url_pattern": "{base_url}/mmz4281/{season_code}/{league_code}.csv",
        "extra_url_pattern": "{base_url}/new/{league_code}.csv",
        "main_leagues": {"I1": "Serie A", "E0": "Premier League"},
        "extra_leagues": {"USA": "MLS", "DNK": "Denmark"},
        "seasons": {
            "I1": ["2425", "2526"],
            "E0": ["2526"],
            "USA": [2025, 2026],
            "DNK": ["2024/2025", "2025/2026"],
        },
        "played_only": True,
        "request_delay_seconds": 0,
        "max_retries": 1,
    }


def _cfg(tmp_path):
    return {
        "paths": {
            "raw": tmp_path / "raw",
            "manifest": tmp_path / "meta" / "MANIFEST.sha256",
            "download_log": tmp_path / "meta" / "log" / "download_log.csv",
        },
        "data_source": _ds(),
    }


def test_build_targets_counts_and_fields():
    targets = build_targets({"data_source": _ds()})
    assert len(targets) == 5
    for t in targets:
        assert {"league", "season", "url", "rel_path"} <= set(t)
    main = [t for t in targets if t["league"] in ("I1", "E0")]
    extra = [t for t in targets if t["league"] in ("USA", "DNK")]
    assert len(main) == 3
    assert len(extra) == 2


def test_build_targets_main_values():
    targets = build_targets({"data_source": _ds()})
    by = {(t["league"], str(t["season"])): t for t in targets}
    t = by[("I1", "2526")]
    assert t["url"] == "https://example.test/mmz4281/2526/I1.csv"
    assert t["rel_path"] == "I1_2526.csv"
    assert by[("I1", "2425")]["rel_path"] == "I1_2425.csv"
    assert by[("E0", "2526")]["url"] == "https://example.test/mmz4281/2526/E0.csv"


def test_build_targets_extra_values():
    targets = build_targets({"data_source": _ds()})
    by = {t["league"]: t for t in targets}
    assert by["USA"]["season"] == "all"
    assert by["USA"]["url"] == "https://example.test/new/USA.csv"
    assert by["USA"]["rel_path"] == "USA_all.csv"
    assert by["DNK"]["rel_path"] == "DNK_all.csv"


def test_add_raw_file_writes_and_manifests(tmp_path):
    raw = tmp_path / "raw"
    manifest = tmp_path / "meta" / "MANIFEST.sha256"
    content = b"a,b\n1,2\n"
    p = add_raw_file(content, "sub/dir/x.csv", raw, manifest)
    assert p == raw / "sub" / "dir" / "x.csv"
    assert p.read_bytes() == content
    assert not os.access(p, os.W_OK)
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert lines == [f"{hashlib.sha256(content).hexdigest()}  sub/dir/x.csv"]
    verify_raw_manifest(manifest, raw)


def test_add_raw_file_preserves_existing_lines(tmp_path):
    raw = tmp_path / "raw"
    manifest = tmp_path / "MANIFEST.sha256"
    add_raw_file(b"one", "a.csv", raw, manifest)
    add_raw_file(b"two", "b.csv", raw, manifest)
    lines = [ln for ln in manifest.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert lines[0].endswith("  a.csv")
    assert lines[1].endswith("  b.csv")
    verify_raw_manifest(manifest, raw)


def test_add_raw_file_existing_target_raises(tmp_path):
    raw = tmp_path / "raw"
    manifest = tmp_path / "MANIFEST.sha256"
    p = add_raw_file(b"one", "a.csv", raw, manifest)
    before = manifest.read_text(encoding="utf-8")
    with pytest.raises(FileExistsError):
        add_raw_file(b"other", "a.csv", raw, manifest)
    assert p.read_bytes() == b"one"
    assert manifest.read_text(encoding="utf-8") == before


def test_add_raw_file_tamper_detected(tmp_path):
    raw = tmp_path / "raw"
    manifest = tmp_path / "MANIFEST.sha256"
    p = add_raw_file(b"abcdef", "a.csv", raw, manifest)
    os.chmod(p, stat.S_IWRITE)
    p.write_bytes(b"abcdeg")
    with pytest.raises(ValueError):
        verify_raw_manifest(manifest, raw)


def test_download_all_success_and_log(tmp_path):
    cfg = _cfg(tmp_path)
    calls = []

    def fetch(url):
        calls.append(url)
        return 200, ("data for " + url).encode()

    df = download_all(cfg, "2026-01-02", fetch=fetch)
    assert list(df.columns) == [
        "url", "rel_path", "downloaded_at_utc", "http_status", "bytes", "sha256",
    ]
    assert len(df) == 5
    assert len(calls) == 5
    assert set(calls) == set(df["url"])
    for _, row in df.iterrows():
        assert row["http_status"] == 200
        assert row["rel_path"].startswith("football-data/2026-01-02/")
        content = ("data for " + row["url"]).encode()
        assert row["bytes"] == len(content)
        assert row["sha256"] == hashlib.sha256(content).hexdigest()
        assert str(row["downloaded_at_utc"]) != ""
        assert (cfg["paths"]["raw"] / row["rel_path"]).read_bytes() == content
    assert "football-data/2026-01-02/I1_2526.csv" in set(df["rel_path"])
    assert "football-data/2026-01-02/USA_all.csv" in set(df["rel_path"])
    verify_raw_manifest(cfg["paths"]["manifest"], cfg["paths"]["raw"])
    log = pd.read_csv(cfg["paths"]["download_log"])
    assert len(log) == 5
    assert list(log.columns) == list(df.columns)


def test_download_all_retries_and_failures(tmp_path):
    cfg = _cfg(tmp_path)
    counts = {}

    def fetch(url):
        counts[url] = counts.get(url, 0) + 1
        if url.endswith("/E0.csv"):
            return 404, b"nope"
        if url.endswith("/USA.csv"):
            raise OSError("boom")
        return 200, b"ok,data\n1,2\n"

    df = download_all(cfg, "2026-01-02", fetch=fetch)
    assert len(df) == 5
    for url, n in counts.items():
        if url.endswith("/E0.csv") or url.endswith("/USA.csv"):
            assert n == 2
        else:
            assert n == 1
    bad404 = df[df["url"].str.endswith("/E0.csv")].iloc[0]
    assert bad404["http_status"] == 404
    assert bad404["bytes"] == 0
    assert bad404["sha256"] == ""
    badexc = df[df["url"].str.endswith("/USA.csv")].iloc[0]
    assert badexc["http_status"] == 0
    assert badexc["bytes"] == 0
    assert badexc["sha256"] == ""
    raw = cfg["paths"]["raw"]
    assert not (raw / bad404["rel_path"]).exists()
    assert not (raw / badexc["rel_path"]).exists()
    manifest_lines = [
        ln for ln in cfg["paths"]["manifest"].read_text(encoding="utf-8").splitlines() if ln.strip()
    ]
    assert len(manifest_lines) == 3
    verify_raw_manifest(cfg["paths"]["manifest"], raw)


def test_download_all_log_appends_with_single_header(tmp_path):
    cfg = _cfg(tmp_path)

    def fetch(url):
        return 200, b"x"

    download_all(cfg, "2026-01-02", fetch=fetch)
    download_all(cfg, "2026-01-03", fetch=fetch)
    text = cfg["paths"]["download_log"].read_text(encoding="utf-8")
    assert text.count("downloaded_at_utc") == 1
    log = pd.read_csv(cfg["paths"]["download_log"])
    assert len(log) == 10

"""Download football-data.co.uk files into the read-only raw area.

add_raw_file is the only code allowed to write under data/raw.
"""
import hashlib
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fbmodel.io_guard import make_read_only

LOG_COLUMNS = ["url", "rel_path", "downloaded_at_utc", "http_status", "bytes", "sha256"]
RAW_SUBDIR = "football-data"


def build_targets(cfg) -> list[dict]:
    """One target per main league x season; one per extra league (file holds all seasons)."""
    ds = cfg["data_source"]
    targets = []
    for league in ds["main_leagues"]:
        for season in ds["seasons"][league]:
            url = ds["main_url_pattern"].format(
                base_url=ds["base_url"], season_code=season, league_code=league
            )
            targets.append(
                {"league": league, "season": str(season), "url": url,
                 "rel_path": f"{league}_{season}.csv"}
            )
    for league in ds["extra_leagues"]:
        url = ds["extra_url_pattern"].format(base_url=ds["base_url"], league_code=league)
        targets.append(
            {"league": league, "season": "all", "url": url, "rel_path": f"{league}_all.csv"}
        )
    return targets


def add_raw_file(content: bytes, rel_path: str, raw_dir, manifest_path) -> Path:
    """Create a new read-only raw file and append its manifest line. Never overwrites."""
    target = Path(raw_dir) / rel_path
    if target.exists():
        raise FileExistsError(f"Raw file already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "xb") as fh:
        fh.write(content)
    make_read_only(target)
    digest = hashlib.sha256(content).hexdigest()
    manifest = Path(manifest_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(f"{digest}  {Path(rel_path).as_posix()}\n")
    return target


def make_http_fetch(cfg):
    """Default fetch(url) -> (status, bytes); follows redirects."""
    ds = cfg["data_source"]

    def fetch(url):
        req = urllib.request.Request(url, headers={"User-Agent": ds["user_agent"]})
        try:
            with urllib.request.urlopen(req, timeout=ds["timeout_seconds"]) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, b""

    return fetch


def download_all(cfg, snapshot_date: str, fetch=None) -> pd.DataFrame:
    ds = cfg["data_source"]
    paths = cfg["paths"]
    if fetch is None:
        fetch = make_http_fetch(cfg)
    rows = []
    for i, t in enumerate(build_targets(cfg)):
        if i and ds["request_delay_seconds"]:
            time.sleep(ds["request_delay_seconds"])
        status, content = 0, b""
        for _attempt in range(1 + ds["max_retries"]):
            try:
                status, content = fetch(t["url"])
            except Exception:  # noqa: BLE001 - any fetch failure is logged, not raised
                status, content = 0, b""
            if status == 200:
                break
        rel = f"{RAW_SUBDIR}/{snapshot_date}/{t['rel_path']}"
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if status == 200:
            add_raw_file(content, rel, paths["raw"], paths["manifest"])
            rows.append([t["url"], rel, stamp, status, len(content),
                         hashlib.sha256(content).hexdigest()])
        else:
            rows.append([t["url"], rel, stamp, status, 0, ""])
    out = pd.DataFrame(rows, columns=LOG_COLUMNS)
    log = Path(paths["download_log"])
    log.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(log, mode="a", header=not log.exists(), index=False)
    return out

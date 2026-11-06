"""Read raw football-data CSV files without touching them on disk."""
import io
from pathlib import Path

import pandas as pd

ENCODINGS = (("utf-8-sig", "utf-8"), ("cp1252", "cp1252"), ("latin-1", "latin-1"))


def read_raw_csv(path) -> tuple[pd.DataFrame, str]:
    """Return (frame, encoding label). Empty trailing columns and blank rows are
    dropped in memory only."""
    data = Path(path).read_bytes()
    last_err = None
    for codec, label in ENCODINGS:
        try:
            text = data.decode(codec)
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
        df = pd.read_csv(io.StringIO(text), skip_blank_lines=True)
        df = df.dropna(how="all")
        # drop fully empty trailing columns (kept: empty columns followed by data columns)
        keep = len(df.columns)
        while keep > 0 and df.iloc[:, keep - 1].isna().all():
            keep -= 1
        df = df.iloc[:, :keep].reset_index(drop=True)
        return df, label
    raise last_err  # pragma: no cover - latin-1 decodes any byte string

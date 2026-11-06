import hashlib

import pandas as pd

from fbmodel.data.read_raw import read_raw_csv


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_utf8_plain(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes("Home,Away\nRoma,Lazio\n".encode("utf-8"))
    df, enc = read_raw_csv(p)
    assert enc == "utf-8"
    assert list(df.columns) == ["Home", "Away"]
    assert str(df.loc[0, "Home"]) == "Roma"


def test_utf8_bom_stripped(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"\xef\xbb\xbfDiv,Date\nI1,01/01/2025\n")
    df, enc = read_raw_csv(p)
    assert enc == "utf-8"
    assert list(df.columns)[0] == "Div"


def test_cp1252_fallback(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes("Home,Away\nCafé,Lazio\n".encode("cp1252"))
    df, enc = read_raw_csv(p)
    assert enc == "cp1252"
    assert str(df.loc[0, "Home"]) == "Café"


def test_latin1_fallback_on_undefined_cp1252_byte(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"Home,Away\nA\x81B,Lazio\n")
    df, enc = read_raw_csv(p)
    assert enc == "latin-1"
    assert len(df) == 1


def test_drops_empty_trailing_columns_and_blank_rows_file_unchanged(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"A,B,,\n1,2,,\n,,,\n3,4,,\n")
    before = _sha(p)
    df, enc = read_raw_csv(p)
    assert list(df.columns) == ["A", "B"]
    assert len(df) == 2
    assert [float(x) for x in pd.to_numeric(df["A"])] == [1.0, 3.0]
    assert [float(x) for x in pd.to_numeric(df["B"])] == [2.0, 4.0]
    assert _sha(p) == before


def test_file_unchanged_after_read(tmp_path):
    p = tmp_path / "a.csv"
    p.write_bytes(b"\xef\xbb\xbfX,Y\n1,2\n")
    before = _sha(p)
    read_raw_csv(p)
    assert _sha(p) == before

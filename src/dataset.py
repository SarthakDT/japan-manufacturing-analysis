"""
dataset.py — the single canonical loader for validated prefecture x industry CSVs.

Three modules previously carried their own near-identical loader:
`shift_share.load_cells`, `build_panel.load_industry_slice` and
`lq_break_test.load_employment`. They read the same path pattern with the same
dtypes and differed only in which filter they applied, so a change to the file
layout or the dtype handling had to be made in three places to stay correct.

This module owns that read. Callers choose a filter, not a file path.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "processed_data"

# prefecture_code and industry_code are zero-padded identifiers, not integers.
# Reading them as int would silently turn "09" into 9 and break every join.
ID_DTYPES = {"prefecture_code": str, "industry_code": str}


def slice_path(year: int, table: str = "3-01") -> Path:
    return PROCESSED / f"manufacturing_{year}_table{table}.csv"


def load_cells(year: int, table: str = "3-01", *,
               usable_only: bool = False) -> pd.DataFrame:
    """Validated prefecture x industry cells for one reference year.

    usable_only=True keeps only cells where value added and employment are both
    flagged `ok` and employment is positive — the filter required for any ratio
    with employment in the denominator. Left False, every cell in the 47 x 24
    grid is returned, including suppressed ones carrying NaN and a flag.
    """
    path = slice_path(year, table)
    if not path.exists():
        raise SystemExit(f"missing {path}. Run validate_manufacturing.py first.")
    df = pd.read_csv(path, dtype=ID_DTYPES)
    if usable_only:
        df = df[(df.value_added_flag == "ok")
                & (df.employment_flag == "ok")
                & (df.employment > 0)].copy()
    return df


def load_panel() -> pd.DataFrame:
    """The prefecture x year analysis panel."""
    path = PROCESSED / "panel_prefecture_year.csv"
    if not path.exists():
        raise SystemExit(f"missing {path}. Run build_panel.py first.")
    return pd.read_csv(path, dtype={"prefecture_code": str, "top_industry_code": str})


def available_slices() -> pd.DataFrame:
    """Every validated slice on disk, as (reference_year, table, path)."""
    rows = []
    for p in sorted(PROCESSED.glob("manufacturing_*_table*.csv")):
        stem = p.stem.replace("manufacturing_", "")
        year, _, table = stem.partition("_table")
        rows.append({"reference_year": int(year), "table": table, "path": p})
    return pd.DataFrame(rows)


def ensure_utf8_stdout() -> None:
    """Make stdout UTF-8 safe.

    These scripts print Japanese prefecture and industry names. On Windows the
    default console encoding is cp1252, which raises UnicodeEncodeError and
    kills the script part-way through — after some work, before writing output.
    Reconfiguring here means the repo runs from a bare terminal without the
    caller having to set PYTHONIOENCODING first.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass  # already wrapped, or not a real stream (e.g. under nbconvert)

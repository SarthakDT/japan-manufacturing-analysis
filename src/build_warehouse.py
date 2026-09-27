"""
build_warehouse.py — load the validated CSVs into one queryable DuckDB file.

WHY THIS EXISTS
The project holds 14 validated CSVs across three source tables and five
reference years. Any cross-table or cross-year question — "capital intensity
against productivity by industry", "which cells moved rank most" — previously
needed a bespoke Python script to locate, read and join the right files. One
consolidated store removes that.

WHAT IT IS NOT
Not a data warehouse in the dimensional sense, and not a second implementation
of the project's metrics. The location quotient and Herfindahl index stay in
src/metrics.py; re-deriving them in SQL would recreate the duplication that
Session 08 set out to remove. See docs/concepts.md section 7.

ENGINE
DuckDB, embedded, so there is no server to run and the repo stays clone-and-run.
The SQL is Postgres dialect and avoids DuckDB-only syntax where a standard form
exists, so it ports with little change.

Usage:
    python src/build_warehouse.py --rebuild --check
    python src/build_warehouse.py --query "SELECT * FROM v_productivity LIMIT 5"
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import available_slices, ensure_utf8_stdout, load_cells, load_panel
from viz_style import INDUSTRY_EN, ROMAJI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = PROJECT_ROOT / "sql"
DB_PATH = PROJECT_ROOT / "warehouse" / "japan_manufacturing.duckdb"

# Which coverage each source table describes. Recorded on every row so a query
# can never silently mix 4+ and 30+ establishments, which are different
# populations rather than a sample of one another.
SIZE_CLASS = {"3-01": "4+", "muni3-01": "4+", "3-03": "30+", "3-04": "30+"}

# Columns that are identifiers rather than measures.
NON_MEASURE = {"year", "prefecture_code", "prefecture_name",
               "industry_code", "industry_name"}


def melt_slice(df: pd.DataFrame, year: int, table: str) -> pd.DataFrame:
    """Turn one wide validated CSV into long (cell, measure, value, flag) rows."""
    measures = [c for c in df.columns
                if c not in NON_MEASURE and not c.endswith("_flag")]
    blocks = []
    for m in measures:
        flag_col = m + "_flag"
        if flag_col in df.columns:
            flags = df[flag_col]
        else:
            # A few derived columns carry no flag. Mark present values 'ok' so
            # `flag` is never null and the not-ok/not-null check stays meaningful.
            flags = df[m].notna().map({True: "ok", False: "absent_from_source"})
        blocks.append(pd.DataFrame({
            "reference_year": year,
            "prefecture_code": df["prefecture_code"],
            "prefecture_name": df["prefecture_name"],
            "industry_code": df["industry_code"],
            "industry_name": df["industry_name"],
            "source_table": table,
            "size_class": SIZE_CLASS[table],
            "measure": m,
            "value": df[m],
            "flag": flags,
        }))
    return pd.concat(blocks, ignore_index=True)


def build(con: duckdb.DuckDBPyConnection) -> dict:
    con.execute((SQL_DIR / "01_build.sql").read_text(encoding="utf-8"))

    slices = available_slices()
    frames = [melt_slice(load_cells(r.reference_year, r.table), r.reference_year, r.table)
              for r in slices.itertuples()]
    facts = pd.concat(frames, ignore_index=True)

    # NULL out every non-ok value so no query can treat a suppressed cell as a
    # number. The flag stays, so the reason is still recoverable.
    facts.loc[facts["flag"] != "ok", "value"] = None

    con.register("facts_df", facts)
    con.execute("INSERT INTO fact_cells SELECT * FROM facts_df")

    name_by_code = (facts.drop_duplicates("prefecture_code")
                    .set_index("prefecture_code")["prefecture_name"])
    pref = pd.DataFrame({"prefecture_code": sorted(name_by_code.index)})
    pref["name_ja"] = pref.prefecture_code.map(name_by_code)
    pref["name_romaji"] = pref.name_ja.map(ROMAJI).fillna(pref.name_ja)
    con.register("pref_df", pref)
    con.execute("INSERT INTO dim_prefecture SELECT * FROM pref_df")

    ind_ja = (facts.drop_duplicates("industry_code")
              .set_index("industry_code")["industry_name"])
    ind = pd.DataFrame({"industry_code": sorted(ind_ja.index)})
    ind["name_ja"] = ind.industry_code.map(ind_ja)
    ind["name_en"] = ind.industry_code.map(INDUSTRY_EN).fillna("Total, all manufacturing")
    con.register("ind_df", ind)
    con.execute("INSERT INTO dim_industry SELECT * FROM ind_df")

    panel = load_panel().rename(columns={"year": "reference_year",
                                         "value_added_total": "value_added",
                                         "employment_total": "employment",
                                         "establishments_total": "establishments"})
    panel_cols = ["reference_year", "prefecture_code", "prefecture_name", "instrument",
                  "value_added", "employment", "establishments", "va_per_worker",
                  "hhi_employment", "lq_top", "aging_ratio", "mfg_intensity"]
    con.register("panel_df", panel[panel_cols])
    con.execute("INSERT INTO fact_panel SELECT * FROM panel_df")

    con.execute((SQL_DIR / "02_views.sql").read_text(encoding="utf-8"))

    return {"slices": len(slices), "fact_rows": len(facts),
            "panel_rows": len(panel),
            "prefectures": len(pref), "industries": len(ind)}


def check(con: duckdb.DuckDBPyConnection) -> int:
    """Load checks.

    These confirm the CSVs arrived intact and the view logic is sound. They are
    NOT independent validation of the metrics: both sides share an author and
    the same reading of the source, so a conceptual error would sit in both.
    Reported as a load check, nothing more.
    """
    print("load checks:")
    failures = 0

    def report(label, ok, detail=""):
        nonlocal failures
        suffix = ("  -> " + detail) if detail and not ok else ""
        print("  [{}] {}{}".format("PASS" if ok else "FAIL", label, suffix))
        failures += (not ok)

    expected = 0
    for r in available_slices().itertuples():
        df = load_cells(r.reference_year, r.table)
        n_meas = len([c for c in df.columns
                      if c not in NON_MEASURE and not c.endswith("_flag")])
        expected += len(df) * n_meas
    got = con.execute("SELECT COUNT(*) FROM fact_cells").fetchone()[0]
    report("fact_cells row count equals the sum over slices ({:,})".format(expected),
           got == expected, "got {:,}".format(got))

    got = con.execute(
        "SELECT COUNT(*) FROM fact_cells WHERE flag <> 'ok' AND value IS NOT NULL"
    ).fetchone()[0]
    report("no non-ok row carries a value", got == 0, "{} rows".format(got))

    got = con.execute(
        "SELECT COUNT(DISTINCT prefecture_code) FROM fact_cells WHERE industry_code <> '00'"
    ).fetchone()[0]
    report("47 prefectures present", got == 47, "got {}".format(got))

    got = con.execute("SELECT COUNT(*) FROM fact_cells WHERE flag IS NULL").fetchone()[0]
    report("flag is never null", got == 0, "{} rows".format(got))

    panel = load_panel()
    got = con.execute("SELECT COUNT(*) FROM fact_panel").fetchone()[0]
    report("fact_panel loaded all {} panel rows".format(len(panel)),
           got == len(panel), "got {}".format(got))

    # Cross-grain sanity: visible industry cells can never exceed the published
    # prefecture total. If they do, the two grains have been misaligned.
    got = con.execute(
        "SELECT COUNT(*) FROM (SELECT DISTINCT reference_year, prefecture_code, "
        "visible_coverage FROM v_cell_share_of_prefecture) WHERE visible_coverage > 1.0001"
    ).fetchone()[0]
    report("no prefecture has visible cells exceeding its published total",
           got == 0, "{} prefecture-years".format(got))

    # The shortfall must be the documented suppression, not a load error. The
    # panel computes its own va_coverage_pct by a different route (pandas sum
    # over cells against the published total row), so agreement between the two
    # is a genuine cross-check rather than a restatement.
    sql_cov = con.execute(
        "SELECT DISTINCT reference_year AS year, prefecture_code, visible_coverage "
        "FROM v_cell_share_of_prefecture"
    ).df()
    ref = panel[panel.va_coverage_pct.notna()][["year", "prefecture_code", "va_coverage_pct"]]
    m = ref.merge(sql_cov, on=["year", "prefecture_code"])
    worst = (m.va_coverage_pct / 100 - m.visible_coverage).abs().max() if len(m) else 1.0
    report("warehouse coverage matches the panel's own va_coverage_pct "
           "on all {} rows (worst {:.2e})".format(len(m), worst),
           len(m) == len(ref) and worst < 1e-9)

    lo = con.execute(
        "SELECT MIN(visible_coverage) FROM (SELECT DISTINCT reference_year, "
        "prefecture_code, visible_coverage FROM v_cell_share_of_prefecture)"
    ).fetchone()[0]
    # Floor is Shimane 2016 at 0.9476: chemicals and non-ferrous metals both
    # suppressed, two high-value industries, so 5.2% of value added is hidden.
    report("visible coverage never below 94% (min {:.4f})".format(lo), lo > 0.94)

    print("\nload checks: {}".format("ALL PASSED" if not failures
                                     else "{} FAILED".format(failures)))
    return 0 if not failures else 1


def run_questions(con: duckdb.DuckDBPyConnection) -> int:
    """Execute the named queries in sql/03_questions.sql and print each result."""
    text = (SQL_DIR / "03_questions.sql").read_text(encoding="utf-8")
    for chunk in text.split("-- name: ")[1:]:
        name, _, body = chunk.partition(chr(10))
        # Strip line comments BEFORE splitting on the statement terminator.
        # Splitting first truncates at any semicolon inside a comment, which
        # silently produced an unparseable fragment.
        stripped = chr(10).join(re.sub(r"--.*$", "", ln) for ln in body.split(chr(10)))
        stmt = stripped.split(";")[0]
        print()
        print("=" * 72)
        print(name.strip())
        print("=" * 72)
        print(con.execute(stmt).df().to_string(index=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rebuild", action="store_true", help="drop and reload")
    ap.add_argument("--check", action="store_true", help="run load checks")
    ap.add_argument("--query", help="run one SQL statement and print the result")
    ap.add_argument("--questions", action="store_true",
                    help="run sql/03_questions.sql and print each named result")
    args = ap.parse_args(argv)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if args.rebuild and DB_PATH.exists():
        DB_PATH.unlink()

    con = duckdb.connect(str(DB_PATH))
    try:
        exists = con.execute(
            "SELECT COUNT(*) FROM duckdb_tables() WHERE table_name = 'fact_cells'"
        ).fetchone()[0]
        if args.rebuild or not exists:
            info = build(con)
            print("built {}: {:,} cell rows from {} slices, {} panel rows, "
                  "{} prefectures, {} industries".format(
                      DB_PATH.name, info["fact_rows"], info["slices"],
                      info["panel_rows"], info["prefectures"], info["industries"]))
        if args.query:
            print(con.execute(args.query).df().to_string(index=False))
            return 0
        if args.questions:
            return run_questions(con)
        if args.check:
            return check(con)
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())

"""
build_dashboard_data.py — the one extract both dashboards read.

WHY THIS EXISTS
The project has two front-ends: a Power BI report the author builds by hand from
dashboard/POWER_BI_GUIDE.md, and a Streamlit app in app/. If each computed its
own shift-share, location quotients or residuals, the two would drift, and
neither could be checked against the other. So every derived number is computed
here, once, by the modules that already own it, and both front-ends only filter
and aggregate what this script writes.

    e-Stat -> validation -> processed CSVs -> DuckDB + SQL views -> THIS -> dashboards

WHY A STAR SCHEMA HERE, WHEN sql/01_build.sql REFUSED ONE
The DuckDB store serves ad-hoc SQL over one fact grain, where dimensions would
be ceremony. Power BI is different: its filter propagation runs along
relationships from dimension tables to fact tables, and a slicer on a column
that lives only inside a fact table cannot filter a second fact table. Same
principle - build the structure the consuming tool needs - different tool,
different answer. See docs/concepts.md section 8.

TABLES (dashboard/data/, UTF-8 with BOM so Excel and Power BI read Japanese)
    dim_prefecture             47 rows   code, names, region, map location
    dim_industry               24 rows   JSIC 2-digit code, names
    dim_year                    5 rows   instrument, whether industry detail exists
    fact_prefecture_year      235 rows   headline figures + shift-share + diagnosis
    fact_prefecture_industry  4,512 rows  cells, LQ, shares, median-polish residual
    fact_industry_year         96 rows   national VA/worker, capital per worker (30+)
    fact_waterfall            752 rows   4 steps per prefecture-year, for a waterfall

The script refuses to write anything if a check fails.

Usage:
    python src/build_dashboard_data.py
    python src/build_dashboard_data.py --check-only    # build and check, write nothing
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from anomaly_detect import analyse as median_polish_analysis
from build_warehouse import build as build_warehouse
from dataset import ensure_utf8_stdout, load_cells, load_panel
from metrics import employment_share, location_quotient
from shift_share import decompose, load_cells as load_usable_cells
from viz_style import INDUSTRY_EN, ROMAJI

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "dashboard" / "data"
EXPECTED_PATH = PROJECT_ROOT / "dashboard" / "expected_values.md"

DETAIL_YEARS = [2016, 2017, 2018, 2019]   # years with industry detail (Census of Manufacture)
TOLERANCE = 1e-9

# The eight standard regions (地方区分), by JIS prefecture code. Mie (24) is
# placed in Kinki, as in the MIC/Statistics Bureau convention; some sources put
# it in Chubu (Tokai). Recorded here so the choice is visible, not implied.
REGIONS = [
    ("Hokkaido", range(1, 2)),
    ("Tohoku", range(2, 8)),
    ("Kanto", range(8, 15)),
    ("Chubu", range(15, 24)),
    ("Kinki", range(24, 31)),
    ("Chugoku", range(31, 36)),
    ("Shikoku", range(36, 40)),
    ("Kyushu-Okinawa", range(40, 48)),
]

# Quadrant labels. Diagnostic wording on purpose: each says where the gap sits,
# not what to do about it. See docs/concepts.md section 8 (diagnostic vs
# prescriptive).
DIAGNOSIS = {
    (True, True): "Strong mix, strong performance",
    (False, True): "Weak mix, strong performance",
    (True, False): "Strong mix, weak performance",
    (False, False): "Weak mix, weak performance",
}

WATERFALL_STEPS = [
    (1, "National benchmark"),
    (2, "Industry mix"),
    (3, "Within-industry performance"),
    (4, "Suppression adjustment"),
]


def region_of(code: str) -> str:
    n = int(code)
    for name, rng in REGIONS:
        if n in rng:
            return name
    raise ValueError(f"no region for prefecture code {code}")


# --- dimensions ---------------------------------------------------------------

def build_dim_prefecture(panel: pd.DataFrame) -> pd.DataFrame:
    d = (panel.drop_duplicates("prefecture_code")
         [["prefecture_code", "prefecture_name"]]
         .rename(columns={"prefecture_name": "name_ja"})
         .sort_values("prefecture_code").reset_index(drop=True))
    d["name_en"] = d.name_ja.map(ROMAJI)
    d["region"] = d.prefecture_code.map(region_of)
    d["region_order"] = d.region.map({name: i + 1 for i, (name, _) in enumerate(REGIONS)})
    # "Aichi Prefecture, Japan" geocodes unambiguously in Power BI's map visuals;
    # a bare "Aichi" can resolve to a city of the same name.
    d["map_location"] = d.name_en.map(lambda n: f"{n} Prefecture, Japan")
    return d


def build_dim_industry() -> pd.DataFrame:
    cells = load_cells(DETAIL_YEARS[-1])
    d = (cells.drop_duplicates("industry_code")[["industry_code", "industry_name"]]
         .rename(columns={"industry_name": "name_ja"})
         .sort_values("industry_code").reset_index(drop=True))
    d["name_en"] = d.industry_code.map(INDUSTRY_EN)
    return d


def build_dim_year(panel: pd.DataFrame) -> pd.DataFrame:
    d = (panel.groupby("year").instrument.first().reset_index()
         .rename(columns={"year": "reference_year"}))
    d["has_industry_detail"] = d.reference_year.isin(DETAIL_YEARS)
    # Survey editions are labelled one year later than the data they hold.
    # docs/reference-years.md has the proof.
    d["source_edition"] = np.where(
        d.instrument == "CoM",
        d.reference_year.map(lambda y: f"Census of Manufacture, {y + 1} edition"),
        "2021 Economic Census for Business Activity")
    return d


# --- facts --------------------------------------------------------------------

def build_fact_prefecture_year(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Headline figures from the panel plus shift-share, and the raw decomposition."""
    base = panel.rename(columns={"year": "reference_year",
                                 "value_added_total": "value_added",
                                 "employment_total": "employment",
                                 "establishments_total": "establishments"})
    base = base[["reference_year", "prefecture_code", "instrument", "value_added",
                 "employment", "establishments", "va_per_worker", "hhi_employment",
                 "top_industry_code", "lq_top", "va_coverage_pct",
                 "pop_total", "aging_ratio", "mfg_intensity"]].copy()

    # Rank within year on the published-total basis, 1 = highest.
    base["rank_va_per_worker"] = (base.groupby("reference_year").va_per_worker
                                  .rank(ascending=False, method="min").astype(int))
    nat = base.groupby("reference_year")[["value_added", "employment"]].sum()
    base["national_va_per_worker"] = base.reference_year.map(nat.value_added / nat.employment)
    base["gap_to_national"] = base.va_per_worker - base.national_va_per_worker
    base["share_of_national_va"] = base.value_added / base.reference_year.map(nat.value_added)

    ss = pd.concat([decompose(load_usable_cells(y), y) for y in DETAIL_YEARS],
                   ignore_index=True).rename(columns={"year": "reference_year"})
    ss_cols = ss[["reference_year", "prefecture_code", "benchmark", "mix_effect",
                  "within_effect", "va_per_worker"]].rename(
        columns={"benchmark": "shift_share_benchmark",
                 "va_per_worker": "va_per_worker_visible_cells"})

    out = base.merge(ss_cols, on=["reference_year", "prefecture_code"], how="left")
    out["suppression_adjustment"] = out.va_per_worker - out.va_per_worker_visible_cells
    has = out.mix_effect.notna()
    out["diagnosis"] = None
    out.loc[has, "diagnosis"] = [DIAGNOSIS[(m > 0, w > 0)]
                                 for m, w in zip(out.loc[has, "mix_effect"],
                                                 out.loc[has, "within_effect"])]
    out = out.sort_values(["reference_year", "prefecture_code"]).reset_index(drop=True)
    return out, ss


def build_fact_prefecture_industry() -> pd.DataFrame:
    frames = []
    for y in DETAIL_YEARS:
        cells = load_cells(y)  # full 47 x 24 grid, suppressed cells kept as NaN + flag
        d = cells[["prefecture_code", "industry_code", "establishments", "employment",
                   "value_added", "value_added_flag"]].copy()
        d.insert(0, "reference_year", y)

        usable = ((cells.value_added_flag == "ok") & (cells.employment_flag == "ok")
                  & (cells.employment > 0))
        d["va_per_worker"] = np.where(usable, cells.value_added / cells.employment, np.nan)

        d["employment_share"] = employment_share(cells).values
        d["lq"] = location_quotient(cells).values
        emp = cells.employment.fillna(0.0)
        d["national_employment_share"] = (cells.industry_code.map(
            emp.groupby(cells.industry_code).sum()) / emp.sum()).values

        mp = median_polish_analysis(y)["long"][["prefecture_code", "industry_code",
                                                "residual", "pct_vs_expected"]]
        d = d.merge(mp.rename(columns={"residual": "residual_log"}),
                    on=["prefecture_code", "industry_code"], how="left")
        frames.append(d)
    return (pd.concat(frames, ignore_index=True)
            .sort_values(["reference_year", "prefecture_code", "industry_code"])
            .reset_index(drop=True))


def build_fact_industry_year() -> pd.DataFrame:
    # National VA/worker per industry on the 4+ basis, from the same usable
    # cells the shift-share uses, so the benchmark and this table agree.
    rows = []
    for y in DETAIL_YEARS:
        c = load_usable_cells(y)
        g = c.groupby("industry_code")[["value_added", "employment"]].sum()
        rows.append(pd.DataFrame({
            "reference_year": y, "industry_code": g.index,
            "value_added": g.value_added.values, "employment": g.employment.values,
            "national_va_per_worker": (g.value_added / g.employment).values}))
    nat = pd.concat(rows, ignore_index=True)

    # Capital intensity comes from the SQL layer, built fresh in memory from the
    # committed CSVs so this script never depends on a stale warehouse file.
    con = duckdb.connect()
    try:
        build_warehouse(con)
        cap = con.execute("SELECT * FROM v_industry_capital_intensity").df()
    finally:
        con.close()
    cap["reference_year"] = cap.reference_year.astype(int)
    # The sums travel with the ratios so Power BI can aggregate as a ratio of
    # sums; a ratio column alone can only be averaged, which is wrong.
    out = nat.merge(cap[["reference_year", "industry_code", "cells_matched",
                         "employment_30plus", "value_added_30plus", "capital_stock_30plus",
                         "capital_per_worker_30plus", "va_per_worker_30plus"]],
                    on=["reference_year", "industry_code"], how="left")
    return out.sort_values(["reference_year", "industry_code"]).reset_index(drop=True)


def build_fact_waterfall(fpy: pd.DataFrame) -> pd.DataFrame:
    d = fpy[fpy.mix_effect.notna()]
    parts = {1: d.shift_share_benchmark, 2: d.mix_effect,
             3: d.within_effect, 4: d.suppression_adjustment}
    frames = [pd.DataFrame({"reference_year": d.reference_year,
                            "prefecture_code": d.prefecture_code,
                            "step_order": order, "step": name,
                            "amount": parts[order].values})
              for order, name in WATERFALL_STEPS]
    return (pd.concat(frames, ignore_index=True)
            .sort_values(["reference_year", "prefecture_code", "step_order"])
            .reset_index(drop=True))


# --- checks -------------------------------------------------------------------

def run_checks(t: dict[str, pd.DataFrame], panel: pd.DataFrame) -> int:
    failures = 0

    def report(label, ok, detail=""):
        nonlocal failures
        print("  [{}] {}{}".format("PASS" if ok else "FAIL", label,
                                   ("  -> " + detail) if detail and not ok else ""))
        failures += (not ok)

    print("dashboard extract checks:")

    keys = {
        "dim_prefecture": ["prefecture_code"],
        "dim_industry": ["industry_code"],
        "dim_year": ["reference_year"],
        "fact_prefecture_year": ["reference_year", "prefecture_code"],
        "fact_prefecture_industry": ["reference_year", "prefecture_code", "industry_code"],
        "fact_industry_year": ["reference_year", "industry_code"],
        "fact_waterfall": ["reference_year", "prefecture_code", "step_order"],
    }
    for name, k in keys.items():
        dup = int(t[name].duplicated(k).sum())
        report(f"{name}: key ({', '.join(k)}) is unique", dup == 0, f"{dup} duplicates")

    report("dim_prefecture has 47 rows", len(t["dim_prefecture"]) == 47)
    report("dim_industry has 24 rows", len(t["dim_industry"]) == 24)
    report("every prefecture has a region and an English name",
           t["dim_prefecture"][["region", "name_en"]].notna().all().all())

    # Referential integrity. In Power BI an orphan key does not raise an error;
    # it lands in a silent "(Blank)" member and its values vanish from slicers.
    dims = {"prefecture_code": set(t["dim_prefecture"].prefecture_code),
            "industry_code": set(t["dim_industry"].industry_code),
            "reference_year": set(t["dim_year"].reference_year)}
    for name, k in keys.items():
        if not name.startswith("fact_"):
            continue
        for col in k:
            if col in dims:
                orphans = set(t[name][col]) - dims[col]
                report(f"{name}.{col}: every key exists in its dimension",
                       not orphans, f"orphans {sorted(orphans)[:5]}")
    orphans = set(t["fact_prefecture_year"].top_industry_code.dropna()) - dims["industry_code"]
    report("fact_prefecture_year.top_industry_code exists in dim_industry", not orphans)

    # Reconciliation to the committed panel, on the columns copied from it.
    fpy = t["fact_prefecture_year"]
    ref = panel.rename(columns={"year": "reference_year"}).merge(
        fpy, on=["reference_year", "prefecture_code"], suffixes=("_panel", ""))
    report("fact_prefecture_year covers every panel row",
           len(ref) == len(panel) == len(fpy), f"{len(ref)} vs {len(panel)}")
    for a, b in [("value_added_total", "value_added"), ("employment_total", "employment"),
                 ("va_per_worker_panel", "va_per_worker")]:
        worst = float((ref[a] - ref[b]).abs().max())
        report(f"{b} reconciles to the panel (worst {worst:.1e})", worst < TOLERANCE)

    # The decomposition identity carried through: benchmark + mix + within
    # equals the visible-cell VA/worker, and the adjustment closes it to the
    # published figure the KPI card shows.
    wf = t["fact_waterfall"]
    closed = wf.groupby(["reference_year", "prefecture_code"]).amount.sum().rename("closed")
    chk = fpy.set_index(["reference_year", "prefecture_code"]).join(closed, how="inner")
    worst = float((chk.closed - chk.va_per_worker).abs().max())
    report(f"waterfall sums to published VA/worker for all {len(chk)} prefecture-years "
           f"(worst {worst:.1e})", len(chk) == 47 * len(DETAIL_YEARS) and worst < TOLERANCE)

    # 2020 has no industry detail. Its shift-share must be missing, never zero:
    # a zero would read as "exactly at benchmark" on the diagnosis chart.
    y20 = fpy[fpy.reference_year == 2020]
    report("2020 rows exist and carry null mix, within and diagnosis",
           len(y20) == 47 and y20[["mix_effect", "within_effect"]].isna().all().all()
           and y20.diagnosis.isna().all())
    report("no 2020 rows in the industry-grain facts",
           not (t["fact_prefecture_industry"].reference_year == 2020).any()
           and not (t["fact_industry_year"].reference_year == 2020).any())

    fpi = t["fact_prefecture_industry"]
    report("fact_prefecture_industry is the full 47 x 24 grid per year",
           len(fpi) == 47 * 24 * len(DETAIL_YEARS), f"{len(fpi)} rows")
    report("suppressed cells carry null VA/worker, never zero",
           fpi.loc[fpi.value_added_flag != "ok", "va_per_worker"].isna().all())
    s = fpi.groupby(["reference_year", "prefecture_code"]).employment_share.sum()
    report("employment shares sum to 1 per prefecture-year",
           float((s - 1).abs().max()) < TOLERANCE)

    counts = fpy[fpy.reference_year == 2019].diagnosis.value_counts()
    report("2019 diagnosis covers all 47 prefectures", int(counts.sum()) == 47,
           counts.to_dict().__repr__())

    fiy = t["fact_industry_year"]
    report("capital per worker present for every industry-year",
           fiy.capital_per_worker_30plus.notna().all(),
           f"{int(fiy.capital_per_worker_30plus.isna().sum())} missing")

    print("\ndashboard extract checks: {}".format(
        "ALL PASSED" if not failures else f"{failures} FAILED"))
    return failures


# --- expected values for manual Power BI verification ---------------------------

def write_expected_values(t: dict[str, pd.DataFrame]) -> str:
    fpy = t["fact_prefecture_year"].merge(t["dim_prefecture"], on="prefecture_code")
    y = fpy[fpy.reference_year == 2019].set_index("name_en")
    nat = y.national_va_per_worker.iloc[0]

    def signed(v):
        # Round first so a -0.001 prints as +0.00, not as a confusing -0.00.
        return f"{round(v, 2) + 0.0:+.2f}"

    def row(name):
        r = y.loc[name]
        return (f"| {name} | {r.va_per_worker:.2f} | {int(r.rank_va_per_worker)} | "
                f"{r.share_of_national_va:.2%} | {r.shift_share_benchmark:.2f} | "
                f"{signed(r.mix_effect)} | {signed(r.within_effect)} | "
                f"{signed(r.suppression_adjustment)} | {r.diagnosis} |")

    counts = y.diagnosis.value_counts()
    nat_by_year = (t["fact_prefecture_year"].groupby("reference_year")
                   [["value_added", "employment"]].sum())
    nat_rows = "\n".join(f"| {yr} | {r.value_added / r.employment:.2f} |"
                         for yr, r in nat_by_year.iterrows())

    fiy = t["fact_industry_year"].merge(t["dim_industry"], on="industry_code")
    fiy19 = fiy[fiy.reference_year == 2019].sort_values("national_va_per_worker",
                                                         ascending=False)
    top, bottom = fiy19.iloc[0], fiy19.iloc[-1]
    rho = fiy19[["capital_per_worker_30plus", "va_per_worker_30plus"]].rank().corr().iloc[0, 1]

    lines = [
        "# Expected values",
        "",
        "Generated by `src/build_dashboard_data.py` — do not edit by hand.",
        "",
        "The numbers a correct build of either dashboard should display. Use this as the",
        "checklist when building the Power BI report: if a card or tooltip disagrees",
        "with a figure here, the DAX is wrong, not the data. The Streamlit app is",
        "checked against the same figures automatically by `src/run_checks.py`.",
        "",
        "Units: value added in million yen per worker, nominal. Reference year 2019",
        "unless stated.",
        "",
        "## National value added per worker (ratio of sums over all 47 prefectures)",
        "",
        "| Reference year | VA per worker |",
        "|---|---|",
        nat_rows,
        "",
        f"With **no prefecture selected**, the Overview KPI card for 2019 must read "
        f"**{nat:.2f}**. If it reads a different number, the measure is averaging the "
        f"`va_per_worker` column instead of dividing summed value added by summed "
        f"employment.",
        "",
        "## Prefecture benchmark page, 2019",
        "",
        "| Prefecture | VA per worker | Rank of 47 | Share of national VA | Benchmark "
        "| Industry mix | Within-industry | Suppression adj. | Diagnosis |",
        "|---|---|---|---|---|---|---|---|---|",
        *[row(n) for n in ["Aichi", "Yamaguchi", "Tokyo", "Osaka", "Kochi", "Okinawa"]],
        "",
        "Benchmark + industry mix + within-industry + suppression adjustment equals VA",
        "per worker exactly; the waterfall's total bar must match the KPI card.",
        "",
        "## Diagnosis page, 2019",
        "",
        "| Diagnosis | Prefectures |",
        "|---|---|",
        *[f"| {k} | {int(counts.get(k, 0))} |" for k in DIAGNOSIS.values()],
        "",
        "## Industry context page, 2019",
        "",
        f"- Highest national VA per worker: **{top.name_en}** at "
        f"{top.national_va_per_worker:.2f}",
        f"- Lowest: **{bottom.name_en}** at {bottom.national_va_per_worker:.2f}",
        f"- Spearman rank correlation of capital per worker with VA per worker across the "
        f"24 industries (30+ basis, matched cells): **{rho:+.2f}**",
        "",
        "This is lower than the +0.72 in the README, which pools 2016-2019 in",
        "`sql/03_questions.sql` Q1. Year by year on matched cells it runs +0.63 to",
        "+0.73; the dashboard shows one year at a time, so expect the single-year value.",
        "",
        "## Filters that must return blank",
        "",
        "- Industry mix, within-industry and diagnosis with **2020** selected: the 2021",
        "  Economic Census has no prefecture x industry detail.",
        "- Industry mix and within-industry with **several prefectures** selected: they",
        "  are non-additive, so summing them across prefectures is meaningless.",
        "",
    ]
    return "\n".join(lines)


def build_all() -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    panel = load_panel()
    fpy, _ = build_fact_prefecture_year(panel)
    tables = {
        "dim_prefecture": build_dim_prefecture(panel),
        "dim_industry": build_dim_industry(),
        "dim_year": build_dim_year(panel),
        "fact_prefecture_year": fpy,
        "fact_prefecture_industry": build_fact_prefecture_industry(),
        "fact_industry_year": build_fact_industry_year(),
        "fact_waterfall": build_fact_waterfall(fpy),
    }
    return tables, panel


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check-only", action="store_true",
                    help="build and check the extract without writing it")
    args = ap.parse_args(argv)

    tables, panel = build_all()
    if run_checks(tables, panel):
        print("refusing to write the extract: checks failed")
        return 1
    if args.check_only:
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        # Full float precision so a reconciliation downstream is not defeated by
        # rounding on write; dashboards format for display themselves.
        df.to_csv(OUT_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")
        print(f"wrote {name}.csv  ({len(df):,} rows)")
    EXPECTED_PATH.write_text(write_expected_values(tables), encoding="utf-8")
    print(f"wrote {EXPECTED_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

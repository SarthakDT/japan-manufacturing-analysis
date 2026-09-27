"""
build_panel.py — collapse the prefecture x industry x year slices into the
prefecture x year analysis table.

Two sources, deliberately:

  * Prefecture TOTALS come from the 【00】製造業計 row in the raw JSON.
    `validate_manufacturing.py` excludes that row (it is a total, not an
    industry), but summing the 24 industries understates a prefecture because
    confidentiality-suppressed cells drop out of the sum. The 【00】 row carries
    the true total including those establishments. For reference year 2019 the
    understatement is ~0.03% on value added; small, but free to avoid.

  * Industry SHARES for the location quotient and the diversity index come from
    the validated CSVs, where shares must sum to 1 across the 24 industries.

Employment is never suppressed in these tables, so the two agree on employment
and differ only on value added. `va_coverage_pct` reports the gap per row.

Usage:
    python src/build_panel.py
    python src/build_panel.py --years 2016 2017 2018 2019 --table 3-01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_manufacturing import (  # noqa: E402  reuse, do not duplicate
    MEASURE_MAP,
    PREF_NAME_TO_CODE,
    PREFECTURES,
    TOTAL_INDUSTRY_CODE,
    classify_value,
    load_pages,
    normalise_measure_name,
    normalise_pref_name,
    parse_industry,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "raw_data" / "manufacturing"
PROCESSED = PROJECT_ROOT / "processed_data"

DEFAULT_YEARS = [2016, 2017, 2018, 2019]
DEFAULT_TABLE = "3-01"


DEFAULT_TOTAL_MEASURES = ("value_added", "employment", "establishments")


def load_prefecture_totals(year: int, table: str,
                           measures: tuple[str, ...] = DEFAULT_TOTAL_MEASURES) -> pd.DataFrame:
    """Pull the 【00】製造業計 row per prefecture straight from the raw pages.

    `measures` selects which mapped measures to return, so the same loader serves
    the main panel (value added, employment, establishments from tables 3-01/3-03)
    and the capital-stock table 3-04.
    """
    pages = sorted((RAW_ROOT / str(year)).glob(f"table{table}_*_p*.json"))
    if not pages:
        raise SystemExit(f"no raw pages for {year} table {table} in {RAW_ROOT / str(year)}")

    df_long, code_to_name, extra = load_pages(pages)
    roles = extra["dim_roles"]
    role_to_dim: dict[str, str] = {}
    for dim_id, role in roles.items():
        role_to_dim.setdefault(role, dim_id)

    d_measure, d_area, d_industry = (role_to_dim["measure"],
                                     role_to_dim["area"],
                                     role_to_dim["industry"])

    work = df_long.copy()
    work["measure"] = (work[d_measure].map(code_to_name[d_measure]).fillna("")
                       .map(lambda s: MEASURE_MAP.get(normalise_measure_name(s))))
    work["prefecture_name"] = (work[d_area].map(code_to_name[d_area]).fillna("")
                               .map(normalise_pref_name))
    work["prefecture_code"] = work["prefecture_name"].map(PREF_NAME_TO_CODE)
    work["industry_code"] = (work[d_industry].map(code_to_name[d_industry]).fillna("")
                             .map(lambda s: parse_industry(s)[0]))

    totals = work[
        work["prefecture_code"].notna()
        & (work["industry_code"] == TOTAL_INDUSTRY_CODE)
        & work["measure"].isin(measures)
    ].copy()

    totals["value"] = totals["raw_value"].map(lambda v: classify_value(v)[0])

    wide = (totals.set_index(["prefecture_code", "measure"])["value"]
            .unstack("measure")
            .rename(columns={"value_added": "value_added_total",
                             "employment": "employment_total",
                             "establishments": "establishments_total"}))
    wide["year"] = year
    return wide.reset_index()


POP_RAW = PROJECT_ROOT / "raw_data" / "population"

# Age bands as the source labels them. Matched by NAME rather than by code,
# because e-Stat's age-band codes are not ordered and not stable across tables.
AGE_BANDS = {
    "総数": "pop_total",
    "15歳未満": "pop_under15",
    "15～64歳": "pop_15_64",
    "65歳以上": "pop_65plus",
}


def load_population() -> pd.DataFrame:
    """Prefecture x year population by three age bands.

    Source: 国勢調査結果による補間補正人口 (intercensal adjusted population),
    statsDataId 0004021110, as of 1 October each year. The intercensal series is
    used in preference to the forward-projected estimates because 2016-2019 sits
    between the 2015 and 2020 censuses, so these figures are reconciled against
    both benchmarks rather than projected from one.

    Only 男女計 (both sexes) and 総人口 (total population, not 日本人人口) are kept.
    """
    pages = sorted(POP_RAW.glob("*_p*.json"))
    if not pages:
        raise SystemExit(f"no population pages in {POP_RAW}")

    df_long, code_to_name, _ = load_pages(pages)

    named = df_long.copy()
    for dim in ("cat01", "cat02", "cat03", "area", "time"):
        if dim in named.columns:
            named[f"{dim}_name"] = named[dim].map(code_to_name.get(dim, {})).fillna("")

    sel = named[
        (named["cat01_name"] == "男女計")
        & (named["cat02_name"] == "総人口")
        & (named["cat03_name"].isin(AGE_BANDS))
    ].copy()

    sel["prefecture_name"] = sel["area_name"].map(normalise_pref_name)
    sel["prefecture_code"] = sel["prefecture_name"].map(PREF_NAME_TO_CODE)
    sel = sel[sel["prefecture_code"].notna()]          # drops the 全国 row
    sel["year"] = sel["time"].astype(str).str[:4].astype(int)
    sel["band"] = sel["cat03_name"].map(AGE_BANDS)

    # The source publishes in 千人 (thousands of persons) — confirmed from the
    # @unit field on every cell, and from the national row reading 127,042.
    # Convert to persons so mfg_intensity is a dimensionless ratio against
    # manufacturing employment, which is counted in 人.
    units = set(sel["unit"].dropna()) if "unit" in sel.columns else set()
    if units and units != {"千人"}:
        raise SystemExit(f"unexpected population unit(s): {units}. Expected 千人.")
    sel["value"] = sel["raw_value"].map(lambda v: classify_value(v)[0]) * 1000.0

    wide = (sel.set_index(["year", "prefecture_code", "band"])["value"]
            .unstack("band").reset_index())
    wide["aging_ratio"] = wide["pop_65plus"] / wide["pop_total"]
    wide["working_age_share"] = wide["pop_15_64"] / wide["pop_total"]
    return wide


def load_industry_slice(year: int, table: str) -> pd.DataFrame:
    path = PROCESSED / f"manufacturing_{year}_table{table}.csv"
    if not path.exists():
        raise SystemExit(f"missing {path}. Run validate_manufacturing.py first.")
    return pd.read_csv(path, dtype={"prefecture_code": str, "industry_code": str})


def build_year(year: int, table: str) -> pd.DataFrame:
    totals = load_prefecture_totals(year, table)
    ind = load_industry_slice(year, table)

    # Shares are computed on the 24 industries so they sum to 1 by construction.
    emp = ind[["prefecture_code", "industry_code", "industry_name",
               "employment", "employment_flag", "value_added", "value_added_flag"]].copy()
    emp["employment"] = emp["employment"].fillna(0.0)

    pref_emp = emp.groupby("prefecture_code")["employment"].transform("sum")
    nat_emp_by_ind = emp.groupby("industry_code")["employment"].transform("sum")
    nat_emp = emp["employment"].sum()

    emp["share"] = emp["employment"] / pref_emp
    emp["nat_share"] = nat_emp_by_ind / nat_emp
    emp["lq"] = emp["share"] / emp["nat_share"]

    rows = []
    for pref_code, grp in emp.groupby("prefecture_code"):
        present = grp[grp["employment"] > 0]
        top = present.loc[present["employment"].idxmax()] if len(present) else None
        rows.append({
            "prefecture_code": pref_code,
            "hhi_employment": float((grp["share"] ** 2).sum()),
            "lq_max": float(grp["lq"].max()),
            "top_industry_code": None if top is None else top["industry_code"],
            "top_industry_name": None if top is None else top["industry_name"],
            "lq_top": None if top is None else float(top["lq"]),
            "n_industries_present": int(len(present)),
            "suppressed_cells": int((grp["value_added_flag"] == "suppressed").sum()),
            "value_added_industry_sum": float(grp["value_added"].sum(skipna=True)),
        })
    derived = pd.DataFrame(rows)

    out = totals.merge(derived, on="prefecture_code", how="outer")
    out["prefecture_name"] = out["prefecture_code"].map(dict(PREFECTURES))
    out["va_per_worker"] = out["value_added_total"] / out["employment_total"]
    out["va_coverage_pct"] = (out["value_added_industry_sum"]
                              / out["value_added_total"] * 100)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", nargs="+", type=int, default=DEFAULT_YEARS)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--no-population", action="store_true",
                        help="skip the population join even if the raw data is present")
    parser.add_argument("--no-2020", action="store_true",
                        help="omit reference year 2020 (2021 Economic Census)")
    args = parser.parse_args(argv)

    frames = [build_year(y, args.table) for y in args.years]
    for f in frames:
        f["instrument"] = "CoM"

    gate = None
    if not args.no_2020:
        from econ_census import load as load_ec, verify_gate

        # Gate before appending: the Economic Census ships its own 2019 figures,
        # so the two instruments can be compared on the SAME year. Anything other
        # than exact agreement means 2020 is not on the CoM basis and must not be
        # concatenated into one column.
        com_2019 = pd.concat(frames).query("year == 2019").set_index("prefecture_code")
        gate = verify_gate(com_2019)
        worst = max(v["max_abs_diff"] for v in gate.values() if isinstance(v, dict))
        if worst != 0:
            raise SystemExit(
                f"Economic Census does not reproduce the Census of Manufacture on 2019 "
                f"(max abs diff {worst}). 2020 must stay a separate cross-section.")

        ec = load_ec(2020)
        ec["instrument"] = "EconCensus"
        ec["prefecture_name"] = ec["prefecture_code"].map(dict(PREFECTURES))
        # Location quotient and HHI need prefecture x industry EMPLOYMENT, which
        # the Economic Census publishes only at prefecture level. Left null rather
        # than substituted with a value-added analogue, which is a different measure.
        for c in ["hhi_employment", "lq_max", "top_industry_code", "top_industry_name",
                  "lq_top", "n_industries_present", "suppressed_cells",
                  "va_coverage_pct", "value_added_industry_sum"]:
            ec[c] = pd.NA
        frames.append(ec)

    panel = pd.concat(frames, ignore_index=True)

    cols = ["year", "prefecture_code", "prefecture_name", "instrument",
            "value_added_total", "employment_total", "establishments_total",
            "va_per_worker", "hhi_employment", "lq_max",
            "top_industry_code", "top_industry_name", "lq_top",
            "n_industries_present", "suppressed_cells", "va_coverage_pct"]

    pop_joined = False
    if POP_RAW.exists() and any(POP_RAW.glob("*_p*.json")) and not args.no_population:
        pop = load_population()
        before = len(panel)
        panel = panel.merge(pop, on=["year", "prefecture_code"], how="left")
        assert len(panel) == before, "population join changed the row count"
        panel["mfg_intensity"] = panel["employment_total"] / panel["pop_15_64"]
        cols += ["pop_total", "pop_under15", "pop_15_64", "pop_65plus",
                 "aging_ratio", "working_age_share", "mfg_intensity"]
        pop_joined = True

    panel = panel[cols].sort_values(["year", "prefecture_code"]).reset_index(drop=True)

    # --- validation -------------------------------------------------------
    n_years = panel["year"].nunique()
    expected = 47 * n_years
    # Specialization measures exist only on the Census of Manufacture rows, so
    # those checks run on that subset rather than being weakened to allow nulls.
    com = panel[panel["instrument"] == "CoM"]
    checks = [
        (f"{expected} rows ({n_years} years x 47)", len(panel) == expected, f"got {len(panel)}"),
        ("47 prefectures per year",
         (panel.groupby("year").size() == 47).all(),
         str(panel.groupby("year").size().to_dict())),
        ("no duplicate prefecture-year",
         not panel.duplicated(["year", "prefecture_code"]).any(), ""),
        ("every row carries an instrument", panel["instrument"].notna().all(), ""),
        ("va_per_worker has no nulls", panel["va_per_worker"].notna().all(),
         f"{int(panel['va_per_worker'].isna().sum())} null"),
        ("va_per_worker strictly positive", (panel["va_per_worker"] > 0).all(), ""),
        ("hhi in (0, 1] on CoM rows",
         ((com["hhi_employment"] > 0) & (com["hhi_employment"] <= 1)).all(), ""),
        ("lq_top positive on CoM rows", (com["lq_top"] > 0).all(), ""),
        ("va_coverage <= 100.5% on CoM rows", (com["va_coverage_pct"] <= 100.5).all(),
         f"max {com['va_coverage_pct'].max():.3f}"),
        ("specialization columns null exactly on non-CoM rows",
         panel.loc[panel["instrument"] != "CoM", "hhi_employment"].isna().all()
         and com["hhi_employment"].notna().all(), ""),
    ]
    if pop_joined:
        checks += [
            ("population joined for every row", panel["pop_total"].notna().all(),
             f"{int(panel['pop_total'].isna().sum())} missing"),
            ("aging_ratio in (0.1, 0.5)",
             panel["aging_ratio"].between(0.1, 0.5).all(),
             f"range {panel['aging_ratio'].min():.3f}-{panel['aging_ratio'].max():.3f}"),
            ("age bands sum to total",
             ((panel["pop_under15"] + panel["pop_15_64"] + panel["pop_65plus"]
               - panel["pop_total"]).abs() / panel["pop_total"] < 0.005).all()
             if "pop_under15" in panel.columns else True, ""),
        ]
    failures = []
    print("validation:")
    for label, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{('  -> ' + detail) if (detail and not ok) else ''}")
        if not ok:
            failures.append(label)

    out_path = PROCESSED / "panel_prefecture_year.csv"
    panel.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\nwrote {out_path}  ({len(panel)} rows x {len(panel.columns)} cols)")

    latest = panel[panel["year"] == max(args.years)].nlargest(5, "va_per_worker")
    print(f"\ntop 5 by value added per worker, {max(args.years)} (百万円/person):")
    for _, r in latest.iterrows():
        print(f"  {r['prefecture_name']:<6} {r['va_per_worker']:6.2f}   "
              f"top industry: {r['top_industry_name']} (LQ {r['lq_top']:.2f})")

    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
lq_break_test.py — does the location quotient survive the 2016 employment break?

Background. From the 2017 survey, 従業者数 changed definition (有給役員, paid
company officers, explicitly included) and the count date moved from 31 December
to 1 June. That break splits manufacturing employment into two non-comparable
blocks. The location quotient is a ratio of shares,

    LQ(p,i) = [ emp(p,i) / emp(p,.) ] / [ emp(.,i) / emp(.,.) ]

so a definitional change that scales every cell by the same factor cancels
exactly. The cancellation is imperfect, though, because paid-officer density
varies by industry: officer-heavy industries (many small owner-managed
establishments) gain proportionally more than plant-heavy ones.

The test. Rank-correlate LQ at reference year 2014 against reference year 2016
and see how much of the cross-sectional ordering is preserved. High correlation
means the LQ ordering is stable across the break and H1 can use all eight
observations. Low correlation means LQ inherits the break and must be modelled in
two blocks, cutting H1 to four.

This tests ORDERING, not levels. It cannot tell you the break is harmless for a
regression in LQ levels — only that prefectures keep their relative positions.

Usage:
    python src/lq_break_test.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pandas as pd
from scipy import stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "processed_data"
METADATA = PROJECT_ROOT / "metadata"

# Both slices are 従業者数 for establishments with 4+ employees, so coverage is
# comparable and the only differences are the definitional ones under test.
SLICES = {
    2014: "manufacturing_2014_tablemuni3-01.csv",   # 平成26年確報 市区町村編
    2016: "manufacturing_2016_table3-01.csv",       # 平成29年確報 地域別 3-01
}


def load_employment(path: Path, year: int) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"prefecture_code": str, "industry_code": str})
    keep = df["employment_flag"] == "ok"
    out = df.loc[keep, ["prefecture_code", "prefecture_name",
                        "industry_code", "industry_name", "employment"]].copy()
    out["year"] = year
    return out


def compute_lq(df: pd.DataFrame) -> pd.DataFrame:
    """Location quotient on the panel's own totals, not the national control row.

    Using the panel's own sums keeps numerator and denominator on identical
    coverage. Mixing in the published national total would import the value of
    cells that are suppressed inside the panel and bias every share.
    """
    total = df["employment"].sum()
    pref_total = df.groupby("prefecture_code")["employment"].transform("sum")
    ind_total = df.groupby("industry_code")["employment"].transform("sum")
    out = df.copy()
    out["pref_share"] = out["employment"] / pref_total
    out["nat_share"] = ind_total / total
    out["lq"] = out["pref_share"] / out["nat_share"]
    return out


def main() -> int:
    frames = {}
    for year, fname in SLICES.items():
        path = PROCESSED / fname
        if not path.exists():
            print(f"ERROR: missing {path}. Run validate_manufacturing.py first.")
            return 2
        frames[year] = compute_lq(load_employment(path, year))

    a, b = frames[2014], frames[2016]
    merged = a.merge(b, on=["prefecture_code", "industry_code"],
                     suffixes=("_2014", "_2016"))
    merged = merged[(merged["lq_2014"] > 0) & (merged["lq_2016"] > 0)]

    report: dict = {
        "test": "LQ rank stability across the reference-year-2016 employment break",
        "years_compared": [2014, 2016],
        "sources": {str(k): v for k, v in SLICES.items()},
        "measure": "従業者数, establishments with 4+ employees",
        "pairs_available": int(len(merged)),
        "pairs_possible": 47 * 24,
    }

    rho_all, p_all = stats.spearmanr(merged["lq_2014"], merged["lq_2016"])
    report["pooled_spearman_rho"] = float(rho_all)
    report["pooled_spearman_p"] = float(p_all)

    # Per-industry: rank-correlate the 47 prefectures within each industry. This
    # is the form that matters, because LQ is compared across prefectures for a
    # given industry, not across industries.
    per_industry = []
    for ind_code, grp in merged.groupby("industry_code"):
        if len(grp) < 10:
            continue
        rho, p = stats.spearmanr(grp["lq_2014"], grp["lq_2016"])
        per_industry.append({
            "industry_code": ind_code,
            "industry_name": grp["industry_name_2016"].iloc[0],
            "n_prefectures": int(len(grp)),
            "spearman_rho": float(rho),
            "p_value": float(p),
        })
    per_industry.sort(key=lambda r: r["spearman_rho"])
    report["per_industry"] = per_industry

    rhos = pd.Series([r["spearman_rho"] for r in per_industry])
    report["per_industry_summary"] = {
        "industries_tested": int(len(rhos)),
        "median_rho": float(rhos.median()),
        "min_rho": float(rhos.min()),
        "max_rho": float(rhos.max()),
        "n_above_0.95": int((rhos > 0.95).sum()),
        "n_below_0.90": int((rhos < 0.90).sum()),
    }

    # Manufacturing employment share is the other quantity that inherits the
    # break, so report it alongside as a sanity check on magnitude.
    share = merged.groupby("prefecture_code")[["employment_2014", "employment_2016"]].sum()
    total_change = (share["employment_2016"].sum() / share["employment_2014"].sum() - 1) * 100
    report["national_employment_change_pct"] = float(total_change)

    verdict_rho = float(rhos.median())
    if verdict_rho > 0.95:
        verdict = ("LQ ordering is stable across the break. H1 can use the full "
                   "8-observation set, with the break still noted.")
    elif verdict_rho > 0.90:
        verdict = ("LQ ordering is largely but not fully stable. Usable across the "
                   "break with a block dummy; report sensitivity to dropping "
                   "pre-2016 years.")
    else:
        verdict = ("LQ inherits the break. Model the two blocks separately; H1 "
                   "effectively has 4 observations.")
    report["verdict"] = verdict

    print("LQ break test — reference year 2014 vs 2016 (従業者数, 4+ establishments)")
    print(f"  pairs compared          : {len(merged)} of {47*24}")
    print(f"  national employment Δ   : {total_change:+.2f}%")
    print(f"  pooled Spearman rho     : {rho_all:.4f}")
    print(f"  per-industry median rho : {rhos.median():.4f}")
    print(f"  per-industry min / max  : {rhos.min():.4f} / {rhos.max():.4f}")
    print(f"  industries with rho>0.95: {(rhos > 0.95).sum()} of {len(rhos)}")
    print(f"  industries with rho<0.90: {(rhos < 0.90).sum()} of {len(rhos)}")
    print("\n  five weakest industries:")
    for r in per_industry[:5]:
        print(f"    {r['spearman_rho']:.4f}  【{r['industry_code']}】{r['industry_name']}")
    print(f"\n  VERDICT: {verdict}")

    METADATA.mkdir(parents=True, exist_ok=True)
    out = METADATA / "lq_break_test.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

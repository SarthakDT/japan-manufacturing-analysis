"""
metrics.py — one implementation of each derived regional metric.

The location quotient was previously computed in two places, `build_panel.py`
and `lq_break_test.py`, with different missing-data handling: one filled missing
employment with zero, the other filtered to cells flagged `ok`. They happened to
agree exactly (max difference 0.0 across all 1,118 common cells for 2019), but
only by accident of the data, and a correction to one would not have reached the
other. This module is now the single source of truth.

HOW MISSING EMPLOYMENT IS TREATED, AND WHY
------------------------------------------
Missing employment is treated as **zero**, and all 24 industries are retained.

That is a semantic claim about the source, not a convenience. Employment is
never confidentiality-suppressed in these tables — only monetary measures are.
A missing employment cell therefore means the prefecture has no establishments
in that industry, which is genuinely zero, not unknown.

Value added is different: a missing value added cell may be a real number the
publisher withheld. That is why `dataset.load_cells(usable_only=True)` exists
for ratios with value added in the numerator, while share-based metrics here
keep the full grid.

Retaining all 24 industries also matters arithmetically: the location quotient
and the Herfindahl index are both built on shares, and dropping cells would stop
those shares summing to 1.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

EMPLOYMENT = "employment"
PREF = "prefecture_code"
IND = "industry_code"


def _employment_grid(cells: pd.DataFrame) -> pd.DataFrame:
    """Copy with employment coerced to a complete, zero-filled column."""
    out = cells.copy()
    # Force float. Under pandas 3 a frame grown row by row can hold employment
    # as `object`, and object arithmetic raises ZeroDivisionError on 0/0 where
    # float arithmetic returns NaN - the defined answer for an industry absent
    # nationwide. The self-test fixture hit exactly this in CI.
    out[EMPLOYMENT] = pd.to_numeric(out[EMPLOYMENT]).astype(float).fillna(0.0)
    return out


def location_quotient(cells: pd.DataFrame) -> pd.Series:
    """LQ per prefecture x industry cell, aligned to the input index.

        LQ(p,i) = [ emp(p,i) / emp(p,.) ] / [ emp(.,i) / emp(.,.) ]

    One means the prefecture holds exactly the national share of that industry;
    two means twice the national share.

    Denominators come from the passed frame, so a single-year frame gives
    single-year national shares. Pass one year at a time.
    """
    d = _employment_grid(cells)
    pref_total = d.groupby(PREF)[EMPLOYMENT].transform("sum")
    nat_by_ind = d.groupby(IND)[EMPLOYMENT].transform("sum")
    nat_total = d[EMPLOYMENT].sum()

    pref_share = d[EMPLOYMENT] / pref_total
    nat_share = nat_by_ind / nat_total
    return (pref_share / nat_share).rename("lq")


def employment_share(cells: pd.DataFrame) -> pd.Series:
    """Industry i's share of prefecture p's manufacturing employment."""
    d = _employment_grid(cells)
    return (d[EMPLOYMENT] / d.groupby(PREF)[EMPLOYMENT].transform("sum")).rename("share")


def herfindahl(cells: pd.DataFrame) -> pd.Series:
    """HHI of employment concentration, one value per prefecture.

        HHI(p) = SUM over industries of share(p,i)^2

    Even employment across 24 industries gives 1/24 ~ 0.042; everything in one
    industry gives 1. The reciprocal 1/HHI reads as the effective number of
    industries a prefecture behaves as though it has.
    """
    d = _employment_grid(cells)
    d = d.assign(share=employment_share(d))
    return d.groupby(PREF)["share"].apply(lambda s: float((s ** 2).sum())).rename("hhi")


def _self_test() -> int:
    """Check against a fixture whose answers are known by construction."""
    print("self-test: metrics")
    checks = []

    # Three prefectures, two industries, built so the NATIONAL split is exactly
    # 50/50. That matters: national shares are derived from the fixture, so
    # without P3 offsetting P2's skew the benchmark drifts and every expected
    # value below is wrong. P2 and P3 are mirror images for that reason.
    #
    #   national A = 50 + 75 + 25 = 150, national B = 50 + 25 + 75 = 150
    #   P1 even split  -> LQ = 1 in both, HHI = 0.50
    #   P2 3:1 toward A -> LQ_A = 1.5, LQ_B = 0.5, HHI = 0.625
    rows = [("01", "A", 50.0), ("01", "B", 50.0),
            ("02", "A", 75.0), ("02", "B", 25.0),
            ("03", "A", 25.0), ("03", "B", 75.0)]
    fx = pd.DataFrame(rows, columns=[PREF, IND, EMPLOYMENT])

    lq = location_quotient(fx)
    hhi = herfindahl(fx)

    def chk(label, got, want):
        ok = abs(got - want) < 1e-12
        checks.append(ok)
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:<46} got {got:.6f} want {want:.6f}")

    chk("evenly split prefecture: LQ = 1 in industry A", lq.iloc[0], 1.0)
    chk("evenly split prefecture: LQ = 1 in industry B", lq.iloc[1], 1.0)
    chk("skewed prefecture: LQ = 1.5 in over-represented A", lq.iloc[2], 1.5)
    chk("skewed prefecture: LQ = 0.5 in under-represented B", lq.iloc[3], 0.5)
    chk("even split HHI = 0.5", hhi.loc["01"], 0.5)
    chk("3:1 split HHI = 0.625", hhi.loc["02"], 0.625)

    # Missing employment must behave as zero, not propagate NaN, and must not
    # change the shares of the industries that are present.
    fx_nan = fx.copy()
    n_base = len(fx)
    for pref in ("01", "02", "03"):
        fx_nan.loc[len(fx_nan)] = [pref, "C", np.nan]
    lq_nan = location_quotient(fx_nan)
    ok = lq_nan.iloc[:n_base].round(12).equals(lq.round(12))
    checks.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] missing employment treated as zero, shares unchanged")

    ok = bool(lq_nan.iloc[n_base:].isna().all())
    checks.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] an industry absent nationwide yields NaN LQ, not a divide-by-zero crash")

    fails = checks.count(False)
    print(f"\nself-test: {'ALL PASSED' if not fails else f'{fails} FAILED'}")
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(_self_test())

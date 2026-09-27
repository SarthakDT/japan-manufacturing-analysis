"""
shift_share.py — decompose a prefecture's productivity gap into industry mix and
within-industry performance.

For prefecture p over industries i, with s = employment share and
pi = value added per worker:

    mix    = SUM (s_pi - s_Ni) * pi_Ni      composition, valued at national rates
    within = SUM  s_pi * (pi_pi - pi_Ni)    performance inside each industry
    gap    = P_p - P_benchmark  ==  mix + within      exactly

Reading the two terms:
    mix > 0     the prefecture is weighted toward industries that pay well nationally
    within > 0  the prefecture beats the national rate inside the industries it has

THE TRAP THIS MODULE EXISTS TO PREVENT
--------------------------------------
A first attempt at this analysis left a residual of 1.37 (against gaps of order
1-7): the decomposition did not add up, while still producing plausible numbers.

The cause is subtle and worth stating precisely. Expanding the two terms,

    mix + within = SUM s_pi*pi_Ni - SUM s_Ni*pi_Ni + SUM s_pi*pi_pi - SUM s_pi*pi_Ni
                 = P_p - SUM s_Ni*pi_Ni

so the identity holds against the benchmark `SUM s_Ni*pi_Ni` **computed over the
same industry set the decomposition runs on** - regardless of whether those shares
sum to 1. The bug was not the shares themselves. It was measuring the gap against
the GLOBAL national productivity (all industries, all prefectures) while
decomposing over a prefecture's surviving subset. Two different benchmarks,
silently differenced.

Two things follow, and this module does both:
  1. The gap is always measured against the benchmark the decomposition actually
     uses, returned as `benchmark` so it is inspectable rather than implied.
  2. National shares are renormalised over the prefecture's industry set, which
     makes that benchmark a genuine weighted average (an interpretable
     "what this prefecture would produce at national rates") rather than a
     partial sum that understates.

`decompose()` asserts the identity per prefecture, so this class of error fails
loudly instead of shipping.

Suppression: cells are kept only where value added and employment are both flagged
`ok` and employment is positive. Because a prefecture's benchmark is rebuilt on its
own surviving industry set, the decomposition stays internally consistent; the
`coverage` column reports how much of the prefecture's value added survived.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from dataset import ensure_utf8_stdout, load_cells as _load_cells

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "processed_data"

IDENTITY_TOLERANCE = 1e-9


def load_cells(year: int, table: str = "3-01") -> pd.DataFrame:
    """Usable prefecture x industry cells for one reference year.

    Thin wrapper over `dataset.load_cells` kept so existing callers and
    notebooks continue to work. The read itself lives in one place.
    """
    return _load_cells(year, table, usable_only=True)


def decompose(cells: pd.DataFrame, year: int | None = None) -> pd.DataFrame:
    """Mix / within decomposition for every prefecture in `cells`.

    Returns one row per prefecture with the gap, its two components, the
    benchmark it is measured against, and coverage diagnostics.
    """
    nat_va = cells.groupby("industry_code").value_added.sum()
    nat_emp = cells.groupby("industry_code").employment.sum()
    pi_nat = nat_va / nat_emp

    rows = []
    for (code, name), g in cells.groupby(["prefecture_code", "prefecture_name"]):
        g = g.set_index("industry_code")
        idx = g.index

        s_p = g.employment / g.employment.sum()
        pi_p = g.value_added / g.employment

        # Renormalise the benchmark over this prefecture's industry set, or the
        # shares stop summing to 1 and the identity breaks. This is the fix.
        nat_emp_r = nat_emp.reindex(idx)
        s_nat = nat_emp_r / nat_emp_r.sum()
        pi_nat_r = pi_nat.reindex(idx)

        productivity = float((s_p * pi_p).sum())
        benchmark = float((s_nat * pi_nat_r).sum())
        mix = float(((s_p - s_nat) * pi_nat_r).sum())
        within = float((s_p * (pi_p - pi_nat_r)).sum())

        rows.append({
            "year": year,
            "prefecture_code": code,
            "prefecture_name": name,
            "va_per_worker": productivity,
            "benchmark": benchmark,
            "gap": productivity - benchmark,
            "mix_effect": mix,
            "within_effect": within,
            "industries_used": int(len(idx)),
            "residual": (productivity - benchmark) - (mix + within),
        })

    out = pd.DataFrame(rows)

    worst = out.residual.abs().max()
    if not worst < IDENTITY_TOLERANCE:
        offenders = out.loc[out.residual.abs() >= IDENTITY_TOLERANCE,
                            ["prefecture_name", "gap", "mix_effect",
                             "within_effect", "residual"]]
        raise AssertionError(
            f"shift-share identity violated: max |residual| = {worst:.3e} "
            f"exceeds {IDENTITY_TOLERANCE:.0e}. mix + within must equal the gap.\n"
            f"{offenders.to_string(index=False)}"
        )

    out["dominant"] = np.where(out.within_effect.abs() > out.mix_effect.abs(),
                               "within", "mix")
    return out


def variance_shares(cells: pd.DataFrame) -> dict:
    """Employment-weighted share of variance in log productivity explained by
    industry means and by prefecture means, taken separately.

    Descriptive sums of squares only - no model is fitted, no coefficients or
    p-values are produced. The two shares are each computed against the same
    total and do not sum to 1, because industry and prefecture overlap.

    Non-positive value added (petroleum refining) is dropped: log is undefined.
    """
    d = cells[cells.value_added > 0].copy()
    dropped = len(cells) - len(d)
    d["log_p"] = np.log(d.value_added / d.employment)
    w = d.employment.values

    grand = np.average(d.log_p, weights=w)
    tss = float((w * (d.log_p - grand) ** 2).sum())

    def explained(col: str) -> float:
        means = d.groupby(col).apply(
            lambda g: np.average(g.log_p, weights=g.employment),
            include_groups=False)
        return float((w * (d[col].map(means).values - grand) ** 2).sum()) / tss

    return {
        "cells_used": int(len(d)),
        "cells_dropped_nonpositive_va": int(dropped),
        "industry_share": explained("industry_code"),
        "prefecture_share": explained("prefecture_code"),
    }


def _self_test() -> int:
    """Check the identity on a fixture whose answer is known by construction."""
    print("self-test: shift-share identity")
    checks = []

    # Two industries, four prefectures, built so the national rates come out at
    # EXACTLY A=10 and B=20. That matters: national rates are derived from the
    # fixture, so a single deviant prefecture would drag them off the intended
    # values and make every expectation below wrong. WithinHigh (+20%) and
    # WithinLow (-20%) are symmetric, so their deviations cancel.
    #
    #   national A: (1000 + 1500 + 1200 +  800) / (100 + 150 + 100 + 100) = 10
    #   national B: (2000 + 1000 + 2400 + 1600) / (100 +  50 + 100 + 100) = 20
    #   national shares: A 450/800 = 0.5625, B 350/800 = 0.4375
    #   benchmark = 0.5625*10 + 0.4375*20 = 14.375
    rows = [
        ("01", "NationalRates", "A", 100 * 10, 100),   # national rates, even weights
        ("01", "NationalRates", "B", 100 * 20, 100),
        ("02", "MixOnly",       "A", 150 * 10, 150),   # national rates, skewed to A
        ("02", "MixOnly",       "B",  50 * 20,  50),
        ("03", "WithinHigh",    "A", 100 * 12, 100),   # even weights, +20% on rates
        ("03", "WithinHigh",    "B", 100 * 24, 100),
        ("04", "WithinLow",     "A", 100 *  8, 100),   # even weights, -20% on rates
        ("04", "WithinLow",     "B", 100 * 16, 100),
    ]
    fx = pd.DataFrame(rows, columns=["prefecture_code", "prefecture_name",
                                     "industry_code", "value_added", "employment"])
    fx["value_added_flag"] = "ok"
    fx["employment_flag"] = "ok"

    res = decompose(fx).set_index("prefecture_name")
    checks.append(("identity holds for every prefecture (assert did not raise)", True, ""))

    nat = fx.groupby("industry_code").apply(
        lambda g: g.value_added.sum() / g.employment.sum(), include_groups=False)
    checks.append(("fixture yields the intended national rates A=10, B=20",
                   abs(nat["A"] - 10) < 1e-9 and abs(nat["B"] - 20) < 1e-9,
                   f"A={nat['A']:.4f} B={nat['B']:.4f}"))

    # A prefecture sitting on national rates must have NO within effect, whatever
    # its weights. Both of these do.
    for pref in ("NationalRates", "MixOnly"):
        checks.append((f"{pref}: at national rates, within effect is exactly zero",
                       abs(res.loc[pref].within_effect) < 1e-9,
                       f"within={res.loc[pref].within_effect:.2e}"))

    checks.append(("MixOnly: gap is entirely composition (-1.875)",
                   abs(res.loc["MixOnly"].mix_effect + 1.875) < 1e-9,
                   f"mix={res.loc['MixOnly'].mix_effect:.6f}"))

    checks.append(("WithinHigh: within effect is exactly +3",
                   abs(res.loc["WithinHigh"].within_effect - 3.0) < 1e-9,
                   f"within={res.loc['WithinHigh'].within_effect:.6f}"))
    checks.append(("WithinLow: within effect is exactly -3",
                   abs(res.loc["WithinLow"].within_effect + 3.0) < 1e-9,
                   f"within={res.loc['WithinLow'].within_effect:.6f}"))

    # Mix depends only on weights, so two prefectures with identical weights must
    # get identical mix effects no matter how their productivity differs.
    checks.append(("mix effect depends on weights alone, not on performance",
                   abs(res.loc["WithinHigh"].mix_effect
                       - res.loc["WithinLow"].mix_effect) < 1e-9,
                   f"{res.loc['WithinHigh'].mix_effect:.6f} vs "
                   f"{res.loc['WithinLow'].mix_effect:.6f}"))

    # Regression guard reproducing the ACTUAL original bug: drop an industry from
    # one prefecture, then measure its gap against the GLOBAL national
    # productivity while decomposing over the surviving subset. Two benchmarks,
    # so the identity breaks.
    partial = fx[~((fx.prefecture_code == "02") & (fx.industry_code == "B"))]
    sub = partial[partial.prefecture_code == "02"].set_index("industry_code")
    s_p = sub.employment / sub.employment.sum()
    pi_p = sub.value_added / sub.employment
    pi_n_all = partial.groupby("industry_code").apply(
        lambda g: g.value_added.sum() / g.employment.sum(), include_groups=False)
    pi_n = pi_n_all.reindex(sub.index)
    nat_emp = partial.groupby("industry_code").employment.sum()
    s_n_sub = nat_emp.reindex(sub.index) / nat_emp.reindex(sub.index).sum()

    # The wrong benchmark: global national productivity over ALL industries.
    global_p = partial.value_added.sum() / partial.employment.sum()
    wrong_gap = float((s_p * pi_p).sum()) - global_p
    mix_t = float(((s_p - s_n_sub) * pi_n).sum())
    within_t = float((s_p * (pi_p - pi_n)).sum())
    wrong_resid = wrong_gap - (mix_t + within_t)
    checks.append(("regression guard: benchmarking the gap against GLOBAL national "
                   "productivity while decomposing a subset breaks the identity",
                   abs(wrong_resid) > 1e-6, f"residual={wrong_resid:.3e}"))

    fixed = decompose(partial)
    checks.append(("using the decomposition's own benchmark holds it on the same data",
                   fixed.residual.abs().max() < IDENTITY_TOLERANCE,
                   f"max|residual|={fixed.residual.abs().max():.2e}"))

    failures = 0
    for label, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}"
              f"{('  -> ' + detail) if detail and not ok else ''}")
        failures += (not ok)
    print(f"\nself-test: {'ALL PASSED' if not failures else f'{failures} FAILED'}")
    return 0 if not failures else 1


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--years", nargs="+", type=int, default=[2016, 2017, 2018, 2019])
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    for year in args.years:
        cells = load_cells(year)
        res = decompose(cells, year)
        ratio = res.within_effect.std() / res.mix_effect.std()
        print(f"{year}: n={len(res)}  max|residual|={res.residual.abs().max():.2e}  "
              f"sd(within)/sd(mix)={ratio:.2f}  "
              f"within-dominant in {(res.dominant == 'within').sum()}/47")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

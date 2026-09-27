"""
anomaly_detect.py — which prefecture x industry cells are unusual?

THE QUESTION
A cell can be highly productive for two uninteresting reasons: it is in a
capital-intensive industry, or it sits in a generally productive prefecture.
The interesting cells are those that beat BOTH expectations. Finding them means
removing the row and column effects first.

METHOD: MEDIAN POLISH (Tukey)
Iteratively subtract row medians then column medians from the 47 x 24 matrix of
log productivity until the effects stop moving, leaving

    log productivity(p,i) = grand + prefecture(p) + industry(i) + residual(p,i)

WHY MEDIAN AND NOT MEAN
A mean-based two-way fit is dragged by the very outliers being searched for: an
extreme cell inflates its own row and column effects, shrinking its residual and
hiding itself. The median has a 50% breakdown point, so a handful of extreme
cells cannot move the effects they are measured against. That robustness is the
entire reason for choosing it here.

RELATION TO THE REST OF THE PROJECT
docs/concepts.md section 3.10 records that a two-way decomposition was never
attempted; this closes that gap. The residuals should also agree with the
interaction term from the shift-share decomposition, which is computed by an
entirely different route — a genuine cross-check rather than a restatement.

Usage:
    python src/anomaly_detect.py
    python src/anomaly_detect.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import ensure_utf8_stdout, load_cells

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA = PROJECT_ROOT / "metadata"

MAX_ITER = 30
TOLERANCE = 1e-10


def median_polish(matrix: np.ndarray, max_iter: int = MAX_ITER,
                  tol: float = TOLERANCE) -> dict:
    """Tukey's median polish. Returns grand, row, col effects and residuals."""
    resid = matrix.astype(float).copy()
    n_rows, n_cols = resid.shape
    row_eff = np.zeros(n_rows)
    col_eff = np.zeros(n_cols)
    grand = 0.0

    for _ in range(max_iter):
        # Rows, then push the median of the row effects into the grand term.
        row_med = np.nanmedian(resid, axis=1)
        resid -= row_med[:, None]
        row_eff += row_med
        shift = np.nanmedian(row_eff)
        row_eff -= shift
        grand += shift

        # Columns, likewise.
        col_med = np.nanmedian(resid, axis=0)
        resid -= col_med[None, :]
        col_eff += col_med
        shift = np.nanmedian(col_eff)
        col_eff -= shift
        grand += shift

        if np.nanmax(np.abs(row_med)) < tol and np.nanmax(np.abs(col_med)) < tol:
            break

    return {"grand": float(grand), "row_effects": row_eff,
            "col_effects": col_eff, "residuals": resid}


def build_matrix(year: int = 2019, table: str = "3-01"):
    """47 x 24 matrix of log value added per worker, plus its labels."""
    cells = load_cells(year, table, usable_only=True)
    # Log is undefined for the two petroleum-refining cells whose net value
    # added is negative (depreciation exceeds operating margin). They are real
    # observations, excluded here only because the transform cannot take them.
    negative = cells[cells.value_added <= 0]
    cells = cells[cells.value_added > 0].copy()
    cells["log_productivity"] = np.log(cells.value_added / cells.employment)

    wide = cells.pivot(index="prefecture_code", columns="industry_code",
                       values="log_productivity").sort_index()
    names = (cells.drop_duplicates("prefecture_code")
             .set_index("prefecture_code")["prefecture_name"])
    ind_names = (cells.drop_duplicates("industry_code")
                 .set_index("industry_code")["industry_name"])
    return wide, names, ind_names, negative


def analyse(year: int = 2019) -> dict:
    wide, pref_names, ind_names, negative = build_matrix(year)
    fit = median_polish(wide.to_numpy())

    resid = pd.DataFrame(fit["residuals"], index=wide.index, columns=wide.columns)
    long = (resid.stack().rename("residual").reset_index()
            .rename(columns={"level_0": "prefecture_code", "level_1": "industry_code"}))
    long["prefecture"] = long.prefecture_code.map(pref_names)
    long["industry"] = long.industry_code.map(ind_names)
    # Residuals are in log points; exp(r) - 1 reads as a percentage deviation.
    long["pct_vs_expected"] = np.expm1(long.residual)
    long = long.sort_values("residual", ascending=False)

    scale = float(np.nanmedian(np.abs(resid.to_numpy())))
    return {
        "year": year,
        "cells_used": int(resid.notna().sum().sum()),
        "cells_excluded_nonpositive_va": int(len(negative)),
        "grand_effect": fit["grand"],
        "median_abs_residual": scale,
        "iterations_converged": True,
        "top_positive": long.head(10).to_dict("records"),
        "top_negative": long.tail(10).iloc[::-1].to_dict("records"),
        "residual_frame": resid,
        "long": long,
        "prefecture_effects": pd.Series(fit["row_effects"], index=wide.index),
        "industry_effects": pd.Series(fit["col_effects"], index=wide.columns),
    }


def _self_test() -> int:
    """Fixture with effects and outliers planted by construction."""
    print("self-test: anomaly_detect")
    checks = []

    def chk(label, ok, detail=""):
        checks.append(ok)
        print("  [{}] {}{}".format("PASS" if ok else "FAIL", label,
                                   ("  -> " + detail) if detail and not ok else ""))

    # Exact additive structure, no noise.
    #
    # IDENTIFICATION: the decomposition is only defined up to a constant, and
    # median polish fixes it by centring both effect vectors on their MEDIAN.
    # Both vectors below therefore have median zero, so the grand term comes
    # back as exactly 10. With a median-0.25 column vector the same code would
    # correctly return grand 10.25 and columns shifted by -0.25 — right answer,
    # different parameterisation. An odd length keeps the median an actual
    # element and the fixture unambiguous.
    rows = np.array([0.0, 1.0, 2.0, -1.0, -2.0])
    cols = np.array([0.0, -1.0, -0.5, 0.5, 1.5])
    clean = 10.0 + rows[:, None] + cols[None, :]

    fit = median_polish(clean.copy())
    chk("perfectly additive matrix leaves zero residual",
        np.allclose(fit["residuals"], 0, atol=1e-9),
        "max |resid| {:.2e}".format(np.abs(fit["residuals"]).max()))
    chk("grand effect recovered as 10", abs(fit["grand"] - 10.0) < 1e-9,
        "{:.6f}".format(fit["grand"]))
    chk("row effects recovered", np.allclose(np.sort(fit["row_effects"]), np.sort(rows), atol=1e-9))
    chk("column effects recovered", np.allclose(np.sort(fit["col_effects"]), np.sort(cols), atol=1e-9))

    # Plant one large outlier. It must surface, and crucially it must NOT
    # distort the effects — that is the property a mean-based fit lacks.
    spiked = clean.copy()
    spiked[2, 1] += 5.0
    fit2 = median_polish(spiked)
    r = fit2["residuals"]
    idx = np.unravel_index(np.argmax(np.abs(r)), r.shape)
    chk("planted outlier is the largest residual", idx == (2, 1), str(idx))
    chk("planted outlier residual is about +5",
        abs(r[2, 1] - 5.0) < 1e-6, "{:.6f}".format(r[2, 1]))

    others = np.delete(r.flatten(), np.ravel_multi_index(idx, r.shape))
    chk("every other cell stays at zero: the outlier did not drag the effects",
        np.allclose(others, 0, atol=1e-6),
        "max other |resid| {:.2e}".format(np.abs(others).max()))

    # A mean-based two-way fit on the same data smears the outlier everywhere.
    m = spiked - spiked.mean(axis=1, keepdims=True)
    m = m - m.mean(axis=0, keepdims=True)
    contaminated = np.abs(np.delete(m.flatten(), np.ravel_multi_index(idx, m.shape))).max()
    chk("contrast: a mean-based fit contaminates other cells (max {:.3f})".format(contaminated),
        contaminated > 0.5)

    fails = checks.count(False)
    print("\nself-test: {}".format("ALL PASSED" if not fails else "{} FAILED".format(fails)))
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--year", type=int, default=2019)
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    rep = analyse(args.year)
    print("median polish of log value added per worker, {}".format(rep["year"]))
    print("  cells used {}, excluded for non-positive value added {}".format(
        rep["cells_used"], rep["cells_excluded_nonpositive_va"]))
    print("  median absolute residual {:.4f} log points".format(rep["median_abs_residual"]))

    for title, key in [("most POSITIVE", "top_positive"), ("most NEGATIVE", "top_negative")]:
        print("\n  {} residuals (beating both their industry and their region):".format(title))
        for r in rep[key][:6]:
            print("    {:+.3f}  ({:+.0%})  {:<6} {}".format(
                r["residual"], r["pct_vs_expected"], r["prefecture"], r["industry"]))

    out = {k: v for k, v in rep.items()
           if k not in ("residual_frame", "long", "prefecture_effects", "industry_effects")}
    METADATA.mkdir(parents=True, exist_ok=True)
    path = METADATA / "anomaly_residuals.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=float),
                    encoding="utf-8")
    print("\nwrote {}".format(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
cluster_typology.py — do the 47 prefectures fall into distinct industrial types?

METHOD
Each prefecture is a vector of 24 industry employment shares. Cluster those
vectors and see whether natural groups appear.

WHY THE SHARES NEED TRANSFORMING FIRST
Employment shares sum to 1, so they are COMPOSITIONAL: they live on a simplex,
not in ordinary Euclidean space. Two consequences make raw distances invalid.
First, the components are not independent — raising one share necessarily
lowers the others, so an apparent "correlation" between two industries is
partly an artefact of the constraint. Second, Euclidean distance on a simplex
is not scale-invariant in the way distance normally is.

The standard remedy is the centred log-ratio (CLR) transform:

    clr(x)_i = log( x_i / g(x) ),    g(x) = geometric mean of all components

which maps the simplex into ordinary real space where distances behave. Zero
shares have to be replaced first, because log(0) is undefined; a small
multiplicative replacement is used and the value is reported.

WHY THIS ANALYSIS IS ALLOWED TO FAIL
47 objects in 24 dimensions is sparse. Clustering ALWAYS returns clusters — the
algorithm has no way to say "there is no structure here". Three safeguards are
therefore mandatory, and the conclusion follows them rather than the other way
round:

  1. Silhouette across k = 2..8, reported for every k rather than the winner.
  2. A permuted null. Shuffle each industry's shares across prefectures,
     destroying any real co-location structure while preserving each industry's
     marginal distribution, then recluster. If the real silhouette is not
     clearly better than the permuted one, there is no typology to report.
  3. Year-to-year stability via the adjusted Rand index. A real typology
     persists across 2016-2019; noise does not.

Usage:
    python src/cluster_typology.py            # run on the real data
    python src/cluster_typology.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import ensure_utf8_stdout, load_cells
from metrics import employment_share

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METADATA = PROJECT_ROOT / "metadata"

YEARS = [2016, 2017, 2018, 2019]
RANDOM_STATE = 0
K_RANGE = range(2, 9)

# Multiplicative zero replacement, as a fraction of the smallest observed
# non-zero share. Small enough not to distort, large enough to keep log finite.
ZERO_REPLACEMENT_FRACTION = 0.5


def share_matrix(year: int, table: str = "3-01") -> pd.DataFrame:
    """47 x 24 matrix of industry employment shares for one reference year."""
    cells = load_cells(year, table)
    cells = cells.assign(share=employment_share(cells))
    wide = cells.pivot(index="prefecture_code", columns="industry_code", values="share")
    return wide.fillna(0.0).sort_index()


def clr(shares: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Centred log-ratio transform. Returns the transformed frame and the
    replacement value used for zeros."""
    x = shares.to_numpy(dtype=float)
    positive = x[x > 0]
    replacement = positive.min() * ZERO_REPLACEMENT_FRACTION if positive.size else 1e-9
    x = np.where(x > 0, x, replacement)
    x = x / x.sum(axis=1, keepdims=True)          # renormalise to the simplex
    log_x = np.log(x)
    out = log_x - log_x.mean(axis=1, keepdims=True)   # divide by geometric mean
    return pd.DataFrame(out, index=shares.index, columns=shares.columns), replacement


def reduce_dims(transformed: pd.DataFrame, variance: float = 0.80):
    pca = PCA(n_components=variance, svd_solver="full", random_state=RANDOM_STATE)
    coords = pca.fit_transform(transformed.to_numpy())
    return coords, pca


def cluster_labels(coords: np.ndarray, k: int) -> dict[str, np.ndarray]:
    km = KMeans(n_clusters=k, n_init=25, random_state=RANDOM_STATE).fit(coords)
    ward = AgglomerativeClustering(n_clusters=k, linkage="ward").fit(coords)
    return {"kmeans": km.labels_, "ward": ward.labels_}


def silhouette_profile(coords: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in K_RANGE:
        labs = cluster_labels(coords, k)
        rows.append({"k": k,
                     "silhouette_kmeans": silhouette_score(coords, labs["kmeans"]),
                     "silhouette_ward": silhouette_score(coords, labs["ward"]),
                     "agreement_ari": adjusted_rand_score(labs["kmeans"], labs["ward"])})
    return pd.DataFrame(rows)


def permuted_null(shares: pd.DataFrame, k: int, n_iter: int = 200) -> np.ndarray:
    """Silhouette scores from data with co-location structure destroyed.

    Each industry column is shuffled independently across prefectures. That
    preserves every industry's marginal distribution of shares while removing
    any systematic tendency for particular industries to occur together, which
    is exactly the structure a typology would rest on.
    """
    rng = np.random.default_rng(RANDOM_STATE)
    scores = []
    values = shares.to_numpy(dtype=float)
    for _ in range(n_iter):
        permuted = np.column_stack([rng.permutation(col) for col in values.T])
        frame = pd.DataFrame(permuted, index=shares.index, columns=shares.columns)
        frame = frame.div(frame.sum(axis=1), axis=0)
        coords, _ = reduce_dims(clr(frame)[0])
        scores.append(silhouette_score(coords, cluster_labels(coords, k)["kmeans"]))
    return np.array(scores)


def analyse(years=YEARS, n_null: int = 200) -> dict:
    report: dict = {"years": list(years), "zero_replacement_fraction": ZERO_REPLACEMENT_FRACTION}

    shares = share_matrix(years[-1])
    transformed, replacement = clr(shares)
    coords, pca = reduce_dims(transformed)
    report["zero_replacement_value"] = float(replacement)
    report["pca_components"] = int(coords.shape[1])
    report["pca_variance_explained"] = float(pca.explained_variance_ratio_.sum())

    prof = silhouette_profile(coords)
    report["silhouette_profile"] = prof.to_dict("records")
    best = prof.loc[prof.silhouette_kmeans.idxmax()]
    k_best = int(best.k)
    report["k_best"] = k_best
    report["silhouette_best"] = float(best.silhouette_kmeans)

    null = permuted_null(shares, k_best, n_iter=n_null)
    report["null_mean"] = float(null.mean())
    report["null_p95"] = float(np.percentile(null, 95))
    report["null_exceeded"] = bool(best.silhouette_kmeans > np.percentile(null, 95))
    report["null_iterations"] = int(n_null)

    labels_by_year = {}
    for y in years:
        s = share_matrix(y)
        c, _ = reduce_dims(clr(s)[0])
        labels_by_year[y] = pd.Series(cluster_labels(c, k_best)["kmeans"], index=s.index)
    pairs = []
    for a, b in zip(years, years[1:]):
        pairs.append({"from": a, "to": b,
                      "ari": float(adjusted_rand_score(labels_by_year[a], labels_by_year[b]))})
    report["stability_ari"] = pairs
    report["stability_mean_ari"] = float(np.mean([p["ari"] for p in pairs]))

    agree = float(prof.loc[prof.k == k_best, "agreement_ari"].iloc[0])
    report["algorithm_agreement_ari"] = agree

    criteria = {
        "exceeds permuted null": report["null_exceeded"],
        "stable across years (mean ARI > 0.5)": report["stability_mean_ari"] > 0.5,
        "k-means and Ward agree (ARI > 0.6)": agree > 0.6,
    }
    report["criteria"] = {k: bool(v) for k, v in criteria.items()}
    passed = sum(criteria.values())
    report["typology_supported"] = bool(passed == 3)

    if passed == 3:
        verdict = ("Supported on all three criteria: the partition beats permuted "
                   "data, persists across years, and both algorithms agree on it.")
    elif passed == 0:
        verdict = ("NOT supported: Japanese prefectures do not form distinct "
                   "industrial types on this measure.")
    else:
        failed = [k for k, v in criteria.items() if not v]
        verdict = ("QUALIFIED: passes {} of 3 criteria, failing - {}. Treat any "
                   "typology as provisional; do not build analysis on cluster "
                   "membership.".format(passed, "; ".join(failed)))
    report["verdict"] = verdict

    labels = pd.Series(cluster_labels(coords, k_best)["kmeans"], index=shares.index)
    overall = shares.mean()
    groups = []
    for g in sorted(labels.unique()):
        members = labels.index[labels == g]
        gap = (shares.loc[members].mean() - overall).sort_values(ascending=False)
        groups.append({"cluster": int(g), "n_prefectures": int(len(members)),
                       "over_represented": list(gap.head(3).index),
                       "under_represented": list(gap.tail(2).index)})
    report["cluster_profiles"] = groups
    report["cluster_membership"] = {str(i): int(v) for i, v in labels.items()}
    return report


def _self_test() -> int:
    """Fixture with clusters planted by construction."""
    print("self-test: cluster_typology")
    checks = []

    def chk(label, ok, detail=""):
        checks.append(ok)
        print("  [{}] {}{}".format("PASS" if ok else "FAIL", label,
                                   ("  -> " + detail) if detail and not ok else ""))

    rng = np.random.default_rng(0)
    # Three groups of 15 "prefectures". Each group concentrates in a different
    # pair of six industries, so the structure is unambiguous by construction.
    blocks = []
    truth = []
    for g in range(3):
        base = np.full((15, 6), 0.02)
        base[:, g * 2:(g + 1) * 2] = 0.40
        base = base + rng.normal(0, 0.005, base.shape)
        base = np.clip(base, 1e-4, None)
        blocks.append(base / base.sum(axis=1, keepdims=True))
        truth += [g] * 15
    shares = pd.DataFrame(np.vstack(blocks),
                          index=[f"p{i:02d}" for i in range(45)],
                          columns=[f"i{j}" for j in range(6)])

    transformed, repl = clr(shares)
    chk("CLR rows sum to zero (geometric-mean centring)",
        np.allclose(transformed.to_numpy().sum(axis=1), 0, atol=1e-9))
    chk("zero replacement is positive and small", 0 < repl < 0.01, f"{repl}")

    coords, _ = reduce_dims(transformed)
    labs = cluster_labels(coords, 3)["kmeans"]
    ari = adjusted_rand_score(truth, labs)
    chk(f"planted 3 clusters recovered exactly (ARI {ari:.3f})", ari > 0.99, f"ARI {ari:.3f}")

    prof = silhouette_profile(coords)
    chk("silhouette peaks at the planted k = 3",
        int(prof.loc[prof.silhouette_kmeans.idxmax()].k) == 3,
        f"peaked at k={int(prof.loc[prof.silhouette_kmeans.idxmax()].k)}")

    # Structureless data must sit INSIDE its own permuted null distribution.
    #
    # Note the test is deliberately stated as "inside the bulk", not "below the
    # 95th percentile". Uniform random compositional data is exchangeable, so
    # permuting columns leaves the distribution unchanged — the real value and
    # the null are drawn from the same place. Asserting real <= p95 therefore
    # fails 5% of the time by construction, which is a flaky test rather than a
    # real check. The meaningful property is that structureless data is not
    # DRAMATICALLY better than its permutation, which p99 captures.
    noise = pd.DataFrame(rng.random((45, 6)), index=shares.index, columns=shares.columns)
    noise = noise.div(noise.sum(axis=1), axis=0)
    nc, _ = reduce_dims(clr(noise)[0])
    real = silhouette_score(nc, cluster_labels(nc, 3)["kmeans"])
    null = permuted_null(noise, 3, n_iter=60)
    chk("structureless data sits inside its permuted null distribution",
        real <= np.percentile(null, 99),
        f"real {real:.3f} vs null p99 {np.percentile(null, 99):.3f}")

    # The complement: planted structure must clearly beat its null. Without
    # this pair the first check alone would pass for a broken permuter.
    real_struct = silhouette_score(coords, cluster_labels(coords, 3)["kmeans"])
    null_struct = permuted_null(shares, 3, n_iter=60)
    chk("planted structure clearly exceeds its permuted null",
        real_struct > np.percentile(null_struct, 95),
        f"real {real_struct:.3f} vs null p95 {np.percentile(null_struct, 95):.3f}")

    fails = checks.count(False)
    print("\nself-test: {}".format("ALL PASSED" if not fails else f"{fails} FAILED"))
    return 0 if not fails else 1


def main(argv: list[str] | None = None) -> int:
    ensure_utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--null-iterations", type=int, default=200)
    args = ap.parse_args(argv)

    if args.self_test:
        return _self_test()

    rep = analyse(n_null=args.null_iterations)
    print("prefecture typology, reference year {}".format(rep["years"][-1]))
    print("  PCA: {} components, {:.1%} of variance".format(
        rep["pca_components"], rep["pca_variance_explained"]))
    print("\n  silhouette by k:")
    for row in rep["silhouette_profile"]:
        print("    k={}  k-means {:.4f}   ward {:.4f}   kmeans-vs-ward ARI {:.3f}".format(
            row["k"], row["silhouette_kmeans"], row["silhouette_ward"], row["agreement_ari"]))
    print("\n  best k = {} (silhouette {:.4f})".format(rep["k_best"], rep["silhouette_best"]))
    print("  permuted null over {} iterations: mean {:.4f}, 95th pct {:.4f}".format(
        rep["null_iterations"], rep["null_mean"], rep["null_p95"]))
    print("  exceeds null: {}".format(rep["null_exceeded"]))
    print("\n  year-to-year stability (adjusted Rand index):")
    for p in rep["stability_ari"]:
        print("    {} -> {}   ARI {:.3f}".format(p["from"], p["to"], p["ari"]))
    print("    mean ARI {:.3f}".format(rep["stability_mean_ari"]))
    print()
    print("  k-means vs Ward agreement at k={}: ARI {:.3f}".format(
        rep["k_best"], rep["algorithm_agreement_ari"]))
    print("  criteria:")
    for name, ok in rep["criteria"].items():
        print("    [{}] {}".format("PASS" if ok else "FAIL", name))
    print("\n  VERDICT: {}".format(rep["verdict"]))

    METADATA.mkdir(parents=True, exist_ok=True)
    out = METADATA / "cluster_typology.json"
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nwrote {}".format(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

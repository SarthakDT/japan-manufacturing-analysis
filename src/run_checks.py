"""
run_checks.py — every check that can run from a fresh clone, in one command.

The raw e-Stat pages are gitignored, so a clone holds the validated CSVs and the
panel but cannot rebuild them. Everything downstream of those files can and
must run, and this script runs it. It is the same command a person runs locally
and GitHub Actions runs on every push (.github/workflows/checks.yml).

WHAT IT DOES NOT DO
It does not refresh data. The Census of Manufacture was abolished and the panel
ends at reference year 2020, so there is nothing to refresh. What can recur
honestly is verification: that the code, the committed data and the committed
dashboard extract still agree with one another.

Steps are run as subprocesses so each one's own exit code is what counts, and a
crash in one cannot be mistaken for a pass by another.

Usage:
    python src/run_checks.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from dataset import ensure_utf8_stdout

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def steps(tmp: Path) -> list[tuple[str, list[str] | None]]:
    """(label, script arguments). None means an in-process check, run below."""
    return [
        ("self-test: parser and validation (synthetic fixture)",
         ["src/validate_manufacturing.py", "--self-test", "--tmp-dir", str(tmp / "fixture")]),
        ("self-test: location quotient and Herfindahl", ["src/metrics.py"]),
        ("self-test: shift-share identity", ["src/shift_share.py", "--self-test"]),
        ("self-test: median polish", ["src/anomaly_detect.py", "--self-test"]),
        ("self-test: clustering pipeline", ["src/cluster_typology.py", "--self-test"]),
        ("shift-share identity on the real data, 2016-2019", ["src/shift_share.py"]),
        ("warehouse: rebuild from the committed CSVs and run load checks",
         ["src/build_warehouse.py", "--rebuild", "--check"]),
        ("warehouse: the two SQL questions execute", ["src/build_warehouse.py", "--questions"]),
        ("dashboard extract: build and run its checks",
         ["src/build_dashboard_data.py", "--check-only"]),
        ("dashboard extract: committed CSVs match a fresh build", None),
        ("streamlit app: every page renders, numbers match expected_values.md",
         ["app/check_app.py"]),
    ]


def check_extract_is_current() -> int:
    """Rebuild the extract in memory and compare it to what is committed.

    Catches the case where analysis code changed but nobody re-ran
    build_dashboard_data.py, so both dashboards would silently show old numbers.
    """
    from build_dashboard_data import OUT_DIR, build_all

    tables, _ = build_all()
    failures = 0
    with tempfile.TemporaryDirectory() as d:
        for name, fresh in tables.items():
            committed_path = OUT_DIR / f"{name}.csv"
            if not committed_path.exists():
                print(f"  [FAIL] {name}.csv is not committed")
                failures += 1
                continue
            # Round-trip the fresh table through CSV so both sides are parsed
            # identically; the comparison is then about content, not dtypes.
            fresh_path = Path(d) / f"{name}.csv"
            fresh.to_csv(fresh_path, index=False, encoding="utf-8-sig")
            read = lambda p: pd.read_csv(p, dtype=str, encoding="utf-8-sig")  # noqa: E731
            same = read(fresh_path).equals(read(committed_path))
            print(f"  [{'PASS' if same else 'FAIL'}] {name}.csv is current"
                  + ("" if same else "  -> re-run python src/build_dashboard_data.py"))
            failures += (not same)
    return 1 if failures else 0


def main() -> int:
    ensure_utf8_stdout()
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for label, args in steps(Path(tmp)):
            print("=" * 78)
            print(label)
            print("=" * 78, flush=True)
            t0 = time.time()
            if args is None:
                code = check_extract_is_current()
            else:
                code = subprocess.run([PY, *args], cwd=ROOT,
                                      env={**os.environ, "PYTHONIOENCODING": "utf-8"}
                                      ).returncode
            results.append((label, code, time.time() - t0))
            print()

    print("=" * 78)
    print("summary")
    print("=" * 78)
    for label, code, secs in results:
        print(f"  [{'PASS' if code == 0 else 'FAIL'}] {label}  ({secs:.1f}s)")
    failed = sum(code != 0 for _, code, _ in results)
    print(f"\n{len(results) - failed} of {len(results)} steps passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

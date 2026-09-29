"""
check_app.py — run every page of the Streamlit app headlessly and check its numbers.

Uses streamlit.testing.v1.AppTest, which executes the real script without a
browser or a server. Two kinds of check:

  1. Every page, in every reference year, renders without raising.
  2. The numbers a user would read match dashboard/expected_values.md — the same
     checklist the Power BI build is verified against, so the two front-ends
     are held to one set of figures. The expected values are parsed from that
     file rather than restated here, so there is one copy of them.

Run by src/run_checks.py; also runnable alone from the repository root:
    python app/check_app.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
ENTRY = str(ROOT / "app" / "streamlit_app.py")
EXPECTED = ROOT / "dashboard" / "expected_values.md"
PAGES = ["views/overview.py", "views/benchmark.py", "views/diagnosis.py",
         "views/industry.py", "views/notes.py"]
YEARS = [2016, 2017, 2018, 2019, 2020]
TIMEOUT = 60


def expected_values() -> dict:
    """Pull the 2019 figures the checks need out of expected_values.md."""
    text = EXPECTED.read_text(encoding="utf-8")
    nat = re.search(r"^\| 2019 \| ([\d.]+) \|$", text, re.M).group(1)
    row = re.search(r"^\| Aichi \| (.+) \|$", text, re.M).group(1).split(" | ")
    counts = dict(re.findall(r"^\| ((?:Strong|Weak) mix, \w+ performance) \| (\d+) \|$",
                             text, re.M))
    return {"national": nat, "va_per_worker": row[0], "rank": row[1], "share": row[2],
            "mix": row[4], "within": row[5], "suppression": row[6], "diagnosis": row[7],
            "counts": {k: int(v) for k, v in counts.items()}}


def run_page(page: str, year: int) -> AppTest:
    at = AppTest.from_file(ENTRY, default_timeout=TIMEOUT)
    at.run()
    at.sidebar.selectbox[0].set_value(year).run()
    at.switch_page(page).run()
    return at


def main() -> int:
    failures = 0

    def report(label, ok, detail=""):
        nonlocal failures
        print("  [{}] {}{}".format("PASS" if ok else "FAIL", label,
                                   ("  -> " + detail) if detail and not ok else ""))
        failures += (not ok)

    print("streamlit app checks:")
    exp = expected_values()

    for page in PAGES:
        for year in YEARS:
            at = run_page(page, year)
            errors = [e.value for e in at.exception]
            report(f"{page} renders for {year} without an exception",
                   not errors, str(errors)[:300])

    at = run_page("views/overview.py", 2019)
    national = {m.label: m.value for m in at.metric}.get("VA per worker, national")
    report(f"Overview 2019: national VA per worker is {exp['national']} "
           "(ratio of sums, not a mean of ratios)",
           national == exp["national"], f"got {national}")

    at = run_page("views/benchmark.py", 2019)
    m = {x.label: x.value for x in at.metric}
    for label, want in [("VA per worker", exp["va_per_worker"]),
                        ("Rank", f"{exp['rank']} of 47"),
                        ("Share of national value added", exp["share"]),
                        ("Diagnosis", exp["diagnosis"]),
                        ("Industry mix", exp["mix"]),
                        ("Within-industry performance", exp["within"]),
                        ("Suppression adjustment", exp["suppression"])]:
        report(f"Benchmark, Aichi 2019: {label} = {want}", m.get(label) == want,
               f"got {m.get(label)}")

    # The waterfall's total bar must equal the KPI card: the steps must close.
    charts = [json.loads(c.proto.spec) for c in at.get("plotly_chart")]
    wf = next((c for c in charts if c["data"][0].get("type") == "waterfall"), None)
    if wf is None:
        report("Benchmark: waterfall chart is rendered", False, "not found")
    else:
        steps = wf["data"][0]["y"][:-1]
        closes = abs(sum(steps) - float(exp["va_per_worker"])) < 0.005
        report(f"Benchmark: waterfall steps close to the KPI card ({exp['va_per_worker']})",
               closes, f"sum {sum(steps):.4f}")

    at = run_page("views/diagnosis.py", 2019)
    rows = at.dataframe[0].value
    got = dict(zip(rows["Diagnosis"], rows["Prefectures"]))
    report("Diagnosis 2019: quadrant counts match expected_values.md",
           got == exp["counts"], f"got {got}")

    print("\nstreamlit app checks: {}".format(
        "ALL PASSED" if not failures else f"{failures} FAILED"))
    return 0 if not failures else 1


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    raise SystemExit(main())

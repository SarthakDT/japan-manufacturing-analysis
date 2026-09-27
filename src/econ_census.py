"""
econ_census.py — reference year 2020 from the 2021 Economic Census.

The Census of Manufacture was abolished after reference year 2019. Its successor,
the Economic Structure Survey, publishes manufacturing results **nationally only**
— its tables have no area dimension at all — so 2021 onward cannot be analysed by
prefecture at any granularity. Reference year 2020 is different: it comes from the
2021 Economic Census (令和3年経済センサス-活動調査), a complete enumeration that
does publish by prefecture.

WHY 2020 IS SAFE TO APPEND
--------------------------
The Economic Census tables carry the prior year (2019) alongside 2020 as a
comparison. Those 2019 figures are **exactly identical** to the Census of
Manufacture's own 2019 figures — max absolute difference of 0 across all 47
prefectures on both employment and value added. The Economic Census reproduces the
CoM basis rather than restating it, so 2020 sits on the same measurement basis as
2016-2019. `verify_gate()` re-runs that check.

WHAT 2020 CANNOT SUPPLY
-----------------------
The Economic Census publishes prefecture × industry **establishments, shipments and
value added**, but employment only at **prefecture level**. The location quotient and
the Herfindahl index are both built on prefecture × industry *employment*, so
neither can be computed for 2020. Those columns stay null rather than being silently
substituted with a value-added-based analogue, which would be a different measure.

TABLE STRUCTURE
---------------
Unlike the Census of Manufacture tables, these flatten time, area and industry into
a single dimension whose member names encode the parts, e.g.

    2019000000_2019_01_北海道

so parsing splits on "_" rather than reading separate dimensions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW = PROJECT_ROOT / "raw_data" / "econ_census_2020"

# statsDataId per measure, 2021 Economic Census, manufacturing, 4+ employees.
TABLES = {
    "employment_total": ("EC-emp", "従業者数"),
    "value_added_total": ("EC-va", "付加価値額"),
    "establishments_total": ("EC-estab", "事業所数"),
}


def _load_measure(tag: str, measure_prefix: str) -> pd.DataFrame:
    """Parse one Economic Census table into year × prefecture rows."""
    pages = sorted(RAW.glob(f"table{tag}_*_p*.json"))
    if not pages:
        raise SystemExit(f"no Economic Census pages for {tag} in {RAW}")

    rows = []
    for page in pages:
        stat = json.loads(page.read_text(encoding="utf-8"))["GET_STATS_DATA"]["STATISTICAL_DATA"]
        maps = {}
        objs = stat["CLASS_INF"]["CLASS_OBJ"]
        objs = objs if isinstance(objs, list) else [objs]
        for obj in objs:
            members = obj.get("CLASS")
            members = members if isinstance(members, list) else [members]
            maps[obj["@id"]] = {m["@code"]: m["@name"] for m in members}

        values = stat["DATA_INF"]["VALUE"]
        values = values if isinstance(values, list) else [values]
        for v in values:
            measure = maps.get("cat01", {}).get(v.get("@cat01"), "")
            # Each table ships the level plus year-on-year and share variants.
            # Only the level (実数) is wanted.
            if not measure.startswith(measure_prefix) or "実数" not in measure:
                continue
            key = maps.get("cat02", {}).get(v.get("@cat02"), "")
            parts = key.split("_")
            if len(parts) < 4:
                continue
            year, area_code = parts[1], parts[2]
            if area_code == "00":          # national total row
                continue
            try:
                value = float(str(v.get("$", "")).replace(",", ""))
            except (TypeError, ValueError):
                continue
            rows.append({"year": int(year), "prefecture_code": area_code, "value": value})
    return pd.DataFrame(rows)


def load(year: int = 2020) -> pd.DataFrame:
    """Prefecture-level totals for one reference year, CoM-compatible columns."""
    out = None
    for column, (tag, prefix) in TABLES.items():
        df = _load_measure(tag, prefix)
        df = df[df.year == year][["prefecture_code", "value"]].rename(columns={"value": column})
        out = df if out is None else out.merge(df, on="prefecture_code", how="outer")
    out["year"] = year
    out["va_per_worker"] = out["value_added_total"] / out["employment_total"]
    return out.sort_values("prefecture_code").reset_index(drop=True)


def verify_gate(panel_2019: pd.DataFrame) -> dict:
    """Check the Economic Census's own 2019 figures against the CoM's.

    `panel_2019` is the 2019 slice of panel_prefecture_year.csv, indexed by
    prefecture_code. Returns the max absolute difference per measure; zero means
    the two sources agree exactly and 2020 may be appended.
    """
    ec19 = load(2019).set_index("prefecture_code")
    idx = sorted(set(ec19.index) & set(panel_2019.index))
    report = {"prefectures_matched": len(idx)}
    for col in ("employment_total", "value_added_total", "establishments_total"):
        if col not in panel_2019.columns:
            continue
        diff = (ec19.loc[idx, col] - panel_2019.loc[idx, col]).abs()
        report[col] = {"max_abs_diff": float(diff.max()),
                       "exact_matches": int((diff == 0).sum())}
    return report


if __name__ == "__main__":
    panel = pd.read_csv(PROJECT_ROOT / "processed_data" / "panel_prefecture_year.csv",
                        dtype={"prefecture_code": str})
    gate = verify_gate(panel[panel.year == 2019].set_index("prefecture_code"))
    print("comparability gate, Economic Census 2019 vs Census of Manufacture 2019:")
    for k, v in gate.items():
        print(f"  {k}: {v}")
    d = load(2020)
    print(f"\n2020: {len(d)} prefectures, "
          f"national VA/worker = "
          f"{d.value_added_total.sum()/d.employment_total.sum():.3f} 百万円")

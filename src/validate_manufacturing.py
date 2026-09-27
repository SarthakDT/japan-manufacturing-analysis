"""
validate_manufacturing.py — turn raw e-Stat Census of Manufacture JSON into a
validated prefecture x industry panel slice.

Non-negotiables encoded here:

  * Confidentiality-suppressed cells (X / χ / Ｘ) become NaN with a `suppressed`
    flag. They are NEVER coerced to 0. Suppression targets thin
    prefecture x industry cells, so it is non-random and correlated with small
    industry presence — exactly the cells a location quotient depends on.
  * The 47 prefectures are WHITELISTED by name, not filtered by blacklisting the
    21 designated cities. A whitelist fails loudly when the source changes; a
    blacklist fails silently and double-counts.
  * The output grid is built by explicit reindex onto the full 47 x 24 product.
    `pivot_table(..., dropna=False)` is not used: it cross-multiplies every
    dimension and explodes the row count.
  * Negative value added is preserved and reported, never clipped. Net value
    added is legitimately negative when depreciation exceeds operating margin.

Usage:
    python src/validate_manufacturing.py --reference-year 2018 --table 3-01
    python src/validate_manufacturing.py --self-test
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "raw_data" / "manufacturing"
PROCESSED_ROOT = PROJECT_ROOT / "processed_data"
METADATA_ROOT = PROJECT_ROOT / "metadata"

# ---------------------------------------------------------------------------
# Reference vocabularies
# ---------------------------------------------------------------------------

# JIS X 0401 order. Names are stored as e-Stat renders them in these tables:
# WITHOUT the 都 / 道 / 府 / 県 suffix, except 北海道 which has no bare form.
PREFECTURES: list[tuple[str, str]] = [
    ("01", "北海道"), ("02", "青森"), ("03", "岩手"), ("04", "宮城"),
    ("05", "秋田"), ("06", "山形"), ("07", "福島"), ("08", "茨城"),
    ("09", "栃木"), ("10", "群馬"), ("11", "埼玉"), ("12", "千葉"),
    ("13", "東京"), ("14", "神奈川"), ("15", "新潟"), ("16", "富山"),
    ("17", "石川"), ("18", "福井"), ("19", "山梨"), ("20", "長野"),
    ("21", "岐阜"), ("22", "静岡"), ("23", "愛知"), ("24", "三重"),
    ("25", "滋賀"), ("26", "京都"), ("27", "大阪"), ("28", "兵庫"),
    ("29", "奈良"), ("30", "和歌山"), ("31", "鳥取"), ("32", "島根"),
    ("33", "岡山"), ("34", "広島"), ("35", "山口"), ("36", "徳島"),
    ("37", "香川"), ("38", "愛媛"), ("39", "高知"), ("40", "福岡"),
    ("41", "佐賀"), ("42", "長崎"), ("43", "熊本"), ("44", "大分"),
    ("45", "宮崎"), ("46", "鹿児島"), ("47", "沖縄"),
]
PREF_NAME_TO_CODE = {name: code for code, name in PREFECTURES}

# JSIC 2-digit manufacturing divisions, post-2008 revision. 24 real industries.
# 【00】製造業計 is the total row and is excluded from the panel.
EXPECTED_INDUSTRY_CODES = [f"{n:02d}" for n in range(9, 33)]  # 09..32
TOTAL_INDUSTRY_CODE = "00"

# e-Stat measure name -> output column. Matching is on the normalised name with
# the unit parenthetical stripped, because the unit suffix varies by year.
MEASURE_MAP: dict[str, str] = {
    "事業所数": "establishments",
    # Table 3-03 reports establishment counts split into size bands instead of a
    # single column, which is why it carries 10 measures against 3-01's 6. The
    # tilde arrives as U+FF5E and NFKC-folds to ASCII '~'.
    "事業所数[合計]": "establishments",
    "事業所数[従業者30人~99人]": "establishments_30_99",
    "事業所数[従業者100人~299人]": "establishments_100_299",
    "事業所数[従業者300人以上]": "establishments_300plus",
    # The pre-2017 市区町村編 lineage (reference years 2010-2014). Note it reports
    # 粗付加価値額 (GROSS) only — it has no net 付加価値額 column at all, so
    # `value_added` is correctly reported missing for those years rather than
    # being silently filled from a differently-defined column.
    "事業所数[計]": "establishments",
    "事業所数[内従業者30人~299人]": "establishments_30_299",
    "事業所数[内従業者300人以上]": "establishments_300plus",
    "製造品出荷額等[内その他収入額]": "other_income",
    "有形固定資産年末現在高(従業者30人以上)": "tangible_fixed_assets_30plus",
    # Table 3-04 (地域別, 30+ employees): inventories and tangible fixed assets.
    # The capital-stock measure is the year-end balance (A+B-E-F); the others are
    # the flows that reconcile it. Used for the capital-deepening test, always
    # paired with 30+ employment from table 3-03 so coverage matches.
    "有形固定資産額[(A+B-E-F) 年末現在高]": "capital_stock_year_end",
    "有形固定資産額[(B+C-D) 投資総額]": "capital_investment",
    "有形固定資産額[F 減価償却額]": "capital_depreciation",
    "有形固定資産額[A 年初現在高]【土地】": "capital_open_land",
    "有形固定資産額[A 年初現在高]【土地以外のもの】": "capital_open_nonland",
    # LABEL DRIFT: the same measures in the 2017 and 2018 surveys (reference years
    # 2016 and 2017) omit the accounting reference letters that later years add.
    # Identical quantities, different strings. Left unmapped this silently yields
    # an empty result rather than an error, so both spellings are listed.
    "有形固定資産額[年末現在高]": "capital_stock_year_end",
    "有形固定資産額[投資総額]": "capital_investment",
    "有形固定資産額[減価償却額]": "capital_depreciation",
    "有形固定資産額[年初現在高]【土地】": "capital_open_land",
    "有形固定資産額[年初現在高]【土地以外のもの】": "capital_open_nonland",
    "従業者数": "employment",
    "現金給与総額": "cash_wages",
    "原材料使用額等": "raw_materials",
    "製造品出荷額等": "shipments",
    "付加価値額": "value_added",
    "付加価値額(従業者29人以下は粗付加価値額)": "value_added",
    "粗付加価値額": "gross_value_added",
    "生産額": "production_value",
}

REQUIRED_MEASURES = ["establishments", "employment", "shipments", "value_added"]
OPTIONAL_MEASURES = ["cash_wages", "raw_materials", "production_value", "gross_value_added",
                     "other_income", "tangible_fixed_assets_30plus",
                     "establishments_30_99", "establishments_100_299",
                     "establishments_30_299", "establishments_300plus",
                     "capital_stock_year_end", "capital_investment",
                     "capital_depreciation", "capital_open_land", "capital_open_nonland"]

# Confidentiality suppression. Three glyphs, and an ASCII-only regex misses two.
SUPPRESSED_GLYPHS = {"X", "x", "Ｘ", "ｘ", "χ", "Χ", "ｘ"}
# Nil / not-applicable-by-definition markers.
NIL_GLYPHS = {"-", "－", "‐", "‑", "–", "—", "―", "ー", "*", "**", "***",
              "＊", "＊＊", "＊＊＊", "…", "・・・", "．．．", ""}


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def as_list(node):
    """e-Stat collapses single-element arrays into bare objects. Normalise."""
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


def normalise_measure_name(raw: str) -> str:
    """Strip the trailing unit parenthetical and width-normalise."""
    s = unicodedata.normalize("NFKC", raw or "").strip()
    # Drop a trailing unit such as （百万円） or （人）, but keep the
    # 付加価値額(従業者29人以下は粗付加価値額) qualifier, which is not a unit.
    s = re.sub(r"[（(](?:人|百万円|万円|千円|円|事業所|件)[)）]\s*$", "", s)
    return s.strip()


def parse_industry(raw_name: str) -> tuple[str | None, str]:
    """Split 【09】食料品製造業 into ('09', '食料品製造業')."""
    s = (raw_name or "").strip()
    m = re.match(r"^[【\[]\s*(\d{1,4})\s*[】\]]\s*(.*)$", s)
    if m:
        return m.group(1).zfill(2), m.group(2).strip()
    return None, s


def normalise_pref_name(raw_name: str) -> str:
    """Return the bare prefecture name, or the input unchanged if not a match.

    Only a trailing 都/府/県 is stripped, and 北海道 is left intact. This must
    never collapse 東京特別区 onto 東京 — they are distinct items and the
    special wards are a subset already counted inside the Tokyo row.
    """
    s = unicodedata.normalize("NFKC", (raw_name or "").strip())
    if s == "北海道":
        return s
    if len(s) > 1 and s[-1] in "都府県":
        candidate = s[:-1]
        if candidate in PREF_NAME_TO_CODE:
            return candidate
    return s


def classify_value(raw) -> tuple[float | None, str]:
    """Map a raw e-Stat cell to (numeric_value, flag)."""
    if raw is None:
        return None, "nil_or_na"
    s = unicodedata.normalize("NFKC", str(raw)).strip()
    if s in SUPPRESSED_GLYPHS or s.upper() == "X":
        return None, "suppressed"
    if s in NIL_GLYPHS:
        return None, "nil_or_na"
    try:
        return float(s.replace(",", "").replace("△", "-")), "ok"
    except ValueError:
        # Catch the suppression glyphs once more after NFKC folding.
        if any(ch in SUPPRESSED_GLYPHS for ch in s):
            return None, "suppressed"
        return None, "non_numeric"


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def load_pages(paths: list[Path]) -> tuple[pd.DataFrame, dict, dict]:
    """Read raw getStatsData pages into a long dataframe plus dimension maps."""
    records: list[dict] = []
    code_to_name: dict[str, dict[str, str]] = {}
    dim_roles: dict[str, str] = {}
    notes: dict[str, str] = {}

    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stat = payload["GET_STATS_DATA"]["STATISTICAL_DATA"]

        for obj in as_list(stat.get("CLASS_INF", {}).get("CLASS_OBJ")):
            dim_id = obj["@id"]
            dim_name = obj.get("@name", "")
            code_to_name.setdefault(dim_id, {})
            for member in as_list(obj.get("CLASS")):
                code_to_name[dim_id][str(member.get("@code"))] = member.get("@name", "")
            # Role detection: never assume industry is @cat01 or area is @area.
            # In these tables the measure dimension is @cat01, named
            # "確報（産業編）・集計項目(H25から)", and industry is @cat02. Note the
            # measure name CONTAINS 産業 (in 産業編), so the measure test must run
            # before the industry test or the two dimensions are swapped.
            if dim_id == "tab" or "表章" in dim_name or "集計項目" in dim_name:
                dim_roles[dim_id] = "measure"
            elif dim_id == "area" or "地域" in dim_name or "都道府県" in dim_name:
                dim_roles[dim_id] = "area"
            elif "時間" in dim_name or dim_id == "time":
                dim_roles[dim_id] = "time"
            elif "産業" in dim_name:
                dim_roles[dim_id] = "industry"

        for note in as_list(stat.get("DATA_INF", {}).get("NOTE")):
            notes[str(note.get("@char"))] = note.get("$", "")

        for cell in as_list(stat.get("DATA_INF", {}).get("VALUE")):
            rec = {k.lstrip("@"): v for k, v in cell.items() if k != "$"}
            rec["raw_value"] = cell.get("$")
            records.append(rec)

    if not records:
        raise SystemExit("no VALUE cells found in the supplied raw pages")

    return pd.DataFrame(records), code_to_name, {"dim_roles": dim_roles, "notes": notes}


# ---------------------------------------------------------------------------
# Transform + validate
# ---------------------------------------------------------------------------

def build_panel(df_long: pd.DataFrame, code_to_name: dict, dim_roles: dict,
                reference_year: int) -> tuple[pd.DataFrame, dict]:
    report: dict = {"input_cells": int(len(df_long))}

    role_to_dim = {}
    for dim_id, role in dim_roles.items():
        role_to_dim.setdefault(role, dim_id)
    for role in ("measure", "area", "industry"):
        if role not in role_to_dim:
            raise SystemExit(
                f"could not locate the '{role}' dimension. "
                f"Roles found: {dim_roles}. Run `fetch_estat.py meta` and inspect."
            )
    d_measure, d_area, d_industry = (role_to_dim["measure"],
                                     role_to_dim["area"],
                                     role_to_dim["industry"])

    work = df_long.copy()

    # Some pre-2017 tables (the 市区町村編 series) bundle several years into one
    # table via a @time dimension. Select the requested reference year before
    # anything else, or every prefecture x industry x measure key appears once
    # per year and the duplicate check fires.
    d_time = role_to_dim.get("time")
    if d_time and d_time in work.columns:
        time_names = work[d_time].map(code_to_name.get(d_time, {})).fillna("")
        wanted = time_names.str.startswith(str(reference_year))
        report["time_dimension"] = {
            "dimension": d_time,
            "available": sorted(set(time_names)),
            "selected": str(reference_year),
            "rows_before": int(len(work)),
        }
        if not wanted.any():
            raise SystemExit(
                f"table has a time dimension but no entry for {reference_year}. "
                f"Available: {sorted(set(time_names))}"
            )
        work = work[wanted].copy()
        report["time_dimension"]["rows_after"] = int(len(work))

    work["measure_raw"] = work[d_measure].map(code_to_name[d_measure]).fillna("")
    work["area_raw"] = work[d_area].map(code_to_name[d_area]).fillna("")
    work["industry_raw"] = work[d_industry].map(code_to_name[d_industry]).fillna("")

    work["measure"] = work["measure_raw"].map(
        lambda s: MEASURE_MAP.get(normalise_measure_name(s))
    )
    unmapped = sorted(set(work.loc[work["measure"].isna(), "measure_raw"]))
    report["unmapped_measures"] = unmapped

    work["prefecture_name"] = work["area_raw"].map(normalise_pref_name)
    work["prefecture_code"] = work["prefecture_name"].map(PREF_NAME_TO_CODE)

    parsed_ind = work["industry_raw"].map(parse_industry)
    work["industry_code"] = parsed_ind.map(lambda t: t[0])
    work["industry_name"] = parsed_ind.map(lambda t: t[1])

    # --- national control rows, kept aside for reconciliation ---------------
    # Two shapes occur. Up to the 2019 survey the current year is an unmarked
    # 全国計 alongside 全国計(YYYY年) comparison rows. In the 2020 survey every
    # national row is year-labelled and there is no unmarked one. Prefer the row
    # explicitly tagged with the reference year; fall back to the unmarked row.
    national_mask = work["area_raw"].str.startswith("全国")
    report["national_area_items"] = sorted(set(work.loc[national_mask, "area_raw"]))

    tagged = work["area_raw"].str.fullmatch(rf"全国計\({reference_year}年\)")
    untagged = work["area_raw"].str.fullmatch(r"全国計")
    if tagged.any():
        national = work[tagged].copy()
        report["national_control_row"] = f"全国計({reference_year}年)"
    else:
        national = work[untagged].copy()
        report["national_control_row"] = "全国計 (unmarked)"
    if not len(national):
        report["national_control_row"] = None

    # --- the panel itself ---------------------------------------------------
    keep = (
        work["prefecture_code"].notna()
        & work["industry_code"].notna()
        & (work["industry_code"] != TOTAL_INDUSTRY_CODE)
        & work["measure"].notna()
    )
    panel = work[keep].copy()

    dropped_areas = sorted(set(work.loc[work["prefecture_code"].isna(), "area_raw"]))
    report["excluded_area_items"] = dropped_areas
    report["excluded_area_count"] = len(dropped_areas)

    classified = panel["raw_value"].map(classify_value)
    panel["value"] = classified.map(lambda t: t[0])
    panel["flag"] = classified.map(lambda t: t[1])

    # Duplicate detection BEFORE reshaping, so the message is actionable.
    key = ["prefecture_code", "industry_code", "measure"]
    dupes = panel[panel.duplicated(key, keep=False)]
    report["duplicate_rows"] = int(len(dupes))
    if len(dupes):
        report["duplicate_examples"] = (
            dupes.sort_values(key)[key + ["raw_value"]].head(12).to_dict("records")
        )
        raise SystemExit(
            f"{len(dupes)} duplicate prefecture x industry x measure rows. "
            "Refusing to aggregate silently — inspect the raw pages."
        )

    # --- explicit 47 x 24 grid ---------------------------------------------
    grid = pd.MultiIndex.from_tuples(
        list(itertools.product([c for c, _ in PREFECTURES], EXPECTED_INDUSTRY_CODES)),
        names=["prefecture_code", "industry_code"],
    )

    values_wide = (panel.set_index(key)["value"].unstack("measure")
                   .reindex(grid))
    flags_wide = (panel.set_index(key)["flag"].unstack("measure")
                  .reindex(grid))

    present = [m for m in REQUIRED_MEASURES + OPTIONAL_MEASURES
               if m in values_wide.columns]
    missing_required = [m for m in REQUIRED_MEASURES if m not in values_wide.columns]
    report["missing_required_measures"] = missing_required

    # A year can be present in a table's time dimension while carrying only
    # national rows: the 市区町村編 lineage holds prefecture detail for its own
    # survey year and keeps prior years as 全国 comparison rows only. That yields
    # an all-NaN 47 x 24 grid, which must fail loudly rather than be written out
    # as a plausible-looking empty CSV.
    if not present:
        raise SystemExit(
            f"no measures survived filtering for reference year {reference_year}. "
            f"{len(panel)} panel cells matched a whitelisted prefecture. "
            f"This table most likely carries prefecture detail for one year only "
            f"and holds other years as national rows. Area items seen: "
            f"{sorted(set(work['area_raw']))[:8]}"
        )

    out = pd.DataFrame(index=grid).reset_index()
    out.insert(0, "year", reference_year)
    out["prefecture_name"] = out["prefecture_code"].map(
        {code: name for code, name in PREFECTURES}
    )
    industry_names = (panel.drop_duplicates("industry_code")
                      .set_index("industry_code")["industry_name"].to_dict())
    out["industry_name"] = out["industry_code"].map(industry_names)

    for measure in present:
        out[measure] = values_wide[measure].to_numpy()
        # A combination absent from the source is distinct from a suppressed one.
        out[f"{measure}_flag"] = pd.Series(
            flags_wide[measure].to_numpy(), index=out.index
        ).fillna("absent_from_source")

    ordered = (["year", "prefecture_code", "prefecture_name",
                "industry_code", "industry_name"]
               + list(itertools.chain.from_iterable(
                   (m, f"{m}_flag") for m in present)))
    out = out[ordered].sort_values(["prefecture_code", "industry_code"]).reset_index(drop=True)

    # --- validation ---------------------------------------------------------
    report["row_count"] = int(len(out))
    report["prefecture_count"] = int(out["prefecture_code"].nunique())
    report["industry_count"] = int(out["industry_code"].nunique())
    report["flag_counts"] = {
        m: flags_wide[m].fillna("absent_from_source").value_counts().to_dict()
        for m in present
    }

    negatives = {}
    for m in present:
        neg = out[out[m] < 0]
        if len(neg):
            negatives[m] = neg[["prefecture_name", "industry_name", m]].to_dict("records")
    report["negative_values"] = negatives

    # --- reconciliation against the 全国計 control row -----------------------
    recon = []
    if len(national):
        nat = national.copy()
        nat_classified = nat["raw_value"].map(classify_value)
        nat["value"] = nat_classified.map(lambda t: t[0])
        nat["measure"] = nat["measure_raw"].map(
            lambda s: MEASURE_MAP.get(normalise_measure_name(s)))
        nat_tot = nat[nat["industry_code"] == TOTAL_INDUSTRY_CODE]
        for m in present:
            control = nat_tot.loc[nat_tot["measure"] == m, "value"]
            if not len(control) or pd.isna(control.iloc[0]):
                continue
            control_val = float(control.iloc[0])
            summed = float(out[m].sum(skipna=True))
            gap = summed - control_val
            recon.append({
                "measure": m,
                "sum_of_47_prefectures": summed,
                "national_control_row": control_val,
                "absolute_gap": gap,
                "relative_gap_pct": (gap / control_val * 100) if control_val else None,
            })
    report["reconciliation"] = recon

    return out, report


# ---------------------------------------------------------------------------
# Self-test on a synthetic fixture
# ---------------------------------------------------------------------------

def _synthetic_payload() -> dict:
    """A miniature e-Stat response exercising every trap the real data has."""
    areas = [("00000", "全国計"), ("90000", "全国計(2014年)"),
             ("13000", "東京"), ("13100", "東京特別区"),
             ("23000", "愛知"), ("23100", "名古屋市"), ("43000", "熊本県")]
    industries = [("00", "【00】製造業計"), ("09", "【09】食料品製造業"),
                  ("22", "【22】鉄鋼業"), ("31", "【31】輸送用機械器具製造業")]
    measures = [("17000000", "事業所数"), ("18000000", "従業者数（人）"),
                ("22000000", "製造品出荷額等（百万円）"),
                ("23000000", "付加価値額(従業者29人以下は粗付加価値額)（百万円）")]

    values = []
    for (a_code, a_name), (i_code, _), (m_code, _) in itertools.product(
            areas, industries, measures):
        if a_name == "熊本県" and i_code == "22":
            raw = "χ"                      # Greek chi suppression
        elif a_name == "東京" and i_code == "31" and m_code == "23000000":
            raw = "Ｘ"                      # full-width suppression
        elif a_name == "愛知" and i_code == "09" and m_code == "23000000":
            raw = "-2500"                  # legitimately negative net value added
        elif a_name == "熊本県" and i_code == "31" and m_code == "17000000":
            raw = "***"                    # nil by definition
        else:
            raw = str(1000 + int(i_code) * 7 + int(m_code[:2]))
        values.append({"@cat01": m_code, "@cat02": i_code, "@area": a_code,
                       "@time": "2018000000", "$": raw})

    # Drop one combination entirely: it must reappear as an explicit NaN row.
    values = [v for v in values
              if not (v["@area"] == "23000" and v["@cat02"] == "22"
                      and v["@cat01"] == "22000000")]

    return {"GET_STATS_DATA": {
        "RESULT": {"STATUS": 0},
        "STATISTICAL_DATA": {
            "RESULT_INF": {"TOTAL_NUMBER": len(values)},
            # Dimension ids and names exactly as e-Stat publishes them for these
            # tables. The measure dimension is @cat01 and its name contains 産業
            # (in 産業編) — the trap that swaps measure and industry if the role
            # tests run in the wrong order.
            "CLASS_INF": {"CLASS_OBJ": [
                {"@id": "cat01", "@name": "確報（産業編）・集計項目(H25から)",
                 "CLASS": [{"@code": c, "@name": n} for c, n in measures]},
                {"@id": "cat02", "@name": "産業中分類(コード付加)",
                 "CLASS": [{"@code": c, "@name": n} for c, n in industries]},
                {"@id": "area", "@name": "都道府県及び東京特別区・政令指定都市(H29から)",
                 "CLASS": [{"@code": c, "@name": n} for c, n in areas]},
            ]},
            "DATA_INF": {
                "NOTE": [{"@char": "X", "$": "秘匿"}],
                "VALUE": values,
            },
        }}}


def run_self_test(tmp_dir: Path) -> int:
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fixture = tmp_dir / "_fixture_selftest.json"
    fixture.write_text(json.dumps(_synthetic_payload(), ensure_ascii=False),
                       encoding="utf-8")
    failures: list[str] = []
    try:
        df_long, code_to_name, extra = load_pages([fixture])
        panel, report = build_panel(df_long, code_to_name,
                                    extra["dim_roles"], reference_year=2018)

        def check(label: str, cond: bool, detail: str = "") -> None:
            print(f"  [{'PASS' if cond else 'FAIL'}] {label}{(' — ' + detail) if detail and not cond else ''}")
            if not cond:
                failures.append(label)

        print("self-test on synthetic fixture:")
        check("grid is exactly 47 x 24 = 1128 rows", len(panel) == 1128,
              f"got {len(panel)}")
        check("47 prefectures", panel["prefecture_code"].nunique() == 47)
        check("24 industries", panel["industry_code"].nunique() == 24)
        check("total row 【00】 excluded", TOTAL_INDUSTRY_CODE not in set(panel["industry_code"]))

        excluded = set(report["excluded_area_items"])
        check("designated cities excluded",
              {"東京特別区", "名古屋市"} <= excluded, str(sorted(excluded)))
        check("other-year national rows excluded", "全国計(2014年)" in excluded)
        check("熊本県 normalised onto the whitelist",
              "熊本" in set(panel["prefecture_name"]))

        def cell(pref, ind, col):
            row = panel[(panel["prefecture_name"] == pref)
                        & (panel["industry_code"] == ind)]
            return row.iloc[0][col]

        check("Greek chi read as suppressed",
              cell("熊本", "22", "value_added_flag") == "suppressed",
              str(cell("熊本", "22", "value_added_flag")))
        check("full-width Ｘ read as suppressed",
              cell("東京", "31", "value_added_flag") == "suppressed",
              str(cell("東京", "31", "value_added_flag")))
        check("suppressed cell is NaN, not 0",
              pd.isna(cell("熊本", "22", "value_added")))
        check("*** read as nil_or_na",
              cell("熊本", "31", "establishments_flag") == "nil_or_na",
              str(cell("熊本", "31", "establishments_flag")))
        check("negative value added preserved",
              cell("愛知", "09", "value_added") == -2500.0,
              str(cell("愛知", "09", "value_added")))
        check("negative reported, not silently kept",
              "value_added" in report["negative_values"])
        check("row absent from source survives as a flagged NaN row",
              pd.isna(cell("愛知", "22", "shipments"))
              and cell("愛知", "22", "shipments_flag") == "absent_from_source",
              str(cell("愛知", "22", "shipments_flag")))
        check("industries never seen in source still present as rows",
              len(panel[panel["industry_code"] == "12"]) == 47)
        check("reconciliation computed against 全国計", len(report["reconciliation"]) > 0)
    finally:
        if fixture.exists():
            fixture.unlink()

    print(f"\nself-test: {'ALL PASSED' if not failures else str(len(failures)) + ' FAILED'}")
    return 0 if not failures else 1


# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-year", type=int)
    parser.add_argument("--table", default="3-01")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--tmp-dir", default=None,
                        help="scratch dir for the self-test fixture")
    args = parser.parse_args(argv)

    if args.self_test:
        tmp = Path(args.tmp_dir) if args.tmp_dir else Path.cwd() / "_scratch_selftest"
        return run_self_test(tmp)

    if not args.reference_year:
        parser.error("--reference-year is required unless --self-test is given")

    year_dir = RAW_ROOT / str(args.reference_year)
    pages = sorted(year_dir.glob(f"table{args.table}_*_p*.json"))
    if not pages:
        print(f"ERROR: no raw pages in {year_dir} for table {args.table}.\n"
              f"Run: python src/fetch_estat.py data --statsdataid <id> "
              f"--reference-year {args.reference_year} --table {args.table}",
              file=sys.stderr)
        return 2

    df_long, code_to_name, extra = load_pages(pages)
    panel, report = build_panel(df_long, code_to_name, extra["dim_roles"],
                                args.reference_year)

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    out_csv = PROCESSED_ROOT / f"manufacturing_{args.reference_year}_table{args.table}.csv"
    panel.to_csv(out_csv, index=False, encoding="utf-8-sig")

    report["source_pages"] = [p.name for p in pages]
    report["output"] = out_csv.name
    report["evidence_class"] = "transformed-by-pipeline"
    METADATA_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = METADATA_ROOT / f"validation_{args.reference_year}_table{args.table}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str),
                           encoding="utf-8")

    ok = (report["row_count"] == 1128
          and report["prefecture_count"] == 47
          and report["industry_count"] == 24
          and report["duplicate_rows"] == 0
          and not report["missing_required_measures"])
    print(f"rows={report['row_count']} prefectures={report['prefecture_count']} "
          f"industries={report['industry_count']} dupes={report['duplicate_rows']}")
    print(f"wrote {out_csv}\nwrote {report_path}")
    if report["negative_values"]:
        print("NOTE: negative values present and preserved — see the report.")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
fetch_estat.py — acquire Census of Manufacture (工業統計調査) tables from the e-Stat API.

Design rules for this project:

  * Raw responses are written to disk byte-for-byte, never parsed-then-reserialised.
    Cleaning happens downstream in validate_manufacturing.py.
  * `replaceSpChar=0` is sent explicitly. e-Stat can substitute `0` for the
    confidentiality-suppression glyphs (X / χ / Ｘ). That would silently destroy
    every location quotient built on thin prefecture x industry cells.
  * Directories are named by REFERENCE YEAR, not survey year. e-Stat labels its
    datasets by survey year, and from the 2017 survey onward the financial items
    refer to the PREVIOUS calendar year. See metadata/reference_year_mapping.md.
    Every download writes a manifest.json recording both years.

Usage:
    python src/fetch_estat.py discover
    python src/fetch_estat.py meta --statsdataid 0003432909
    python src/fetch_estat.py data --statsdataid 0003432909 --reference-year 2018 --table 3-03
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = "https://api.e-stat.go.jp/rest/3.0/app/json"
CENSUS_OF_MANUFACTURE_STATS_CODE = "00550010"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_ROOT = PROJECT_ROOT / "raw_data" / "manufacturing"
METADATA_ROOT = PROJECT_ROOT / "metadata"


class EstatError(RuntimeError):
    pass


def get_app_id() -> str:
    app_id = os.environ.get("ESTAT_APP_ID", "").strip()
    if not app_id:
        raise EstatError(
            "ESTAT_APP_ID is not set.\n"
            "Register (free, instant) at https://www.e-stat.go.jp/mypage/user/preregister\n"
            "then set it, e.g. in PowerShell:  $env:ESTAT_APP_ID = '<your key>'"
        )
    return app_id


def call(endpoint: str, params: dict, *, retries: int = 3) -> tuple[dict, bytes]:
    """Call an e-Stat JSON endpoint. Returns (parsed, raw_bytes).

    e-Stat signals auth failure with HTTP 403 but still returns a valid XML/JSON
    body carrying RESULT.STATUS=100, so the body is read on error responses too.
    """
    query = urllib.parse.urlencode(params)
    url = f"{API_ROOT}/{endpoint}?{query}"
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "japan-mfg-atlas/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read()
            break
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code == 403:
                # Almost certainly an e-Stat auth error rather than a transport failure.
                break
            last_err = exc
        except Exception as exc:  # noqa: BLE001 - transport level, retry
            last_err = exc
        if attempt < retries:
            time.sleep(2 * attempt)
    else:
        raise EstatError(f"request failed after {retries} attempts: {last_err}")

    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise EstatError(f"non-JSON response from {endpoint}: {raw[:400]!r}") from exc

    root_key = next(iter(parsed))
    result = parsed[root_key].get("RESULT", {})
    status = result.get("STATUS")
    if status not in (0, "0"):
        raise EstatError(
            f"e-Stat API error on {endpoint}: STATUS={status} "
            f"MSG={result.get('ERROR_MSG')}"
        )
    return parsed, raw


def _as_list(node):
    """e-Stat collapses single-element arrays into bare objects. Normalise."""
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


def cmd_discover(_args) -> int:
    """Enumerate every Census of Manufacture table across all survey years.

    This is how the statsDataIds for years other than the 2019 survey are found.
    Guessing them is not safe: each survey year has its own independent block.
    """
    stats_code = getattr(_args, "stats_code", None) or CENSUS_OF_MANUFACTURE_STATS_CODE
    params = {
        "appId": get_app_id(),
        "statsCode": stats_code,
        "limit": 10000,
    }
    search_word = getattr(_args, "search_word", None)
    if search_word:
        params["searchWord"] = search_word
    parsed, raw = call("getStatsList", params)

    METADATA_ROOT.mkdir(parents=True, exist_ok=True)
    suffix = "" if stats_code == CENSUS_OF_MANUFACTURE_STATS_CODE else f"_{stats_code}"
    (METADATA_ROOT / f"estat_statslist_raw{suffix}.json").write_bytes(raw)

    tables = _as_list(parsed["GET_STATS_LIST"]["DATALIST_INF"].get("TABLE_INF"))
    out_path = METADATA_ROOT / f"estat_table_index{suffix}.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["statsDataId", "survey_year_label", "table_title", "table_no",
             "cycle", "survey_date", "updated", "total_cells"]
        )
        for t in tables:
            title = t.get("TITLE")
            title_text = title.get("$") if isinstance(title, dict) else title
            title_no = title.get("@no") if isinstance(title, dict) else ""
            writer.writerow([
                t.get("@id"),
                (t.get("STAT_NAME") or {}).get("$", ""),
                title_text,
                title_no,
                t.get("CYCLE"),
                t.get("SURVEY_DATE"),
                t.get("UPDATED_DATE"),
                t.get("OVERALL_TOTAL_NUMBER"),
            ])

    print(f"discovered {len(tables)} tables -> {out_path}")
    print("Inspect the survey_year_label / table_title columns to pick the right year.")
    return 0


def cmd_meta(args) -> int:
    """Fetch dimension metadata. Always run this before `data` for a new table.

    Which dimension id carries industry vs geography (@cat01 vs @area) is a
    per-table decision by the publisher and must not be assumed.
    """
    params = {"appId": get_app_id(), "statsDataId": args.statsdataid}
    parsed, raw = call("getMetaInfo", params)

    dest = METADATA_ROOT / "meta"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"getMetaInfo_{args.statsdataid}.json"
    path.write_bytes(raw)

    info = parsed["GET_META_INFO"]["METADATA_INF"]
    table_inf = info.get("TABLE_INF", {})
    title = table_inf.get("TITLE")
    print("TITLE:", title.get("$") if isinstance(title, dict) else title)
    print("SURVEY_DATE:", table_inf.get("SURVEY_DATE"))
    print("TOTAL CELLS:", table_inf.get("OVERALL_TOTAL_NUMBER"))
    print()
    for obj in _as_list(info["CLASS_INF"]["CLASS_OBJ"]):
        members = _as_list(obj.get("CLASS"))
        print(f"  @{obj['@id']:<8} {obj.get('@name','')}  ({len(members)} items)")
        for m in members[:4]:
            print(f"      {m.get('@code')}  {m.get('@name')}")
        if len(members) > 4:
            print(f"      ... {len(members) - 4} more")
    print(f"\nsaved -> {path}")
    return 0


def cmd_data(args) -> int:
    """Download a full table, paging until exhausted, saving each page raw."""
    app_id = get_app_id()
    if getattr(args, "dest_dir", None):
        year_dir = PROJECT_ROOT / args.dest_dir
    else:
        year_dir = RAW_ROOT / str(args.reference_year)
    year_dir.mkdir(parents=True, exist_ok=True)

    pages: list[str] = []
    start_position = 1
    total_number = None
    rows_seen = 0

    while True:
        params = {
            "appId": app_id,
            "statsDataId": args.statsdataid,
            "metaGetFlg": "Y",
            "cntGetFlg": "N",
            "explanationGetFlg": "Y",
            "annotationGetFlg": "Y",
            "replaceSpChar": 0,   # 0 = do NOT substitute suppression glyphs
            "limit": args.limit,
            "startPosition": start_position,
        }
        parsed, raw = call("getStatsData", params)

        page_no = len(pages) + 1
        fname = f"table{args.table}_{args.statsdataid}_p{page_no:02d}.json"
        (year_dir / fname).write_bytes(raw)
        pages.append(fname)

        stat = parsed["GET_STATS_DATA"]["STATISTICAL_DATA"]
        result_inf = stat["RESULT_INF"]
        total_number = result_inf.get("TOTAL_NUMBER")
        rows_seen += len(_as_list(stat["DATA_INF"].get("VALUE")))
        print(f"  page {page_no}: rows so far {rows_seen} / {total_number}")

        next_key = result_inf.get("NEXT_KEY")
        if not next_key:
            break
        start_position = int(next_key)

    manifest = {
        "statsDataId": args.statsdataid,
        "table_no": args.table,
        "reference_year": args.reference_year,
        "survey_year_label": args.survey_year,
        "downloaded_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": f"{API_ROOT}/getStatsData",
        "replaceSpChar": 0,
        "pages": pages,
        "total_number_reported": total_number,
        "rows_downloaded": rows_seen,
        "evidence_class": "downloaded",
    }
    (year_dir / f"manifest_table{args.table}_{args.statsdataid}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"saved {len(pages)} page(s) + manifest -> {year_dir}")
    if total_number is not None and rows_seen != int(total_number):
        print(f"WARNING: downloaded {rows_seen} rows but API reported {total_number}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_disc = sub.add_parser("discover", help="list tables for a statistic")
    p_disc.add_argument("--stats-code", default=None,
                        help="e-Stat statsCode; defaults to the Census of Manufacture "
                             "(00550010). Population Estimates is 00200524.")
    p_disc.add_argument("--search-word", default=None,
                        help="optional keyword filter applied by the API")

    p_meta = sub.add_parser("meta", help="fetch dimension metadata for one table")
    p_meta.add_argument("--statsdataid", required=True)

    p_data = sub.add_parser("data", help="download one table in full")
    p_data.add_argument("--statsdataid", required=True)
    p_data.add_argument("--reference-year", required=True, type=int,
                        help="calendar year the FINANCIAL items refer to")
    p_data.add_argument("--survey-year", default="", help="e-Stat label, e.g. 2019年確報")
    p_data.add_argument("--table", required=True, help="table number, e.g. 3-01")
    p_data.add_argument("--limit", type=int, default=100000)
    p_data.add_argument("--dest-dir", default=None,
                        help="project-relative output directory, overriding the "
                             "default raw_data/manufacturing/<reference-year>/")

    args = parser.parse_args(argv)
    handlers = {"discover": cmd_discover, "meta": cmd_meta, "data": cmd_data}
    try:
        return handlers[args.cmd](args)
    except EstatError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

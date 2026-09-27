# Acquisition log

Evidence classes used throughout: **verified-from-source** (read directly off an
official page or API response) · **downloaded** (bytes on disk) ·
**transformed** (produced by this project's code) · **assumed** (not yet checked).

---

## 2026-09-14 — Session 1

### Network reachability — verified-from-source

The previous session was blocked by a proxy (`403 host_not_allowed`). **That
block does not exist here.** Diagnosis:

| Host | Result |
|---|---|
| `www.e-stat.go.jp` | HTTP 200 |
| `www.google.com` | HTTP 200 |
| `api.e-stat.go.jp` | HTTP 403 — **but with a valid e-Stat body** |

The API's 403 is e-Stat's own authentication failure, not a transport block.
Response body, verbatim:

```xml
<RESULT>
    <STATUS>100</STATUS>
    <ERROR_MSG>認証に失敗しました。アプリケーションIDを確認して下さい。</ERROR_MSG>
</RESULT>
```

Served through `Server: ZENEDGE` / Oracle WAF, which returns HTTP 403 where the
API itself signals `STATUS=100`. Any client must therefore read the response
body on 403 rather than treating it as a transport error. `fetch_estat.py`
does this.

**Conclusion: the sole blocker is the missing `ESTAT_APP_ID`.** No data has been
downloaded. `raw_data/` and `processed_data/` are empty by design — no
placeholder or synthetic rows were written.

### Table identity — verified-from-source

Checked against `https://www.e-stat.go.jp/dbview?sid=<id>`:

| statsDataId | Table | Title (verbatim) | Size class |
|---|---|---|---|
| `0003432907` | 3-01 | １. 都道府県別、東京特別区・政令指定都市別統計表　（１）従業者４人以上の事業所に関する統計表　1 産業中分類別の事業所数、従業者数、現金給与総額、原材料使用額等、製造品出荷額等及び付加価値額 | 4+ |
| `0003432909` | 3-03 | １. 都道府県別、東京特別区・政令指定都市別統計表　（２）従業者３０人以上の事業所に関する統計表　1 産業中分類別の事業所数、従業者数、現金給与総額、原材料使用額等、製造品出荷額等、生産額及び付加価値額 | 30+ |

Both belong to `２０１９年確報`, published 2020-08-27.

Two corrections to the brief arise from this:

1. **Table 3-03 has seven measures, not six.** Its title includes **生産額**
   (production value), which 3-01 does not. The brief's §2.8 schema describes
   3-01 only. `MEASURE_MAP` in `validate_manufacturing.py` handles both.
2. **Both tables carry reference year 2018, not 2019.** See
   [reference_year_mapping.md](reference_year_mapping.md).

Table 3-01's measure list and area items were read off e-Stat and match the
brief's §2.8 exactly: six measures, and national rows
`全国計(2014年)` … `全国計(2017年)` plus an unmarked `全国計`.

### Survey-year index — verified-from-source

e-Stat 確報 entries under `toukei=00550010&tstat=000001022686`:

| Label | tclass id |
|---|---|
| ２０２０年確報 | `000001156946` (29 datasets, released 2022-03-09) |
| ２０１９年確報 | `000001143706` (29 datasets, released 2020-08-27) |
| 平成30年確報 | `000001133147` |
| 平成29年確報 | `000001118655` |
| 平成26年確報 | `000001081715` |
| 平成25年確報 | `000001070905` |
| 平成24年確報 | `000001064361` |
| 平成22年確報 | `000001045887` |
| 平成21年確報 | `000001041688` |
| 平成20年確報 | `000001036397` |
| 平成19年確報 | `000001034267` |

No 平成23年, 平成27年 or 平成28年 entry exists, confirming the 2011, 2015 and
2016 gaps. Individual statsDataIds for years other than the 2019 survey are
**not known** — e-Stat renders the table list client-side, so it cannot be
scraped. `fetch_estat.py discover` retrieves them from `getStatsList` once a key
is available.

### Pipeline self-test — transformed

`validate_manufacturing.py --self-test` builds a synthetic e-Stat payload in the
session scratchpad, asserts 16 properties, and deletes the fixture. It never
touches `raw_data/` or `processed_data/`. All 16 passed, including: Greek χ and
full-width Ｘ both read as `suppressed`; suppressed cells stay NaN rather than 0;
designated cities and other-year national rows excluded; a combination absent
from the source surviving as an explicit `absent_from_source` NaN row; and the
grid landing on exactly 1,128 rows rather than exploding.

---

## 2026-09-14 — Session 1, continued (API key supplied)

### Discovery — downloaded

`fetch_estat.py discover` returned **661** Census of Manufacture tables to
`estat_table_index.csv`. The raw response was checked and does **not** echo the
application ID, so it is safe to keep in the repository.

### Reference year resolved empirically — verified-from-source

e-Stat's `SURVEY_DATE` field reports `201901-201912` for the ２０１９年確報,
which contradicts METI. The conflict was settled numerically, not by argument:
the 2019 survey's unmarked `全国計` equals the 2020 survey's explicit
`全国計(2018年)` exactly (331,809,377 百万円), and the 2017 figure agrees across
both tables. Details in [reference_year_mapping.md](reference_year_mapping.md).

**`SURVEY_DATE` is unreliable for every survey from 2017 onward.** The brief's
§2.2 mapping is correct; the brief's §2.7/Step 2 instruction to emit
`manufacturing_2019.csv` from `0003432909` was off by one year.

### Dimension structure — corrected against the brief

The brief's §2.8 implies a `tab` dimension for measures. There is none.

| Dimension | id | Name |
|---|---|---|
| Measures | `@cat01` | 確報（産業編）・集計項目(H25から) |
| Industry | `@cat02` | 産業中分類(コード付加) |
| Geography | `@area` | 都道府県及び東京特別区・政令指定都市(H29から) |

The measure dimension's name **contains 産業** (in 産業編). A role test that
checks for 産業 before checking for 集計項目 silently swaps measures and
industries. `validate_manufacturing.py` orders the tests accordingly and the
self-test fixture now reproduces the real dimension names to cover it.

**Table 3-03 has 10 measures, not 6 or 7.** It splits 事業所数 into four size
bands (合計 / 30–99 / 100–299 / 300+) and adds 生産額. Its value-added column is
plain `付加価値額` with no blend qualifier, confirming it is the clean net
measure. Note the band labels use U+FF5E, which NFKC folds to ASCII `~`.

### Downloads — downloaded

| Ref year | Table | statsDataId | Cells |
|---|---|---|---|
| 2018 | 3-01 | `0003432907` | 10,950 |
| 2018 | 3-03 | `0003432909` | 18,250 |
| 2019 | 3-01 | `0003448119` | 10,853 |
| 2019 | 3-03 | `0003448121` | 16,273 |
| 2016 | 3-01 | `0003325921` | 10,950 |
| 2016 | 3-03 | `0003325923` | 18,250 |
| 2017 | 3-01 | `0003389992` | 10,950 |
| 2017 | 3-03 | `0003389994` | 18,250 |
| 2014 | muni 3-01 | `0003144102` | 18,250 |

### Correction made within this session

The municipality table `0003144102` was initially downloaded into reference-year
directories 2010, 2012, 2013 and 2014 on the assumption that its `@time`
dimension carried four usable years. **That was wrong.** Prefecture detail
exists for 2014 only; 2010–2013 are present as single 全国 rows (250 cells each
against 17,250 for 2014). Selecting an earlier year produced a structurally
valid but entirely empty 47 × 24 grid.

Three consequences, all applied:

1. `validate_manufacturing.py` now raises before writing when no measure
   survives filtering, so this class of silent emptiness cannot recur.
2. The empty CSVs and their validation reports for 2010, 2012 and 2013 were
   deleted, along with the duplicate raw copies implying data that is not there.
3. The availability matrix was corrected.

The LQ break test is unaffected: it uses reference years 2014 and 2016, both of
which have genuine prefecture-level detail.

### Validation results — transformed

All four of the 2018/2019 slices: **1,128 rows, 47 prefectures, 24 industries,
0 duplicates.**

Reconciliation against the national control row is the strongest evidence the
pipeline is correct:

| Slice | establishments | employment | shipments | value added |
|---|---|---|---|---|
| 2018 3-01 | 0.0000% | 0.0000% | −0.0239% | −0.0317% |
| 2018 3-03 | 0.0000% | 0.0000% | −1.4169% | −0.9086% |
| 2019 3-01 | 0.0000% | 0.0000% | −0.0430% | −0.0289% |
| 2019 3-03 | 0.0000% | 0.0000% | −1.7076% | −0.5862% |

Counts reconcile **exactly**; they are never suppressed. The monetary gaps are
negative and their size tracks the suppressed-cell count, which is precisely
what correct suppression handling looks like: the suppressed cells are missing
from the prefecture sum but present in the national total. Had the pipeline
zero-filled, the gap would be identical in sign but the flags would be wrong;
had it dropped rows, the row count would not be 1,128.

**Suppression is 3.5× heavier in table 3-03 than in 3-01** (101 vs 29 suppressed
value-added cells for 2018). This is a real cost of the brief's recommendation
to prefer 3-03, and it was not quantified there. See the open question below.

**Negative value added occurs and was preserved**, always in
石油製品・石炭製品製造業 (petroleum and coal products): 愛媛 −4,283 and 和歌山
−26,435 百万円 in 2019 4+. This is the legitimate case the brief anticipated,
where depreciation exceeds operating margin.

Missing cells are **not** missing at random. In 2018 3-03 they concentrate in
石油製品・石炭製品 (18) and なめし革 (13) across 24 prefectures — the thin cells
the brief warned about. They are held as NaN under `suppressed`,
`nil_or_na` or `absent_from_source` and never zero-filled.

### The pre-2017 lineage reports GROSS value added only — verified-from-source

`0003144102` (平成26年確報 市区町村編, reference years 2010–2014) has these ten
measures: 事業所数[計] / [内従業者30人~299人] / [内従業者300人以上], 従業者数,
現金給与総額, 原材料使用額等, 製造品出荷額等, 製造品出荷額等[内その他収入額],
**粗付加価値額**, 有形固定資産年末現在高(従業者30人以上).

It carries **粗付加価値額 (gross)** and no net 付加価値額 column at all. Joining
it to the post-2016 地域別 tables on a single `value_added` column would silently
splice a gross series onto a net/blended one. The pipeline maps it to a separate
`gross_value_added` column and correctly reports `value_added` as missing for
reference years 2010–2014, which is why those runs exit non-zero.

Net value added for the older block is recoverable, but from the **産業編
従業者30人以上** tables, whose numbering is not stable across years:

| Ref year | e-Stat label | Table no | statsDataId (30+) |
|---|---|---|---|
| 2010 | 平成22年確報 | 3-10 | `0003094711` |
| 2012 | 平成24年確報 | 3-10 | `0003097830` |
| 2013 | 平成25年確報 | 2-10 | `0003127834` |
| 2014 | 平成26年確報 | 2-10 | `0003144079` |

None downloaded yet, and none of their schemas verified.

### LQ break test — transformed, 2026-09-14

Reference year 2014 against 2016, 従業者数, 4+ establishments, 1,120 of 1,128
prefecture × industry pairs usable.

| Statistic | Value |
|---|---|
| Pooled Spearman ρ | **0.9869** |
| Per-industry median ρ | **0.9825** |
| Per-industry min / max | 0.9460 / 0.9966 |
| Industries with ρ > 0.95 | 22 of 24 |
| Industries with ρ < 0.90 | 0 of 24 |
| National employment change | +2.27% |

**Verdict: the location quotient survives the break. H1 can use the full
eight-observation set rather than four.**

The two weakest industries are その他の製造業 (0.9460) and なめし革・同製品・毛皮
製造業 (0.9474). Both are small and heterogeneous with many owner-managed
establishments, which is exactly where 有給役員 density is highest — the
predicted mechanism, showing up where theory says it should.

Two caveats. The test measures **ordering**, not levels: it does not license
pooling LQ levels across the break without a block dummy. And the +2.27%
national employment change is far smaller than the prefecture figures quoted in
the brief's §2.4 (Ishikawa +6.8%, Fukushima +3.2%), because those compare
CoM-2017 against Economic-Census-2016, a different and noisier comparison.

---

## 2026-09-14 — Session 2: analysis panel

### `panel_prefecture_year.csv` built — transformed

188 rows (47 × 4 years, 2016–2019), 22 columns, 12 validation checks passing.
Built by `src/build_panel.py`, which reuses the parsing helpers in
`validate_manufacturing.py` rather than duplicating them.

**Totals come from the 【00】製造業計 row, not from summing industries.** Summing
drops suppressed cells, and the loss is concentrated in small prefectures:

| Prefecture | Coverage if summed | Understatement |
|---|---|---|
| 高知 | 98.46% | 1.54% |
| 長崎 | 98.93% | 1.07% |
| 沖縄 | 99.32% | 0.68% |
| 愛知 | 100.00% | 0.00% |

Nationally this recovers 28,992 百万円. The bias is small in absolute terms but
**correlated with prefecture size**, so it would tilt exactly the regressions
this project runs.

### Population acquired — downloaded

statsDataId `0004021110`, 国勢調査結果による補間補正人口, 都道府県 × 年齢3区分,
8,640 cells, as of 1 October each year. Chosen over the forward-projected
estimates (`0003448225`) because 2016–2019 falls between the 2015 and 2020
censuses, so the intercensal series is reconciled against both benchmarks rather
than projected from one.

Filtered to 男女計 and 総人口 (not 日本人人口).

**Unit bug caught:** the source publishes in **千人**, confirmed from the `@unit`
field on every cell and from the national row reading 127,042 (= 127.0 million).
Taken at face value this made `mfg_intensity` dimensionally wrong by 1000×. The
loader now converts to persons and **asserts** the unit is 千人, so a future
year published in a different unit fails loudly instead of silently rescaling.

### Signal preview — transformed, and later WITHDRAWN

> **Withdrawn in Session 07.** These correlations were part of a set of 15 tests run
> at n = 47 with no correction for multiple comparisons. Seven reached nominal
> significance; **none survived Bonferroni or Benjamini-Hochberg**. The hypotheses
> they refer to have been retired and the analysis removed. The table is kept as a
> record of what was run, **not as a finding**. See Part 20 of
> [work_log.md](work_log.md).

Bivariate correlations against `va_per_worker`, 2019, n=47. **Not the analysis** —
run only to check the panel is not inert:

| Relationship | Pearson | p |
|---|---|---|
| H1: LQ of top industry | −0.082 | 0.584 |
| H1b: HHI concentration | **−0.300** | **0.040** |
| H2: aging ratio (level) | −0.142 | 0.341 |
| H2: aging(2016) vs VA/worker CAGR 2016–19 | **+0.274** | 0.062 |
| H3: HHI(2016) vs growth volatility | −0.027 | 0.856 |

All three hypotheses fail or reverse as stated. See the open questions below for
why H1 is probably mis-specified rather than wrong.

National value added per worker CAGR 2016–2019: **+0.34%**.

---

## Open questions — status as of Session 07

- ~~**Which value-added table should be primary?**~~ **Resolved, Session 02:** 3-01 is
  primary, 3-03 the robustness check. 3-01 suppresses ~2.5% of value-added cells
  against ~9% for 3-01's alternative, and 3-03's suppression concentrates in exactly
  the thin cells a location quotient depends on.
- **Reference year 2011** appears in the municipality table's time dimension but was
  not collected by a Census of Manufacture. **Still unverified — do not use.**

## Acquisition status — closed

| Item | Status |
|---|---|
| Reference years 2016–2019, tables 3-01 and 3-03 | **done** |
| Reference year 2017 (`0003389992` / `0003389994`) | **done**, Session 04 |
| Capital, table 3-04, 2016–2019 | **done**, Session 06 |
| Population (人口推計 intercensal, `0004021110`) | **done**, Session 02 |
| LQ break test, 2014 vs 2016 | **done** — ρ = 0.9869 |
| Reference year 2020 (2021 Economic Census) | **done**, Session 06, gate passed at 0 difference |
| Labour Force Survey | **dropped** — model estimates with large prefecture-level sampling error; working-age population used as the denominator instead |
| Economic Census 2011 and 2015 | **not downloaded** — obtainable (`0003389789`, `0003389393`) |
| ESS 2021 onward | **impossible** — no area dimension; see [year_availability_matrix.md](year_availability_matrix.md) |

**Acquisition is complete for the analysis window.** The panel covers reference years
2016–2020 and ends there permanently. Nothing further is blocked on data collection.

# Complete work log — Sessions 01–09

**Dates:** 2026-09-14 to 2026-09-29
**Starting state:** four loose files in the project root, no code, no data, no directories
**Ending state:** a 235-row prefecture × year panel (2016–2020), 7 source modules with
self-tests, 4 notebooks, a DuckDB/SQL layer, a dashboard extract feeding a Streamlit
app and a Power BI build guide, CI on every push, and a concepts reference — with all
hypothesis-testing work removed after a robustness review

| Session | Scope | Outcome |
|---|---|---|
| 01 | Stage 2 data acquisition | 9 validated prefecture × industry slices |
| 02 | Scope reset, then the analysis panel | `panel_prefecture_year.csv`, 188 rows |
| 03 | First analytical deliverable | EDA notebook, 4 charts, findings v1 |
| 04 | Geography vs industry composition | shift-share module, notebook 02, findings v2 |
| 05 | Conceptual reference | `docs/concepts.md`, ~50 concepts |
| 06 | Capital, convergence, reference year 2020 | panel to 235 rows; ESS shown impossible |
| 07 | Robustness review and removal | hypothesis-testing work deleted; see Part 20 |
| 08 | Consolidation, SQL layer, data mining | duplication removed; DuckDB store; clustering and anomaly detection |
| 09 | Stakeholder, decision layer, dashboards | planner framing; star-schema extract; Streamlit app + Power BI guide; CI; fresh-clone bug fixed |

**Read this as a chronological record, not a statement of current belief.** It
deliberately preserves dead ends, tooling accidents, and claims that were later
corrected or withdrawn — the corrections are the point. Statements in Sessions 01–06
were accurate when written; several were superseded. Where that happened the later
session says so explicitly.

In particular: the three original hypotheses discussed throughout Sessions 03–06 were
**retired in Session 07**, and the panel grew from 188 to 235 rows in Session 06.
Evidence classes are tagged throughout: **verified-from-source** · **downloaded** ·
**transformed** · **assumed**.

Parts 0–9 are Session 01, 10–15 Session 02, 16 Session 03, 17 Session 04, 18 Session 05,
19 Session 06, 20 Session 07, 21–25 Session 08.

---

# SESSION 01 — acquisition

---

## Part 0 — Environment reconnaissance

### 0.1 Initial directory inspection

Listed the working directory. Found four pre-existing files, none of them code:

| File | Size |
|---|---|
| `docs/measurement-framework.md` | 10,490 B |
| `Japan_Manufacturing_Stage1.1_Report.docx` | 35,198 B |
| `OECD Report on Value Added vs Gross.pdf` | 1,007,694 B |
| `research notes.docx` | 0 B (empty) |

Confirmed Python 3.11.9 available.

### 0.2 Credential check

Checked for `ESTAT_APP_ID`. **Not set.** Per the brief's Step 0 this is a stop
condition, so no workaround was attempted.

### 0.3 Network diagnosis — the prior session's blocker investigated

The handoff brief reported a proxy block (`403 host_not_allowed`) that prevented
all downloads. First probe returned HTTP 403 from the API, which superficially
matched. Rather than accept that, I probed four hosts:

| Host | Result |
|---|---|
| `api.e-stat.go.jp/rest/3.0/app/getStatsList` | HTTP 403 |
| `www.e-stat.go.jp` | HTTP 200 |
| `www.google.com` | HTTP 200 |
| `api.github.com` | HTTP 200 |

Since the e-Stat website itself resolved fine, the 403 was not a blanket proxy
block. Retested the API with a browser User-Agent, across API versions 3.0 and
2.1, and against the bare API root. All returned 403, which pointed at either a
host-level block or something else entirely.

Resolved it by reading the **response body** rather than trusting the status
code. Used `curl -i` to capture headers and payload:

```
HTTP/1.1 403 Forbidden
Server: ZENEDGE
X-Cdn: Served-By-Zenedge

<GET_STATS_LIST>
  <RESULT>
    <STATUS>100</STATUS>
    <ERROR_MSG>認証に失敗しました。アプリケーションIDを確認して下さい。</ERROR_MSG>
  </RESULT>
```

**Finding (verified-from-source):** the 403 is e-Stat's own authentication
failure, wrapped by an Oracle/Zenedge WAF that maps `STATUS=100` onto HTTP 403.
The prior session's network block **does not exist in this environment**. The
only blocker was the missing credential.

DNS resolution confirmed the host routes through
`api-e-stat-go-jp.o.waas.oci.oraclecloud.net`.

**Consequence for the code:** any API client must read the body on HTTP 403
instead of treating it as a transport error. This was built into
`fetch_estat.py` from the start.

### 0.4 Directory scaffold created

```
raw_data/manufacturing/2019/
processed_data/
metadata/
src/
```

### 0.5 Read the existing measurement framework

Read `docs/measurement-framework.md` in full to align with prior Stage 1.1
decisions: dependent variable, the seven independent variables, the three
hypotheses, and the honest caveat that gross-output measures are theoretically
cleaner at firm level. Carried this into the README rather than restating it
from the brief.

---

## Part 1 — Verification before trusting the brief

The brief explicitly warned that a prior session got the reference-date change
wrong by two years, and instructed me to re-verify anything load-bearing.

### 1.1 Table identity — statsDataId confirmation

Fetched `https://www.e-stat.go.jp/dbview?sid=<id>` for two IDs.

| statsDataId | Table | Verified title | Size class |
|---|---|---|---|
| `0003432907` | 3-01 | １. 都道府県別、東京特別区・政令指定都市別統計表　（１）従業者４人以上の事業所に関する統計表… | 4+ |
| `0003432909` | 3-03 | …（２）従業者３０人以上の事業所に関する統計表… **生産額**及び付加価値額 | 30+ |

Both confirmed as ２０１９年確報, published 2020-08-27.

**Correction 1 to the brief:** table 3-03's title includes **生産額**
(production value), which 3-01 does not. The brief's §2.8 schema (six measures)
describes 3-01 only. At this point I estimated 3-03 had seven measures. That
estimate was itself later corrected — see §3.6.

### 1.2 Reference-year mapping — METI as the producing agency

`WebFetch` on `https://www.meti.go.jp/statistics/tyo/kougyo/` returned HTTP 403.
Worked around it with `curl` and a browser User-Agent against
`result-2.html`, which succeeded.

Retrieved verbatim:

> 平成29年調査より、調査日を12月31日から翌年6月1日に変更していることから、平成29年調査においては、事業所数、従業者数については平成29年6月1日現在、現金給与総額、製造品出荷額等などの経理事項については平成28年1月～12月の実績を調査しています。

And METI's own column labels:

> 平成30(2018)年 ＜平成29(2017)年実績＞
> 平成29(2017)年 ＜平成28(2016)年実績＞

Also confirmed from the same page that 平成23年実績 (2011) and 平成27年実績
(2015) come from the 経済センサス-活動調査, not the Census of Manufacture.

**Finding:** the brief's §2.2 mapping is correct. Survey year and reference year
diverge by one from the 2017 survey onward.

### 1.3 Survey-year index

Fetched the e-Stat 確報 listing for `toukei=00550010&tstat=000001022686` and
recovered tclass ids for eleven survey years. Confirmed **no** 平成23年,
平成27年 or 平成28年 entry exists, corroborating the 2011, 2015 and 2016 gaps.

Discovered ２０２０年確報 exists (tclass `000001156946`, 29 datasets, released
2022-03-09) — the final Census of Manufacture run.

### 1.4 Dead end: e-Stat table listings are client-rendered

Attempted four different URL shapes to enumerate individual table IDs per survey
year through the web UI. All returned either "0件のデータ" or a search shell with
no table metadata. e-Stat renders the table list in JavaScript.

**Conclusion:** individual statsDataIds for other years are not scrapable and
require `getStatsList` via the API. This made the API key the hard blocker for
Step 4, not just Step 2.

### 1.5 Schema confirmation for table 3-01

Fetched the dbview page for `0003432907` asking specifically about notes, area
items and measures. Confirmed against the brief's §2.8:

- Six measures, matching exactly, including the literal blend label
  `付加価値額(従業者29人以下は粗付加価値額)（百万円）`
- National area items: `全国計(2014年)` … `全国計(2017年)` plus an unmarked
  `全国計`

**Inference drawn at this point:** four comparison years 2014–2017 plus a current
row form a contiguous five-year run only if the current row is 2018. This
suggested the brief's Step 2/Step 3 instruction (emit `manufacturing_2019.csv`
from these IDs) was off by one year. Flagged as a probable error, pending proof.

---

## Part 2 — Building the pipeline (pre-credential)

### 2.1 `src/fetch_estat.py` written

Three subcommands:

| Command | Purpose |
|---|---|
| `discover` | `getStatsList` for statsCode 00550010, writes a full table index |
| `meta` | `getMetaInfo` for one table, prints dimension roles and members |
| `data` | `getStatsData` with `NEXT_KEY` paging, writes raw pages plus a manifest |

Design decisions encoded:

- Reads the response body on HTTP 403, because of the finding in §0.3
- Sends `replaceSpChar=0` explicitly so e-Stat cannot substitute `0` for
  confidentiality-suppression glyphs
- Writes raw bytes with `write_bytes`, never parse-then-reserialise
- Names directories by **reference year** and records both years in a manifest
- Retries transport failures with linear backoff, but not auth failures

### 2.2 `src/validate_manufacturing.py` written

Encoded non-negotiables:

- Suppression glyphs → NaN with a `suppressed` flag, never 0
- The 47 prefectures are **whitelisted by name**, not filtered by blacklisting
  the 21 designated cities. A whitelist fails loudly; a blacklist fails silently
  and double-counts.
- The output grid is built by **explicit reindex** onto the 47 × 24 product.
  `pivot_table(dropna=False)` is deliberately not used — the brief records a
  prior session exploding output to 1.27M rows that way.
- Duplicate detection runs **before** reshaping so the error message is
  actionable
- Negative value added preserved and reported, never clipped
- Six suppression/nil glyph families handled including Greek chi (U+03C7) and
  full-width Ｘ (U+FF38)

Reference vocabularies built: 47 prefectures with JIS X 0401 codes, 24 JSIC
2-digit industry codes, a measure-name map, and NFKC-based name normalisation
that strips a trailing 都/府/県 without ever collapsing 東京特別区 onto 東京.

### 2.3 Self-test designed and run

Built `_synthetic_payload()`, a miniature e-Stat response exercising every trap:
Greek chi, full-width Ｘ, `***`, a negative value, a designated city, an
other-year national row, a prefecture with a 県 suffix, and one combination
deleted entirely.

16 assertions, all passing on first run. Fixture written to the session
scratchpad and deleted in a `finally` block.

### 2.4 Contamination check

Verified `raw_data/` and `processed_data/` were still empty and the scratchpad
fixture was gone. Confirmed no test artifact reached the project data
directories.

### 2.5 Documentation written

| File | Content |
|---|---|
| `docs/reference-years.md` | the correction, with METI quotes |
| `docs/acquisition-log.md` | network diagnosis, table identity, evidence classes |
| `docs/data-availability.md` | per-year status, mostly "unverified" |
| `docs/variable-definitions.md` | definitions, the two VA formulas, filtering rules |
| `README.md` | status, limitations, layout, e-Stat attribution |

### 2.6 Bug fixed before it could bite

`fetch_estat.py` referenced `urllib.error.HTTPError` while importing only
`urllib.request` and `urllib.parse`. CPython happens to make `urllib.error`
reachable as a side effect, but that is fragile. Added the explicit import.

### 2.7 Error paths tested

| Scenario | Result |
|---|---|
| No `ESTAT_APP_ID` | clean registration guidance, exit 2 |
| Bad `ESTAT_APP_ID` | surfaces `STATUS=100` and the Japanese message, exit 2 |
| Validator with no raw data | prints the exact fetch command to run, exit 2 |

The bad-key test proved the whole request path worked end to end and needed only
a valid credential.

### 2.8 Handed the blocker to the user

Reported that registration was required, explained the appId issuance form, and
explained why `https://example.com` is the right placeholder URL (IANA-reserved
under RFC 2606, so it cannot accidentally point at a real third party's site,
and the form rejects localhost).

---

## Part 3 — Acquisition (post-credential)

### 3.1 Discovery

`fetch_estat.py discover` returned **661** Census of Manufacture tables, written
to `metadata/estat_table_index.csv` with the raw response preserved.

### 3.2 Credential leakage check

Grepped the saved raw response for the key prefix. **Not present.** e-Stat does
not echo the appId, so the discovery artifact is safe to keep in the repository.

### 3.3 A conflict that had to be resolved, not chosen

`getStatsList` reports `SURVEY_DATE = 201901-201912` for the ２０１９年確報.
Taken at face value this says reference year 2019, **directly contradicting**
METI and my §1.5 inference.

I did not pick a side. Resolved it with evidence, in three steps.

**Step A — dimension metadata.** Fetched `getMetaInfo` for `0003432907`
(2019年確報) and `0003448119` (2020年確報):

| Table | National area rows |
|---|---|
| ２０１９年確報 | 2014, 2015, 2016, 2017 + unmarked `全国計` |
| ２０２０年確報 | 2015, 2016, 2017, 2018, **`全国計(2019年)` explicit** |

The 2020 survey has **no unmarked row** — its current year is labelled outright
as 2019. That alone implies survey year 2020 → reference year 2019.

**Step B — numerical identity.** Queried 製造品出荷額等 for the national rows of
both tables:

| Row | Value (百万円) |
|---|---|
| ２０１９年確報 `全国計` (unmarked) | **331,809,377** |
| ２０２０年確報 `全国計(2018年)` | **331,809,377** |
| ２０１９年確報 `全国計(2017年)` | 319,035,840 |
| ２０２０年確報 `全国計(2017年)` | 319,035,840 |
| ２０２０年確報 `全国計(2019年)` | 322,533,418 |

Exact match. The 2019 survey's current row **is** 2018 data.

**Step C — third corroboration.** `getMetaInfo` on `0003325921` (平成29年確報)
showed national rows starting at `全国計(2012年)`, i.e. 2012–2015 plus current →
2016. Consistent with the same rule.

**Finding (verified-from-source):** e-Stat's `SURVEY_DATE` field is formulaic. It
encodes the survey year as a Jan–Dec span, which was correct while survey year
equalled reference year and has been **wrong for every survey since 2017**. This
is a second, independent trap the brief did not mention.

### 3.4 Dimension structure — a bug the brief would have caused

The brief's §2.8 implies a `tab` dimension for measures. There is none:

| Role | id | Name |
|---|---|---|
| Measures | `@cat01` | 確報（産業編）・集計項目(H25から) |
| Industry | `@cat02` | 産業中分類(コード付加) |
| Geography | `@area` | 都道府県及び東京特別区・政令指定都市(H29から) |

The measure dimension's name **contains 産業** (inside 産業編). My original role
detection tested for 産業 before testing for the measure markers, which would
have silently swapped measures and industries and produced a plausible-looking
but entirely wrong panel.

**Fixed:** reordered the role tests so measure detection (`集計項目`, `表章`,
`tab`) runs first, then area, then time, then industry. Added an explanatory
comment naming the trap.

**Also fixed:** rewrote the self-test fixture to use the real dimension ids and
names, so the test actually covers this rather than a simplified idealisation.
Self-test re-run: all 16 passing.

### 3.5 Downloads — first batch

| Ref year | Table | statsDataId | Cells |
|---|---|---|---|
| 2018 | 3-03 | `0003432909` | 18,250 |
| 2018 | 3-01 | `0003432907` | 10,950 |
| 2019 | 3-03 | `0003448121` | 16,273 |
| 2019 | 3-01 | `0003448119` | 10,853 |

All single-page, row counts matching the API's reported totals.

### 3.6 Measure mapping gap found

First validation run: all four slices produced 1,128 rows, 47 prefectures, 24
industries, 0 duplicates. But both 3-03 runs exited non-zero with
`missing_required_measures: ['establishments']`.

Cause: **table 3-03 has 10 measures, not 6 or 7.** It splits 事業所数 into four
size bands and adds 生産額:

```
事業所数[合計] / [従業者30人~99人] / [従業者100人~299人] / [従業者300人以上]
従業者数 · 現金給与総額 · 原材料使用額等 · 製造品出荷額等 · 生産額 · 付加価値額
```

**Correction 2 to the brief** (superseding my own §1.1 estimate of seven).

Also confirmed 3-03's value-added column is plain `付加価値額` with no blend
qualifier, i.e. the clean net measure the project wants.

### 3.7 Tooling accident — stdlib shadowing

While inspecting measure names, the script crashed with
`AttributeError: module 'inspect' has no attribute 'cleandoc'` from deep inside
numpy.

Cause: I had earlier written a scratchpad helper named `inspect.py`. Python puts
the script's directory first on `sys.path`, so my file shadowed the standard
library `inspect` module and broke numpy's import machinery.

**Fixed:** deleted all scratchpad `.py` files and `__pycache__`, and avoided
stdlib-colliding filenames thereafter. No project file was affected.

### 3.8 Measure mappings added, revalidation

Added the four size-band mappings with a comment noting the tilde arrives as
U+FF5E and NFKC-folds to ASCII `~`. Re-ran self-test (passing) and all four
slices (all exit 0).

### 3.9 Reconciliation results — transformed

| Slice | establishments | employment | shipments | value added |
|---|---|---|---|---|
| 2018 3-01 | 0.0000% | 0.0000% | −0.0239% | −0.0317% |
| 2018 3-03 | 0.0000% | 0.0000% | −1.4169% | −0.9086% |
| 2019 3-01 | 0.0000% | 0.0000% | −0.0430% | −0.0289% |
| 2019 3-03 | 0.0000% | 0.0000% | −1.7076% | −0.5862% |

Counts reconcile exactly because they are never suppressed. Monetary gaps are
negative and their magnitude tracks the suppressed-cell count — the signature of
correct suppression handling.

**Finding:** suppression is **3.5× heavier in 3-03 than 3-01** (101 vs 29
suppressed value-added cells for 2018). The brief recommends 3-03 for its clean
net measure but does not price this cost, and suppression concentrates in exactly
the thin cells a location quotient depends on. Logged as an open question rather
than silently overriding the brief.

**Negative value added** found and preserved, always in
石油製品・石炭製品製造業: 愛媛 −4,283 and 和歌山 −26,435 百万円. This is the
legitimate depreciation-exceeds-margin case the brief anticipated.

### 3.10 Missing-cell investigation

Exactly 47 absent rows in the 2019 3-03 slice looked like a whole industry
dropping out. Investigated: it is coincidental. The missing cells scatter across
25 prefectures and concentrate in thin industries — 石油製品・石炭製品 (18) and
なめし革 (13). This is the non-random missingness the brief warned about, and it
confirms the flag distinction is doing real work.

---

## Part 4 — Extending backwards

### 4.1 Metadata for the 2014 and 2016 candidates

`getMetaInfo` on `0003144102` (平成26年確報) and `0003325921` (平成29年確報).

`0003325921` is a direct structural match to the later 地域別 tables. Downloaded
as reference year 2016.

`0003144102` is **not the same table lineage**. Its title is 市区町村編
(municipality edition), it has 69 areas rather than 73, 10 different measures,
and a `@time` dimension listing 2010–2014.

**Confirms the brief's warning** that the 3-0N numbering does not carry backwards
across the 2017 redesign.

### 4.2 Time-dimension support added

The `@time` dimension meant every prefecture × industry × measure key appeared
once per year, which would trip the duplicate check. Added year selection to
`build_panel()` that runs before all other filtering, records available years in
the report, and raises if the requested year is absent.

### 4.3 Downloads — second batch

Downloaded `0003325921` (ref 2016) and `0003144102` four times (once per year).
The repeated identical requests were slow, roughly two minutes each, and ran in
the background.

### 4.4 The pre-2017 lineage reports GROSS value added

Measure list for `0003144102`:

```
事業所数[計] / [内従業者30人~299人] / [内従業者300人以上]
従業者数 · 現金給与総額 · 原材料使用額等 · 製造品出荷額等
製造品出荷額等[内その他収入額] · 粗付加価値額 · 有形固定資産年末現在高(従業者30人以上)
```

**Finding (verified-from-source):** it carries **粗付加価値額 (gross)** and no
net 付加価値額 column at all. Joining it to the post-2016 tables on a single
`value_added` column would silently splice a gross series onto a net one.

**Handled:** mapped to a separate `gross_value_added` column so `value_added` is
correctly reported missing for that lineage, making the incompatibility loud
rather than invisible.

### 4.5 LQ break test written and run

Wrote `src/lq_break_test.py`. Removed a dead `pd.np.log` expression left in a
`if False` branch before running.

Method: LQ as a ratio of employment shares, computed on the panel's own totals
rather than the published national row, so numerator and denominator share
identical coverage. Compared reference year 2014 against 2016, pooled and
per-industry.

| Statistic | Value |
|---|---|
| Pairs compared | 1,120 of 1,128 |
| Pooled Spearman ρ | **0.9869** |
| Per-industry median ρ | **0.9825** |
| Min / max ρ | 0.9460 / 0.9966 |
| ρ > 0.95 | 22 of 24 industries |
| ρ < 0.90 | 0 of 24 |
| National employment change | +2.27% |

**Verdict: the location quotient survives the break. H1 gets eight observations,
not four.**

Weakest industries: その他の製造業 (0.9460) and なめし革 (0.9474), both small,
heterogeneous and owner-manager dense — where 有給役員 density is highest. The
predicted mechanism appearing where theory says it should.

Caveats recorded: the test measures ordering, not levels, so it does not license
pooling LQ levels without a block dummy. The +2.27% national change is far
smaller than the brief's §2.4 prefecture figures (Ishikawa +6.8%) because those
compare CoM-2017 against Economic-Census-2016, a different and noisier contrast.

### 4.6 Net value added located for the older block

Searched the 661-table index for pre-2017 prefecture tables carrying value added.
Found the 産業編 従業者30人以上 lineage:

| Ref year | Label | Table no | statsDataId |
|---|---|---|---|
| 2010 | 平成22年確報 | 3-10 | `0003094711` |
| 2012 | 平成24年確報 | 3-10 | `0003097830` |
| 2013 | 平成25年確報 | 2-10 | `0003127834` |
| 2014 | 平成26年確報 | 2-10 | `0003144079` |

Note the table number differs by year, so it cannot be templated. Not downloaded;
schemas unverified.

### 4.7 Downloads — third batch

Downloaded and validated reference year 2016 table 3-03 (`0003325923`) and both
2017 tables (`0003389992`, `0003389994`), completing the clean 2016–2019
net-value-added run.

---

## Part 5 — An error I made and corrected

### 5.1 Detection

A cross-slice summary showed the 2010, 2012 and 2013 municipality slices with
**zero measure columns**, while 2014 had all ten. Same table, same code.

### 5.2 Diagnosis

Inspected cell counts per year inside `0003144102`:

| Year | Cells | Areas |
|---|---|---|
| 2010 | 250 | 1 (全国) |
| 2011 | 250 | 1 (全国) |
| 2012 | 250 | 1 (全国) |
| 2013 | 250 | 1 (全国) |
| **2014** | **17,250** | **69** |

**The table advertises five reference years but carries prefecture-level detail
for 2014 only.** The earlier years exist solely as single national comparison
rows.

My §4.3 assumption that one download covered four usable years was **wrong**, and
I had written that claim into the availability matrix.

### 5.3 Why it was dangerous

Selecting 2010 produced a structurally valid 1,128-row grid with 47 prefectures
and 24 industries and zero duplicates — passing every headline check — while
containing no data whatsoever. Exactly the "plausible-looking CSV that silently
poisons everything downstream" the brief's Rule 1 warns about.

### 5.4 Fixes applied

1. **Guard added** to `build_panel()`: raises before writing when no measure
   survives filtering, with a diagnostic naming the likely cause and listing the
   area items actually seen. Verified it now fires for 2010 and that 2014 still
   validates.
2. **Deleted** the three empty CSVs and their validation reports.
3. **Deleted** the duplicate raw copies in `raw_data/manufacturing/{2010,2012,2013}/`
   that implied data which does not exist.
4. **Corrected** the availability matrix with the per-year cell-count table.
5. **Logged** the correction explicitly in `docs/acquisition-log.md` rather than
   quietly fixing it.

**The LQ break test is unaffected** — it uses 2014 and 2016, both of which have
genuine prefecture detail.

---

## Part 6 — Final verification

| Check | Result |
|---|---|
| Validator self-test | 16/16 passing |
| LQ break test reproduces | ρ = 0.9869, same verdict |
| Spot check: Aichi 輸送用機械器具, 2019, 30+ | 304,772 persons engaged, 5,962,731 百万円 VA |
| Derived productivity | 19.6 million yen per worker (≈ USD 130k) — plausible for Toyota's home prefecture |
| Scratchpad cleaned | all helper scripts and `__pycache__` removed |
| Credential in project files | none |

### Final validation table — all nine slices

| Slice | Rows | Pref | Ind | Dup | VA ok | suppressed | missing | VA recon gap |
|---|---|---|---|---|---|---|---|---|
| 2014 muni 3-01 | 1128 | 47 | 24 | 0 | 1093\* | 28 | 7 | — |
| 2016 3-01 | 1128 | 47 | 24 | 0 | 1091 | 29 | 8 | −0.0510% |
| 2016 3-03 | 1128 | 47 | 24 | 0 | 975 | 109 | 44 | −0.5647% |
| 2017 3-01 | 1128 | 47 | 24 | 0 | 1095 | 24 | 9 | −0.0306% |
| 2017 3-03 | 1128 | 47 | 24 | 0 | 987 | 98 | 43 | −0.6599% |
| 2018 3-01 | 1128 | 47 | 24 | 0 | 1092 | 29 | 7 | −0.0317% |
| 2018 3-03 | 1128 | 47 | 24 | 0 | 983 | 101 | 44 | −0.9086% |
| 2019 3-01 | 1128 | 47 | 24 | 0 | 1093 | 25 | 10 | −0.0289% |
| 2019 3-03 | 1128 | 47 | 24 | 0 | 976 | 105 | 47 | −0.5862% |

\* 2014 figures are `gross_value_added`, not net. Not comparable to the rest.

---

## Part 7 — Artifact inventory (end of Session 01)

### Created — code

| File | Purpose |
|---|---|
| `src/fetch_estat.py` | e-Stat API client: discover / meta / data |
| `src/validate_manufacturing.py` | cleaning, flagging, grid construction, validation, self-test |
| `src/lq_break_test.py` | LQ rank-stability test across the 2016 break |

### Created — documentation

| File | Purpose |
|---|---|
| `README.md` | status, getting started, measurement, limitations, attribution |
| `docs/reference-years.md` | the year correction with three independent proofs |
| `docs/acquisition-log.md` | chronological log with evidence classes |
| `docs/data-availability.md` | per-reference-year status and table IDs |
| `docs/variable-definitions.md` | definitions, VA formulas, filtering, conventions |
| `docs/work-log.md` | this file |

### Created — data

- `raw_data/manufacturing/{2014,2016,2017,2018,2019}/` — 9 raw API pages plus 9 manifests
- `processed_data/` — 9 validated CSVs
- `metadata/estat_table_index.csv` + `estat_statslist_raw.json` — 661-table index
- `metadata/meta/getMetaInfo_*.json` — 4 dimension metadata captures
- `metadata/validation_*.json` — 9 validation reports
- `metadata/lq_break_test.json` — LQ test output

### Deleted (deliberately)

- `processed_data/manufacturing_{2010,2012,2013}_tablemuni3-01.csv` — all-NaN
- `metadata/validation_{2010,2012,2013}_tablemuni3-01.json`
- `raw_data/manufacturing/{2010,2012,2013}/` — duplicate copies implying absent data
- all scratchpad helper scripts and `__pycache__`

---

## Part 8 — Corrections to the handoff brief

| # | Brief said | Actually |
|---|---|---|
| 1 | Download `0003432909`, emit `manufacturing_2019.csv` | Those IDs are reference year **2018**. Proven by exact numerical identity. |
| 2 | Table 3-01 schema: 6 measures, `tab` dimension | No `tab` dimension. Measures are `@cat01`, industry `@cat02`. The measure name contains 産業 and will swap the two if matched naively. |
| 3 | (3-03 implied same 6 measures) | 3-03 has **10** measures: four 事業所数 size bands plus 生産額. |
| 4 | (not mentioned) | e-Stat's `SURVEY_DATE` field is **wrong for every survey from 2017 onward**. |
| 5 | Prefer 3-03 for clean net VA | Correct, but 3-03 suppresses **3.5×** more value-added cells, concentrated in the thin cells LQ depends on. Trade-off unpriced. |
| 6 | (not mentioned) | After 2016 the dependent variable divides CY-T value added by a 1-June-T+1 headcount. A structural numerator/denominator misalignment, not just a labelling issue. |
| 7 | (not mentioned) | The pre-2017 市区町村編 lineage carries **gross** value added only. |
| 8 | §2.2 mapping, §2.8 area/industry traps, suppression glyphs, JSIC structure | **All confirmed correct.** |

---

## Part 9 — State at the end of Session 01

**Open questions carried forward:**

1. **Which table is primary for value added?** 3-03 gives clean net VA but
   suppresses 9% of cells against 2.6% for 3-01. Resolved in Session 02 — see
   §10.3.
2. **Reference year 2011** appears in the municipality time dimension but was
   never collected by a Census of Manufacture. Not verified; still do not use.

**The structural problem, stated plainly:** an excellent pipeline, nine validated
slices, and **zero analysis**. No chart, no regression, no stated finding. That
framed the whole of Session 02.

---

# SESSION 02 — scope reset and the analysis panel

---

## Part 10 — Advisory review and scope reset

### 10.1 The request

Asked for a brutally pragmatic assessment as a senior advisor, explicitly
optimising for recruiter value over academic completeness, with an instruction to
say directly if the project was being over-researched or over-engineered.

Two clarifying questions were asked before any recommendation:

| Question | Answer |
|---|---|
| Remaining effort budget | 3–5 sessions |
| Final artifact | Analysis notebook **and** Streamlit dashboard |

Both answers pointed the same way, so no further questions were needed.

### 10.2 The diagnosis

Three stages in (1.1 research, 1.2 framework, Session 01 acquisition) with no
analytical output. A hiring manager gives a portfolio project roughly 90 seconds
and there was nothing to look at.

**The survey-redesign discovery was being over-weighted.** Value added for year T
divided by a headcount taken five months after year T ends is a real mismatch,
but it applies identically to all 47 prefectures, so cross-sectional rankings
barely move and it largely cancels in growth rates. Downgraded from a workstream
to one README paragraph.

### 10.3 Decisions taken

**Cut entirely:** Economic Structure Survey 2021–2023; Economic Census years
2011/2015/2020; municipality data; 4-digit JSIC; robot density; port
infrastructure; the Labour Force Survey.

**Reversed the Session 01 recommendation on the primary table.** Table 3-01 (4+)
becomes primary, 3-03 (30+) becomes a robustness check:

| | 3-01 (4+) | 3-03 (30+) |
|---|---|---|
| Suppressed VA cells | 25–29 (~2.5%) | 98–109 (~9%) |
| Establishments | ~182k | ~46k |
| VA definition | blended | clean net |

Suppression in 3-03 concentrates in thin prefecture × industry cells — exactly
what LQ needs. The blend bias in 3-01 affects levels, is stable year to year, and
is absorbed by prefecture fixed effects.

**Two-tier panel architecture.** `prefecture × industry × year` is an
intermediate used only to compute LQ and diversity. `prefecture × year`
(47 × 4 = 188 rows) is the analysis unit.

**Labour Force Survey deleted as a dependency.** Manufacturing employment share
needs a denominator; instead of the LFS model estimates (published as 参考
reference values with large prefecture-level sampling error), use working-age
population from the population pull:
`mfg_intensity = manufacturing_employment / working_age_population`.

**Name:** drop "Atlas" — it names a format rather than a finding and promises map
coverage the project will not deliver. Proposed *The Specialization Trade-off:
Manufacturing Productivity Across Japan's 47 Prefectures*, to be finalised only
after results are known.

### 10.4 Plan written and approved

Plan file written to `~/.claude/plans/`, reviewed, and approved without changes.

---

## Part 11 — Building the prefecture-year panel

### 11.1 `src/build_panel.py` written

Imports `load_pages`, `classify_value`, `normalise_pref_name`, `parse_industry`,
`normalise_measure_name`, `MEASURE_MAP`, `PREFECTURES`, `PREF_NAME_TO_CODE` and
`TOTAL_INDUSTRY_CODE` from `validate_manufacturing.py` rather than duplicating
any parsing logic.

### 11.2 The 【00】製造業計 design decision

`validate_manufacturing.py` deliberately excludes industry code `00` because it
is a total, not an industry. But **summing the 24 industries understates a
prefecture**, because confidentiality-suppressed cells drop out of the sum. The
`【00】` row carries the true total including those establishments.

So the builder takes two different things from two different places:

| Quantity | Source | Why |
|---|---|---|
| `value_added_total`, `employment_total`, `establishments_total` | the `【00】` row, read from raw JSON | includes suppressed cells |
| industry shares for LQ and HHI | the 24 validated industry rows | shares must sum to 1 |

### 11.3 First run

188 rows, 9 validation checks passing: row count, 47 prefectures per year, 4
distinct years, no duplicate prefecture-year, no nulls in `va_per_worker`,
strictly positive productivity, HHI bounded in (0, 1], positive `lq_top`, and
coverage never exceeding 100.5%.

### 11.4 My prediction was wrong

The approved plan predicted "Aichi at the top." It is **7th of 47**. Top five for
reference year 2019, value added per worker in 百万円:

| Prefecture | VA/worker | Top industry | LQ |
|---|---|---|---|
| 山口 | 20.33 | 化学工業 | 3.23 |
| 徳島 | 18.41 | 電子部品・デバイス | 3.55 |
| 滋賀 | 17.78 | プラスチック製品 | 1.69 |
| 茨城 | 15.47 | 食料品 | 1.07 |
| 京都 | 15.23 | 食料品 | 1.04 |

Aichi holds **12.8% of national value added** but ranks 7th on productivity.
Tokyo ranks 27th, Osaka 22nd, Kumamoto 34th. Scale is not productivity — a
finding in its own right, and the seed of the eventual narrative.

Distribution for 2019: mean 12.24, median 11.95, sd 2.80, range 6.93–20.33.

### 11.5 Cross-check that the 【00】 row was actually used

| Prefecture | `【00】` row | Summed industries | Coverage |
|---|---|---|---|
| 愛知 | 12,810,137 | 12,810,139 | 100.000% |
| 東京 | 2,816,070 | 2,816,072 | 100.000% |

A 2 百万円 difference out of 12.8 trillion is rounding in the published figures.
Both prefectures have **zero** suppressed cells, so this confirmed correctness but
not benefit.

### 11.6 Quantifying the benefit

Checked the prefectures that **do** have suppressed cells:

| Prefecture | Suppressed | Understated by |
|---|---|---|
| 高知 | 3 | 1.54% |
| 長崎 | 2 | 1.07% |
| 沖縄 | 2 | 0.68% |
| 奈良 | 2 | 0.46% |
| 愛知 | 0 | 0.00% |

Nationally 28,992 百万円 recovered. Small in absolute terms, but **the bias is
concentrated in small prefectures** — precisely those at the bottom of the
productivity distribution. Summing would have systematically tilted any
regression of productivity on size or specialization.

---

## Part 12 — Population (the stretch goal)

### 12.1 `fetch_estat.py` extended

Three backwards-compatible additions:

- `discover --stats-code` (defaults to the Census of Manufacture)
- `discover --search-word` for API-side keyword filtering
- `data --dest-dir` to write outside `raw_data/manufacturing/<year>/`

Index output is suffixed by statsCode so the manufacturing index is not
overwritten.

### 12.2 Discovery

`discover --stats-code 00200524` (人口推計) returned **420** tables.

### 12.3 Table selection, with reasoning

Filtered to prefecture × age-band tables. Two serious candidates:

| statsDataId | Series | Note |
|---|---|---|
| `0003448225` | 令和2年国勢調査基準 estimates | projected forward from the 2020 census |
| **`0004021110`** | **国勢調査結果による補間補正人口** | **intercensal, reconciled between censuses** |

Chose `0004021110`. The analysis window 2016–2019 sits **between** the 2015 and
2020 censuses, so the intercensal adjusted series is benchmarked against both
rather than projected from one. 8,640 cells, as of 1 October each year.

Metadata confirmed the dimensions: `@cat01` 男女別, `@cat02` 総人口 vs 日本人人口,
`@cat03` 年齢3区分 (総数 / 15歳未満 / 15～64歳 / 65歳以上), `@area` 48 items,
`@time` 2016–2019 plus one more.

Filtered to 男女計 and 総人口, dropping 日本人人口.

Age bands are matched **by name, not by code**, because e-Stat's age-band codes
are neither ordered nor stable across tables (`008` is 15歳未満 while `002` is
15～64歳).

### 12.4 Loader and join

`load_population()` added to `build_panel.py`. The join asserts the row count is
unchanged, so a many-to-one mismatch fails loudly rather than silently
duplicating rows. Three validation checks added: population present on every row,
aging ratio within (0.1, 0.5), and age bands summing to the total within 0.5%.

### 12.5 Unit bug found and fixed

First joined run produced `mfg_intensity` values like 181.59 for Aichi. Tokyo's
`pop_total` read 14,007.

The source publishes in **千人 (thousands of persons)**. Verified from the source
rather than inferred: every cell carries `@unit='千人'`, the `tab` class declares
`"@unit":"千人"`, and the national row reads 127,042 — Japan's 127.0 million.

Taken at face value this made `mfg_intensity` wrong by a factor of 1000. The
loader now multiplies by 1000 **and asserts the unit is 千人**, so a future
vintage published in different units fails loudly instead of silently rescaling.

After the fix: Tokyo 14,007,000 people and 2.7% manufacturing intensity; Aichi
7,557,000 and 18.2%. Aging ratio ranges from 0.221 (沖縄) to 0.368 (秋田).

### 12.6 Second stdlib-shadowing accident

A scratchpad helper named `signal.py` shadowed the standard library `signal`
module, which `pyarrow` imports, producing a misleading
`partially initialized module 'pandas' has no attribute 'read_csv'` error.

Same class of bug as the `inspect.py` incident in §3.7. Cleared the scratchpad
and adopted a `zz_` filename prefix. A related PowerShell quoting failure while
combining the cleanup and heredoc in one command was resolved by splitting them
into separate calls and using the Write tool for the script.

---

## Part 13 — Signal preview, and why it matters

Run **only** to confirm the panel was not inert. Not the analysis. Bivariate
correlations against `va_per_worker`, reference year 2019, n = 47:

| Relationship | Pearson | Spearman | p |
|---|---|---|---|
| H1: LQ of top industry | −0.082 | −0.194 | 0.584 |
| H1b: HHI concentration | **−0.300** | −0.288 | **0.040** |
| H2: aging ratio (level) | −0.142 | −0.311 | 0.341 |
| H2: aging(2016) vs VA/worker CAGR 2016–19 | **+0.274** | — | 0.062 |
| H3: HHI(2016) vs growth volatility | −0.027 | — | 0.856 |

National value added per worker CAGR 2016–2019: **+0.34%**.

**All three hypotheses fail or reverse as stated.** Concentration is associated
with *lower* productivity; more-aged prefectures grew *faster*; diversity shows no
relationship with stability.

### H1 is mis-specified, not refuted

The productivity leaders (Yamaguchi chemicals, Tokushima electronics, Shiga
plastics) lead because they are specialized in **capital-intensive** industries,
not because agglomeration works. At prefecture level, LQ conflates *specialized*
with *specialized in what*.

**The correct test is at prefecture × industry level**, using the 4,512-row
intermediate: regress log value added per worker for industry *i* in prefecture
*p* on LQ(p,i) with **industry fixed effects**. Industry FE absorbs "chemicals is
capital-intensive" and isolates the agglomeration effect, with 1,128 observations
per year instead of 47.

This changes the approved plan in one respect: the intermediate table becomes an
analysis unit for H1, not merely a feeder for LQ.

### H3 now requires the older years

Volatility computed from three growth observations is too noisy to test anything.
The 2010–2014 extension moves from **optional** to **required** if H3 is to be
tested at all.

---

## Part 14 — Artifact inventory, Session 02

### Created

| Path | Purpose |
|---|---|
| `src/build_panel.py` | prefecture-year panel builder with population join |
| `processed_data/panel_prefecture_year.csv` | **the deliverable** — 188 rows × 22 cols |
| `raw_data/population/` | 1 raw page + manifest, statsDataId `0004021110` |
| `metadata/estat_table_index_00200524.csv` | 420-table population index |
| `metadata/estat_statslist_raw_00200524.json` | raw discovery response |
| `metadata/meta/getMetaInfo_0004021110.json` | population dimension metadata |
| `~/.claude/plans/…md` | the approved scope-reset plan |

### Modified

| Path | Change |
|---|---|
| `src/fetch_estat.py` | `--stats-code`, `--search-word`, `--dest-dir` |
| `README.md` | status rewritten around the panel; population sourcing documented |
| `docs/acquisition-log.md` | Session 02 section, unit bug, signal preview |
| `docs/work-log.md` | this file |

### Panel schema (22 columns)

```
year, prefecture_code, prefecture_name,
value_added_total, employment_total, establishments_total,   # from 【00】
va_per_worker, hhi_employment, lq_max,
top_industry_code, top_industry_name, lq_top,
n_industries_present, suppressed_cells, va_coverage_pct,     # data quality
pop_total, pop_under15, pop_15_64, pop_65plus,
aging_ratio, working_age_share, mfg_intensity
```

### Regression suite, re-run at session end

| Check | Result |
|---|---|
| `validate_manufacturing.py --self-test` | 16/16 passing |
| `lq_break_test.py` | ρ = 0.9869, verdict unchanged |
| `build_panel.py` | 188 rows, 12/12 checks passing |
| Scratchpad and `__pycache__` | cleaned |
| API key in project files | none |

---

## Part 15 — Consolidated open questions and next steps

### Open questions

1. **Reference year 2011** appears in the municipality time dimension but was
   never collected by a Census of Manufacture. Unverified; do not use.
2. **Does H1 survive industry fixed effects?** The single most important
   unanswered question. If it does not, the project's narrative changes from
   "specialization pays" to "industry mix explains almost everything," which is
   still a publishable finding.
3. **Final project name** — hold until session 3 results are known.

### Next steps, in priority order

1. **`notebooks/01_analysis.ipynb`** — H1 at prefecture × industry level with
   industry fixed effects, H2 and H3 at prefecture level, 5–6 charts. Load the
   `dataviz` skill before writing any chart code.
2. **Extend the panel to reference years 2010–2014** via the 産業編 30+ tables
   (`0003094711`, `0003097830`, `0003127834`, `0003144079` — numbering differs
   per year, each needs a `meta` call first). Now required for H3.
3. **`app.py`** Streamlit dashboard — load `developing-with-streamlit`.
4. **README rewritten around findings**, led by the reference-year catch.

### Explicitly out of scope

Economic Census years 2011/2015/2020 · Economic Structure Survey 2021–2023 ·
municipality data · 4-digit JSIC · robot density · port infrastructure ·
Labour Force Survey.

---

# SESSION 03 — first analytical deliverable

---

## Part 16 — EDA notebook and four charts

**Goal:** move the project from "data preparation" to "data analysis" by producing
artifacts a recruiter can actually look at. No regressions.

### 16.1 Toolchain

`matplotlib` 3.10.5 and `pandas` 2.2.3 were present; `nbformat`/`nbconvert` were
not and were installed. The notebook is generated with `nbformat` and executed
with `nbconvert --execute --inplace`, so outputs are embedded and it renders on
GitHub without anyone running it.

### 16.2 Palette, validated not eyeballed

Two series colors, checked with the data-viz validator under `--pairs all` on the
light surface (`#fcfcfb`):

| Pair | CVD ΔE | Normal-vision ΔE | Contrast |
|---|---|---|---|
| blue `#2a78d6` ↔ orange `#eb6834` | 24.7 (protan) | 33.6 | both ≥ 3:1 — PASS |

A third slot (aqua `#1baf7a`) passed separation but sat at **2.74:1** contrast,
which triggers a relief obligation. Dropped rather than accepted — two colors plus
a recessive gray covers all four charts.

Encoding convention held across every chart: **blue = the data, orange = the
subject of the chart's question, gray = context.**

The validator ships as an ES module with a `.js` extension and its CLI guard
requires that exact filename, so it was run from a scratch directory containing a
`package.json` declaring `{"type": "module"}`.

### 16.3 Romanised labels

All prefecture and industry labels are romanised via `src/viz_style.py`. Two
reasons: the audience is English-reading, and it removes any dependency on a CJK
font being installed on the rendering machine.

### 16.4 Charts, and the defects found by looking at them

Four PNGs in `outputs/charts/`. Rendering them and inspecting caught three
defects that no validator would have:

1. **Title/subtitle collision on all four charts.** `axes.titlepad` was 14pt while
   the deck line sits at 1.02 axes fraction and is ~9.5pt tall. Fixed by raising
   titlepad to 32.
2. **Chart 1's median reference label** first sat below the bars (clipped), then
   above the axes (colliding with the deck line). Parked in the bottom margin with
   an expanded y-limit.
3. **A wrong calculation in the notebook.** Recovered value added was computed as
   `total × (1 − mean(coverage_pct)/100)`, averaging ratios across differently-sized
   prefectures. It printed **112,746** million yen against the correct **28,992**.
   Caught because the correct figure had been computed independently in Session 02.
   Now summed per prefecture.

Chart 4 uses a **zero-baseline** y-axis deliberately: the question is whether
productivity is stagnant, and a truncated axis would manufacture a trend.

### 16.5 Findings — all numbers independently re-verified

| Claim | Verified |
|---|---|
| National VA/worker 2016 → 2019 | 12.86 → 12.99, CAGR **+0.34%** |
| Aichi share of national value added | **12.78%** |
| Aichi productivity rank | **7 of 47** |
| Prefecture spread (max/min) | **2.93×** |
| **Industry spread (max/min)** | **5.90×** |
| Ratio of the two | **2.01×** |
| HHI vs productivity | r = −0.300, p = 0.040 |
| LQ of largest industry vs productivity | r = −0.082, p = 0.584 |
| Aging(2016) vs growth 2016–19 | r = +0.274, p = 0.062 |
| Prefectures with suppressed cells | 11 of 47 |

**The surprise: industry mix spans twice the range that geography does.** National
value added per worker varies 5.90× between the 24 JSIC divisions but only 2.93×
between the 47 prefectures.

That single fact explains why both specialization hypotheses came out backwards.
The prefecture-level concentration measure confounds *how* specialized a region is
with *what it is specialized in*; the most concentrated prefectures are often rural
and food-dominated. H1 has not been refuted, it has not yet been tested.

### 16.6 Artifacts

| Path | Purpose |
|---|---|
| `notebooks/01_exploratory_analysis.ipynb` | 21 cells, 6 sections, executed with outputs embedded |
| `outputs/charts/chart1_top15_productivity.png` | Top 15, Aichi highlighted |
| `outputs/charts/chart2_hhi_vs_productivity.png` | concentration vs productivity |
| `outputs/charts/chart3_aging_vs_growth.png` | aging vs productivity growth |
| `outputs/charts/chart4_national_trend.png` | national trend, zero-baseline |
| `outputs/findings_v1.md` | one page, 4 findings |
| `src/viz_style.py` | palette, romaji maps, matplotlib defaults |

### 16.7 Open question promoted

The project's question moves from *"does specialization pay?"* to **"how much of
regional productivity is just industry mix?"** The next step is the
prefecture × industry regression with industry fixed effects — 1,128 observations
per year rather than 47.

---

# SESSION 04 — geography or industry composition?

---

## Part 17 — Answering the A-vs-B question

**Objective:** determine whether productivity differences are driven by regional
characteristics (A) or industry composition (B). Descriptive only, no regressions.

### 17.1 The question turned out to have two correct answers

| Level | Method | Answer |
|---|---|---|
| Cell | variance decomposition | **industry** — 51.6% vs 15.0% |
| Aggregate | shift-share | **within-industry (regional)** — 2.56× the mix effect |

Both hold. Industry identity predicts whether a given prefecture × industry cell is
productive, but prefectures are too diversified (HHI 0.06–0.25) for that to carry
through to their aggregates. The mix effect is damped by diversification; the
within-industry effect passes through undamped.

### 17.2 Session 03's headline was wrong, and this session corrected it

Session 03 compared **5.90×** (spread of industry means) against **2.93×** (spread of
prefecture aggregates) and concluded industry mattered twice as much. Invalid: a
prefecture aggregate is an employment-weighted average over 24 industries and is
mechanically compressed, so the two dispersions sit at different levels of
aggregation.

Like-for-like, within-industry spread across prefectures is **6.62×** against the
**5.90×** between-industry span. Regional and industry effects are comparable, with
regional slightly larger. The user approved correcting this rather than preserving
the original wording.

### 17.3 `src/shift_share.py` — and a diagnosis I had to correct mid-session

Decomposition: `mix = Σ(s_pi − s_Ni)·π_Ni`, `within = Σ s_pi·(π_pi − π_Ni)`,
with `gap = mix + within` exactly.

During planning a first attempt left a **residual of 1.37**. My initial diagnosis was
"national shares reindexed onto a subset no longer sum to 1." **That diagnosis was
wrong**, and the self-test proved it: a regression guard built on that theory passed
when it should have failed, because expanding the two terms shows the identity holds
against `Σ s_Ni·π_Ni` *whatever* those shares sum to.

The real cause: measuring the gap against the **global** national productivity while
decomposing over a prefecture's surviving industry subset. Two different benchmarks,
silently differenced. The module now returns `benchmark` explicitly so it is
inspectable, and asserts the identity per prefecture (achieved 4e-15).

The self-test fixture also had to be rebuilt. The first version assumed national
rates of 10 and 20, but national rates are derived *from* the fixture, so the deviant
prefecture dragged them off and three assertions failed. Fixed by adding symmetric
+20%/−20% prefectures whose deviations cancel, giving exact analytic expectations.
10 checks, all passing.

### 17.4 Results, independently re-verified

| Measure | Value |
|---|---|
| Between-industry span | 5.90× (petroleum 34.8 → leather 5.9) |
| Median within-industry spread | 6.62× (range 1.85× to 38.4×) |
| Industries exceeding the 5.90× span | 14 of 24 |
| sd(within)/sd(mix), 2019 | 2.56 |
| Same ratio, 2016–2018 | 2.42 / 2.30 / 2.51 — stable |
| Within-dominant prefectures | 36–37 of 47 in every year |
| Variance shares, industry / prefecture | 51.6% / 15.0% |
| Identity residual | ≤ 4.4e-15 in all four years |

Aichi's decomposition is the headline: gap +2.10 = mix **+0.42** + within **+1.69**.
It is productive because it is unusually good at making cars, not because cars are
lucrative. Tokyo is the only mix-driven case among the five.

### 17.5 Chart defects caught by looking at the renders

1. **Chart 6's legend sat on the Tokushima data**, placing the legend's own "Total
   gap" diamond beside Tokushima's real one. Moved to the upper-right quadrant,
   the only empty region given Aichi's short bars.
2. **Chart 7's national-average label rendered outside the axes** — boxplot
   positions run 1..n, so the y-coordinate of 0.3 fell below the bottom category.
   Moved above the top box with the limit widened.
3. Fixed a matplotlib 3.9 deprecation (`labels` → `tick_labels` on `boxplot`).

Chart 7 uses a **log x-axis**: within-industry spreads reach 38× and a linear axis
compressed the lower two-thirds into unreadability.

### 17.6 Artifacts

| Path | Purpose |
|---|---|
| `src/shift_share.py` | decomposition + variance shares, 10 self-tests |
| `notebooks/02_industry_mix_analysis.ipynb` | 18 cells, executed, 0 errors |
| `outputs/charts/chart5_industry_productivity.png` | 24 industries ranked |
| `outputs/charts/chart6_shift_share_decomposition.png` | mix vs within, 5 prefectures |
| `outputs/charts/chart7_within_industry_spread.png` | boxplots, log scale |
| `outputs/findings_v2.md` | 4 findings + the correction |
| `README_draft.md` | 4 sections, 6 one-sentence findings |

### 17.7 What this settles

Regional effects are real and large, so the planned fixed-effects design is
justified rather than speculative. H1 remains untested: the prefecture-level
measures confound *how* specialized a region is with *what it is specialized in*,
and only industry fixed effects separate them.

---

# SESSION 05 — conceptual reference

---

## Part 18 — `docs/concepts.md`

Documentation only. No analysis re-run, no finding changed.

### 18.1 What was built

A single reference covering ~45 concepts across six domains: measuring
productivity, regional and agglomeration economics, statistics and inference,
official statistics and data quality, manufacturing domain knowledge, and
visualization. Plus a concept → file/session index.

Each entry follows one shape: what it is in plain language, the equation as
**implemented** rather than as a textbook idealises it, a hand-checkable worked
example, and where the project used it. Project figures are marked **[real]** and
were re-verified from `processed_data/` before being written; teaching-only
examples are marked **[illustrative]** so they can never be mistaken for results.

### 18.2 A gap surfaced, not papered over

**Nothing in this project has been deflated for prices.** All value added is
nominal.

- Cross-sectional findings are **unaffected** — a single year shares one price
  level, so rankings, LQ, the shift-share and the 6.62× spread all stand.
- The **+0.34% growth figure is nominal growth.** Describing it as "productivity
  growth" without qualification overstates what was measured.

Four sessions had not raised this. It qualifies one finding rather than
invalidating any, and now appears in `docs/concepts.md` §1.5 and in the open
questions. Fixing it properly needs an industry-level output deflator.

### 18.3 Two stale documents corrected

`docs/variable-definitions.md` still carried pre-Session-02 facts:

1. It listed **3-03 as primary** and 3-01 as the robustness check. Session 02
   reversed this on suppression grounds (3-03 loses ~9% of value-added cells
   against ~2.5%, concentrated in the thin cells LQ depends on). Corrected, with
   the reasoning recorded so the reversal is not silently re-reversed later.
2. It said 3-03 has **seven** measures. It has **ten** — 生産額 plus four
   事業所数 size bands. The seven was an estimate made before `getMetaInfo` was
   downloaded; the metadata later contradicted it.

Both were written before the data existed and were never revisited. Worth noting
as a general hazard: documents drafted during planning drift out of step once the
data arrives.

### 18.4 Verification

Every project number in the document re-derived from source rather than copied
from notebooks or this log, including the location quotient worked example
(Aichi transport equipment, LQ = 2.71), the HHI figures, the shift-share
decomposition, and the CAGR. File paths and function names checked against the
repository.

### 18.5 Artifacts

| Path | Action |
|---|---|
| `docs/concepts.md` | created |
| `docs/variable-definitions.md` | primary/robustness roles and measure count corrected |
| `README_draft.md` | linked to the concepts document |

---

# SESSION 06 — testing three things the docs said were untestable

---

## Part 19 — Concept revisions, capital, and reference year 2020

The concepts document asserted three limitations without testing them. All three
turned out to be wrong or answerable.

### 19.1 "2021+ was cut for comparability" — wrong reason

The stated reason was that the Economic Structure Survey is sample-based and
excludes 個人経営. True, but **not the binding constraint**. Checked against the API,
its manufacturing tables (`0004048573/4/5`) have **no area dimension at all** — only
measures and a combined time × industry key. Prefecture-level output from that
survey exists solely for broad-division sales and wholesale/retail.

**Manufacturing value added by prefecture does not exist for 2021 onward.** The panel
ends at 2020 as a data limit, not a scope choice. A plausible explanation had been
recorded as a verified one.

### 19.2 Capital deepening — answerable, and the answer is a clean refutation

Capital stock **is** published: table 3-04, 有形固定資産額, prefecture × industry,
30+ employees. Downloaded for reference years 2016–2019 (`0003325924`,
`0003389995`, `0003432910`, `0003448122`), 1,128 validated rows each.

Tested as a chain, since both links must hold:

| Link | Result |
|---|---|
| aging(2016) → capital deepening | r = **+0.269**, p = 0.068 — holds |
| capital deepening → productivity growth | r = **+0.027**, p = 0.855 — **fails** |

Older regions did automate faster. Automating produced no measured productivity
gain. The mechanism fails at an identifiable step, which is a stronger result than a
weak overall correlation would have been.

Convergence is real (r = −0.310, p = 0.034) but does not absorb the aging effect
either: aging survives both controls on the 30+ basis (p = 0.025).

**And the result is coverage-dependent.** Identical specification, same prefectures,
same years: aging is significant on the 30+ basis (p = 0.032) and not on 4+
(p = 0.132). A single headline from one table would have been reported as settled.

### 19.3 Reference year 2020 — added, after a gate that passed perfectly

The 2021 Economic Census publishes by prefecture and carries **2019 alongside
2020**, so the two instruments could be compared **on the same year** rather than
across adjacent ones:

| Measure | Max abs diff, 2019 | Exact matches |
|---|---|---|
| Employment | 0 | 47 / 47 |
| Value added | 0 | 47 / 47 |
| Establishments | 0 | 47 / 47 |

The Economic Census **reproduces** the Census of Manufacture basis rather than
restating it. 2020 appended; panel now **235 rows** with an `instrument` column so
the sources can never be silently pooled. Location quotient and Herfindahl are
**null for 2020** — the Economic Census publishes employment only at prefecture
level, and a value-added analogue would be a different measure.

Notebooks 01 and 02 were pinned to `instrument == "CoM"` so their published findings
are unchanged; notebook 01's CAGR still reads +0.3390%. 2020 is the COVID year, and
a growth rate spanning it measures a shock.

### 19.4 Two bugs caught this session

**Label drift across survey years.** The same capital measures are spelled
`有形固定資産額[年末現在高]` in the 2017–2018 surveys and
`有形固定資産額[(A+B-E-F) 年末現在高]` from 2019. Identical quantities, different
strings. Left unmapped this returns **zero rows rather than raising**, and 2016 and
2017 silently produced nothing. Caught only by checking row counts per year.

**Closure late-binding in Chart 8.** Axis formatters written as
`lambda v, _: xf.format(v)` capture `xf` by reference and are evaluated at render
time, after the loop ends — so both panels took the *last* panel's formatters and
the aging **level** rendered as "+20%". Fixed by binding as a default argument.
Caught by looking at the rendered PNG.

### 19.5 Shift-share specification sensitivity, quantified

The credibility question was asked directly and split in two. The **bug** is a
non-issue: caught during planning, never reached a published number, now guarded by
an identity assertion. The **specification dependence** is a real limitation:

| Specification | sd(mix) | sd(within) | sd(interaction) | within-dominant |
|---|---|---|---|---|
| Two-way (shipped) | 0.867 | 2.215 | — | 37 / 47 |
| Three-way | 0.867 | 2.259 | **1.189** | 38 / 47 |

The headline survives, but the interaction carries ~28% of variation and the two-way
form folds it into "within". Yamaguchi's +4.97 is really +1.26 within and +3.71
interaction. Aichi's "80% from being good at it" is nearer half. Both §2.5 and the
Chart 6 reading were softened accordingly.

### 19.6 Artifacts

| Path | Action |
|---|---|
| `docs/concepts.md` | §1.2, §2.2, §2.5, §2.7, §2.8, §3.10, §4.1 rewritten |
| `src/shift_share.py` | unchanged; three-way run as a sensitivity check |
| `src/econ_census.py` | new — 2020 loader and comparability gate |
| `src/build_panel.py` | `instrument` column, 2020 append, generalised totals loader |
| `src/validate_manufacturing.py` | capital measures, both label spellings |
| `notebooks/03_capital_and_convergence.ipynb` | new, 17 cells, 0 errors |
| `outputs/charts/chart8_capital_deepening.png` | new |
| `outputs/findings_v3.md` | new |
| `docs/data-availability.md` | 2020, capital, 2021+ impossibility |

---

# SESSION 07 — removing the weak inference

---

## Part 20 — What was deleted and why

A robustness review found the project's statistical inference did not hold up, while
its data engineering did. Acting on that, everything resting on the three original
hypotheses was removed. **No version control existed and a snapshot was declined, so
these deletions are permanent.**

### 20.1 The finding that triggered it

Fifteen tests across H1, H2 and H3, all n = 47, no correction for multiple
comparisons. Seven reached nominal significance at 0.05. **None survived Bonferroni
(threshold 0.0033 against a best p of 0.0129) or Benjamini-Hochberg at q < 0.05.**

With 47 prefectures and a four-year window, this class of hypothesis testing cannot
separate signal from noise. The response was to withdraw the findings rather than
publish them with caveats.

### 20.2 Deleted

| Path | Reason |
|---|---|
| `outputs/findings_v1.md` | carried a **retracted claim as a live headline** — the 5.90× vs 2.93× comparison that v2 disproved, with no retraction notice |
| `outputs/findings_v2.md`, `findings_v3.md` | built on uncorrected p-values |
| `README.md` (old root) | stale: "Atlas" name, 188 rows, 3-03 described as primary |
| `notebooks/03_capital_and_convergence.ipynb` | entirely H2-driven regressions |
| `chart2_hhi_vs_productivity.png` | H1 significance test |
| `chart3_aging_vs_growth.png` | H2 significance test |
| `chart8_capital_deepening.png` | H2 significance test |

### 20.3 Revised, not deleted

**Notebook 01** — dropped 7 cells (aging analysis, specialization analysis, and the
invalid between-vs-within spread comparison). Kept data overview, distribution,
rankings and the national trend. Now 14 cells, 0 errors, charts 1 and 4.

**Notebook 02** — kept nearly whole; it is magnitude and decomposition work with no
p-values. Three cells reframed off the retired hypotheses. **One real accuracy defect
fixed:** it still claimed Aichi's advantage was "+1.69 from outperforming", which the
three-way decomposition had already shown overstates the case. Corrected to a fifth
mix, half within, a third interaction, with Yamaguchi's interaction-dominated split
shown alongside.

**`docs/measurement-framework.md`** — §3 rewritten to list only variables actually
built, recording that robot density and port infrastructure were dropped as
unobtainable and that the Labour Force Survey denominator was replaced. §4 replaced
with a retirement note explaining why each hypothesis failed and that power, not any
single hypothesis, was the underlying problem.

**`README_draft.md` → `README.md`** — promoted. Findings rewritten as six magnitudes
and decompositions that do not depend on a significance threshold, plus an explicit
note on statistical power.

**`docs/concepts.md`** — six dangling references repaired, §2.7 and §2.8 rewritten to
record the tests as withdrawn while keeping the concepts and noting the capital data
survives intact, and a banner added so remaining H1/H2/H3 mentions read as history.

### 20.4 Kept untouched

All of `src/` (7 modules, self-tests passing), `raw_data/` (19 MB, 36 files),
`processed_data/` (14 CSVs including all four capital slices), and all metadata. The
pipeline is the project's strongest asset and nothing in the review questioned it.

### 20.5 Verified after removal

| Check | Result |
|---|---|
| `shift_share.py --self-test` | ALL PASSED |
| `validate_manufacturing.py --self-test` | ALL PASSED |
| `econ_census.py` gate | 0 difference, 47/47 |
| `build_panel.py` | 235 rows, all checks pass |
| `lq_break_test.py` | ρ = 0.9869 |
| Notebooks 01, 02 | 0 errors, 5 charts matching 5 PNGs |
| Dangling references | none |

### 20.6 Still outstanding

No git repository. No `requirements.txt`. Reference year 2020 sits in the panel but
is analysed nowhere. Chart filenames now run 1, 4, 5, 6, 7 — renumbering was deferred
until the new hypotheses settle the chart set.

---

# SESSION 08 — consolidation, SQL, and data mining

---

## Part 21 — Removing duplication before adding anything

Adding a SQL layer on top of the existing code would have created a **third**
implementation of the location quotient, so consolidation came first.

**Audited duplication.** Three near-identical CSV loaders (`shift_share.load_cells`,
`build_panel.load_industry_slice`, `lq_break_test.load_employment`), and the location
quotient implemented twice with **different missing-data handling** — `fillna(0)` in
one, `flag == 'ok'` in the other.

Checked before changing anything: the two agreed **exactly**, max difference 0.0
across all 1,118 common cells. Benign, but only by accident — employment is never
suppressed, so the differing cells contributed zero either way. A correction to one
would not have reached the other.

**Consolidated into** `src/dataset.py` (one loader) and `src/metrics.py` (one location
quotient, one Herfindahl), with the missing-data semantics documented rather than
implicit: missing employment means zero *because employment is never suppressed*,
unlike value added.

**Regression gate:** the rebuilt panel is byte-identical, md5 `160c8d10…` before and
after, and every self-test stayed green.

**`lq_break_test.py` reframed.** It existed to clear the retired H1 to pool years
across the 2016 break. The finding (ρ = 0.9869) is still a live comparability fact, so
the script stays and the H1 framing goes.

### A portability bug found on the way

These scripts print Japanese prefecture names and **crashed on a default Windows
console** (cp1252), part-way through — after doing work, before writing output. They
only ever worked because `PYTHONIOENCODING` was being set manually. Anyone cloning the
repo would have hit it. `dataset.ensure_utf8_stdout()` now reconfigures stdout, and
every script that prints Japanese calls it.

This also produced a **false pass**: a comparison against a baseline JSON reported
"IDENTICAL" while the script had actually crashed before rewriting the file.

---

## Part 22 — A small SQL layer, scoped down twice

The first plan proposed a Kimball star schema justified as "cross-validation" of the
pandas pipeline. **Both claims were withdrawn after challenge.**

- Writing the same metric twice by the same author catches typos, not conceptual
  errors. The self-tests already catch more.
- A star schema over 235 panel rows and ~110k cells solves problems this project does
  not have: scale, conformed dimensions, slowly-changing dimensions, incremental
  loads, concurrency. None apply.

**What was built instead:** one long `fact_cells` table (110,544 rows from 13 slices),
a `fact_panel` table, two thin lookups, four views. DuckDB, Postgres-dialect SQL, no
server. Views deliberately exclude the location quotient and Herfindahl index, which
live in `src/metrics.py` — re-deriving them in SQL is the duplication Part 21 removed.

### Two real bugs the load checks caught

**A definitional mismatch.** `v_productivity` first summed the 24 industries and
disagreed with the panel by up to **0.492**. The panel takes totals from the published
`【00】製造業計` row, which includes suppressed establishments; summing drops them. The
check caught a genuine definitional difference, not a typo.

Investigating revealed the deeper issue: the validated CSVs **exclude** the `【00】`
row by design, so prefecture totals cannot be recovered from `fact_cells` at all.
Hence the second grain, `fact_panel`, and the view that joins them —
`v_cell_share_of_prefecture` — which is the query that genuinely needed both.

**A fragile SQL parser.** The question runner split files on `;` to find statement
boundaries and truncated a query at a semicolon **inside a comment**. Comments are now
stripped before splitting.

### The coverage cross-check

Warehouse `visible_coverage` matches the panel's independently-computed
`va_coverage_pct` on all 188 rows to **2.22e-16**. Two different routes, same answer.
Floor is Shimane 2016 at 0.9476 — chemicals and non-ferrous metals both suppressed.

### The two questions, and a real finding

**Q1: does capital intensity explain productivity at INDUSTRY level?** Yes.
Spearman **+0.718, p = 7.7e-05** across 24 industries. Petroleum ranks 1st on both;
leather 24th on both. This matters because at *prefecture* level capital deepening
explained nothing (Session 06). **Capital explains between-industry productivity and
not between-region productivity** — a cleaner statement than either result alone.

Biggest divergence: information and communications equipment, 23rd on capital and 8th
on productivity.

**Q2: which cells moved rank most, 2016 to 2019?** Petroleum and coal dominates, as
expected from its volatility. The first run had a bug — cells with suppressed value
added were ranked on NULL productivity, producing a spurious 45-place "gain" for Saga.
Fixed with an explicit null guard.

---

## Part 23 — Prefecture typology clustering

CLR → PCA (7 components, 80.2% of variance) → k-means and Ward.

**Verdict: QUALIFIED, passing 2 of 3 criteria.**

| Criterion | Result |
|---|---|
| Exceeds permuted null | PASS — 0.3671 vs null p95 0.3351 |
| Stable across years | PASS — ARI 1.000, 1.000, 0.636, mean 0.879 |
| k-means and Ward agree | **FAIL — ARI 0.351** |

Silhouette peaks at k = 2 (0.367) and collapses to ~0.19 for every larger k, so there
is at most one meaningful split. What it finds is **7 prefectures versus 40** —
Hokkaido, the four Shikoku prefectures, Kagoshima and Okinawa, weighted toward food,
pulp and ceramics. That is closer to outlier detection than to a typology.

The verdict logic initially reported "Supported" because it only checked the null and
stability. The algorithm-agreement criterion was in the plan and missing from the
code; adding it changed the answer. **Cluster membership should not be used as a
variable in later analysis.**

### Two self-test lessons

The fixture expectations were wrong twice, the same way as the shift-share fixture in
Session 04: **national rates are derived from the fixture**, so an unbalanced fixture
shifts the benchmark and invalidates every expected value. Fixed by adding a
mirror-image prefecture so the national split is exactly 50/50.

A second test was **flaky by construction**. Uniform random compositional data is
exchangeable, so permuting its columns leaves the distribution unchanged — the real
statistic and the null are draws from the same distribution, and "real ≤ null p95"
fails 5% of the time by design. Replaced with the non-flaky property, plus its
complement so a broken permuter cannot pass.

---

## Part 24 — Anomaly detection by median polish

Tukey's median polish on the 47 × 24 matrix of log productivity. Median rather than
mean because it is **robust to the outliers being searched for** — the self-test
plants a +5 outlier and shows median polish returning exactly +5 at that cell and
exactly zero everywhere else, while a mean-based fit smears up to 0.8 across the whole
row and column.

Closes a gap recorded in `docs/concepts.md` §3.10, which noted a two-way decomposition
had never been attempted.

**Results, 2019:** 1,091 cells, median absolute residual **0.1661 log points** (~18%).
Largest positive residual is Kyoto in other manufacturing at **+2.308** (~9× expected),
then Aichi in petroleum and Oita in non-ferrous metals.

### The cross-check, and why weak agreement is correct

Shift-share interaction against median-polish residual: overall Spearman **−0.13**,
but the top interaction cells land in the **top 7% of residuals** (Yamaguchi 26/1091,
Tokushima 24/1091).

That is the expected pattern. The interaction `(s_p − s_N)(π_p − π_N)` is positive in
*two* different situations — over-represented and productive, or under-represented and
unproductive — and is weighted by employment share and measured in levels. The
residual is an unweighted proportional deviation in log space. They answer different
questions, agree where both are extreme, and there is no reason for the full orderings
to align.

A fixture error here too: median polish centres effects on their **median**, so a
fixture whose column effects had median 0.25 correctly returned a grand term of 10.25.
The code was right; the expectation ignored the identification convention.

### A chart defect caught by looking

The residual heatmap rendered missing cells in the **same near-white** as a zero
residual, because a diverging map centres on white and matplotlib draws NaN as the
axes background. Suppressed data was indistinguishable from average data. Fixed with
an explicit grey for missing.

---

## Part 25 — Documentation

`docs/concepts.md` gained **section 7, Data engineering and data mining**: 14 entries
covering long-vs-wide storage, why no star schema, DRY, DuckDB versus PostgreSQL,
window functions, compositional data and CLR, PCA, k-means and Ward, silhouette,
permutation nulls, adjusted Rand index, median polish, outlier-detection families, and
three roads not taken (dbt, PySAL/Moran's I, co-location clustering).

Every entry carries a **Learn more** reading list, at the user's explicit request. The
document is now 68 entries and about 14,100 words.

---

# SESSION 09 — a stakeholder, a decision layer and two dashboards

---

## Part 26 — The review, and where this session departed from it

A recruiter-perspective review rated the work about 9/10 on quality but about 7/10
on fit for a Data Analyst portfolio. The bottom of the stack (acquisition,
validation, SQL, reproducibility) was strong. The top layer was missing: no
stakeholder, no dashboard, no decision. It also flagged over-sophisticated analysis
leading the README and some overbroad language. The fix chosen was **packaging, not
more analysis**.

Four departures from the review, each for a stated reason:

| Review recommended | Done instead | Why |
|---|---|---|
| Stakeholder: a firm choosing where to expand | **A prefectural planner** benchmarking the sector | Value added per worker is not a siting criterion. Yamaguchi's figure comes from chemicals a new plant would not inherit. A planner's question is exactly what the shift-share answers. |
| Automate a recurring refresh | **One check command, run by CI on every push** | The source survey was abolished, so a refresh would refresh nothing. Verification is what can recur honestly. |
| A map on page 1 | Optional; the ranked bar is primary | Geocoding needs manual verification, and area maps overweight Hokkaido. |
| A dashboard | **Two front-ends on one extract** | Power BI, built by the user from a written spec, and a Streamlit app built and tested here. |

### A bug the review missed

The README's quick start said the analysis "runs with no API key" and listed
`python src/build_panel.py` first. That script, and `econ_census.py`, read raw API
pages, which are gitignored. **Step one failed on every fresh clone.** Nobody noticed
because every check had run on the author's machine, where the raw files exist. The
quick start is now split into what runs from a clone and what needs re-acquisition.
CI now runs everything on a clean clone.

### Overbroad language corrected

The README said n = 47 left "not enough statistical power for hypothesis testing".
That is broader than the evidence. The precise statement: the original 15 tests at
n = 47 produced nominally significant results that did not survive correction for
multiple comparisons, so the project does not treat those associations as robust
evidence.

A second, smaller one surfaced while writing the new README: "within-industry
dominates in 37 of 47, stable across all four years". The count is actually 37, 36,
36 and 37. It is now stated as "36–37 of 47 in every year".

---

## Part 27 — The dashboard extract

`src/build_dashboard_data.py` writes seven CSVs to `dashboard/data/`: 3 dimensions
and 4 facts, one per grain. **A star schema, after Session 08 rejected one.** Same
principle, different consumer. Power BI's slicers filter along relationships from
dimensions to facts, so a shared `dim_prefecture` is what lets a region slicer
filter every fact table. Documented in concepts §7.2 (postscript) and §8.1.

Nothing is re-derived. Shift-share comes from `shift_share.decompose()`, LQ and
shares from `metrics.py`, and residuals from `anomaly_detect.analyse()`. Capital
intensity comes from a new SQL view, `v_industry_capital_intensity`, over an
in-memory DuckDB built from the committed CSVs. That gives the SQL layer a place in
the delivered pipeline, not only in exploration.

**The waterfall has four steps, not three.** The shift-share runs on published
industry cells; the headline figure uses the published prefecture total, which also
includes suppressed establishments. For Yamaguchi, 2019, they are 20.45 and 20.33.
A three-step waterfall would end at a different number from the KPI card beside it.
A fourth step, the *suppression adjustment*, closes the gap.

**32 checks, and the script refuses to write if any fail:**

- key uniqueness at every grain
- referential integrity (Power BI turns orphan keys into silent "(Blank)" rows, not errors)
- reconciliation to the panel, with worst difference 0.0
- waterfall sums to the published figure for all 188 prefecture-years (worst 3.6e-15)
- 2020 carries null, never zero, decomposition values
- the full 47 × 24 grid

**Expected values re-derived independently.** A scratch script with no project
imports recomputed Aichi, Yamaguchi and Okinawa from the raw CSVs. All matched:
Aichi 15.10, rank 7, 12.78%, mix +0.42, within +1.69.

**A discrepancy found and kept visible.** The capital–value added rank correlation
for 2019 on matched cells is **+0.63**, not the README's +0.72. The +0.72 pools
2016–2019 in SQL Q1, which also sums capital and employment over unmatched cells.
Year by year on matched cells it runs from +0.63 to +0.73. The finding holds. The
README now states the range, and `expected_values.md` explains why the dashboard
shows the single-year value.

A `-0.00` in the generated table (Aichi's suppression adjustment, −0.000003) was
fixed by rounding before formatting.

Panel md5 unchanged: `160c8d10…`.

---

## Part 28 — Power BI guide and Streamlit app

**`dashboard/POWER_BI_GUIDE.md`** is written for someone who knows SQL but not Power
BI. It covers:

- Importing with code columns forced to Text. Power Query turns "09" into 9 and
  breaks relationships.
- Nine single-direction 1:\* relationships, with a Mermaid diagram.
- Measures written as ratios of sums, with ratio columns hidden so they can't be
  averaged.
- `REMOVEFILTERS` for the national figure and `RANKX(ALL(...))` so rank stays out of 47.
- `HASONEVALUE` guards on the non-additive shift-share terms.
- Five pages, the palette from `viz_style.py`, publishing options, and a 12-item
  checklist.

To let DAX aggregate capital per worker as a ratio of sums, the view and the extract
gained summed capital, value added and employment columns. The ratio column alone
could only have been averaged.

**`app/`**, the Streamlit app, has the same five pages, via `st.navigation`. It reads
only `dashboard/data/`. Its one computation is `va_per_worker()`, a ratio of sums.
`viz_style.py` now imports matplotlib lazily, so the app can share the palette
without its lean deployment requirements installing matplotlib.

- **A state bug caught in design.** The Diagnosis page highlights the prefecture
  chosen on the Benchmark page. Streamlit clears a widget's state when the page that
  draws it is left, so the choice is copied to a plain session key.
- **`app/check_app.py`** uses `AppTest` to render all 5 pages in all 5 years (25
  runs, no exceptions). It also checks the Overview national figure, the seven Aichi
  benchmark metrics, the waterfall closure and the quadrant counts. The expected
  figures are parsed from `expected_values.md`, not restated.
- **Mutation test.** Changing the aggregation to a mean of ratios made the Overview
  check fail at **12.24** against 12.99. The check can catch the error it exists for.

### Visual check

Headless Edge screenshots of the live app captured a blank page, because Streamlit
renders over a websocket after load. Instead, each chart's figure spec was pulled
out of `AppTest`, written to standalone HTML and screenshotted. Two defects were
found and fixed:

- **Margins too tight.** Minus signs and leading digits were clipped off tick
  labels, and axis titles overlapped them.
- **Label collisions.** All 24 labels on the capital scatter collided. It now labels
  the extremes plus transport equipment; the rest show on hover.

---

## Part 29 — One command, run on every push

`src/run_checks.py` runs 11 steps as subprocesses, so each step's own exit code
counts:

- all five self-tests
- the shift-share identity on real data
- the warehouse rebuild, load checks and questions
- the extract's checks
- a **staleness check**: the committed extract must match a fresh build
- the app tests

The staleness check was itself mutation-tested. The first attempt edited a line
ending in scientific notation that the regex didn't match, so nothing changed and
the check passed. That was a broken test, not a broken check. Retried on a matching
line, it failed as it should.

`.github/workflows/checks.yml` runs the same command on Python 3.11 on every push and
pull request. `requirements.txt` gained `streamlit` and `plotly`; `app/requirements.txt`
lists only what the deployed app needs.

---

## Part 30 — README, executive summary, concepts

The **README was reordered** so the decision comes before the method:

1. the question
2. the stakeholder, labelled illustrative
3. six insights ending in one implication
4. the quadrant table with its caveat
5. the dashboards
6. how it's built
7. an appendix for clustering, median polish and variance decomposition
8. limitations

The dashboard section describes what exists and **claims no screenshots or live link
before they exist**.

One more overclaim was caught in the draft. Insight 1 said the top three prefectures
all run process industries. By location quotient, Tokushima's most specialised
industry is electronic components and Shiga's is plastics. It now says only that
Yamaguchi's lead rests on chemicals (LQ 3.2).

**`docs/executive-summary.md`**: one page for the planner, ending with what the
analysis cannot say.

**Notebooks 03 and 04** are retitled Appendix A and B, keeping their paths so
existing links hold.

**`docs/concepts.md` §8, Business intelligence and reporting:** 10 entries, each with
**Learn more**:

- star schema in Power BI
- relationships
- measures and `CALCULATE`
- ratio of sums
- additivity
- waterfalls
- diagnostic vs prescriptive
- CI
- Streamlit
- one extract, two front-ends

The index moved to §9. The mistakes list gained the fresh-clone quick start. The
document now has 78 entries.

### Left for the user

- **Build the Power BI report** from the guide and tick the checklist. It can't be
  built or verified here.
- **Deploy the app** to Streamlit Community Cloud (entrypoint
  `app/streamlit_app.py`). This needs the user's GitHub login. The README gets the
  link only after the deploy.

---

## Attribution


This project uses the e-Stat API (政府統計の総合窓口). Its content is not
guaranteed by the Japanese government.

> この分析は、政府統計総合窓口(e-Stat)のAPI機能を使用していますが、
> サービスの内容は国によって保証されたものではありません。

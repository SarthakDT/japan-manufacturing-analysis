# Manufacturing panel slice — reference year 2018

Source: 工業統計調査 `２０１９年確報` (survey conducted 1 June 2019).
Financial items refer to **January–December 2018**; counts to **1 June 2019**.
See [reference-years.md](reference-years.md).

**Data status: not yet downloaded.** This file records source definitions
verified from e-Stat and METI, and since updated with observed counts from the
downloaded data.

---

## 1. Tables

| Table | statsDataId | Coverage | Value-added measure | Role |
|---|---|---|---|---|
| 3-01 | `0003432907` | 従業者4人以上 | 付加価値額(従業者29人以下は粗付加価値額) — **blended** | **primary** |
| 3-03 | `0003432909` | 従業者30人以上 | 付加価値額 — **net** | robustness check |

**These roles were reversed in Session 02, and the reversal is deliberate.** The
original plan made 3-03 primary for its clean net value added. Measured against the
downloaded data, 3-03 suppresses ~9% of value-added cells (98–109 per year) against
~2.5% for 3-01 (24–29 per year), and that suppression concentrates in thin
prefecture × industry cells — exactly what a location quotient depends on. 3-01 also
covers ~182k establishments against ~46k.

The blend bias in 3-01 affects levels, is stable year to year, and is absorbed by
prefecture fixed effects. Reporting "results hold on the net-value-added subsample"
is stronger than silently analysing the sparser table. 3-03 remains the robustness
check for exactly that purpose.

**Measure counts, verified from `getMetaInfo`:** 3-01 has **6** measures. 3-03 has
**10** — it adds 生産額 and splits 事業所数 into four size bands
(合計 / 従業者30人~99人 / 100人~299人 / 300人以上). An earlier draft of this file
said seven; that was an estimate made before the metadata was downloaded.

## 2. Variable definitions — preserve the Japanese names

| Japanese | Output column | Unit | Note |
|---|---|---|---|
| 事業所数 | `establishments` | count | |
| 従業者数 | `employment` | 人 (persons) | **Persons engaged**, not employees. Includes proprietors and unpaid family workers. From the 2017 survey it also explicitly includes 有給役員 (paid company officers). Do not translate as "employees". |
| 現金給与総額 | `cash_wages` | 百万円 | |
| 原材料使用額等 | `raw_materials` | 百万円 | |
| 製造品出荷額等 | `shipments` | 百万円 | |
| 付加価値額 | `value_added` | 百万円 | Definition depends on establishment size — see §3 |
| 生産額 | `production_value` | 百万円 | Table 3-03 only |

**The monetary unit is 百万円 (millions of yen)** — not yen, not thousands.

## 3. The two value-added definitions

This is the most consequential definitional issue in the source.

**30+ employees — 付加価値額 (net):**
```
出荷額等 + inventory change − taxes − 原材料使用額等 − 減価償却額
```
Depreciation is deducted.

**4–29 employees — 粗付加価値額 (gross):**
```
出荷額等 − taxes − 原材料使用額等
```
Neither depreciation nor inventory adjustment.

The published 4+ column is a **blend of the two**, which is why it is labelled
literally `付加価値額(従業者29人以下は粗付加価値額)`. The blend ratio varies by
prefecture and correlates with plant size and capital intensity — that is, with
the explanatory variables. This is systematic bias, not noise.

This argues for table 3-03, and Session 01 recommended it on exactly this ground.
**Session 02 reversed that decision** — see §1. The blend bias is real but affects
levels, is stable year to year, and is absorbed by prefecture fixed effects,
whereas 3-03's much heavier suppression removes whole cells non-randomly from the
thin industries a location quotient depends on.

The trade-off each way, stated plainly:

- **3-01 (primary):** cleaner coverage (~182k establishments, ~2.5% of value-added
  cells suppressed), at the cost of a value-added measure that blends net and gross
  by establishment size.
- **3-03 (robustness):** a clean net measure, at the cost of covering only ~46k
  establishments and suppressing ~9% of value-added cells. Results reported on
  3-03 measure **large-establishment productivity**, which is a different quantity,
  not merely a smaller sample.

Both limitations belong in the README and in any write-up.

## 4. Missing-value conventions

| Symbol | Meaning | Flag emitted |
|---|---|---|
| `X`, `χ` (Greek chi), `Ｘ` (full-width) | suppressed for confidentiality | `suppressed` |
| `***`, `-`, `－` | nil / not applicable by definition | `nil_or_na` |
| anything else unparseable | — | `non_numeric` |
| combination absent from source | — | `absent_from_source` |

**Never coerced to 0.** Suppression targets thin prefecture × industry cells, so
it is non-random and correlated with small industry presence — exactly the cells
a location quotient depends on. Zero-filling would distort every LQ
systematically.

The API is called with `replaceSpChar=0`. e-Stat's 特殊文字の選択 option can
substitute `0` for these glyphs; it must not be used.

## 5. Geography — filtering

The area dimension has **73 items, not 47**. Three traps:

1. **Five national rows.** `全国計` plus `全国計(2014年)`…`全国計(2017年)`, which
   embed other years' data inside the table.
2. **21 designated cities that are subsets of their prefectures**, already
   counted in the prefecture rows: 札幌市, 仙台市, さいたま市, 千葉市, 東京特別区,
   横浜市, 川崎市, 相模原市, 新潟市, 静岡市, 浜松市, 名古屋市, 京都市, 大阪市,
   堺市, 神戸市, 岡山市, 広島市, 北九州市, 福岡市, 熊本市. Summing all 73
   double-counts badly. `東京特別区` ⊂ `東京`.
3. Prefecture names appear **without** the 都/府/県 suffix.

The pipeline **whitelists** the 47 prefectures by name rather than blacklisting
cities. A whitelist fails loudly when the source changes; a blacklist fails
silently.

## 6. Industry

JSIC 2-digit, codes in full-width brackets. 24 real divisions (`【09】`–`【32】`)
plus `【00】製造業計`, which is a **total row and is excluded**. Codes 25/26/27
(はん用機械 / 生産用機械 / 業務用機械) confirm the post-2008 JSIC structure, so the
major manufacturing reclassification predates the 2010 window.

Target shape after filtering: **47 × 24 = 1,128 rows.**

## 7. Validation performed

Written by `validate_manufacturing.py`, reported to
`metadata/validation_2018_table<N>.json`:

- exactly 47 prefectures and 24 industries, `【00】` excluded
- exactly 1,128 rows, built by explicit reindex onto the full grid so that
  fully-suppressed cells survive as explicit NaN rows
- zero duplicate prefecture × industry × measure rows (hard failure if any)
- negatives preserved and listed, never clipped — net value added is
  legitimately negative when depreciation exceeds operating margin
- prefecture sums reconciled against the `全国計` control row, with the gap
  reported rather than asserted to be zero. Small gaps are expected from
  rounding and from suppression.

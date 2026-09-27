# Reference-year mapping — 工業統計調査 (Census of Manufacture)

**Status: verified-from-source, 2026-09-14.** This file corrects an error in the
project handoff brief. Read it before labelling any downloaded table.

---

## 1. The rule

From the **平成29年 (2017) survey** onward, METI moved the survey date from
31 December to **1 June**, and the financial items were re-based to the
**previous calendar year**. Within a single post-2017 table the two halves refer
to different moments:

| Item group | Japanese | Refers to |
|---|---|---|
| Counts | 事業所数, 従業者数 | 1 June of the **survey year** |
| Financial | 現金給与総額, 原材料使用額等, 製造品出荷額等, 付加価値額 | Jan–Dec of the **previous** calendar year |

Verbatim from METI (`https://www.meti.go.jp/statistics/tyo/kougyo/result-2.html`):

> 平成29年調査より、調査日を12月31日から翌年6月1日に変更していることから、平成29年調査においては、事業所数、従業者数については平成29年6月1日現在、現金給与総額、製造品出荷額等などの経理事項については平成28年1月～12月の実績を調査しています。

The same page labels its result columns explicitly, which removes all ambiguity:

> 平成30(2018)年 ＜平成29(2017)年実績＞
> 平成29(2017)年 ＜平成28(2016)年実績＞

---

## 2. e-Stat labels datasets by SURVEY year, not reference year

This is the trap. A dataset titled `２０１９年確報` is the survey conducted on
1 June 2019, and its value-added figures are **calendar year 2018**.

### 2a. e-Stat's own `SURVEY_DATE` field is unreliable here — do not trust it

`getStatsList` reports `SURVEY_DATE = 201901-201912` for the `２０１９年確報`.
Taken at face value that says reference year 2019, contradicting METI. The field
is formulaic: it encodes the survey year as a Jan–Dec span. That was correct
while survey year equalled reference year (through the 2014 survey) and has been
wrong for every survey since the 2017 redesign. **Use the evidence below, not
`SURVEY_DATE`.**

### 2b. Proof by numerical identity — verified 2026-09-14

Compare the national 製造品出荷額等 (4+ establishments, 百万円) across two tables:

| Row | statsDataId | Value |
|---|---|---|
| `２０１９年確報` → `全国計` (unmarked) | `0003432907` | **331,809,377** |
| `２０２０年確報` → `全国計(2018年)` | `0003448119` | **331,809,377** |
| `２０１９年確報` → `全国計(2017年)` | `0003432907` | 319,035,840 |
| `２０２０年確報` → `全国計(2017年)` | `0003448119` | 319,035,840 |
| `２０２０年確報` → `全国計(2019年)` | `0003448119` | 322,533,418 |

The 2019 survey's unmarked current row is numerically identical to the 2020
survey's row explicitly labelled 2018. The 2017 figure agrees across both
tables. **The ２０１９年確報 therefore holds reference year 2018.**

### 2c. Structural corroboration

The area dimension is constructed as four year-labelled comparison rows plus the
current year:

| Table | National rows | Implied current year |
|---|---|---|
| 平成29年確報 | 2012, 2013, 2014, 2015 + unmarked | **2016** |
| ２０１９年確報 | 2014, 2015, 2016, 2017 + unmarked | **2018** |
| ２０２０年確報 | 2015, 2016, 2017, **2019年 explicit** | **2019** |

Each set is contiguous only under the reference-year reading. Note that the
2020 survey drops the unmarked row and labels its current year `全国計(2019年)`
outright, which removes the ambiguity entirely.

---

## 3. Corrected mapping

| Reference year (panel axis) | Collected by | e-Stat label |
|---|---|---|
| 2010 | 2010 CoM | 平成22年確報 |
| 2011 | 2012 Economic Census | — (no CoM) |
| 2012 | 2012 CoM | 平成24年確報 |
| 2013 | 2013 CoM | 平成25年確報 |
| 2014 | 2014 CoM | 平成26年確報 |
| 2015 | 2016 Economic Census | — (no CoM) |
| 2016 | 2017 CoM — first 1-June survey | 平成29年確報 |
| 2017 | 2018 CoM | 平成30年確報 |
| 2018 | 2019 CoM | **２０１９年確報** |
| 2019 | 2020 CoM — final run | **２０２０年確報** |
| 2020 | 2021 Economic Census | — |
| 2021–2023 | 経済構造実態調査 (ESS) | separate pipeline |

The e-Stat 確報 list for `toukei=00550010` contains no 平成23年, 平成27年 or
平成28年 entry, confirming the 2011, 2015 and 2016 survey gaps.

---

## 4. Consequence for the brief's Step 2

The brief instructs: download statsDataId `0003432909` / `0003432907` and emit
`manufacturing_2019.csv`. That is wrong by one year. Those IDs are the
`２０１９年確報` and carry **reference year 2018**.

- For reference year **2018** → statsDataIds `0003432907` (3-01) and
  `0003432909` (3-03). Both verified.
- For reference year **2019** → the `２０２０年確報` tables
  (tclass `000001156946`, 29 datasets, released 2022-03-09). **Their
  statsDataIds are not yet known** and must come from
  `python src/fetch_estat.py discover`.

This project therefore names raw directories and processed files by
**reference year**, and every download writes a `manifest.json` recording both
the reference year and the e-Stat survey-year label.

---

## 5. A second consequence the brief does not mention

Because counts and financial items refer to different dates after 2017, the
dependent variable

```
value added (Jan–Dec of year T)  ÷  persons engaged (1 June of year T+1)
```

mixes a flow measured over one calendar year with a headcount taken five months
after that year ended. Before the 2017 survey the two were aligned (both
31 December of year T).

This is a **structural mismatch in the dependent variable that begins at
reference year 2016**, not merely a labelling issue. It compounds the
有給役員 (paid company officers) definitional break at the same point, and is a
further reason to model the pre-2016 and post-2016 employment blocks separately
rather than attempting a point adjustment.

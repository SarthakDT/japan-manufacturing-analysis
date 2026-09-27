# Year-by-year availability matrix

Indexed by **reference year** (the panel's time axis), not survey year.
Nothing is marked downloaded unless files exist on disk.

Status: `downloaded` · `verified` (IDs confirmed, not yet pulled) ·
`unverified` · `gap` (confirmed absent).

### Validated and on disk

| Ref year | e-Stat label | Table | statsDataId | Coverage | VA measure |
|---|---|---|---|---|---|
| 2014 | 平成26年確報 市区町村編 | muni 3-01 | `0003144102` | 4+ | **粗付加価値額 (gross only)** |
| 2016 | 平成29年確報 地域別 | 3-01 | `0003325921` | 4+ | 付加価値額 (blended) |
| 2016 | 平成29年確報 地域別 | 3-03 | `0003325923` | 30+ | 付加価値額 (net) |
| 2017 | 平成30年確報 地域別 | 3-01 | `0003389992` | 4+ | blended |
| 2017 | 平成30年確報 地域別 | 3-03 | `0003389994` | 30+ | net |
| 2018 | ２０１９年確報 地域別 | 3-01 | `0003432907` | 4+ | blended |
| 2018 | ２０１９年確報 地域別 | 3-03 | `0003432909` | 30+ | net |
| 2019 | ２０２０年確報 地域別 | 3-01 | `0003448119` | 4+ | blended |
| 2019 | ２０２０年確報 地域別 | 3-03 | `0003448121` | 30+ | net |

All nine slices: 1,128 rows, 47 prefectures, 24 industries, 0 duplicates.

**Net value added is available for reference years 2016–2019 — a clean
four-year run.** 2014 has gross only and is not comparable on value added,
though its employment is comparable and is what the LQ break test uses.

### Identified but not downloaded

| Ref year | e-Stat label | Table no | statsDataId (30+, net VA) |
|---|---|---|---|
| 2010 | 平成22年確報 産業編 | 3-10 | `0003094711` |
| 2012 | 平成24年確報 産業編 | 3-10 | `0003097830` |
| 2013 | 平成25年確報 産業編 | 2-10 | `0003127834` |
| 2014 | 平成26年確報 産業編 | 2-10 | `0003144079` |

Schemas unverified. Note the table number differs by year (3-10, 3-10, 2-10,
2-10), so it cannot be templated.

### Reference year 2020 — downloaded and gated

| Measure | statsDataId | Coverage |
|---|---|---|
| Employment by prefecture | `0004003971` | 4+ |
| Value added by prefecture | `0004003973` | 4+ |
| Establishments by prefecture | `0004003970` | 4+ |
| Value added by prefecture × industry | `0004003977` | 4+ |

Source: 2021 Economic Census (令和3年経済センサス‐活動調査), a **complete
enumeration**. These tables carry 2019 alongside 2020, so the two instruments were
compared **on the same year**: max absolute difference **0** across all 47
prefectures on employment, value added and establishments. The Economic Census
reproduces the Census of Manufacture basis rather than restating it, so 2020 is on
the same measurement basis and has been appended with an `instrument` column.

**Limitation:** the Economic Census publishes employment only at prefecture level,
not prefecture × industry. Location quotient and Herfindahl values are therefore
**null for 2020**, not substituted.

**Caveat:** 2020 is the COVID year. National value added per worker was 12.970
against 12.988 in 2019. Notebooks 01 and 02 filter to the Census of Manufacture
window so their growth figures measure a trend rather than a shock.

### Capital stock — downloaded

| Ref year | Table | statsDataId | Coverage |
|---|---|---|---|
| 2016 | 3-04 | `0003325924` | 30+ |
| 2017 | 3-04 | `0003389995` | 30+ |
| 2018 | 3-04 | `0003432910` | 30+ |
| 2019 | 3-04 | `0003448122` | 30+ |

有形固定資産額 by prefecture × industry, 1,128 validated rows each. Note the measure
labels drift: reference years 2016–2017 use `有形固定資産額[年末現在高]` while
2018–2019 use `有形固定資産額[(A+B-E-F) 年末現在高]`. Identical quantities, different
strings; left unmapped this silently returns zero rows.

### Gaps and closed questions

| Ref year | Status |
|---|---|
| 2011 | `gap` — no CoM. Obtainable from the 2012 Economic Census (`0003389789`), not downloaded |
| 2015 | `gap` — no CoM. Obtainable from the 2016 Economic Census (`0003389393`), not downloaded |
| **2021 onward** | **`impossible` — see below** |

**2021 onward is not a scope decision, it is a data limit.** The 経済構造実態調査
(Economic Structure Survey) publishes manufacturing tables with **no area dimension
at all** — verified against `0004048573`, `0004048574` and `0004048575`, whose only
dimensions are measures and a combined time × industry key. Prefecture-level output
from that survey exists only for broad-division sales and for wholesale and retail.

**Manufacturing value added by prefecture does not exist for 2021 onward.** The panel
ends at reference year 2020 permanently.

Full index of all 661 Census of Manufacture tables:
[metadata/estat_table_index.csv](../metadata/estat_table_index.csv), produced by
`fetch_estat.py discover`.

## Notes

1. **The 3-0N numbering does not mean the same thing before and after the 2017
   redesign.** The brief warned about this and it is confirmed. For the 平成26年
   survey, `3-01` is a **市区町村編** (municipality edition) table with 69 areas,
   10 measures and a `@time` dimension. For the 平成29年 survey onward, `3-01`
   is a **地域別** table with 73 areas and 6 measures. They are not the same
   table lineage and must not be concatenated without checking definitions.

2. **The pre-2017 municipality table's time dimension is a trap.** It advertises
   reference years 2010–2014, but **prefecture-level detail exists for 2014
   only**. Cell counts per year in `0003144102`:

   | Year | Cells | Areas |
   |---|---|---|
   | 2010 | 250 | 1 (全国) |
   | 2011 | 250 | 1 (全国) |
   | 2012 | 250 | 1 (全国) |
   | 2013 | 250 | 1 (全国) |
   | **2014** | **17,250** | **69** |

   Selecting 2010, 2012 or 2013 yields an all-NaN 47 × 24 grid that looks
   structurally valid. `validate_manufacturing.py` now refuses to write output
   when no measure survives filtering, rather than emitting a plausible-looking
   empty CSV. Prefecture data for 2010–2013 must come from the 産業編 tables
   listed above.

4. e-Stat's `SURVEY_DATE` metadata field is formulaic and **wrong for every
   survey from 2017 onward**. See
   [reference-years.md](reference-years.md) §2a.

## Comparability blocks

Two breaks split the window, and they do not fall in the same place for every
variable. That is the central design constraint of this panel.

| Variable | Break at ref yr 2016 | Break at ref yr 2020 | Longest clean run |
|---|---|---|---|
| Value added | none — financial items were always Jan–Dec | yes — CoM abolished; ESS is sample-based and drops 個人経営 | 2016–2019 (4 yrs) |
| Employment (従業者数) | **yes** — 有給役員 added, date moved to 1 June | yes | 2010+2012–2014, then 2016–2019 |
| Industry employment (LQ) | see the LQ break test | yes | pending |

The reference-date move affects counts only, never financial items. Treating
value added and employment as sharing one consistent window is the trap.

# Tableau build guide

Build the Tableau edition of the Japanese Manufacturing Benchmarking dashboard from the canonical extract in `dashboard/data/`.

The project deliberately calculates the statistical analysis once in Python. Tableau should filter, aggregate and communicate those results, not reimplement shift-share decomposition or median-polish residuals. This keeps Tableau and Streamlit aligned.

## Scope and prerequisites

- Tableau Desktop (or Tableau Public if you are comfortable publishing the workbook and data publicly).
- Repository cloned locally; no e-Stat API key is needed for the committed extracts.
- Python environment installed for rebuilding/checking the extract when needed.

Run from the repository root:

```bash
python src/build_dashboard_data.py
python src/run_checks.py
```

The source extract is in `dashboard/data/`. It contains seven CSVs, encoded as UTF-8 with BOM to keep Japanese labels readable:

| Table | Grain | Role |
|---|---|---|
| `dim_prefecture.csv` | one row per prefecture | prefecture labels, region and map location |
| `dim_industry.csv` | one row per industry | industry labels |
| `dim_year.csv` | one row per reference year | reference year and whether industry detail exists |
| `fact_prefecture_year.csv` | prefecture × year | headline metrics, ranks, gap and diagnosis components |
| `fact_prefecture_industry.csv` | prefecture × industry × year | industry shares, LQ and residuals |
| `fact_industry_year.csv` | industry × year | national industry productivity and capital per worker |
| `fact_waterfall.csv` | four steps per prefecture × year | waterfall step labels and amounts |

## 1. Connect the data

1. Open Tableau Desktop → **Connect → Text file** and select `dashboard/data/fact_prefecture_year.csv`.
2. On the Data Source page, use **Add** to add the other six CSVs.
3. Build relationships (logical layer, not physical joins) using the keys below. Keep each table at its declared grain.

### Relationships

- `dim_prefecture.prefecture_code` → `fact_prefecture_year.prefecture_code`
- `dim_prefecture.prefecture_code` → `fact_prefecture_industry.prefecture_code`
- `dim_prefecture.prefecture_code` → `fact_waterfall.prefecture_code`
- `dim_industry.industry_code` → `fact_prefecture_industry.industry_code`
- `dim_industry.industry_code` → `fact_industry_year.industry_code`
- `dim_year.reference_year` → each fact table's `reference_year`

Set each relationship to one dimension row matching many fact rows. Tableau may call this a relationship rather than enforcing cardinality. Confirm that codes with leading zeros remain strings; `prefecture_code` and `industry_code` are keys, not quantities. If Tableau imports them as numbers, change their data type to **String**.

Do not physically join all facts together. Their grains differ and a physical join can multiply rows, inflating employment and value added. Do not relate `fact_prefecture_year.top_industry_code` to `dim_industry.industry_code` as a second active path; use it only for a targeted lookup if needed.

### Data types

- String: all prefecture and industry codes; names, region, diagnosis, instrument, step and source-edition labels.
- Number (whole): `reference_year`, `rank_va_per_worker`, `step_order`, `region_order`.
- Number (decimal): monetary values, employment, ratios, shares, effects and residuals.
- Boolean: `has_industry_detail`.

Leave blank/suppressed observations as null. **Do not replace them with zero.**

## 2. Core calculated fields

Create these calculated fields. The explicit ratio-of-sums is important: never average the per-row productivity ratio to get the national figure.

### Headline productivity

```tableau
// VA per Worker (million yen)
SUM([value_added]) / SUM([employment])
```

Use this on a view built from `fact_prefecture_year`. It is a ratio of sums, so national productivity is not biased by weighting small and large prefectures equally.

For a separate national benchmark line on prefecture comparisons, prefer the supplied `national_va_per_worker` value at prefecture-year grain only when the view has one reference year and does not sum across prefectures. To recompute the benchmark for all prefectures in a year, use a FIXED LOD expression against the appropriate fact table and verify it against the canonical expected values. LOD expressions ignore ordinary dimension filters unless those filters are context filters; be deliberate about that behavior.

### Gap to national

```tableau
// Use only where one reference year is selected.
AVG([va_per_worker]) - AVG([national_va_per_worker])
```

The provided `va_per_worker` field is stored at prefecture-year grain, so AVG is safe only when the view is constrained to one record per prefecture-year. For an aggregate KPI, use the ratio-of-sums field instead.

### Rank

Use the stored `rank_va_per_worker` for a reproducible rank of 1 through 47. Sort descending by `va_per_worker` and verify with `dashboard/expected_values.md`.

### Industry mix / within-industry diagnosis

Use the precomputed `mix_effect`, `within_effect`, and `suppression_adjustment` fields from `fact_prefecture_year`; do not derive them from ratios in Tableau. Add a warning/blank state when `has_industry_detail` is false (2020) and when more than one prefecture is selected: the terms are not additive across prefectures.

The `diagnosis` field labels the sign quadrants of mix and within-industry performance. It is a diagnostic, not a causal claim or a policy recommendation.

### Industry location quotient

Use the precomputed `lq` from `fact_prefecture_industry`. LQ above 1 means an industry's share of a prefecture's manufacturing employment exceeds its national share for that year. Keep the field at prefecture × industry × year grain and do not sum it.

### Industry capital-intensity scatterplot

Use `fact_industry_year`, with one year selected. Plot `capital_per_worker_30plus` against `va_per_worker_30plus` (or the available field names in the extract), color by industry, and label selected outliers. This is descriptive association, not causality. Capital measures cover establishments with 30+ employees.

## 3. Build the dashboards

Create four dashboards in this order. Use consistent typography, restrained colors, visible units, and a persistent reference-year filter.

### A. National overview

- KPI: national value added per worker (million yen, nominal).
- KPI: total manufacturing value added (trillion yen) and employment (millions).
- Horizontal bar ranking of all 47 prefectures, colored by region; include a reference line for the national benchmark.
- Line chart of national value added per worker over 2016–2020.
- A detail table with prefecture, rank, value added per worker, gap to national and share of national value added.
- Filters: reference year and region. Prefer an explicit year filter over a range when showing decompositions.

### B. Prefecture explorer

- Select one prefecture; show value added per worker, national gap, rank and share of national value added.
- Make a waterfall-like view from `fact_waterfall`: use `step` sorted by `step_order`; amount is `SUM(amount)`. The first step is the benchmark and following steps are relative changes. Configure the chart as a waterfall or Gantt/Running Total construction and verify the final result exactly matches published prefecture productivity.
- Add a paired bar chart: prefecture employment share vs national employment share by industry, plus LQ in the tooltip.
- Add a diverging bar chart of `pct_vs_expected` by industry, keeping suppressed values null.

For 2020, hide decomposition and cell-level industry views and display: “Reference year 2020 uses the 2021 Economic Census, which has prefecture totals but no prefecture × industry detail.”

### C. Mix vs within-industry diagnosis

- Scatter: `mix_effect` (x) versus `within_effect` (y); one mark per prefecture for a single reference year.
- Add zero reference lines on both axes and label quadrant meanings.
- Color by the stored `diagnosis`.
- Add prefecture and region filters. Be careful that the effects are prefecture-level; do not present their sum over several prefectures as a meaningful aggregate.
- Tooltip: prefecture, region, value added per worker, rank, mix effect, within-industry effect, suppression adjustment and diagnosis.

### D. Industry economics

- Horizontal bars of national industry value added per worker.
- Scatter of capital per worker vs value added per worker (30+ employee establishment basis).
- Industry × year heatmap for productivity or relative-to-national metrics.
- Filters: reference year and industry.
- Explain that per-worker productivity is not hourly productivity and the figures are nominal.

## 4. Map of Japan (optional)

Use `dim_prefecture.map_location` as the geographic role/location field where Tableau can resolve it; otherwise use the official prefecture name as a geographic role and country = Japan. Check all 47 marks manually. Name-based geocoding can misplace prefectures or fail to resolve Japanese administrative units, so do not publish the map without confirming the locations. If mapping is unreliable, the ranked bar chart is the dependable comparison.

## 5. Validation: required before publishing

Use `dashboard/expected_values.md` as the reference.

- [ ] National VA per worker: 2016 = 12.86; 2017 = 13.43; 2018 = 13.41; 2019 = 12.99; 2020 = 12.97.
- [ ] In 2019, Aichi: 15.10 million yen per worker, rank 7, 12.78% share of national value added.
- [ ] In 2019, Yamaguchi: 20.33, rank 1.
- [ ] In 2019, diagnosis counts: 13 strong mix/strong performance; 5 weak mix/strong performance; 3 strong mix/weak performance; 26 weak mix/weak performance.
- [ ] Highest 2019 national industry productivity is petroleum & coal = 34.81; lowest is leather = 5.90.
- [ ] With year 2020 selected, mix/within effects and industry-level views are blank/unavailable, not zero.
- [ ] With multiple prefectures selected, don't aggregate the non-additive decomposition terms into a combined score.
- [ ] Suppressed cells remain blank; don't recode to zero.
- [ ] Waterfall closes to the published productivity value, including the suppression adjustment.

If a value differs, first inspect the table grain, relationship model, filter context and aggregation. Do not “fix” a mismatch by editing the source values or changing the precomputed analysis.

## 6. Publishing and portfolio presentation

- **Tableau Public:** only use it if you are comfortable making the workbook and underlying published data public. Never publish secrets or private data.
- **Tableau Cloud/Server:** use your organization's authentication and permissions if you need controlled access.
- Keep a `dashboard/tableau/` folder for workbook documentation, screenshots and a short build log. Tableau workbook files are best saved from Tableau Desktop; use the guide as a reproducible build recipe rather than pretending a workbook has been generated programmatically.
- In the portfolio README, describe this as an interactive Tableau layer over a validated Python/SQL analytics pipeline. State the data's reference-year limit (2016–2020), nominal units and correlational nature.


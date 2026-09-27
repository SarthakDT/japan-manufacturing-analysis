-- =============================================================================
-- 02_views.sql — derived views.
--
-- SCOPE RULE: these cover only what Python does NOT already compute
-- canonically. The location quotient and the Herfindahl index live in
-- src/metrics.py and are deliberately NOT re-derived here — a second
-- implementation is the duplication this layer exists to avoid, and the two
-- would drift. Views earn their place by answering questions that previously
-- needed a bespoke script across 14 CSVs.
-- =============================================================================

-- A cell as a share of its own prefecture's total.
--
-- This is the view that justifies holding both grains in one store. It joins
-- the industry grain (fact_cells) to the prefecture grain (fact_panel), which
-- previously meant loading two differently-shaped CSVs and aligning them in
-- pandas. The coverage column exposes how much of a prefecture's value added
-- the visible industry cells actually account for: below 100% means
-- confidentiality suppression is hiding part of it.
CREATE OR REPLACE VIEW v_cell_share_of_prefecture AS
SELECT
    c.reference_year,
    c.prefecture_code,
    c.prefecture_name,
    c.industry_code,
    c.industry_name,
    c.value                                   AS cell_value_added,
    p.value_added                             AS prefecture_value_added,
    c.value / NULLIF(p.value_added, 0)        AS share_of_prefecture,
    SUM(c.value) OVER (PARTITION BY c.reference_year, c.prefecture_code)
        / NULLIF(p.value_added, 0)            AS visible_coverage
FROM fact_cells c
JOIN fact_panel p
  ON p.reference_year = c.reference_year
 AND p.prefecture_code = c.prefecture_code
WHERE c.source_table = '3-01'
  AND c.measure = 'value_added'
  AND c.flag = 'ok';

-- Capital per worker on the 30+ basis. Computed ad hoc in a deleted notebook
-- and canonically nowhere; capital (table 3-04) and employment (3-03) live in
-- different source tables, which is exactly why this was awkward before.
CREATE OR REPLACE VIEW v_capital_intensity AS
WITH cap AS (
    SELECT reference_year, prefecture_code,
           SUM(value) FILTER (WHERE measure = 'capital_stock_year_end' AND flag = 'ok') AS capital_stock
    FROM fact_cells
    WHERE source_table = '3-04' AND industry_code <> '00'
    GROUP BY 1, 2
),
emp AS (
    SELECT reference_year, prefecture_code, prefecture_name,
           SUM(value) FILTER (WHERE measure = 'employment'  AND flag = 'ok') AS employment,
           SUM(value) FILTER (WHERE measure = 'value_added' AND flag = 'ok') AS value_added
    FROM fact_cells
    WHERE source_table = '3-03' AND industry_code <> '00'
    GROUP BY 1, 2, 3
)
SELECT e.reference_year, e.prefecture_code, e.prefecture_name,
       c.capital_stock, e.employment,
       c.capital_stock / NULLIF(e.employment, 0) AS capital_per_worker,
       e.value_added   / NULLIF(e.employment, 0) AS va_per_worker
FROM emp e
JOIN cap c USING (reference_year, prefecture_code);

-- Same measure on both coverage bases, side by side. Session 06 found the
-- aging result flipped significance between 4+ and 30+; comparing coverage
-- used to need a script every time.
CREATE OR REPLACE VIEW v_measure_by_size_class AS
SELECT
    reference_year, prefecture_code, prefecture_name,
    industry_code, industry_name, measure,
    MAX(value) FILTER (WHERE size_class = '4+'  AND flag = 'ok') AS value_4plus,
    MAX(value) FILTER (WHERE size_class = '30+' AND flag = 'ok') AS value_30plus,
    MAX(value) FILTER (WHERE size_class = '30+' AND flag = 'ok')
      / NULLIF(MAX(value) FILTER (WHERE size_class = '4+' AND flag = 'ok'), 0) AS share_from_large
FROM fact_cells
WHERE source_table IN ('3-01', '3-03')
GROUP BY 1, 2, 3, 4, 5, 6;

-- Year-on-year change per cell, via LAG over the reference-year ordering.
CREATE OR REPLACE VIEW v_year_over_year AS
SELECT
    reference_year, prefecture_code, prefecture_name,
    industry_code, industry_name, source_table, size_class, measure,
    value,
    LAG(value) OVER w                                           AS prev_value,
    value - LAG(value) OVER w                                   AS abs_change,
    (value - LAG(value) OVER w) / NULLIF(LAG(value) OVER w, 0)  AS pct_change
FROM fact_cells
WHERE flag = 'ok'
WINDOW w AS (
    PARTITION BY prefecture_code, industry_code, source_table, measure
    ORDER BY reference_year
);

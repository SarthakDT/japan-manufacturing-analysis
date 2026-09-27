-- =============================================================================
-- 03_questions.sql — questions the project had not asked, because they were
-- awkward across 14 separate CSVs.
--
-- These are the justification for the SQL layer. If it produced nothing new it
-- would be decoration. Each query is named and run by
-- src/build_warehouse.py --questions.
-- =============================================================================

-- Q1. Does the capital-intensity story hold at INDUSTRY level?
--
-- The project established that capital-intensive industries (chemicals,
-- petroleum) sit at the top of the productivity ranking, but only ever
-- inspected capital at PREFECTURE level, where it explained nothing. Capital
-- lives in table 3-04 and employment in 3-03, so pairing them by industry meant
-- reading two differently-shaped CSVs per year and aligning them by hand.
--
-- name: q1_capital_intensity_by_industry
WITH cap AS (
    SELECT industry_code,
           SUM(value) AS capital_stock
    FROM fact_cells
    WHERE source_table = '3-04'
      AND measure = 'capital_stock_year_end'
      AND flag = 'ok'
      AND industry_code <> '00'
    GROUP BY industry_code
),
prod AS (
    SELECT industry_code,
           SUM(value) FILTER (WHERE measure = 'employment')  AS employment,
           SUM(value) FILTER (WHERE measure = 'value_added') AS value_added
    FROM fact_cells
    WHERE source_table = '3-03'
      AND flag = 'ok'
      AND industry_code <> '00'
      AND measure IN ('employment', 'value_added')
    GROUP BY industry_code
)
SELECT
    i.name_en                                              AS industry,
    ROUND(c.capital_stock / NULLIF(p.employment, 0), 2)    AS capital_per_worker,
    ROUND(p.value_added   / NULLIF(p.employment, 0), 2)    AS va_per_worker,
    RANK() OVER (ORDER BY c.capital_stock / NULLIF(p.employment, 0) DESC) AS rank_capital,
    RANK() OVER (ORDER BY p.value_added   / NULLIF(p.employment, 0) DESC) AS rank_productivity
FROM prod p
JOIN cap  c USING (industry_code)
JOIN dim_industry i USING (industry_code)
ORDER BY capital_per_worker DESC;


-- Q2. Which prefecture x industry cells moved RANK most between 2016 and 2019?
--
-- Levels are well covered; movement is not. Ranking within an industry across
-- prefectures, then differencing those ranks across years, needs two window
-- functions over a pivot that spans four separate CSVs.
--
-- name: q2_biggest_rank_movers
WITH cells AS (
    SELECT reference_year, prefecture_code, industry_code,
           SUM(value) FILTER (WHERE measure = 'value_added') AS value_added,
           SUM(value) FILTER (WHERE measure = 'employment')  AS employment
    FROM fact_cells
    WHERE source_table = '3-01'
      AND reference_year IN (2016, 2019)
      AND flag = 'ok'
      AND industry_code <> '00'
      AND measure IN ('value_added', 'employment')
    GROUP BY 1, 2, 3
),
ranked AS (
    SELECT reference_year, prefecture_code, industry_code,
           value_added / NULLIF(employment, 0) AS va_per_worker,
           RANK() OVER (PARTITION BY reference_year, industry_code
                        ORDER BY value_added / NULLIF(employment, 0) DESC) AS rnk
    FROM cells
    -- Both guards are needed. employment > 0 avoids divide-by-zero; the
    -- value_added guard excludes cells whose value added was suppressed, which
    -- would otherwise be ranked on a NULL productivity and produce spurious
    -- "movement" for a prefecture that simply had no published figure.
    WHERE employment > 0
      AND value_added IS NOT NULL
),
movement AS (
    SELECT prefecture_code, industry_code,
           MAX(rnk)          FILTER (WHERE reference_year = 2016) AS rank_2016,
           MAX(rnk)          FILTER (WHERE reference_year = 2019) AS rank_2019,
           MAX(va_per_worker) FILTER (WHERE reference_year = 2016) AS vapw_2016,
           MAX(va_per_worker) FILTER (WHERE reference_year = 2019) AS vapw_2019
    FROM ranked
    GROUP BY 1, 2
    HAVING COUNT(DISTINCT reference_year) = 2
)
SELECT
    p.name_romaji                       AS prefecture,
    i.name_en                           AS industry,
    m.rank_2016,
    m.rank_2019,
    m.rank_2016 - m.rank_2019           AS places_gained,
    ROUND(m.vapw_2016, 2)               AS vapw_2016,
    ROUND(m.vapw_2019, 2)               AS vapw_2019
FROM movement m
JOIN dim_prefecture p USING (prefecture_code)
JOIN dim_industry   i USING (industry_code)
ORDER BY ABS(m.rank_2016 - m.rank_2019) DESC
LIMIT 12;

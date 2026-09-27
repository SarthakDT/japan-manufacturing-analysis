-- =============================================================================
-- 01_build.sql — the consolidated fact table and its lookups.
--
-- WHY LONG FORMAT
-- The three source tables carry different measure sets: 3-01 has 6 measures,
-- 3-03 has 10 (establishment counts split by size band, plus 生産額), and 3-04
-- has 20 (inventories and tangible fixed assets). A wide schema would be mostly
-- NULL. One row per (cell, measure) keeps it dense and lets a new source table
-- be added without a schema change.
--
-- WHY THE FLAG TRAVELS WITH THE VALUE
-- A NULL here can mean three different things: confidentiality-suppressed
-- (a real number the publisher withheld), nil by definition (no such
-- establishments), or absent from the source response. Collapsing those to
-- NULL alone would lose the distinction that every downstream decision rests
-- on, so `flag` is carried on the same row.
--
-- WHAT THIS IS NOT
-- Not a star schema. At ~170k rows across one fact grain there are no conformed
-- dimensions, no slowly-changing dimensions and no incremental load to manage,
-- so dimensional modelling would add ceremony without solving anything. See
-- docs/concepts.md §7.
-- =============================================================================

DROP TABLE IF EXISTS fact_cells;

CREATE TABLE fact_cells (
    reference_year   INTEGER  NOT NULL,
    prefecture_code  VARCHAR  NOT NULL,
    prefecture_name  VARCHAR  NOT NULL,
    industry_code    VARCHAR  NOT NULL,
    industry_name    VARCHAR  NOT NULL,
    source_table     VARCHAR  NOT NULL,   -- '3-01' | '3-03' | '3-04' | 'muni3-01'
    size_class       VARCHAR  NOT NULL,   -- '4+' | '30+'
    measure          VARCHAR  NOT NULL,
    value            DOUBLE,              -- NULL when not 'ok'
    flag             VARCHAR  NOT NULL    -- ok | suppressed | nil_or_na | absent_from_source
);

-- Lookups. Deliberately thin: readable labels for joins, nothing more.
DROP TABLE IF EXISTS dim_prefecture;
CREATE TABLE dim_prefecture (
    prefecture_code VARCHAR PRIMARY KEY,
    name_ja         VARCHAR NOT NULL,
    name_romaji     VARCHAR NOT NULL
);

DROP TABLE IF EXISTS dim_industry;
CREATE TABLE dim_industry (
    industry_code VARCHAR PRIMARY KEY,
    name_ja       VARCHAR NOT NULL,
    name_en       VARCHAR NOT NULL
);

-- The prefecture x year grain, loaded from the committed analysis panel.
--
-- WHY A SECOND TABLE RATHER THAN AGGREGATING fact_cells
-- The validated cell CSVs deliberately exclude the published total row
-- (industry code 00) because it is a total, not an industry. Prefecture totals
-- therefore cannot be recovered by summing fact_cells: summing drops every
-- suppressed cell, and that loss concentrates in small prefectures. The panel
-- carries the publisher's own totals, so it is loaded as its own grain.
--
-- Having both grains in one place is what makes v_cell_share_of_prefecture
-- possible, which is the query that was genuinely awkward before.
DROP TABLE IF EXISTS fact_panel;
CREATE TABLE fact_panel (
    reference_year   INTEGER NOT NULL,
    prefecture_code  VARCHAR NOT NULL,
    prefecture_name  VARCHAR NOT NULL,
    instrument       VARCHAR NOT NULL,
    value_added      DOUBLE,
    employment       DOUBLE,
    establishments   DOUBLE,
    va_per_worker    DOUBLE,
    hhi_employment   DOUBLE,
    lq_top           DOUBLE,
    aging_ratio      DOUBLE,
    mfg_intensity    DOUBLE
);

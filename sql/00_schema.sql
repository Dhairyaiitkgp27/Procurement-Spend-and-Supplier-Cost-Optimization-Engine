-- ============================================================================
-- 00_schema.sql  —  Base views over the cleaned procurement ledger
-- Engine: DuckDB (read_csv_auto). Run all files via:  python -m src.run_sql
-- NOTE: the dataset is SIMULATED; savings queries return MODELED opportunity.
-- ============================================================================

CREATE OR REPLACE VIEW pos AS
SELECT * FROM read_csv_auto('data/processed/procurement_clean.csv', header=true);

-- Region cost-tier lookup (mirrors config.benchmarking.region_tiers)
CREATE OR REPLACE VIEW region_tier AS
SELECT supplier_country,
       CASE WHEN supplier_country IN
            ('China','India','Vietnam','Mexico','Poland','Brazil')
            THEN 'LowCost' ELSE 'HighCost' END AS region_tier
FROM (SELECT DISTINCT supplier_country FROM pos);

CREATE OR REPLACE VIEW pos_ext AS
SELECT p.*, r.region_tier
FROM pos p JOIN region_tier r USING (supplier_country);

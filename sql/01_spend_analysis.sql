-- ============================================================================
-- 01_spend_analysis.sql  —  Spend cube, Pareto and concentration
-- ============================================================================

-- Headline KPIs
SELECT
    COUNT(*)                                   AS po_lines,
    COUNT(DISTINCT po_id)                      AS purchase_orders,
    COUNT(DISTINCT supplier_id)                AS suppliers,
    COUNT(DISTINCT category)                   AS categories,
    COUNT(DISTINCT business_unit)              AS business_units,
    ROUND(SUM(line_spend), 0)                  AS total_spend,
    ROUND(AVG(line_spend), 0)                  AS avg_line_spend
FROM pos;

-- Spend by category with share
SELECT category,
       ROUND(SUM(line_spend), 0)                                   AS spend,
       ROUND(100.0 * SUM(line_spend) / SUM(SUM(line_spend)) OVER (), 2) AS pct_of_spend,
       COUNT(DISTINCT supplier_id)                                 AS suppliers
FROM pos
GROUP BY category
ORDER BY spend DESC;

-- Supplier Pareto: cumulative share, flag the set that carries 80%
WITH s AS (
    SELECT supplier_id, supplier_name, SUM(line_spend) AS spend
    FROM pos GROUP BY supplier_id, supplier_name
), r AS (
    SELECT *,
        SUM(spend) OVER (ORDER BY spend DESC) /
        SUM(spend) OVER ()                        AS cum_share,
        ROW_NUMBER() OVER (ORDER BY spend DESC)   AS rnk
    FROM s
)
SELECT rnk, supplier_name, ROUND(spend,0) AS spend,
       ROUND(100*cum_share,2) AS cumulative_pct,
       CASE WHEN cum_share <= 0.80 THEN 1 ELSE 0 END AS within_top_80pct
FROM r ORDER BY rnk;

-- Supplier concentration (Herfindahl-Hirschman Index) by category
WITH cs AS (
    SELECT category, supplier_id, SUM(line_spend) AS spend
    FROM pos GROUP BY category, supplier_id
), tot AS (
    SELECT category, SUM(spend) AS cat_total FROM cs GROUP BY category
), shares AS (
    SELECT cs.category, cs.spend / tot.cat_total AS share
    FROM cs JOIN tot USING (category)
)
SELECT category,
       COUNT(*)                          AS n_suppliers,
       ROUND(SUM(share * share), 4)       AS supplier_hhi
FROM shares
GROUP BY category
ORDER BY supplier_hhi DESC;

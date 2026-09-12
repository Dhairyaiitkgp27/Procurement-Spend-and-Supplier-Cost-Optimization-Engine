-- ============================================================================
-- 02_price_benchmarking.sql  —  Item/region reference prices & overpayment
-- Reference price = median unit price per (item, region_tier);
-- competitive price = 25th percentile. Overpaid if supplier > reference*1.10.
-- ============================================================================

-- Benchmark table per (item, region_tier)
CREATE OR REPLACE TEMP VIEW benchmark AS
SELECT item, region_tier,
       COUNT(*)                                   AS n_txns,
       COUNT(DISTINCT supplier_id)                AS n_suppliers,
       MEDIAN(unit_price)                         AS reference_price,
       QUANTILE_CONT(unit_price, 0.25)            AS competitive_price,
       (COUNT(*) >= 20 AND COUNT(DISTINCT supplier_id) >= 2) AS benchmarkable
FROM pos_ext
GROUP BY item, region_tier;

-- Supplier vs reference: weighted price premium and modeled excess spend
WITH si AS (
    SELECT p.supplier_id, p.supplier_name, p.category, p.item, p.region_tier,
           SUM(p.line_spend)                              AS spend,
           SUM(p.quantity)                                AS qty,
           SUM(p.unit_price * p.quantity)/SUM(p.quantity) AS supplier_price,
           b.reference_price, b.competitive_price, b.benchmarkable
    FROM pos_ext p
    JOIN benchmark b USING (item, region_tier)
    WHERE b.benchmarkable
    GROUP BY p.supplier_id, p.supplier_name, p.category, p.item, p.region_tier,
             b.reference_price, b.competitive_price, b.benchmarkable
)
SELECT supplier_id, supplier_name, category,
       ROUND(SUM(spend),0)                                             AS benchmarked_spend,
       ROUND(SUM((supplier_price/reference_price - 1) * spend)/SUM(spend), 4) AS wtd_price_premium,
       ROUND(SUM(GREATEST((supplier_price - reference_price) * qty, 0)), 0)   AS modeled_excess_vs_reference,
       SUM(CASE WHEN supplier_price > reference_price*1.10 THEN 1 ELSE 0 END) AS n_overpriced_items
FROM si
GROUP BY supplier_id, supplier_name, category
HAVING modeled_excess_vs_reference > 0
ORDER BY modeled_excess_vs_reference DESC
LIMIT 25;

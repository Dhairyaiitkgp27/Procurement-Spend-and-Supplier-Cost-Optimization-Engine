-- ============================================================================
-- 05_savings_opportunity.sql  —  MODELED savings summary (base 50% capture)
-- Mirrors the disjoint lever decomposition in src/savings_engine.py.
-- All values are MODELED opportunity from SIMULATED data, not realized savings.
-- ============================================================================
CREATE OR REPLACE TEMP VIEW benchmark AS
SELECT item, region_tier, MEDIAN(unit_price) AS reference_price,
       QUANTILE_CONT(unit_price,0.25) AS competitive_price,
       COUNT(DISTINCT supplier_id) AS n_suppliers,
       (COUNT(*)>=20 AND COUNT(DISTINCT supplier_id)>=2) AS benchmarkable
FROM pos_ext GROUP BY item, region_tier;

CREATE OR REPLACE TEMP VIEW on_ref AS
SELECT item, region_tier, MEDIAN(unit_price) AS on_contract_ref
FROM pos_ext WHERE contract_status='On-Contract' GROUP BY item, region_tier;

WITH
price_lever AS (   -- on-contract, price -> reference
    SELECT SUM(GREATEST((p.unit_price - b.reference_price)*p.quantity,0)) AS gross
    FROM pos_ext p JOIN benchmark b USING (item, region_tier)
    WHERE b.benchmarkable AND p.contract_status='On-Contract'
      AND p.unit_price > b.reference_price*1.10),
compliance_lever AS (  -- off-contract, price -> on-contract reference
    SELECT SUM(GREATEST((p.unit_price - o.on_contract_ref)*p.quantity,0)) AS gross
    FROM pos_ext p JOIN on_ref o USING (item, region_tier)
    WHERE p.contract_status='Off-Contract'),
consolidation_lever AS (  -- fragmented items, reference -> best-in-class
    SELECT SUM(CASE WHEN p.unit_price > b.competitive_price
               THEN GREATEST(b.reference_price - b.competitive_price,0)*p.quantity*0.60
               ELSE 0 END) AS gross
    FROM pos_ext p JOIN benchmark b USING (item, region_tier)
    WHERE b.benchmarkable AND b.n_suppliers >= 3)
SELECT 'price_negotiation'      AS lever, ROUND((SELECT gross FROM price_lever),0)        AS gross_gap,
       ROUND(0.50*(SELECT gross FROM price_lever),0)                                      AS modeled_base
UNION ALL SELECT 'contract_compliance', ROUND((SELECT gross FROM compliance_lever),0),
       ROUND(0.50*(SELECT gross FROM compliance_lever),0)
UNION ALL SELECT 'supplier_consolidation', ROUND((SELECT gross FROM consolidation_lever),0),
       ROUND(0.50*(SELECT gross FROM consolidation_lever),0)
ORDER BY gross_gap DESC;

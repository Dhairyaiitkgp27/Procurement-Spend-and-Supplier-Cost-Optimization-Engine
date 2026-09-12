-- ============================================================================
-- 03_contract_compliance.sql  —  On/off-contract split & maverick premium
-- Maverick premium = off-contract spend paid above the ON-contract reference.
-- ============================================================================

-- Overall + per-category compliance rate by spend
SELECT category,
       ROUND(SUM(line_spend),0)                                            AS total_spend,
       ROUND(SUM(CASE WHEN contract_status='On-Contract' THEN line_spend END),0) AS on_contract_spend,
       ROUND(100.0*SUM(CASE WHEN contract_status='On-Contract' THEN line_spend ELSE 0 END)
             /SUM(line_spend), 2)                                          AS compliance_pct
FROM pos
GROUP BY ROLLUP(category)
ORDER BY total_spend DESC NULLS FIRST;

-- Modeled maverick premium: off-contract lines priced above on-contract median
WITH on_ref AS (
    SELECT item, region_tier, MEDIAN(unit_price) AS on_contract_ref
    FROM pos_ext WHERE contract_status='On-Contract'
    GROUP BY item, region_tier
)
SELECT p.category,
       ROUND(SUM(p.line_spend),0)                                              AS off_contract_spend,
       ROUND(SUM(GREATEST((p.unit_price - o.on_contract_ref) * p.quantity, 0)),0) AS addressable_maverick_premium
FROM pos_ext p
JOIN on_ref o USING (item, region_tier)
WHERE p.contract_status='Off-Contract'
GROUP BY p.category
ORDER BY addressable_maverick_premium DESC;

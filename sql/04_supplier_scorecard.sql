-- ============================================================================
-- 04_supplier_scorecard.sql  —  Delivery / quality / compliance metrics
-- Sub-scores mirror src/supplier_scorecard.py (SPI weighting done in Python).
-- ============================================================================
SELECT supplier_id, supplier_name,
       ROUND(SUM(line_spend),0)                          AS spend,
       COUNT(*)                                          AS lines,
       ROUND(AVG(CASE WHEN on_time THEN 1.0 ELSE 0 END),4) AS otd_rate,
       ROUND(AVG(CASE WHEN is_defect THEN 1.0 ELSE 0 END),4) AS defect_rate,
       ROUND(AVG(CASE WHEN contract_status='On-Contract' THEN 1.0 ELSE 0 END),4) AS on_contract_rate,
       ROUND(STDDEV_POP(delay_days),2)                   AS delay_volatility,
       -- documented sub-scores (0-100)
       ROUND(100*AVG(CASE WHEN on_time THEN 1.0 ELSE 0 END),1)               AS delivery_score,
       ROUND(GREATEST(0, 100*(1 - AVG(CASE WHEN is_defect THEN 1.0 ELSE 0 END)/0.12)),1) AS quality_score,
       ROUND(100*AVG(CASE WHEN contract_status='On-Contract' THEN 1.0 ELSE 0 END),1)     AS compliance_score
FROM pos
GROUP BY supplier_id, supplier_name
HAVING SUM(line_spend) >= 250000
ORDER BY spend DESC
LIMIT 25;

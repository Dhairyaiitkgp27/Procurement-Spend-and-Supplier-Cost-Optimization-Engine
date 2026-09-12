# CV Bullets — Procurement Spend & Supplier Cost Optimization

Exactly five bullets, each using numbers computed by the pipeline (synthetic,
reproducible dataset; savings are modeled opportunity).

1. Built an end-to-end procurement cost-optimization engine in Python analyzing
   **$692.8M** of spend across **46,424 PO lines**,
   **106 suppliers** and **10 categories**,
   benchmarking every supplier price within (item, region) peer groups to identify a
   **$92.7M savings gap** and **$46.4M
   (6.69% of spend) of modeled savings** at realistic capture.

2. Engineered a five-lever savings model on **non-overlapping price gaps**
   (price renegotiation, contract-compliance recovery, supplier consolidation,
   demand aggregation, payment-term optimization), cross-validated in SQL, quantifying
   **$51.8M** of addressable maverick-spend leakage from a
   **53% contract-compliance rate** vs a 90% target.

3. Designed a weighted **Supplier Performance Index** and a five-factor supplier
   **risk model** over 106 suppliers, ranking 105
   into tiers and flagging **20 high/critical-risk
   suppliers** ($184.0M of spend) and single-source exposure.

4. Implemented a rule-based recommendation and negotiation-prioritization engine that
   assigns every supplier a strategic action (**12 REPLACE,
   19 NEGOTIATE, 50 CONSOLIDATE,
   9 RETAIN**) and ranks a **Top-10 negotiation list covering
   32.27% of spend**, with conservative/base/aggressive scenarios
   ($15.5M–$67.5M modeled).

5. Delivered a reproducible analytics stack — data-quality remediation (score
   **98/100**), a DuckDB SQL layer, a **pytest** validation suite, an
   interactive **Streamlit + Plotly** executive dashboard (7 pages) and a Power BI
   star-schema export — driven entirely by a single config file.

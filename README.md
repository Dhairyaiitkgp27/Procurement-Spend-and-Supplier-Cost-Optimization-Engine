# Procurement Spend & Supplier Cost Optimization Engine

An end-to-end procurement analytics engine that ingests a raw purchase-order
ledger and produces a full cost-optimization program: data-quality remediation,
spend analytics, price benchmarking, contract-compliance analysis, supplier
scorecards, supplier risk scoring, a five-lever savings engine, negotiation
prioritization, rule-based strategic recommendations, scenario optimization, and
an interactive executive dashboard.

> **Data disclaimer.** The dataset in this project is **synthetic**, generated with a fixed random seed to be realistic and fully reproducible. It does **not** represent any real company. All savings figures are **modeled / estimated opportunity**, not realized savings.

## Headline results (modeled)

| Metric | Value |
|---|---|
| Total spend analyzed | **$692.8M** across 46,424 PO lines |
| Suppliers / categories / business units | 106 / 10 / 5 |
| Data-quality score after remediation | 98.4 / 100 (756 rows removed) |
| Modeled gross savings gap | **$92.7M** |
| Modeled savings (base, 50% capture) | **$46.4M** (6.69% of spend) |
| Scenario range (period) | $15.5M → $44.4M → $67.5M |
| Suppliers flagged REPLACE / NEGOTIATE | 12 / 19 |

## Project structure

```
procurement-optimization/
├── config.yaml              # every tunable assumption (nothing hard-coded in logic)
├── requirements.txt
├── data/
│   ├── raw/                 # generated raw ledger + supplier ground-truth
│   └── processed/           # cleaned ledger
├── sql/                     # DuckDB analysis queries (spend, benchmarking, compliance, ...)
├── src/                     # analytics package (one module per phase)
│   ├── config.py            # paths, config loader + validation, logging, formatting
│   ├── data_generation.py   # reproducible synthetic ledger with injected inefficiencies
│   ├── data_quality.py      # Phase 1
│   ├── spend_analysis.py    # Phase 2
│   ├── price_benchmarking.py# Phase 3
│   ├── contract_compliance.py# Phase 4
│   ├── supplier_scorecard.py# Phase 5
│   ├── supplier_risk.py     # Phase 6
│   ├── savings_engine.py    # Phase 7 (5 non-overlapping levers)
│   ├── negotiation.py       # Phase 8
│   ├── recommendations.py   # Phase 9
│   ├── scenarios.py         # Phase 10
│   ├── pipeline.py          # orchestrator -> consolidated_kpis.json
│   ├── run_sql.py           # executes the SQL layer via DuckDB
│   ├── export_star_schema.py# Power BI star-schema export
│   └── generate_docs.py     # regenerates these markdown docs from outputs
├── dashboard/app.py         # Phase 11 — Streamlit + Plotly (7 pages)
├── tests/                   # pytest suite (data quality, reconciliation, savings, scenarios)
├── outputs/                 # consolidated_kpis.json, tables/, powerbi/
└── notebooks/               # walkthrough
```

## How to run

```bash
pip install -r requirements.txt

# 1) run the full analytics pipeline (generates data + all outputs)
python -m src.pipeline

# 2) (optional) execute the SQL analysis layer
python -m src.run_sql

# 3) (optional) export the Power BI star schema
python -m src.export_star_schema

# 4) regenerate the markdown deliverables from the outputs
python -m src.generate_docs

# 5) launch the executive dashboard
streamlit run dashboard/app.py

# run the tests
pytest -q
```

## Methodology (short)

Prices are benchmarked within **(item, region cost-tier)** peer groups so that a
Chinese supplier is compared to other low-cost-region suppliers, not to a German
one. The **reference price** is the group median and the **best-in-class price**
is the 25th percentile. Savings use a deliberately **non-overlapping five-lever
decomposition** (see `config.yaml`) so lever values can be summed without double
counting, and each lever is reported at conservative / base / aggressive capture
rates (25 / 50 / 75%). See `RESULTS.md` for the full numbers and
`EXECUTIVE_SUMMARY.md` for the narrative.

All thresholds, weights and capture rates live in `config.yaml`; the code reads
them at runtime, and `src/config.py` validates that scorecard, risk and
negotiation weights each sum to 1.0.

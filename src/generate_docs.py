"""Generate all markdown deliverables from the pipeline outputs.

Every number is read from outputs/consolidated_kpis.json and outputs/tables/*.csv
so the documents can never drift from the analysis. Run AFTER the pipeline:

    python -m src.pipeline && python -m src.generate_docs
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .config import PATHS

ROOT = PATHS["root"]
K = json.loads((PATHS["outputs"] / "consolidated_kpis.json").read_text())


def _t(name):
    return pd.read_csv(PATHS["tables"] / f"{name}.csv")


def money(x, dp=1):
    x = float(x); a = abs(x)
    if a >= 1e9: return f"${x/1e9:.{dp}f}B"
    if a >= 1e6: return f"${x/1e6:.{dp}f}M"
    if a >= 1e3: return f"${x/1e3:.0f}K"
    return f"${x:,.0f}"


def df_to_md(df, cols=None, headers=None, money_cols=(), pct_cols=(), round_cols=()):
    df = df.copy()
    if cols: df = df[cols]
    for c in money_cols:
        if c in df: df[c] = df[c].map(lambda v: money(v))
    for c in pct_cols:
        if c in df: df[c] = (df[c].astype(float) * 100).round(1).astype(str) + "%"
    for c in round_cols:
        if c in df: df[c] = df[c].astype(float).round(1)
    head = headers or list(df.columns)
    out = ["| " + " | ".join(str(h) for h in head) + " |",
           "|" + "|".join(["---"] * len(head)) + "|"]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(str(v) for v in r.values) + " |")
    return "\n".join(out)


# convenience handles
S, B, C = K["spend"], K["benchmarking"], K["compliance"]
SC, R, SV = K["scorecard"], K["risk"], K["savings"]
RC, NG, SN = K["recommendations"], K["negotiation"], K["scenarios"]
DQ = K["data_quality"]
DISC = ("> **Data disclaimer.** The dataset in this project is **synthetic**, generated "
        "with a fixed random seed to be realistic and fully reproducible. It does **not** "
        "represent any real company. All savings figures are **modeled / estimated "
        "opportunity**, not realized savings.")


def write(path, text):
    Path(ROOT / path).write_text(text.rstrip() + "\n")
    print("wrote", path)


# ============================== README =====================================
def readme():
    return f"""# Procurement Spend & Supplier Cost Optimization Engine

An end-to-end procurement analytics engine that ingests a raw purchase-order
ledger and produces a full cost-optimization program: data-quality remediation,
spend analytics, price benchmarking, contract-compliance analysis, supplier
scorecards, supplier risk scoring, a five-lever savings engine, negotiation
prioritization, rule-based strategic recommendations, scenario optimization, and
an interactive executive dashboard.

{DISC}

## Headline results (modeled)

| Metric | Value |
|---|---|
| Total spend analyzed | **{money(S['total_spend'])}** across {S['po_line_count']:,} PO lines |
| Suppliers / categories / business units | {S['supplier_count']} / {S['category_count']} / {S['business_unit_count']} |
| Data-quality score after remediation | {DQ['dq_score']:.1f} / 100 ({DQ['rows_removed']:,} rows removed) |
| Modeled gross savings gap | **{money(SV['cost_savings_gross_gap'])}** |
| Modeled savings (base, 50% capture) | **{money(SV['cost_savings_base'])}** ({SV['cost_savings_base_pct_of_spend']}% of spend) |
| Scenario range (period) | {money(SN['conservative_period'])} → {money(SN['base_period'])} → {money(SN['aggressive_period'])} |
| Suppliers flagged REPLACE / NEGOTIATE | {RC.get('n_replace',0)} / {RC.get('n_negotiate',0)} |

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
"""


# ============================== RESULTS ====================================
def results_md():
    lev = _t("savings_by_lever").sort_values("gross_gap", ascending=False)
    lev["lever"] = lev["lever"].str.replace("_", " ").str.title()
    scen = _t("scenario_optimization")
    tgt = _t("top_negotiation_targets")
    rsum = _t("recommendation_summary")
    cat = _t("spend_by_category").sort_values("spend", ascending=False)

    lev_md = df_to_md(lev, cols=["lever", "opportunities", "current_spend",
                                 "gross_gap", "savings_conservative", "savings_base",
                                 "savings_aggressive"],
                      headers=["Lever", "Opportunities", "Addressable spend", "Gross gap",
                               "Conservative (25%)", "Base (50%)", "Aggressive (75%)"],
                      money_cols=["current_spend", "gross_gap", "savings_conservative",
                                  "savings_base", "savings_aggressive"])
    scen_md = df_to_md(scen, cols=["scenario", "levers", "capture_rate", "cost_savings_period",
                                   "cost_savings_annualized", "savings_pct_of_spend",
                                   "suppliers_affected"],
                       headers=["Scenario", "Levers", "Capture", "Savings (period)",
                                "Savings (annualized)", "% of spend", "Suppliers"],
                       money_cols=["cost_savings_period", "cost_savings_annualized"])
    tgt_md = df_to_md(tgt.head(10),
                      cols=["priority_rank", "supplier_name", "category", "current_spend",
                            "price_premium", "modeled_savings_base",
                            "on_time_delivery_rate", "recommended_action"],
                      headers=["#", "Supplier", "Category", "Spend", "Price premium",
                               "Modeled savings", "OTD", "Action"],
                      money_cols=["current_spend", "modeled_savings_base"],
                      pct_cols=["price_premium", "on_time_delivery_rate"])
    rec_md = df_to_md(rsum, cols=["recommendation", "suppliers", "spend", "modeled_savings_base"],
                      headers=["Action", "Suppliers", "Spend", "Modeled savings"],
                      money_cols=["spend", "modeled_savings_base"])
    cat_md = df_to_md(cat, cols=["category", "spend"], headers=["Category", "Spend"],
                      money_cols=["spend"])

    return f"""# Results — Procurement Spend & Supplier Cost Optimization

{DISC}

All figures below are computed by the pipeline from the cleaned ledger and
written to `outputs/consolidated_kpis.json`. Re-running `python -m src.pipeline`
reproduces them exactly (fixed seed = {K['meta']['seed']}).

## 1. Data quality (Phase 1)

Raw ledger of **{DQ['raw_rows']:,}** PO lines with deliberately injected defects
(duplicates, missing keys, non-positive quantities/prices, impossible dates,
extreme price outliers, malformed contract flags). After remediation:

- Clean ledger: **{DQ['clean_rows']:,}** lines · removed **{DQ['rows_removed']:,}** · repaired **{DQ['rows_repaired']:,}**
- **Data-quality score: {DQ['dq_score']:.1f} / 100**

## 2. Spend analytics (Phase 2)

- Total spend analyzed: **{money(S['total_spend'])}** over ~{SV['analyzed_years']} years
- **{S['po_count']:,}** purchase orders · **{S['po_line_count']:,}** lines · avg line {money(S['avg_line_value'],0)}
- **{S['supplier_count']}** suppliers · **{S['category_count']}** categories · **{S['business_unit_count']}** business units · **{S['country_count']}** countries
- Spend concentration: **{S['suppliers_for_80pct_spend']} suppliers ({S['suppliers_for_80pct_pct']:.1f}%)** account for 80% of spend; top-10 share **{S['top10_supplier_spend_share']*100:.1f}%**; supplier HHI **{S['supplier_spend_hhi']:.4f}**

**Spend by category**

{cat_md}

## 3. Price benchmarking (Phase 3)

Benchmarked within (item, region cost-tier) peer groups; reference = median,
best-in-class = 25th percentile.

- Benchmarkable groups: **{B['benchmarkable_groups']}**, covering **{B['benchmarkable_spend_share']*100:.1f}%** of spend
- Overpriced supplier–item combinations: **{B['overpriced_supplier_item_combos']}** across **{B['n_overpriced_suppliers']}** suppliers
- Persistent-premium suppliers (structurally expensive): **{B['n_persistent_premium_suppliers']}**
- Average overpriced premium: **{B['avg_overpriced_premium']*100:.1f}%**
- Gross price excess vs reference (pre-capture): **{money(B['total_excess_vs_reference'])}**

## 4. Contract compliance (Phase 4)

- Compliance by spend: **{C['compliance_rate_spend']*100:.1f}%** vs target **{C['compliance_target']*100:.0f}%**
- Off-contract (maverick) spend: **{money(C['off_contract_spend'])}**
- Addressable maverick premium (off-contract paid above on-contract prices): **{money(C['addressable_maverick_premium'])}**
- Suppliers below 50% compliance: **{C['n_suppliers_below_50pct_compliance']}**

## 5. Supplier scorecard (Phase 5)

Supplier Performance Index (SPI) = weighted cost, delivery, quality, compliance
and lead-time reliability sub-scores.

- Ranked suppliers: **{SC['ranked_suppliers']}** · average SPI **{SC['avg_spi']:.1f}/100**
- Tier A suppliers: **{SC['tier_A_suppliers']}** · Tier D: **{SC['tier_D_suppliers']}**
- Average on-time delivery: **{SC['avg_otd_rate']*100:.1f}%** · average defect rate **{SC['avg_defect_rate']*100:.2f}%**

## 6. Supplier risk (Phase 6)

Composite risk from delivery, quality, price-volatility, concentration and trend.

- CRITICAL: **{R['critical_suppliers']}** · HIGH: **{R['high_suppliers']}** · MEDIUM: **{R['medium_suppliers']}** · LOW: **{R['low_suppliers']}**
- Spend exposed to high/critical-risk suppliers: **{money(R['spend_at_high_or_critical'])}**
- Single-source items: **{R['single_source_items']}** worth **{money(R['single_source_item_spend'])}** · chronically-late suppliers: **{R['n_chronically_late']}**

## 7. Savings opportunity (Phase 7)

Five **non-overlapping** levers (each on a disjoint price gap):

{lev_md}

- **Modeled gross savings gap: {money(SV['cost_savings_gross_gap'])}**
- Base-case modeled savings (50% capture): **{money(SV['cost_savings_base'])}** — **{SV['cost_savings_base_pct_of_spend']}% of spend** (~{money(SV['cost_savings_base_annualized'])}/yr)
- Range: {money(SV['cost_savings_conservative'])} (conservative) → {money(SV['cost_savings_aggressive'])} (aggressive)
- Payment-terms financial value: **{money(SV['payment_terms_annual_value'])}/yr** (working capital + early-pay discounts)

## 8. Negotiation prioritization (Phase 8)

Priority = f(savings opportunity, spend, performance gap, negotiability). The
**Top 10 targets** cover **{money(NG['top_targets_spend'])}** of spend
(**{NG['top_targets_spend_share']}%**) and **{money(NG['top_targets_modeled_savings'])}**
of modeled savings.

{tgt_md}

## 9. Strategic recommendations (Phase 9)

{rec_md}

## 10. Scenario optimization (Phase 10)

{scen_md}

*Ordering is asserted monotonic (conservative ≤ base ≤ aggressive) by the engine.*
"""


# ============================ EXECUTIVE SUMMARY ============================
def exec_summary():
    tgt = _t("top_negotiation_targets").head(5)
    top_lines = []
    for _, r in tgt.iterrows():
        top_lines.append(
            f"- **{r['supplier_name']}** ({r['category']}) — {money(r['current_spend'])} spend, "
            f"{r['price_premium']*100:.0f}% above benchmark, ~{money(r['modeled_savings_base'])} "
            f"modeled savings → **{r['recommended_action']}**")
    return f"""# Executive Summary — Procurement Cost Optimization

*Prepared as a management-consulting style briefing. {K['meta']['project']}.*

{DISC}

## The situation

A multinational's procurement organization spends **{money(S['total_spend'])}** across
**{S['supplier_count']} suppliers**, **{S['category_count']} categories** and
**{S['business_unit_count']} business units** (~{SV['analyzed_years']} years of PO data,
{S['po_line_count']:,} lines). The spend base is only moderately consolidated
({S['suppliers_for_80pct_spend']} suppliers cover 80% of spend) and contract
discipline is weak: **only {C['compliance_rate_spend']*100:.0f}% of spend is on-contract**
against a 90% target.

## The opportunity (modeled)

Benchmarking every supplier price within its (item, region cost-tier) peer group
surfaces a **{money(SV['cost_savings_gross_gap'])} gross savings gap**. At a realistic
**50% capture**, that is **{money(SV['cost_savings_base'])} of modeled savings —
{SV['cost_savings_base_pct_of_spend']}% of spend (~{money(SV['cost_savings_base_annualized'])}/yr)**,
with a governance range of **{money(SN['conservative_period'])} → {money(SN['base_period'])} → {money(SN['aggressive_period'])}**
across conservative, base and aggressive scenarios. A further
**{money(SV['payment_terms_annual_value'])}/yr** of financial value sits in payment-term
optimization.

The single largest lever is **contract compliance**: redirecting maverick,
off-contract spend to negotiated prices is worth
{money(_t('savings_by_lever').set_index('lever').loc['contract_compliance','gross_gap'])}
gross on its own.

## Where to act first

Top negotiation targets (full list in `RESULTS.md`):

{chr(10).join(top_lines)}

## Recommended program

1. **Compliance first (highest ROI, lowest risk).** Route off-contract spend onto
   existing contracts and reference prices — the biggest, lowest-effort lever.
2. **Renegotiate the persistent overpayers.** {B['n_persistent_premium_suppliers']} suppliers
   are structurally above market; the Top-10 target list sequences them by value and negotiability.
3. **Consolidate fragmented categories** toward best-in-class suppliers where quality is comparable.
4. **De-risk the tail.** {R['critical_suppliers']+R['high_suppliers']} suppliers are high/critical
   risk ({money(R['spend_at_high_or_critical'])} of spend); {R['single_source_items']} single-source
   items ({money(R['single_source_item_spend'])}) need a dual-sourcing plan.
5. **Adopt the base scenario** as the target ({money(SN['base_period'])} modeled, balanced execution risk),
   with aggressive levers phased in as capability matures.

## Strategic dispositions

Of {S['supplier_count']} suppliers, the rule-based engine recommends
**REPLACE {RC.get('n_replace',0)}**, **NEGOTIATE {RC.get('n_negotiate',0)}**,
**CONSOLIDATE {RC.get('n_consolidate',0)}**, **RETAIN {RC.get('n_retain',0)}**,
**MONITOR {RC.get('n_monitor',0)}** — a concrete action for every supplier.

*All figures are modeled opportunity from a simulated dataset, intended to
demonstrate the methodology and quantify potential, not to assert booked savings.*
"""


# ============================ INTERVIEW Q&A ================================
def interview_qa():
    return f"""# Interview Q&A — Procurement Optimization Project

{DISC}

**Q1. What does this project do, in one line?**
It turns a raw purchase-order ledger into a full procurement cost-optimization
program — data cleaning, spend analytics, price benchmarking, compliance,
supplier scorecards and risk, a five-lever savings engine, negotiation
prioritization, strategic recommendations, scenarios and a dashboard — and
quantifies **{money(SV['cost_savings_base'])} of modeled savings ({SV['cost_savings_base_pct_of_spend']}% of {money(S['total_spend'])} spend)**.

**Q2. The data is synthetic — why, and is that a weakness?**
No real proprietary procurement ledger is public at this scale. I built a
seed-controlled generator that injects realistic structure *and* realistic
inefficiencies (overpriced archetypes, maverick spend, unreliable suppliers,
single-source items), then computed every number from that data. It makes the
project fully reproducible and lets me validate the analytics against a known
ground truth. Every deliverable labels savings as **modeled opportunity**, never
realized savings — the honesty is the point.

**Q3. How do you benchmark prices fairly?**
Within **(item, region cost-tier)** peer groups, so a low-cost-region supplier is
compared with its true peers, not a high-cost one. Reference price = group
median; best-in-class = 25th percentile. A group is only "benchmarkable" with
≥20 transactions and ≥2 suppliers — here that covers **{B['benchmarkable_spend_share']*100:.0f}% of spend**.

**Q4. Your five savings levers — don't they double-count?**
That's the crux. I defined them on **disjoint price gaps**: price negotiation
moves on-contract overpayers *to* the median; compliance moves *off-contract*
lines to on-contract prices; consolidation captures the residual median → best-in-class
gap on fragmented items; demand aggregation applies only to residual spend already
at/below reference; payment terms is pure financial value. Because the gaps don't
overlap, the lever values are additive. The SQL layer independently recomputes the
three main levers and reconciles to the Python engine.

**Q5. What are capture rates and why 25/50/75%?**
The gross gap is the theoretical maximum; you never capture all of it. Capture
rates model negotiation realism — conservative (25%), base (50%), aggressive
(75%). They map to the three scenarios: **{money(SN['conservative_period'])} → {money(SN['base_period'])} → {money(SN['aggressive_period'])}**.

**Q6. How is the Supplier Performance Index built?**
A 0–100 weighted score over five documented sub-scores — cost competitiveness
(30%), on-time delivery (20%), quality (20%), contract compliance (15%), lead-time
reliability (15%). Weights live in `config.yaml` and are validated to sum to 1.0.
Only suppliers above a spend threshold are ranked into tiers A–D. Average SPI here
is **{SC['avg_spi']:.1f}**.

**Q7. How does risk scoring work and what did it find?**
Composite of delivery, quality, price-volatility, concentration and trend risk,
banded LOW/MEDIUM/HIGH/CRITICAL. It flags **{R['critical_suppliers']} critical** and
**{R['high_suppliers']} high-risk** suppliers ({money(R['spend_at_high_or_critical'])} of spend)
and **{R['single_source_items']} single-source items** — including one specialty item
deliberately sole-sourced in the data, which the engine correctly surfaces.

**Q8. How do you decide REPLACE vs NEGOTIATE vs RETAIN?**
A transparent rule cascade, not a black box: critical risk or (poor quality + poor
delivery + above-market price) → REPLACE; good performer but expensive → NEGOTIATE;
minor player in a fragmented category → CONSOLIDATE; top-quartile & competitive &
low-risk → RETAIN; else MONITOR. Every supplier gets a recommendation *and a reason
string*. Result: {RC.get('n_replace',0)} REPLACE, {RC.get('n_negotiate',0)} NEGOTIATE,
{RC.get('n_consolidate',0)} CONSOLIDATE, {RC.get('n_retain',0)} RETAIN, {RC.get('n_monitor',0)} MONITOR.

**Q9. How are negotiation targets prioritized?**
A weighted score over savings opportunity (40%), spend (25%), performance gap
(20%) and negotiability (15%) — where negotiability rewards uncommitted spend and
category competition and penalizes sole-source dependence. The Top-10 covers
**{NG['top_targets_spend_share']}% of spend**.

**Q10. How did you validate correctness?**
A `pytest` suite: data-quality checks catch the injected defects (duplicates
removed essentially exactly), spend reconciles to the total from every angle,
savings are non-negative and never exceed the spend at stake, capture is monotonic
per opportunity, scenarios are monotonically ordered, and every REPLACE is
justified by the underlying metrics. The SQL and Python savings independently agree.

**Q11. What's the tech stack and architecture?**
Python (pandas, NumPy, SciPy, scikit-learn), a DuckDB SQL layer over the cleaned
CSV, Streamlit + Plotly for the 7-page dashboard, and a Power BI star-schema
export. One module per phase, an orchestrator that emits a single
`consolidated_kpis.json`, and a doc generator so the written deliverables are
regenerated from that JSON — the numbers can't drift.

**Q12. If this were real, what would you do next?**
Replace the generator with the real ERP feed, calibrate capture rates against
historically realized savings, add supplier-quoted lead times and external market
indices to the benchmark, and track realized-vs-modeled savings over time to close
the loop.
"""


# ============================== CV BULLETS =================================
def cv_bullets():
    lev = _t("savings_by_lever").set_index("lever")
    compliance_gap = lev.loc["contract_compliance", "gross_gap"]
    return f"""# CV Bullets — Procurement Spend & Supplier Cost Optimization

Exactly five bullets, each using numbers computed by the pipeline (synthetic,
reproducible dataset; savings are modeled opportunity).

1. Built an end-to-end procurement cost-optimization engine in Python analyzing
   **{money(S['total_spend'])}** of spend across **{S['po_line_count']:,} PO lines**,
   **{S['supplier_count']} suppliers** and **{S['category_count']} categories**,
   benchmarking every supplier price within (item, region) peer groups to identify a
   **{money(SV['cost_savings_gross_gap'])} savings gap** and **{money(SV['cost_savings_base'])}
   ({SV['cost_savings_base_pct_of_spend']}% of spend) of modeled savings** at realistic capture.

2. Engineered a five-lever savings model on **non-overlapping price gaps**
   (price renegotiation, contract-compliance recovery, supplier consolidation,
   demand aggregation, payment-term optimization), cross-validated in SQL, quantifying
   **{money(compliance_gap)}** of addressable maverick-spend leakage from a
   **{K['compliance']['compliance_rate_spend']*100:.0f}% contract-compliance rate** vs a 90% target.

3. Designed a weighted **Supplier Performance Index** and a five-factor supplier
   **risk model** over {S['supplier_count']} suppliers, ranking {SC['ranked_suppliers']}
   into tiers and flagging **{R['critical_suppliers']+R['high_suppliers']} high/critical-risk
   suppliers** ({money(R['spend_at_high_or_critical'])} of spend) and single-source exposure.

4. Implemented a rule-based recommendation and negotiation-prioritization engine that
   assigns every supplier a strategic action (**{RC.get('n_replace',0)} REPLACE,
   {RC.get('n_negotiate',0)} NEGOTIATE, {RC.get('n_consolidate',0)} CONSOLIDATE,
   {RC.get('n_retain',0)} RETAIN**) and ranks a **Top-10 negotiation list covering
   {NG['top_targets_spend_share']}% of spend**, with conservative/base/aggressive scenarios
   ({money(SN['conservative_period'])}–{money(SN['aggressive_period'])} modeled).

5. Delivered a reproducible analytics stack — data-quality remediation (score
   **{DQ['dq_score']:.0f}/100**), a DuckDB SQL layer, a **pytest** validation suite, an
   interactive **Streamlit + Plotly** executive dashboard (7 pages) and a Power BI
   star-schema export — driven entirely by a single config file.
"""


# ============================ POWER BI GUIDE ==============================
def powerbi_guide():
    return f"""# Power BI Guide — Star Schema & DAX

`python -m src.export_star_schema` writes an import-ready model to
`outputs/powerbi/`. A `.pbix` can't be authored in this environment, so this
documents the model and the measures to recreate the dashboard in Power BI.

{DISC}

## Model (star schema)

- **fact_po_lines** (grain = one PO line) — `line_spend`, `quantity`, `unit_price`,
  `on_time`, `is_defect`, `delay_days`, `contract_status`, plus `supplier_id`,
  `category`, `business_unit`, `date_key`.
- **dim_supplier** — SPI, tier, sub-scores, OTD/defect rates, composite risk & band,
  price premium/index, strategic recommendation, country.
- **dim_category**, **dim_business_unit**, **dim_date** (with year/quarter/month).

Relationships: `fact_po_lines[supplier_id] → dim_supplier`,
`[category] → dim_category`, `[business_unit] → dim_business_unit`,
`[date_key] → dim_date[date_key]` (single-direction, one-to-many).

## Core DAX measures

```DAX
Total Spend       = SUM ( fact_po_lines[line_spend] )
On-Contract Spend = CALCULATE ( [Total Spend], fact_po_lines[contract_status] = "On-Contract" )
Compliance %      = DIVIDE ( [On-Contract Spend], [Total Spend] )
On-Time Delivery %= AVERAGE ( fact_po_lines[on_time] )
Defect Rate       = AVERAGE ( fact_po_lines[is_defect] )
Supplier Count    = DISTINCTCOUNT ( fact_po_lines[supplier_id] )

-- Pareto: cumulative spend share by supplier
Cumulative Spend %% =
VAR curr = [Total Spend]
RETURN DIVIDE (
    SUMX ( FILTER ( ALLSELECTED ( dim_supplier ), [Total Spend] >= curr ), [Total Spend] ),
    CALCULATE ( [Total Spend], ALLSELECTED ( dim_supplier ) ) )

-- Spend exposed to high/critical-risk suppliers
Spend at Risk =
CALCULATE ( [Total Spend], dim_supplier[risk_band] IN {{ "HIGH", "CRITICAL" }} )
```

## Suggested pages
Mirror the Streamlit app: Executive Overview (KPI cards + savings-by-lever +
scenarios), Spend Analytics (category bar + supplier Pareto + monthly trend),
Supplier Scorecard (SPI histogram + tier + cost-vs-delivery scatter), Savings
Opportunity, Negotiation Targets (supplier×category matrix), Supplier Risk, and
the Executive Action Plan (recommendation breakdown).

Current headline for validation: total spend **{money(S['total_spend'])}**,
compliance **{K['compliance']['compliance_rate_spend']*100:.0f}%**, modeled base savings
**{money(SV['cost_savings_base'])}**.
"""


def main():
    write("README.md", readme())
    write("RESULTS.md", results_md())
    write("EXECUTIVE_SUMMARY.md", exec_summary())
    write("INTERVIEW_QA.md", interview_qa())
    write("CV_BULLETS.md", cv_bullets())
    write("POWERBI_GUIDE.md", powerbi_guide())
    print("\nAll documents generated from outputs/consolidated_kpis.json")


if __name__ == "__main__":
    main()

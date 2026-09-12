# Interview Q&A — Procurement Optimization Project

> **Data disclaimer.** The dataset in this project is **synthetic**, generated with a fixed random seed to be realistic and fully reproducible. It does **not** represent any real company. All savings figures are **modeled / estimated opportunity**, not realized savings.

**Q1. What does this project do, in one line?**
It turns a raw purchase-order ledger into a full procurement cost-optimization
program — data cleaning, spend analytics, price benchmarking, compliance,
supplier scorecards and risk, a five-lever savings engine, negotiation
prioritization, strategic recommendations, scenarios and a dashboard — and
quantifies **$46.4M of modeled savings (6.69% of $692.8M spend)**.

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
≥20 transactions and ≥2 suppliers — here that covers **89% of spend**.

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
(75%). They map to the three scenarios: **$15.5M → $44.4M → $67.5M**.

**Q6. How is the Supplier Performance Index built?**
A 0–100 weighted score over five documented sub-scores — cost competitiveness
(30%), on-time delivery (20%), quality (20%), contract compliance (15%), lead-time
reliability (15%). Weights live in `config.yaml` and are validated to sum to 1.0.
Only suppliers above a spend threshold are ranked into tiers A–D. Average SPI here
is **72.3**.

**Q7. How does risk scoring work and what did it find?**
Composite of delivery, quality, price-volatility, concentration and trend risk,
banded LOW/MEDIUM/HIGH/CRITICAL. It flags **2 critical** and
**18 high-risk** suppliers ($184.0M of spend)
and **2 single-source items** — including one specialty item
deliberately sole-sourced in the data, which the engine correctly surfaces.

**Q8. How do you decide REPLACE vs NEGOTIATE vs RETAIN?**
A transparent rule cascade, not a black box: critical risk or (poor quality + poor
delivery + above-market price) → REPLACE; good performer but expensive → NEGOTIATE;
minor player in a fragmented category → CONSOLIDATE; top-quartile & competitive &
low-risk → RETAIN; else MONITOR. Every supplier gets a recommendation *and a reason
string*. Result: 12 REPLACE, 19 NEGOTIATE,
50 CONSOLIDATE, 9 RETAIN, 16 MONITOR.

**Q9. How are negotiation targets prioritized?**
A weighted score over savings opportunity (40%), spend (25%), performance gap
(20%) and negotiability (15%) — where negotiability rewards uncommitted spend and
category competition and penalizes sole-source dependence. The Top-10 covers
**32.27% of spend**.

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

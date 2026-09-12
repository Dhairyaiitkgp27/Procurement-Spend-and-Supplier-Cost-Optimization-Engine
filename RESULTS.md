# Results — Procurement Spend & Supplier Cost Optimization

> **Data disclaimer.** The dataset in this project is **synthetic**, generated with a fixed random seed to be realistic and fully reproducible. It does **not** represent any real company. All savings figures are **modeled / estimated opportunity**, not realized savings.

All figures below are computed by the pipeline from the cleaned ledger and
written to `outputs/consolidated_kpis.json`. Re-running `python -m src.pipeline`
reproduces them exactly (fixed seed = 20260610).

## 1. Data quality (Phase 1)

Raw ledger of **47,180** PO lines with deliberately injected defects
(duplicates, missing keys, non-positive quantities/prices, impossible dates,
extreme price outliers, malformed contract flags). After remediation:

- Clean ledger: **46,424** lines · removed **756** · repaired **130**
- **Data-quality score: 98.4 / 100**

## 2. Spend analytics (Phase 2)

- Total spend analyzed: **$692.8M** over ~3.49 years
- **18,363** purchase orders · **46,424** lines · avg line $15K
- **106** suppliers · **10** categories · **5** business units · **10** countries
- Spend concentration: **43 suppliers (40.6%)** account for 80% of spend; top-10 share **44.1%**; supplier HHI **0.0287**

**Spend by category**

| Category | Spend |
|---|---|
| Raw_Metals | $112.5M |
| Facilities | $105.6M |
| Raw_Polymers | $102.9M |
| Logistics_Freight | $95.3M |
| IT_Software | $75.2M |
| IT_Hardware | $62.7M |
| Packaging | $56.2M |
| Professional_Services | $42.8M |
| MRO | $27.5M |
| Office_Supplies | $12.1M |

## 3. Price benchmarking (Phase 3)

Benchmarked within (item, region cost-tier) peer groups; reference = median,
best-in-class = 25th percentile.

- Benchmarkable groups: **81**, covering **88.6%** of spend
- Overpriced supplier–item combinations: **284** across **51** suppliers
- Persistent-premium suppliers (structurally expensive): **28**
- Average overpriced premium: **22.0%**
- Gross price excess vs reference (pre-capture): **$41.8M**

## 4. Contract compliance (Phase 4)

- Compliance by spend: **52.6%** vs target **90%**
- Off-contract (maverick) spend: **$328.1M**
- Addressable maverick premium (off-contract paid above on-contract prices): **$51.8M**
- Suppliers below 50% compliance: **44**

## 5. Supplier scorecard (Phase 5)

Supplier Performance Index (SPI) = weighted cost, delivery, quality, compliance
and lead-time reliability sub-scores.

- Ranked suppliers: **105** · average SPI **72.3/100**
- Tier A suppliers: **27** · Tier D: **26**
- Average on-time delivery: **82.5%** · average defect rate **2.89%**

## 6. Supplier risk (Phase 6)

Composite risk from delivery, quality, price-volatility, concentration and trend.

- CRITICAL: **2** · HIGH: **18** · MEDIUM: **36** · LOW: **50**
- Spend exposed to high/critical-risk suppliers: **$184.0M**
- Single-source items: **2** worth **$58.1M** · chronically-late suppliers: **21**

## 7. Savings opportunity (Phase 7)

Five **non-overlapping** levers (each on a disjoint price gap):

| Lever | Opportunities | Addressable spend | Gross gap | Conservative (25%) | Base (50%) | Aggressive (75%) |
|---|---|---|---|---|---|---|
| Contract Compliance | 198 | $272.4M | $51.8M | $12.9M | $25.9M | $38.8M |
| Supplier Consolidation | 204 | $474.5M | $24.8M | $6.2M | $12.4M | $18.6M |
| Price Negotiation | 125 | $65.9M | $12.2M | $3.0M | $6.1M | $9.1M |
| Demand Aggregation | 145 | $264.9M | $4.0M | $993K | $2.0M | $3.0M |

- **Modeled gross savings gap: $92.7M**
- Base-case modeled savings (50% capture): **$46.4M** — **6.69% of spend** (~$13.3M/yr)
- Range: $23.2M (conservative) → $69.6M (aggressive)
- Payment-terms financial value: **$1.1M/yr** (working capital + early-pay discounts)

## 8. Negotiation prioritization (Phase 8)

Priority = f(savings opportunity, spend, performance gap, negotiability). The
**Top 10 targets** cover **$223.5M** of spend
(**32.27%**) and **$20.9M**
of modeled savings.

| # | Supplier | Category | Spend | Price premium | Modeled savings | OTD | Action |
|---|---|---|---|---|---|---|---|
| 1 | Keystone Components | Facilities | $39.8M | 25.4% | $6.3M | 83.7% | NEGOTIATE |
| 2 | Atlas Solutions | Raw_Metals | $56.6M | 10.3% | $4.5M | 61.1% | REPLACE |
| 3 | Cascade Group | Logistics_Freight | $18.8M | 41.1% | $3.5M | 44.9% | REPLACE |
| 4 | Vertex Solutions | IT_Software | $14.2M | 22.4% | $1.8M | 59.0% | REPLACE |
| 5 | Quantum Global | Logistics_Freight | $10.1M | 19.6% | $1.3M | 59.2% | REPLACE |
| 6 | Cascade Supply Co | Raw_Polymers | $52.3M | -2.3% | $812K | 95.5% | RETAIN |
| 7 | Vanguard Group | Facilities | $5.0M | 18.8% | $737K | 58.8% | REPLACE |
| 8 | Cascade Components | Raw_Metals | $3.7M | 7.1% | $280K | 55.2% | MONITOR |
| 9 | BlueRidge Industries | IT_Software | $16.7M | 5.2% | $974K | 77.1% | MONITOR |
| 10 | Pioneer Industries | Raw_Polymers | $6.3M | 24.5% | $780K | 58.5% | REPLACE |

## 9. Strategic recommendations (Phase 9)

| Action | Suppliers | Spend | Modeled savings |
|---|---|---|---|
| RETAIN | 9 | $174.7M | $4.7M |
| MONITOR | 16 | $145.8M | $6.8M |
| CONSOLIDATE | 50 | $143.5M | $6.6M |
| REPLACE | 12 | $130.7M | $14.4M |
| NEGOTIATE | 19 | $98.1M | $13.8M |

## 10. Scenario optimization (Phase 10)

| Scenario | Levers | Capture | Savings (period) | Savings (annualized) | % of spend | Suppliers |
|---|---|---|---|---|---|---|
| CONSERVATIVE | price, compliance | 0.25 | $15.5M | $4.4M | 2.23 | 103 |
| BASE | price, compliance, consolidation | 0.5 | $44.4M | $12.7M | 6.41 | 106 |
| AGGRESSIVE | price, compliance, consolidation, payment_terms | 0.75 | $67.5M | $19.3M | 9.74 | 106 |

*Ordering is asserted monotonic (conservative ≤ base ≤ aggressive) by the engine.*

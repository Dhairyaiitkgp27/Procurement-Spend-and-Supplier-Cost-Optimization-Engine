# Power BI Guide — Star Schema & DAX

`python -m src.export_star_schema` writes an import-ready model to
`outputs/powerbi/`. A `.pbix` can't be authored in this environment, so this
documents the model and the measures to recreate the dashboard in Power BI.

> **Data disclaimer.** The dataset in this project is **synthetic**, generated with a fixed random seed to be realistic and fully reproducible. It does **not** represent any real company. All savings figures are **modeled / estimated opportunity**, not realized savings.

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
CALCULATE ( [Total Spend], dim_supplier[risk_band] IN { "HIGH", "CRITICAL" } )
```

## Suggested pages
Mirror the Streamlit app: Executive Overview (KPI cards + savings-by-lever +
scenarios), Spend Analytics (category bar + supplier Pareto + monthly trend),
Supplier Scorecard (SPI histogram + tier + cost-vs-delivery scatter), Savings
Opportunity, Negotiation Targets (supplier×category matrix), Supplier Risk, and
the Executive Action Plan (recommendation breakdown).

Current headline for validation: total spend **$692.8M**,
compliance **53%**, modeled base savings
**$46.4M**.

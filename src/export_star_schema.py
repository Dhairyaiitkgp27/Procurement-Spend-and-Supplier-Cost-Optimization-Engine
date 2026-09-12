"""Export a Power BI-ready star schema from the cleaned ledger + phase outputs.

Because a .pbix cannot be authored in this environment, this produces the model
as CSVs (one fact + conformed dimensions) that import directly into Power BI /
Tableau. Suggested DAX measures are documented in POWERBI_GUIDE.md.

    python -m src.export_star_schema   ->   outputs/powerbi/*.csv
"""
from __future__ import annotations

import pandas as pd

from .config import PATHS, get_logger

log = get_logger("star_schema")


def run() -> None:
    out = PATHS["outputs"] / "powerbi"
    out.mkdir(parents=True, exist_ok=True)
    clean = pd.read_csv(PATHS["data_processed"] / "procurement_clean.csv",
                        parse_dates=["order_date", "promised_date", "delivery_date"])

    def t(name):
        p = PATHS["tables"] / f"{name}.csv"
        return pd.read_csv(p) if p.exists() else pd.DataFrame()

    # ---- FACT: PO line grain ----------------------------------------------
    fact = clean[["po_line_id", "po_id", "supplier_id", "category", "business_unit",
                  "item", "order_date", "quantity", "unit_price", "line_spend",
                  "payment_terms", "contract_status", "on_time", "is_defect",
                  "delay_days", "lead_time_days"]].copy()
    fact["date_key"] = fact["order_date"].dt.strftime("%Y%m%d").astype(int)
    fact.to_csv(out / "fact_po_lines.csv", index=False)

    # ---- DIM supplier (scorecard + risk + recommendation + price) ---------
    dim = t("supplier_scorecard")
    keep_sc = [c for c in ["supplier_id", "supplier_name", "spend", "spi",
                           "performance_tier", "cost_score", "delivery_score",
                           "quality_score", "compliance_score", "leadtime_score",
                           "otd_rate", "defect_rate", "on_contract_rate"] if c in dim.columns]
    dim = dim[keep_sc]
    risk = t("supplier_risk")[["supplier_id", "composite_risk", "risk_band",
                               "primary_risk_driver"]]
    rec = t("supplier_recommendations")[["supplier_id", "recommendation",
                                         "recommendation_reason", "primary_category"]]
    price = t("supplier_price_position")[["supplier_id", "weighted_price_premium",
                                          "weighted_price_index"]]
    dim = (dim.merge(risk, on="supplier_id", how="left")
              .merge(rec, on="supplier_id", how="left")
              .merge(price, on="supplier_id", how="left"))
    # attach country (modal country per supplier from ledger)
    ctry = (clean.groupby("supplier_id")["supplier_country"]
            .agg(lambda s: s.mode().iat[0]).reset_index())
    dim = dim.merge(ctry, on="supplier_id", how="left")
    dim.to_csv(out / "dim_supplier.csv", index=False)

    # ---- DIM category ------------------------------------------------------
    cat = (clean.groupby("category")
           .agg(total_spend=("line_spend", "sum"),
                suppliers=("supplier_id", "nunique"),
                lines=("po_line_id", "count")).reset_index())
    disp = t("category_price_dispersion")
    if not disp.empty:
        dcol = "category" if "category" in disp.columns else disp.columns[0]
        cat = cat.merge(disp, left_on="category", right_on=dcol, how="left")
    cat.to_csv(out / "dim_category.csv", index=False)

    # ---- DIM business unit -------------------------------------------------
    bu = (clean.groupby("business_unit")
          .agg(total_spend=("line_spend", "sum"),
               suppliers=("supplier_id", "nunique")).reset_index())
    bu.to_csv(out / "dim_business_unit.csv", index=False)

    # ---- DIM date ----------------------------------------------------------
    d = pd.DataFrame({"order_date": pd.date_range(clean["order_date"].min(),
                                                  clean["order_date"].max(), freq="D")})
    d["date_key"] = d["order_date"].dt.strftime("%Y%m%d").astype(int)
    d["year"] = d["order_date"].dt.year
    d["quarter"] = d["order_date"].dt.to_period("Q").astype(str)
    d["month"] = d["order_date"].dt.to_period("M").astype(str)
    d["month_name"] = d["order_date"].dt.strftime("%b %Y")
    d.to_csv(out / "dim_date.csv", index=False)

    log.info("Star schema exported -> %s (fact=%d rows, %d suppliers)",
             out, len(fact), len(dim))


if __name__ == "__main__":
    run()

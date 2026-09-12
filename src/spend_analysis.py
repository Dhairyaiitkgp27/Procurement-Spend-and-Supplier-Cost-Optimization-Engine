"""Phase 2 — Procurement spend analysis.

Descriptive spend cube, Pareto (80/20) analyses and concentration (HHI) risk.
All numbers are derived from the cleaned ledger produced by Phase 1.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger

log = get_logger("spend_analysis")


def _pareto(series: pd.Series, threshold: float = 0.80) -> pd.DataFrame:
    """Return a ranked frame with cumulative share and an 80% flag."""
    s = series.sort_values(ascending=False)
    total = s.sum()
    out = s.to_frame("spend")
    out["share"] = out["spend"] / total
    out["cum_share"] = out["share"].cumsum()
    out["rank"] = np.arange(1, len(out) + 1)
    # entities up to and including the one that crosses the threshold
    crossed = out["cum_share"] >= threshold
    cutoff_rank = int(crossed.idxmax() and out.loc[crossed, "rank"].min())
    out["within_80pct"] = out["rank"] <= cutoff_rank
    return out.reset_index()


def _hhi(series: pd.Series) -> float:
    """Herfindahl-Hirschman Index on spend shares (0-1)."""
    shares = series / series.sum()
    return float((shares ** 2).sum())


def run(clean: pd.DataFrame) -> dict:
    df = clean
    total_spend = df["line_spend"].sum()

    kpis = {
        "total_spend": float(total_spend),
        "po_count": int(df["po_id"].nunique()),
        "po_line_count": int(len(df)),
        "supplier_count": int(df["supplier_id"].nunique()),
        "category_count": int(df["category"].nunique()),
        "business_unit_count": int(df["business_unit"].nunique()),
        "country_count": int(df["supplier_country"].nunique()),
        "item_count": int(df["item"].nunique()),
        "total_quantity": float(df["quantity"].sum()),
        "avg_po_value": float(df.groupby("po_id")["line_spend"].sum().mean()),
        "avg_line_value": float(df["line_spend"].mean()),
        "spend_weighted_avg_unit_price": float(
            (df["unit_price"] * df["quantity"]).sum() / df["quantity"].sum()),
    }

    # ---- spend by dimension ------------------------------------------------
    by_supplier = (df.groupby(["supplier_id", "supplier_name"])
                   .agg(spend=("line_spend", "sum"),
                        lines=("po_line_id", "count"),
                        categories=("category", "nunique"))
                   .reset_index().sort_values("spend", ascending=False))
    by_category = (df.groupby("category")["line_spend"].sum()
                   .sort_values(ascending=False).reset_index(name="spend"))
    by_bu = (df.groupby("business_unit")["line_spend"].sum()
             .sort_values(ascending=False).reset_index(name="spend"))
    by_country = (df.groupby("supplier_country")["line_spend"].sum()
                  .sort_values(ascending=False).reset_index(name="spend"))
    by_item = (df.groupby(["category", "item"])["line_spend"].sum()
               .sort_values(ascending=False).reset_index(name="spend"))

    # ---- time series -------------------------------------------------------
    monthly = (df.groupby("order_month")["line_spend"].sum().reset_index(name="spend"))
    quarterly = (df.groupby("order_quarter")["line_spend"].sum().reset_index(name="spend"))
    monthly_by_cat = (df.groupby(["order_month", "category"])["line_spend"].sum()
                      .reset_index(name="spend"))

    # ---- Pareto ------------------------------------------------------------
    pareto_supplier = _pareto(by_supplier.set_index("supplier_name")["spend"])
    pareto_category = _pareto(by_category.set_index("category")["spend"])
    pareto_bu = _pareto(by_bu.set_index("business_unit")["spend"])

    n_sup_80 = int(pareto_supplier["within_80pct"].sum())
    n_cat_80 = int(pareto_category["within_80pct"].sum())

    # ---- concentration -----------------------------------------------------
    supplier_hhi = _hhi(by_supplier.set_index("supplier_id")["spend"])
    category_hhi = _hhi(by_category.set_index("category")["spend"])
    # supplier concentration WITHIN each category (single-source detection later)
    cat_supplier_hhi = (df.groupby("category")
                        .apply(lambda g: _hhi(g.groupby("supplier_id")["line_spend"].sum()),
                               include_groups=False)
                        .reset_index(name="supplier_hhi").sort_values("supplier_hhi", ascending=False))
    cat_supplier_hhi["n_suppliers"] = cat_supplier_hhi["category"].map(
        df.groupby("category")["supplier_id"].nunique())

    kpis["suppliers_for_80pct_spend"] = n_sup_80
    kpis["suppliers_for_80pct_pct"] = round(100 * n_sup_80 / kpis["supplier_count"], 1)
    kpis["categories_for_80pct_spend"] = n_cat_80
    kpis["supplier_spend_hhi"] = round(supplier_hhi, 4)
    kpis["category_spend_hhi"] = round(category_hhi, 4)
    kpis["top10_supplier_spend_share"] = round(
        float(by_supplier.head(10)["spend"].sum() / total_spend), 4)

    tables = {
        "spend_by_supplier": by_supplier,
        "spend_by_category": by_category,
        "spend_by_business_unit": by_bu,
        "spend_by_country": by_country,
        "spend_by_item": by_item,
        "spend_monthly": monthly,
        "spend_quarterly": quarterly,
        "spend_monthly_by_category": monthly_by_cat,
        "pareto_supplier": pareto_supplier,
        "pareto_category": pareto_category,
        "pareto_business_unit": pareto_bu,
        "category_supplier_concentration": cat_supplier_hhi,
    }
    for name, tbl in tables.items():
        tbl.to_csv(PATHS["tables"] / f"{name}.csv", index=False)

    log.info("Spend analysis | total=%.1fM | %d suppliers carry 80%% of spend | supplier HHI=%.3f",
             total_spend / 1e6, n_sup_80, supplier_hhi)
    return {"kpis": kpis, "tables": tables}


if __name__ == "__main__":
    from .data_quality import run as dq
    clean, _ = dq()
    run(clean)

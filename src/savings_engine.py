"""Phase 7 — Savings opportunity engine.

Five levers, deliberately defined on DISJOINT price gaps so their savings can be
summed without double counting (see config.yaml for the decomposition):

    LEVER 1  price negotiation    : ON-contract overpaid lines   price -> reference
    LEVER 2  contract compliance  : OFF-contract lines           price -> on-contract ref
    LEVER 3  supplier consolidation: fragmented items            reference -> best-in-class
    LEVER 4  demand aggregation    : items split across >=3 BUs   scale discount on residual
    LEVER 5  payment terms         : working-capital / early-pay financial value

Because the data is SIMULATED, all outputs are MODELED / ESTIMATED savings
opportunity, never realized savings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("savings_engine")

PAYMENT_TERM_DAYS = {"NET15": 15, "NET30": 30, "NET45": 45, "NET60": 60,
                     "NET90": 90, "2_10_NET30": 30}
COST_LEVERS = ("price", "compliance", "consolidation", "demand")


def build_cost_register(clean, bench_out, comp_out, cfg,
                        premium_threshold, levers=COST_LEVERS):
    """Supplier x category x lever savings register (gross gaps only).

    premium_threshold gates the price lever (which lines count as overpaid).
    levers selects which of the four cost levers to include.
    """
    scfg = cfg["savings"]
    bl = bench_out["benchmark_lines"]
    ref_tbl = bench_out["tables"]["benchmark_reference"]
    maverick = comp_out["maverick_lines"]
    parts = []

    if "price" in levers:  # LEVER 1 — on-contract renegotiation
        on = bl[bl["contract_status"] == "On-Contract"].copy()
        on["gap"] = np.where(
            on["unit_price"] > on["reference_price"] * (1 + premium_threshold),
            (on["unit_price"] - on["reference_price"]) * on["quantity"], 0.0)
        p = (on[on["gap"] > 0].groupby(["supplier_id", "supplier_name", "category"])
             .agg(current_spend=("line_spend", "sum"), gross_gap=("gap", "sum"),
                  lines=("po_line_id", "count")).reset_index())
        p["lever"] = "price_negotiation"
        parts.append(p)

    if "compliance" in levers:  # LEVER 2 — off-contract maverick premium
        m = (maverick[maverick["maverick_premium_value"] > 0]
             .groupby(["supplier_id", "supplier_name", "category"])
             .agg(current_spend=("line_spend", "sum"),
                  gross_gap=("maverick_premium_value", "sum"),
                  lines=("po_line_id", "count")).reset_index())
        m["lever"] = "contract_compliance"
        parts.append(m)

    if "consolidation" in levers:  # LEVER 3 — fragmented -> best-in-class
        frag = ref_tbl[(ref_tbl["benchmarkable"]) &
                       (ref_tbl["n_suppliers"] >= scfg["consolidation"]["min_suppliers_fragmented"])]
        cons = bl.merge(frag[["item", "region_tier", "reference_price", "competitive_price"]],
                        on=["item", "region_tier"], suffixes=("", "_f"), how="inner")
        cons["gap"] = np.where(
            cons["unit_price"] > cons["competitive_price"],
            np.maximum(cons["reference_price"] - cons["competitive_price"], 0.0)
            * cons["quantity"] * scfg["consolidation"]["max_share_shiftable"], 0.0)
        c = (cons[cons["gap"] > 0].groupby(["supplier_id", "supplier_name", "category"])
             .agg(current_spend=("line_spend", "sum"), gross_gap=("gap", "sum"),
                  lines=("po_line_id", "count")).reset_index())
        c["lever"] = "supplier_consolidation"
        parts.append(c)

    if "demand" in levers:  # LEVER 4 — cross-BU scale discount on residual
        dcfg = scfg["demand_aggregation"]
        item_bu = clean.groupby("item")["business_unit"].nunique()
        multi = item_bu[item_bu >= dcfg["min_business_units"]].index
        resid = bl[(bl["item"].isin(multi)) & (bl["unit_price"] <= bl["reference_price"])].copy()
        resid["gap"] = resid["line_spend"] * dcfg["scale_discount"]
        d = (resid.groupby(["supplier_id", "supplier_name", "category"])
             .agg(current_spend=("line_spend", "sum"), gross_gap=("gap", "sum"),
                  lines=("po_line_id", "count")).reset_index())
        d["lever"] = "demand_aggregation"
        parts.append(d)

    if not parts:
        return pd.DataFrame(columns=["supplier_id", "supplier_name", "category",
                                     "current_spend", "gross_gap", "lines", "lever"])
    reg = pd.concat(parts, ignore_index=True)
    reg = reg[reg["gross_gap"] >= scfg["min_opportunity_value"]].copy()
    return reg


def run(clean, bench_out, comp_out, cfg=None):
    cfg = cfg or load_config()
    scfg = cfg["savings"]
    caps = scfg["capture_rates"]
    n_years = (clean["order_date"].max() - clean["order_date"].min()).days / 365.25
    thr = cfg["benchmarking"]["overpriced_premium_threshold"]

    reg = build_cost_register(clean, bench_out, comp_out, cfg, thr, COST_LEVERS)
    for lvl in ("conservative", "base", "aggressive"):
        reg[f"savings_{lvl}"] = reg["gross_gap"] * caps[lvl]
    reg = reg.sort_values("savings_base", ascending=False)

    pt = _payment_terms(clean, cfg, n_years)

    lever_summary = (reg.groupby("lever")
                     .agg(opportunities=("lever", "count"),
                          current_spend=("current_spend", "sum"),
                          gross_gap=("gross_gap", "sum"),
                          savings_conservative=("savings_conservative", "sum"),
                          savings_base=("savings_base", "sum"),
                          savings_aggressive=("savings_aggressive", "sum"))
                     .reset_index().sort_values("savings_base", ascending=False))

    total_spend = clean["line_spend"].sum()
    cost_base = reg["savings_base"].sum()
    kpis = {
        "analyzed_years": round(float(n_years), 2),
        "total_spend": float(total_spend),
        "cost_savings_gross_gap": float(reg["gross_gap"].sum()),
        "cost_savings_conservative": float(reg["savings_conservative"].sum()),
        "cost_savings_base": float(cost_base),
        "cost_savings_aggressive": float(reg["savings_aggressive"].sum()),
        "cost_savings_base_pct_of_spend": round(100 * cost_base / total_spend, 2),
        "cost_savings_base_annualized": float(cost_base / n_years),
        "payment_terms_annual_value": float(pt["annual_value_total"]),
        "n_opportunities": int(len(reg)),
        "n_suppliers_with_opportunity": int(reg["supplier_id"].nunique()),
    }

    reg.to_csv(PATHS["tables"] / "savings_register.csv", index=False)
    lever_summary.to_csv(PATHS["tables"] / "savings_by_lever.csv", index=False)
    pt["detail"].to_csv(PATHS["tables"] / "payment_terms_opportunity.csv", index=False)

    log.info("Savings | gross gap %.1fM | base modeled %.1fM (%.1f%% of spend) | payment-terms %.1fM/yr",
             kpis["cost_savings_gross_gap"] / 1e6, cost_base / 1e6,
             kpis["cost_savings_base_pct_of_spend"], pt["annual_value_total"] / 1e6)
    return {"kpis": kpis,
            "tables": {"savings_register": reg, "savings_by_lever": lever_summary,
                       "payment_terms": pt["detail"]},
            "payment_terms_summary": pt}


def _payment_terms(clean, cfg, n_years):
    p = cfg["savings"]["payment_terms"]
    df = clean.copy()
    df["term_days"] = df["payment_terms"].map(PAYMENT_TERM_DAYS)
    rows = []
    short = df[df["term_days"] < p["dpo_target_days"]]
    for term, g in short.groupby("payment_terms"):
        term_annual = g["line_spend"].sum() / n_years
        extra_days = p["dpo_target_days"] - PAYMENT_TERM_DAYS[term]
        released = term_annual * extra_days / 365.0
        rows.append({"lever": "dpo_extension", "payment_terms": term,
                     "annual_spend": term_annual, "extra_days": extra_days,
                     "working_capital_released": released,
                     "annual_value": released * p["wacc"]})
    ep = df[df["payment_terms"] == p["early_pay_terms"]]
    ep_annual = ep["line_spend"].sum() / n_years
    ep_value = ep_annual * p["early_pay_discount"] * p["early_pay_capture"]
    rows.append({"lever": "early_pay_discount", "payment_terms": p["early_pay_terms"],
                 "annual_spend": ep_annual, "extra_days": 0,
                 "working_capital_released": 0.0, "annual_value": ep_value})
    detail = pd.DataFrame(rows)
    return {"detail": detail,
            "annual_value_total": float(detail["annual_value"].sum()),
            "dpo_value": float(detail.loc[detail.lever == "dpo_extension", "annual_value"].sum()),
            "early_pay_value": float(ep_value)}


if __name__ == "__main__":
    from .data_quality import run as dq
    from .price_benchmarking import run as bench
    from .contract_compliance import run as comp
    clean, _ = dq()
    b = bench(clean); c = comp(clean)
    run(clean, b, c)

"""Phase 10 — Scenario optimization.

Three governance scenarios differing in ambition. Each re-runs the cost levers at
its own premium threshold, lever set and capture rate, and layers on payment-term
value where included:

    CONSERVATIVE  price + compliance,                         25% capture, thr 0.15
    BASE          + supplier consolidation,                   50% capture, thr 0.10
    AGGRESSIVE    + payment-term optimisation,                75% capture, thr 0.07

All figures are MODELED opportunity from simulated data. The engine asserts a
monotonic ordering (conservative <= base <= aggressive) as a sanity check.
"""
from __future__ import annotations

import pandas as pd

from .config import PATHS, get_logger, load_config
from .savings_engine import build_cost_register, _payment_terms

log = get_logger("scenarios")

_LEVER_MAP = {"price": "price", "compliance": "compliance",
              "consolidation": "consolidation", "demand": "demand"}


def run(clean, bench_out, comp_out, cfg=None) -> dict:
    cfg = cfg or load_config()
    caps = cfg["savings"]["capture_rates"]
    n_years = (clean["order_date"].max() - clean["order_date"].min()).days / 365.25
    total_spend = clean["line_spend"].sum()

    rows = []
    for name, sc in cfg["scenarios"].items():
        cost_levers = tuple(_LEVER_MAP[l] for l in sc["include_levers"] if l in _LEVER_MAP)
        capture = caps[sc["capture"]]
        reg = build_cost_register(clean, bench_out, comp_out, cfg,
                                  sc["premium_threshold"], cost_levers)
        cost_period = float(reg["gross_gap"].sum() * capture)
        cost_annual = cost_period / n_years

        pt_annual = 0.0
        if "payment_terms" in sc["include_levers"]:
            pt_annual = _payment_terms(clean, cfg, n_years)["annual_value_total"]

        rows.append({
            "scenario": name.upper(),
            "levers": ", ".join(sc["include_levers"]),
            "capture_rate": capture,
            "premium_threshold": sc["premium_threshold"],
            "addressable_spend": float(reg["current_spend"].sum()),
            "cost_savings_period": cost_period,
            "cost_savings_annualized": cost_annual,
            "payment_terms_annual": pt_annual,
            "total_annual_value": cost_annual + pt_annual,
            "savings_pct_of_spend": round(100 * cost_period / total_spend, 2),
            "suppliers_affected": int(reg["supplier_id"].nunique()),
            "categories_affected": int(reg["category"].nunique()),
        })

    scen = pd.DataFrame(rows)
    order = {"CONSERVATIVE": 0, "BASE": 1, "AGGRESSIVE": 2}
    scen = scen.sort_values("scenario", key=lambda s: s.map(order)).reset_index(drop=True)

    tradeoffs = {
        "CONSERVATIVE": "Lowest execution risk: renegotiate clear overpayers and curb "
                        "maverick spend only. High confidence, no supplier switching.",
        "BASE": "Balanced: adds consolidation of fragmented categories. Some sourcing "
                "effort and change management; recommended target.",
        "AGGRESSIVE": "Highest ambition: adds payment-term extension and deeper price "
                      "capture. Requires supplier switching, finance alignment and "
                      "carries relationship/continuity risk.",
    }
    scen["risk_tradeoff"] = scen["scenario"].map(tradeoffs)

    # monotonic sanity check
    cp = scen.set_index("scenario")["cost_savings_period"]
    assert cp["CONSERVATIVE"] <= cp["BASE"] <= cp["AGGRESSIVE"], \
        f"Scenario ordering violated: {cp.to_dict()}"

    scen.to_csv(PATHS["tables"] / "scenario_optimization.csv", index=False)

    kpis = {
        "conservative_period": float(cp["CONSERVATIVE"]),
        "base_period": float(cp["BASE"]),
        "aggressive_period": float(cp["AGGRESSIVE"]),
        "base_total_annual_value": float(
            scen.set_index("scenario").loc["BASE", "total_annual_value"]),
        "aggressive_total_annual_value": float(
            scen.set_index("scenario").loc["AGGRESSIVE", "total_annual_value"]),
    }
    log.info("Scenarios | conservative %.1fM | base %.1fM | aggressive %.1fM (period, modeled)",
             cp["CONSERVATIVE"] / 1e6, cp["BASE"] / 1e6, cp["AGGRESSIVE"] / 1e6)
    return {"kpis": kpis, "tables": {"scenario_optimization": scen}}


if __name__ == "__main__":
    print("Run via pipeline.py")

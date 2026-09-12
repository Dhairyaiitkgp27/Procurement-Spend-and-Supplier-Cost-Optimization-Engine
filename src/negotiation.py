"""Phase 8 — Negotiation prioritization.

Priority score = weighted blend of four normalised (0-1) components:

    savings_opportunity : modeled base savings at stake with the supplier
    spend               : annual leverage / relationship size
    performance_gap     : how far below best-in-class the supplier performs
    negotiability       : how easy it is to move (uncommitted spend + alternatives,
                          penalised when the supplier is effectively sole-source)

The Top-N suppliers become the negotiation target list with full context and the
strategic action inherited from Phase 9.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("negotiation")


def _mm(s: pd.Series) -> pd.Series:
    lo, hi = s.min(), s.max()
    if hi <= lo:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return (s - lo) / (hi - lo)


def run(features: pd.DataFrame, cfg=None) -> dict:
    cfg = cfg or load_config()
    w = cfg["negotiation"]["weights"]
    top_n = cfg["negotiation"]["top_n_targets"]
    f = features.copy()

    f["off_contract_share"] = 1 - f["on_contract_rate"].fillna(0)
    f["performance_gap"] = 100 - f["spi"].fillna(f["spi"].median())

    # negotiability: uncommitted spend + category competition, penalised if sole-source
    comp_n = _mm(f["primary_cat_n_suppliers"].fillna(1).astype(float))
    negotiability = 0.5 * f["off_contract_share"] + 0.5 * comp_n
    sole = (f["max_category_share"].fillna(0) >= 0.40)
    negotiability = np.where(sole, negotiability * 0.5, negotiability)
    f["negotiability"] = negotiability

    f["c_savings"] = _mm(f["savings_base"].fillna(0))
    f["c_spend"] = _mm(f["spend"].fillna(0))
    f["c_perfgap"] = _mm(f["performance_gap"])
    f["c_negotiability"] = _mm(pd.Series(f["negotiability"], index=f.index))

    f["priority_score"] = (100 * (
        w["savings_opportunity"] * f["c_savings"]
        + w["spend"] * f["c_spend"]
        + w["performance_gap"] * f["c_perfgap"]
        + w["negotiability"] * f["c_negotiability"])).round(2)

    f = f.sort_values("priority_score", ascending=False)
    f["priority_rank"] = range(1, len(f) + 1)

    cols = ["priority_rank", "supplier_name", "primary_category", "spend",
            "weighted_price_index", "weighted_price_premium", "savings_base",
            "otd_rate", "quality_score", "on_contract_rate", "risk_band",
            "recommendation", "priority_score"]
    targets = f.head(top_n)[cols].rename(columns={
        "primary_category": "category", "spend": "current_spend",
        "weighted_price_index": "price_index_vs_benchmark",
        "weighted_price_premium": "price_premium",
        "savings_base": "modeled_savings_base",
        "otd_rate": "on_time_delivery_rate",
        "on_contract_rate": "contract_compliance_rate",
        "recommendation": "recommended_action"})

    f.to_csv(PATHS["tables"] / "negotiation_priority.csv", index=False)
    targets.to_csv(PATHS["tables"] / "top_negotiation_targets.csv", index=False)

    kpis = {
        "top_n": int(top_n),
        "top_targets_spend": float(targets["current_spend"].sum()),
        "top_targets_modeled_savings": float(targets["modeled_savings_base"].sum()),
        "top_targets_spend_share": round(
            100 * targets["current_spend"].sum() / f["spend"].sum(), 2),
    }
    log.info("Negotiation | top %d targets cover %s spend, %.1fM modeled savings (%.1f%% of spend)",
             top_n, f"${targets['current_spend'].sum()/1e6:.0f}M",
             targets["modeled_savings_base"].sum() / 1e6, kpis["top_targets_spend_share"])
    return {"kpis": kpis, "tables": {"negotiation_priority": f,
                                     "top_negotiation_targets": targets}}


if __name__ == "__main__":
    print("Run via pipeline.py")

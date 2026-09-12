"""Phase 5 — Supplier scorecard (weighted Supplier Performance Index, SPI).

Five sub-scores on a common 0-100 scale, combined with transparent, justified
weights. Each sub-score uses explicit, documented anchor points so the mapping
from raw metric to score is auditable (no black boxes).

    cost_competitiveness : premium -5%..+30%  -> 100..0
    on_time_delivery     : OTD rate 0..1      -> 0..100
    quality              : defect rate 0..12%  -> 100..0
    contract_compliance  : compliance 0..1     -> 0..100
    lead_time_reliability: delay std 0..30d     -> 100..0
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("supplier_scorecard")


def _clip(x, lo=0.0, hi=100.0):
    return np.clip(x, lo, hi)


def run(clean: pd.DataFrame, price_position: pd.DataFrame, cfg=None) -> dict:
    cfg = cfg or load_config()
    w = cfg["scorecard"]["weights"]

    # ---- raw operational metrics per supplier ------------------------------
    g = (clean.groupby(["supplier_id", "supplier_name"])
         .agg(spend=("line_spend", "sum"),
              lines=("po_line_id", "count"),
              otd_rate=("on_time", "mean"),
              defect_rate=("is_defect", "mean"),
              on_contract_rate=("contract_status", lambda s: (s == "On-Contract").mean()),
              delay_std=("delay_days", "std"),
              delay_mean=("delay_days", "mean"),
              lead_time_mean=("lead_time_days", "mean"),
              categories=("category", "nunique"))
         .reset_index())
    g["delay_std"] = g["delay_std"].fillna(0.0)

    # ---- cost competitiveness from benchmarking ---------------------------
    g = g.merge(price_position[["supplier_id", "weighted_price_premium",
                                "weighted_price_index", "benchmarked_spend"]],
                on="supplier_id", how="left")
    g["weighted_price_premium"] = g["weighted_price_premium"].fillna(0.0)

    # ---- sub-scores (documented anchors) ----------------------------------
    g["cost_score"] = _clip(100 * (0.30 - g["weighted_price_premium"]) / (0.30 - (-0.05)))
    g["delivery_score"] = _clip(100 * g["otd_rate"])
    g["quality_score"] = _clip(100 * (1 - g["defect_rate"] / 0.12))
    g["compliance_score"] = _clip(100 * g["on_contract_rate"])
    g["leadtime_score"] = _clip(100 * (1 - g["delay_std"] / 30.0))

    # ---- weighted Supplier Performance Index ------------------------------
    g["spi"] = (
        w["cost_competitiveness"] * g["cost_score"]
        + w["on_time_delivery"] * g["delivery_score"]
        + w["quality"] * g["quality_score"]
        + w["contract_compliance"] * g["compliance_score"]
        + w["lead_time_reliability"] * g["leadtime_score"]
    ).round(2)

    # ---- ranking / tiers ---------------------------------------------------
    g["rank_confident"] = g["spend"] >= cfg["scorecard"]["min_spend_for_ranking"]
    ranked = g[g["rank_confident"]].copy()
    ranked = ranked.sort_values("spi", ascending=False)
    ranked["spi_rank"] = np.arange(1, len(ranked) + 1)
    # performance quartile tier A/B/C/D on the ranked population
    q = ranked["spi"].quantile([0.75, 0.50, 0.25]).to_dict()
    def tier(x):
        if x >= q[0.75]:
            return "A"
        if x >= q[0.50]:
            return "B"
        if x >= q[0.25]:
            return "C"
        return "D"
    ranked["performance_tier"] = ranked["spi"].apply(tier)
    g = g.merge(ranked[["supplier_id", "spi_rank", "performance_tier"]],
                on="supplier_id", how="left")
    g["performance_tier"] = g["performance_tier"].fillna("Unranked")

    g = g.sort_values("spi", ascending=False)

    kpis = {
        "avg_spi": round(float(ranked["spi"].mean()), 2),
        "median_spi": round(float(ranked["spi"].median()), 2),
        "ranked_suppliers": int(len(ranked)),
        "tier_A_suppliers": int((ranked["performance_tier"] == "A").sum()),
        "tier_D_suppliers": int((ranked["performance_tier"] == "D").sum()),
        "avg_otd_rate": round(float((clean["on_time"]).mean()), 4),
        "avg_defect_rate": round(float(clean["is_defect"].mean()), 4),
        "weights": w,
    }

    g.to_csv(PATHS["tables"] / "supplier_scorecard.csv", index=False)
    log.info("Scorecard | ranked=%d | avg SPI=%.1f | avg OTD=%.1f%% | avg defect=%.2f%%",
             len(ranked), kpis["avg_spi"], 100 * kpis["avg_otd_rate"],
             100 * kpis["avg_defect_rate"])
    return {"kpis": kpis, "tables": {"supplier_scorecard": g}}


if __name__ == "__main__":
    from .data_quality import run as dq
    from .price_benchmarking import run as bench
    clean, _ = dq()
    b = bench(clean)
    run(clean, b["tables"]["supplier_price_position"])

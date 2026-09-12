"""Phase 9 — Strategic recommendation engine (rule-based & explainable).

Assembles a single per-supplier feature frame from the scorecard, benchmarking,
risk, savings and compliance phases, then applies a transparent decision cascade:

    REPLACE     critical risk, OR poor quality + poor delivery + above-market price
    NEGOTIATE   acceptable performance but priced materially above benchmark
    CONSOLIDATE minor player in a fragmented category with acceptable quality
    RETAIN      top-quartile performance at a competitive price and low risk
    MONITOR     everything else

Every classification carries a human-readable reason string.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("recommendations")


def build_features(clean, scorecard, price_position, risk, savings_register,
                   compliance_supplier, cfg) -> pd.DataFrame:
    """One row per supplier with all decision-relevant metrics."""
    f = scorecard[["supplier_id", "supplier_name", "spend", "spi", "performance_tier",
                   "cost_score", "delivery_score", "quality_score", "compliance_score",
                   "leadtime_score", "otd_rate", "defect_rate", "on_contract_rate"]].copy()
    f = f.merge(price_position[["supplier_id", "weighted_price_premium", "weighted_price_index",
                                "persistent_premium"]], on="supplier_id", how="left")
    f = f.merge(risk[["supplier_id", "composite_risk", "risk_band",
                      "max_category_share", "primary_risk_driver"]], on="supplier_id", how="left")
    # savings rolled to supplier + dominant lever
    if len(savings_register):
        sav = (savings_register.groupby("supplier_id")
               .agg(savings_base=("savings_base", "sum")).reset_index())
        dom = (savings_register.sort_values("savings_base", ascending=False)
               .drop_duplicates("supplier_id")[["supplier_id", "lever"]]
               .rename(columns={"lever": "primary_lever"}))
        f = f.merge(sav, on="supplier_id", how="left").merge(dom, on="supplier_id", how="left")
    else:
        f["savings_base"] = 0.0; f["primary_lever"] = None
    f["savings_base"] = f["savings_base"].fillna(0.0)
    f["weighted_price_premium"] = f["weighted_price_premium"].fillna(0.0)

    # primary category + category fragmentation
    prim = (clean.groupby(["supplier_id", "category"])["line_spend"].sum()
            .reset_index().sort_values("line_spend", ascending=False)
            .drop_duplicates("supplier_id")[["supplier_id", "category"]]
            .rename(columns={"category": "primary_category"}))
    f = f.merge(prim, on="supplier_id", how="left")
    cat_nsup = clean.groupby("category")["supplier_id"].nunique()
    f["primary_cat_n_suppliers"] = f["primary_category"].map(cat_nsup)
    return f


def run(clean, scorecard, price_position, risk, savings_register,
        compliance_supplier, cfg=None) -> dict:
    cfg = cfg or load_config()
    rc = cfg["recommendations"]
    f = build_features(clean, scorecard, price_position, risk, savings_register,
                       compliance_supplier, cfg)

    ranked_spi = f.loc[f["spi"].notna(), "spi"]
    hi_cut = ranked_spi.quantile(rc["perf_high_pct"])
    lo_cut = ranked_spi.quantile(rc["perf_low_pct"])
    min_frag = cfg["savings"]["consolidation"]["min_suppliers_fragmented"]

    def classify(r):
        hi = r["spi"] >= hi_cut
        lo = r["spi"] <= lo_cut
        prem_high = r["weighted_price_premium"] > rc["premium_high"]
        prem_ok = r["weighted_price_premium"] < rc["premium_ok"]
        low_q = r["quality_score"] < 50
        poor_d = r["delivery_score"] < 60
        crit = r["risk_band"] == "CRITICAL"
        high_r = r["risk_band"] in ("HIGH", "CRITICAL")
        fragmented = (r["primary_cat_n_suppliers"] or 0) >= min_frag
        minor = (r["max_category_share"] or 0) < 0.08

        if crit:
            return "REPLACE", f"Critical risk band ({r['composite_risk']:.0f}); primary driver {r['primary_risk_driver']}"
        if low_q and poor_d and prem_high:
            return "REPLACE", "Poor quality + poor delivery + above-market price"
        if lo and prem_high and high_r:
            return "REPLACE", "Bottom-quartile performance, high risk and above-market price"
        if prem_high and not lo:
            return "NEGOTIATE", f"Priced {r['weighted_price_premium']*100:.0f}% above benchmark at acceptable performance"
        if prem_high and lo:
            return "NEGOTIATE", f"Priced {r['weighted_price_premium']*100:.0f}% above benchmark (weak performer — hard bargaining)"
        if fragmented and minor and not low_q:
            return "CONSOLIDATE", f"Minor share in fragmented category ({int(r['primary_cat_n_suppliers'])} suppliers)"
        if hi and prem_ok and not high_r:
            return "RETAIN", "Top-quartile performance at competitive price"
        return "MONITOR", "Acceptable but no decisive lever; monitor"

    res = f.apply(classify, axis=1, result_type="expand")
    f["recommendation"] = res[0]
    f["recommendation_reason"] = res[1]
    f = f.sort_values(["recommendation", "savings_base"], ascending=[True, False])

    summary = (f.groupby("recommendation")
               .agg(suppliers=("supplier_id", "count"),
                    spend=("spend", "sum"),
                    modeled_savings_base=("savings_base", "sum"))
               .reset_index().sort_values("spend", ascending=False))

    f.to_csv(PATHS["tables"] / "supplier_recommendations.csv", index=False)
    summary.to_csv(PATHS["tables"] / "recommendation_summary.csv", index=False)

    counts = f["recommendation"].value_counts().to_dict()
    kpis = {f"n_{k.lower()}": int(v) for k, v in counts.items()}
    kpis["spend_flagged_replace"] = float(f.loc[f.recommendation == "REPLACE", "spend"].sum())
    kpis["spend_flagged_negotiate"] = float(f.loc[f.recommendation == "NEGOTIATE", "spend"].sum())
    kpis["savings_in_negotiate"] = float(f.loc[f.recommendation == "NEGOTIATE", "savings_base"].sum())

    log.info("Recommendations | " + " ".join(f"{k}={v}" for k, v in counts.items()))
    return {"kpis": kpis, "tables": {"supplier_recommendations": f,
                                     "recommendation_summary": summary},
            "features": f}


if __name__ == "__main__":
    print("Run via pipeline.py")

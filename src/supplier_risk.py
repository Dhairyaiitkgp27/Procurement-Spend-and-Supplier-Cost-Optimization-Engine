"""Phase 6 — Supplier risk scoring.

Five risk dimensions (0-100, higher = worse), combined into a weighted composite
and banded LOW / MEDIUM / HIGH / CRITICAL. Also flags single-source categories.

    delivery_risk      : late rate + avg lateness magnitude
    quality_risk       : defect (major+reject) rate
    price_volatility   : within-item price coefficient of variation
    concentration_risk : our dependency (max share of any category we ride on them)
    trend_risk         : deterioration in defect / delay over time
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("supplier_risk")


def _clip(x, lo=0.0, hi=100.0):
    return np.clip(x, lo, hi)


def _band(score, bands):
    for name, (lo, hi) in bands.items():
        if lo <= score < hi:
            return name
    return "CRITICAL"


def run(clean: pd.DataFrame, cfg=None) -> dict:
    cfg = cfg or load_config()
    rcfg = cfg["risk"]
    w = rcfg["weights"]
    df = clean.copy()
    mid = df["order_date"].median()

    # ---- base per-supplier metrics ----------------------------------------
    base = (df.groupby(["supplier_id", "supplier_name"])
            .agg(spend=("line_spend", "sum"),
                 lines=("po_line_id", "count"),
                 otd_rate=("on_time", "mean"),
                 defect_rate=("is_defect", "mean"))
            .reset_index())
    base["late_rate"] = 1 - base["otd_rate"]

    # avg positive delay (magnitude of lateness on late orders)
    late = df[df["delay_days"] > 0]
    avg_delay = late.groupby("supplier_id")["delay_days"].mean()
    base["avg_late_delay"] = base["supplier_id"].map(avg_delay).fillna(0.0)

    # ---- price volatility: within-item price CV, spend-weighted -----------
    def _sup_price_cv(g):
        cvs, wts = [], []
        for _, gi in g.groupby("item"):
            if len(gi) >= 5 and gi["unit_price"].mean() > 0:
                cvs.append(gi["unit_price"].std(ddof=0) / gi["unit_price"].mean())
                wts.append(gi["line_spend"].sum())
        if not cvs:
            return 0.0
        return float(np.average(cvs, weights=wts))
    price_cv = df.groupby("supplier_id").apply(_sup_price_cv, include_groups=False)
    base["price_cv"] = base["supplier_id"].map(price_cv).fillna(0.0)

    # ---- concentration: max share of any category we ride on this supplier
    sup_cat_share = df.groupby(["supplier_id", "category"]).apply(
        lambda g: g["line_spend"].sum(), include_groups=False)
    cat_totals = df.groupby("category")["line_spend"].sum()
    share_tbl = (sup_cat_share.reset_index(name="sup_cat_spend"))
    share_tbl["cat_total"] = share_tbl["category"].map(cat_totals)
    share_tbl["share"] = share_tbl["sup_cat_spend"] / share_tbl["cat_total"]
    max_share = share_tbl.groupby("supplier_id")["share"].max()
    base["max_category_share"] = base["supplier_id"].map(max_share).fillna(0.0)

    # ---- trend: later-half minus earlier-half deterioration ---------------
    df["_half"] = np.where(df["order_date"] <= mid, "H1", "H2")
    def _trend(g):
        h1 = g[g["_half"] == "H1"]; h2 = g[g["_half"] == "H2"]
        if len(h1) < 10 or len(h2) < 10:
            return pd.Series({"d_defect": 0.0, "d_delay": 0.0})
        return pd.Series({
            "d_defect": h2["is_defect"].mean() - h1["is_defect"].mean(),
            "d_delay": h2["delay_days"].mean() - h1["delay_days"].mean(),
        })
    trend = df.groupby("supplier_id").apply(_trend, include_groups=False).reset_index()
    base = base.merge(trend, on="supplier_id", how="left").fillna({"d_defect": 0, "d_delay": 0})

    # ---- risk sub-scores ---------------------------------------------------
    base["delivery_risk"] = _clip((base["late_rate"] / 0.35) * 70
                                   + (base["avg_late_delay"] / 25.0) * 30)
    base["quality_risk"] = _clip(base["defect_rate"] / 0.12 * 100)
    base["price_volatility_risk"] = _clip(base["price_cv"] / 0.20 * 100)
    base["concentration_risk"] = _clip(base["max_category_share"] / 0.60 * 100)
    base["trend_risk"] = _clip(np.maximum(0, base["d_defect"] * 1500)
                               + np.maximum(0, base["d_delay"] * 4))

    base["composite_risk"] = (
        w["delivery_risk"] * base["delivery_risk"]
        + w["quality_risk"] * base["quality_risk"]
        + w["price_volatility"] * base["price_volatility_risk"]
        + w["concentration_risk"] * base["concentration_risk"]
        + w["trend_risk"] * base["trend_risk"]
    ).round(2)
    base["risk_band"] = base["composite_risk"].apply(lambda s: _band(s, rcfg["bands"]))

    # ---- driver label (top contributing dimension) ------------------------
    dims = ["delivery_risk", "quality_risk", "price_volatility_risk",
            "concentration_risk", "trend_risk"]
    base["primary_risk_driver"] = base[dims].idxmax(axis=1).str.replace("_risk", "")

    base = base.sort_values("composite_risk", ascending=False)

    # ---- single-source categories -----------------------------------------
    def _hhi(s):
        sh = s / s.sum()
        return float((sh ** 2).sum())
    cat_hhi = (df.groupby("category")
               .apply(lambda g: _hhi(g.groupby("supplier_id")["line_spend"].sum()),
                      include_groups=False)
               .reset_index(name="supplier_hhi"))
    cat_hhi["n_suppliers"] = cat_hhi["category"].map(df.groupby("category")["supplier_id"].nunique())
    cat_hhi["top_supplier_share"] = cat_hhi["category"].map(
        share_tbl.sort_values("share", ascending=False).groupby("category")["share"].first())
    cat_hhi["single_source_flag"] = ((cat_hhi["supplier_hhi"] >= rcfg["single_source_hhi"])
                                     | (cat_hhi["top_supplier_share"] >= 0.40))
    cat_hhi = cat_hhi.sort_values("supplier_hhi", ascending=False)

    # item-level single-source: an item supplied by exactly one supplier
    item_src = (df.groupby("item")
                .agg(n_suppliers=("supplier_id", "nunique"),
                     spend=("line_spend", "sum"),
                     category=("category", "first"))
                .reset_index())
    item_src["single_source_flag"] = item_src["n_suppliers"] == 1
    item_src["dual_source_flag"] = item_src["n_suppliers"] == 2
    item_src["top_supplier"] = item_src["item"].map(
        df.groupby("item").apply(
            lambda g: g.groupby("supplier_name")["line_spend"].sum().idxmax(),
            include_groups=False))
    single_items = item_src[item_src["single_source_flag"]].sort_values("spend", ascending=False)
    item_src.to_csv(PATHS["tables"] / "item_source_concentration.csv", index=False)

    band_counts = base["risk_band"].value_counts().to_dict()
    kpis = {
        "critical_suppliers": int(band_counts.get("CRITICAL", 0)),
        "high_suppliers": int(band_counts.get("HIGH", 0)),
        "medium_suppliers": int(band_counts.get("MEDIUM", 0)),
        "low_suppliers": int(band_counts.get("LOW", 0)),
        "spend_at_high_or_critical": float(
            base.loc[base["risk_band"].isin(["HIGH", "CRITICAL"]), "spend"].sum()),
        "single_source_categories": int(cat_hhi["single_source_flag"].sum()),
        "single_source_items": int(item_src["single_source_flag"].sum()),
        "single_source_item_spend": float(single_items["spend"].sum()),
        "dual_source_items": int(item_src["dual_source_flag"].sum()),
        "n_chronically_late": int((base["late_rate"] > 0.25).sum()),
        "n_high_defect": int((base["defect_rate"] > 0.05).sum()),
    }

    tables = {"supplier_risk": base, "category_concentration_risk": cat_hhi}
    for name, tbl in tables.items():
        tbl.to_csv(PATHS["tables"] / f"{name}.csv", index=False)

    log.info("Risk | CRITICAL=%d HIGH=%d MED=%d LOW=%d | %.1fM spend at high/critical | %d single-source cats",
             kpis["critical_suppliers"], kpis["high_suppliers"], kpis["medium_suppliers"],
             kpis["low_suppliers"], kpis["spend_at_high_or_critical"] / 1e6,
             kpis["single_source_categories"])
    return {"kpis": kpis, "tables": tables}


if __name__ == "__main__":
    from .data_quality import run as dq
    clean, _ = dq()
    run(clean)

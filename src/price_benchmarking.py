"""Phase 3 — Price benchmarking (core diagnostic).

Builds a defensible reference price for each comparable group and measures how
far each supplier / business unit sits above it.

Comparability rule: prices are only benchmarked WITHIN an ``(item, region_tier)``
group, where region tiers group supplier countries of similar cost structure.
A group is benchmarkable only if it has enough transactions AND more than one
supplier (otherwise there is no market signal).

    reference_price  = median unit price of comparable lines
    competitive_price= 25th percentile (best-in-class)
    price_premium    = supplier_price / reference_price - 1
    price_index      = supplier_price / reference_price * 100
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("price_benchmarking")


def _region_tier_map(cfg) -> dict:
    m = {}
    for tier, countries in cfg["benchmarking"]["region_tiers"].items():
        for c in countries:
            m[c] = tier
    return m


def add_region_tier(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    df = df.copy()
    df["region_tier"] = df["supplier_country"].map(_region_tier_map(cfg)).fillna("HighCost")
    return df


def run(clean: pd.DataFrame, cfg=None) -> dict:
    cfg = cfg or load_config()
    bcfg = cfg["benchmarking"]
    df = add_region_tier(clean, cfg)

    grp_keys = ["item", "region_tier"]
    ref_pct = bcfg["reference_percentile"]
    comp_pct = bcfg["competitive_percentile"]

    def wavg(g):
        return np.average(g["unit_price"], weights=g["quantity"])

    ref = (df.groupby(grp_keys)
           .apply(lambda g: pd.Series({
               "reference_price": g["unit_price"].quantile(ref_pct),
               "competitive_price": g["unit_price"].quantile(comp_pct),
               "weighted_avg_price": wavg(g),
               "min_price": g["unit_price"].min(),
               "max_price": g["unit_price"].max(),
               "price_cv": g["unit_price"].std(ddof=0) / g["unit_price"].mean(),
               "n_txns": len(g),
               "n_suppliers": g["supplier_id"].nunique(),
               "group_spend": g["line_spend"].sum(),
           }), include_groups=False)
           .reset_index())
    ref["benchmarkable"] = ((ref["n_txns"] >= bcfg["min_comparable_txns"]) &
                            (ref["n_suppliers"] >= bcfg["min_suppliers_per_item"]))
    ref["category"] = ref["item"].map(df.drop_duplicates("item").set_index("item")["category"])

    bench = ref[ref["benchmarkable"]].copy()
    log.info("Benchmarkable groups: %d / %d | covering %.1f%% of spend",
             len(bench), len(ref),
             100 * bench["group_spend"].sum() / df["line_spend"].sum())

    # ---- supplier x item premium ------------------------------------------
    keep = df.merge(bench[grp_keys + ["reference_price", "competitive_price"]],
                    on=grp_keys, how="inner")
    si = (keep.groupby(["supplier_id", "supplier_name", "category", "item", "region_tier"])
          .apply(lambda g: pd.Series({
              "supplier_price": np.average(g["unit_price"], weights=g["quantity"]),
              "reference_price": g["reference_price"].iloc[0],
              "competitive_price": g["competitive_price"].iloc[0],
              "quantity": g["quantity"].sum(),
              "spend": g["line_spend"].sum(),
              "lines": len(g),
          }), include_groups=False)
          .reset_index())
    si["price_premium"] = si["supplier_price"] / si["reference_price"] - 1
    si["price_index"] = (si["supplier_price"] / si["reference_price"] * 100).round(1)
    si["premium_vs_competitive"] = si["supplier_price"] / si["competitive_price"] - 1
    si["overpriced"] = si["price_premium"] > bcfg["overpriced_premium_threshold"]
    # excess spend vs reference (what could be addressed before capture rate)
    si["excess_spend_vs_reference"] = np.maximum(
        (si["supplier_price"] - si["reference_price"]) * si["quantity"], 0.0)
    si = si.sort_values("excess_spend_vs_reference", ascending=False)

    # ---- supplier price position (rolled up) ------------------------------
    def _supplier_roll(g):
        bench_spend = g["spend"].sum()
        wpremium = np.average(g["price_premium"], weights=g["spend"]) if bench_spend else 0.0
        over = g[g["overpriced"]]
        return pd.Series({
            "benchmarked_spend": bench_spend,
            "weighted_price_premium": wpremium,
            "weighted_price_index": round(100 * (1 + wpremium), 1),
            "overpriced_spend": over["spend"].sum(),
            "overpriced_share": over["spend"].sum() / bench_spend if bench_spend else 0.0,
            "n_items": g["item"].nunique(),
            "n_overpriced_items": over["item"].nunique(),
            "excess_spend_vs_reference": g["excess_spend_vs_reference"].sum(),
        })

    sp = si.groupby(["supplier_id", "supplier_name"]).apply(
        _supplier_roll, include_groups=False).reset_index()
    # persistent premium: overpaid on a majority of benchmarked spend across >=2 items
    sp["persistent_premium"] = (sp["overpriced_share"] > 0.5) & (sp["n_overpriced_items"] >= 2)
    sp = sp.sort_values("excess_spend_vs_reference", ascending=False)

    # ---- category price dispersion ----------------------------------------
    cat_disp = (bench.groupby("category")
                .agg(mean_price_cv=("price_cv", "mean"),
                     max_price_cv=("price_cv", "max"),
                     benchmarkable_groups=("item", "count"))
                .reset_index().sort_values("mean_price_cv", ascending=False))
    catprem = (si.groupby("category")
               .apply(lambda g: np.average(g["price_premium"], weights=g["spend"]),
                      include_groups=False)
               .reset_index(name="weighted_price_premium"))
    cat_disp = cat_disp.merge(catprem, on="category", how="left")

    # ---- business unit benchmark position ---------------------------------
    bu_line = keep.copy()
    bu_line["excess_vs_reference"] = np.maximum(
        (bu_line["unit_price"] - bu_line["reference_price"]) * bu_line["quantity"], 0.0)
    bu = (bu_line.groupby("business_unit")
          .apply(lambda g: pd.Series({
              "benchmarked_spend": g["line_spend"].sum(),
              "weighted_price_premium": np.average(
                  g["unit_price"] / g["reference_price"] - 1, weights=g["line_spend"]),
              "excess_spend_vs_reference": g["excess_vs_reference"].sum(),
          }), include_groups=False)
          .reset_index().sort_values("weighted_price_premium", ascending=False))

    kpis = {
        "benchmarkable_groups": int(len(bench)),
        "benchmarkable_spend_share": round(
            float(bench["group_spend"].sum() / df["line_spend"].sum()), 4),
        "overpriced_supplier_item_combos": int(si["overpriced"].sum()),
        "total_excess_vs_reference": float(si["excess_spend_vs_reference"].sum()),
        "n_overpriced_suppliers": int((sp["overpriced_spend"] > 0).sum()),
        "n_persistent_premium_suppliers": int(sp["persistent_premium"].sum()),
        "avg_overpriced_premium": float(
            si.loc[si["overpriced"], "price_premium"].mean()),
    }

    tables = {
        "benchmark_reference": ref,
        "supplier_item_premium": si,
        "supplier_price_position": sp,
        "category_price_dispersion": cat_disp,
        "bu_price_position": bu,
    }
    for name, tbl in tables.items():
        tbl.to_csv(PATHS["tables"] / f"{name}.csv", index=False)

    log.info("Overpriced supplier-item combos: %d | modeled excess vs reference: %.1fM",
             kpis["overpriced_supplier_item_combos"], kpis["total_excess_vs_reference"] / 1e6)
    return {"kpis": kpis, "tables": tables, "benchmark_lines": keep}


if __name__ == "__main__":
    from .data_quality import run as dq
    from .spend_analysis import run as spend
    clean, _ = dq()
    run(clean)

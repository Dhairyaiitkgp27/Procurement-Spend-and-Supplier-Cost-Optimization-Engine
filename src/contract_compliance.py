"""Phase 4 — Contract compliance & maverick spend.

Measures how much spend flows through contracts vs off-contract ("maverick")
buying, at supplier / category / business-unit level, and quantifies the
*addressable maverick premium*: the extra price paid on off-contract lines
relative to what on-contract buyers pay for the same item in the same region.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config
from .price_benchmarking import add_region_tier

log = get_logger("contract_compliance")


def run(clean: pd.DataFrame, cfg=None) -> dict:
    cfg = cfg or load_config()
    df = add_region_tier(clean, cfg)
    df["is_on_contract"] = df["contract_status"] == "On-Contract"

    total = df["line_spend"].sum()
    on_spend = df.loc[df["is_on_contract"], "line_spend"].sum()
    off_spend = total - on_spend

    # ---- on-contract reference price per (item, region_tier) --------------
    on_ref = (df[df["is_on_contract"]].groupby(["item", "region_tier"])["unit_price"]
              .median().reset_index(name="on_contract_ref_price"))

    off = df[~df["is_on_contract"]].merge(on_ref, on=["item", "region_tier"], how="left")
    off = off.dropna(subset=["on_contract_ref_price"])
    off["maverick_premium_value"] = np.maximum(
        (off["unit_price"] - off["on_contract_ref_price"]) * off["quantity"], 0.0)

    addressable_premium = off["maverick_premium_value"].sum()

    # ---- compliance by dimension ------------------------------------------
    def _compliance(gcol):
        g = (df.groupby(gcol)
             .apply(lambda x: pd.Series({
                 "total_spend": x["line_spend"].sum(),
                 "on_contract_spend": x.loc[x["is_on_contract"], "line_spend"].sum(),
                 "lines": len(x),
                 "off_contract_lines": int((~x["is_on_contract"]).sum()),
             }), include_groups=False)
             .reset_index())
        g["off_contract_spend"] = g["total_spend"] - g["on_contract_spend"]
        g["compliance_rate"] = g["on_contract_spend"] / g["total_spend"]
        return g.sort_values("off_contract_spend", ascending=False)

    supplier_comp = _compliance(["supplier_id", "supplier_name"])
    category_comp = _compliance("category")
    bu_comp = _compliance("business_unit")

    # attach addressable premium per category / supplier
    prem_by_cat = off.groupby("category")["maverick_premium_value"].sum()
    category_comp["addressable_premium"] = category_comp["category"].map(prem_by_cat).fillna(0.0)
    prem_by_sup = off.groupby("supplier_id")["maverick_premium_value"].sum()
    supplier_comp["addressable_premium"] = supplier_comp["supplier_id"].map(prem_by_sup).fillna(0.0)

    # ---- maverick focus: off-contract spend where an on-contract path exists
    # (item is bought on-contract somewhere) -> genuinely redirectable
    redirectable = off[off["on_contract_ref_price"].notna()]["line_spend"].sum()

    kpis = {
        "total_spend": float(total),
        "on_contract_spend": float(on_spend),
        "off_contract_spend": float(off_spend),
        "compliance_rate_spend": round(float(on_spend / total), 4),
        "compliance_rate_count": round(float(df["is_on_contract"].mean()), 4),
        "compliance_target": cfg["compliance"]["target_rate"],
        "gap_to_target_spend": float(max(cfg["compliance"]["target_rate"] * total - on_spend, 0)),
        "redirectable_off_contract_spend": float(redirectable),
        "addressable_maverick_premium": float(addressable_premium),
        "n_suppliers_below_50pct_compliance": int((supplier_comp["compliance_rate"] < 0.5).sum()),
    }

    tables = {
        "supplier_compliance": supplier_comp,
        "category_compliance": category_comp,
        "bu_compliance": bu_comp,
    }
    for name, tbl in tables.items():
        tbl.to_csv(PATHS["tables"] / f"{name}.csv", index=False)

    log.info("Compliance %.1f%% by spend | off-contract %.1fM | addressable maverick premium %.1fM",
             100 * kpis["compliance_rate_spend"], off_spend / 1e6, addressable_premium / 1e6)
    return {"kpis": kpis, "tables": tables, "maverick_lines": off}


if __name__ == "__main__":
    from .data_quality import run as dq
    clean, _ = dq()
    run(clean)

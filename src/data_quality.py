"""Phase 1 — Production-grade data-quality ingestion & validation.

Runs a battery of deterministic checks over the raw ledger, produces a machine-
readable DQ report, and returns a *clean* dataset that every downstream phase
consumes. Each check records how many rows it flagged and what action was taken.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List

import numpy as np
import pandas as pd

from .config import PATHS, get_logger, load_config

log = get_logger("data_quality")

VALID_CONTRACT = {"On-Contract", "Off-Contract"}
VALID_QUALITY = {"OK", "MINOR_DEFECT", "MAJOR_DEFECT", "REJECTED"}
DATE_COLS = ["order_date", "promised_date", "delivery_date"]


@dataclass
class CheckResult:
    name: str
    flagged: int
    pct_of_raw: float
    action: str
    severity: str  # error (row removed/repaired) | warning (kept, flagged)


@dataclass
class DQReport:
    raw_rows: int = 0
    clean_rows: int = 0
    rows_removed: int = 0
    rows_repaired: int = 0
    checks: List[CheckResult] = field(default_factory=list)
    dq_score: float = 0.0

    def add(self, name, flagged, action, severity, raw_rows):
        self.checks.append(CheckResult(
            name=name, flagged=int(flagged),
            pct_of_raw=round(100 * flagged / raw_rows, 3) if raw_rows else 0.0,
            action=action, severity=severity))

    def to_dict(self):
        d = asdict(self)
        return d


def _load_raw() -> pd.DataFrame:
    df = pd.read_csv(PATHS["data_raw"] / "procurement_pos.csv")
    for c in DATE_COLS:
        df[c] = pd.to_datetime(df[c], errors="coerce")
    return df


def run(df: pd.DataFrame | None = None, cfg=None):
    """Validate + clean. Returns (clean_df, report_dict)."""
    cfg = cfg or load_config()
    if df is None:
        df = _load_raw()
    else:
        df = df.copy()
        for c in DATE_COLS:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    raw_rows = len(df)
    rep = DQReport(raw_rows=raw_rows)
    remove_mask = pd.Series(False, index=df.index)

    # --- 1. Duplicate PO line ids (business key must be unique) -------------
    dup_line = df["po_line_id"].duplicated(keep="first")
    rep.add("duplicate_po_line_id", dup_line.sum(), "removed (keep first)", "error", raw_rows)
    remove_mask |= dup_line

    # --- 2. Fully duplicated rows ------------------------------------------
    dup_full = df.duplicated(keep="first")
    rep.add("exact_duplicate_rows", dup_full.sum(), "flagged (subset of above)", "warning", raw_rows)

    # --- 3. Missing supplier -----------------------------------------------
    miss_sup = df["supplier_id"].isna() | df["supplier_name"].isna()
    rep.add("missing_supplier", miss_sup.sum(), "removed", "error", raw_rows)
    remove_mask |= miss_sup

    # --- 4. Missing price ---------------------------------------------------
    miss_price = df["unit_price"].isna()
    rep.add("missing_unit_price", miss_price.sum(), "removed", "error", raw_rows)
    remove_mask |= miss_price

    # --- 5. Non-positive quantity ------------------------------------------
    bad_qty = df["quantity"].isna() | (df["quantity"] <= 0)
    rep.add("nonpositive_quantity", bad_qty.sum(), "removed", "error", raw_rows)
    remove_mask |= bad_qty

    # --- 6. Negative / zero price ------------------------------------------
    neg_price = df["unit_price"].notna() & (df["unit_price"] <= 0)
    rep.add("nonpositive_unit_price", neg_price.sum(), "removed", "error", raw_rows)
    remove_mask |= neg_price

    # --- 7. Date inconsistency (delivery before order) ---------------------
    date_bad = (df["delivery_date"].notna() & df["order_date"].notna()
                & (df["delivery_date"] < df["order_date"]))
    rep.add("delivery_before_order", date_bad.sum(), "removed", "error", raw_rows)
    remove_mask |= date_bad

    # --- 8. Missing / unparseable dates ------------------------------------
    date_missing = df[DATE_COLS].isna().any(axis=1)
    rep.add("missing_or_unparseable_date", date_missing.sum(), "flagged", "warning", raw_rows)

    # --- 9. Delivery anomaly (extreme late slip vs promised) ----------------
    slip = (df["delivery_date"] - df["promised_date"]).dt.days
    late_anom = slip > 120
    rep.add("delivery_slip_gt_120d", late_anom.sum(), "flagged (kept)", "warning", raw_rows)

    # --- 10. Extreme unit price (robust per-item outlier) -------------------
    extreme = _flag_extreme_prices(df)
    rep.add("extreme_unit_price_outlier", extreme.sum(), "removed", "error", raw_rows)
    remove_mask |= extreme

    # --- 11. Invalid contract-status label ----------------------------------
    bad_contract = ~df["contract_status"].isin(VALID_CONTRACT)
    rep.add("invalid_contract_status", bad_contract.sum(), "normalized -> Off-Contract", "warning", raw_rows)

    # --- 12. Invalid quality label ------------------------------------------
    bad_qual = ~df["quality_outcome"].isin(VALID_QUALITY)
    rep.add("invalid_quality_label", bad_qual.sum(), "flagged", "warning", raw_rows)

    # ---------------- apply cleaning ---------------------------------------
    clean = df.loc[~remove_mask].copy()
    # normalize the malformed contract labels among survivors
    repaired = (~clean["contract_status"].isin(VALID_CONTRACT)).sum()
    clean.loc[~clean["contract_status"].isin(VALID_CONTRACT), "contract_status"] = "Off-Contract"

    # derived helper columns used across phases
    clean["line_spend"] = (clean["quantity"] * clean["unit_price"]).round(2)
    clean["on_time"] = clean["delivery_date"] <= clean["promised_date"]
    clean["lead_time_days"] = (clean["delivery_date"] - clean["order_date"]).dt.days
    clean["promised_lead_days"] = (clean["promised_date"] - clean["order_date"]).dt.days
    clean["delay_days"] = (clean["delivery_date"] - clean["promised_date"]).dt.days
    clean["is_defect"] = clean["quality_outcome"].isin(["MAJOR_DEFECT", "REJECTED"])
    clean["order_month"] = clean["order_date"].dt.to_period("M").astype(str)
    clean["order_quarter"] = clean["order_date"].dt.to_period("Q").astype(str)
    clean["order_year"] = clean["order_date"].dt.year

    rep.clean_rows = len(clean)
    rep.rows_removed = int(remove_mask.sum())
    rep.rows_repaired = int(repaired)
    # DQ score: share of raw rows that were clean OR only needed a soft repair.
    rep.dq_score = round(100 * (raw_rows - rep.rows_removed) / raw_rows, 2)

    log.info("DQ complete | raw=%s clean=%s removed=%s repaired=%s | score=%.2f",
             f"{raw_rows:,}", f"{rep.clean_rows:,}", f"{rep.rows_removed:,}",
             rep.rows_repaired, rep.dq_score)

    out = PATHS["tables"] / "dq_report.json"
    with open(out, "w") as fh:
        json.dump(rep.to_dict(), fh, indent=2)
    clean.to_csv(PATHS["data_processed"] / "procurement_clean.csv", index=False)
    log.info("Wrote clean ledger + DQ report")
    return clean, rep.to_dict()


def _flag_extreme_prices(df: pd.DataFrame, cap: float = 4.0, mad_z: float = 8.0) -> pd.Series:
    """Flag prices that are implausibly high for their item.

    A row is extreme if its price exceeds ``cap`` x the item median OR its
    robust (MAD) z-score exceeds ``mad_z``. Thresholds are intentionally loose
    so that *legitimately* expensive suppliers (premiums up to ~50%) are NOT
    removed — only fat-finger entries (8-25x) are.
    """
    price = df["unit_price"]
    med = df.groupby("item")["unit_price"].transform("median")
    mad = df.groupby("item")["unit_price"].transform(
        lambda s: (s - s.median()).abs().median())
    mad = mad.replace(0, np.nan)
    robust_z = 0.6745 * (price - med).abs() / mad
    flag = price.notna() & (price > 0) & ((price > cap * med) | (robust_z > mad_z))
    return flag.fillna(False)


if __name__ == "__main__":
    run()

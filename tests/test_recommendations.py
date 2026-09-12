"""Phase 9 — recommendations: valid labels and defensible REPLACE logic."""
import pandas as pd
from src.config import PATHS

VALID = {"RETAIN", "NEGOTIATE", "CONSOLIDATE", "REPLACE", "MONITOR"}


def _t(name):
    return pd.read_csv(PATHS["tables"] / f"{name}.csv")


def test_every_supplier_classified():
    rec = _t("supplier_recommendations")
    assert rec["recommendation"].isin(VALID).all()
    assert rec["recommendation_reason"].notna().all()


def test_key_actions_present(results):
    k = results["recommendations"]["kpis"]
    assert k.get("n_replace", 0) > 0
    assert k.get("n_retain", 0) > 0


def test_replace_suppliers_are_actually_poor():
    rec = _t("supplier_recommendations")
    rep = rec[rec["recommendation"] == "REPLACE"]
    # each REPLACE is justified by high risk OR (weak quality & delivery & premium)
    ok = ((rep["risk_band"].isin(["HIGH", "CRITICAL"])) |
          ((rep["quality_score"] < 50) & (rep["delivery_score"] < 60) &
           (rep["weighted_price_premium"] > 0.10)))
    assert ok.all()

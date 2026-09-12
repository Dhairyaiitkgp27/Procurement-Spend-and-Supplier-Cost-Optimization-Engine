"""Phase 3 — benchmarking: excess spend is non-negative and premiums sane."""
import pandas as pd
from src.config import PATHS


def _t(name):
    return pd.read_csv(PATHS["tables"] / f"{name}.csv")


def test_excess_non_negative():
    si = _t("supplier_item_premium")
    assert (si["excess_spend_vs_reference"] >= -1e-6).all()


def test_benchmarkable_share_reasonable(results):
    share = results["bench"]["kpis"]["benchmarkable_spend_share"]
    assert 0.5 <= share <= 1.0


def test_price_index_positive():
    sp = _t("supplier_price_position")
    assert (sp["weighted_price_index"] > 0).all()

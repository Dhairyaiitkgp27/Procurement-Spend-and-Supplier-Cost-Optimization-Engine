"""Phase 2 — spend analysis: totals reconcile and concentration is well-formed."""
import pandas as pd
from src.config import PATHS


def _t(name):
    return pd.read_csv(PATHS["tables"] / f"{name}.csv")


def test_category_spend_reconciles(results):
    total = results["spend"]["kpis"]["total_spend"]
    by_cat = _t("spend_by_category")["spend"].sum()
    assert abs(by_cat - total) / total < 1e-6


def test_supplier_spend_reconciles(results):
    total = results["spend"]["kpis"]["total_spend"]
    by_sup = _t("spend_by_supplier")["spend"].sum()
    assert abs(by_sup - total) / total < 1e-6


def test_pareto_cumulative_monotonic():
    par = _t("pareto_supplier")
    cum = par["cum_share"].values
    assert (cum[1:] >= cum[:-1] - 1e-9).all()
    assert abs(cum[-1] - 1.0) < 1e-6


def test_hhi_in_unit_interval(results):
    hhi = results["spend"]["kpis"]["supplier_spend_hhi"]
    assert 0.0 < hhi <= 1.0

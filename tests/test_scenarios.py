"""Phase 10 — scenarios: monotonic ambition and sane magnitudes."""
import pandas as pd
from src.config import PATHS


def test_scenarios_monotonic(results):
    k = results["scenarios"]["kpis"]
    assert k["conservative_period"] <= k["base_period"] <= k["aggressive_period"]


def test_scenario_savings_pct_reasonable():
    scen = pd.read_csv(PATHS["tables"] / "scenario_optimization.csv")
    assert (scen["savings_pct_of_spend"] > 0).all()
    assert (scen["savings_pct_of_spend"] < 25).all()


def test_capture_rates_ordered(cfg):
    c = cfg["savings"]["capture_rates"]
    assert c["conservative"] < c["base"] < c["aggressive"]

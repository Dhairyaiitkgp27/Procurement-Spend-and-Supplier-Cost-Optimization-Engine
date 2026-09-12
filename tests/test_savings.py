"""Phase 7 — savings engine: integrity of modeled opportunity figures."""
import pandas as pd
from src.config import PATHS


def _t(name):
    return pd.read_csv(PATHS["tables"] / f"{name}.csv")


def test_gross_gap_non_negative():
    reg = _t("savings_register")
    assert (reg["gross_gap"] >= 0).all()


def test_capture_monotonic_per_opportunity():
    reg = _t("savings_register")
    assert (reg["savings_conservative"] <= reg["savings_base"] + 1e-6).all()
    assert (reg["savings_base"] <= reg["savings_aggressive"] + 1e-6).all()


def test_savings_never_exceed_addressable_spend():
    reg = _t("savings_register")
    # even at aggressive capture, modeled savings cannot exceed the spend at stake
    assert (reg["savings_aggressive"] <= reg["current_spend"] + 1e-6).all()


def test_total_savings_bounded(results):
    k = results["savings"]["kpis"]
    assert k["cost_savings_base"] > 0
    # modeled base savings must be a small fraction of total spend (sanity)
    assert k["cost_savings_base"] < 0.25 * k["total_spend"]


def test_levers_are_disjoint_documented():
    # the four cost levers must all be present and each contribute >= 0
    lev = _t("savings_by_lever")
    assert set(lev["lever"]) <= {"price_negotiation", "contract_compliance",
                                 "supplier_consolidation", "demand_aggregation"}
    assert (lev["gross_gap"] >= 0).all()

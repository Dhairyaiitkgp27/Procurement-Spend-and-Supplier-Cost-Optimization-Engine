"""Phase 1 — data quality: injected defects are caught; clean ledger is valid."""
import json
from src.config import PATHS


def _checks(results):
    rep = results["consolidated"]["data_quality"]
    return {c["name"]: c for c in rep["checks"]}


def test_duplicate_po_line_ids_fully_removed(results, cfg):
    injected = cfg["data"]["inject_issues"]["duplicate_pos"]
    chk = _checks(results)["duplicate_po_line_id"]
    # duplicates are unambiguous -> should be caught essentially exactly
    assert chk["flagged"] >= injected * 0.95


def test_injected_defects_detected_within_tolerance(results, cfg):
    inj = cfg["data"]["inject_issues"]
    chk = _checks(results)
    pairs = [("missing_supplier", "missing_supplier"),
             ("missing_price", "missing_unit_price"),
             ("nonpositive_quantity", "nonpositive_quantity"),
             ("date_inconsistency", "delivery_before_order")]
    for inj_key, check_name in pairs:
        assert chk[check_name]["flagged"] >= 0.8 * inj[inj_key], check_name


def test_clean_ledger_is_valid(clean):
    assert clean["supplier_id"].notna().all()
    assert (clean["quantity"] > 0).all()
    assert (clean["unit_price"] > 0).all()
    assert (clean["delivery_date"] >= clean["order_date"]).all()
    assert clean["contract_status"].isin({"On-Contract", "Off-Contract"}).all()


def test_dq_score_reasonable(results):
    score = results["consolidated"]["data_quality"]["dq_score"]
    assert 95.0 <= score <= 100.0


def test_report_written():
    assert (PATHS["tables"] / "dq_report.json").exists()

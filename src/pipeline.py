"""End-to-end pipeline orchestrator.

Runs every phase in dependency order, passing outputs in memory, and writes a
single consolidated KPI JSON that the documentation and dashboard read from.

    generate -> data_quality -> spend_analysis -> price_benchmarking
    -> contract_compliance -> supplier_scorecard -> supplier_risk
    -> savings_engine -> recommendations -> negotiation -> scenarios
"""
from __future__ import annotations

import json
import warnings

from .config import PATHS, ensure_dirs, fmt_money, get_logger, load_config

warnings.filterwarnings("ignore")
log = get_logger("pipeline")


def run_pipeline(force_generate: bool = True) -> dict:
    cfg = load_config()
    ensure_dirs()

    from . import data_generation, data_quality, spend_analysis, price_benchmarking
    from . import contract_compliance, supplier_scorecard, supplier_risk
    from . import savings_engine, recommendations, negotiation, scenarios

    raw_path = PATHS["data_raw"] / "procurement_pos.csv"
    if force_generate or not raw_path.exists():
        log.info("Phase 0 | generating synthetic dataset ...")
        data_generation.generate(cfg)

    log.info("Phase 1 | data quality ...")
    clean, dq_report = data_quality.run(cfg=cfg)

    log.info("Phase 2 | spend analysis ...")
    spend = spend_analysis.run(clean)

    log.info("Phase 3 | price benchmarking ...")
    bench = price_benchmarking.run(clean, cfg)

    log.info("Phase 4 | contract compliance ...")
    comp = contract_compliance.run(clean, cfg)

    log.info("Phase 5 | supplier scorecard ...")
    scard = supplier_scorecard.run(clean, bench["tables"]["supplier_price_position"], cfg)

    log.info("Phase 6 | supplier risk ...")
    risk = supplier_risk.run(clean, cfg)

    log.info("Phase 7 | savings engine ...")
    sav = savings_engine.run(clean, bench, comp, cfg)

    log.info("Phase 9 | strategic recommendations ...")
    rec = recommendations.run(
        clean,
        scard["tables"]["supplier_scorecard"],
        bench["tables"]["supplier_price_position"],
        risk["tables"]["supplier_risk"],
        sav["tables"]["savings_register"],
        comp["tables"]["supplier_compliance"],
        cfg)

    log.info("Phase 8 | negotiation prioritization ...")
    neg = negotiation.run(rec["features"], cfg)

    log.info("Phase 10 | scenario optimization ...")
    scen = scenarios.run(clean, bench, comp, cfg)

    consolidated = {
        "meta": {
            "project": cfg["project"]["name"],
            "currency": cfg["project"]["currency"],
            "data_note": "All figures derived from a SIMULATED procurement dataset. "
                         "Savings are MODELED / ESTIMATED opportunity, not realized savings.",
            "seed": cfg["data"]["seed"],
        },
        "data_quality": dq_report,
        "spend": spend["kpis"],
        "benchmarking": bench["kpis"],
        "compliance": comp["kpis"],
        "scorecard": scard["kpis"],
        "risk": risk["kpis"],
        "savings": sav["kpis"],
        "recommendations": rec["kpis"],
        "negotiation": neg["kpis"],
        "scenarios": scen["kpis"],
    }
    out = PATHS["outputs"] / "consolidated_kpis.json"
    out.write_text(json.dumps(consolidated, indent=2, default=str))
    log.info("Consolidated KPIs written -> %s", out)

    results = {"clean": clean, "spend": spend, "bench": bench, "comp": comp,
               "scorecard": scard, "risk": risk, "savings": sav,
               "recommendations": rec, "negotiation": neg, "scenarios": scen,
               "consolidated": consolidated}
    _print_headlines(consolidated)
    return results


def _print_headlines(c: dict) -> None:
    s, b, sv, sc = c["spend"], c["benchmarking"], c["savings"], c["scenarios"]
    print("\n" + "=" * 66)
    print("  PROCUREMENT OPTIMIZATION — HEADLINE RESULTS (MODELED)")
    print("=" * 66)
    print(f"  Total spend analyzed        {fmt_money(s['total_spend'])}  "
          f"({s['po_line_count']:,} PO lines, {s['supplier_count']} suppliers)")
    print(f"  Categories / BUs / countries {s['category_count']} / "
          f"{s['business_unit_count']} / {s['country_count']}")
    print(f"  Suppliers = 80% of spend    {s['suppliers_for_80pct_spend']} "
          f"({s['suppliers_for_80pct_pct']:.1f}%)")
    print(f"  Benchmarkable spend         {b['benchmarkable_spend_share']*100:.1f}%")
    print(f"  Gross cost-savings gap      {fmt_money(sv['cost_savings_gross_gap'])}")
    print(f"  Modeled savings (base 50%)  {fmt_money(sv['cost_savings_base'])}  "
          f"({sv['cost_savings_base_pct_of_spend']}% of spend)")
    print(f"  Scenario range (period)     {fmt_money(sc['conservative_period'])} -> "
          f"{fmt_money(sc['base_period'])} -> {fmt_money(sc['aggressive_period'])}")
    print(f"  Payment-terms value / yr    {fmt_money(sv['payment_terms_annual_value'])}")
    print("=" * 66 + "\n")


if __name__ == "__main__":
    run_pipeline(force_generate=True)

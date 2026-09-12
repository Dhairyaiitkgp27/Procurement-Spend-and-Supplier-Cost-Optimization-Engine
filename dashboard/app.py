"""Procurement Spend & Supplier Cost Optimization — executive dashboard.

Seven pages, all reading from the pipeline outputs in ``outputs/``:
    1. Executive Overview      5. Negotiation Targets
    2. Spend Analytics         6. Supplier Risk
    3. Supplier Scorecard      7. Executive Action Plan
    4. Savings Opportunity

Run:  streamlit run dashboard/app.py
(First run the analytics:  python -m src.pipeline)

The underlying dataset is SIMULATED. Every savings figure shown is MODELED /
ESTIMATED opportunity, not realized savings.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
KPI_FILE = ROOT / "outputs" / "consolidated_kpis.json"

# ---- palette: disciplined instrument-panel look, one teal accent -----------
INK = "#12303f"
TEAL = "#1f8a80"
AMBER = "#e0a13a"
CLAY = "#c05a48"
SLATE = "#5b7186"
BAND_COLORS = {"LOW": "#3f9d7a", "MEDIUM": "#e0a13a", "HIGH": "#d98232", "CRITICAL": "#c05a48"}
ACTION_COLORS = {"RETAIN": "#3f9d7a", "NEGOTIATE": "#1f8a80", "CONSOLIDATE": "#4f83b3",
                 "REPLACE": "#c05a48", "MONITOR": "#8a8f98"}
SEQ = ["#dbe7e6", "#9cc7c1", "#5aa79d", "#1f8a80", "#12303f"]

st.set_page_config(page_title="Procurement Optimization", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown(f"""
<style>
  .block-container {{padding-top: 2.2rem; max-width: 1400px;}}
  h1, h2, h3 {{color: {INK}; font-weight: 700;}}
  .kpi {{background: #ffffff; border: 1px solid #e6ebef; border-left: 4px solid {TEAL};
         border-radius: 8px; padding: 14px 16px;}}
  .kpi .v {{font-size: 1.7rem; font-weight: 700; color: {INK}; line-height: 1.1;}}
  .kpi .l {{font-size: 0.78rem; color: {SLATE}; margin-top: 2px;}}
  .disc {{background: #fbf6ec; border: 1px solid #ecdcb8; color: #7a5b1e;
          border-radius: 6px; padding: 8px 12px; font-size: 0.82rem;}}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_kpis():
    return json.loads(KPI_FILE.read_text()) if KPI_FILE.exists() else None


@st.cache_data
def tbl(name):
    p = TABLES / f"{name}.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def money(x, dp=1):
    a = abs(x)
    if a >= 1e9: return f"${x/1e9:.{dp}f}B"
    if a >= 1e6: return f"${x/1e6:.{dp}f}M"
    if a >= 1e3: return f"${x/1e3:.0f}K"
    return f"${x:,.0f}"


def kpi_row(items):
    cols = st.columns(len(items))
    for c, (val, lab) in zip(cols, items):
        c.markdown(f"<div class='kpi'><div class='v'>{val}</div>"
                   f"<div class='l'>{lab}</div></div>", unsafe_allow_html=True)


def style_fig(fig, h=380):
    fig.update_layout(template="plotly_white", height=h,
                      margin=dict(l=10, r=10, t=40, b=10),
                      font=dict(color=INK, size=12),
                      title_font=dict(size=15, color=INK),
                      legend=dict(orientation="h", y=-0.15))
    return fig


K = load_kpis()
if K is None:
    st.error("No pipeline outputs found. Run `python -m src.pipeline` first.")
    st.stop()

DISCLAIMER = ("Dataset is **simulated** for demonstration. All savings are "
              "**modeled / estimated opportunity**, not realized savings.")

PAGES = ["Executive Overview", "Spend Analytics", "Supplier Scorecard",
         "Savings Opportunity", "Negotiation Targets", "Supplier Risk",
         "Executive Action Plan"]
st.sidebar.title("Procurement Engine")
st.sidebar.caption("Spend & Supplier Cost Optimization")
page = st.sidebar.radio("View", PAGES)
st.sidebar.markdown("---")
st.sidebar.markdown(f"<div class='disc'>{DISCLAIMER}</div>", unsafe_allow_html=True)


# ============================ 1. EXECUTIVE OVERVIEW =========================
if page == "Executive Overview":
    st.title("Executive Overview")
    s, b, sv, sc = K["spend"], K["benchmarking"], K["savings"], K["scenarios"]
    kpi_row([
        (money(s["total_spend"]), "Total spend analyzed"),
        (f"{s['supplier_count']}", "Active suppliers"),
        (f"{s['po_line_count']:,}", "PO lines"),
        (f"{s['category_count']} / {s['business_unit_count']}", "Categories / BUs"),
    ])
    st.write("")
    kpi_row([
        (money(sv["cost_savings_gross_gap"]), "Gross savings gap (modeled)"),
        (money(sv["cost_savings_base"]), "Base-case savings (50% capture)"),
        (f"{sv['cost_savings_base_pct_of_spend']}%", "of total spend"),
        (money(sv["payment_terms_annual_value"]), "Payment-terms value / yr"),
    ])
    st.write("")
    c1, c2 = st.columns([1.15, 1])
    with c1:
        lev = tbl("savings_by_lever").sort_values("savings_base")
        names = lev["lever"].str.replace("_", " ").str.title()
        fig = go.Figure()
        fig.add_bar(y=names, x=lev["savings_conservative"], name="Conservative 25%",
                    orientation="h", marker_color=SEQ[1])
        fig.add_bar(y=names, x=lev["savings_base"] - lev["savings_conservative"],
                    name="→ Base 50%", orientation="h", marker_color=SEQ[2])
        fig.add_bar(y=names, x=lev["savings_aggressive"] - lev["savings_base"],
                    name="→ Aggressive 75%", orientation="h", marker_color=SEQ[3])
        fig.update_layout(barmode="stack", title="Modeled savings by lever (capture range)",
                          xaxis_title="Modeled savings (USD)")
        st.plotly_chart(style_fig(fig), width='stretch')
    with c2:
        scen = tbl("scenario_optimization")
        fig = go.Figure()
        fig.add_bar(x=scen["scenario"], x0=0, y=scen["cost_savings_period"],
                    marker_color=[SEQ[1], TEAL, INK],
                    text=[money(v) for v in scen["cost_savings_period"]],
                    textposition="outside")
        fig.update_layout(title="Scenario opportunity (period, modeled)",
                          yaxis_title="Modeled savings (USD)")
        st.plotly_chart(style_fig(fig), width='stretch')

    st.subheader("Where the spend sits")
    cat = tbl("spend_by_category").head(10)
    catcol = "category" if "category" in cat.columns else cat.columns[0]
    spcol = "spend" if "spend" in cat.columns else cat.columns[1]
    fig = px.treemap(cat, path=[px.Constant("All categories"), catcol], values=spcol,
                     color=spcol, color_continuous_scale=SEQ)
    st.plotly_chart(style_fig(fig, 340), width='stretch')


# ============================ 2. SPEND ANALYTICS ============================
elif page == "Spend Analytics":
    st.title("Spend Analytics")
    s = K["spend"]
    kpi_row([
        (money(s["total_spend"]), "Total spend"),
        (f"{s['suppliers_for_80pct_spend']}", "Suppliers = 80% of spend"),
        (f"{s['supplier_spend_hhi']:.3f}", "Supplier HHI"),
        (f"{s['top10_supplier_spend_share']*100:.0f}%", "Top-10 supplier share"),
    ])
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        cat = tbl("spend_by_category")
        catcol = "category" if "category" in cat.columns else cat.columns[0]
        spcol = "spend" if "spend" in cat.columns else cat.columns[1]
        cat = cat.sort_values(spcol)
        fig = px.bar(cat, x=spcol, y=catcol, orientation="h", color=spcol,
                     color_continuous_scale=SEQ, title="Spend by category")
        fig.update_layout(coloraxis_showscale=False, xaxis_title="Spend (USD)", yaxis_title="")
        st.plotly_chart(style_fig(fig), width='stretch')
    with c2:
        par = tbl("pareto_supplier")
        if not par.empty:
            par = par.reset_index(drop=True); par["rank"] = par.index + 1
            cumcol = [c for c in par.columns if "cum" in c.lower()][0]
            fig = go.Figure()
            spc = [c for c in par.columns if c.lower() in ("spend", "value")][0]
            fig.add_bar(x=par["rank"], y=par[spc], marker_color=SEQ[2], name="Supplier spend")
            fig.add_scatter(x=par["rank"], y=par[cumcol] * (100 if par[cumcol].max() <= 1 else 1),
                            yaxis="y2", mode="lines", line=dict(color=CLAY, width=3),
                            name="Cumulative %")
            fig.add_hline(y=80, yref="y2", line_dash="dot", line_color=SLATE)
            fig.update_layout(title="Supplier Pareto (spend concentration)",
                              xaxis_title="Supplier rank",
                              yaxis=dict(title="Spend (USD)"),
                              yaxis2=dict(title="Cumulative %", overlaying="y",
                                          side="right", range=[0, 100]))
            st.plotly_chart(style_fig(fig), width='stretch')
    mon = tbl("spend_monthly")
    if not mon.empty:
        mcol = mon.columns[0]; vcol = [c for c in mon.columns if c != mcol][0]
        fig = px.area(mon, x=mcol, y=vcol, title="Monthly spend trend")
        fig.update_traces(line_color=TEAL, fillcolor="rgba(31,138,128,0.15)")
        fig.update_layout(xaxis_title="", yaxis_title="Spend (USD)")
        st.plotly_chart(style_fig(fig, 320), width='stretch')
    st.subheader("Category supplier concentration")
    conc = tbl("category_supplier_concentration")
    if not conc.empty:
        st.dataframe(conc, width='stretch', hide_index=True)


# ============================ 3. SUPPLIER SCORECARD =========================
elif page == "Supplier Scorecard":
    st.title("Supplier Scorecard")
    sc = K["scorecard"]
    kpi_row([
        (f"{sc['avg_spi']:.1f}", "Average SPI (0-100)"),
        (f"{sc['ranked_suppliers']}", "Ranked suppliers"),
        (f"{sc['tier_A_suppliers']}", "Tier A suppliers"),
        (f"{sc['avg_otd_rate']*100:.0f}%", "Avg on-time delivery"),
    ])
    st.write("")
    df = tbl("supplier_scorecard")
    ranked = df[df["performance_tier"] != "Unranked"] if "performance_tier" in df else df
    c1, c2 = st.columns([1, 1.1])
    with c1:
        fig = px.histogram(ranked, x="spi", nbins=24, title="SPI distribution",
                           color_discrete_sequence=[TEAL])
        fig.update_layout(xaxis_title="Supplier Performance Index", yaxis_title="Suppliers")
        st.plotly_chart(style_fig(fig), width='stretch')
    with c2:
        if "performance_tier" in ranked:
            tier = (ranked.groupby("performance_tier")
                    .agg(suppliers=("supplier_id", "count"), spend=("spend", "sum"))
                    .reset_index())
            fig = px.bar(tier, x="performance_tier", y="spend", color="performance_tier",
                         color_discrete_sequence=SEQ[1:], title="Spend by performance tier",
                         category_orders={"performance_tier": ["A", "B", "C", "D"]})
            fig.update_layout(showlegend=False, xaxis_title="Tier", yaxis_title="Spend (USD)")
            st.plotly_chart(style_fig(fig), width='stretch')
    st.subheader("Cost vs. delivery (bubble = spend)")
    if {"cost_score", "delivery_score"}.issubset(ranked.columns):
        fig = px.scatter(ranked, x="cost_score", y="delivery_score", size="spend",
                         color="quality_score", color_continuous_scale=SEQ,
                         hover_name="supplier_name", size_max=40)
        fig.update_layout(xaxis_title="Cost competitiveness score",
                          yaxis_title="Delivery score")
        st.plotly_chart(style_fig(fig, 420), width='stretch')
    st.subheader("Supplier detail")
    show = ["supplier_name", "spend", "spi", "performance_tier", "cost_score",
            "delivery_score", "quality_score", "compliance_score", "otd_rate", "defect_rate"]
    show = [c for c in show if c in df.columns]
    st.dataframe(df.sort_values("spi", ascending=False)[show],
                 width='stretch', hide_index=True)


# ============================ 4. SAVINGS OPPORTUNITY ========================
elif page == "Savings Opportunity":
    st.title("Savings Opportunity")
    st.markdown(f"<div class='disc'>{DISCLAIMER}</div>", unsafe_allow_html=True)
    sv = K["savings"]
    st.write("")
    kpi_row([
        (money(sv["cost_savings_gross_gap"]), "Gross gap"),
        (money(sv["cost_savings_conservative"]), "Conservative (25%)"),
        (money(sv["cost_savings_base"]), "Base (50%)"),
        (money(sv["cost_savings_aggressive"]), "Aggressive (75%)"),
    ])
    st.write("")
    lev = tbl("savings_by_lever").sort_values("gross_gap", ascending=False)
    names = lev["lever"].str.replace("_", " ").str.title()
    # waterfall of gross gap by lever
    fig = go.Figure(go.Waterfall(
        orientation="v", measure=["relative"] * len(lev) + ["total"],
        x=list(names) + ["Total gross gap"],
        y=list(lev["gross_gap"]) + [0],
        connector={"line": {"color": SLATE}},
        increasing={"marker": {"color": TEAL}}, totals={"marker": {"color": INK}}))
    fig.update_layout(title="Modeled gross savings gap by lever")
    st.plotly_chart(style_fig(fig, 400), width='stretch')

    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.subheader("Top modeled opportunities")
        reg = tbl("savings_register")
        cols = ["supplier_name", "category", "lever", "current_spend",
                "gross_gap", "savings_base"]
        cols = [c for c in cols if c in reg.columns]
        st.dataframe(reg[cols].head(20), width='stretch', hide_index=True)
    with c2:
        st.subheader("Payment terms")
        pt = tbl("payment_terms_opportunity")
        if not pt.empty:
            fig = px.bar(pt, x="annual_value", y="payment_terms", color="lever",
                         orientation="h", color_discrete_sequence=[TEAL, AMBER],
                         title="Annual financial value")
            fig.update_layout(xaxis_title="USD / yr", yaxis_title="")
            st.plotly_chart(style_fig(fig, 320), width='stretch')


# ============================ 5. NEGOTIATION TARGETS ========================
elif page == "Negotiation Targets":
    st.title("Negotiation Targets")
    ng = K["negotiation"]
    kpi_row([
        (f"Top {ng['top_n']}", "Priority targets"),
        (money(ng["top_targets_spend"]), "Spend covered"),
        (money(ng["top_targets_modeled_savings"]), "Modeled savings"),
        (f"{ng['top_targets_spend_share']}%", "of total spend"),
    ])
    st.write("")
    st.subheader("Opportunity heatmap — supplier × category (modeled savings gap)")
    reg = tbl("savings_register")
    if not reg.empty:
        top_sup = (reg.groupby("supplier_name")["gross_gap"].sum()
                   .sort_values(ascending=False).head(18).index)
        piv = (reg[reg["supplier_name"].isin(top_sup)]
               .pivot_table(index="supplier_name", columns="category",
                            values="gross_gap", aggfunc="sum", fill_value=0))
        piv = piv.loc[piv.sum(axis=1).sort_values().index]
        fig = px.imshow(piv, color_continuous_scale=SEQ, aspect="auto",
                        labels=dict(color="Gross gap (USD)"))
        st.plotly_chart(style_fig(fig, 480), width='stretch')
    st.subheader("Top negotiation targets")
    tg = tbl("top_negotiation_targets")
    if not tg.empty:
        fmt = tg.copy()
        for c in ["current_spend", "modeled_savings_base"]:
            if c in fmt: fmt[c] = fmt[c].map(lambda v: money(v))
        for c in ["price_premium", "on_time_delivery_rate", "contract_compliance_rate"]:
            if c in fmt: fmt[c] = (fmt[c] * 100).round(1).astype(str) + "%"
        st.dataframe(fmt, width='stretch', hide_index=True)


# ============================ 6. SUPPLIER RISK =============================
elif page == "Supplier Risk":
    st.title("Supplier Risk")
    rk = K["risk"]
    kpi_row([
        (f"{rk['critical_suppliers']}", "Critical-risk suppliers"),
        (f"{rk['high_suppliers']}", "High-risk suppliers"),
        (money(rk["spend_at_high_or_critical"]), "Spend at high/critical"),
        (f"{rk['single_source_items']}", "Single-source items"),
    ])
    st.write("")
    df = tbl("supplier_risk")
    c1, c2 = st.columns([1, 1.2])
    with c1:
        band = (df.groupby("risk_band").agg(suppliers=("supplier_id", "count"),
                                            spend=("spend", "sum")).reset_index())
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        band["risk_band"] = pd.Categorical(band["risk_band"], order, ordered=True)
        band = band.sort_values("risk_band")
        fig = px.bar(band, x="risk_band", y="spend", color="risk_band",
                     color_discrete_map=BAND_COLORS, title="Spend by risk band")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Spend (USD)")
        st.plotly_chart(style_fig(fig), width='stretch')
    with c2:
        fig = px.scatter(df, x="composite_risk", y="spend", color="risk_band",
                         color_discrete_map=BAND_COLORS, hover_name="supplier_name",
                         size="spend", size_max=32, title="Risk vs. spend exposure")
        fig.update_layout(xaxis_title="Composite risk score", yaxis_title="Spend (USD)")
        st.plotly_chart(style_fig(fig), width='stretch')
    cc1, cc2 = st.columns(2)
    with cc1:
        st.subheader("Highest-risk suppliers")
        cols = [c for c in ["supplier_name", "composite_risk", "risk_band",
                            "primary_risk_driver", "spend"] if c in df.columns]
        st.dataframe(df.sort_values("composite_risk", ascending=False)[cols].head(12),
                     width='stretch', hide_index=True)
    with cc2:
        st.subheader("Single / dual-source items")
        it = tbl("item_source_concentration")
        if not it.empty:
            it = it[it["n_suppliers"] <= 2].sort_values("spend", ascending=False)
            cols = [c for c in ["item", "category", "n_suppliers", "spend", "top_supplier"]
                    if c in it.columns]
            st.dataframe(it[cols], width='stretch', hide_index=True)


# ============================ 7. EXECUTIVE ACTION PLAN ======================
elif page == "Executive Action Plan":
    st.title("Executive Action Plan")
    st.caption("Rule-based strategic disposition per supplier")
    rec = K["recommendations"]
    summ = tbl("recommendation_summary")
    order = ["RETAIN", "NEGOTIATE", "CONSOLIDATE", "REPLACE", "MONITOR"]
    summ["recommendation"] = pd.Categorical(summ["recommendation"], order, ordered=True)
    summ = summ.sort_values("recommendation")
    kpi_row([(f"{int(summ.loc[summ.recommendation==a, 'suppliers'].sum() or 0)}", a)
             for a in order[:4]])
    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(summ, x="recommendation", y="suppliers", color="recommendation",
                     color_discrete_map=ACTION_COLORS, title="Suppliers by action")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Suppliers")
        st.plotly_chart(style_fig(fig), width='stretch')
    with c2:
        fig = px.bar(summ, x="recommendation", y="spend", color="recommendation",
                     color_discrete_map=ACTION_COLORS, title="Spend by action")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Spend (USD)")
        st.plotly_chart(style_fig(fig), width='stretch')

    df = tbl("supplier_recommendations")
    st.subheader("Supplier dispositions")
    pick = st.multiselect("Filter by action", order, default=order)
    view = df[df["recommendation"].isin(pick)] if "recommendation" in df else df
    cols = [c for c in ["supplier_name", "primary_category", "recommendation",
                        "recommendation_reason", "spend", "spi", "weighted_price_premium",
                        "risk_band", "savings_base"] if c in view.columns]
    st.dataframe(view.sort_values("spend", ascending=False)[cols],
                 width='stretch', hide_index=True)

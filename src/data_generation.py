"""Reproducible synthetic procurement dataset generator.

The dataset is SYNTHETIC. It is engineered to resemble a large multinational's
purchase-order ledger and to contain *detectable* inefficiencies (overpriced
suppliers, off-contract "maverick" spend, chronically late / defective
suppliers, and fragmented spend that could be consolidated) so that the
downstream analytics have genuine signal to find.

No figure produced anywhere in this project is invented: everything is computed
from the ledger emitted here. Because the ledger is simulated, all savings are
reported as MODELED / ESTIMATED opportunity, never realized savings.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PATHS, ensure_dirs, get_logger, load_config

log = get_logger("data_generation")

# ---------------------------------------------------------------------------
# Reference master data
# ---------------------------------------------------------------------------
BUSINESS_UNITS = [
    "NA_Manufacturing", "EMEA_Operations", "APAC_Operations",
    "Corporate_Functions", "RnD_Division",
]
# Relative share of PO lines by business unit.
BU_WEIGHTS = np.array([0.30, 0.24, 0.22, 0.12, 0.12])

# Supplier home countries with a structural cost index (region pricing).
COUNTRY_COST_INDEX = {
    "United States": 1.12, "Germany": 1.10, "United Kingdom": 1.08, "Japan": 1.09,
    "China": 0.88, "India": 0.86, "Vietnam": 0.85, "Mexico": 0.92,
    "Poland": 0.95, "Brazil": 0.94,
}
COUNTRIES = list(COUNTRY_COST_INDEX)

# category -> list of (item_name, reference_unit_price, qty_lo, qty_hi)
# Quantities are per-PO-line and sized so blended spend lands in the
# hundreds-of-millions with a realistic category mix.
CATEGORY_ITEMS = {
    "IT_Hardware": [
        ("Laptop_Standard_14in", 1200, 1, 30), ("Laptop_Pro_16in", 2100, 1, 18),
        ("Monitor_27in_4K", 450, 2, 55), ("Docking_Station", 180, 2, 70),
        ("Server_Rack_1U", 6500, 1, 6), ("Network_Switch_48p", 3200, 1, 9),
    ],
    "IT_Software": [
        ("SaaS_CRM_Seat_Yr", 90, 20, 500), ("SaaS_Collab_Seat_Yr", 22, 50, 1400),
        ("Endpoint_Security_Lic", 140, 10, 280), ("Database_License_Core", 3500, 1, 16),
    ],
    "Office_Supplies": [
        ("Paper_A4_Case", 42, 10, 180), ("Toner_Cartridge", 95, 3, 70),
        ("Ergonomic_Chair", 260, 1, 35), ("Stationery_Kit", 35, 10, 180),
    ],
    "Logistics_Freight": [
        ("FTL_Domestic_Load", 1800, 1, 22), ("LTL_Shipment", 420, 1, 50),
        ("Ocean_Container_40ft", 3900, 1, 12), ("Air_Freight_per_kg", 6.5, 100, 2600),
        ("Last_Mile_Parcel", 9.5, 100, 4000),
    ],
    "Raw_Metals": [
        ("Steel_Coil_Tonne", 820, 2, 55), ("Aluminum_Ingot_Tonne", 2450, 1, 28),
        ("Copper_Wire_Tonne", 9200, 1, 8), ("Stainless_Sheet_Tonne", 3100, 1, 22),
    ],
    "Raw_Polymers": [
        ("PP_Resin_Tonne", 1350, 2, 45), ("PET_Resin_Tonne", 1150, 2, 55),
        ("ABS_Resin_Tonne", 2200, 1, 30), ("Nylon_Compound_Tonne", 3400, 1, 20),
    ],
    "MRO": [
        ("Bearing_Set", 140, 3, 55), ("Hydraulic_Pump", 1900, 1, 10),
        ("Industrial_Filter", 85, 5, 110), ("Safety_Gloves_Box", 28, 10, 260),
        ("Lubricant_Drum", 320, 1, 50),
    ],
    "Professional_Services": [
        ("Consulting_Day", 1600, 1, 25), ("Audit_Engagement", 22000, 1, 3),
        ("Contract_Dev_Day", 720, 1, 35), ("Training_Session", 3800, 1, 8),
    ],
    "Packaging": [
        ("Corrugated_Box_1k", 480, 2, 90), ("Pallet_Wood", 14, 50, 1800),
        ("Shrink_Film_Roll", 95, 5, 130), ("Label_Roll_10k", 60, 10, 260),
    ],
    "Facilities": [
        ("HVAC_Service_Visit", 2400, 1, 10), ("Electricity_MWh", 95, 50, 1100),
        ("Cleaning_Contract_Mo", 5200, 1, 8), ("Security_Service_Mo", 4100, 1, 8),
    ],
}
CATEGORIES = list(CATEGORY_ITEMS)
# Share of PO *lines* per category (raw materials fewer lines but high value;
# freight / packaging / software high line count).
CATEGORY_LINE_WEIGHTS = np.array(
    [0.11, 0.10, 0.09, 0.15, 0.08, 0.08, 0.12, 0.05, 0.10, 0.10]
)

# Specialty items deliberately restricted to 1-2 suppliers -> single/dual-source
# concentration risk (no competitive benchmark available for these).
SINGLE_SOURCE_ITEMS = {
    "Copper_Wire_Tonne": 1,
    "Audit_Engagement": 1,
    "Database_License_Core": 2,
    "Nylon_Compound_Tonne": 2,
}

PAYMENT_TERMS = ["NET15", "NET30", "NET45", "NET60", "NET90", "2_10_NET30"]
PAYMENT_TERM_DAYS = {"NET15": 15, "NET30": 30, "NET45": 45, "NET60": 60,
                     "NET90": 90, "2_10_NET30": 30}

# Supplier archetypes: (share, price_lo, price_hi, otd_lo, otd_hi,
#                        defect_lo, defect_hi, contract_propensity,
#                        annual_price_drift, leadtime_cv)
ARCHETYPES = {
    "Strategic":      (0.15, 0.90, 1.02, 0.92, 0.985, 0.004, 0.020, 0.90, 0.005, 0.10),
    "Standard":       (0.44, 1.00, 1.10, 0.82, 0.93,  0.010, 0.040, 0.65, 0.010, 0.18),
    "Overpriced":     (0.15, 1.15, 1.42, 0.80, 0.92,  0.010, 0.045, 0.45, 0.020, 0.20),
    "Risky":          (0.13, 0.98, 1.20, 0.58, 0.80,  0.045, 0.120, 0.40, 0.035, 0.35),
    "CheapButRisky":  (0.09, 0.80, 0.94, 0.62, 0.82,  0.050, 0.100, 0.35, 0.015, 0.30),
    "Distressed":     (0.04, 1.05, 1.28, 0.44, 0.62,  0.100, 0.185, 0.30, 0.050, 0.42),
}

NAME_ROOTS = [
    "Meridian", "Apex", "Vertex", "Summit", "Keystone", "Ironclad", "BlueRidge",
    "Cascade", "Pinnacle", "Northstar", "Vanguard", "Orion", "Titan", "Atlas",
    "Sterling", "Crimson", "Falcon", "Granite", "Harbor", "Zenith", "Delta",
    "Quantum", "Nimbus", "Helios", "Cobalt", "Emerald", "Sequoia", "Onyx",
    "Redwood", "Brightwater", "Copperline", "Silverpeak", "Ironwood", "Everest",
    "Frontier", "Beacon", "Trident", "Cardinal", "Sentinel", "Pioneer",
]
NAME_SUFFIX = ["Industries", "Supply Co", "Global", "Trading", "Manufacturing",
               "Group", "Logistics", "Materials", "Partners", "Systems",
               "Solutions", "Components", "Works", "Enterprises"]


# ---------------------------------------------------------------------------
def _build_suppliers(rng: np.random.Generator, n: int) -> pd.DataFrame:
    """Create the supplier master with archetype-driven behaviour."""
    arche_names = list(ARCHETYPES)
    shares = np.array([ARCHETYPES[a][0] for a in arche_names])
    shares = shares / shares.sum()
    assigned = rng.choice(arche_names, size=n, p=shares)

    # Unique-ish company names.
    combos = [(r, s) for r in NAME_ROOTS for s in NAME_SUFFIX]
    rng.shuffle(combos)
    names = [f"{combos[i][0]} {combos[i][1]}" for i in range(n)]

    rows = []
    for i in range(n):
        a = ARCHETYPES[assigned[i]]
        (_, p_lo, p_hi, otd_lo, otd_hi, d_lo, d_hi, contract_prop, drift, lt_cv) = a
        country = rng.choice(COUNTRIES)
        rows.append({
            "supplier_id": f"S{i+1:03d}",
            "supplier_name": names[i],
            "supplier_country": country,
            "archetype": assigned[i],           # ground truth, NOT used by analytics
            "price_factor": rng.uniform(p_lo, p_hi),
            "otd_base": rng.uniform(otd_lo, otd_hi),
            "defect_rate": rng.uniform(d_lo, d_hi),
            "contract_propensity": contract_prop,
            "annual_drift": drift,
            "leadtime_cv": lt_cv,
            "promised_leadtime": int(rng.integers(7, 45)),
            # Per-supplier price noise scale (volatility signal for risk phase).
            "price_noise": rng.uniform(0.10, 0.24) if assigned[i] in ("Risky", "Distressed")
                           else rng.uniform(0.02, 0.10),
        })
    sup = pd.DataFrame(rows)

    # Assign each supplier 1-3 categories it serves (creates concentration /
    # single-source patterns because not every supplier covers every category).
    served = []
    for _ in range(n):
        k = rng.integers(1, 4)
        served.append(set(rng.choice(CATEGORIES, size=k, replace=False)))
    sup["categories"] = served
    return sup


def _category_supplier_pool(sup: pd.DataFrame):
    """Map category -> (supplier_index_array, sampling_probability_array).

    Probabilities are skewed (Zipf-like) so a few suppliers hold large share of
    each category -> realistic concentration / HHI signal.
    """
    pools = {}
    rng = np.random.default_rng(1)  # local, deterministic skew
    for cat in CATEGORIES:
        idx = np.array([i for i, s in enumerate(sup["categories"]) if cat in s])
        if len(idx) == 0:  # ensure every category has suppliers
            idx = rng.choice(len(sup), size=4, replace=False)
        weights = 1.0 / np.arange(1, len(idx) + 1) ** rng.uniform(0.7, 1.3)
        rng.shuffle(weights)
        weights = weights / weights.sum()
        pools[cat] = (idx, weights)
    return pools


def _sample_dates(rng, n, start, end, promised_leadtime, otd, lt_cv):
    """Vectorised order/promised/delivery dates for one supplier-block."""
    span = (end - start).days
    order_offset = rng.integers(0, span, size=n)
    order_date = start + pd.to_timedelta(order_offset, unit="D")
    promised = order_date + pd.to_timedelta(promised_leadtime, unit="D")

    # On-time draw: if late, positive slip; slip magnitude scales with lead-time CV.
    on_time = rng.random(n) < otd
    slip = np.where(
        on_time,
        rng.integers(-5, 1, size=n),                     # early / exactly on time (<=0)
        np.round(rng.gamma(shape=2.0, scale=promised_leadtime * lt_cv + 2, size=n)),
    ).astype(int)
    delivery = promised + pd.to_timedelta(slip, unit="D")
    return order_date, promised, delivery, on_time


def generate(cfg=None) -> pd.DataFrame:
    cfg = cfg or load_config()
    ensure_dirs()
    dcfg = cfg["data"]
    rng = np.random.default_rng(dcfg["seed"])

    start = pd.Timestamp(dcfg["start_date"])
    end = pd.Timestamp(dcfg["end_date"])
    n_target = dcfg["n_po_lines"]

    sup = _build_suppliers(rng, dcfg["n_suppliers"])
    pools = _category_supplier_pool(sup)

    # Fix a small set of items to 1-2 sole suppliers (single/dual-source).
    item_to_cat = {it[0]: cat for cat, items in CATEGORY_ITEMS.items() for it in items}
    sole_suppliers = {}
    for it_name, k in SINGLE_SOURCE_ITEMS.items():
        idx_pool, prob_pool = pools[item_to_cat[it_name]]
        order = np.argsort(prob_pool)[::-1]
        sole_suppliers[it_name] = idx_pool[order[:k]]

    # Lines per category.
    cat_counts = rng.multinomial(n_target, CATEGORY_LINE_WEIGHTS / CATEGORY_LINE_WEIGHTS.sum())

    frames = []
    for cat, n_cat in zip(CATEGORIES, cat_counts):
        if n_cat == 0:
            continue
        items = CATEGORY_ITEMS[cat]
        item_names = [it[0] for it in items]
        item_ref = np.array([it[1] for it in items], float)
        item_lo = np.array([it[2] for it in items], float)
        item_hi = np.array([it[3] for it in items], float)

        idx_pool, prob_pool = pools[cat]
        chosen_sup = rng.choice(idx_pool, size=n_cat, p=prob_pool)

        # Item choice (some skew toward first items).
        item_p = 1.0 / np.arange(1, len(items) + 1) ** 0.5
        item_p = item_p / item_p.sum()
        chosen_item = rng.choice(len(items), size=n_cat, p=item_p)

        # Force single/dual-source items onto their designated supplier(s).
        for it_name, sole in sole_suppliers.items():
            if it_name in item_names:
                j = item_names.index(it_name)
                m = chosen_item == j
                if m.any():
                    chosen_sup[m] = rng.choice(sole, size=int(m.sum()))

        # Quantity: lognormal-ish within [lo, hi] per item.
        lo = item_lo[chosen_item]; hi = item_hi[chosen_item]
        u = rng.beta(1.6, 3.0, size=n_cat)  # skew toward smaller orders
        quantity = np.round(lo + u * (hi - lo)).astype(int)
        quantity = np.maximum(quantity, 1)

        ref = item_ref[chosen_item]

        # --- price construction -------------------------------------------
        price_factor = sup["price_factor"].to_numpy()[chosen_sup]
        country = sup["supplier_country"].to_numpy()[chosen_sup]
        cost_index = np.array([COUNTRY_COST_INDEX[c] for c in country])
        drift = sup["annual_drift"].to_numpy()[chosen_sup]
        noise_scale = sup["price_noise"].to_numpy()[chosen_sup]

        # Business unit.
        bu = rng.choice(BUSINESS_UNITS, size=n_cat, p=BU_WEIGHTS)

        # Dates per supplier (loop over the suppliers actually used in block).
        order_date = np.empty(n_cat, dtype="datetime64[ns]")
        promised = np.empty(n_cat, dtype="datetime64[ns]")
        delivery = np.empty(n_cat, dtype="datetime64[ns]")
        for s_idx in np.unique(chosen_sup):
            mask = chosen_sup == s_idx
            m = int(mask.sum())
            od, pr, dl, _ = _sample_dates(
                rng, m, start, end,
                int(sup["promised_leadtime"].iloc[s_idx]),
                float(sup["otd_base"].iloc[s_idx]),
                float(sup["leadtime_cv"].iloc[s_idx]),
            )
            order_date[mask] = od.values
            promised[mask] = pr.values
            delivery[mask] = dl.values

        years_elapsed = (pd.to_datetime(order_date) - start).days / 365.25
        drift_mult = 1.0 + drift * years_elapsed

        # Contract status: propensity per supplier, off-contract adds a premium.
        contract_prop = sup["contract_propensity"].to_numpy()[chosen_sup]
        on_contract = rng.random(n_cat) < contract_prop
        maverick_bump = np.where(on_contract, 1.0,
                                 rng.uniform(1.03, 1.18, size=n_cat))

        noise = rng.normal(1.0, noise_scale)
        unit_price = ref * price_factor * cost_index * drift_mult * maverick_bump * noise
        unit_price = np.maximum(unit_price, ref * 0.4)  # floor
        unit_price = np.round(unit_price, 2)

        # Quality outcome from supplier defect rate (worsens slightly over time
        # for high-drift suppliers -> "worsening performance" signal).
        defect_rate = sup["defect_rate"].to_numpy()[chosen_sup]
        eff_defect = np.clip(defect_rate * (1 + 0.15 * years_elapsed * (drift > 0.02)), 0, 0.5)
        roll = rng.random(n_cat)
        quality = np.where(
            roll < eff_defect * 0.25, "REJECTED",
            np.where(roll < eff_defect * 0.6, "MAJOR_DEFECT",
                     np.where(roll < eff_defect, "MINOR_DEFECT", "OK")),
        )

        pay_p = np.array([0.05, 0.34, 0.24, 0.18, 0.11, 0.08])
        payment = rng.choice(PAYMENT_TERMS, size=n_cat, p=pay_p / pay_p.sum())

        block = pd.DataFrame({
            "supplier_id": sup["supplier_id"].to_numpy()[chosen_sup],
            "supplier_name": sup["supplier_name"].to_numpy()[chosen_sup],
            "supplier_country": country,
            "category": cat,
            "item": [item_names[i] for i in chosen_item],
            "business_unit": bu,
            "order_date": pd.to_datetime(order_date),
            "promised_date": pd.to_datetime(promised),
            "delivery_date": pd.to_datetime(delivery),
            "quantity": quantity,
            "unit_price": unit_price,
            "payment_terms": payment,
            "contract_status": np.where(on_contract, "On-Contract", "Off-Contract"),
            "quality_outcome": quality,
        })
        frames.append(block)

    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1.0, random_state=dcfg["seed"]).reset_index(drop=True)

    # Purchase-order id: group ~1-4 lines into a PO.
    n = len(df)
    n_po = int(n / 2.3)
    df["po_id"] = "PO" + rng.integers(100000, 100000 + n_po, size=n).astype(str)
    df["po_line_id"] = ["L" + f"{i+1:06d}" for i in range(n)]
    df["line_spend"] = (df["quantity"] * df["unit_price"]).round(2)

    df = _inject_quality_issues(df, rng, dcfg["inject_issues"])

    cols = ["po_id", "po_line_id", "supplier_id", "supplier_name", "supplier_country",
            "item", "category", "business_unit", "order_date", "promised_date",
            "delivery_date", "quantity", "unit_price", "line_spend", "payment_terms",
            "contract_status", "quality_outcome"]
    df = df[cols]

    log.info("Generated %s PO lines (incl. injected defects) | %s suppliers | %s categories",
             f"{len(df):,}", df["supplier_id"].nunique(), df["category"].nunique())

    out = PATHS["data_raw"] / "procurement_pos.csv"
    df.to_csv(out, index=False)
    sup.drop(columns=["categories"]).to_csv(PATHS["data_raw"] / "supplier_master_truth.csv", index=False)
    log.info("Wrote raw ledger -> %s", out)
    return df


def _inject_quality_issues(df: pd.DataFrame, rng, spec: dict) -> pd.DataFrame:
    """Corrupt a controlled number of rows so Phase 1 has real defects to catch."""
    df = df.copy()
    n = len(df)

    def pick(k):
        return rng.choice(n, size=min(k, n), replace=False)

    # 1) duplicate PO lines (append exact copies)
    dup_rows = df.iloc[pick(spec["duplicate_pos"])].copy()
    df = pd.concat([df, dup_rows], ignore_index=True)

    # refresh n / index after append
    n = len(df)

    # 2) missing supplier
    df.loc[pick(spec["missing_supplier"]), ["supplier_id", "supplier_name"]] = np.nan
    # 3) missing price
    idx = pick(spec["missing_price"]); df.loc[idx, "unit_price"] = np.nan
    df.loc[idx, "line_spend"] = np.nan
    # 4) non-positive quantity
    idx = pick(spec["nonpositive_quantity"])
    df.loc[idx, "quantity"] = rng.choice([0, -1, -5, -10], size=len(idx))
    # 5) negative price
    idx = pick(spec["negative_price"])
    df.loc[idx, "unit_price"] = -np.abs(df.loc[idx, "unit_price"].fillna(50))
    # 6) date inconsistency (delivery before order)
    idx = pick(spec["date_inconsistency"])
    df.loc[idx, "delivery_date"] = df.loc[idx, "order_date"] - pd.to_timedelta(
        rng.integers(2, 30, size=len(idx)), unit="D")
    # 7) extreme price (fat-finger)
    idx = pick(spec["extreme_price"])
    df.loc[idx, "unit_price"] = df.loc[idx, "unit_price"].abs().fillna(100) * rng.uniform(8, 25, size=len(idx))
    # 8) contract flag conflict: force Off-Contract on some On-Contract lines
    on_idx = df.index[df["contract_status"] == "On-Contract"].to_numpy()
    if len(on_idx):
        idx = rng.choice(on_idx, size=min(spec["contract_flag_conflict"], len(on_idx)), replace=False)
        df.loc[idx, "contract_status"] = "OFF-CONTRACT?"  # inconsistent label

    # recompute line_spend where still valid
    valid = df["unit_price"].notna() & df["quantity"].notna()
    df.loc[valid, "line_spend"] = (df.loc[valid, "quantity"] * df.loc[valid, "unit_price"]).round(2)
    return df.reset_index(drop=True)


if __name__ == "__main__":
    generate()

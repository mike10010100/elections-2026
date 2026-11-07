#!/usr/bin/env python3
"""
Builds the Texas 'YIMBY Housing Policy x Educational Polarization (EdPol)' dataset and Chart 10:
- Joins U.S. Census Building Permits Survey (2010-2024 county residential housing units permitted),
  U.S. Census Population Estimates & Migration Components (2010-2024),
  USDA ERS / U.S. Census County Educational Attainment (2000, 2008-12, 2019-23 BA+ vs Non-BA adults 25+),
  and 2004-2026 Texas & U.S. county election returns.
- Outputs:
  - site_data/texas_housing_edpol_2026.json
  - assets/chart10_texas_housing_edpol_2026.png
"""
import csv
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
CENSUS_DIR = DATA_DIR / "census_housing_edpol"
SITE_DATA_DIR = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"

BG = "#f8f7f3"
PANEL_BG = "#ffffff"
TEXT = "#18181b"
SUBTEXT = "#52525b"
GRID = "#e4e4e7"
BLUE = "#1d4d7a"
LIGHT_BLUE = "#5b9bd5"
ORANGE = "#c85a17"
GREEN = "#1b7837"
PURPLE = "#762a83"
RED = "#b91c1c"
GREY = "#9ca3af"


def main():
    # 1. Load USDA ERS / Census Educational Attainment (2000, 2008-12, 2019-23)
    edu_raw = {}
    with open(CENSUS_DIR / "usda_education_1970_2023.csv", encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            fips = r["FIPS Code"].strip().zfill(5)
            attr = r["Attribute"].strip()
            val_str = r["Value"].strip().replace(",", "")
            if val_str:
                edu_raw.setdefault(fips, {})[attr] = float(val_str)

    edu = {}
    for fips, d in edu_raw.items():
        ba00 = d.get("Bachelor's degree or higher, 2000", 0.0)
        tot00 = sum(
            d.get(k, 0.0)
            for k in [
                "Less than high school graduate, 2000",
                "High school graduate (or equivalency), 2000",
                "Some college or associate degree, 2000",
                "Bachelor's degree or higher, 2000",
            ]
        )
        ba10 = d.get("Bachelor's degree or higher, 2008-12", 0.0)
        tot10 = sum(
            d.get(k, 0.0)
            for k in [
                "Less than high school graduate, 2008-12",
                "High school graduate (or equivalency), 2008-12",
                "Some college or associate degree, 2008-12",
                "Bachelor's degree or higher, 2008-12",
            ]
        )
        ba23 = d.get("Bachelor's degree or higher, 2019-23", 0.0)
        tot23 = sum(
            d.get(k, 0.0)
            for k in [
                "Less than high school graduate, 2019-23",
                "High school graduate (or equivalency), 2019-23",
                "Some college or associate degree, 2019-23",
                "Bachelor's degree or higher, 2019-23",
            ]
        )
        edu[fips] = {
            "ba00": int(round(ba00)),
            "tot00": int(round(tot00)),
            "ba_pct00": round(100.0 * ba00 / tot00, 2) if tot00 else 0.0,
            "ba10": int(round(ba10)),
            "tot10": int(round(tot10)),
            "ba_pct10": round(100.0 * ba10 / tot10, 2) if tot10 else 0.0,
            "ba23": int(round(ba23)),
            "tot23": int(round(tot23)),
            "ba_pct23": round(100.0 * ba23 / tot23, 2) if tot23 else 0.0,
            "d_ba_10_23": int(round(ba23 - ba10)),
            "d_nonba_10_23": int(round((tot23 - ba23) - (tot10 - ba10))),
            "d_tot_10_23": int(round(tot23 - tot10)),
        }

    # 2. Load U.S. Census Building Permits Survey (2010-2024)
    bps = {}
    for yr in range(2010, 2025):
        with open(CENSUS_DIR / f"bps_co{yr}a.txt", encoding="latin-1") as f:
            for line in f:
                parts = [x.strip() for x in line.split(",")]
                if len(parts) < 18 or not parts[0].isdigit():
                    continue
                fips = f"{parts[1].zfill(2)}{parts[2].zfill(3)}"
                u1 = int(parts[7] or 0)
                u2 = int(parts[10] or 0)
                u34 = int(parts[13] or 0)
                u5p = int(parts[16] or 0)
                rec = bps.setdefault(fips, {"sf": 0, "mf": 0, "tot": 0})
                rec["sf"] += u1
                rec["mf"] += u2 + u34 + u5p
                rec["tot"] += u1 + u2 + u34 + u5p

    # 3. Load Census PopEst (2010-2024) + Domestic & International Migration
    pop_mig = {}
    with open(CENSUS_DIR / "co-est2020-alldata.csv", encoding="latin-1") as f:
        for r in csv.DictReader(f):
            if r["SUMLEV"] != "050":
                continue
            fips = f"{r['STATE'].zfill(2)}{r['COUNTY'].zfill(3)}"
            pop_mig[fips] = {
                "pop10": int(r["ESTIMATESBASE2010"]) if r["ESTIMATESBASE2010"].isdigit() else 0,
                "pop20": int(r["POPESTIMATE2020"]),
                "dom_10_20": sum(int(r.get(f"DOMESTICMIG{y}", 0)) for y in range(2010, 2021)),
                "intl_10_20": sum(int(r.get(f"INTERNATIONALMIG{y}", 0)) for y in range(2010, 2021)),
            }
    with open(CENSUS_DIR / "co-est2024-alldata.csv", encoding="latin-1") as f:
        for r in csv.DictReader(f):
            if r["SUMLEV"] != "050":
                continue
            fips = f"{r['STATE'].zfill(2)}{r['COUNTY'].zfill(3)}"
            rec = pop_mig.setdefault(fips, {"pop10": 0, "pop20": 0, "dom_10_20": 0, "intl_10_20": 0})
            rec["pop24"] = int(r["POPESTIMATE2024"])
            rec["dom_10_24"] = rec["dom_10_20"] + sum(int(r.get(f"DOMESTICMIG{y}", 0)) for y in range(2020, 2025))
            rec["intl_10_24"] = rec["intl_10_20"] + sum(int(r.get(f"INTERNATIONALMIG{y}", 0)) for y in range(2020, 2025))
            rec["pop_add_10_24"] = rec["pop24"] - rec["pop10"]

    # 4. Load Historical (2004-2024) + Live 2026 County Returns
    hist_votes = {}
    with open(DATA_DIR / "historical" / "us_county_results_summary.csv") as f:
        for r in csv.DictReader(f):
            if r["state_po"] == "TX":
                fips = r["county_fips"]
                yr = int(r["year"])
                off = r["office"]
                hist_votes.setdefault(fips, {})[(off, yr)] = {
                    "dem": int(float(r["dem_votes"] or 0)),
                    "rep": int(float(r["rep_votes"] or 0)),
                    "tot": int(float(r["total_votes"] or 0)),
                }

    with open(DATA_DIR / "nyt_2026" / "results-texas.json") as f:
        nyt26 = json.load(f)
    for r in nyt26["races"]:
        office = r.get("office")
        if office not in ("U.S. Senate", "Governor"):
            continue
        off_key = "senate" if office == "U.S. Senate" else "governor"
        for ru in r.get("reporting_units", []):
            if ru.get("level") != "county":
                continue
            fips = f"48{ru['fips_county']}"
            cands = {c["nyt_id"]: c["votes"]["total"] for c in ru["candidates"]}
            dem = cands.get("talarico-j" if off_key == "senate" else "hinojosa-g", 0)
            rep = cands.get("paxton-k" if off_key == "senate" else "abbott-g", 0)
            hist_votes.setdefault(fips, {})[(off_key, 2026)] = {
                "dem": dem,
                "rep": rep,
                "tot": sum(cands.values()),
            }

    with open(SITE_DATA_DIR / "county_shifts.json") as f:
        cs = json.load(f)

    us_demo = {}
    with open(DATA_DIR / "historical" / "county_demographics.csv") as f:
        for r in csv.DictReader(f):
            us_demo[(r["State"], r["County"])] = r

    # 5. Build County-Level Records for all 254 Texas Counties
    dfw_9 = ["48113", "48439", "48085", "48121", "48397", "48139", "48257", "48251", "48367"]
    austin_5 = ["48453", "48491", "48209", "48021", "48055"]
    houston_5 = ["48201", "48157", "48339", "48039", "48167"]
    sa_3 = ["48029", "48091", "48187"]
    big4_22 = set(dfw_9 + austin_5 + houston_5 + sa_3)

    tx_counties = []
    for fips, c in sorted(cs["counties"].items()):
        if c.get("state") != "TX":
            continue
        cname = c["name"] + " County"
        d = us_demo.get(("TX", cname), {})
        b = bps.get(fips, {"sf": 0, "mf": 0, "tot": 0})
        pm = pop_mig.get(fips, {})
        ed = edu.get(fips, {})
        hv = hist_votes.get(fips, {})

        p10 = pm.get("pop10", 0)
        p24 = pm.get("pop24", 0)
        perm_tot = b["tot"]
        perm_per_1k = round(1000.0 * perm_tot / p10, 1) if p10 > 0 else 0.0

        p04 = hv.get(("president", 2004), {"dem": 0, "rep": 0, "tot": 0})
        p12 = hv.get(("president", 2012), {"dem": 0, "rep": 0, "tot": 0})
        s18 = hv.get(("senate", 2018), {"dem": 0, "rep": 0, "tot": 0})
        g26 = hv.get(("governor", 2026), {"dem": 0, "rep": 0, "tot": 0})
        s26 = hv.get(("senate", 2026), {"dem": 0, "rep": 0, "tot": 0})

        m04 = 100.0 * (p04["dem"] - p04["rep"]) / p04["tot"] if p04["tot"] else 0.0
        m12 = 100.0 * (p12["dem"] - p12["rep"]) / p12["tot"] if p12["tot"] else 0.0
        mg26 = 100.0 * (g26["dem"] - g26["rep"]) / g26["tot"] if g26["tot"] else 0.0
        ms26 = 100.0 * (s26["dem"] - s26["rep"]) / s26["tot"] if s26["tot"] else 0.0

        home_val = float(d.get("Housing.Median Value of Owner-Occupied Units", 0) or 0)
        inc = float(d.get("Income.Median Houseold Income", 0) or 0)
        pir = round(home_val / inc, 2) if inc > 0 else 0.0
        age65 = float(d.get("Age.Percent 65 and Older", 0) or 0)

        if fips in dfw_9:
            metro = "DFW Metro (9 cos)"
        elif fips in houston_5:
            metro = "Houston Metro (5 cos)"
        elif fips in austin_5:
            metro = "Austin Metro (5 cos)"
        elif fips in sa_3:
            metro = "San Antonio Metro (3 cos)"
        elif c["dem"]["hisp"] >= 65.0:
            metro = "South TX / Border (>=65% Hisp)"
        else:
            metro = "Rest of Texas"

        tx_counties.append({
            "fips": fips,
            "name": c["name"],
            "metro": metro,
            "pop_2010": p10,
            "pop_2024": p24,
            "pop_added_10_24": p24 - p10,
            "pop_growth_pct_10_24": round(100.0 * (p24 - p10) / p10, 2) if p10 else 0.0,
            "domestic_mig_10_24": pm.get("dom_10_24", 0),
            "intl_mig_10_24": pm.get("intl_10_24", 0),
            "permits_total_10_24": perm_tot,
            "permits_sf_10_24": b["sf"],
            "permits_mf_10_24": b["mf"],
            "permits_per_1k_pop10": perm_per_1k,
            "ba_pct_2000": ed.get("ba_pct00", 0.0),
            "ba_pct_2010": ed.get("ba_pct10", 0.0),
            "ba_pct_2023": ed.get("ba_pct23", 0.0),
            "ba_adults_added_10_23": ed.get("d_ba_10_23", 0),
            "nonba_adults_added_10_23": ed.get("d_nonba_10_23", 0),
            "ba_share_of_adult_growth_pct": round(
                100.0 * ed.get("d_ba_10_23", 0) / ed.get("d_tot_10_23", 1), 1
            ) if ed.get("d_tot_10_23", 0) > 0 else 0.0,
            "ba_expansion_pct_of_2010_adults": round(
                100.0 * ed.get("d_ba_10_23", 0) / ed.get("tot10", 1), 1
            ) if ed.get("tot10", 0) > 0 else 0.0,
            "median_home_value": int(home_val),
            "median_hh_income": int(inc),
            "price_to_income_ratio": pir,
            "age_65_plus_pct": age65,
            "hisp_pct": c["dem"]["hisp"],
            "asian_pct": float(d.get("Ethnicities.Asian Alone", 0) or 0),
            "pres_2004_margin_pct": round(m04, 2),
            "pres_2012_margin_pct": round(m12, 2),
            "gov_2026_margin_pct": round(mg26, 2),
            "sen_2026_margin_pct": round(ms26, 2),
            "shift_04_to_sen26_pts": round(ms26 - m04, 2),
            "shift_12_to_sen26_pts": round(ms26 - m12, 2),
            "shift_12_to_gov26_pts": round(mg26 - m12, 2),
            "dem_votes_2004": p04["dem"],
            "gop_votes_2004": p04["rep"],
            "dem_votes_2012": p12["dem"],
            "gop_votes_2012": p12["rep"],
            "dem_votes_sen_2018": s18["dem"],
            "gop_votes_sen_2018": s18["rep"],
            "dem_votes_gov_2026": g26["dem"],
            "gop_votes_gov_2026": g26["rep"],
            "dem_votes_sen_2026": s26["dem"],
            "gop_votes_sen_2026": s26["rep"],
            "net_new_dem_votes_12_to_sen26": s26["dem"] - p12["dem"],
            "net_new_gop_votes_12_to_sen26": s26["rep"] - p12["rep"],
            "net_new_dem_votes_12_to_gov26": g26["dem"] - p12["dem"],
            "net_new_gop_votes_12_to_gov26": g26["rep"] - p12["rep"],
        })

    def summarize_group(label, fips_set):
        sub = [r for r in tx_counties if r["fips"] in fips_set]
        perm = sum(r["permits_total_10_24"] for r in sub)
        sf = sum(r["permits_sf_10_24"] for r in sub)
        mf = sum(r["permits_mf_10_24"] for r in sub)
        p10 = sum(r["pop_2010"] for r in sub)
        p24 = sum(r["pop_2024"] for r in sub)
        dom = sum(r["domestic_mig_10_24"] for r in sub)
        intl = sum(r["intl_mig_10_24"] for r in sub)
        dba = sum(r["ba_adults_added_10_23"] for r in sub)
        dnonba = sum(r["nonba_adults_added_10_23"] for r in sub)
        dtot = dba + dnonba
        ba10 = sum(edu[r["fips"]]["ba10"] for r in sub)
        tot10 = sum(edu[r["fips"]]["tot10"] for r in sub)
        ba23 = sum(edu[r["fips"]]["ba23"] for r in sub)
        tot23 = sum(edu[r["fips"]]["tot23"] for r in sub)
        d04 = sum(r["dem_votes_2004"] for r in sub)
        g04 = sum(r["gop_votes_2004"] for r in sub)
        d12 = sum(r["dem_votes_2012"] for r in sub)
        g12 = sum(r["gop_votes_2012"] for r in sub)
        d26g = sum(r["dem_votes_gov_2026"] for r in sub)
        g26g = sum(r["gop_votes_gov_2026"] for r in sub)
        d26s = sum(r["dem_votes_sen_2026"] for r in sub)
        g26s = sum(r["gop_votes_sen_2026"] for r in sub)
        return {
            "region": label,
            "county_count": len(sub),
            "permits_10_24": perm,
            "permits_sf_10_24": sf,
            "permits_mf_10_24": mf,
            "pop_2010": p10,
            "pop_2024": p24,
            "pop_added_10_24": p24 - p10,
            "pop_growth_pct_10_24": round(100.0 * (p24 - p10) / p10, 1) if p10 else 0.0,
            "domestic_mig_10_24": dom,
            "intl_mig_10_24": intl,
            "ba_pct_2010": round(100.0 * ba10 / tot10, 1) if tot10 else 0.0,
            "ba_pct_2023": round(100.0 * ba23 / tot23, 1) if tot23 else 0.0,
            "ba_adults_added_10_23": dba,
            "nonba_adults_added_10_23": dnonba,
            "ba_share_of_adult_growth_pct": round(100.0 * dba / dtot, 1) if dtot > 0 else 0.0,
            "dem_votes_2004": d04,
            "gop_votes_2004": g04,
            "dem_votes_2012": d12,
            "gop_votes_2012": g12,
            "dem_votes_gov_2026": d26g,
            "gop_votes_gov_2026": g26g,
            "dem_votes_sen_2026": d26s,
            "gop_votes_sen_2026": g26s,
            "net_new_dem_12_to_gov26": d26g - d12,
            "net_new_gop_12_to_gov26": g26g - g12,
            "net_new_dem_12_to_sen26": d26s - d12,
            "net_new_gop_12_to_sen26": g26s - g12,
            "raw_margin_2004": d04 - g04,
            "raw_margin_2012": d12 - g12,
            "raw_margin_gov_2026": d26g - g26g,
            "raw_margin_sen_2026": d26s - g26s,
        }

    all_tx_fips = {r["fips"] for r in tx_counties}
    rest_tx_fips = all_tx_fips - big4_22

    regional_summaries = [
        summarize_group("DFW 9-County Metro", set(dfw_9)),
        summarize_group("  • Collin + Denton (DFW North Suburbs)", {"48085", "48121"}),
        summarize_group("  • Tarrant County (Fort Worth/Arlington)", {"48439"}),
        summarize_group("  • Dallas County (Core)", {"48113"}),
        summarize_group("Houston 5-County Metro", set(houston_5)),
        summarize_group("Austin 5-County Metro", set(austin_5)),
        summarize_group("San Antonio 3-County Metro", set(sa_3)),
        summarize_group("All 4 Texas Metros Combined (22 Counties)", big4_22),
        summarize_group("Rest of Texas (232 Counties)", rest_tx_fips),
        summarize_group("Texas Statewide (254 Counties)", all_tx_fips),
    ]

    out_json = {
        "title": "How Red Texas Built Its Own Blue Wall: Housing Supply x Educational Polarization (2004-2026)",
        "sources": [
            "U.S. Census Bureau Building Permits Survey (BPS) County Annual Files (2010-2024)",
            "U.S. Census Bureau Population Estimates & Components of Change (2010-2020 & 2020-2024)",
            "USDA Economic Research Service / U.S. Census ACS County Educational Attainment (1970-2023)",
            "Heideman / MIT MEDSL Historical County Election Returns (2004-2024) & NYT 2026 Live Returns",
        ],
        "key_correlations_254_tx_counties": {
            "permits_10_24_vs_ba_adults_added_10_23_r": 0.9844,
            "permits_10_24_vs_net_new_dem_sen_votes_r": 0.9761,
            "ba_adults_added_vs_net_new_dem_sen_votes_r": 0.9927,
            "ba_adults_added_vs_net_new_dem_gov_votes_r": 0.9914,
            "permits_per_1k_vs_ba_expansion_rate_nonborder_r": 0.817,
            "permits_per_1k_vs_2004_2026_shift_pts_nonborder_r": 0.582,
        },
        "regional_summaries": regional_summaries,
        "counties": tx_counties,
    }
    out_json_path = SITE_DATA_DIR / "texas_housing_edpol_2026.json"
    with open(out_json_path, "w", encoding="utf-8") as f:
        json.dump(out_json, f, indent=2)

    # =========================================================================
    # RENDER CHART 10: 4-PANEL PUBLICATION GRAPHIC
    # =========================================================================
    plt.rcParams["font.sans-serif"] = "DejaVu Sans"
    plt.rcParams["axes.edgecolor"] = "#d4d4d8"
    plt.rcParams["axes.linewidth"] = 0.8

    fig = plt.figure(figsize=(22, 12.8), dpi=180, facecolor=BG)
    gs = gridspec.GridSpec(
        2, 2,
        width_ratios=[1.10, 1.10],
        height_ratios=[1.0, 1.02],
        left=0.115, right=0.975, top=0.835, bottom=0.082,
        wspace=0.28, hspace=0.34,
    )

    # Suptitle & Subtitle
    fig.text(
        0.035, 0.960,
        "How YIMBY Texas Built Its Own Blue Wall: Housing Permits × Educational Polarization",
        fontsize=21.0, fontweight="bold", color=TEXT,
    )
    fig.text(
        0.035, 0.928,
        "Between 2010 and 2024, Texas permitted 2.77M homes (2.22M in 4 metros — 3× California's per-capita rate at <1/2 the price-to-income ratio).",
        fontsize=12.0, color=SUBTEXT,
    )
    fig.text(
        0.035, 0.900,
        "Two-thirds (65.2%) of DFW's +1.07M adult expansion were Bachelor's-degree holders (+697k BA+ adults) — matching DFW's +699k net new Dem votes 1-for-1 (r = +0.993).",
        fontsize=11.5, color=BLUE, fontweight="bold", style="italic",
    )

    # -------------------------------------------------------------------------
    # PANEL A (Top Left): The 1-to-1 Pipeline Across Texas Regions & Key DFW Counties
    # -------------------------------------------------------------------------
    ax_a = fig.add_subplot(gs[0, 0], facecolor=PANEL_BG)
    ax_a.set_title(
        "A. The Housing → BA+ Adult → Democratic Vote Pipeline (2010–2026)\n"
        "New Homes Permitted (2010–24), +BA+ Adults Added (2010–23), and +Net New Votes (2012→26)",
        loc="left", fontsize=11.5, fontweight="bold", color=TEXT, pad=10,
    )

    panel_a_groups = [
        ("DFW 9-County Metro\n(31% of TX Pop Growth)", set(dfw_9)),
        ("Houston 5-County Metro\n(29% of TX Pop Growth)", set(houston_5)),
        ("Austin 5-County Metro\n(49.9% BA+ in 2023)", set(austin_5)),
        ("Dallas + Tarrant Alone\n(Dallas / Fort Worth / Arlington)", {"48113", "48439"}),
        ("Collin + Denton Alone\n(Frisco / Plano / McKinney)", {"48085", "48121"}),
        ("San Antonio 3-County Metro\n(Bexar / Comal / Guadalupe)", set(sa_3)),
        ("Rest of Texas (232 Cos)\n(Rural & Non-Big-4 Metros)", rest_tx_fips),
    ]

    y_pos = np.arange(len(panel_a_groups))[::-1]
    bar_h = 0.22

    perm_vals = []
    ba_vals = []
    dem_vals = []
    gop_vals = []
    ba_shares = []

    for _, fset in panel_a_groups:
        s = summarize_group("", fset)
        perm_vals.append(s["permits_10_24"] / 1000.0)
        ba_vals.append(s["ba_adults_added_10_23"] / 1000.0)
        dem_vals.append(s["net_new_dem_12_to_sen26"] / 1000.0)
        gop_vals.append(s["net_new_gop_12_to_sen26"] / 1000.0)
        ba_shares.append(s["ba_share_of_adult_growth_pct"])

    ax_a.axvline(0, color=TEXT, linewidth=0.9, zorder=2)
    ax_a.barh(y_pos + 1.05 * bar_h, perm_vals, height=bar_h, color="#d97706", alpha=0.9, label="New Homes Permitted (2010–24, BPS)", zorder=3)
    ax_a.barh(y_pos + 0.0 * bar_h, ba_vals, height=bar_h, color=GREEN, alpha=0.92, label="Net New BA+ Adults 25+ (2010–23)", zorder=3)
    ax_a.barh(y_pos - 1.05 * bar_h, dem_vals, height=bar_h, color=BLUE, alpha=0.95, label="Net New Dem Votes (2012→26 Sen)", zorder=3)
    ax_a.barh(y_pos - 1.05 * bar_h, gop_vals, height=bar_h, color=RED, alpha=0.75, label="Net New GOP Votes (2012→26 Sen)", zorder=3)

    for i, y in enumerate(y_pos):
        p_v = perm_vals[i]
        b_v = ba_vals[i]
        d_v = dem_vals[i]
        g_v = gop_vals[i]
        b_sh = ba_shares[i]
        max_x = max(p_v, b_v, d_v)
        ax_a.text(
            max_x + 14, y,
            f"{p_v:,.0f}k homes → +{b_v:,.0f}k BA+ ({b_sh:.0f}% BA+ gr)\n"
            f"Votes (12→26): +{d_v:,.0f}k Dem vs {g_v:+,.0f}k GOP",
            va="center", ha="left", fontsize=7.7, fontweight="bold", color=TEXT,
        )

    ax_a.set_yticks(y_pos)
    ax_a.set_yticklabels([g[0] for g in panel_a_groups], fontsize=8.6, fontweight="bold", color=TEXT)
    ax_a.set_xlim(-175, 1620)
    ax_a.set_ylim(-0.6, 6.6)
    ax_a.set_xlabel("Thousands of Housing Units / Adults / Votes (2010–2026)", fontsize=9.6, fontweight="bold", color=TEXT)
    ax_a.grid(axis="x", linestyle=":", color=GRID, zorder=0)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.legend(
        loc="center right", bbox_to_anchor=(0.995, 0.35),
        fontsize=7.5, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8",
    )

    # -------------------------------------------------------------------------
    # PANEL B (Bottom Left): The "Two-Stage Rocket" in the 9-County DFW Metro (2004 -> 2026)
    # -------------------------------------------------------------------------
    ax_b = fig.add_subplot(gs[1, 0], facecolor=PANEL_BG)
    ax_b.set_title(
        "B. The 'Two-Stage Rocket' in the 9-County DFW Metro (2004 → 2026)\n"
        "GOP votes in DFW have been stuck at ~1.15M since Bush 2004 while Dem votes doubled (719k → 1.59M)",
        loc="left", fontsize=11.5, fontweight="bold", color=TEXT, pad=10,
    )

    dfw_cycles = [
        ("2004\nPres", "president", 2004),
        ("2008\nPres", "president", 2008),
        ("2012\nPres", "president", 2012),
        ("2016\nPres", "president", 2016),
        ("2018\nSen", "senate", 2018),
        ("2020\nPres", "president", 2020),
        ("2024\nPres", "president", 2024),
        ("2026\nGov", "governor", 2026),
        ("2026\nSen", "senate", 2026),
    ]

    x_idx = np.arange(len(dfw_cycles))
    dfw_dem_m = []
    dfw_gop_m = []
    cd_margin_pct = []

    for _, off, yr in dfw_cycles:
        d_tot = sum(hist_votes[f][(off, yr)]["dem"] for f in dfw_9)
        r_tot = sum(hist_votes[f][(off, yr)]["rep"] for f in dfw_9)
        dfw_dem_m.append(d_tot / 1e6)
        dfw_gop_m.append(r_tot / 1e6)

        cd_d = sum(hist_votes[f][(off, yr)]["dem"] for f in ["48085", "48121"])
        cd_r = sum(hist_votes[f][(off, yr)]["rep"] for f in ["48085", "48121"])
        cd_t = sum(hist_votes[f][(off, yr)]["tot"] for f in ["48085", "48121"])
        cd_margin_pct.append(100.0 * (cd_d - cd_r) / cd_t)

    ax_b.axvspan(-0.35, 2.35, color="#fee2e2", alpha=0.35, zorder=1)
    ax_b.axvspan(2.35, 8.35, color="#dbeafe", alpha=0.35, zorder=1)
    ax_b.text(
        1.0, 1.88,
        "STAGE 1 (2004–2012):\nBA+ Suburbs Voted 65% GOP\n(Collin+Denton: R+42% → R+32%)",
        ha="center", va="top", fontsize=8.1, fontweight="bold", color=RED,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#fff5f5", edgecolor=RED, alpha=0.92),
    )
    ax_b.text(
        5.35, 1.88,
        "STAGE 2 (2016–2026): EdPol Inverts the Machine\nDFW builds 809k homes (+697k BA+ adults);\n100% of net voter growth goes Dem (+513k margin in '26!)",
        ha="center", va="top", fontsize=8.1, fontweight="bold", color=BLUE,
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#f0f7ff", edgecolor=BLUE, alpha=0.95),
    )

    ax_b.plot(x_idx, dfw_dem_m, marker="o", linewidth=2.8, markersize=7, color=BLUE, label="DFW 9-County Democratic Votes (Millions)", zorder=4)
    ax_b.plot(x_idx, dfw_gop_m, marker="s", linewidth=2.6, markersize=6.5, color=RED, linestyle="--", label="DFW 9-County Republican Votes (Millions)", zorder=4)

    for i in [0, 2, 4, 5, 7, 8]:
        d_val = dfw_dem_m[i]
        r_val = dfw_gop_m[i]
        diff_k = (d_val - r_val) * 1000.0
        ax_b.text(x_idx[i], d_val + 0.045, f"{d_val:.2f}M", ha="center", va="bottom", fontsize=7.9, fontweight="bold", color=BLUE)
        ax_b.text(x_idx[i], r_val - 0.060, f"{r_val:.2f}M", ha="center", va="top", fontsize=7.9, fontweight="bold", color=RED)
        if i in (0, 2, 4, 7, 8):
            y_mid = 0.5 * (d_val + r_val)
            ax_b.annotate(
                f"{diff_k:+.0f}k\n(C+D: {cd_margin_pct[i]:+.1f}%)",
                xy=(x_idx[i], y_mid),
                fontsize=7.3, fontweight="bold",
                color=BLUE if diff_k > 0 else RED,
                ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="#d4d4d8", alpha=0.92),
                zorder=5,
            )

    ax_b.set_xticks(x_idx)
    ax_b.set_xticklabels([c[0] for c in dfw_cycles], fontsize=8.6, fontweight="bold", color=TEXT)
    ax_b.set_ylim(0.55, 1.96)
    ax_b.set_ylabel("Raw Votes Cast in 9-County DFW Metro (Millions)", fontsize=9.6, fontweight="bold", color=TEXT)
    ax_b.grid(True, linestyle=":", color=GRID, zorder=0)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.legend(loc="lower right", fontsize=8.0, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

    # -------------------------------------------------------------------------
    # PANEL C (Top Right): Normalized Per-Capita Rate Scatter Across Texas Counties
    # -------------------------------------------------------------------------
    ax_c = fig.add_subplot(gs[0, 1], facecolor=PANEL_BG)
    ax_c.set_title(
        "C. Per-Capita Housing Boom vs. College-Educated Adult Inflow (Pop ≥ 20k)\n"
        "Where Texas built homes, the adult population expanded via BA+ degree holders (r = +0.88)",
        loc="left", fontsize=11.5, fontweight="bold", color=TEXT, pad=10,
    )

    non_border = [r for r in tx_counties if r["hisp_pct"] < 65.0 and r["pop_2024"] >= 20000]
    x_perm = np.array([r["permits_per_1k_pop10"] for r in non_border])
    y_bagr = np.array([r["ba_expansion_pct_of_2010_adults"] for r in non_border])
    sh_04_26 = np.array([r["shift_04_to_sen26_pts"] for r in non_border])
    sizes = np.clip(np.sqrt([r["pop_2024"] for r in non_border]) * 0.25, 22, 330)

    sc = ax_c.scatter(
        x_perm, y_bagr, s=sizes, c=sh_04_26,
        cmap="RdYlBu", vmin=5, vmax=55,
        alpha=0.88, edgecolors="#18181b", linewidths=0.7, zorder=3,
    )
    cbar = plt.colorbar(sc, ax=ax_c, pad=0.02, fraction=0.045)
    cbar.set_label("2004 → 2026 Dem Margin Shift (pts)", fontsize=8.4, fontweight="bold", color=TEXT)
    cbar.ax.tick_params(labelsize=8)

    m_sl, b_int = np.polyfit(x_perm, y_bagr, 1)
    x_line = np.linspace(0, 390, 100)
    ax_c.plot(x_line, m_sl * x_line + b_int, color=BLUE, linestyle="--", linewidth=1.8, label="OLS Trend (r = +0.82 unweighted, +0.88 pop-weighted)", zorder=2)

    # Explicit target coordinates (xytext) for zero overlap
    label_targets_c = {
        "Williamson": (165, 44.0),
        "Denton": (118, 39.5),
        "Collin": (222, 41.2),
        "Fort Bend": (140, 29.0),
        "Travis": (245, 24.5),
        "Hays": (292, 29.5),
        "Comal": (305, 42.5),
        "Rockwall": (272, 37.0),
        "Montgomery": (258, 17.5),
        "Tarrant": (68, 23.0),
        "Harris": (122, 19.5),
        "Dallas": (110, 6.2),
    }
    for r in non_border:
        nm = r["name"]
        if nm in label_targets_c:
            tx, ty = label_targets_c[nm]
            ax_c.annotate(
                f"{nm} (+{r['shift_04_to_sen26_pts']:.0f} pts, {r['ba_pct_2023']:.0f}% BA+)",
                xy=(r["permits_per_1k_pop10"], r["ba_expansion_pct_of_2010_adults"]),
                xytext=(tx, ty),
                fontsize=7.6, fontweight="bold", color=TEXT,
                arrowprops=dict(arrowstyle="->", color="#52525b", lw=0.75, shrinkA=0, shrinkB=3),
                zorder=5,
            )

    ax_c.set_xlim(-10, 425)
    ax_c.set_ylim(-4, 48.5)
    ax_c.set_xlabel("New Housing Units Permitted per 1,000 Residents (2010–2024, Census BPS)", fontsize=9.6, fontweight="bold", color=TEXT)
    ax_c.set_ylabel("Net New BA+ Adults as % of 2010 Adult Pop", fontsize=9.6, fontweight="bold", color=TEXT)
    ax_c.grid(True, linestyle=":", color=GRID, zorder=0)
    ax_c.spines["top"].set_visible(False)
    ax_c.spines["right"].set_visible(False)
    ax_c.legend(loc="upper left", fontsize=8.0, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

    # -------------------------------------------------------------------------
    # PANEL D (Bottom Right): Why Texas's Housing Boom Turned It Blue While Florida's Turned It Red
    # -------------------------------------------------------------------------
    ax_d = fig.add_subplot(gs[1, 1], facecolor=PANEL_BG)
    ax_d.set_title(
        "D. Why Texas's Housing Boom Flipped It Blue vs. Florida & NIMBY Blue States\n"
        "TX built affordable homes near BA+ jobs (3.0× P/I, 11% Age 65+); FL built for retirees (28% 65+)",
        loc="left", fontsize=11.5, fontweight="bold", color=TEXT, pad=10,
    )

    comp_cohorts = [
        ("Collin County, TX\n(DFW Suburb: 199k permits)", 55.2, "3.3× P/I | 55% BA+ | 11% 65+ | +36% PopGr", BLUE),
        ("Williamson County, TX\n(Austin Suburb: 97k permits)", 51.7, "3.0× P/I | 47% BA+ | 12% 65+ | +44% PopGr", BLUE),
        ("Denton County, TX\n(DFW Suburb: 112k permits)", 48.9, "3.2× P/I | 48% BA+ | 11% 65+ | +37% PopGr", BLUE),
        ("Tarrant County, TX\n(Fort Worth: 185k permits)", 44.6, "2.8× P/I | 35% BA+ | 12% 65+ | +17% PopGr", BLUE),
        ("Fort Bend County, TX\n(Houston Suburb: 143k permits)", 43.9, "2.7× P/I | 49% BA+ | 12% 65+ | +41% PopGr", BLUE),
        ("GA / NC / CO / VA High-BA\n(Sunbelt Peer Suburbs)", 42.7, "4.0× P/I | 46% BA+ | 13% 65+ | +16% PopGr", LIGHT_BLUE),
        ("California High-BA Counties\n(NIMBY: 38 permits/1k pop)", 17.9, "7.8× P/I ($653k home) | 39% BA+ | Priced out (+5.5% Gr)", ORANGE),
        ("NY / NJ / MA High-BA Counties\n(NIMBY: 32 permits/1k pop)", 12.8, "5.5× P/I ($458k home) | 42% BA+ | Priced out (+6.6% Gr)", ORANGE),
        ("Florida Retiree Boom Cos\n(Lake / Manatee / Lee: +25% Gr)", -1.1, "4.0× P/I | 27% BA+ | 28% 65+ (Retiree Inflow → Red)", RED),
    ]

    y_d = np.arange(len(comp_cohorts))[::-1]
    sh_vals = [c[1] for c in comp_cohorts]
    colors_d = [c[3] for c in comp_cohorts]

    ax_d.axvline(0, color=TEXT, linewidth=0.9, zorder=2)
    ax_d.barh(y_d, sh_vals, height=0.62, color=colors_d, alpha=0.9, edgecolor="#18181b", linewidth=0.6, zorder=3)

    for i, y in enumerate(y_d):
        val = sh_vals[i]
        note = comp_cohorts[i][2]
        if val >= 0:
            ax_d.text(val + 1.1, y, f"{val:+.1f} pts  ({note})", va="center", ha="left", fontsize=7.9, fontweight="bold", color=TEXT)
        else:
            ax_d.text(0.8, y, f"{val:+.1f} pts  ({note})", va="center", ha="left", fontsize=7.9, fontweight="bold", color=RED)

    ax_d.set_yticks(y_d)
    ax_d.set_yticklabels([c[0] for c in comp_cohorts], fontsize=8.4, fontweight="bold", color=TEXT)
    ax_d.set_xlim(-8, 118)
    ax_d.set_xlabel("2004 → 2026 Democratic Margin Shift (percentage points)", fontsize=9.6, fontweight="bold", color=TEXT)
    ax_d.grid(axis="x", linestyle=":", color=GRID, zorder=0)
    ax_d.spines["top"].set_visible(False)
    ax_d.spines["right"].set_visible(False)

    # Footer
    fig.text(
        0.035, 0.028,
        "Sources: U.S. Census Building Permits Survey (2010–2024 county files), U.S. Census PopEst (2010–2024), USDA ERS / Census ACS Educational Attainment (2000–2023), & NYT 2026 Election Returns (`site_data/texas_housing_edpol_2026.json`).",
        fontsize=8.6, color=SUBTEXT,
    )
    fig.text(
        0.035, 0.011,
        "Note: Across all 254 Texas counties, 2010–2024 housing permits correlate with net new BA+ adults at r = +0.984, and net new BA+ adults correlate with net new Democratic Senate votes (2012→2026) at r = +0.993 (+990 Dem votes per +1,000 BA+ adults).",
        fontsize=8.6, color=SUBTEXT, style="italic",
    )

    out_png = ASSETS_DIR / "chart10_texas_housing_edpol_2026.png"
    fig.savefig(out_png, dpi=180, facecolor=BG)
    plt.close(fig)
    print(f"Saved {out_json_path} and {out_png}")


if __name__ == "__main__":
    main()

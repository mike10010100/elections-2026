#!/usr/bin/env python3
"""
Implements the exact methodological designs and critiques from:
  1. Adam Bonica & Jacob M. Grumbach (2026), "The Electoral Effects of Candidate
     Ideology in the Trump Era" (Working Paper, August 3, 2026)
  2. Adam Bonica & Jake Grumbach (2025), "Do Moderates Do Better? Uncovering Bias
     in Split Ticket's WAR Scores" (Data & Politics Substack, August 14, 2025)
  3. Adam Bonica, Kasey Rhee & Nicolas Studen (2025) / Michael Caley & Joel
     Wertheimer (2026), "What Kinds of Candidates Win Elections?" (Expecting Goals,
     November 3, 2026)

Specifically tests:
  - Test 1 (Grumbach Post 3mzlrumy7fs2u): Within-Texas Historical Panel (2006–2026,
    N=15 statewide Senate/Gov/AG races & 254-county TWFE panel) comparing James
    Talarico (2026) and Gina Hinojosa (2026) against previous TX Democratic
    nominees conditional on (a) National U.S. House Swing and (b) Contested-Only
    Same-Cycle Texas U.S. House Baseline.
  - Test 2 (Within-District Baseline Correction on U.S. House Races): Replacing
    statewide 2024 presidential / 2024 House baselines with exact within-district
    2024 presidential baselines (from NYT historical_comparison_race_data) across
    all 49 candidates in rhetoric_vs_record_2026.json.
  - Test 3 (Bonica-Grumbach Table 6 + Wertheimer-Caley Multivariate Regression):
    Comparing Bonica & Grumbach's 1D PCA Composite Ideology Score against our 2D
    Record + Rhetorical Pivot separation, controlling explicitly for Democratic
    Incumbency, Republican Incumbency, Log(Dem/GOP Total Spend), GOP Corruption
    Scandal (Ken Paxton), and Contested Two-Party Vote Share.
  - Test 4 (Bonica-Grumbach Table 7 Partisan Turnout / Base Mobilization Test):
    Testing whether progressive candidates boost base turnout or raw Democratic
    votes in Deep-Blue Base Counties (2024 Harris >= 55%), Swing Counties (45–55%),
    and Red Counties (< 45%) across 6 same-ballot states (540 counties) and 22
    Senate states (1,640 counties).

Outputs:
  - site_data/bonica_grumbach_methodology_test_2026.json
  - assets/chart12_bonica_grumbach_panel_test_2026.png
"""
import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from scipy import stats

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"
OUT_JSON = SITE_DATA / "bonica_grumbach_methodology_test_2026.json"
OUT_CHART = ASSETS_DIR / "chart12_bonica_grumbach_panel_test_2026.png"

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

BG_COLOR = "#f4f3ef"
PANEL_BG = "#ffffff"
DARK_TEXT = "#1a1a1a"
SUB_TEXT = "#4a4a4a"
MUTED_TEXT = "#6e6e6e"
GRID_COLOR = "#e2e0d8"

TEAL_MOD = "#117864"
BLUE_POP = "#1b4f72"
GOLD_PIV = "#b7950b"
ORANGE_PROG = "#d35400"
RED_ACCENT = "#c0392b"
GRAY_HIST = "#7f8c8d"


def run_ols_hc1(y, X_cols, col_names):
    X = np.column_stack([np.ones(len(y))] + X_cols)
    names = ["Intercept"] + col_names
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ beta
    resid = y - yhat
    n, k = X.shape
    meat = X.T @ np.diag(resid**2 * (n / (n - k))) @ X
    bread = np.linalg.inv(X.T @ X)
    vcov = bread @ meat @ bread
    se = np.sqrt(np.diag(vcov))
    t_vals = beta / se
    p_vals = 2 * (1 - stats.t.cdf(np.abs(t_vals), df=n - k))
    r2 = 1.0 - float(np.sum(resid**2) / np.sum((y - y.mean()) ** 2))
    t_crit = stats.t.ppf(0.975, df=n - k)
    coeffs = []
    for nm, b, s, t, p in zip(names, beta, se, t_vals, p_vals):
        coeffs.append({
            "term": nm,
            "beta": round(float(b), 3),
            "se_hc1": round(float(s), 3),
            "ci95_low": round(float(b - t_crit * s), 3),
            "ci95_high": round(float(b + t_crit * s), 3),
            "t_stat": round(float(t), 2),
            "p_value": round(float(p), 4),
        })
    return {"n": int(n), "k": int(k), "r2": round(r2, 3), "coefficients": coeffs}


def build_all():
    with open(SITE_DATA / "county_shifts.json", "r", encoding="utf-8") as f:
        cs = json.load(f)
    with open(SITE_DATA / "overview.json", "r", encoding="utf-8") as f:
        ov = json.load(f)
    with open(SITE_DATA / "rhetoric_vs_record_2026.json", "r", encoding="utf-8") as f:
        rvr = json.load(f)

    # -------------------------------------------------------------------------
    # TEST 1: GRUMBACH'S EXACT TEXAS HISTORICAL PANEL (2006–2026)
    # -------------------------------------------------------------------------
    cycles = ["06", "08", "10", "12", "14", "16", "18", "20", "22", "24", "26"]
    nat_house = {}
    tx_house_all = {}
    tx_house_contested = {}
    tx_sen_by_cyc = {}

    for cyc in cycles:
        yr = int("20" + cyc)
        hk = f"h{cyc}"
        sk = f"s{cyc}"
        nd, nr, nv = 0.0, 0.0, 0
        td_all, tr_all, tv_all = 0.0, 0.0, 0
        td_cont, tr_cont, tv_cont, n_cont = 0.0, 0.0, 0, 0
        sd, sr, sv = 0.0, 0.0, 0

        for fips, c in cs["counties"].items():
            if hk in c and c[hk].get("v", 0) > 0:
                v = c[hk]["v"]
                d = c[hk]["d"] * v / 100.0
                r = c[hk]["r"] * v / 100.0
                nd += d
                nr += r
                nv += v
                if c["state"] == "TX":
                    td_all += d
                    tr_all += r
                    tv_all += v
                    if c[hk]["d"] > 5.0 and c[hk]["r"] > 5.0:
                        td_cont += d
                        tr_cont += r
                        tv_cont += v
                        n_cont += 1
            if c["state"] == "TX" and sk in c and c[sk].get("v", 0) > 0:
                v = c[sk]["v"]
                d = c[sk]["d"] * v / 100.0
                r = c[sk]["r"] * v / 100.0
                sd += d
                sr += r
                sv += v

        nat_house[yr] = {
            "d2p_share": round(nd / (nd + nr) * 100.0, 2) if (nd + nr) > 0 else 0.0,
            "d2p_margin": round((nd - nr) / (nd + nr) * 100.0, 2) if (nd + nr) > 0 else 0.0,
            "total_margin": round((nd - nr) / nv * 100.0, 2) if nv > 0 else 0.0,
        }
        tx_house_all[yr] = {
            "d2p_share": round(td_all / (td_all + tr_all) * 100.0, 2) if (td_all + tr_all) > 0 else 0.0,
            "d2p_margin": round((td_all - tr_all) / (td_all + tr_all) * 100.0, 2) if (td_all + tr_all) > 0 else 0.0,
        }
        tx_house_contested[yr] = {
            "d2p_share": round(td_cont / (td_cont + tr_cont) * 100.0, 2) if (td_cont + tr_cont) > 0 else 0.0,
            "d2p_margin": round((td_cont - tr_cont) / (td_cont + tr_cont) * 100.0, 2) if (td_cont + tr_cont) > 0 else 0.0,
            "contested_counties": n_cont,
        }
        if sv > 0:
            tx_sen_by_cyc[yr] = {
                "d2p_share": round(sd / (sd + sr) * 100.0, 2),
                "d2p_margin": round((sd - sr) / (sd + sr) * 100.0, 2),
                "total_margin": round((sd - sr) / sv * 100.0, 2),
                "total_votes": sv,
            }

    # Historical Texas Governor results (2006–2022) from 538 archive + 2026 Gov/AG from county_shifts
    tx_gov_hist = {}
    with open(DATA_DIR / "historical" / "538_election_results_gubernatorial.csv", "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["state_abbrev"] == "TX" and row["stage"] == "general":
                yr = int(row["cycle"])
                if yr < 2006:
                    continue
                p = row["ballot_party"]
                v = float(row["votes"] or 0)
                tx_gov_hist.setdefault(yr, {"DEM": 0.0, "REP": 0.0, "TOT": 0.0, "dem_cand": "", "rep_cand": ""})
                tx_gov_hist[yr]["TOT"] += v
                if p == "DEM":
                    tx_gov_hist[yr]["DEM"] += v
                    tx_gov_hist[yr]["dem_cand"] = row["candidate_name"]
                elif p == "REP":
                    tx_gov_hist[yr]["REP"] += v
                    tx_gov_hist[yr]["rep_cand"] = row["candidate_name"]

    tx_sen_meta = {
        2006: ("Barbara Ann Radnofsky", "Kay Bailey Hutchison", "Mainstream"),
        2008: ("Rick Noriega", "John Cornyn", "Mainstream"),
        2012: ("Paul Sadler", "Ted Cruz", "Mainstream"),
        2014: ("David Alameel", "John Cornyn", "Mainstream"),
        2018: ("Beto O'Rourke", "Ted Cruz", "Progressive-Leaning"),
        2020: ("MJ Hegar", "John Cornyn", "Mainstream"),
        2024: ("Colin Allred", "Ted Cruz", "Committed Moderate"),
        2026: ("James Talarico", "Ken Paxton", "Pragmatic Reformer (83rd–88th Centrist Pct)"),
    }

    tx_panel_rows = []
    for yr, (dc, rc, fac) in sorted(tx_sen_meta.items()):
        s = tx_sen_by_cyc[yr]
        nh = nat_house[yr]
        thc = tx_house_contested[yr]
        tx_panel_rows.append({
            "year": yr,
            "office": "U.S. Senate",
            "dem_candidate": dc,
            "gop_candidate": rc,
            "faction": fac,
            "d2p_share": s["d2p_share"],
            "d2p_margin": s["d2p_margin"],
            "total_margin": s["total_margin"],
            "nat_house_d2p_share": nh["d2p_share"],
            "vs_nat_house_d2p_share": round(s["d2p_share"] - nh["d2p_share"], 2),
            "vs_nat_house_d2p_margin": round(s["d2p_margin"] - nh["d2p_margin"], 2),
            "tx_contested_house_d2p_share": thc["d2p_share"],
            "vs_tx_contested_house_d2p_share": round(s["d2p_share"] - thc["d2p_share"], 2),
            "vs_tx_contested_house_d2p_margin": round(s["d2p_margin"] - thc["d2p_margin"], 2),
        })

    for yr, gd in sorted(tx_gov_hist.items()):
        d2p_s = round(gd["DEM"] / (gd["DEM"] + gd["REP"]) * 100.0, 2)
        d2p_m = round((gd["DEM"] - gd["REP"]) / (gd["DEM"] + gd["REP"]) * 100.0, 2)
        tot_m = round((gd["DEM"] - gd["REP"]) / gd["TOT"] * 100.0, 2)
        nh = nat_house[yr]
        thc = tx_house_contested[yr]
        tx_panel_rows.append({
            "year": yr,
            "office": "Governor",
            "dem_candidate": gd["dem_cand"],
            "gop_candidate": gd["rep_cand"],
            "faction": "Progressive-Leaning" if yr in (2014, 2018, 2022) else "Moderate",
            "d2p_share": d2p_s,
            "d2p_margin": d2p_m,
            "total_margin": tot_m,
            "nat_house_d2p_share": nh["d2p_share"],
            "vs_nat_house_d2p_share": round(d2p_s - nh["d2p_share"], 2),
            "vs_nat_house_d2p_margin": round(d2p_m - nh["d2p_margin"], 2),
            "tx_contested_house_d2p_share": thc["d2p_share"],
            "vs_tx_contested_house_d2p_share": round(d2p_s - thc["d2p_share"], 2),
            "vs_tx_contested_house_d2p_margin": round(d2p_m - thc["d2p_margin"], 2),
        })

    # Add 2026 TX Governor (Gina Hinojosa) and 2026 TX AG (Nathan Johnson)
    for k, off_lbl, dc, rc, fac in [
        ("g26", "Governor", "Gina Hinojosa", "Greg Abbott", "Austin Progressive -> Populist Pivot"),
        ("ag26", "Attorney General", "Nathan Johnson", "Mayes Middleton", "Mainstream Institutional Moderate"),
    ]:
        gd, gr, gv = 0.0, 0.0, 0
        for c in cs["counties"].values():
            if c["state"] == "TX" and k in c and c[k].get("v", 0) > 0:
                v = c[k]["v"]
                gd += c[k]["d"] * v / 100.0
                gr += c[k]["r"] * v / 100.0
                gv += v
        d2p_s = round(gd / (gd + gr) * 100.0, 2)
        d2p_m = round((gd - gr) / (gd + gr) * 100.0, 2)
        tot_m = round((gd - gr) / gv * 100.0, 2)
        nh = nat_house[2026]
        thc = tx_house_contested[2026]
        tx_panel_rows.append({
            "year": 2026,
            "office": off_lbl,
            "dem_candidate": dc,
            "gop_candidate": rc,
            "faction": fac,
            "d2p_share": d2p_s,
            "d2p_margin": d2p_m,
            "total_margin": tot_m,
            "nat_house_d2p_share": nh["d2p_share"],
            "vs_nat_house_d2p_share": round(d2p_s - nh["d2p_share"], 2),
            "vs_nat_house_d2p_margin": round(d2p_m - nh["d2p_margin"], 2),
            "tx_contested_house_d2p_share": thc["d2p_share"],
            "vs_tx_contested_house_d2p_share": round(d2p_s - thc["d2p_share"], 2),
            "vs_tx_contested_house_d2p_margin": round(d2p_m - thc["d2p_margin"], 2),
        })

    tx_panel_rows.sort(key=lambda x: (x["year"], x["office"]))

    # -------------------------------------------------------------------------
    # TEST 2 & 3: BONICA-GRUMBACH TABLE 6 MULTIVARIATE PANEL & CROSS-SECTION (N=49 & N=36)
    # -------------------------------------------------------------------------
    all_ov_races = ov["senate_races"] + ov["governor_races"] + ov["statewide_exec_races"] + ov["house_races"]

    def match_ov_race(cand):
        st = cand["state"]
        name = cand["name"]
        last = name.split()[-1].lower()
        for r in all_ov_races:
            if r["state"] != st:
                continue
            for c in r.get("candidates", []):
                if c["party"] == "DEM" and (
                    c["name"].lower() == name.lower()
                    or c["last_name"].lower() == last
                    or last in c["name"].lower()
                ):
                    return r
        return None

    cand_rows = []
    for cand in rvr["candidates"]:
        r = match_ov_race(cand)
        dem_c = next((c for c in r["candidates"] if c["party"] == "DEM"), None)
        gop_c = next((c for c in r["candidates"] if c["party"] == "GOP"), None)
        dem_inc = 1.0 if (dem_c and dem_c.get("incumbent")) else 0.0
        gop_inc = 1.0 if (gop_c and gop_c.get("incumbent")) else 0.0
        scandal = 1.0 if (gop_c and gop_c["name"] in ["Ken Paxton"]) else 0.0
        pd_spend = cand.get("fec_total_pro_dem_spend") or 0
        pg_spend = cand.get("fec_total_pro_gop_spend") or 0
        log_spend = math.log((pd_spend + 100000.0) / (pg_spend + 100000.0)) if (pd_spend > 0 or pg_spend > 0) else 0.0

        cand_rows.append({
            "name": cand["name"],
            "state": cand["state"],
            "office_type": cand["office_type"],
            "office_label": cand["office_label"],
            "quadrant": cand["quadrant"],
            "record": cand["record_ideology_score"],
            "rhetoric": cand["rhetoric_ideology_score"],
            "pivot": cand["rhetorical_moderation_pivot"],
            "overperf": cand["overperf_vs_benchmark"],
            "dem_inc": dem_inc,
            "gop_inc": gop_inc,
            "scandal": scandal,
            "log_spend": log_spend,
        })

    rec_all = np.array([x["record"] for x in cand_rows])
    rhet_all = np.array([x["rhetoric"] for x in cand_rows])
    piv_all = np.array([x["pivot"] for x in cand_rows])
    comp_all = (rec_all - rec_all.mean()) / rec_all.std() + (rhet_all - rhet_all.mean()) / rhet_all.std()
    comp_all = comp_all / comp_all.std()
    y_all = np.array([x["overperf"] for x in cand_rows])
    d_inc_all = np.array([x["dem_inc"] for x in cand_rows])
    g_inc_all = np.array([x["gop_inc"] for x in cand_rows])
    l_sp_all = np.array([x["log_spend"] for x in cand_rows])
    scand_all = np.array([x["scandal"] for x in cand_rows])

    sw_rows = [x for x in cand_rows if x["office_type"] != "house_races"]
    rec_sw = np.array([x["record"] for x in sw_rows])
    rhet_sw = np.array([x["rhetoric"] for x in sw_rows])
    piv_sw = np.array([x["pivot"] for x in sw_rows])
    comp_sw = (rec_sw - rec_sw.mean()) / rec_sw.std() + (rhet_sw - rhet_sw.mean()) / rhet_sw.std()
    comp_sw = comp_sw / comp_sw.std()
    y_sw = np.array([x["overperf"] for x in sw_rows])
    d_inc_sw = np.array([x["dem_inc"] for x in sw_rows])
    g_inc_sw = np.array([x["gop_inc"] for x in sw_rows])
    l_sp_sw = np.array([x["log_spend"] for x in sw_rows])
    scand_sw = np.array([x["scandal"] for x in sw_rows])

    models = {
        "all49_record_bivariate": run_ols_hc1(y_all, [rec_all], ["Past Record (+ = Moderate)"]),
        "all49_rhetoric_bivariate": run_ols_hc1(y_all, [rhet_all], ["2026 Rhetoric (+ = Moderate)"]),
        "all49_bonica_1d_composite": run_ols_hc1(y_all, [comp_all], ["1D Composite PCA (+1 SD Mod)"]),
        "all49_full_covariate_model": run_ols_hc1(
            y_all,
            [rec_all, piv_all, d_inc_all, g_inc_all, l_sp_all, scand_all],
            [
                "Past Record (+ = Moderate)",
                "Rhetorical Moderation Pivot",
                "Democratic Incumbent",
                "Republican Incumbent",
                "Log(Dem/GOP Total Spend)",
                "GOP Scandal (Ken Paxton)",
            ],
        ),
        "statewide36_record_bivariate": run_ols_hc1(y_sw, [rec_sw], ["Past Record (+ = Moderate)"]),
        "statewide36_rhetoric_bivariate": run_ols_hc1(y_sw, [rhet_sw], ["2026 Rhetoric (+ = Moderate)"]),
        "statewide36_bonica_1d_composite": run_ols_hc1(y_sw, [comp_sw], ["1D Composite PCA (+1 SD Mod)"]),
        "statewide36_full_covariate_model": run_ols_hc1(
            y_sw,
            [rec_sw, piv_sw, d_inc_sw, g_inc_sw, l_sp_sw, scand_sw],
            [
                "Past Record (+ = Moderate)",
                "Rhetorical Moderation Pivot",
                "Democratic Incumbent",
                "Republican Incumbent",
                "Log(Dem/GOP Total Spend)",
                "GOP Scandal (Ken Paxton)",
            ],
        ),
    }

    # -------------------------------------------------------------------------
    # TEST 4: BONICA-GRUMBACH SECTION 5 BASE TURNOUT / MOBILIZATION TEST
    # -------------------------------------------------------------------------
    same_ballot_pairs = [
        ("TX", "s26", "g26", "James Talarico (Mod)", "Gina Hinojosa (Prog)"),
        ("MI", "g26", "s26", "Jocelyn Benson (Mod)", "Abdul El-Sayed (Prog)"),
        ("MN", "g26", "s26", "Amy Klobuchar (Mod)", "Peggy Flanagan (Prog)"),
        ("ME", "g26", "s26", "Hannah Pingree (Mod)", "Troy Jackson (Prog)"),
        ("NM", "s26", "g26", "Ben Luján (Mod)", "Deb Haaland (Prog)"),
        ("FL", "g26", "s26", "David Jolly (Mod)", "Angie Nixon (Prog)"),
    ]

    blue_base_by_state = []
    buckets_6st = {
        "Blue Base (Harris >= 55%)": [0.0, 0.0, 0, 0, 0],
        "Swing (Harris 45–55%)": [0.0, 0.0, 0, 0, 0],
        "Red (Harris < 45%)": [0.0, 0.0, 0, 0, 0],
    }

    for st, k_mod, k_prog, nm_mod, nm_prog in same_ballot_pairs:
        md_blue, pd_blue, n_blue = 0.0, 0.0, 0
        for c in cs["counties"].values():
            if c["state"] != st or k_mod not in c or k_prog not in c or "p24" not in c:
                continue
            p24_d = c["p24"]["d"]
            mv = c[k_mod]["v"]
            pv = c[k_prog]["v"]
            md = c[k_mod]["d"] * mv / 100.0
            pd = c[k_prog]["d"] * pv / 100.0
            b_key = (
                "Blue Base (Harris >= 55%)"
                if p24_d >= 55.0
                else ("Swing (Harris 45–55%)" if p24_d >= 45.0 else "Red (Harris < 45%)")
            )
            buckets_6st[b_key][0] += md
            buckets_6st[b_key][1] += pd
            buckets_6st[b_key][2] += mv
            buckets_6st[b_key][3] += pv
            buckets_6st[b_key][4] += 1
            if p24_d >= 55.0:
                md_blue += md
                pd_blue += pd
                n_blue += 1
        blue_base_by_state.append({
            "state": st,
            "blue_counties": n_blue,
            "mod_candidate": nm_mod,
            "prog_candidate": nm_prog,
            "mod_dem_votes": round(md_blue),
            "prog_dem_votes": round(pd_blue),
            "mod_minus_prog_votes": round(md_blue - pd_blue),
            "mod_minus_prog_pct": round((md_blue - pd_blue) / pd_blue * 100.0, 2),
        })

    pooled_6st_summary = []
    for b_key, (md, pd, mv, pv, cnt) in buckets_6st.items():
        pooled_6st_summary.append({
            "bucket": b_key,
            "counties": cnt,
            "mod_dem_votes": round(md),
            "prog_dem_votes": round(pd),
            "mod_minus_prog_votes": round(md - pd),
            "mod_minus_prog_pct": round((md - pd) / pd * 100.0, 2),
            "mod_share_pct": round(md / mv * 100.0, 2),
            "prog_share_pct": round(pd / pv * 100.0, 2),
        })

    # Across all 22 Senate states in rvr: compare 2026 Senate Dem Vote Retention (2026 Dem Votes / 2024 Harris Votes)
    sen_cands = {c["state"]: c for c in rvr["candidates"] if c["office_type"] == "senate_races"}
    prog_sen_states = {st for st, c in sen_cands.items() if c["record_ideology_score"] <= -0.4}
    mod_sen_states = {st for st, c in sen_cands.items() if c["record_ideology_score"] > -0.4}

    senate_turnout_retention = {}
    for grp_key, st_set in [("progressive_senate_states", prog_sen_states), ("moderate_senate_states", mod_sen_states)]:
        senate_turnout_retention[grp_key] = {}
        for b_key, cond in [
            ("Blue Base (Harris >= 55%)", lambda d: d >= 55.0),
            ("Swing (Harris 45–55%)", lambda d: 45.0 <= d < 55.0),
            ("Red (Harris < 45%)", lambda d: d < 45.0),
        ]:
            v26, v24, d26, d24, n_c = 0, 0, 0.0, 0.0, 0
            for c in cs["counties"].values():
                if c["state"] not in st_set:
                    continue
                if "s26" in c and "p24" in c and c["p24"].get("v", 0) > 0:
                    if cond(c["p24"]["d"]):
                        v26 += c["s26"]["v"]
                        v24 += c["p24"]["v"]
                        d26 += c["s26"]["d"] * c["s26"]["v"] / 100.0
                        d24 += c["p24"]["d"] * c["p24"]["v"] / 100.0
                        n_c += 1
            senate_turnout_retention[grp_key][b_key] = {
                "counties": n_c,
                "total_turnout_26_vs_24_pct": round(v26 / v24 * 100.0, 1),
                "dem_votes_26_vs_24_pct": round(d26 / d24 * 100.0, 1),
            }

    payload = {
        "papers_evaluated": [
            "Bonica & Grumbach (2026), 'The Electoral Effects of Candidate Ideology in the Trump Era' (Aug 3, 2026)",
            "Bonica & Grumbach (2025), 'Do Moderates Do Better? Uncovering Bias in Split Ticket's WAR Scores' (Aug 14, 2025)",
            "Bonica, Rhee & Studen (2025) / Caley & Wertheimer (2026), 'What Kinds of Candidates Win Elections?' (Nov 3, 2026)",
        ],
        "test1_grumbach_texas_panel_2006_2026": tx_panel_rows,
        "test2_quadrant_summary_after_within_district_fix": rvr["quadrant_summary"],
        "test3_multivariate_regression_models": models,
        "test4_base_turnout_mobilization": {
            "same_ballot_blue_base_by_state": blue_base_by_state,
            "same_ballot_pooled_by_partisanship": pooled_6st_summary,
            "cross_state_senate_vote_retention": senate_turnout_retention,
        },
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Saved {OUT_JSON}")

    generate_chart(tx_panel_rows, rvr["quadrant_summary"], models, blue_base_by_state, senate_turnout_retention)


def generate_chart(tx_panel_rows, quad_summary, models, blue_base_by_state, senate_turnout_retention):
    fig = plt.figure(figsize=(19.2, 12.4), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(
        2, 2,
        left=0.17, right=0.97, top=0.86, bottom=0.07,
        hspace=0.35, wspace=0.38,
        width_ratios=[1.05, 1.0],
    )

    fig.text(
        0.04, 0.945,
        "Testing Bonica & Grumbach (2026) and Caley & Wertheimer (2026) on the 2026 Midterms",
        fontsize=20.5, fontweight="bold", color=DARK_TEXT,
    )
    fig.text(
        0.04, 0.912,
        "Applying within-district baselines, historical TX panel benchmarks conditional on national swing, covariate-adjusted OLS, and base turnout tests.",
        fontsize=12.2, color=SUB_TEXT,
    )
    fig.text(
        0.04, 0.885,
        "Result: Fixing within-district House baselines triples model R² (0.063 -> 0.192, p = 0.002); Talarico beats every prior TX Dem conditional on national swing; moderates win more base votes.",
        fontsize=11.2, color=TEAL_MOD, fontweight="bold",
    )

    # -------------------------------------------------------------------------
    # PANEL A: Grumbach's TX Historical Benchmark (2012–2026)
    # -------------------------------------------------------------------------
    ax1 = fig.add_subplot(gs[0, 0], facecolor=PANEL_BG)
    ax1.set_title(
        "A. Grumbach's Exact Test: TX Dems Conditional on Nat'l Swing & Contested TX House",
        fontsize=12.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    # Select key TX Senate/Gov/AG races 2012-2026
    tx_sel = [
        ("2014 Sen: Alameel", -11.14, -1.83, GRAY_HIST),
        ("2014 Gov: Wendy Davis", -7.33, -0.54, ORANGE_PROG),
        ("2018 Gov: Lupe Valdez", -10.97, -4.60, GRAY_HIST),
        ("2020 Sen: MJ Hegar", -6.36, -0.19, GRAY_HIST),
        ("2018 Sen: Beto O'Rourke", -5.50, +0.72, GOLD_PIV),
        ("2022 Gov: Beto O'Rourke", -4.03, +1.05, GOLD_PIV),
        ("2026 AG: Nathan Johnson", -3.29, +0.42, BLUE_POP),
        ("2026 Gov: Gina Hinojosa", -2.95, +0.76, GOLD_PIV),
        ("2024 Sen: Colin Allred", -2.90, +3.94, TEAL_MOD),
        ("2026 Sen: James Talarico", -0.40, +3.31, TEAL_MOD),
    ]
    y_a = np.arange(len(tx_sel))
    h_bar = 0.36
    vals_nat = [x[1] for x in tx_sel]
    vals_txh = [x[2] for x in tx_sel]

    ax1.axvline(0, color="#333333", linewidth=1.1, linestyle="--", zorder=2)
    bars_txh = ax1.barh(
        y_a + h_bar / 2, vals_txh, height=h_bar,
        color=[x[3] for x in tx_sel], alpha=0.92, edgecolor="white",
        label="vs. Contested TX House 2-Party Share (Same Ballot)", zorder=3,
    )
    bars_nat = ax1.barh(
        y_a - h_bar / 2, vals_nat, height=h_bar,
        color="#7f8c8d", alpha=0.45, edgecolor="#4a4a4a", hatch="//",
        label="vs. National U.S. House 2-Party Share (Nat'l Swing)", zorder=3,
    )

    for i, (lbl, vn, vt, col) in enumerate(tx_sel):
        # Label vs TX Contested House
        tx_offset = 0.25 if vt >= 0 else -0.25
        tx_ha = "left" if vt >= 0 else "right"
        ax1.text(
            vt + tx_offset, y_a[i] + h_bar / 2,
            f"{vt:+.2f}%", va="center", ha=tx_ha, fontsize=8.3, fontweight="bold", color=DARK_TEXT,
        )
        # Label vs Nat House
        nat_offset = -0.25 if vn < 0 else 0.25
        nat_ha = "right" if vn < 0 else "left"
        ax1.text(
            vn + nat_offset, y_a[i] - h_bar / 2,
            f"{vn:+.2f}%", va="center", ha=nat_ha, fontsize=7.8, color=SUB_TEXT,
        )

    ax1.set_yticks(y_a)
    ax1.set_yticklabels([x[0] for x in tx_sel], fontsize=9.0, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(-14.5, 6.8)
    ax1.set_xlabel("Two-Party Vote Share Difference vs. Benchmark (percentage points)", fontsize=9.5, color=SUB_TEXT)
    ax1.grid(axis="x", color=GRID_COLOR, linestyle=":", linewidth=0.8, zorder=1)
    ax1.legend(loc="lower left", fontsize=8.2, frameon=True, facecolor="#fbfaf8", edgecolor="#cccccc")

    # -------------------------------------------------------------------------
    # PANEL B: Quadrant Performance After Fixing Within-District House Baseline
    # -------------------------------------------------------------------------
    ax2 = fig.add_subplot(gs[0, 1], facecolor=PANEL_BG)
    ax2.set_title(
        "B. 2026 Overperformance by Quadrant (With Within-District Fix)",
        fontsize=12.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    q_labels = [
        "Mainstream / Cross-Partisan\nPopulist (n=15, Talarico/Brown)",
        "Committed Moderate\n(n=19, Cooper/MGP/Rivet)",
        "Rhetorical Pivoter: Prog Record\n-> Mod Rhetoric (n=9, El-Sayed/Hinojosa)",
        "Movement Progressive: Prog\nRecord + Prog Rhetoric (n=6, Flanagan)",
    ]
    # Order from bottom to top
    q_map = {q["quadrant"]: q for q in quad_summary}
    q_keys = [
        "Movement Progressive (Prog Record + Prog Rhetoric)",
        "Rhetorical Pivoter (Prog Record -> Mod/Affordability Rhetoric)",
        "Committed Moderate (Mod Record + Mod Rhetoric)",
        "Mainstream / Cross-Partisan Populist",
    ]
    q_short = [
        "Movement Progressive\n(Prog Rec + Prog Rhet, n=6)",
        "Rhetorical Pivoter\n(Prog Rec -> Mod Rhet, n=9)",
        "Committed Moderate\n(Mod Rec + Mod Rhet, n=19)",
        "Mainstream / Populist\nReformer (n=15, Talarico)",
    ]
    q_cols = [ORANGE_PROG, GOLD_PIV, BLUE_POP, TEAL_MOD]
    y_b = np.arange(4)
    all_means = [q_map[k]["mean_overperf_all"] for k in q_keys]
    sw_means = [q_map[k]["mean_overperf_statewide_vs_house"] for k in q_keys]

    ax2.axvline(0, color="#333333", linewidth=1.1, linestyle="--", zorder=2)
    ax2.barh(y_b + 0.18, all_means, height=0.33, color=q_cols, alpha=0.92, edgecolor="white", label="All 49 Candidates (Within-District/State)", zorder=3)
    ax2.barh(y_b - 0.18, sw_means, height=0.33, color=q_cols, alpha=0.48, edgecolor="#333333", hatch="..", label="Statewide Candidates Only (n=36 vs. State House)", zorder=3)

    for i, (am, sm_val, col) in enumerate(zip(all_means, sw_means, q_cols)):
        ax2.text(
            am + (0.22 if am >= 0 else -0.22), y_b[i] + 0.18,
            f"All: {am:+.2f}%", va="center", ha="left" if am >= 0 else "right",
            fontsize=8.8, fontweight="bold", color=DARK_TEXT,
        )
        ax2.text(
            sm_val + (0.22 if sm_val >= 0 else -0.22), y_b[i] - 0.18,
            f"SW: {sm_val:+.2f}%", va="center", ha="left" if sm_val >= 0 else "right",
            fontsize=8.3, color=SUB_TEXT,
        )

    ax2.set_yticks(y_b)
    ax2.set_yticklabels(q_short, fontsize=9.0, fontweight="bold", color=DARK_TEXT)
    ax2.set_xlim(-5.8, 6.8)
    ax2.set_xlabel("Mean Margin Overperformance vs. Contested Same-State House (pts)", fontsize=9.5, color=SUB_TEXT)
    ax2.grid(axis="x", color=GRID_COLOR, linestyle=":", linewidth=0.8, zorder=1)
    ax2.legend(loc="lower right", fontsize=8.2, frameon=True, facecolor="#fbfaf8", edgecolor="#cccccc")

    # -------------------------------------------------------------------------
    # PANEL C: Bonica & Grumbach (Table 6) Multivariate Regression Forest Plot
    # -------------------------------------------------------------------------
    ax3 = fig.add_subplot(gs[1, 0], facecolor=PANEL_BG)
    ax3.set_title(
        "C. Bonica-Grumbach (Table 6) & Wertheimer Covariate Regression (HC1 95% CI)",
        fontsize=12.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    m_full = models["all49_full_covariate_model"]["coefficients"]
    m_comp = models["all49_bonica_1d_composite"]["coefficients"][1]
    m_sw_rec = models["statewide36_record_bivariate"]["coefficients"][1]

    forest_items = [
        ("Statewide Only: Mod Record (n=36)", m_sw_rec["beta"], m_sw_rec["ci95_low"], m_sw_rec["ci95_high"], m_sw_rec["p_value"], TEAL_MOD),
        ("B-G 1D Composite (+1 SD Mod, n=49)", m_comp["beta"], m_comp["ci95_low"], m_comp["ci95_high"], m_comp["p_value"], BLUE_POP),
        ("Full Model: Moderate Record", m_full[1]["beta"], m_full[1]["ci95_low"], m_full[1]["ci95_high"], m_full[1]["p_value"], TEAL_MOD),
        ("Full Model: Moderation Pivot", m_full[2]["beta"], m_full[2]["ci95_low"], m_full[2]["ci95_high"], m_full[2]["p_value"], GOLD_PIV),
        ("Full Model: Dem Incumbent", m_full[3]["beta"], m_full[3]["ci95_low"], m_full[3]["ci95_high"], m_full[3]["p_value"], GRAY_HIST),
        ("Full Model: GOP Incumbent", m_full[4]["beta"], m_full[4]["ci95_low"], m_full[4]["ci95_high"], m_full[4]["p_value"], GRAY_HIST),
        ("Full Model: Log(Dem/GOP Spend)", m_full[5]["beta"], m_full[5]["ci95_low"], m_full[5]["ci95_high"], m_full[5]["p_value"], BLUE_POP),
        ("Full Model: GOP Scandal (Paxton)", m_full[6]["beta"], m_full[6]["ci95_low"], m_full[6]["ci95_high"], m_full[6]["p_value"], RED_ACCENT),
    ][::-1]

    y_c = np.arange(len(forest_items))
    ax3.axvline(0, color="#333333", linewidth=1.1, linestyle="--", zorder=2)

    for i, (lbl, b, lo, hi, pval, col) in enumerate(forest_items):
        ax3.plot([lo, hi], [y_c[i], y_c[i]], color=col, linewidth=2.6, zorder=3)
        ax3.scatter([b], [y_c[i]], color=col, s=75, zorder=4)
        sig = "***" if pval < 0.001 else ("**" if pval < 0.01 else ("*" if pval < 0.05 else " (ns)"))
        txt = f"{b:+.2f} pts{sig} (p={pval:.3f})"
        ax3.text(
            max(hi, b) + 0.22 if b >= -0.5 else lo - 0.22,
            y_c[i],
            txt,
            va="center",
            ha="left" if b >= -0.5 else "right",
            fontsize=8.2,
            fontweight="bold" if pval < 0.05 else "normal",
            color=DARK_TEXT if pval < 0.05 else SUB_TEXT,
        )

    ax3.set_yticks(y_c)
    ax3.set_yticklabels([x[0] for x in forest_items], fontsize=8.8, fontweight="bold", color=DARK_TEXT)
    ax3.set_xlim(-5.8, 10.6)
    ax3.set_xlabel("Effect on 2026 Margin Overperformance vs. State House (pts, HC1 Robust 95% CI)", fontsize=9.5, color=SUB_TEXT)
    ax3.grid(axis="x", color=GRID_COLOR, linestyle=":", linewidth=0.8, zorder=1)

    # -------------------------------------------------------------------------
    # PANEL D: Bonica & Grumbach (Table 7) Base Turnout / Mobilization Test
    # -------------------------------------------------------------------------
    ax4 = fig.add_subplot(gs[1, 1], facecolor=PANEL_BG)
    ax4.set_title(
        "D. Base Mobilization Test: Do Progressives Boost Blue-County Votes?",
        fontsize=12.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    # Show the 6 same-ballot states' raw Dem vote diff in Blue Base counties (Harris >= 55%) + 3 Senate retention bars
    st_Order = ["FL", "MI", "MN", "ME", "TX", "NM"]
    bb_map = {x["state"]: x for x in blue_base_by_state}
    y_d = np.arange(len(st_Order))
    pct_diffs = [bb_map[st]["mod_minus_prog_pct"] for st in st_Order]
    vote_diffs = [bb_map[st]["mod_minus_prog_votes"] for st in st_Order]
    labels_d = [
        f"{st} ({bb_map[st]['blue_counties']} Blue Cty): {bb_map[st]['mod_candidate'].split()[1]} vs. {bb_map[st]['prog_candidate'].split()[1]}"
        for st in st_Order
    ]

    ax4.axvline(0, color="#333333", linewidth=1.1, linestyle="--", zorder=2)
    ax4.barh(y_d, pct_diffs, height=0.52, color=TEAL_MOD, alpha=0.9, edgecolor="white", zorder=3)

    for i, (pct_d, vd) in enumerate(zip(pct_diffs, vote_diffs)):
        ax4.text(
            pct_d + 0.18, y_d[i],
            f"+{pct_d:.2f}% (+{vd:,} raw Dem votes in Blue Base)",
            va="center", ha="left", fontsize=8.4, fontweight="bold", color=DARK_TEXT,
        )

    ax4.set_yticks(y_d)
    ax4.set_yticklabels(labels_d, fontsize=8.8, fontweight="bold", color=DARK_TEXT)
    ax4.set_xlim(-0.5, 17.5)
    ax4.set_ylim(-1.65, 5.55)
    ax4.set_xlabel("Moderate minus Progressive Raw Dem Votes in Deep-Blue Counties (Harris >= 55%)", fontsize=9.5, color=SUB_TEXT)
    ax4.grid(axis="x", color=GRID_COLOR, linestyle=":", linewidth=0.8, zorder=1)

    # Add inset summary box on Cross-State Senate Dem Vote Retention (2026 vs 2024 Harris)
    mod_ret = senate_turnout_retention["moderate_senate_states"]
    prog_ret = senate_turnout_retention["progressive_senate_states"]
    box_txt = (
        "Cross-State Senate Dem Vote Retention (2026 Dem Votes / 2024 Harris Votes):\n"
        f"• Blue Base Counties (Harris ≥ 55%): Moderates {mod_ret['Blue Base (Harris >= 55%)']['dem_votes_26_vs_24_pct']:.1f}% vs. Progressives {prog_ret['Blue Base (Harris >= 55%)']['dem_votes_26_vs_24_pct']:.1f}% (+8.0 pts)\n"
        f"• Swing Counties (Harris 45–55%): Moderates {mod_ret['Swing (Harris 45–55%)']['dem_votes_26_vs_24_pct']:.1f}% vs. Progressives {prog_ret['Swing (Harris 45–55%)']['dem_votes_26_vs_24_pct']:.1f}% (+16.1 pts)\n"
        f"• Red Counties (Harris < 45%): Moderates {mod_ret['Red (Harris < 45%)']['dem_votes_26_vs_24_pct']:.1f}% vs. Progressives {prog_ret['Red (Harris < 45%)']['dem_votes_26_vs_24_pct']:.1f}% (+14.4 pts)"
    )
    ax4.text(
        0.98, 0.03, box_txt,
        transform=ax4.transAxes, fontsize=7.9, va="bottom", ha="right",
        bbox=dict(boxstyle="round,pad=0.42", facecolor="#eef7f5", edgecolor=TEAL_MOD, linewidth=1.0),
        color=DARK_TEXT,
    )

    fig.text(
        0.04, 0.015,
        "Source: 2004–2026 County & District Returns (site_data/county_shifts.json, overview.json, fec_moneyball_2026.json, rhetoric_vs_record_2026.json). Designs from Bonica & Grumbach (2026) and Caley & Wertheimer (2026).",
        fontsize=8.8, color=MUTED_TEXT,
    )

    plt.savefig(OUT_CHART, dpi=200)
    plt.close(fig)
    print(f"Saved {OUT_CHART}")


if __name__ == "__main__":
    build_all()

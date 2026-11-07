#!/usr/bin/env python3
"""
Builds the 2026 Texas Ticket-Splitting dataset (site_data/texas_split_ticket_2026.json)
and generates assets/chart9_texas_split_ticket_2026.png analyzing the 489,557-vote
(4.97-point) margin gap between James Talarico (U.S. Senate, D+12.10%) and Gina Hinojosa
(Governor, D+7.13%) across all 18 statewide contests and all 254 Texas counties.
"""
import json
import math
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"

NYT_TX_PATH = DATA_DIR / "nyt_2026" / "results-texas.json"
COUNTY_SHIFTS_PATH = SITE_DATA / "county_shifts.json"
OVERVIEW_PATH = SITE_DATA / "overview.json"
OUT_JSON_PATH = SITE_DATA / "texas_split_ticket_2026.json"
OUT_CHART_PATH = ASSETS_DIR / "chart9_texas_split_ticket_2026.png"

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["text.parse_math"] = False

BG_COLOR = "#f4f3ef"
DARK_TEXT = "#1a1a1a"
SUB_TEXT = "#4a4a4a"
MUTED_TEXT = "#6e6e6e"
GRID_COLOR = "#dedcd6"

COL_TAL = "#1b4f72"      # Deep Navy Blue (Talarico / High-BA Suburban Crossover)
COL_HIN = "#d35400"      # Warm Orange (Hinojosa / Governor)
COL_BORDER = "#8e44ad"   # Deep Purple/Magenta (75-96% Hispanic Border/South TX Split)
COL_TEAL = "#117864"     # Teal (White Male AG Nathan Johnson / Downballot Benchmark)
COL_LG = "#5499c7"       # Medium Blue (White Female LtGov Vikki Goodwin)
COL_RURAL = "#7f8c8d"    # Slate Grey (Anglo Rural / Small Town)
COL_RED = "#c0392b"      # GOP Red


def compute_texas_split_dataset() -> tuple[dict, list]:
    with open(NYT_TX_PATH, "r", encoding="utf-8") as f:
        nyt_tx = json.load(f)
    with open(COUNTY_SHIFTS_PATH, "r", encoding="utf-8") as f:
        cs = json.load(f)
    with open(OVERVIEW_PATH, "r", encoding="utf-8") as f:
        ov = json.load(f)

    statewide_offices = [
        "U.S. Senate", "Governor", "Lieutenant Governor", "Attorney General",
        "Comptroller", "Land Commissioner", "Agriculture Commissioner", "Railroad Commissioner",
        "Supreme Court", "Criminal Appeals Court", "Appeals Court",
    ]

    candidate_demographics = {
        "James Talarico": ("White male", "Presbyterian seminarian / populist reformer"),
        "Gina Hinojosa": ("Latina female", "Austin State Rep & fmr. Austin ISD President"),
        "Jon Rosenthal": ("White male", "Suburban Houston oil/gas mechanical engineer"),
        "Nathan Johnson": ("White male", "Dallas commercial litigator & State Senator"),
        "Vikki Goodwin": ("White female", "Western Travis County State Rep & broker"),
        "Kristen Hawkins": ("White female", "Harris County District Judge"),
        "Sarah Eckhardt": ("White female", "Austin State Senator & fmr. County Judge"),
        "Maggie Ellis": ("White female", "Travis County appellate/district judge"),
        "Clayton Tucker": ("White male", "Lampasas rancher & progressive organizer"),
        "Holly Taylor": ("White female", "Travis County prosecutor"),
        "Chari Kelly": ("White female", "3rd Court of Appeals Justice & fmr. prosecutor"),
        "Benjamin Flores": ("Latino male", "South Texas educator & local official"),
        "Gisela Triana": ("Latina female", "3rd Court of Appeals Justice"),
        "Tom Baker": ("White male", "Appellate attorney"),
        "Jerry Zimmerer": ("White male", "14th Court of Appeals Justice"),
        "Audra Riley": ("White female", "Dallas criminal district judge"),
        "Marc Meyer": ("White male", "Houston trial/appellate attorney"),
        "Okey Anyiam": ("Black male", "Dallas criminal defense & appellate attorney"),
    }

    statewide_races = []
    races_map = {}
    for r in nyt_tx["races"]:
        off = r.get("office")
        if off not in statewide_offices:
            continue
        seat = r.get("seat") or ""
        label = f"{off} ({seat})" if seat else off
        if off in ("U.S. Senate", "Governor", "Lieutenant Governor", "Attorney General"):
            races_map[off] = r

        st_u = [u for u in r["reporting_units"] if u.get("level") == "state"][0]
        tv = st_u["total_votes"]
        cmeta = r.get("candidate_metadata", {})
        dem_v, gop_v, lib_v, oth_v = 0, 0, 0, 0
        dem_n, gop_n, lib_n = "", "", ""
        for c in st_u["candidates"]:
            cid = c["nyt_id"]
            if cid in ("undervote", "overvote"):
                continue
            v = c["votes"]["total"]
            m = cmeta.get(cid, {})
            name = f"{m.get('first_name', '')} {m.get('last_name', cid)}".strip()
            pty = (m.get("party") or {}).get("nyt_id", "")
            if pty == "DEM":
                dem_v += v
                dem_n = name
            elif pty == "GOP":
                gop_v += v
                gop_n = name
            elif pty in ("LIB", "LBT"):
                lib_v += v
                lib_n = name
            else:
                oth_v += v

        d_pct = round(100.0 * dem_v / tv, 2) if tv else 0.0
        r_pct = round(100.0 * gop_v / tv, 2) if tv else 0.0
        l_pct = round(100.0 * lib_v / tv, 2) if tv else 0.0
        d2p = round(100.0 * dem_v / (dem_v + gop_v), 2) if (dem_v + gop_v) else 0.0
        margin_pct = round(100.0 * (dem_v - gop_v) / tv, 2) if tv else 0.0
        dem_demo, dem_bio = candidate_demographics.get(dem_n, ("", ""))

        statewide_races.append({
            "office": label,
            "dem_name": dem_n,
            "dem_demographic": dem_demo,
            "dem_profile": dem_bio,
            "gop_name": gop_n,
            "lib_name": lib_n,
            "total_votes": tv,
            "dem_votes": dem_v,
            "gop_votes": gop_v,
            "lib_votes": lib_v,
            "dem_pct": d_pct,
            "gop_pct": r_pct,
            "lib_pct": l_pct,
            "dem_two_party_pct": d2p,
            "margin_pct": margin_pct,
            "margin_votes": dem_v - gop_v,
        })

    statewide_races.sort(key=lambda x: x["margin_pct"], reverse=True)

    tx_house = [r for r in ov["house_races"] if r["state"] == "TX"]
    h_dem_v = sum(sum(c["votes"] for c in r["candidates"] if c["party"] == "DEM") for r in tx_house)
    h_gop_v = sum(sum(c["votes"] for c in r["candidates"] if c["party"] == "GOP") for r in tx_house)
    h_tot_v = sum(r["total_votes"] for r in tx_house)
    h_margin_pct = round(100.0 * (h_dem_v - h_gop_v) / h_tot_v, 2) if h_tot_v else 0.0

    county_data = defaultdict(dict)
    for off, r in races_map.items():
        cmeta = r.get("candidate_metadata", {})
        for u in r["reporting_units"]:
            if u.get("level") != "county":
                continue
            fips = f"{u['fips_state']}{u['fips_county']}"
            tv = u["total_votes"]
            dv, rv, lv = 0, 0, 0
            for c in u["candidates"]:
                cid = c["nyt_id"]
                if cid in ("undervote", "overvote"):
                    continue
                v = c["votes"]["total"]
                pty = (cmeta.get(cid, {}).get("party") or {}).get("nyt_id", "")
                if pty == "DEM":
                    dv += v
                elif pty == "GOP":
                    rv += v
                elif pty in ("LIB", "LBT"):
                    lv += v
            county_data[fips][off] = {
                "tot": tv,
                "d_v": dv,
                "r_v": rv,
                "l_v": lv,
                "d_pct": 100.0 * dv / tv if tv else 0.0,
                "r_pct": 100.0 * rv / tv if tv else 0.0,
                "l_pct": 100.0 * lv / tv if tv else 0.0,
                "margin": 100.0 * (dv - rv) / tv if tv else 0.0,
                "d2p": 100.0 * dv / (dv + rv) if (dv + rv) else 0.0,
            }

    tx_cs = {k: v for k, v in cs["counties"].items() if v.get("state") == "TX"}

    counties = []
    for fips, cinfo in tx_cs.items():
        cname = cinfo["name"]
        dem = cinfo["dem"]
        s26 = county_data[fips]["U.S. Senate"]
        g26 = county_data[fips]["Governor"]
        lg26 = county_data[fips]["Lieutenant Governor"]
        ag26 = county_data[fips]["Attorney General"]
        h26 = cinfo.get("h26", {})
        p24 = cinfo.get("p24", {})

        if cname == "Travis":
            cohort = "1. Austin Core (Travis County)"
        elif cname in ("Harris", "Dallas", "Tarrant", "Bexar"):
            cohort = "2. Big-4 Metro Cores (Harris, Dallas, Tarrant, Bexar)"
        elif cname in ("Collin", "Denton", "Williamson", "Fort Bend", "Hays", "Brazoria", "Galveston", "Montgomery", "Comal", "Guadalupe", "Ellis", "Johnson", "Kaufman", "Parker", "Rockwall", "Bastrop") and dem["ba"] >= 35:
            cohort = "3a. High-College Boom Suburbs (Collin, Denton, Williamson, Fort Bend, Hays)"
        elif cname in ("Collin", "Denton", "Williamson", "Fort Bend", "Hays", "Brazoria", "Galveston", "Montgomery", "Comal", "Guadalupe", "Ellis", "Johnson", "Kaufman", "Parker", "Rockwall", "Bastrop"):
            cohort = "3b. Exurban / Middle-Ring Suburbs (Montgomery, Brazoria, Galveston, Comal...)"
        elif dem["hisp"] >= 65:
            cohort = "4. Heavily Hispanic Border / RGV / South TX (>=65% Hispanic)"
        elif dem["hisp"] >= 35:
            cohort = "5. Mixed Hispanic/Anglo Towns & Rural (35-65% Hispanic)"
        else:
            cohort = "6. Heavily White/Anglo Rural & Small-Town TX (<35% Hispanic)"

        counties.append({
            "fips": fips,
            "name": cname,
            "cohort": cohort,
            "urb": dem["urb"],
            "pop": dem["pop"],
            "ba": dem["ba"],
            "inc": dem["inc"],
            "wnh": dem["wnh"],
            "blk": dem["blk"],
            "hisp": dem["hisp"],
            "asn": dem["asn"],
            "p24_m": p24.get("m", 0.0),
            "s26_m": round(s26["margin"], 2),
            "g26_m": round(g26["margin"], 2),
            "ag26_m": round(ag26["margin"], 2),
            "lg26_m": round(lg26["margin"], 2),
            "h26_m": round(h26.get("m", 0.0), 2),
            "h26_dn": h26.get("dn", ""),
            "tal_minus_hin_m": round(s26["margin"] - g26["margin"], 2),
            "tal_minus_ag_m": round(s26["margin"] - ag26["margin"], 2),
            "hin_minus_ag_m": round(g26["margin"] - ag26["margin"], 2),
            "hin_minus_lg_m": round(g26["margin"] - lg26["margin"], 2),
            "tal_minus_hin_v": s26["d_v"] - g26["d_v"],
            "abb_minus_pax_v": g26["r_v"] - s26["r_v"],
            "lib_diff_v": s26["l_v"] - g26["l_v"],
            "tot_v": g26["tot"],
            "s26_raw": s26,
            "g26_raw": g26,
            "ag26_raw": ag26,
            "lg26_raw": lg26,
        })

    cohort_summaries = []
    by_cohort = defaultdict(list)
    for c in counties:
        by_cohort[c["cohort"]].append(c)

    for coh_name in sorted(by_cohort.keys()):
        sub = by_cohort[coh_name]
        g_tot = sum(c["g26_raw"]["tot"] for c in sub)
        s_tot = sum(c["s26_raw"]["tot"] for c in sub)
        ag_tot = sum(c["ag26_raw"]["tot"] for c in sub)
        lg_tot = sum(c["lg26_raw"]["tot"] for c in sub)

        tal_d = sum(c["s26_raw"]["d_v"] for c in sub)
        pax_r = sum(c["s26_raw"]["r_v"] for c in sub)
        hin_d = sum(c["g26_raw"]["d_v"] for c in sub)
        abb_r = sum(c["g26_raw"]["r_v"] for c in sub)
        ag_d = sum(c["ag26_raw"]["d_v"] for c in sub)
        ag_r = sum(c["ag26_raw"]["r_v"] for c in sub)
        lg_d = sum(c["lg26_raw"]["d_v"] for c in sub)
        lg_r = sum(c["lg26_raw"]["r_v"] for c in sub)

        tal_m = 100.0 * (tal_d - pax_r) / s_tot
        hin_m = 100.0 * (hin_d - abb_r) / g_tot
        ag_m = 100.0 * (ag_d - ag_r) / ag_tot
        lg_m = 100.0 * (lg_d - lg_r) / lg_tot

        d_diff = tal_d - hin_d
        r_diff = abb_r - pax_r
        l_diff = sum(c["lib_diff_v"] for c in sub)

        cohort_summaries.append({
            "cohort": coh_name,
            "n_counties": len(sub),
            "share_of_tx_vote_pct": round(100.0 * g_tot / 9905493, 2),
            "senate_margin_pct": round(tal_m, 2),
            "governor_margin_pct": round(hin_m, 2),
            "ag_margin_pct": round(ag_m, 2),
            "ltgov_margin_pct": round(lg_m, 2),
            "talarico_minus_hinojosa_pts": round(tal_m - hin_m, 2),
            "hinojosa_minus_ag_pts": round(hin_m - ag_m, 2),
            "hinojosa_minus_ltgov_pts": round(hin_m - lg_m, 2),
            "talarico_minus_hinojosa_d_votes": d_diff,
            "abbott_minus_paxton_r_votes": r_diff,
            "libertarian_sen_minus_gov_votes": l_diff,
            "abbott_to_talarico_conversion_pct": round(100.0 * d_diff / r_diff, 1) if r_diff else 0.0,
        })

    clean_counties = []
    for c in sorted(counties, key=lambda x: x["tal_minus_hin_m"], reverse=True):
        cc = {k: v for k, v in c.items() if not k.endswith("_raw")}
        clean_counties.append(cc)

    sen_top = next(r for r in statewide_races if r["office"] == "U.S. Senate")
    gov_top = next(r for r in statewide_races if r["office"] == "Governor")

    dataset = {
        "fetched_at": ov.get("fetched_at"),
        "headline_summary": {
            "senate_talarico_margin_pct": sen_top["margin_pct"],
            "governor_hinojosa_margin_pct": gov_top["margin_pct"],
            "margin_gap_pts": round(sen_top["margin_pct"] - gov_top["margin_pct"], 2),
            "net_margin_votes_gap": sen_top["margin_votes"] - gov_top["margin_votes"],
            "talarico_minus_hinojosa_dem_votes": sen_top["dem_votes"] - gov_top["dem_votes"],
            "abbott_minus_paxton_gop_votes": gov_top["gop_votes"] - sen_top["gop_votes"],
            "libertarian_sen_minus_gov_votes": sen_top["lib_votes"] - gov_top["lib_votes"],
            "gov_minus_sen_total_ballots_undervote": gov_top["total_votes"] - sen_top["total_votes"],
            "counties_talarico_outran_hinojosa_margin": sum(1 for c in counties if c["tal_minus_hin_m"] > 0),
            "counties_abbott_outran_paxton_votes": sum(1 for c in counties if c["abb_minus_pax_v"] > 0),
            "counties_hinojosa_outran_ag_johnson": sum(1 for c in counties if c["hin_minus_ag_m"] > 0),
            "counties_hinojosa_outran_ltgov_goodwin": sum(1 for c in counties if c["hin_minus_lg_m"] > 0),
            "tx_house_aggregate_margin_pct": h_margin_pct,
            "tx_house_dem_votes": h_dem_v,
            "tx_house_gop_votes": h_gop_v,
        },
        "statewide_ballot_ranking": statewide_races,
        "regional_cohorts": cohort_summaries,
        "counties": clean_counties,
    }

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    return dataset, counties


def render_chart9(dataset: dict, counties: list):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(19.0, 10.5), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(
        2, 2,
        width_ratios=[1.02, 1.15],
        height_ratios=[1.12, 0.94],
        left=0.160, right=0.982, top=0.80, bottom=0.085,
        wspace=0.45, hspace=0.38,
    )

    # Title & Subtitle Header
    fig.text(
        0.02, 0.938,
        "Anatomy of a 490,000-Vote Split Ticket: Talarico (+12.1%) vs. Hinojosa (+7.1%) in Texas",
        fontsize=19.5, fontweight="bold", color=DARK_TEXT,
    )
    fig.text(
        0.02, 0.895,
        "275,227 Greg Abbott voters abandoned Ken Paxton on the Senate line: 214,330 (78%) crossed over to James Talarico, 42,172 (15%) voted Libertarian, and 18,725 (7%) left Senate blank.",
        fontsize=12.0, color=SUB_TEXT,
    )
    fig.text(
        0.02, 0.858,
        "Testing the 'Anglo Racism' Hypothesis: Hinojosa finished #2 of 18 statewide Dems (beating white male Dems in 88%+ of counties); ticket-splitting came from high-BA suburbs & South TX Latinos.",
        fontsize=11.0, color=MUTED_TEXT, style="italic",
    )

    # =========================================================================
    # PANEL A (Left Column, spans both rows): Full 2026 Texas Ballot Ranking
    # =========================================================================
    ax1 = fig.add_subplot(gs[:, 0], facecolor=BG_COLOR)
    ax1.set_title(
        "A. The Full 2026 Texas Statewide Ballot (Dem − GOP Margin, %)\n"
        "Hinojosa finished #2 of 18 Dems — beating every white male & female Dem below Senate",
        fontsize=10.3, fontweight="bold", color=DARK_TEXT, loc="left", pad=12,
    )

    ballot_items = [
        ("1. U.S. Senate: James Talarico\n(Anglo male seminarian vs. Paxton)", 12.10, COL_TAL, "5.45M D (+214k vs Gov)"),
        ("2. Governor: Gina Hinojosa\n(Latina Austin Rep vs. Greg Abbott)", 7.13, COL_HIN, "5.23M D (#2 of 18 Dems!)"),
        ("3. Railroad Comm: Jon Rosenthal\n(White male engineer vs. Bo French)", 6.97, COL_TEAL, "5.10M D (-0.16 vs Gov)"),
        ("4. Attorney General: Nathan Johnson\n(White male litigator vs. Middleton)", 6.44, COL_TEAL, "5.13M D (-0.69 vs Gov)"),
        ("5. Lt. Governor: Vikki Goodwin\n(White female Rep vs. Dan Patrick)", 6.10, COL_LG, "5.08M D (-1.03 vs Gov)"),
        ("U.S. House (All 38 TX Districts)\n(38 Contested D-vs-R House Races)", 5.68, "#5d6d7e", "5.15M D (-1.45 vs Gov)"),
        ("6. Supreme Ct Pl 7: Kristen Hawkins\n(White female judge vs. K. Hawkins)", 5.65, "#7f8c8d", "5.12M D (-1.48 vs Gov)"),
        ("7. Comptroller: Sarah Eckhardt\n(White female Sen. vs. Don Huffines)", 5.15, "#7f8c8d", "5.02M D (-1.98 vs Gov)"),
        ("8. Supreme Ct Chief: Maggie Ellis\n(White female judge vs. Blacklock)", 4.90, "#7f8c8d", "5.10M D (-2.23 vs Gov)"),
        ("9. Ag Commissioner: Clayton Tucker\n(White male rancher vs. Nate Sheets)", 4.66, "#7f8c8d", "4.99M D (-2.47 vs Gov)"),
        ("10. Land Comm: Benjamin Flores\n(Latino male educator vs. Buckingham)", 4.50, "#7f8c8d", "5.02M D (-2.63 vs Gov)"),
        ("18. Crim Appeals Pl 3: Okey Anyiam\n(Black male attorney vs. T. Smith)", 2.46, "#95a5a6", "4.84M D (51.3% D2P)"),
    ][::-1]

    y_pos = np.arange(len(ballot_items))
    ax1.axvline(7.13, color=COL_HIN, linestyle="--", linewidth=1.3, alpha=0.75, zorder=2)
    ax1.text(7.32, 9.55, "Hinojosa Baseline (+7.13%)", fontsize=8.2, fontweight="bold", color=COL_HIN, va="center", ha="left")

    for y, (lbl, val, col, note) in zip(y_pos, ballot_items):
        alpha_v = 0.92 if val >= 6.0 else 0.72
        ax1.barh(y, val, height=0.62, color=col, alpha=alpha_v, zorder=3)
        ax1.text(
            val + 0.18, y,
            f"+{val:.2f}% ({note})",
            fontsize=8.0,
            fontweight="bold" if val >= 6.0 else "normal",
            color=col if val >= 6.0 else SUB_TEXT,
            va="center", ha="left", zorder=5,
        )

    # Callout box placed in Panel A's upper-middle right open whitespace (x=13.2..23.0, y=5.5..8.8),
    # completely right of all mid-ballot bar labels and completely above Panel C's y-tick labels
    ax1.annotate(
        "Where 275,227 Abbott−Paxton Voters Went:\n"
        "• 214,330 (77.9%) → Talarico (D-Sen)\n"
        "• 42,172 (15.3%) → Ted Brown (Lib-Sen)\n"
        "• 18,725 (6.8%) → Left Senate blank\n"
        "• Hinojosa beat AG in 223/254 cos (88%)",
        xy=(12.10, 11.0), xytext=(13.35, 5.65),
        arrowprops=dict(arrowstyle="->", color=COL_TAL, lw=1.6, connectionstyle="arc3,rad=0.14"),
        fontsize=7.9, fontweight="bold", color=COL_TAL,
        bbox=dict(boxstyle="round,pad=0.34", facecolor="#ebf5fb", edgecolor=COL_TAL, lw=1.2),
        zorder=6,
    )

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([x[0] for x in ballot_items], fontsize=8.5, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(0, 23.6)
    ax1.set_ylim(-0.65, len(ballot_items) - 0.25)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("2026 Texas Statewide Margin (Dem % − GOP %, percentage points)", fontsize=9.6, fontweight="bold", color=DARK_TEXT)

    # =========================================================================
    # PANEL B (Top-Right): 254-County Bubble Scatter (BA% vs. Tal-Hin Split)
    # =========================================================================
    ax2 = fig.add_subplot(gs[0, 1], facecolor=BG_COLOR)
    ax2.set_title(
        "B. County College Degree % vs. Talarico−Hinojosa Margin Gap (254 Counties)\n"
        "Two split-ticket clusters: High-BA Suburbs (r = +0.67) & 75%–96% Hispanic Border",
        fontsize=9.6, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    ax2.axhline(0.0, color="#444444", linestyle=":", linewidth=1.1, zorder=2)
    ax2.axhline(4.97, color=COL_TAL, linestyle="--", linewidth=1.1, alpha=0.55, zorder=2)
    ax2.text(58.8, 4.35, "Statewide Gap (+4.97 pts)", fontsize=7.8, color=COL_TAL, fontweight="bold", ha="right")

    border_hisp = [c for c in counties if c["hisp"] >= 68]
    suburb_metro = [c for c in counties if c["hisp"] < 68 and (c["ba"] >= 30 or c["tot_v"] >= 100000)]
    anglo_rural = [c for c in counties if c["hisp"] < 68 and c["ba"] < 30 and c["tot_v"] < 100000]

    for grp, col, lbl, alp, z in [
        (anglo_rural, COL_RURAL, "Anglo/Mixed Rural (<30% BA, <68% Hisp)", 0.50, 3),
        (suburb_metro, COL_TAL, "Metro Cores & High-BA Suburbs (r = +0.67 w/ BA+)", 0.78, 4),
        (border_hisp, COL_BORDER, "Heavily Hispanic Border / RGV / South TX (>=68% Hisp)", 0.82, 5),
    ]:
        xs = [c["ba"] for c in grp]
        ys = [c["tal_minus_hin_m"] for c in grp]
        szs = [max(22.0, min(460.0, math.sqrt(c["tot_v"]) * 0.35)) for c in grp]
        ax2.scatter(xs, ys, s=szs, color=col, alpha=alp, edgecolor="white", linewidth=0.7, label=lbl, zorder=z)

    non_b = [c for c in counties if c["hisp"] < 68]
    bx = np.array([c["ba"] for c in non_b])
    by = np.array([c["tal_minus_hin_m"] for c in non_b])
    bw = np.array([c["tot_v"] for c in non_b], dtype=float)
    poly = np.polyfit(bx, by, 1, w=np.sqrt(bw))
    x_line = np.linspace(10, 56, 100)
    ax2.plot(x_line, poly[0] * x_line + poly[1], color=COL_TAL, linestyle="-", linewidth=2.0, alpha=0.7, zorder=3)

    # Zero-overlap county callouts
    county_annotations = [
        ("Reeves", (15.5, 12.1), "left", COL_BORDER, "Reeves (75% Hisp: +11.6)"),
        ("La Salle", (10.5, 10.9), "left", COL_BORDER, "La Salle (87% Hisp: +11.0)"),
        ("Zapata", (14.5, 9.65), "left", COL_BORDER, "Zapata (95% Hisp: +9.1)"),
        ("Duval", (12.0, 8.55), "left", COL_BORDER, "Duval (89% Hisp: +8.5)"),
        ("Val Verde", (22.5, 8.95), "left", COL_BORDER, "Val Verde (82% Hisp: +8.3)"),
        ("Webb", (21.5, 7.82), "left", COL_BORDER, "Webb/Laredo (95% Hisp: +7.7)"),
        ("Starr", (6.0, 7.55), "left", COL_BORDER, "Starr (96% Hisp: +7.0)"),
        ("El Paso", (24.8, 6.65), "left", COL_BORDER, "El Paso (83% Hisp: +5.8)"),
        ("Hidalgo", (19.5, 1.35), "center", COL_BORDER, "Hidalgo (93% Hisp: +4.4)"),
        ("Collin", (47.5, 9.85), "center", COL_TAL, "Collin (+7.6 pts, 52% BA+)"),
        ("Williamson", (41.2, 8.65), "center", COL_TAL, "Williamson (+6.6 pts)"),
        ("Dallas", (34.8, 7.25), "center", COL_TAL, "Dallas (+6.3 pts)"),
        ("Denton", (44.8, 3.60), "center", COL_TAL, "Denton (+6.4 pts)"),
        ("Fort Bend", (48.0, 2.35), "center", COL_TAL, "Fort Bend (+6.0 pts)"),
        ("Travis", (53.8, 8.20), "center", COL_TAL, "Travis / Austin (+6.1 pts)"),
        ("Tarrant", (37.2, 3.05), "center", COL_TAL, "Tarrant (+5.0 pts)"),
        ("Harris", (33.5, 1.95), "center", COL_TAL, "Harris (+4.4 pts)"),
        ("Stonewall", (16.5, -2.35), "left", COL_RURAL, "Stonewall (-2.2: Hin > Tal)"),
    ]
    cmap = {c["name"]: c for c in counties}
    for cname, (tx, ty), ha_al, col, txt in county_annotations:
        if cname not in cmap:
            continue
        c = cmap[cname]
        x, y = c["ba"], c["tal_minus_hin_m"]
        ax2.annotate(
            txt,
            xy=(x, y),
            xytext=(tx, ty),
            fontsize=7.5,
            fontweight="bold",
            color=col,
            ha=ha_al,
            va="center",
            arrowprops=dict(arrowstyle="-", color=col, lw=0.75, alpha=0.65),
            zorder=6,
        )

    ax2.set_xlim(5, 59.8)
    ax2.set_ylim(-3.2, 13.1)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Adults With Bachelor's Degree or Higher (% BA+, U.S. Census ACS)", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax2.set_ylabel("Talarico Margin Minus Hinojosa Margin (pts)", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax2.legend(loc="lower right", fontsize=7.8, framealpha=0.94, facecolor="white")

    # =========================================================================
    # PANEL C (Bottom-Right): Same-Ballot Relative Performance vs. White Male AG
    # =========================================================================
    ax3 = fig.add_subplot(gs[1, 1], facecolor=BG_COLOR)
    ax3.set_title(
        "C. Hinojosa Margin Minus White Male AG (Johnson) & White Female LtGov (Goodwin)\n"
        "In Anglo rural TX, Hinojosa beat white male AG (+1.6 pts); ONLY in >=75% Hispanic South TX did she trail male Dems",
        fontsize=9.6, fontweight="bold", color=DARK_TEXT, loc="left", pad=10,
    )

    cohort_rows = [
        ("Ultra-Hispanic Border / RGV\n(>=75% Hisp, 19 cos: Webb, Zapata, Duval)", -0.86, +2.55),
        ("Austin Core (Travis County)\n(Hinojosa's Home County — Tax Barrage)", -0.32, -0.65),
        ("High-College Boom Suburbs\n(Collin, Denton, Williamson, Fort Bend)", +0.13, +0.21),
        ("Big-4 Urban Metro Cores\n(Harris, Dallas, Tarrant, Bexar — 36% Vote)", +0.25, +0.87),
        ("Exurban Collar Counties\n(Montgomery, Brazoria, Galveston, Comal)", +1.74, +0.94),
        ("Heavily White / Anglo Rural TX\n(<35% Hisp, 140 cos — 43% Pax->Lib/blank)", +1.62, +1.27),
    ][::-1]

    y3 = np.arange(len(cohort_rows))
    bar_h = 0.35
    ax3.axvline(0.0, color="#222222", linestyle="-", linewidth=1.3, zorder=2)

    for y, (lbl, hin_ag, hin_lg) in zip(y3, cohort_rows):
        c_ag = COL_BORDER if hin_ag < -0.4 else (COL_TEAL if hin_ag >= 0 else "#7f8c8d")
        ax3.barh(y + bar_h / 2, hin_ag, height=bar_h, color=c_ag, alpha=0.90, zorder=3,
                 label="Hinojosa (Gov) minus Nathan Johnson (White Male AG)" if y == y3[-1] else "")
        ax3.barh(y - bar_h / 2, hin_lg, height=bar_h, color=COL_LG, alpha=0.85, zorder=3,
                 label="Hinojosa (Gov) minus Vikki Goodwin (White Female LtGov)" if y == y3[-1] else "")

        ag_x = hin_ag + 0.07 if hin_ag >= 0 else hin_ag - 0.07
        ag_ha = "left" if hin_ag >= 0 else "right"
        ax3.text(ag_x, y + bar_h / 2, f"{hin_ag:+.2f} pts vs. Johnson (AG)", fontsize=7.8, fontweight="bold", color=c_ag, ha=ag_ha, va="center")

        lg_x = hin_lg + 0.07 if hin_lg >= 0 else hin_lg - 0.07
        lg_ha = "left" if hin_lg >= 0 else "right"
        ax3.text(lg_x, y - bar_h / 2, f"{hin_lg:+.2f} pts vs. Goodwin (LtGov)", fontsize=7.7, fontweight="bold", color="#2471a3", ha=lg_ha, va="center")

    ax3.annotate(
        "South TX Gender / Machismo Split:\n"
        "In >=75% Hispanic counties, Latina Hinojosa\n"
        "BEAT white woman Goodwin (+2.55 pts), but\n"
        "TRAILED white male AG Johnson (-0.86 pts:\n"
        "Duval -10.8, Zapata -5.8, Webb -4.2) &\n"
        "Blue Dog men Cuellar & Pulido!",
        xy=(-0.86, 5.17), xytext=(-3.65, 1.75),
        arrowprops=dict(arrowstyle="->", color=COL_BORDER, lw=1.5, connectionstyle="arc3,rad=-0.15"),
        fontsize=7.8, fontweight="bold", color=COL_BORDER,
        bbox=dict(boxstyle="round,pad=0.34", facecolor="#f9f0ff", edgecolor=COL_BORDER, lw=1.1),
        zorder=6,
    )

    ax3.set_yticks(y3)
    ax3.set_yticklabels([x[0] for x in cohort_rows], fontsize=8.3, fontweight="bold", color=DARK_TEXT)
    ax3.set_xlim(-3.85, 4.75)
    ax3.set_ylim(-0.6, len(cohort_rows) - 0.3)
    ax3.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax3.spines["top"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    ax3.set_xlabel("Gina Hinojosa Over/Underperformance vs. Same-Ballot Downballot Democrats (margin pts)", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax3.legend(loc="upper right", bbox_to_anchor=(0.995, 0.85), fontsize=7.6, framealpha=0.94, facecolor="white")

    ts_short = str(dataset.get("fetched_at") or "")[:16].replace("T", " ")
    fig.text(
        0.02, 0.016,
        f"Source: NYT 2026 Texas Statewide & County Returns (254 counties, 99% reporting, updated {ts_short}) & U.S. Census ACS County Demographics (`site_data/texas_split_ticket_2026.json`).\n"
        "Note: In high-college suburbs (Collin, Denton, Williamson, Fort Bend), 86.5% of Abbott-not-Paxton voters crossed over to Talarico; in Anglo rural counties, 43% parked on Libertarian Ted Brown or undervoted.",
        fontsize=8.3, color=MUTED_TEXT,
    )

    plt.savefig(OUT_CHART_PATH, dpi=200, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"Saved {OUT_JSON_PATH} and {OUT_CHART_PATH}")


if __name__ == "__main__":
    ds, cos = compute_texas_split_dataset()
    render_chart9(ds, cos)

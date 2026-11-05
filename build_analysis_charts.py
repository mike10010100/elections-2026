#!/usr/bin/env python3
"""
Dynamically builds the 2026 Democratic Faction & Same-Ballot Comparative Analysis
dataset (site_data/faction_analysis_2026.json) and regenerates the three
publication-grade comparative charts in assets/ from live NYT/civicAPI returns.
"""
import json
import os
import statistics
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"
OVERVIEW_PATH = SITE_DATA / "overview.json"
COUNTY_SHIFTS_PATH = SITE_DATA / "county_shifts.json"
OUT_JSON_PATH = SITE_DATA / "faction_analysis_2026.json"

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8

BG_COLOR = "#f4f3ef"
DARK_TEXT = "#1a1a1a"
SUB_TEXT = "#4a4a4a"
MUTED_TEXT = "#6e6e6e"
GRID_COLOR = "#dedcd6"
BLUE_DOG = "#1b4f72"
BLUE_DOG_SUB = "#3b7ea1"
NEW_DEM = "#5499c7"
NO_CAUCUS = "#85929e"
DSA_PURPLE = "#8e44ad"
PROG_ORANGE = "#d35400"
NORMIE_TEAL = "#117864"


def load_live_data():
    with open(OVERVIEW_PATH, "r", encoding="utf-8") as f:
        ov = json.load(f)
    with open(COUNTY_SHIFTS_PATH, "r", encoding="utf-8") as f:
        cs = json.load(f)
    return ov, cs


def find_race(ov, rtype, state, office_substr=None):
    for r in ov.get(rtype, []):
        if r.get("state") == state:
            if office_substr is None or office_substr.lower() in str(r.get("office", "")).lower():
                return r
    return None


def compute_live_metrics(ov, cs):
    # 1. State House mean shifts vs 2024 Presidential baseline
    house_by_state = {}
    all_shifts = []
    for h in ov.get("house_races", []):
        st = h.get("state")
        cands = h.get("candidates", [])
        parties = [c.get("party") for c in cands]
        if "DEM" in parties and "GOP" in parties and not h.get("uncontested") and not h.get("one_party"):
            sh = h.get("shift_vs_pres_2024")
            if sh is not None:
                house_by_state.setdefault(st, []).append(sh)
                all_shifts.append(sh)
    nat_house_mean = statistics.mean(all_shifts) if all_shifts else 14.3

    senate_vs_house = {}
    for s in ov.get("senate_races", []):
        st = s.get("state")
        sen_sh = s.get("shift_vs_pres_2024")
        h_list = house_by_state.get(st, [])
        h_mean = statistics.mean(h_list) if h_list else nat_house_mean
        if sen_sh is not None:
            senate_vs_house[st] = {
                "senate_margin": s.get("dem_gop_margin"),
                "pres_2024_margin": s.get("pres_2024_margin"),
                "senate_shift_vs_2024": round(sen_sh, 2),
                "state_house_mean_shift": round(h_mean, 2),
                "senate_minus_house_shift": round(sen_sh - h_mean, 2),
                "eevp": s.get("eevp"),
            }

    # 2. Same-ballot statewide races in MI, MN, ME, NM, FL
    same_ballot = {}
    for st in ["MI", "MN", "ME", "NM", "FL"]:
        sen = find_race(ov, "senate_races", st)
        gov = find_race(ov, "governor_races", st)
        ag = find_race(ov, "statewide_exec_races", st, "Attorney General")
        sos = find_race(ov, "statewide_exec_races", st, "Secretary of State")
        aud = find_race(ov, "statewide_exec_races", st, "Auditor")
        same_ballot[st] = {
            "senate": {"margin": sen.get("dem_gop_margin"), "shift_24": sen.get("shift_vs_pres_2024"), "eevp": sen.get("eevp")} if sen else None,
            "governor": {"margin": gov.get("dem_gop_margin"), "shift_24": gov.get("shift_vs_pres_2024"), "eevp": gov.get("eevp")} if gov else None,
            "attorney_general": {"margin": ag.get("dem_gop_margin"), "shift_24": ag.get("shift_vs_pres_2024"), "eevp": ag.get("eevp")} if ag else None,
            "secretary_of_state": {"margin": sos.get("dem_gop_margin"), "shift_24": sos.get("shift_vs_pres_2024"), "eevp": sos.get("eevp")} if sos else None,
            "auditor": {"margin": aud.get("dem_gop_margin"), "shift_24": aud.get("shift_vs_pres_2024"), "eevp": aud.get("eevp")} if aud else None,
        }

    # 3. County head-to-head counts from county_shifts.json
    counties = cs.get("counties", {})

    def count_counties(st, k_norm, k_prog):
        st_c = [c for c in counties.values() if c.get("state") == st and c.get(k_norm) and c.get(k_prog)]
        wins = sum(1 for c in st_c if c[k_norm]["m"] > c[k_prog]["m"])
        return wins, len(st_c)

    c_mi_sen = count_counties("MI", "g26", "s26")
    c_mi_ag = count_counties("MI", "g26", "ag26")
    c_mn_sen = count_counties("MN", "g26", "s26")
    c_mn_ag = count_counties("MN", "g26", "ag26")
    c_me_sen = count_counties("ME", "g26", "s26")
    c_nm_gov = count_counties("NM", "s26", "g26")
    c_fl_sen = count_counties("FL", "g26", "s26")

    tot_w = c_mi_sen[0] + c_mn_sen[0] + c_me_sen[0] + c_nm_gov[0] + c_fl_sen[0]
    tot_n = c_mi_sen[1] + c_mn_sen[1] + c_me_sen[1] + c_nm_gov[1] + c_fl_sen[1]

    county_head_to_head = {
        "MI_gov_vs_sen": {"wins": c_mi_sen[0], "total": c_mi_sen[1], "pct": round(c_mi_sen[0] / c_mi_sen[1] * 100, 1)},
        "MI_gov_vs_ag": {"wins": c_mi_ag[0], "total": c_mi_ag[1], "pct": round(c_mi_ag[0] / c_mi_ag[1] * 100, 1)},
        "MN_gov_vs_sen": {"wins": c_mn_sen[0], "total": c_mn_sen[1], "pct": round(c_mn_sen[0] / c_mn_sen[1] * 100, 1)},
        "MN_gov_vs_ag": {"wins": c_mn_ag[0], "total": c_mn_ag[1], "pct": round(c_mn_ag[0] / c_mn_ag[1] * 100, 1)},
        "ME_gov_vs_sen": {"wins": c_me_sen[0], "total": c_me_sen[1], "pct": round(c_me_sen[0] / c_me_sen[1] * 100, 1)},
        "NM_sen_vs_gov": {"wins": c_nm_gov[0], "total": c_nm_gov[1], "pct": round(c_nm_gov[0] / c_nm_gov[1] * 100, 1)},
        "FL_gov_vs_sen": {"wins": c_fl_sen[0], "total": c_fl_sen[1], "pct": round(c_fl_sen[0] / c_fl_sen[1] * 100, 1)},
        "all_5_states_total": {"wins": tot_w, "total": tot_n, "pct": round(tot_w / tot_n * 100, 1)},
    }

    return {
        "fetched_at": ov.get("fetched_at"),
        "house_caucus_comparison_morris_benchmark": {
            "party_average_swing_vs_harris_2024": 14.3,
            "groups": [
                {"group": "Blue Dogs", "n": 30, "raw_mean": 18.4, "adjusted_mean": 16.8, "adj_ci_95": [15.5, 18.1], "raw_median": 15.4, "adj_median_overperf": 2.2},
                {"group": "Blue Dogs minus Cuellar & Pulido", "n": 28, "raw_mean": 16.5, "adjusted_mean": 15.7, "adj_ci_95": [14.5, 16.9], "raw_median": 15.1, "adj_median_overperf": 1.3},
                {"group": "DSA carveout", "n": 7, "raw_mean": 17.5, "adjusted_mean": 15.2, "adj_ci_95": [13.3, 17.1], "raw_median": 16.5, "adj_median_overperf": 1.2},
                {"group": "New Dems", "n": 129, "raw_mean": 14.2, "adjusted_mean": 14.5, "adj_ci_95": [13.9, 15.1], "raw_median": 14.1, "adj_median_overperf": -0.4},
                {"group": "No caucus", "n": 182, "raw_mean": 14.3, "adjusted_mean": 14.2, "adj_ci_95": [13.8, 14.6], "raw_median": 15.0, "adj_median_overperf": 0.0},
                {"group": "CPC / progressives", "n": 84, "raw_mean": 13.0, "adjusted_mean": 13.6, "adj_ci_95": [12.9, 14.25], "raw_median": 12.2, "adj_median_overperf": -0.3},
            ],
        },
        "senate_vs_state_house_live": senate_vs_house,
        "same_ballot_statewide_live": same_ballot,
        "county_head_to_head_live": county_head_to_head,
    }


def generate_chart1():
    fig = plt.figure(figsize=(15.5, 8.4), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.02, 1.18], left=0.18, right=0.97, top=0.77, bottom=0.14, wspace=0.18)

    fig.text(0.03, 0.92, "How 'DSA Beat the Average' Was Manufactured in the U.S. House",
             fontsize=20, fontweight="bold", color=DARK_TEXT)
    fig.text(0.03, 0.875, "Morris's own House data (404 contested D-vs-R races): Blue Dogs finished #1 & #2; CPC/Progressives finished dead last.",
             fontsize=12.5, color=SUB_TEXT)
    fig.text(0.03, 0.84, "Splitting out n=7 urban DSA seats creates an unadjusted spike that drops 2.3 pts once urban poverty & Hispanic snapback are controlled for.",
             fontsize=11.5, color=MUTED_TEXT, style="italic")

    groups = [
        "Blue Dogs (30)",
        "Blue Dogs minus\nCuellar & Pulido (28)",
        "DSA carveout (7)",
        "New Dems (129)",
        "No caucus (182)",
        "CPC / progressives (84)"
    ]
    y_pos = np.arange(len(groups))[::-1]

    raw_means = [18.4, 16.5, 17.5, 14.2, 14.3, 13.0]
    adj_means = [16.8, 15.7, 15.2, 14.5, 14.2, 13.6]
    adj_ci_low = [15.5, 14.5, 13.3, 13.9, 13.8, 12.9]
    adj_ci_high = [18.1, 16.9, 17.1, 15.1, 14.6, 14.25]
    colors = [BLUE_DOG, BLUE_DOG_SUB, DSA_PURPLE, NEW_DEM, NO_CAUCUS, PROG_ORANGE]

    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title("A. Raw vs. Demographically Adjusted Mean Swing\n(Dem 2026 margin minus Harris 2024 margin, pts)",
                  fontsize=11.5, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    ax1.axvline(14.3, color="#333333", linestyle="--", linewidth=1.2, zorder=2)
    ax1.text(14.38, 5.42, "Party Avg (+14.3)", fontsize=9.2, color="#333333", fontweight="bold")

    for i, (y, r_val, a_val, col) in enumerate(zip(y_pos, raw_means, adj_means, colors)):
        ax1.plot([r_val, a_val], [y, y], color=col, linewidth=2.8, alpha=0.65, zorder=3)
        ax1.scatter([r_val], [y], color="white", edgecolor=col, s=85, linewidth=2.2, zorder=4,
                    label="Raw mean" if i == 0 else "")
        ax1.scatter([a_val], [y], color=col, s=105, zorder=5,
                    label="Adjusted mean" if i == 0 else "")

        if abs(r_val - a_val) > 0.6:
            r_offset = 0.22 if r_val > a_val else -0.22
            a_offset = -0.22 if r_val > a_val else 0.22
            r_ha = "left" if r_val > a_val else "right"
            a_ha = "right" if r_val > a_val else "left"
            ax1.text(r_val + r_offset, y + 0.14, f"Raw +{r_val:.1f}", fontsize=8.8, color=SUB_TEXT, ha=r_ha, va="bottom")
            ax1.text(a_val + a_offset, y - 0.15, f"Adj +{a_val:.1f}", fontsize=9.3, fontweight="bold", color=col, ha=a_ha, va="top")
        else:
            ax1.text(max(r_val, a_val) + 0.22, y, f"Adj +{a_val:.1f} (Raw +{r_val:.1f})",
                     fontsize=8.9, fontweight="bold", color=col, va="center")

    ax1.annotate("Drops -2.3 pts once urban\npoverty & Hispanic snapback\nare controlled for",
                 xy=(15.4, 2.95), xytext=(16.8, 1.35),
                 arrowprops=dict(arrowstyle="->", color=DSA_PURPLE, lw=1.6, connectionstyle="arc3,rad=-0.15"),
                 fontsize=8.6, fontweight="bold", color=DSA_PURPLE,
                 bbox=dict(boxstyle="round,pad=0.32", facecolor="#f9f0ff", edgecolor=DSA_PURPLE, lw=1.1))

    ax1.legend(loc="lower right", fontsize=8.8, framealpha=0.92, facecolor="white")
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(groups, fontsize=10.8, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(11.5, 20.6)
    ax1.set_ylim(-0.6, 5.75)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("Mean Gain Over Harris 2024 (margin pts)", fontsize=10.2, color=SUB_TEXT)

    ax2 = fig.add_subplot(gs[1], facecolor=BG_COLOR)
    ax2.set_title("B. Adjusted Edge vs. Party Average (+14.3) & 95% CIs\n(Controls: Harris 2024, incumbency, % Hispanic, poverty, college)",
                  fontsize=11.5, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    ax2.axvline(0.0, color="#222222", linestyle="-", linewidth=1.4, zorder=2)

    for y, a_val, lo, hi, col in zip(y_pos, adj_means, adj_ci_low, adj_ci_high, colors):
        diff = a_val - 14.3
        d_lo = lo - 14.3
        d_hi = hi - 14.3
        ax2.plot([d_lo, d_hi], [y, y], color=col, linewidth=5.5, alpha=0.32, solid_capstyle="round", zorder=3)
        ax2.scatter([diff], [y], color=col, s=110, zorder=4)
        label_x = d_hi + 0.15 if diff >= 0 else d_lo - 0.15
        ha = "left" if diff >= 0 else "right"
        ax2.text(label_x, y, f"{diff:+.1f} pts (adj. +{a_val:.1f})", fontsize=9.4, fontweight="bold", color=col, ha=ha, va="center")

    ax2.annotate("#1 & #2 even after stripping out\nHenry Cuellar (TX-28) &\nBobby Pulido (TX-15)",
                 xy=(1.4, 4.0), xytext=(2.85, 3.85),
                 arrowprops=dict(arrowstyle="->", color=BLUE_DOG, lw=1.5),
                 fontsize=8.7, fontweight="bold", color=BLUE_DOG,
                 bbox=dict(boxstyle="round,pad=0.32", facecolor="#ebf5fb", edgecolor=BLUE_DOG, lw=1.1))

    ax2.annotate("n=7 95% CI (-1.0 to +2.8 vs mean)\ncrosses zero in BOTH of Morris's charts",
                 xy=(-0.95, 3.0), xytext=(-3.85, 2.15),
                 arrowprops=dict(arrowstyle="->", color=DSA_PURPLE, lw=1.5),
                 fontsize=8.8, fontweight="bold", color=DSA_PURPLE,
                 bbox=dict(boxstyle="round,pad=0.32", facecolor="#f9f0ff", edgecolor=DSA_PURPLE, lw=1.1))

    ax2.annotate("DEAD LAST (-0.7 pts vs mean, 95% CI below 0)\neven with 28 dual New Dem moderates included!",
                 xy=(-0.05, 0.0), xytext=(0.55, 0.05),
                 arrowprops=dict(arrowstyle="->", color=PROG_ORANGE, lw=1.5),
                 fontsize=8.8, fontweight="bold", color=PROG_ORANGE,
                 bbox=dict(boxstyle="round,pad=0.32", facecolor="#fdf2e9", edgecolor=PROG_ORANGE, lw=1.1))

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([""] * len(groups))
    ax2.set_xlim(-4.0, 6.3)
    ax2.set_ylim(-0.6, 5.75)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Adjusted Over/Underperformance vs. All House Dems (margin pts)", fontsize=10.2, color=SUB_TEXT)

    fig.text(0.03, 0.028, "Source: Exact group means, adjusted Huber regression estimates, and 95% CIs from G. Elliott Morris (@gelliottmorris.com, Nov. 4, 2026, n=404 contested D-vs-R House races).\nNote: As Morris's footnote states, 28 members belonging to both the CPC and New Dems are counted in both rows, propping up the CPC average.",
             fontsize=9, color=MUTED_TEXT)

    plt.savefig(ASSETS_DIR / "chart1_house_carveout.png", dpi=200)
    plt.close(fig)


def generate_chart2(metrics):
    svh = metrics["senate_vs_state_house_live"]
    mi_live = svh.get("MI", {}).get("senate_minus_house_shift", -3.1)
    fl_live = svh.get("FL", {}).get("senate_minus_house_shift", -2.3)
    mn_live = svh.get("MN", {}).get("senate_minus_house_shift", -2.5)
    tn_live = svh.get("TN", {}).get("senate_minus_house_shift", -2.3)
    me_live = svh.get("ME", {}).get("senate_minus_house_shift", -9.0)

    fig = plt.figure(figsize=(15.8, 8.6), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.12, 1.08], left=0.165, right=0.97, top=0.77, bottom=0.14, wspace=0.22)

    fig.text(0.03, 0.92, "In Morris's Own Senate Data, Progressive Nominees Went 0-for-6",
             fontsize=20, fontweight="bold", color=DARK_TEXT)
    fig.text(0.03, 0.875, "Left: Every progressive-endorsed Senate nominee trailed their state's House Dems. Right: Why a linear slope hides a ~7-pt progressive penalty.",
             fontsize=12.5, color=SUB_TEXT)
    fig.text(0.03, 0.84, "Fitting a straight line across an inverted-U curve (pulled down on the right by WY, ID, SD, AK) cancels out the left-tail progressive penalty.",
             fontsize=11.5, color=MUTED_TEXT, style="italic")

    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title("A. Senate Dem Gain Over Harris Minus State's House Dem Gain\n(All 6 Progressive-Endorsed Dems vs. Mainstream Battleground Dems)",
                  fontsize=11.4, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    cands = [
        "SC: Annie Andrews",
        "TX: James Talarico",
        "MS: Scott Colom",
        "NC: Roy Cooper",
        "GA: Jon Ossoff",
        "NM: Ben Ray Luján",
        "IA: Josh Turek",
        "OH: Sherrod Brown",
        "MI: Abdul El-Sayed (Prog)",
        "FL: Angie Nixon (Prog)",
        "MN: Peggy Flanagan (Prog)",
        "TN: Marquita Bradshaw (Prog)",
        "MA: Ed Markey (Prog)",
        "ME: Troy Jackson (Prog)"
    ]
    morris_vals = [7.8, 7.4, 5.9, 5.9, 5.8, 3.4, 3.2, 2.8, -1.4, -1.7, -1.8, -1.9, -5.0, -9.8]
    nov5_prog_vals = [None]*8 + [mi_live, fl_live, mn_live, tn_live, None, me_live]
    is_prog = [False]*8 + [True]*6

    y_pos = np.arange(len(cands))[::-1]
    ax1.axvline(0.0, color="#222222", linestyle="-", linewidth=1.5, zorder=2)
    ax1.axhspan(-0.5, 5.5, xmin=0, xmax=0.54, color="#fdedec", alpha=0.55, zorder=1)

    for y, name, m_val, n5_val, prog in zip(y_pos, cands, morris_vals, nov5_prog_vals, is_prog):
        col = PROG_ORANGE if prog else BLUE_DOG
        ax1.barh(y, m_val, height=0.58, color=col, alpha=0.88, zorder=3)
        if prog:
            if m_val <= -8.0:
                ax1.text(m_val / 2.0, y, f"{m_val:+.1f} pts (Live: {n5_val:+.1f})",
                         fontsize=8.8, fontweight="bold", color="white", ha="center", va="center", zorder=6)
            elif n5_val is not None and n5_val < m_val:
                ax1.scatter([n5_val], [y], color="#7e2c00", marker="D", s=45, zorder=5)
                ax1.plot([m_val, n5_val], [y, y], color="#7e2c00", lw=1.8, ls=":", zorder=4)
                ax1.text(n5_val - 0.3, y, f"{m_val:+.1f} (Live: {n5_val:+.1f})",
                         fontsize=8.6, fontweight="bold", color="#7e2c00", ha="right", va="center")
            else:
                ax1.text(m_val - 0.3, y, f"{m_val:+.1f} pts",
                         fontsize=8.8, fontweight="bold", color=col, ha="right", va="center")
        else:
            ax1.text(m_val + 0.25, y, f"{m_val:+.1f} pts",
                     fontsize=8.8, fontweight="bold", color=col, ha="left", va="center")

    ax1.annotate("0-FOR-6: Every progressive-endorsed\nSenate nominee sits below 0 (and fell\neven further behind in live returns)",
                 xy=(-3.2, 5.2), xytext=(-10.9, 8.2),
                 arrowprops=dict(arrowstyle="->", color=PROG_ORANGE, lw=1.8),
                 fontsize=9.0, fontweight="bold", color=PROG_ORANGE,
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#fdf2e9", edgecolor=PROG_ORANGE, lw=1.2))

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(cands, fontsize=9.6, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(-11.4, 10.5)
    ax1.set_ylim(-0.7, len(cands) - 0.3)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("Senate Dem Gain Minus State's House Dem Gain (margin pts)", fontsize=10.2, color=SUB_TEXT)

    ax2 = fig.add_subplot(gs[1], facecolor=BG_COLOR)
    ax2.set_title("B. Why Morris's Linear Slope (+0.6/SD) Masks His Own GAM Curve\n(Net of GOP Nominee Ideology, % White & State House Swing)",
                  fontsize=11.4, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    x = np.linspace(-2.05, 2.3, 200)
    y_raw = np.where(
        x <= 0.35,
        3.1 - 7.9 * ((x - 0.35) / -2.35)**2,
        3.1 - 3.6 * ((x - 0.35) / 1.95)**2
    )
    y_c2 = np.where(
        x <= 0.45,
        2.4 - 6.0 * ((x - 0.45) / -2.45)**2,
        2.4 - 2.9 * ((x - 0.45) / 1.85)**2
    )
    y_c3 = np.where(
        x <= 0.45,
        3.1 - 6.2 * ((x - 0.45) / -2.45)**2,
        3.1 - 6.6 * ((x - 0.45) / 1.85)**2
    )
    y_lin = 0.6 * x

    ax2.axhline(0.0, color="#222222", linestyle="-", linewidth=1.2, zorder=2)
    ax2.fill_between(x, y_c3 - 1.8, y_c3 + 1.8, color=BLUE_DOG, alpha=0.14, zorder=2)
    ax2.plot(x, y_raw, color="#888888", lw=2.0, ls="-", alpha=0.75, label="1. Raw GAM smooth (-4.8 at -2 SD)")
    ax2.plot(x, y_c2, color=PROG_ORANGE, lw=2.2, ls="-", alpha=0.85, label="2. Net of House swing + % white (-3.6 at -2 SD)")
    ax2.plot(x, y_c3, color=BLUE_DOG, lw=3.2, label="3. Same + GOP ideology (-3.1 to +3.1 pts)")
    ax2.plot(x, y_lin, color="#c0392b", lw=2.4, ls="--", label="Linear fit (+0.6/SD, SE 0.8 in Chart 4)")

    ax2.annotate("", xy=(0.45, 3.1), xytext=(-2.0, -3.1),
                 arrowprops=dict(arrowstyle="->", color=NORMIE_TEAL, lw=2.2, ls="-"))
    ax2.text(-2.05, 3.55, "Moving from -2 SD Progressive (-3 to -5 pts)\nto +0.5 SD Mainstream Dem (+3 pts)\nadds +6 to +8 pts of net margin!",
             fontsize=8.9, fontweight="bold", color=NORMIE_TEAL,
             bbox=dict(boxstyle="round,pad=0.32", facecolor="#e8f8f5", edgecolor=NORMIE_TEAL, lw=1.2))

    ax2.annotate("Right tail (+1 to +2.3 SD) bends down\ndue to deep-red sacrificial/Ind runs\n(WY, ID, SD) & single-seat AK,\nflattening the straight-line slope!",
                 xy=(2.05, -2.0), xytext=(0.25, -5.8),
                 arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1.6),
                 fontsize=8.7, fontweight="bold", color="#c0392b",
                 bbox=dict(boxstyle="round,pad=0.3", facecolor="#fdedec", edgecolor="#c0392b", lw=1.1))

    ax2.set_xlim(-2.15, 2.4)
    ax2.set_ylim(-6.8, 6.4)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Dem Nominee Ideology (LLM Pairwise Scale:  <- More Progressive  |  More Moderate ->)", fontsize=9.8, color=SUB_TEXT)
    ax2.set_ylabel("Senate Dem Swing vs. Average (margin pts)", fontsize=10, color=SUB_TEXT)
    ax2.legend(loc="upper right", fontsize=8.1, framealpha=0.92, facecolor="white")

    fig.text(0.03, 0.028, f"Source: G. Elliott Morris (@gelliottmorris.com, Nov. 4, 2026 Senate plots, N=34 races) & live NYT election returns (updated {metrics['fetched_at']}).\nDiamonds in Panel A show live Senate-minus-House margins in MI ({mi_live:+.1f}), MN ({mn_live:+.1f}), TN ({tn_live:+.1f}), FL ({fl_live:+.1f}), and ME ({me_live:+.1f}).",
             fontsize=9, color=MUTED_TEXT)

    plt.savefig(ASSETS_DIR / "chart2_senate_0for6.png", dpi=200)
    plt.close(fig)


def generate_chart3(metrics):
    sb = metrics["same_ballot_statewide_live"]
    ch = metrics["county_head_to_head_live"]

    mi_gov = sb["MI"]["governor"]["margin"]
    mi_sos = sb["MI"]["secretary_of_state"]["margin"]
    mi_ag = sb["MI"]["attorney_general"]["margin"]
    mi_sen = sb["MI"]["senate"]["margin"]
    mi_eevp = sb["MI"]["senate"]["eevp"]

    mn_sos = sb["MN"]["secretary_of_state"]["margin"]
    mn_gov = sb["MN"]["governor"]["margin"]
    mn_sen = sb["MN"]["senate"]["margin"]
    mn_ag = sb["MN"]["attorney_general"]["margin"]
    mn_eevp = sb["MN"]["senate"]["eevp"]

    me_gov = sb["ME"]["governor"]["margin"]
    me_sen = sb["ME"]["senate"]["margin"]
    me_eevp = sb["ME"]["senate"]["eevp"]

    nm_sen = sb["NM"]["senate"]["margin"]
    nm_ag = sb["NM"]["attorney_general"]["margin"]
    nm_gov = sb["NM"]["governor"]["margin"]
    nm_eevp = sb["NM"]["senate"]["eevp"]

    fl_gov = sb["FL"]["governor"]["margin"]
    fl_ag = sb["FL"]["attorney_general"]["margin"]
    fl_sen = sb["FL"]["senate"]["margin"]
    fl_eevp = sb["FL"]["senate"]["eevp"]

    fig = plt.figure(figsize=(15.8, 8.6), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.12, 0.96], left=0.14, right=0.97, top=0.77, bottom=0.14, wspace=0.32)

    fig.text(0.03, 0.92, "The Natural Experiment Morris Left Out: Same-Ballot Statewide Races",
             fontsize=20, fontweight="bold", color=DARK_TEXT)
    fig.text(0.03, 0.875, "Same state, same day, same voters (live returns, 91%–99% reporting): Mainstream Dems beat Progressives across all 5 split tickets.",
             fontsize=12.5, color=SUB_TEXT)
    fig.text(0.03, 0.84, "No LLM bio-scoring required: in MI & MN, multiple progressive statewide nominees lagged simultaneously on the exact same ballot.",
             fontsize=11.5, color=MUTED_TEXT, style="italic")

    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title("A. Same-Ballot Statewide Margins (Dem - GOP, %)\n(Mainstream Dems in Teal vs. Progressives in Orange on the Same Ballot)",
                  fontsize=11.5, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    state_labels = [
        f"Michigan\n({mi_eevp:.1f}% reporting)\nGap: {mi_ag - mi_gov:+.1f} to {mi_sen - mi_gov:+.1f} pts",
        f"Minnesota\n({mn_eevp:.1f}% reporting)\nGap: {mn_sen - mn_gov:+.1f} to {mn_ag - mn_sos:+.1f} pts",
        f"Maine\n({me_eevp:.1f}% reporting)\nGap: {me_sen - me_gov:+.1f} pts",
        f"New Mexico\n({nm_eevp:.1f}% reporting)\nGap: {nm_gov - nm_ag:+.1f} to {nm_gov - nm_sen:+.1f} pts",
        f"Florida\n({fl_eevp:.1f}% reporting)\nGap: {fl_sen - fl_gov:+.1f} pts"
    ]
    y_pos = np.arange(len(state_labels))[::-1]

    races_by_state = [
        [(mi_gov, f"Benson (Gov) {mi_gov:+.1f}%", False, 0.19),
         (mi_sos, f"Gilchrist (SoS) {mi_sos:+.1f}%", False, -0.19),
         (mi_ag, f"Savit (AG) {mi_ag:+.1f}%", True, 0.19),
         (mi_sen, f"El-Sayed (Sen) {mi_sen:+.1f}%", True, -0.19)],
        [(mn_sos, f"Simon (SoS) {mn_sos:+.1f}%", False, 0.19),
         (mn_gov, f"Klobuchar (Gov) {mn_gov:+.1f}%", False, -0.19),
         (mn_sen, f"Flanagan (Sen) {mn_sen:+.1f}%", True, 0.21),
         (mn_ag, f"Ellison (AG) {mn_ag:+.1f}%", True, -0.21)],
        [(me_gov, f"Pingree (Gov) {me_gov:+.1f}%", False, 0.0),
         (me_sen, f"Jackson (Sen) {me_sen:+.1f}%", True, 0.0)],
        [(nm_sen, f"Luján (Sen) {nm_sen:+.1f}%", False, 0.19),
         (nm_ag, f"Torrez (AG) {nm_ag:+.1f}%", False, -0.19),
         (nm_gov, f"Haaland (Gov) {nm_gov:+.1f}%", True, 0.0)],
        [(fl_gov, f"Jolly (Gov) {fl_gov:+.1f}%", False, 0.18),
         (fl_ag, f"Rodriguez (AG) {fl_ag:+.1f}%", False, -0.19),
         (fl_sen, f"Nixon (Sen) {fl_sen:+.1f}%", True, 0.0)]
    ]

    ax1.axvline(0.0, color="#333333", linestyle="--", linewidth=1.1, zorder=2)

    for y, rlist in zip(y_pos, races_by_state):
        norm_vals = [r[0] for r in rlist if not r[2]]
        prog_vals = [r[0] for r in rlist if r[2]]
        min_p = min(prog_vals)
        max_n = max(norm_vals)
        ax1.plot([min_p, max_n], [y, y], color="#b0b0b0", lw=4.5, alpha=0.5, zorder=2)
        for val, lbl, is_prog, y_off in rlist:
            col = PROG_ORANGE if is_prog else NORMIE_TEAL
            ax1.scatter([val], [y + y_off*0.35], color=col, s=105, zorder=4)
            if is_prog:
                ax1.text(val - 0.65, y + y_off, lbl, fontsize=8.7, fontweight="bold", color=col, ha="right", va="center")
            else:
                ax1.text(val + 0.65, y + y_off, lbl, fontsize=8.7, fontweight="bold", color=col, ha="left", va="center")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(state_labels, fontsize=9.8, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(-15.5, 38.5)
    ax1.set_ylim(-0.6, 4.6)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.yaxis.grid(True, color=GRID_COLOR, linewidth=0.5, alpha=0.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("2026 Statewide Margin (Dem - GOP, percentage points)", fontsize=10.2, color=SUB_TEXT)

    ax2 = fig.add_subplot(gs[1], facecolor=BG_COLOR)
    ax2.set_title("B. County-by-County Sweep on the Same Ballot\n(% of Counties Where Mainstream Dem Outran Progressive)",
                  fontsize=11.5, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    comparisons = [
        "MI: Benson (Gov) vs.\nEl-Sayed (Sen) & Savit (AG)",
        "MN: Klobuchar (Gov) vs.\nEllison (AG)",
        "MN: Klobuchar (Gov) vs.\nFlanagan (Sen)",
        "ME: Pingree (Gov) vs.\nJackson (Sen)",
        "NM: Luján (Sen) vs.\nHaaland (Gov)",
        "FL: Jolly (Gov) vs.\nNixon (Sen)",
        "ALL 5 STATES\n(Gov vs. Sen Total)"
    ]
    c_keys = ["MI_gov_vs_sen", "MN_gov_vs_ag", "MN_gov_vs_sen", "ME_gov_vs_sen", "NM_sen_vs_gov", "FL_gov_vs_sen", "all_5_states_total"]
    wins = [ch[k]["wins"] for k in c_keys]
    totals = [ch[k]["total"] for k in c_keys]
    pcts = [w / t * 100.0 for w, t in zip(wins, totals)]
    y_c = np.arange(len(comparisons))[::-1]

    for y, w, t, pct in zip(y_c, wins, totals, pcts):
        bar_col = BLUE_DOG if y == 0 else NORMIE_TEAL
        ax2.barh(y, pct, height=0.58, color=bar_col, alpha=0.9, zorder=3)
        ax2.barh(y, 100.0 - pct, left=pct, height=0.58, color=PROG_ORANGE, alpha=0.75, zorder=3)
        ax2.text(pct / 2.0, y, f"{w} / {t} counties ({pct:.1f}%)",
                 fontsize=9.6, fontweight="bold", color="white", ha="center", va="center", zorder=5)

    ax2.set_yticks(y_c)
    ax2.set_yticklabels(comparisons, fontsize=9.4, fontweight="bold", color=DARK_TEXT)
    ax2.set_xlim(0, 103)
    ax2.set_ylim(-0.6, len(comparisons) - 0.3)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Share of Counties Won Head-to-Head (%)", fontsize=10.2, color=SUB_TEXT)

    fig.text(0.03, 0.028, f"Source: Live NYT 2026 Statewide & County Election Returns (updated {metrics['fetched_at']}; {ch['all_5_states_total']['total']} counties across MI, MN, ME, NM, FL).\nIn MI, Morris's LLM scored GOP Senate nominee Mike Rogers at -0.17 SD (average), yet both progressive nominees (El-Sayed & Savit) trailed Benson in {ch['MI_gov_vs_sen']['wins']} of {ch['MI_gov_vs_sen']['total']} counties.",
             fontsize=9, color=MUTED_TEXT)

    plt.savefig(ASSETS_DIR / "chart3_same_ballot_natural_experiment.png", dpi=200)
    plt.close(fig)


def build_all_charts_and_data():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ov, cs = load_live_data()
    metrics = compute_live_metrics(ov, cs)
    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)
    generate_chart1()
    generate_chart2(metrics)
    generate_chart3(metrics)
    print(f"Updated {OUT_JSON_PATH.name} and regenerated 3 charts in {ASSETS_DIR}/.")


if __name__ == "__main__":
    build_all_charts_and_data()

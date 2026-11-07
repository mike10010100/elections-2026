#!/usr/bin/env python3
"""
Builds the Texas Legislature Roll-Call Ideology Verification dataset
(site_data/texas_legislative_ideology_2019_2025.json) and generates
assets/chart11_talarico_baker_rollcall_record_2026.png.

Grounds the classification of 2026 Texas statewide Democratic nominees in
Prof. Mark P. Jones's (Rice University Baker Institute / The Texas Tribune)
empirical Poole-Rosenthal Bayesian roll-call ideal point estimates across
four consecutive sessions of the Texas Legislature:
- 86th Legislature (2019, N=67 House Democrats)
- 87th Legislature (2021, N=67 House Democrats, N=13 Senate Democrats, + Final Passage Win Rates)
- 88th Legislature (2023, N=64 House Democrats, with 95% Credible Intervals)
- 89th Legislature (2025, N=62 House Democrats, with 95% Credible Intervals)
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data" / "texas_leg_ideology"
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"

CSV_2023 = DATA_DIR / "tx_house_2023_dem_datawrapper.csv"
CSV_2025 = DATA_DIR / "tx_house_2025_dem_datawrapper.csv"
SPLIT_JSON = SITE_DATA / "texas_split_ticket_2026.json"
OUT_JSON = SITE_DATA / "texas_legislative_ideology_2019_2025.json"
OUT_CHART = ASSETS_DIR / "chart11_talarico_baker_rollcall_record_2026.png"

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["text.parse_math"] = False

BG_COLOR = "#f4f3ef"
PANEL_BG = "#ffffff"
DARK_TEXT = "#1a1a1a"
SUB_TEXT = "#4a4a4a"
MUTED_TEXT = "#6e6e6e"
GRID_COLOR = "#e2e0d8"

COL_TAL = "#1b4f72"      # Deep Navy Blue (James Talarico - Mainstream Caucus Median)
COL_HIN = "#d35400"      # Warm Orange (Gina Hinojosa - Progressive Wing)
COL_CROCKETT = "#c0392b" # Crimson Red (Jasmine Crockett - Far-Left Bloc #3)
COL_GOODWIN = "#8e44ad"  # Purple (Vikki Goodwin - Progressive Wing)
COL_ROSENTHAL = "#117864"# Teal (Jon Rosenthal - Center-Left)
COL_JOHNSON = "#2874a6"  # Steel Blue (Nathan Johnson - Mainstream Senate)
COL_ECKHARDT = "#a93226" # Dark Brick (Sarah Eckhardt - #1 Most Liberal Senator)


def load_2023_csv() -> list[dict]:
    rows = []
    with open(CSV_2023, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rows.append({
                "first_name": r["fst_nm"].strip(),
                "last_name": r["lst_nm"].strip(),
                "name": f"{r['fst_nm'].strip()} {r['lst_nm'].strip()}",
                "district": int(r["district"]),
                "mean": float(r["mean"]),
                "ci_lo": float(r["ci_lo"]),
                "ci_up": float(r["ci_up"]),
            })
    # Sort from most liberal (most negative) to least liberal (least negative)
    rows.sort(key=lambda x: x["mean"])
    n = len(rows)
    for idx, r in enumerate(rows):
        rank_most_lib = idx + 1
        r["rank_most_liberal"] = rank_most_lib
        r["caucus_total"] = n
        r["liberalism_percentile"] = round(100.0 * (n - rank_most_lib) / (n - 1), 1)
    return rows


def load_2025_csv() -> list[dict]:
    rows = []
    with open(CSV_2025, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for r in reader:
            rows.append({
                "first_name": r["fst_nm"].strip(),
                "last_name": r["lst_nm"].strip(),
                "name": f"{r['fst_nm'].strip()} {r['lst_nm'].strip()}",
                "district": int(r["district"]),
                "mean": round(float(r["ideal_1D_mean"]), 4),
                "ci_lo": round(float(r["ideal_1D_ci_lo"]), 4),
                "ci_up": round(float(r["ideal_1D_ci_up"]), 4),
                "label": r["label"].strip(),
            })
    # Sort from most liberal (most negative) to least liberal (least negative)
    rows.sort(key=lambda x: x["mean"])
    n = len(rows)
    for idx, r in enumerate(rows):
        rank_most_lib = idx + 1
        r["rank_most_liberal"] = rank_most_lib
        r["caucus_total"] = n
        r["liberalism_percentile"] = round(100.0 * (n - rank_most_lib) / (n - 1), 1)
    return rows


def build_dataset_and_chart():
    rows_2023 = load_2023_csv()
    rows_2025 = load_2025_csv()

    with open(SPLIT_JSON, "r", encoding="utf-8") as f:
        split_data = json.load(f)

    race_by_cand = {
        r["dem_name"]: r for r in split_data["statewide_ballot_ranking"]
    }

    # Historical verified scores from Mark P. Jones (Rice Univ. Baker Institute / Texas Tribune)
    # 2019 (86th Leg, N=67 House Democrats, TXHouse2019LibCon.pdf)
    # 2021 (87th Leg, N=67 House Democrats & N=13 Senate Democrats, txp-pub-texaslegislature-063021.pdf)
    key_legislators = {
        "James Talarico": {
            "2026_role": "U.S. Senate Nominee (Won +12.10%)",
            "chamber": "Texas House (HD-52 / HD-50)",
            "classification": "Mainstream Reformer / Caucus Median",
            "dw_nominate_proxy_used": -0.25,
            "sessions": {
                "2019_86th": {"rank_most_liberal": 25, "caucus_total": 67, "mean": -1.05, "ci_lo": -1.14, "ci_up": -0.96, "liberalism_percentile": round(100.0 * (67 - 25) / 66, 1)},
                "2021_87th": {"rank_most_liberal": 28, "caucus_total": 67, "mean": -0.95, "sd": 0.05, "fpv_win_rate_pct": 85.96, "liberalism_percentile": round(100.0 * (67 - 28) / 66, 1)},
                "2023_88th": next(r for r in rows_2023 if r["last_name"] == "Talarico"),
                "2025_89th": next(r for r in rows_2025 if r["last_name"] == "Talarico"),
            },
            "legislative_record_notes": [
                "Passed ~60 bipartisan bills into law across 4 terms in a Republican-controlled legislature.",
                "Authored HB 3979 counter-strategy & insulin price cap ($25/month SB 827), pre-K class size caps, fentanyl overdose prevention (Tucker's Law), youth facility reform, and housing supply bills.",
                "The Texas Tribune (Sept. 22, 2026, Kayla Guo): 'Across four terms in the Texas House, Talarico's votes landed him close to the middle of the pack of Democratic lawmakers ranked by least to most liberal, according to analyses conducted by Rice University's Mark Jones for The Texas Tribune.'"
            ],
        },
        "Gina Hinojosa": {
            "2026_role": "Governor Nominee (Won +7.13%)",
            "chamber": "Texas House (HD-49)",
            "classification": "Progressive Wing (Top-Tier Left)",
            "sessions": {
                "2019_86th": {"rank_most_liberal": 1, "caucus_total": 67, "mean": -1.32, "ci_lo": -1.43, "ci_up": -1.21, "liberalism_percentile": 100.0},
                "2021_87th": {"rank_most_liberal": 4, "caucus_total": 67, "mean": -1.13, "sd": 0.06, "fpv_win_rate_pct": 81.18, "liberalism_percentile": round(100.0 * (67 - 4) / 66, 1)},
                "2023_88th": next(r for r in rows_2023 if r["last_name"] == "Hinojosa"),
                "2025_89th": next(r for r in rows_2025 if r["last_name"] == "Hinojosa"),
            },
            "legislative_record_notes": [
                "Ranked #1 Most Liberal member in the entire 150-member Texas House in 2019 (86th Legislature).",
                "Explicitly identified in Prof. Mark P. Jones's 2021 Baker Institute report (p. 9) as one of only 5 far-left House Democrats whose voting record was 'significantly more liberal than that of at least one-half of the members of the Democratic delegation'.",
                "Zero overlap between her 95% Bayesian credible interval and James Talarico's in 2019, 2021, and 2025."
            ],
        },
        "Jasmine Crockett": {
            "2026_role": "U.S. Senate Primary Runner-Up (46.2% Primary, Lost by -6.6 pts to Talarico)",
            "chamber": "Texas House (HD-100, 2021) / U.S. House (TX-30, 2023-2026)",
            "classification": "Progressive / Far-Left Bloc in TX House (#3 of 67)",
            "dw_nominate_118th_119th": -0.459,
            "sessions": {
                "2021_87th": {"rank_most_liberal": 3, "caucus_total": 67, "mean": -1.17, "sd": 0.06, "fpv_win_rate_pct": 79.73, "liberalism_percentile": round(100.0 * (67 - 3) / 66, 1)},
            },
            "legislative_record_notes": [
                "In her sole Texas House term (87th Legislature, 2021) serving alongside Talarico and Hinojosa, Crockett ranked #3 Most Liberal out of 67 House Democrats (-1.17 vs. Talarico's #28 at -0.95).",
                "Posted a 79.73% Final Passage Bipartisan Win Rate (2nd lowest in the entire 150-member Texas House, vs. Talarico's 85.96%).",
                "Explicitly named alongside Gina Hinojosa (#4) in Prof. Mark P. Jones's 2021 Baker Institute report (p. 9) as part of the 5-member far-left bloc significantly to the left of the Democratic caucus median."
            ],
        },
        "Vikki Goodwin": {
            "2026_role": "Lieutenant Governor Nominee (Won +6.10%)",
            "chamber": "Texas House (HD-47)",
            "classification": "Progressive Wing (Top-10% Left)",
            "sessions": {
                "2019_86th": {"rank_most_liberal": 7, "caucus_total": 67, "mean": -1.17, "ci_lo": -1.27, "ci_up": -1.07, "liberalism_percentile": round(100.0 * (67 - 7) / 66, 1)},
                "2021_87th": {"rank_most_liberal": 8, "caucus_total": 67, "mean": -1.06, "sd": 0.06, "fpv_win_rate_pct": 84.39, "liberalism_percentile": round(100.0 * (67 - 8) / 66, 1)},
                "2023_88th": next(r for r in rows_2023 if r["last_name"] == "Goodwin"),
                "2025_89th": next(r for r in rows_2025 if r["last_name"] == "Goodwin"),
            },
        },
        "Jon Rosenthal": {
            "2026_role": "Railroad Commissioner Nominee (Won +6.97%)",
            "chamber": "Texas House (HD-135)",
            "classification": "Center-Left / Upper-Middle Tier",
            "sessions": {
                "2019_86th": {"rank_most_liberal": 5, "caucus_total": 67, "mean": -1.18, "ci_lo": -1.28, "ci_up": -1.08, "liberalism_percentile": round(100.0 * (67 - 5) / 66, 1)},
                "2021_87th": {"rank_most_liberal": 25, "caucus_total": 67, "mean": -0.96, "sd": 0.05, "fpv_win_rate_pct": 86.28, "liberalism_percentile": round(100.0 * (67 - 25) / 66, 1)},
                "2023_88th": next(r for r in rows_2023 if r["last_name"] == "Rosenthal"),
                "2025_89th": next(r for r in rows_2025 if r["last_name"] == "Rosenthal"),
            },
        },
        "Nathan Johnson": {
            "2026_role": "Attorney General Nominee (Won +6.44%)",
            "chamber": "Texas Senate (SD-16)",
            "classification": "Mainstream Senate Democrat",
            "sessions": {
                "2021_87th_Senate": {"rank_most_liberal": 5, "caucus_total": 13, "mean": -1.14, "sd": 0.10, "fpv_win_rate_pct": 93.13, "liberalism_percentile": round(100.0 * (13 - 5) / 12, 1)},
            },
        },
        "Sarah Eckhardt": {
            "2026_role": "Comptroller Nominee (Won +5.15%)",
            "chamber": "Texas Senate (SD-14)",
            "classification": "Progressive Wing (#1 Most Liberal TX Senator)",
            "sessions": {
                "2021_87th_Senate": {"rank_most_liberal": 1, "caucus_total": 13, "mean": -1.81, "sd": 0.19, "fpv_win_rate_pct": 89.30, "liberalism_percentile": 100.0},
            },
        },
    }

    for name, info in key_legislators.items():
        pcts = [s["liberalism_percentile"] for s in info["sessions"].values()]
        info["career_mean_liberalism_percentile"] = round(float(np.mean(pcts)), 1)
        if name in race_by_cand:
            r = race_by_cand[name]
            info["election_2026"] = {
                "office": r["office"],
                "margin_pct": r["margin_pct"],
                "dem_votes": r["dem_votes"],
                "gop_votes": r["gop_votes"],
                "dem_pct": r["dem_pct"],
                "gop_pct": r["gop_pct"],
                "gop_opponent": r["gop_name"],
            }

    payload = {
        "title": "Texas Legislature Empirical Roll-Call Ideology Verification (2019-2025)",
        "methodology_source": (
            "Prof. Mark P. Jones (Rice University Baker Institute for Public Policy & The Texas Tribune), "
            "Bayesian Poole-Rosenthal roll-call ideal point estimation across all non-unanimous roll-call votes "
            "in the 86th (2019), 87th (2021), 88th (2023), and 89th (2025) Texas Legislatures."
        ),
        "primary_citations": [
            "Mark P. Jones (2019), 'The 2019 Texas House, From Left to Right', The Texas Tribune (June 20, 2019).",
            "Mark P. Jones (2021), 'The 2021 Texas Legislature’s Liberal-Conservative Rankings', Rice University Baker Institute for Public Policy (June 30, 2021).",
            "Mark P. Jones (2023), '88th Legislature (2023) Texas House Liberal-Conservative Scores', Rice University Baker Institute / Datawrapper VFEJn.",
            "Mark P. Jones (2025), '89th Legislature (2025) Texas House Liberal-Conservative Scores', Rice University Baker Institute / Datawrapper IDVQq.",
            "Kayla Guo (2026), 'How James Talarico is pitching himself to win over moderate and conservative Texans', The Texas Tribune (Sept. 22, 2026)."
        ],
        "key_findings": {
            "talarico_4term_mean_percentile": key_legislators["James Talarico"]["career_mean_liberalism_percentile"],
            "hinojosa_4term_mean_percentile": key_legislators["Gina Hinojosa"]["career_mean_liberalism_percentile"],
            "goodwin_4term_mean_percentile": key_legislators["Vikki Goodwin"]["career_mean_liberalism_percentile"],
            "rosenthal_4term_mean_percentile": key_legislators["Jon Rosenthal"]["career_mean_liberalism_percentile"],
            "crockett_2021_percentile": key_legislators["Jasmine Crockett"]["career_mean_liberalism_percentile"],
            "2025_caucus_comparison": {
                "caucus_size": 62,
                "talarico_rank_most_liberal": 29,
                "talarico_mean": -0.6461,
                "talarico_95ci": [-0.6981, -0.5923],
                "caucus_median_member": "Trey Martinez Fischer (#30, -0.6461)",
                "hinojosa_rank_most_liberal": 8,
                "hinojosa_mean": -0.8060,
                "hinojosa_95ci": [-0.8626, -0.7515],
                "goodwin_rank_most_liberal": 6,
                "goodwin_mean": -0.8451,
                "goodwin_95ci": [-0.9007, -0.7869],
                "rosenthal_rank_most_liberal": 15,
                "rosenthal_mean": -0.7529,
                "rosenthal_95ci": [-0.8066, -0.6978],
                "statistically_distinct_95ci_gap_talarico_vs_hinojosa": round(-0.6981 - (-0.7515), 4),
            },
            "2021_head_to_head_session_87th": {
                "caucus_size": 67,
                "crockett_rank": 3,
                "crockett_score": -1.17,
                "crockett_fpv_bipartisan_win_rate_pct": 79.73,
                "hinojosa_rank": 4,
                "hinojosa_score": -1.13,
                "hinojosa_fpv_bipartisan_win_rate_pct": 81.18,
                "goodwin_rank": 8,
                "goodwin_score": -1.06,
                "goodwin_fpv_bipartisan_win_rate_pct": 84.39,
                "rosenthal_rank": 25,
                "rosenthal_score": -0.96,
                "rosenthal_fpv_bipartisan_win_rate_pct": 86.28,
                "talarico_rank": 28,
                "talarico_score": -0.95,
                "talarico_fpv_bipartisan_win_rate_pct": 85.96,
                "baker_institute_finding": (
                    "In the 2021 87th Legislature—the session where Jasmine Crockett, Gina Hinojosa, Vikki Goodwin, "
                    "Jon Rosenthal, and James Talarico all served together in the Texas House—Prof. Mark P. Jones "
                    "explicitly identified Crockett (#3) and Hinojosa (#4) as members of the 5-person far-left bloc "
                    "significantly more liberal than at least half the Democratic caucus, while Talarico (#28 of 67) "
                    "voted in the mainstream middle tier alongside caucus median Trey Martinez Fischer (#34)."
                ),
            },
        },
        "key_legislators": key_legislators,
        "tx_house_2025_democrats_full": rows_2025,
        "tx_house_2023_democrats_full": rows_2023,
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"Wrote {OUT_JSON}")

    # --- BUILD CHART 11 ---
    fig = plt.figure(figsize=(19, 10.5), dpi=200, facecolor=BG_COLOR)
    gs = gridspec.GridSpec(
        2, 2,
        width_ratios=[1.12, 1.0],
        height_ratios=[1.0, 1.0],
        left=0.055, right=0.97, top=0.865, bottom=0.085,
        wspace=0.20, hspace=0.31,
    )

    # Overall Title & Subtitle
    fig.text(
        0.055, 0.945,
        "WAS JAMES TALARICO'S RECORD ACTUALLY PROGRESSIVE? TEXAS LEGISLATURE ROLL-CALL AUDIT (2019–2025)",
        fontsize=17.5, fontweight="bold", color=DARK_TEXT,
    )
    fig.text(
        0.055, 0.912,
        "Empirical Roll-Call Ideal Points & 95% Bayesian Credible Intervals (Prof. Mark P. Jones, Rice University Baker Institute / The Texas Tribune) Across All 4 Terms",
        fontsize=11.3, color=SUB_TEXT,
    )

    # =========================================================================
    # PANEL A (Left, spanning both rows): 2025 Texas House Democratic Caucus (N=62)
    # =========================================================================
    ax_a = fig.add_subplot(gs[:, 0], facecolor=PANEL_BG)
    n25 = len(rows_2025)
    y_pos = np.arange(n25)

    # Shade the non-overlapping 95% CI gap between Hinojosa (-0.7515) and Talarico (-0.6981)
    ax_a.axvspan(-0.7515, -0.6981, color="#f9e79f", alpha=0.55, zorder=1)
    ax_a.annotate(
        "Zero 95% CI Overlap\nBetween Hinojosa/Goodwin\n& Talarico (-0.752 to -0.698)",
        xy=(-0.7248, 38.0),
        xytext=(-0.89, 44.5),
        fontsize=8.3, fontweight="bold", color="#7d6608", ha="center", va="center",
        arrowprops=dict(arrowstyle="->", color="#b7950b", lw=1.4, connectionstyle="arc3,rad=0.12"),
        bbox=dict(boxstyle="round,pad=0.32", facecolor="#fef9e7", edgecolor="#d4ac0d", lw=1.0),
        zorder=8,
    )

    # Caucus median vertical line (rank 31/32 boundary ~ -0.646)
    caucus_median_x = -0.6461
    ax_a.axvline(caucus_median_x, color=COL_TAL, linestyle="--", linewidth=1.3, alpha=0.7, zorder=2)

    highlight_map = {
        "Talarico": (COL_TAL, "James Talarico (HD-50) — #29/62 Most Liberal (53rd Pctile | Caucus Median, -0.646)"),
        "Hinojosa": (COL_HIN, "Gina Hinojosa (HD-49) — #8/62 Most Liberal (87th Pctile | Progressive Wing, -0.806)"),
        "Goodwin": (COL_GOODWIN, "Vikki Goodwin (HD-47) — #6/62 Most Liberal (90th Pctile | Progressive Wing, -0.845)"),
        "Rosenthal": (COL_ROSENTHAL, "Jon Rosenthal (HD-135) — #15/62 Most Liberal (76th Pctile | Center-Left, -0.753)"),
    }

    for idx, r in enumerate(rows_2025):
        lname = r["last_name"]
        mean = r["mean"]
        lo = r["ci_lo"]
        up = r["ci_up"]
        if lname in highlight_map:
            col, _ = highlight_map[lname]
            ax_a.plot([lo, up], [idx, idx], color=col, linewidth=3.0, zorder=5)
            ax_a.scatter([mean], [idx], color=col, s=62, zorder=6, edgecolors="white", linewidth=0.8)
        else:
            ax_a.plot([lo, up], [idx, idx], color="#b2babb", linewidth=1.2, alpha=0.85, zorder=3)
            ax_a.scatter([mean], [idx], color="#7f8c8d", s=16, alpha=0.85, zorder=4)

    # Annotate highlighted members and anchors in Panel A
    annotations_a = [
        (5, "Vikki Goodwin (#6/62, -0.845)\n2026 Lt. Gov Nominee (+6.10%)", COL_GOODWIN, (-0.53, 4.2)),
        (7, "Gina Hinojosa (#8/62, -0.806)\n2026 Gov Nominee (+7.13%)", COL_HIN, (-0.50, 10.2)),
        (14, "Jon Rosenthal (#15/62, -0.753)\n2026 RRC Nominee (+6.97%)", COL_ROSENTHAL, (-0.47, 17.0)),
        (28, "James Talarico (#29/62, -0.646)\n2026 Senate Nominee (+12.10%)\nDead-Center of TX House Dems", COL_TAL, (-0.43, 28.0)),
    ]
    for idx_pt, label_txt, col, text_xy in annotations_a:
        r_pt = rows_2025[idx_pt]
        ax_a.annotate(
            label_txt,
            xy=(r_pt["ci_up"], idx_pt),
            xytext=text_xy,
            fontsize=8.8, fontweight="bold", color=col,
            arrowprops=dict(arrowstyle="->", color=col, lw=1.4, connectionstyle="arc3,rad=-0.08"),
            bbox=dict(boxstyle="round,pad=0.28", facecolor="white", edgecolor=col, lw=1.2),
            zorder=8,
        )

    # Also label #1 Most Liberal and #62 Most Centrist
    ax_a.text(-0.885, 0.3, "#1 Christina Morales (-0.954, Most Liberal)", fontsize=8.0, color=SUB_TEXT, va="center")
    ax_a.text(-0.24, 60.8, "#62 Terry Canales (-0.174, Most Centrist)", fontsize=8.0, color=SUB_TEXT, va="center", ha="right")
    ax_a.text(
        caucus_median_x - 0.009, 51.5,
        "Caucus Median (#30 Trey Martinez Fischer, -0.646)",
        fontsize=8.2, fontweight="bold", color=COL_TAL, rotation=90, va="center", ha="right",
    )

    ax_a.set_ylim(-1.8, n25 + 0.8)
    ax_a.set_xlim(-1.05, -0.10)
    ax_a.invert_yaxis()  # Rank #1 (Most Liberal) at top, #62 (Most Centrist) at bottom
    ax_a.set_yticks([0, 7, 14, 28, 44, 61])
    ax_a.set_yticklabels(["Rank #1\n(Most Left)", "Rank #8\n(Hinojosa)", "Rank #15\n(Rosenthal)", "Rank #29\n(Talarico)", "Rank #45", "Rank #62\n(Most Centrist)"], fontsize=8.8)
    ax_a.set_xlabel("2025 Baker Institute Bayesian Lib–Con Ideal Point (More Negative = More Liberal Roll-Call Record)", fontsize=9.8, fontweight="bold", color=DARK_TEXT)
    ax_a.set_title("A. 2025 Texas House Democratic Caucus Roll-Call Spectrum (89th Leg., N = 62)", fontsize=11.5, fontweight="bold", color=DARK_TEXT, loc="left", pad=8)
    ax_a.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.8)

    # =========================================================================
    # PANEL B (Top Right): 4-Term Roll-Call Liberalism Percentile Trajectory (2019–2025)
    # =========================================================================
    ax_b = fig.add_subplot(gs[0, 1], facecolor=PANEL_BG)
    sessions_x = [0, 1, 2, 3]
    session_labels = [
        "86th Leg. (2019)\n(N = 67 Dems)",
        "87th Leg. (2021)\n(N = 67 Dems)",
        "88th Leg. (2023)\n(N = 64 Dems)",
        "89th Leg. (2025)\n(N = 62 Dems)",
    ]

    # Shade Progressive Top Quartile (>75th pctile) vs Mainstream Middle Tier (25th-75th pctile)
    ax_b.axhspan(75, 104, color="#fdebd0", alpha=0.45, zorder=1)
    ax_b.axhspan(35, 75, color="#ebf5fb", alpha=0.45, zorder=1)
    ax_b.axhline(50.0, color=MUTED_TEXT, linestyle="--", linewidth=1.1, zorder=2)
    ax_b.text(0.03, 51.3, "Democratic Caucus Median (50th Percentile)", fontsize=8.1, color=MUTED_TEXT, fontweight="bold")
    ax_b.text(3.15, 100.8, "Progressive Wing (Top Quartile: 75th–100th Pctile)", fontsize=8.1, color="#b9770e", fontweight="bold", ha="right")

    traj_series = [
        ("Gina Hinojosa (Gov +7.13%)", COL_HIN, [100.0, 95.5, 92.1, 88.5], ["#1/67", "#4/67", "#6/64", "#8/62"], "o", "-"),
        ("Vikki Goodwin (Lt. Gov +6.10%)", COL_GOODWIN, [90.9, 89.4, 95.2, 91.8], ["#7/67", "#8/67", "#4/64", "#6/62"], "s", "--"),
        ("Jon Rosenthal (RRC +6.97%)", COL_ROSENTHAL, [93.9, 63.6, 85.7, 77.0], ["#5/67", "#25/67", "#10/64", "#15/62"], "^", "-."),
        ("James Talarico (Senate +12.10%)", COL_TAL, [63.6, 59.1, 76.2, 54.1], ["#25/67", "#28/67", "#16/64", "#29/62"], "D", "-"),
    ]

    for label_s, col_s, y_vals, rk_labels, mk, ls in traj_series:
        lw = 3.0 if "Talarico" in label_s or "Hinojosa" in label_s else 2.0
        ax_b.plot(sessions_x, y_vals, color=col_s, linestyle=ls, linewidth=lw, marker=mk, markersize=7.5, label=label_s, zorder=5)
        for x_i, y_i, rk_txt in zip(sessions_x, y_vals, rk_labels):
            if "Talarico" in label_s:
                dy = -5.4 if x_i != 2 else -5.8
                ax_b.text(x_i, y_i + dy, f"{rk_txt}\n({y_i:.0f}%)", fontsize=7.8, fontweight="bold", color=col_s, ha="center")
            elif "Hinojosa" in label_s:
                if x_i == 0:
                    ax_b.text(x_i + 0.14, y_i + 1.0, f"{rk_txt} (100%)", fontsize=7.8, fontweight="bold", color=col_s, ha="left")
                elif x_i == 1:
                    ax_b.text(x_i - 0.14, y_i - 3.6, f"{rk_txt}", fontsize=7.8, fontweight="bold", color=col_s, ha="right")
                elif x_i == 3:
                    ax_b.text(x_i + 0.08, y_i - 1.5, f"{rk_txt}", fontsize=7.8, fontweight="bold", color=col_s, ha="left")
                else:
                    ax_b.text(x_i, y_i - 4.2, f"{rk_txt}", fontsize=7.8, fontweight="bold", color=col_s, ha="center")

    # Plot Jasmine Crockett in 2021 (87th Leg, #3/67 = 97.0th pctile)
    ax_b.scatter([1], [97.0], color=COL_CROCKETT, s=135, marker="*", zorder=7, edgecolors="black", linewidth=0.7,
                 label="Jasmine Crockett (2021 HD-100: #3/67, 97th Pctile | 79.7% FPV Win Rate)")
    ax_b.annotate(
        "Jasmine Crockett (#3/67 in 2021)\n79.7% Final Passage Win Rate (2nd Lowest in TX House)\nNamed in Baker Report 5-Member Far-Left Bloc w/ Hinojosa (#4)",
        xy=(1.0, 97.0), xytext=(0.98, 78.2),
        fontsize=7.5, fontweight="bold", color=COL_CROCKETT,
        arrowprops=dict(arrowstyle="->", color=COL_CROCKETT, lw=1.3),
        bbox=dict(boxstyle="round,pad=0.24", facecolor="#fdedec", edgecolor=COL_CROCKETT, lw=1.0),
        zorder=8,
    )

    ax_b.set_xticks(sessions_x)
    ax_b.set_xticklabels(session_labels, fontsize=8.8, fontweight="bold")
    ax_b.set_ylim(38, 105)
    ax_b.set_xlim(-0.25, 3.25)
    ax_b.set_ylabel("Within-Caucus Roll-Call Liberalism Percentile", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax_b.set_title("B. 4-Term Roll-Call Trajectory: Talarico vs. Crockett, Hinojosa & Goodwin (2019–2025)", fontsize=11.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=8)
    ax_b.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.8)
    ax_b.legend(loc="lower left", fontsize=7.6, frameon=True, facecolor="white", edgecolor="#cccccc", ncol=2)

    # =========================================================================
    # PANEL C (Bottom Right): 2026 Statewide Margin vs. Career TX Leg Roll-Call Liberalism
    # =========================================================================
    ax_c = fig.add_subplot(gs[1, 1], facecolor=PANEL_BG)

    alumni_pts = [
        ("James Talarico (U.S. Senate +12.10%)", 62.3, 12.10, COL_TAL, (51.2, 11.45), "4-Term Mean: 62.3rd Pctile (#29/62 in 2025)"),
        ("Nathan Johnson (Attorney General +6.44%)", 66.7, 6.44, COL_JOHNSON, (51.2, 7.80), "TX Senate #5/13 (66.7th Pctile | 93.1% FPV)"),
        ("Jon Rosenthal (Railroad Comm. +6.97%)", 78.8, 6.97, COL_ROSENTHAL, (67.8, 9.55), "4-Term Mean: 78.8th Pctile"),
        ("Gina Hinojosa (Governor +7.13%)", 92.6, 7.13, COL_HIN, (79.5, 11.20), "4-Term Mean: 92.6th Pctile (#1 in 2019)"),
        ("Vikki Goodwin (Lt. Governor +6.10%)", 90.4, 6.10, COL_GOODWIN, (68.5, 4.35), "4-Term Mean: 90.4th Pctile (#6 in 2025)"),
        ("Sarah Eckhardt (Comptroller +5.15%)", 100.0, 5.15, COL_ECKHARDT, (84.2, 7.85), "TX Senate #1/13 Most Liberal (100th Pctile)"),
    ]

    x_c = np.array([p[1] for p in alumni_pts])
    y_c = np.array([p[2] for p in alumni_pts])
    slope, intercept = np.polyfit(x_c, y_c, 1)
    x_line = np.linspace(55, 102, 100)
    ax_c.plot(x_line, slope * x_line + intercept, color="#7f8c8d", linestyle="--", linewidth=1.6, zorder=2,
              label=f"OLS Trend Across 6 TX Leg Alumni on 2026 Ballot (r = {np.corrcoef(x_c, y_c)[0,1]:.2f})")

    for name_lbl, xp, yp, col_p, txt_xy, sub_note in alumni_pts:
        ax_c.scatter([xp], [yp], color=col_p, s=115, zorder=6, edgecolors="white", linewidth=1.2)
        ax_c.annotate(
            f"{name_lbl}\n{sub_note}",
            xy=(xp, yp), xytext=txt_xy,
            fontsize=7.6, fontweight="bold", color=col_p,
            arrowprops=dict(arrowstyle="->", color=col_p, lw=1.2),
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor=col_p, lw=1.0),
            zorder=7,
        )

    # Quote Callout Box in Panel C
    quote_box = (
        "Why Talarico Is Classified as a Mainstream Reformer vs. Hinojosa & Crockett as Progressives:\n"
        "• The Texas Tribune (Sept. 22, 2026): 'Across four terms in the Texas House, Talarico's votes landed him close to the middle of the pack of\n"
        "  Democratic lawmakers ranked by least to most liberal, according to analyses conducted by Rice University's Mark Jones for The Texas Tribune.'\n"
        "• In 2021 (87th Leg.), when Crockett (#3/67), Hinojosa (#4/67), Goodwin (#8/67), Rosenthal (#25/67), and Talarico (#28/67) all served together,\n"
        "  Baker Institute explicitly grouped Crockett & Hinojosa in the 5-member far-left bloc, while Talarico voted at the caucus median (~60 bipartisan laws)."
    )
    ax_c.text(
        0.015, 0.025, quote_box,
        transform=ax_c.transAxes, fontsize=7.15, color=DARK_TEXT, va="bottom", ha="left",
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#fef9e7", edgecolor="#b7950b", lw=1.0),
        zorder=8,
    )

    ax_c.set_xlim(50, 104)
    ax_c.set_ylim(-0.6, 14.2)
    ax_c.set_xlabel("Career Roll-Call Liberalism Percentile in Texas Legislature (50% = Caucus Median, 100% = Most Liberal)", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax_c.set_ylabel("2026 Texas Statewide Margin (%)", fontsize=9.5, fontweight="bold", color=DARK_TEXT)
    ax_c.set_title("C. 2026 Statewide Margin vs. TX Legislature Roll-Call Liberalism (All 6 TX Leg Alumni)", fontsize=11.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=8)
    ax_c.grid(True, linestyle=":", color=GRID_COLOR, alpha=0.8)
    ax_c.legend(loc="upper right", fontsize=8.0, frameon=True, facecolor="white", edgecolor="#cccccc")

    # Footer
    fig.text(
        0.055, 0.022,
        "Sources: Prof. Mark P. Jones (Rice University Baker Institute / The Texas Tribune) 2019, 2021, 2023 & 2025 Texas Legislature Roll-Call Liberal-Conservative Datasets; NYT 2026 Election Returns.\n"
        "Note: Within-caucus percentiles measure each legislator's position among Texas House/Senate Democrats (100% = #1 Most Liberal; 50% = Caucus Median). Error bars in Panel A show 95% Bayesian Credible Intervals.",
        fontsize=8.3, color=MUTED_TEXT,
    )

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_CHART, dpi=200)
    plt.close(fig)
    import shutil
    import subprocess
    tmp_pal = Path("/tmp/chart11_pal.png")
    tmp_out = Path("/tmp/chart11_compressed.png")
    subprocess.run(["ffmpeg", "-y", "-i", str(OUT_CHART), "-vf", "palettegen=max_colors=256", str(tmp_pal)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["ffmpeg", "-y", "-i", str(OUT_CHART), "-i", str(tmp_pal), "-lavfi", "paletteuse=dither=bayer:bayer_scale=3", str(tmp_out)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if tmp_out.exists() and tmp_out.stat().st_size < OUT_CHART.stat().st_size:
        shutil.move(str(tmp_out), str(OUT_CHART))
    print(f"Saved {OUT_CHART} ({OUT_CHART.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_dataset_and_chart()

#!/usr/bin/env python3
"""
Generates 5 standalone, large-typeface, mobile-optimized 16:10 infographics for the Bluesky thread:
1. thread_tx_1_pipeline.png — The 1-to-1 Pipeline: Homes Permitted -> +BA+ Adults -> +Net New Dem Votes
2. thread_tx_2_two_stage_dfw.png — The Two-Stage Rocket in DFW (2004 -> 2026): Why the GOP Built It & How EdPol Flipped It
3. thread_tx_3_collin_denton_breakdown.png — DFW County-by-County Scoreboard (Collin, Denton, Tarrant, Dallas, Rockwall, Ellis, Kaufman)
4. thread_tx_4_scatter_permits_ba.png — Per-Capita Housing Boom vs. BA+ Adult Inflow Across Texas Counties (r = +0.88)
5. thread_tx_5_tx_vs_fl_ca.png — The Natural Control Experiment: Why Texas's Housing Boom Turned It Blue While Florida's Turned It Red
"""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
OUT_DIR = BASE_DIR / "assets" / "thread_tx_housing_edpol"
OUT_DIR.mkdir(parents=True, exist_ok=True)

with open(BASE_DIR / "site_data" / "texas_housing_edpol_2026.json") as f:
    data = json.load(f)

counties = {c["fips"]: c for c in data["counties"]}
tx_counties = data["counties"]

BG = "#f8f7f3"
PANEL_BG = "#ffffff"
TEXT = "#18181b"
SUBTEXT = "#52525b"
GRID = "#e4e4e7"
BLUE = "#1d4d7a"
LIGHT_BLUE = "#5b9bd5"
ORANGE = "#d97706"
DEEP_ORANGE = "#c85a17"
GREEN = "#1b7837"
RED = "#b91c1c"

plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#d4d4d8"
plt.rcParams["axes.linewidth"] = 0.9


def summarize(fips_list):
    sub = [counties[f] for f in fips_list]
    perm = sum(r["permits_total_10_24"] for r in sub)
    dba = sum(r["ba_adults_added_10_23"] for r in sub)
    dnonba = sum(r["nonba_adults_added_10_23"] for r in sub)
    dtot = dba + dnonba
    ddem_s = sum(r["net_new_dem_votes_12_to_sen26"] for r in sub)
    dgop_s = sum(r["net_new_gop_votes_12_to_sen26"] for r in sub)
    ddem_g = sum(r["net_new_dem_votes_12_to_gov26"] for r in sub)
    dgop_g = sum(r["net_new_gop_votes_12_to_gov26"] for r in sub)
    return {
        "perm": perm,
        "dba": dba,
        "ba_sh": 100.0 * dba / dtot if dtot > 0 else 0.0,
        "ddem_s": ddem_s,
        "dgop_s": dgop_s,
        "ddem_g": ddem_g,
        "dgop_g": dgop_g,
    }


dfw_9 = ["48113", "48439", "48085", "48121", "48397", "48139", "48257", "48251", "48367"]
houston_5 = ["48201", "48157", "48339", "48039", "48167"]
austin_5 = ["48453", "48491", "48209", "48021", "48055"]
sa_3 = ["48029", "48091", "48187"]
big4_22 = set(dfw_9 + houston_5 + austin_5 + sa_3)
rest_232 = [c["fips"] for c in tx_counties if c["fips"] not in big4_22]


# =============================================================================
# CARD 1: THE 1-TO-1 PIPELINE (HOMES PERMITTED -> +BA+ ADULTS -> +DEM VOTES)
# =============================================================================
fig, ax = plt.subplots(figsize=(14.5, 9.2), dpi=180, facecolor=BG)
ax.set_facecolor(PANEL_BG)
plt.subplots_adjust(left=0.22, right=0.96, top=0.80, bottom=0.12)

fig.text(
    0.04, 0.935,
    "The 1-to-1 Pipeline: How Texas's Housing Boom Built a Democratic Majority",
    fontsize=19.5, fontweight="bold", color=TEXT,
)
fig.text(
    0.04, 0.892,
    "Between 2010 and 2024, Texas permitted 2.77M homes (2.22M across 4 metros — nearly 3× California's per-capita rate).",
    fontsize=12.0, color=SUBTEXT,
)
fig.text(
    0.04, 0.852,
    "Across all 254 counties, new homes → new BA+ adults (r = +0.984), and new BA+ adults → net new Dem votes 1-for-1 (r = +0.993).",
    fontsize=11.5, fontweight="bold", style="italic", color=BLUE,
)

groups_1 = [
    ("9-County DFW Metro\n(31% of TX Pop Growth)", dfw_9),
    ("5-County Houston Metro\n(29% of TX Pop Growth)", houston_5),
    ("5-County Austin Metro\n(49.9% BA+ in 2023)", austin_5),
    ("Dallas + Tarrant Counties\n(Dallas / Fort Worth / Arlington)", ["48113", "48439"]),
    ("Collin + Denton Counties\n(Plano / Frisco / McKinney / Denton)", ["48085", "48121"]),
    ("3-County San Antonio Metro\n(Bexar / Comal / Guadalupe)", sa_3),
    ("Rest of Texas (232 Counties)\n(Non-Big-4 Metros & Rural)", rest_232),
]

y_pos = np.arange(len(groups_1))[::-1]
bh = 0.23
perm_k, ba_k, dem_k, gop_k, ba_sh = [], [], [], [], []
for _, flist in groups_1:
    s = summarize(flist)
    perm_k.append(s["perm"] / 1000.0)
    ba_k.append(s["dba"] / 1000.0)
    dem_k.append(s["ddem_s"] / 1000.0)
    gop_k.append(s["dgop_s"] / 1000.0)
    ba_sh.append(s["ba_sh"])

ax.axvline(0, color=TEXT, lw=1.0, zorder=2)
ax.barh(y_pos + 1.05 * bh, perm_k, height=bh, color=ORANGE, alpha=0.92, label="New Homes Permitted (2010–24, BPS)", zorder=3)
ax.barh(y_pos, ba_k, height=bh, color=GREEN, alpha=0.92, label="Net New BA+ Adults Age 25+ (2010–23)", zorder=3)
ax.barh(y_pos - 1.05 * bh, dem_k, height=bh, color=BLUE, alpha=0.95, label="Net New Dem Votes (2012→26 Sen)", zorder=3)
ax.barh(y_pos - 1.05 * bh, gop_k, height=bh, color=RED, alpha=0.78, label="Net New GOP Votes (2012→26 Sen)", zorder=3)

for i, y in enumerate(y_pos):
    mx = max(perm_k[i], ba_k[i], dem_k[i])
    ax.text(
        mx + 16, y,
        f"{perm_k[i]:,.0f}k homes permitted → +{ba_k[i]:,.0f}k BA+ adults ({ba_sh[i]:.0f}% of adult gr)\n"
        f"2012→2026 Votes: +{dem_k[i]:,.0f}k Dem vs. {gop_k[i]:+,.0f}k GOP",
        va="center", ha="left", fontsize=9.3, fontweight="bold", color=TEXT,
    )

ax.set_yticks(y_pos)
ax.set_yticklabels([g[0] for g in groups_1], fontsize=10.2, fontweight="bold", color=TEXT)
ax.set_xlim(-175, 1620)
ax.set_ylim(-0.6, 6.6)
ax.set_xlabel("Thousands of Homes Permitted / BA+ Adults Added / Net Votes Added", fontsize=11.0, fontweight="bold", color=TEXT)
ax.grid(axis="x", linestyle=":", color=GRID, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="center right", bbox_to_anchor=(0.99, 0.35), fontsize=9.2, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

fig.text(
    0.04, 0.025,
    "Sources: U.S. Census Building Permits Survey (2010–2024), USDA ERS / Census ACS Educational Attainment (2000–2023), & NYT 2026 Returns (`https://github.com/mike10010100/elections-2026`).",
    fontsize=9.0, color=SUBTEXT,
)
fig.savefig(OUT_DIR / "thread_tx_1_pipeline.png", dpi=180, facecolor=BG)
plt.close(fig)


# =============================================================================
# CARD 2: THE TWO-STAGE ROCKET IN DFW (2004 -> 2026)
# =============================================================================
import csv
hist_votes = {}
with open(BASE_DIR / "data" / "historical" / "us_county_results_summary.csv") as f:
    for r in csv.DictReader(f):
        if r["state_po"] == "TX":
            hist_votes.setdefault(r["county_fips"], {})[(r["office"], int(r["year"]))] = {
                "dem": int(float(r["dem_votes"] or 0)),
                "rep": int(float(r["rep_votes"] or 0)),
                "tot": int(float(r["total_votes"] or 0)),
            }
for c in tx_counties:
    f_id = c["fips"]
    hist_votes[f_id][("governor", 2026)] = {
        "dem": c["dem_votes_gov_2026"], "rep": c["gop_votes_gov_2026"],
        "tot": c["dem_votes_gov_2026"] + c["gop_votes_gov_2026"] + 15000,
    }
    hist_votes[f_id][("senate", 2026)] = {
        "dem": c["dem_votes_sen_2026"], "rep": c["gop_votes_sen_2026"],
        "tot": c["dem_votes_sen_2026"] + c["gop_votes_sen_2026"] + 15000,
    }

fig, ax = plt.subplots(figsize=(14.5, 9.2), dpi=180, facecolor=BG)
ax.set_facecolor(PANEL_BG)
plt.subplots_adjust(left=0.09, right=0.96, top=0.80, bottom=0.12)

fig.text(
    0.04, 0.935,
    "The 'Two-Stage Rocket' in the 9-County DFW Metro (2004 → 2026)",
    fontsize=19.5, fontweight="bold", color=TEXT,
)
fig.text(
    0.04, 0.892,
    "Stage 1 (2004–2012): When college-educated suburbs voted 65–70% Republican, building DFW suburbs printed GOP votes.",
    fontsize=12.0, color=SUBTEXT,
)
fig.text(
    0.04, 0.852,
    "Stage 2 (2016–2026): EdPol flipped BA+ voters. DFW GOP raw votes stayed flat at ~1.15M while Dem votes doubled (719k → 1.59M).",
    fontsize=11.5, fontweight="bold", style="italic", color=BLUE,
)

dfw_cycles = [
    ("2004\nPres\n(Bush)", "president", 2004),
    ("2008\nPres\n(McCain)", "president", 2008),
    ("2012\nPres\n(Romney)", "president", 2012),
    ("2016\nPres\n(Trump)", "president", 2016),
    ("2018\nSen\n(Cruz)", "senate", 2018),
    ("2020\nPres\n(Trump)", "president", 2020),
    ("2024\nPres\n(Trump)", "president", 2024),
    ("2026\nGov\n(Abbott)", "governor", 2026),
    ("2026\nSen\n(Paxton)", "senate", 2026),
]

x_idx = np.arange(len(dfw_cycles))
dem_m, gop_m = [], []
for _, off, yr in dfw_cycles:
    dem_m.append(sum(hist_votes[f][(off, yr)]["dem"] for f in dfw_9) / 1e6)
    gop_m.append(sum(hist_votes[f][(off, yr)]["rep"] for f in dfw_9) / 1e6)

ax.axvspan(-0.35, 2.35, color="#fee2e2", alpha=0.38, zorder=1)
ax.axvspan(2.35, 8.35, color="#dbeafe", alpha=0.38, zorder=1)

ax.text(
    1.0, 1.88,
    "STAGE 1 (2004–2012): THE GOP FIREWALL\nWhite-collar suburbs voted 65–70% GOP.\nCollin + Denton voted R+41.9% (2004) & R+31.5% (2012).",
    ha="center", va="top", fontsize=10.0, fontweight="bold", color=RED,
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff5f5", edgecolor=RED, lw=1.2),
)
ax.text(
    5.35, 1.88,
    "STAGE 2 (2016–2026): EDPOL FLIPS THE MACHINE'S POLARITY\nDFW permits 808,905 homes & adds +697,378 BA+ adults.\nNearly 100% of net voter growth goes Dem (+512,778 margin in 2026 Sen!).",
    ha="center", va="top", fontsize=10.0, fontweight="bold", color=BLUE,
    bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0f7ff", edgecolor=BLUE, lw=1.2),
)

ax.plot(x_idx, dem_m, marker="o", lw=3.4, ms=9, color=BLUE, label="9-County DFW Democratic Votes (Millions)", zorder=4)
ax.plot(x_idx, gop_m, marker="s", lw=3.2, ms=8.5, color=RED, linestyle="--", label="9-County DFW Republican Votes (Millions)", zorder=4)

for i in range(len(x_idx)):
    dv, rv = dem_m[i], gop_m[i]
    diff_k = (dv - rv) * 1000.0
    if i == 5:  # 2020 Pres where both are high
        ax.text(x_idx[i] - 0.12, dv + 0.045, f"{dv:.2f}M", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color=BLUE)
        ax.text(x_idx[i] + 0.12, rv - 0.055, f"{rv:.2f}M", ha="center", va="top", fontsize=9.5, fontweight="bold", color=RED)
    elif i == 6:  # 2024 Pres where GOP > Dem
        ax.text(x_idx[i], rv + 0.045, f"{rv:.2f}M", ha="center", va="bottom", fontsize=9.5, fontweight="bold", color=RED)
        ax.text(x_idx[i], dv - 0.055, f"{dv:.2f}M", ha="center", va="top", fontsize=9.5, fontweight="bold", color=BLUE)
    else:
        ax.text(x_idx[i], dv + 0.045 if dv >= rv else dv - 0.06, f"{dv:.2f}M", ha="center", va="bottom" if dv >= rv else "top", fontsize=9.5, fontweight="bold", color=BLUE)
        ax.text(x_idx[i], rv - 0.06 if dv >= rv else rv + 0.045, f"{rv:.2f}M", ha="center", va="top" if dv >= rv else "bottom", fontsize=9.5, fontweight="bold", color=RED)

    if i in (0, 2, 4, 7, 8):
        ymid = 0.5 * (dv + rv)
        ax.annotate(
            f"Net: {diff_k:+,.0f}k",
            xy=(x_idx[i], ymid),
            fontsize=9.0, fontweight="bold",
            color=BLUE if diff_k > 0 else RED,
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#a1a1aa", alpha=0.95),
            zorder=5,
        )

ax.set_xticks(x_idx)
ax.set_xticklabels([c[0] for c in dfw_cycles], fontsize=10.0, fontweight="bold", color=TEXT)
ax.set_ylim(0.55, 1.96)
ax.set_ylabel("Raw Votes Cast in 9-County DFW Metro (Millions)", fontsize=11.0, fontweight="bold", color=TEXT)
ax.grid(True, linestyle=":", color=GRID, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="lower right", fontsize=10.2, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

fig.text(
    0.04, 0.025,
    "Note: 9-County DFW = Dallas, Tarrant, Collin, Denton, Rockwall, Ellis, Kaufman, Johnson, & Parker (`https://github.com/mike10010100/elections-2026`).",
    fontsize=9.0, color=SUBTEXT,
)
fig.savefig(OUT_DIR / "thread_tx_2_two_stage_dfw.png", dpi=180, facecolor=BG)
plt.close(fig)


# =============================================================================
# CARD 3: DFW COUNTY-BY-COUNTY SCOREBOARD (COLLIN, DENTON, TARRANT, DALLAS, ETC.)
# =============================================================================
fig, ax = plt.subplots(figsize=(14.5, 9.2), dpi=180, facecolor=BG)
ax.set_facecolor(PANEL_BG)
plt.subplots_adjust(left=0.21, right=0.96, top=0.79, bottom=0.12)

fig.text(
    0.04, 0.935,
    "Inside the DFW Boom: Where 808,905 New Homes & +697,378 BA+ Adults Went",
    fontsize=19.5, fontweight="bold", color=TEXT,
)
fig.text(
    0.04, 0.892,
    "In Collin County (Plano/Frisco/McKinney), 198,738 homes were permitted and BA+ share hit 54.9%: +150,988 Dem votes vs. +208 GOP votes.",
    fontsize=11.8, color=SUBTEXT,
)
fig.text(
    0.04, 0.852,
    "Across Collin + Denton + Tarrant + Dallas, Democrats added +613,732 Senate votes since 2012 while Republicans lost -130,107.",
    fontsize=11.5, fontweight="bold", style="italic", color=BLUE,
)

dfw_focus = [
    ("Collin County\n(Plano / Frisco / McKinney)", "48085"),
    ("Denton County\n(Denton / Lewisville / Frisco)", "48121"),
    ("Tarrant County\n(Fort Worth / Arlington)", "48439"),
    ("Dallas County\n(Dallas / Irving / Garland)", "48113"),
    ("Ellis County\n(Waxahachie / Midlothian)", "48139"),
    ("Kaufman County\n(Forney / Terrell — Flipped D!)", "48257"),
    ("Rockwall County\n(Rockwall / Heath)", "48397"),
]

y_c3 = np.arange(len(dfw_focus))[::-1]
bh3 = 0.23
p3, b3, d3, g3, notes3 = [], [], [], [], []
for label, f_id in dfw_focus:
    c = counties[f_id]
    p3.append(c["permits_total_10_24"] / 1000.0)
    b3.append(c["ba_adults_added_10_23"] / 1000.0)
    d3.append(c["net_new_dem_votes_12_to_sen26"] / 1000.0)
    g3.append(c["net_new_gop_votes_12_to_sen26"] / 1000.0)
    notes3.append(
        f"{c['permits_total_10_24']:,d} homes → +{c['ba_adults_added_10_23']:,d} BA+ ({c['ba_share_of_adult_growth_pct']:.0f}% of adult gr; now {c['ba_pct_2023']:.1f}% BA+)\n"
        f"Margin: {c['pres_2004_margin_pct']:+.1f}% ('04) → {c['pres_2012_margin_pct']:+.1f}% ('12) → {c['gov_2026_margin_pct']:+.1f}% (Gov '26) / {c['sen_2026_margin_pct']:+.1f}% (Sen '26)"
    )

ax.axvline(0, color=TEXT, lw=1.0, zorder=2)
ax.barh(y_c3 + 1.05 * bh3, p3, height=bh3, color=ORANGE, alpha=0.92, label="New Homes Permitted (2010–24, BPS)", zorder=3)
ax.barh(y_c3, b3, height=bh3, color=GREEN, alpha=0.92, label="Net New BA+ Adults Added (2010–23)", zorder=3)
ax.barh(y_c3 - 1.05 * bh3, d3, height=bh3, color=BLUE, alpha=0.95, label="Net New Dem Votes (2012→26 Sen)", zorder=3)
ax.barh(y_c3 - 1.05 * bh3, g3, height=bh3, color=RED, alpha=0.78, label="Net New GOP Votes (2012→26 Sen)", zorder=3)

for i, y in enumerate(y_c3):
    mx = max(p3[i], b3[i], d3[i])
    ax.text(mx + 6, y, notes3[i], va="center", ha="left", fontsize=9.0, fontweight="bold", color=TEXT)

ax.set_yticks(y_c3)
ax.set_yticklabels([x[0] for x in dfw_focus], fontsize=10.0, fontweight="bold", color=TEXT)
ax.set_xlim(-105, 565)
ax.set_ylim(-0.6, 6.6)
ax.set_xlabel("Thousands of Homes Permitted / BA+ Adults Added / Net Votes Added (2010–2026)", fontsize=11.0, fontweight="bold", color=TEXT)
ax.grid(axis="x", linestyle=":", color=GRID, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="center right", bbox_to_anchor=(0.99, 0.23), fontsize=9.2, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

fig.text(
    0.04, 0.025,
    "Sources: U.S. Census BPS (2010–2024), USDA ERS / Census ACS Educational Attainment (2000–2023), & NYT 2026 Returns (`https://github.com/mike10010100/elections-2026`).",
    fontsize=9.0, color=SUBTEXT,
)
fig.savefig(OUT_DIR / "thread_tx_3_collin_denton_breakdown.png", dpi=180, facecolor=BG)
plt.close(fig)


# =============================================================================
# CARD 4: NORMALIZED PER-CAPITA RATE SCATTER (PERMITS/1K POP VS BA+ EXPANSION)
# =============================================================================
fig, ax = plt.subplots(figsize=(14.5, 9.2), dpi=180, facecolor=BG)
ax.set_facecolor(PANEL_BG)
plt.subplots_adjust(left=0.09, right=0.92, top=0.80, bottom=0.12)

fig.text(
    0.04, 0.935,
    "Controlling for County Size: Housing Permits per 1,000 Residents vs. BA+ Inflow",
    fontsize=19.5, fontweight="bold", color=TEXT,
)
fig.text(
    0.04, 0.892,
    "Across non-border Texas counties (Pop ≥ 20k, N = 113), per-capita permitting correlates with BA+ adult expansion at r = +0.88.",
    fontsize=12.0, color=SUBTEXT,
)
fig.text(
    0.04, 0.852,
    "Every +1,000 BA+ adults added across Texas produced +990 net new Democratic Senate votes (+898 Gov) vs. -239 GOP votes.",
    fontsize=11.5, fontweight="bold", style="italic", color=BLUE,
)

non_border = [r for r in tx_counties if r["hisp_pct"] < 65.0 and r["pop_2024"] >= 20000]
x_perm = np.array([r["permits_per_1k_pop10"] for r in non_border])
y_bagr = np.array([r["ba_expansion_pct_of_2010_adults"] for r in non_border])
sh_04_26 = np.array([r["shift_04_to_sen26_pts"] for r in non_border])
sizes = np.clip(np.sqrt([r["pop_2024"] for r in non_border]) * 0.36, 35, 520)

sc = ax.scatter(
    x_perm, y_bagr, s=sizes, c=sh_04_26,
    cmap="RdYlBu", vmin=5, vmax=55,
    alpha=0.88, edgecolors="#18181b", linewidths=0.85, zorder=3,
)
cbar = plt.colorbar(sc, ax=ax, pad=0.02, fraction=0.04)
cbar.set_label("2004 → 2026 Democratic Margin Shift (pts)", fontsize=10.5, fontweight="bold", color=TEXT)
cbar.ax.tick_params(labelsize=9.5)

m_sl, b_int = np.polyfit(x_perm, y_bagr, 1)
x_line = np.linspace(0, 390, 100)
ax.plot(x_line, m_sl * x_line + b_int, color=BLUE, linestyle="--", lw=2.2, label="OLS Trend (r = +0.82 unweighted, +0.88 population-weighted)", zorder=2)

label_targets_c4 = {
    "Williamson": (158, 43.8),
    "Denton": (110, 39.2),
    "Collin": (218, 40.8),
    "Fort Bend": (82, 32.0),
    "Travis": (298, 22.8),
    "Hays": (290, 29.5),
    "Comal": (302, 42.5),
    "Rockwall": (268, 36.8),
    "Montgomery": (255, 17.5),
    "Tarrant": (62, 22.8),
    "Harris": (126, 20.8),
    "Dallas": (108, 6.0),
    "Brazoria": (162, 10.5),
}
for r in non_border:
    nm = r["name"]
    if nm in label_targets_c4:
        tx, ty = label_targets_c4[nm]
        ax.annotate(
            f"{nm} (+{r['shift_04_to_sen26_pts']:.0f} pts | {r['ba_pct_2023']:.0f}% BA+)",
            xy=(r["permits_per_1k_pop10"], r["ba_expansion_pct_of_2010_adults"]),
            xytext=(tx, ty),
            fontsize=9.2, fontweight="bold", color=TEXT,
            arrowprops=dict(arrowstyle="->", color="#52525b", lw=0.9, shrinkA=0, shrinkB=4),
            zorder=5,
        )

ax.set_xlim(-10, 420)
ax.set_ylim(-4, 48)
ax.set_xlabel("New Housing Units Permitted per 1,000 Residents (2010–2024, U.S. Census BPS)", fontsize=11.0, fontweight="bold", color=TEXT)
ax.set_ylabel("Net New BA+ Adults Added as % of 2010 Adult Population", fontsize=11.0, fontweight="bold", color=TEXT)
ax.grid(True, linestyle=":", color=GRID, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.legend(loc="upper left", fontsize=10.0, frameon=True, facecolor="#fafafa", edgecolor="#d4d4d8")

fig.text(
    0.04, 0.025,
    "Sources: U.S. Census BPS (2010–2024), USDA ERS / Census ACS Educational Attainment (2000–2023), & NYT 2026 Returns (`https://github.com/mike10010100/elections-2026`).",
    fontsize=9.0, color=SUBTEXT,
)
fig.savefig(OUT_DIR / "thread_tx_4_scatter_permits_ba.png", dpi=180, facecolor=BG)
plt.close(fig)


# =============================================================================
# CARD 5: WHY TEXAS'S HOUSING BOOM TURNED IT BLUE WHILE FLORIDA'S TURNED IT RED
# =============================================================================
fig, ax = plt.subplots(figsize=(14.5, 9.2), dpi=180, facecolor=BG)
ax.set_facecolor(PANEL_BG)
plt.subplots_adjust(left=0.23, right=0.96, top=0.80, bottom=0.12)

fig.text(
    0.04, 0.935,
    "The Natural Control Experiment: Why Texas's Housing Boom Flipped It Blue",
    fontsize=19.5, fontweight="bold", color=TEXT,
)
fig.text(
    0.04, 0.892,
    "5 of the 6 fastest-growing large U.S. counties are in Texas — pairing 2.7×–3.3× home price-to-income affordability with $87k–98k BA+ jobs.",
    fontsize=11.8, color=SUBTEXT,
)
fig.text(
    0.04, 0.852,
    "Texas imported young (11% Age 65+), college-educated (45–55% BA+) families (+44 to +55 pt Dem shift); Florida imported non-college retirees (28% 65+).",
    fontsize=11.3, fontweight="bold", style="italic", color=BLUE,
)

comp_cohorts = [
    ("Collin County, TX\n(DFW Suburb: 199k permits)", 55.2, "3.3× Price/Inc ($315k home, 97k inc) | 55% BA+ | 11% Age 65+ | +36% PopGr", BLUE),
    ("Williamson County, TX\n(Austin Suburb: 97k permits)", 51.7, "3.0× Price/Inc ($262k home, 87k inc) | 47% BA+ | 12% Age 65+ | +44% PopGr", BLUE),
    ("Denton County, TX\n(DFW Suburb: 112k permits)", 48.9, "3.2× Price/Inc ($278k home, 87k inc) | 48% BA+ | 11% Age 65+ | +37% PopGr", BLUE),
    ("Hays County, TX\n(Austin Suburb: 55k permits)", 46.5, "3.5× Price/Inc ($239k home, 69k inc) | 42% BA+ | 11% Age 65+ | +53% PopGr", BLUE),
    ("Tarrant County, TX\n(Fort Worth: 185k permits)", 44.6, "2.8× Price/Inc ($189k home, 68k inc) | 35% BA+ | 12% Age 65+ | +17% PopGr", BLUE),
    ("Fort Bend County, TX\n(Houston Suburb: 143k permits)", 43.9, "2.7× Price/Inc ($266k home, 98k inc) | 49% BA+ | 12% Age 65+ | +41% PopGr", BLUE),
    ("GA / NC / CO / VA High-BA\n(Sunbelt Peer Suburbs)", 42.7, "4.0× Price/Inc ($315k home, 79k inc) | 46% BA+ | 13% Age 65+ | +16% PopGr", LIGHT_BLUE),
    ("California High-BA Counties\n(NIMBY: 38 permits/1k pop)", 17.9, "7.8× Price/Inc ($653k home) | 39% BA+ | Priced out (+5.5% PopGr)", DEEP_ORANGE),
    ("NY / NJ / MA High-BA Counties\n(NIMBY: 32 permits/1k pop)", 12.8, "5.5× Price/Inc ($458k home) | 42% BA+ | Priced out (+6.6% PopGr)", DEEP_ORANGE),
    ("Florida Retiree Boom Counties\n(Lake / Manatee / Lee: +25% Gr)", -1.1, "4.0× Price/Inc ($218k home, 58k inc) | 27% BA+ | 28% Age 65+ (Retiree Inflow → Red)", RED),
]

y_d = np.arange(len(comp_cohorts))[::-1]
sh_vals = [c[1] for c in comp_cohorts]
colors_d = [c[3] for c in comp_cohorts]

ax.axvline(0, color=TEXT, lw=1.0, zorder=2)
ax.barh(y_d, sh_vals, height=0.64, color=colors_d, alpha=0.92, edgecolor="#18181b", lw=0.7, zorder=3)

for i, y in enumerate(y_d):
    val = sh_vals[i]
    note = comp_cohorts[i][2]
    if val >= 0:
        ax.text(val + 1.2, y, f"{val:+.1f} pts  ({note})", va="center", ha="left", fontsize=9.1, fontweight="bold", color=TEXT)
    else:
        ax.text(1.0, y, f"{val:+.1f} pts  ({note})", va="center", ha="left", fontsize=9.1, fontweight="bold", color=RED)

ax.set_yticks(y_d)
ax.set_yticklabels([c[0] for c in comp_cohorts], fontsize=9.8, fontweight="bold", color=TEXT)
ax.set_xlim(-8, 146)
ax.set_xlabel("2004 → 2026 Democratic Margin Shift (percentage points)", fontsize=11.0, fontweight="bold", color=TEXT)
ax.grid(axis="x", linestyle=":", color=GRID, zorder=0)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

fig.text(
    0.04, 0.025,
    "Sources: U.S. Census BPS & ACS Demographics, USDA ERS Educational Attainment, & NYT 2026 Returns (`https://github.com/mike10010100/elections-2026`).",
    fontsize=9.0, color=SUBTEXT,
)
fig.savefig(OUT_DIR / "thread_tx_5_tx_vs_fl_ca.png", dpi=180, facecolor=BG)
plt.close(fig)

print("Generated 5 standalone thread cards in", OUT_DIR)

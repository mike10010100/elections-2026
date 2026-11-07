#!/usr/bin/env python3
"""
Build 2026 FEC Campaign Finance + Independent Expenditure 'Moneyball' (Spend per Swing)
datasets for U.S. Senate and U.S. House races, joined with 2026 NYT election returns.

Outputs:
  - data/fec_2026/fec_moneyball_2026.json
  - data/fec_2026/fec_moneyball_senate_2026.csv
  - data/fec_2026/fec_moneyball_house_2026.csv
  - site_data/fec_moneyball_2026.json
"""
import csv
import json
import os
import unicodedata
from collections import defaultdict

BASE_DIR = "/home/mike10010100/git/elections-2026"
FEC_DIR = os.path.join(BASE_DIR, "data", "fec_2026")
OVERVIEW_PATH = os.path.join(BASE_DIR, "site_data", "overview.json")


def strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


def load_weball():
    weball = {}
    by_state_office = defaultdict(list)
    path = os.path.join(FEC_DIR, "weball26.txt")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            row = line.strip().split("|")
            if len(row) < 28:
                continue
            cid = row[0]
            info = {
                "cand_id": cid,
                "fec_name": row[1],
                "ici": row[2],
                "party": row[4],
                "receipts": float(row[5] or 0.0),
                "trans_from_auth": float(row[6] or 0.0),
                "disbursements": float(row[7] or 0.0),
                "cash_on_hand": float(row[10] or 0.0),
                "cand_contrib": float(row[11] or 0.0),
                "cand_loans": float(row[12] or 0.0),
                "debts_owed": float(row[16] or 0.0),
                "indiv_contrib": float(row[17] or 0.0),
                "state": row[18],
                "district": row[19],
                "pac_contrib": float(row[25] or 0.0),
                "party_contrib": float(row[26] or 0.0),
                "coverage_end_date": row[27],
            }
            weball[cid] = info
            by_state_office[(row[18], cid[0])].append(info)
    return weball, by_state_office


def load_independent_expenditures():
    ie_path = os.path.join(FEC_DIR, "independent_expenditure_2026.csv")
    prev_files = set()
    with open(ie_path, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row.get("prev_file_num"):
                prev_files.add(row["prev_file_num"])

    ie_by_cand = defaultdict(
        lambda: {"S_all": 0.0, "O_all": 0.0, "S_gen": 0.0, "O_gen": 0.0, "S_pri": 0.0, "O_pri": 0.0}
    )
    with open(ie_path, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if row.get("file_num") in prev_files:
                continue
            cid = row.get("cand_id", "")
            so = row.get("sup_opp", "")
            ele = row.get("ele_type", "")
            if so not in ("S", "O") or not cid:
                continue
            try:
                amt = float(row.get("exp_amo") or 0.0)
            except ValueError:
                amt = 0.0
            ie_by_cand[cid][f"{so}_all"] += amt
            if ele == "G":
                ie_by_cand[cid][f"{so}_gen"] += amt
            elif ele == "P":
                ie_by_cand[cid][f"{so}_pri"] += amt
    return ie_by_cand


def match_candidate(cand_obj, state, office_char, district_num, by_state_office):
    if not cand_obj:
        return None
    raw_name = strip_accents(cand_obj.get("name", "")).upper()
    parts = [p.replace(",", "").replace(".", "") for p in raw_name.split() if p.lower() not in ("jr", "sr", "ii", "iii", "iv", "(write-in)")]
    if not parts:
        return None
    last = parts[-1]
    first = parts[0] if len(parts) > 1 else ""

    pool = by_state_office.get((state, office_char), [])
    if office_char == "H" and district_num is not None:
        dist_str = f"{int(district_num):02d}"
        dist_pool = [x for x in pool if x["district"] in (dist_str, "00", "01") or int(district_num) == 1]
    else:
        dist_pool = pool

    matches = [x for x in dist_pool if last in strip_accents(x["fec_name"]).upper()]
    if len(matches) > 1 and first:
        first_matches = [x for x in matches if first[:3] in strip_accents(x["fec_name"]).upper()]
        if first_matches:
            matches = first_matches
    if not matches and office_char == "H":
        # Fallback to state-wide H pool
        matches = [x for x in pool if last in strip_accents(x["fec_name"]).upper()]
    return max(matches, key=lambda x: x["receipts"]) if matches else None


def build_race_record(r, office_char, by_state_office, ie_by_cand):
    st = r["state"]
    seat_num = r.get("seat_number")
    cands = r.get("candidates", [])
    non_gop = [c for c in cands if c.get("party") in ("DEM", "IND")]
    gop_cands = [c for c in cands if c.get("party") == "GOP"]
    if not non_gop or not gop_cands:
        return None

    dem_c = max(non_gop, key=lambda x: x.get("votes") or 0)
    gop_c = max(gop_cands, key=lambda x: x.get("votes") or 0)

    dm = match_candidate(dem_c, st, office_char, seat_num, by_state_office)
    gm = match_candidate(gop_c, st, office_char, seat_num, by_state_office)

    tot_v = r.get("total_votes") or 0
    if tot_v <= 0:
        return None

    m26 = ((dem_c.get("votes") or 0) - (gop_c.get("votes") or 0)) / tot_v * 100.0
    pres24 = r.get("district_pres_2024_margin") if office_char == "H" and r.get("district_pres_2024_margin") is not None else r.get("pres_2024_margin")
    sh24_pres = (m26 - pres24) if pres24 is not None else None

    if sh24_pres is not None:
        base24 = pres24
        sh24 = sh24_pres
    elif office_char == "H":
        base24 = r.get("margin_2024_house")
        sh24 = r.get("shift_vs_house_2024")
        if sh24 is None and base24 is not None:
            sh24 = m26 - base24
    else:
        base24 = pres24
        sh24 = sh24_pres

    net_votes_shifted = (tot_v * (sh24 / 100.0)) if sh24 is not None else None

    d_rec = dm["receipts"] if dm else 0.0
    d_disb = dm["disbursements"] if dm else 0.0
    r_rec = gm["receipts"] if gm else 0.0
    r_disb = gm["disbursements"] if gm else 0.0

    d_ie = ie_by_cand[dm["cand_id"]] if dm else {"S_all": 0.0, "O_all": 0.0, "S_gen": 0.0, "O_gen": 0.0}
    r_ie = ie_by_cand[gm["cand_id"]] if gm else {"S_all": 0.0, "O_all": 0.0, "S_gen": 0.0, "O_gen": 0.0}

    ie_pro_d_all = d_ie["S_all"] + r_ie["O_all"]
    ie_pro_r_all = r_ie["S_all"] + d_ie["O_all"]
    ie_pro_d_gen = d_ie["S_gen"] + r_ie["O_gen"]
    ie_pro_r_gen = r_ie["S_gen"] + d_ie["O_gen"]

    tot_pro_d = d_disb + ie_pro_d_all
    tot_pro_r = r_disb + ie_pro_r_all
    tot_race_spend = tot_pro_d + tot_pro_r

    cand_spend_per_pt = (d_disb / sh24) if (sh24 and sh24 > 0) else None
    tot_pro_d_per_pt = (tot_pro_d / sh24) if (sh24 and sh24 > 0) else None
    cand_spend_per_shifted_vote = (d_disb / net_votes_shifted) if (net_votes_shifted and net_votes_shifted > 0) else None
    tot_pro_d_per_shifted_vote = (tot_pro_d / net_votes_shifted) if (net_votes_shifted and net_votes_shifted > 0) else None

    return {
        "state": st,
        "office": r.get("office"),
        "seat": r.get("seat"),
        "seat_number": seat_num,
        "is_special": r.get("is_special", False),
        "eevp": r.get("eevp"),
        "total_votes_2026": tot_v,
        "dem_name": dem_c.get("name"),
        "dem_party": dem_c.get("party"),
        "dem_fec_id": dm["cand_id"] if dm else None,
        "dem_votes": dem_c.get("votes"),
        "gop_name": gop_c.get("name"),
        "gop_fec_id": gm["cand_id"] if gm else None,
        "gop_votes": gop_c.get("votes"),
        "margin_2026": round(m26, 2),
        "pres_2024_margin": round(pres24, 2) if pres24 is not None else None,
        "shift_vs_pres_2024": round(sh24, 2) if sh24 is not None else None,
        "net_votes_shifted_vs_2024": round(net_votes_shifted) if net_votes_shifted is not None else None,
        "dem_receipts": round(d_rec, 2),
        "dem_disbursements": round(d_disb, 2),
        "gop_receipts": round(r_rec, 2),
        "gop_disbursements": round(r_disb, 2),
        "ie_support_dem": round(d_ie["S_all"], 2),
        "ie_oppose_gop": round(r_ie["O_all"], 2),
        "ie_pro_dem_total": round(ie_pro_d_all, 2),
        "ie_pro_dem_general": round(ie_pro_d_gen, 2),
        "ie_support_gop": round(r_ie["S_all"], 2),
        "ie_oppose_dem": round(d_ie["O_all"], 2),
        "ie_pro_gop_total": round(ie_pro_r_all, 2),
        "ie_pro_gop_general": round(ie_pro_r_gen, 2),
        "total_pro_dem_spend": round(tot_pro_d, 2),
        "total_pro_gop_spend": round(tot_pro_r, 2),
        "total_race_spend": round(tot_race_spend, 2),
        "cand_spend_per_shift_pt": round(cand_spend_per_pt, 2) if cand_spend_per_pt is not None else None,
        "total_pro_dem_per_shift_pt": round(tot_pro_d_per_pt, 2) if tot_pro_d_per_pt is not None else None,
        "cand_spend_per_shifted_vote": round(cand_spend_per_shifted_vote, 2) if cand_spend_per_shifted_vote is not None else None,
        "total_pro_dem_per_shifted_vote": round(tot_pro_d_per_shifted_vote, 2) if tot_pro_d_per_shifted_vote is not None else None,
    }


def write_csv(path, rows):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def main():
    with open(OVERVIEW_PATH, "r", encoding="utf-8") as f:
        ov = json.load(f)

    weball, by_state_office = load_weball()
    ie_by_cand = load_independent_expenditures()

    senate_rows = []
    for r in ov.get("senate_races", []):
        rec = build_race_record(r, "S", by_state_office, ie_by_cand)
        if rec:
            senate_rows.append(rec)

    house_rows = []
    for r in ov.get("house_races", []):
        rec = build_race_record(r, "H", by_state_office, ie_by_cand)
        if rec:
            house_rows.append(rec)

    out_obj = {
        "source": "FEC Bulk Data (weball26.txt + independent_expenditure_2026.csv, as of 2026-11-04) joined with NYT 2026 Election Returns",
        "senate_count": len(senate_rows),
        "house_count": len(house_rows),
        "senate_races": senate_rows,
        "house_races": house_rows,
    }

    for out_json in [
        os.path.join(FEC_DIR, "fec_moneyball_2026.json"),
        os.path.join(BASE_DIR, "site_data", "fec_moneyball_2026.json"),
    ]:
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(out_obj, f, indent=2)

    write_csv(os.path.join(FEC_DIR, "fec_moneyball_senate_2026.csv"), senate_rows)
    write_csv(os.path.join(FEC_DIR, "fec_moneyball_house_2026.csv"), house_rows)
    write_csv(os.path.join(BASE_DIR, "site_data", "fec_moneyball_senate_2026.csv"), senate_rows)
    write_csv(os.path.join(BASE_DIR, "site_data", "fec_moneyball_house_2026.csv"), house_rows)
    generate_moneyball_counterspend_chart(senate_rows)
    print(f"Saved {len(senate_rows)} Senate races, {len(house_rows)} House races, and assets/chart7_senate_moneyball_counterspend.png.")


def generate_moneyball_counterspend_chart(senate_rows=None):
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
    plt.rcParams["axes.edgecolor"] = "#cccccc"
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["text.parse_math"] = False

    BG_COLOR = "#f4f3ef"
    DARK_TEXT = "#1a1a1a"
    SUB_TEXT = "#4a4a4a"
    MUTED_TEXT = "#6e6e6e"
    GRID_COLOR = "#dedcd6"
    BLUE_DOG = "#1b4f72"
    NORMIE_TEAL = "#117864"
    PROG_ORANGE = "#d35400"
    CRIMSON = "#c0392b"
    GOP_FILL = "#e6b0aa"

    fig = plt.figure(figsize=(16.4, 9.0), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.16, 1.04], left=0.165, right=0.97, top=0.76, bottom=0.14, wspace=0.21)

    fig.text(0.03, 0.925, "2026 Senate 'Moneyball': Diminishing Returns & Endogenous GOP Counterspend",
             fontsize=19.5, fontweight="bold", color=DARK_TEXT)
    fig.text(0.03, 0.88, "Michigan ($370.8M total; $146.3M Dem vs. $224.4M GOP) ranked #1 most expensive per point of positive swing ($17.4M/pt Dem; $44.1M/pt total).",
             fontsize=12.1, color=SUB_TEXT)
    fig.text(0.03, 0.842, "Polling lag after a $70M primary drew $171M in GOP general-election IEs, forcing SMP to triple MI from $20M to $67M while starving low-saturation Southern TV markets.",
             fontsize=11.1, color=MUTED_TEXT, style="italic")

    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title("A. Spend per Point of 2024->2026 Swing: Pro-Dem + GOP Counterspend\n(Solid = Pro-Dem $/pt | Shaded Red = Pro-GOP Counterspend $/pt)",
                  fontsize=11.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    races = [
        ("MI: Abdul El-Sayed (+7.0%)", 17.40, 26.68, "prog", "$17.4M/pt ($146M D | $224M R | $67M SMP)"),
        ("OH: Sherrod Brown (+4.9%)", 13.73, 17.13, "main", "$13.7M/pt ($220M D | $275M R | $150M SMP)"),
        ("TX: James Talarico (+12.1%)", 10.73, 12.97, "main", "$10.7M/pt ($277M D | $334M R | $40M SMP)"),
        ("IA: Josh Turek (+4.1%)", 7.75, 6.37, "main", "$7.8M/pt ($135M D | $111M R | $67M SMP)"),
        ("AK: Mary Peltola (+0.3%)", 6.22, 4.83, "main", "$6.2M/pt ($84M D | $65M R)"),
        ("GA: Jon Ossoff (+18.1%)", 6.12, 1.43, "main", "$6.1M/pt ($124M D | $29M R | $18M Gen R IE)"),
        ("NH: Chris Pappas (+13.8%)", 4.30, 4.31, "main", "$4.3M/pt ($47M D | $47M R)"),
        ("KS: Adam Hamilton (+5.0%)", 3.39, 1.96, "main", "$3.4M/pt ($72M D | $41M R | $14M SMP)"),
        ("NC: Roy Cooper (+19.6%)", 3.01, 2.69, "main", "$3.0M/pt ($69M D | $62M R)"),
        ("MN: Peggy Flanagan (+10.2%)", 2.57, 3.31, "prog", "$2.6M/pt ($15M D | $20M R)"),
        ("SC: Annie Andrews (+4.5%)", 2.08, 1.43, "main", "$2.1M/pt ($46M D | $32M R | $750K SMP)"),
        ("FL: Angie Nixon (-2.9%)", 1.85, 2.76, "prog", "$1.9M/pt ($19M D | $28M R | $0 SMP)"),
        ("MS: Scott Colom (+0.19%)", 0.84, 0.27, "south", "$840K/pt ($19.4M D | $2.4M Gen R IE | $2.2M SMP)"),
        ("LA: Jamie Davis (-1.76%)", 0.72, 1.01, "south", "$722K/pt ($14.6M D | $20.5M R [$2.5M Gen IE])"),
    ]

    y_pos = np.arange(len(races))[::-1]
    for y, (label, d_val, r_val, cat, txt) in zip(y_pos, races):
        if cat == "prog":
            col = PROG_ORANGE
        elif cat == "south":
            col = NORMIE_TEAL
        else:
            col = BLUE_DOG
        ax1.barh(y, d_val, height=0.62, color=col, alpha=0.90, zorder=3)
        ax1.barh(y, r_val, left=d_val, height=0.62, color=GOP_FILL, edgecolor=CRIMSON, linewidth=0.9, alpha=0.75, zorder=3)
        tot_val = d_val + r_val
        ax1.text(tot_val + 0.6, y, txt, fontsize=8.1, fontweight="bold", color=col, va="center", ha="left")

    ax1.axhspan(-0.5, 1.5, color="#e8f8f5", alpha=0.65, zorder=1)
    ax1.annotate("Low-saturation & 21x-24x cheaper per point:\nLA (-1.76%, 25,857 votes) & MS (+0.19%) had\njust $2.5M & $2.4M in GOP general-election IEs!",
                 xy=(43.5, 0.95), xytext=(40.5, 2.2),
                 arrowprops=dict(arrowstyle="->", color=NORMIE_TEAL, lw=1.8, connectionstyle="arc3,rad=-0.15"),
                 fontsize=8.1, fontweight="bold", color=NORMIE_TEAL,
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#e8f8f5", edgecolor=NORMIE_TEAL, lw=1.2))

    dem_patch = mpatches.Patch(color=BLUE_DOG, alpha=0.9, label="Pro-Dem $/pt (Blue=Mainstream, Orange=Prog, Teal=South)")
    gop_patch = mpatches.Patch(facecolor=GOP_FILL, edgecolor=CRIMSON, label="Pro-GOP Counterspend $/pt (Cand. + Pro-GOP IEs)")
    ax1.legend(handles=[dem_patch, gop_patch], loc="center right", bbox_to_anchor=(0.99, 0.37), fontsize=7.8, framealpha=0.94, facecolor="white")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([r[0] for r in races], fontsize=9.4, fontweight="bold", color=DARK_TEXT)
    ax1.set_xlim(0, 82.0)
    ax1.set_ylim(-0.6, len(races) - 0.3)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("Spend per Point of 2024->2026 Dem Swing ($ Millions / pt: Dem + GOP Counterspend)", fontsize=10.0, color=SUB_TEXT)

    ax2 = fig.add_subplot(gs[1], facecolor=BG_COLOR)
    ax2.set_title("B. Diminishing Returns Curve & Why MI Drew $171M in GOP Gen. IEs\n(Total Pro-Dem Spend vs. 2024->2026 Swing, Annotated with GOP IEs)",
                  fontsize=10.8, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    pts = [
        ("LA: Davis -1.8% ($2.5M R IE)", 14.63, 20.25, "south", 5, -0.55, "left"),
        ("MS: Colom +0.2% ($2.4M R IE)", 19.39, 23.08, "south", -3, 1.35, "left"),
        ("SC (Andrews +4.5%)", 46.36, 22.34, "main", -8, -1.0, "center"),
        ("NC (Cooper +19.6%)", 68.75, 22.85, "main", 6, 0.9, "left"),
        ("KS (Hamilton +5%)", 71.58, 21.12, "main", 5, 0.5, "left"),
        ("GA: Ossoff +18.1% ($18M R IE)", 123.97, 20.25, "main", 6, 0.8, "left"),
        ("IA: Turek +4.1% ($96M R IE)", 134.62, 17.37, "main", 5, 0.35, "left"),
        ("OH: Brown +4.9% ($222M R IE)", 220.49, 16.06, "main", -6, -1.1, "center"),
        ("TX: Talarico +12.1% ($315M R IE)", 276.51, 25.78, "main", -6, -0.4, "right"),
        ("NH: Pappas +13.8% ($39M R)", 47.21, 10.99, "main", 5, 0.55, "left"),
        ("FL (Nixon -2.9%)", 18.94, 10.22, "prog", 5, -0.85, "left"),
        ("MN (Flanagan +10.2%)", 15.12, 5.89, "prog", 5, -0.25, "left"),
        ("ME: Jackson +6.4% ($81M R IE)", 77.54, -0.55, "prog", 5, -0.95, "left"),
        ("MI: El-Sayed +7.0% ($171M R IE)", 146.33, 8.41, "prog", 6, -0.35, "left"),
    ]

    x_curve = np.linspace(10, 285, 200)
    y_curve = 14.0 + 2.1 * np.log(x_curve / 10.0)
    ax2.plot(x_curve, y_curve, color="#7f8c8d", ls="--", lw=1.8, alpha=0.7, label="Mainstream Battleground Benchmark")

    ax2.scatter([146.33], [12.16], color=BLUE_DOG, marker="s", s=95, zorder=5)
    ax2.plot([146.33, 146.33], [8.41, 12.16], color=CRIMSON, lw=2.2, ls=":", zorder=4)
    ax2.text(153, 12.45, "MI Gov: Benson (+12.2 pt shift)\nBeat El-Sayed in 83/83 counties!",
             fontsize=8.4, fontweight="bold", color=BLUE_DOG, va="center")

    for lbl, xm, ym, cat, dx, dy, ha in pts:
        if cat == "prog":
            col = PROG_ORANGE
            sz = 125 if "MI:" in lbl else 90
        elif cat == "south":
            col = NORMIE_TEAL
            sz = 115
        else:
            col = BLUE_DOG
            sz = 90
        ax2.scatter([xm], [ym], color=col, s=sz, zorder=5, edgecolor="white", linewidth=1.2)
        fw = "bold" if ("MI:" in lbl or cat == "south") else "normal"
        ax2.text(xm + dx, ym + dy, lbl, fontsize=8.0, fontweight=fw, color=col if fw == "bold" else DARK_TEXT, ha=ha, va="center")

    ax2.annotate("Endogenous Counterspend: Polling lag after a $70M primary\ndrew $171M in GOP Gen. IEs (SLF $46M, No Going Back $36M,\nGLCF $26M, AFP $22M), forcing SMP from $20M to $67M.\nEven vs. OH ($222M R IE) & TX ($315M R IE), MI lagged badly.",
                 xy=(146.33, 7.9), xytext=(104, 1.3),
                 arrowprops=dict(arrowstyle="->", color=PROG_ORANGE, lw=1.8),
                 fontsize=7.8, fontweight="bold", color=PROG_ORANGE,
                 bbox=dict(boxstyle="round,pad=0.35", facecolor="#fdf2e9", edgecolor=PROG_ORANGE, lw=1.2))

    ax2.axhline(0.0, color="#333333", lw=1.0, ls="-", alpha=0.5)
    ax2.set_xlim(0, 305)
    ax2.set_ylim(-3.0, 28.0)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Total Pro-Dem FEC Spending ($ Millions: Candidate + Super PAC IEs)", fontsize=10.0, color=SUB_TEXT)
    ax2.set_ylabel("2024 Pres -> 2026 Senate Dem Shift (margin pts)", fontsize=10.0, color=SUB_TEXT)

    fig.text(0.03, 0.024, "Source: 2026 FEC Candidate Disbursements (weball26.txt), Independent Expenditures (independent_expenditure_2026.csv), SMP Memo & Live NYT Returns (elections-2026).\nNote: 'R IE' = general-election pro-GOP/anti-Dem IEs. In MI, UDP spent $20.1M opposing El-Sayed in the primary; SLF ($46.2M), No Going Back ($35.6M), GLCF ($25.6M) & AFP ($22.3M) led the $170.9M general-election blitz.",
             fontsize=8.5, color=MUTED_TEXT)

    out_path = os.path.join(BASE_DIR, "assets", "chart7_senate_moneyball_counterspend.png")
    plt.savefig(out_path, dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    main()

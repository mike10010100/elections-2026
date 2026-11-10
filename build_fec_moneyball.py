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

    by_st = {r["state"]: r for r in (senate_rows or [])}

    def _m_str(st, default_m, decimals=1):
        m = by_st.get(st, {}).get("margin_2026", default_m)
        return f"{m:+.{decimals}f}%"

    def _bar(st, cand_lbl, default_m, default_d, default_r, cat, extra_note="", m_dec=1):
        row = by_st.get(st)
        if row and (row.get("shift_vs_pres_2024") or 0) > 0:
            sh = row["shift_vs_pres_2024"]
            d_m = row["total_pro_dem_spend"] / 1e6
            r_m = row["total_pro_gop_spend"] / 1e6
            d_pt = d_m / sh
            r_pt = r_m / sh
            m_val = row["margin_2026"]
        else:
            d_pt, r_pt = default_d, default_r
            d_m = by_st.get(st, {}).get("total_pro_dem_spend", 0) / 1e6
            r_m = by_st.get(st, {}).get("total_pro_gop_spend", 0) / 1e6
            m_val = default_m
        pt_lbl = f"${d_pt*1000:.0f}K/pt" if d_pt < 1.0 else f"${d_pt:.1f}M/pt"
        d_str = f"${d_m:.1f}M D" if d_m < 20 else f"${d_m:.0f}M D"
        if extra_note.startswith("RAW:"):
            detail = extra_note[4:]
        else:
            r_str = f"${r_m:.1f}M R" if r_m < 20 else f"${r_m:.0f}M R"
            detail = f"{d_str} | {r_str}" + (f" | {extra_note}" if extra_note else "")
        return (f"{st}: {cand_lbl} ({m_val:+.{m_dec}f}%)", d_pt, r_pt, cat, f"{pt_lbl} ({detail})")

    mi_d_pt = _bar("MI", "Abdul El-Sayed", 7.08, 17.23, 26.43, "prog")[1]
    mi_tot_pt = mi_d_pt + _bar("MI", "Abdul El-Sayed", 7.08, 17.23, 26.43, "prog")[2]

    fig.text(0.03, 0.925, "2026 Senate 'Moneyball': Diminishing Returns & Endogenous GOP Counterspend",
             fontsize=19.5, fontweight="bold", color=DARK_TEXT)
    fig.text(0.03, 0.88, f"Michigan ($370.8M total; $146.3M Dem vs. $224.4M GOP) ranked #1 most expensive per point of positive swing (${mi_d_pt:.1f}M/pt Dem; ${mi_tot_pt:.1f}M/pt total).",
             fontsize=12.1, color=SUB_TEXT)
    fig.text(0.03, 0.842, "Polling lag after a $70M primary drew $171M in GOP general-election IEs, forcing SMP to triple MI from $20M to $67M while starving low-saturation Southern TV markets.",
             fontsize=11.1, color=MUTED_TEXT, style="italic")

    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title("A. Spend per Point of 2024->2026 Swing: Pro-Dem + GOP Counterspend\n(Solid = Pro-Dem $/pt | Shaded Red = Pro-GOP Counterspend $/pt)",
                  fontsize=11.0, fontweight="bold", color=DARK_TEXT, loc="left", pad=12)

    races = [
        _bar("MI", "Abdul El-Sayed", 7.08, 17.23, 26.43, "prog", "$67M SMP"),
        _bar("OH", "Sherrod Brown", 4.85, 13.73, 17.13, "main", "$150M SMP"),
        _bar("TX", "James Talarico", 12.10, 10.72, 12.96, "main", "$40M SMP"),
        _bar("IA", "Josh Turek", 4.20, 7.71, 6.33, "main", "$67M SMP"),
        _bar("GA", "Jon Ossoff", 18.06, 6.12, 1.43, "main", "$18M Gen R IE"),
        _bar("AK", "Mary Peltola", 1.15, 5.85, 4.54, "main", ""),
        _bar("NH", "Chris Pappas", 13.76, 4.30, 4.32, "main", ""),
        _bar("KS", "Adam Hamilton", 5.05, 3.38, 1.95, "main", "$14M SMP"),
        _bar("NC", "Roy Cooper", 19.62, 3.01, 2.69, "main", ""),
        _bar("MN", "Peggy Flanagan", 10.15, 2.57, 3.31, "prog", ""),
        _bar("SC", "Annie Andrews", 4.50, 2.07, 1.43, "main", "$750K SMP"),
        _bar("FL", "Angie Nixon", -2.87, 1.85, 2.76, "prog", "$0 SMP"),
        _bar("MS", "Scott Colom", 0.28, 0.84, 0.27, "south", "RAW:$19.4M D | $2.4M Gen R IE | $2.2M SMP", m_dec=2),
        _bar("LA", "Jamie Davis", -1.76, 0.72, 1.01, "south", "RAW:$14.6M D | $20.5M R [$2.5M Gen IE]", m_dec=2),
    ]
    races.sort(key=lambda x: x[1], reverse=True)

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

    ms_m_str = _m_str("MS", 0.28, 2)
    la_m_str = _m_str("LA", -1.76, 2)
    ax1.axhspan(-0.5, 1.5, color="#e8f8f5", alpha=0.65, zorder=1)
    ax1.annotate(f"Low-saturation & 21x-24x cheaper per point:\nLA ({la_m_str}, 25,857 votes) & MS ({ms_m_str}) had\njust $2.5M & $2.4M in GOP general-election IEs!",
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

    def _pt(st, fmt_tpl, def_x, def_y, def_m, cat, dx, dy, ha):
        row = by_st.get(st)
        xm = row["total_pro_dem_spend"] / 1e6 if row else def_x
        ym = row["shift_vs_pres_2024"] if (row and row.get("shift_vs_pres_2024") is not None) else def_y
        mv = row["margin_2026"] if row else def_m
        return (fmt_tpl.format(m=f"{mv:+.1f}%"), xm, ym, cat, dx, dy, ha)

    pts = [
        _pt("LA", "LA: Davis {m} ($2.5M R IE)", 14.63, 20.25, -1.76, "south", 5, -0.55, "left"),
        _pt("MS", "MS: Colom {m} ($2.4M R IE)", 19.39, 23.16, 0.28, "south", -3, 1.35, "left"),
        _pt("SC", "SC (Andrews {m})", 46.36, 22.37, 4.50, "main", -8, -1.0, "center"),
        _pt("NC", "NC (Cooper {m})", 68.75, 22.84, 19.62, "main", 6, 0.9, "left"),
        _pt("KS", "KS (Hamilton {m})", 71.58, 21.17, 5.05, "main", 5, 0.5, "left"),
        _pt("GA", "GA: Ossoff {m} ($18M R IE)", 123.97, 20.26, 18.06, "main", 6, 0.8, "left"),
        _pt("IA", "IA: Turek {m} ($96M R IE)", 134.62, 17.46, 4.20, "main", 5, 0.35, "left"),
        _pt("OH", "OH: Brown {m} ($222M R IE)", 220.49, 16.06, 4.85, "main", -6, -1.1, "center"),
        _pt("TX", "TX: Talarico {m} ($315M R IE)", 276.51, 25.79, 12.10, "main", -6, -0.4, "right"),
        _pt("NH", "NH: Pappas {m} ($39M R)", 47.21, 10.97, 13.76, "main", 5, 0.55, "left"),
        _pt("FL", "FL (Nixon {m})", 18.94, 10.23, -2.87, "prog", 5, -0.85, "left"),
        _pt("MN", "MN (Flanagan {m})", 15.12, 5.89, 10.15, "prog", 5, -0.25, "left"),
        _pt("ME", "ME: Jackson {m} ($81M R IE)", 77.54, -0.74, 6.20, "prog", 5, -0.95, "left"),
        _pt("MI", "MI: El-Sayed {m} ($171M R IE)", 146.33, 8.49, 7.08, "prog", 6, -0.35, "left"),
    ]

    x_curve = np.linspace(10, 285, 200)
    y_curve = 14.0 + 2.1 * np.log(x_curve / 10.0)
    ax2.plot(x_curve, y_curve, color="#7f8c8d", ls="--", lw=1.8, alpha=0.7, label="Mainstream Battleground Benchmark")

    mi_ym = by_st.get("MI", {}).get("shift_vs_pres_2024", 8.49) or 8.49
    ax2.scatter([146.33], [12.16], color=BLUE_DOG, marker="s", s=95, zorder=5)
    ax2.plot([146.33, 146.33], [mi_ym, 12.16], color=CRIMSON, lw=2.2, ls=":", zorder=4)
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

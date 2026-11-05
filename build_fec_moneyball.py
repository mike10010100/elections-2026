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
    pres24 = r.get("pres_2024_margin")
    sh24_pres = (m26 - pres24) if pres24 is not None else None

    if office_char == "H":
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
    print(f"Saved {len(senate_rows)} Senate races and {len(house_rows)} House races.")


if __name__ == "__main__":
    main()

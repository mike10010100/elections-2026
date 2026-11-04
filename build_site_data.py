#!/usr/bin/env python3
"""
Compiles raw 2024 & 2026 election results from:
- data/latest.json (civicAPI 39,474 races)
- data/results_2024_11_05.json (civicAPI 2024 races)
- data/nyt_2024/*.json (NYT 2024 national & 50-state results)
- data/nyt_2026/*.json (NYT 2026 national & 50-state results)

into compact, structured static JSON files in site_data/ for the GitHub Pages interactive web app.
"""
import collections
import datetime
import glob
import json
import shutil
import statistics
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SITE_DATA_DIR = BASE_DIR / "site_data"
STATES_RACES_DIR = SITE_DATA_DIR / "states"

STATE_FIPS_TO_POSTAL = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO",
    "09": "CT", "10": "DE", "11": "DC", "12": "FL", "13": "GA", "15": "HI",
    "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
    "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH",
    "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
    "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD",
    "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY",
}
POSTAL_TO_STATE_FIPS = {v: k for k, v in STATE_FIPS_TO_POSTAL.items()}

AP_STATE_ABBR = {
    "AL": "Ala.", "AK": "Alaska", "AZ": "Ariz.", "AR": "Ark.", "CA": "Calif.",
    "CO": "Colo.", "CT": "Conn.", "DE": "Del.", "DC": "D.C.", "FL": "Fla.",
    "GA": "Ga.", "HI": "Hawaii", "ID": "Idaho", "IL": "Ill.", "IN": "Ind.",
    "IA": "Iowa", "KS": "Kan.", "KY": "Ky.", "LA": "La.", "ME": "Maine",
    "MD": "Md.", "MA": "Mass.", "MI": "Mich.", "MN": "Minn.", "MS": "Miss.",
    "MO": "Mo.", "MT": "Mont.", "NE": "Neb.", "NV": "Nev.", "NH": "N.H.",
    "NJ": "N.J.", "NM": "N.M.", "NY": "N.Y.", "NC": "N.C.", "ND": "N.D.",
    "OH": "Ohio", "OK": "Okla.", "OR": "Ore.", "PA": "Pa.", "RI": "R.I.",
    "SC": "S.C.", "SD": "S.D.", "TN": "Tenn.", "TX": "Texas", "UT": "Utah",
    "VT": "Vt.", "VA": "Va.", "WA": "Wash.", "WV": "W.Va.", "WI": "Wis.",
    "WY": "Wyo.",
}

# Governors not up for election in 2026 (14 states: DE, IN, KY, LA, MO, MS, MT, NC, ND, NJ, UT, VA, WA, WV)
GOV_NO_ELECTION_2026 = {
    "DE": "DEM", "IN": "GOP", "KY": "DEM", "LA": "GOP", "MO": "GOP",
    "MS": "GOP", "MT": "GOP", "NC": "DEM", "ND": "GOP", "NJ": "DEM",
    "UT": "GOP", "VA": "DEM", "WA": "DEM", "WV": "GOP",
}


def load_nyt_races(folder_name: str) -> list[dict]:
    races_by_id = {}
    folder = DATA_DIR / folder_name
    for p in sorted(folder.glob("results-*.json")):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for r in d.get("races", []):
            nid = r.get("nyt_id")
            if not nid:
                continue
            existing = races_by_id.get(nid)
            if not existing or len(r.get("reporting_units", [])) >= len(existing.get("reporting_units", [])):
                races_by_id[nid] = r
    return list(races_by_id.values())


def normalize_party(party_id: str | dict | None, caucus: str | dict | None = None) -> str:
    if isinstance(party_id, dict):
        party_id = party_id.get("nyt_id") or party_id.get("name") or ""
    if isinstance(caucus, dict):
        caucus = caucus.get("nyt_id") or caucus.get("name") or ""
    p = str(party_id or "").upper()
    c = str(caucus or "").upper()
    if p in ("DEM", "DEMOCRAT", "DEMOCRATIC") or c == "DEM":
        return "DEM"
    if p in ("GOP", "REP", "REPUBLICAN") or c == "GOP":
        return "GOP"
    if p in ("YES", "NO"):
        return p
    if p in ("IND", "INDEPENDENT"):
        return "IND"
    if p in ("LIB", "LIBERTARIAN"):
        return "LIB"
    if p in ("GRN", "GREEN"):
        return "GRN"
    return p or "OTH"


def extract_race_summary(r: dict) -> dict:
    cmeta = r.get("candidate_metadata") or {}
    top_unit = r.get("top_reporting_unit") or {}
    if not top_unit and r.get("reporting_units"):
        state_units = [u for u in r["reporting_units"] if u.get("level") in ("state", "national")]
        top_unit = state_units[0] if state_units else r["reporting_units"][0]

    total_votes = top_unit.get("total_votes") or 0
    expected_votes = top_unit.get("total_expected_vote") or total_votes
    eevp = top_unit.get("eevp")
    if eevp is None:
        eevp = round(100 * total_votes / expected_votes) if expected_votes > 0 else 0

    outcome = r.get("outcome") or {}
    won_ids = set(outcome.get("won") or [])
    lead_ids = set(outcome.get("leading") or [])
    runoff_ids = set(outcome.get("runoff") or [])

    candidates = []
    for c in top_unit.get("candidates") or []:
        cid = c.get("nyt_id")
        if cid == "undervote" or cid == "overvote":
            continue
        m = cmeta.get(cid) or {}
        pty_obj = m.get("party") or {}
        norm_pty = normalize_party(pty_obj.get("nyt_id"), m.get("party_caucus"))
        v = (c.get("votes") or {}).get("total") or 0
        pct = round(100.0 * v / total_votes, 2) if total_votes > 0 else 0.0
        fname = m.get("first_name") or ""
        lname = m.get("last_name") or cid or ""
        full_name = f"{fname} {lname}".strip()
        candidates.append({
            "id": cid,
            "name": full_name,
            "last_name": lname,
            "party": norm_pty,
            "party_label": pty_obj.get("abbreviation") or norm_pty,
            "incumbent": bool(m.get("incumbent")),
            "img_url": m.get("img_url"),
            "votes": v,
            "percent": pct,
            "winner": bool(c.get("winner")) or (cid in won_ids),
            "leading": cid in lead_ids,
            "runoff": cid in runoff_ids,
        })

    candidates.sort(key=lambda x: (x["winner"], x["votes"]), reverse=True)

    dem_cand = next((c for c in candidates if c["party"] == "DEM"), None)
    gop_cand = next((c for c in candidates if c["party"] == "GOP"), None)
    dem_pct = dem_cand["percent"] if dem_cand else 0.0
    gop_pct = gop_cand["percent"] if gop_cand else 0.0
    dem_gop_margin = round(dem_pct - gop_pct, 2)

    top_margin_pct = 0.0
    top_margin_votes = 0
    if len(candidates) >= 2:
        top_margin_pct = round(candidates[0]["percent"] - candidates[1]["percent"], 2)
        top_margin_votes = candidates[0]["votes"] - candidates[1]["votes"]
    elif len(candidates) == 1:
        top_margin_pct = 100.0
        top_margin_votes = candidates[0]["votes"]

    called = any(c["winner"] for c in candidates) or r.get("race_call_status") == "Called"
    winner_cand = next((c for c in candidates if c["winner"]), None)
    leader_cand = winner_cand or (candidates[0] if candidates else None)

    state_postal = top_unit.get("state_postal") or (r.get("nyt_id") or "")[:2]
    seat = r.get("seat") or ""
    seat_num = r.get("seat_number")

    return {
        "nyt_id": r.get("nyt_id"),
        "office": r.get("office"),
        "office_id": r.get("office_id"),
        "state": state_postal,
        "state_fips": POSTAL_TO_STATE_FIPS.get(state_postal, ""),
        "seat": seat,
        "seat_number": seat_num,
        "type": r.get("type"),
        "uncontested": bool(r.get("uncontested")),
        "incumbent_party": normalize_party((r.get("party") or {}).get("nyt_id")),
        "rating": r.get("general_rating") or r.get("rating"),
        "called": called,
        "race_call_status": r.get("race_call_status"),
        "party_flip": outcome.get("party_flip"),
        "eevp": eevp,
        "total_votes": total_votes,
        "expected_votes": expected_votes,
        "remaining_votes": max(0, expected_votes - total_votes),
        "precincts_reporting": top_unit.get("precincts_reporting") or 0,
        "precincts_total": top_unit.get("precincts_total") or 0,
        "dem_gop_margin": dem_gop_margin,
        "top_margin_pct": top_margin_pct,
        "top_margin_votes": top_margin_votes,
        "winner_party": winner_cand["party"] if winner_cand else None,
        "leader_party": leader_cand["party"] if leader_cand else None,
        "candidates": candidates[:6],
        "ballot_measure_text": r.get("ballot_measure_text"),
        "long_description": r.get("long_description"),
        "seat_description": r.get("seat_description"),
    }


def extract_county_office_data(races: list[dict], target_office: str) -> dict[str, dict]:
    counties = {}
    for r in races:
        if r.get("office") != target_office:
            continue
        # For Senate in states with two races (regular + special, e.g., if any), prefer General over Special
        cmeta = r.get("candidate_metadata") or {}
        party_map = {}
        name_map = {}
        for cid, m in cmeta.items():
            pty = normalize_party((m.get("party") or {}).get("nyt_id"), m.get("party_caucus"))
            party_map[cid] = pty
            name_map[cid] = f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()

        units = r.get("reporting_units") or []
        has_county = any(u.get("level") == "county" for u in units)
        for u in units:
            lvl = u.get("level")
            if has_county and lvl != "county":
                continue
            if not has_county and lvl not in ("county", "township"):
                continue
            fs = u.get("fips_state")
            fc = u.get("fips_county")
            if not fs or not fc:
                continue
            fips = f"{fs}{fc}"
            tv = u.get("total_votes") or 0
            ev = u.get("total_expected_vote") or tv
            eevp = u.get("eevp")
            if eevp is None:
                eevp = round(100 * tv / ev) if ev > 0 else 0

            dem_v = 0
            gop_v = 0
            ind_v = 0
            dem_n = ""
            gop_n = ""
            ind_n = ""
            for c in u.get("candidates") or []:
                cid = c.get("nyt_id")
                if cid in ("undervote", "overvote"):
                    continue
                v = (c.get("votes") or {}).get("total") or 0
                pty = party_map.get(cid, "OTH")
                if pty == "DEM":
                    if v >= dem_v and name_map.get(cid):
                        dem_n = name_map[cid]
                    dem_v += v
                elif pty == "GOP":
                    if v >= gop_v and name_map.get(cid):
                        gop_n = name_map[cid]
                    gop_v += v
                elif pty == "IND":
                    if v >= ind_v and name_map.get(cid):
                        ind_n = name_map[cid]
                    ind_v += v

            if fips not in counties:
                counties[fips] = {
                    "state": u.get("state_postal"),
                    "name": u.get("name") if lvl == "county" else "",
                    "dem_v": 0,
                    "gop_v": 0,
                    "ind_v": 0,
                    "tot_v": 0,
                    "exp_v": 0,
                    "eevp_sum": 0,
                    "eevp_cnt": 0,
                    "dem_n": dem_n,
                    "gop_n": gop_n,
                    "ind_n": ind_n,
                }
            rec = counties[fips]
            if lvl == "county" and u.get("name"):
                rec["name"] = u["name"]
            if dem_n and not rec["dem_n"]:
                rec["dem_n"] = dem_n
            if gop_n and not rec["gop_n"]:
                rec["gop_n"] = gop_n
            if ind_n and not rec["ind_n"]:
                rec["ind_n"] = ind_n
            rec["dem_v"] += dem_v
            rec["gop_v"] += gop_v
            rec["ind_v"] += ind_v
            rec["tot_v"] += tv
            rec["exp_v"] += ev
            rec["eevp_sum"] += eevp
            rec["eevp_cnt"] += 1

    out = {}
    for fips, rec in counties.items():
        tot = rec["tot_v"]
        dem_pct = round(100.0 * rec["dem_v"] / tot, 2) if tot > 0 else 0.0
        gop_pct = round(100.0 * rec["gop_v"] / tot, 2) if tot > 0 else 0.0
        ind_pct = round(100.0 * rec["ind_v"] / tot, 2) if tot > 0 else 0.0
        margin = round(dem_pct - gop_pct, 2)
        eevp = round(rec["eevp_sum"] / rec["eevp_cnt"]) if rec["eevp_cnt"] > 0 else 0
        out[fips] = {
            "state": rec["state"],
            "name": rec["name"],
            "dem_v": rec["dem_v"],
            "gop_v": rec["gop_v"],
            "ind_v": rec["ind_v"],
            "tot_v": tot,
            "exp_v": rec["exp_v"],
            "dem_pct": dem_pct,
            "gop_pct": gop_pct,
            "ind_pct": ind_pct,
            "margin": margin,
            "eevp": min(100, eevp),
            "dem_n": rec["dem_n"],
            "gop_n": rec["gop_n"],
            "ind_n": rec["ind_n"],
        }
    return out


def build_all():
    SITE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATES_RACES_DIR.mkdir(parents=True, exist_ok=True)

    # Copy TopoJSON into site_data
    topo_src = DATA_DIR / "counties-albers-10m.json"
    topo_dst = SITE_DATA_DIR / "counties-albers-10m.json"
    if topo_src.exists():
        shutil.copy2(topo_src, topo_dst)

    with open(topo_src, encoding="utf-8") as f:
        topo = json.load(f)
    topo_county_names = {
        g["id"]: (g.get("properties") or {}).get("name", "")
        for g in topo["objects"]["counties"]["geometries"]
    }

    print("Loading NYT 2024 and 2026 races...")
    races_24 = load_nyt_races("nyt_2024")
    races_26 = load_nyt_races("nyt_2026")

    # Extract race summaries
    summaries_24 = [extract_race_summary(r) for r in races_24]
    summaries_26 = [extract_race_summary(r) for r in races_26]

    # Index 2024 summaries by (office, state, seat_number/seat)
    house_24_by_key = {}
    senate_24_by_state = {}
    pres_24_by_state = {}
    gov_24_by_state = {}
    for s in summaries_24:
        off = s["office"]
        st = s["state"]
        if off == "U.S. House":
            key = f"{st}-{s['seat_number'] or s['seat']}"
            house_24_by_key[key] = s
        elif off == "U.S. Senate":
            senate_24_by_state[st] = s
        elif off == "President":
            pres_24_by_state[st] = s
        elif off == "Governor":
            gov_24_by_state[st] = s

    # Build 2026 Senate, Governor, House lists with 2024 comparisons
    senate_26 = []
    governor_26 = []
    house_26 = []
    measures_26 = []
    statewide_exec_26 = []

    for s in summaries_26:
        off = s["office"]
        st = s["state"]
        p24 = pres_24_by_state.get(st)
        s["pres_2024_margin"] = p24["dem_gop_margin"] if p24 else None
        if p24 and (s["dem_gop_margin"] != 0):
            s["shift_vs_pres_2024"] = round(s["dem_gop_margin"] - p24["dem_gop_margin"], 2)
        else:
            s["shift_vs_pres_2024"] = None

        if off == "U.S. Senate":
            senate_26.append(s)
        elif off == "Governor":
            governor_26.append(s)
        elif off == "U.S. House" and s["nyt_id"] != "US-G-H-2026-11-03":
            key = f"{st}-{s['seat_number'] or s['seat']}"
            h24 = house_24_by_key.get(key)
            if h24:
                s["margin_2024_house"] = h24["dem_gop_margin"]
                s["winner_2024_party"] = h24["winner_party"] or h24["leader_party"]
                s["shift_vs_house_2024"] = round(s["dem_gop_margin"] - h24["dem_gop_margin"], 2)
            else:
                s["margin_2024_house"] = None
                s["winner_2024_party"] = s["incumbent_party"]
                s["shift_vs_house_2024"] = None
            house_26.append(s)
        elif off in ("Amendment", "Proposition", "Question", "Constitutional Amendment", "Measure", "Referendum", "Initiative", "Bond Measure", "State Question"):
            measures_26.append(s)
        elif off in ("Attorney General", "Secretary of State", "Treasurer", "Lieutenant Governor", "Controller", "Auditor", "Supreme Court"):
            statewide_exec_26.append(s)

    senate_26.sort(key=lambda x: (x["called"], x["top_margin_pct"]))
    governor_26.sort(key=lambda x: (x["called"], x["top_margin_pct"]))
    house_26.sort(key=lambda x: (x["called"], x["top_margin_pct"]))
    measures_26.sort(key=lambda x: (x["state"], x["seat"]))
    statewide_exec_26.sort(key=lambda x: (x["state"], x["office"]))

    # Load NYT partyControlData for Senate, House, and State Legislatures
    with open(DATA_DIR / "nyt_2026" / "results-senate.json", encoding="utf-8") as f:
        sen_pc = json.load(f).get("partyControlData", {}).get("results", [{}])[0].get("offices", {}).get("S", {})
    with open(DATA_DIR / "nyt_2026" / "results-house.json", encoding="utf-8") as f:
        house_pc = json.load(f).get("partyControlData", {}).get("results", [{}])[0].get("offices", {}).get("H", {})

    # Compute detailed Senate, House, and Governor balance of power
    sen_dem_called = sum(1 for r in senate_26 if r["called"] and r["winner_party"] == "DEM")
    sen_gop_called = sum(1 for r in senate_26 if r["called"] and r["winner_party"] == "GOP")
    sen_dem_lead = sum(1 for r in senate_26 if not r["called"] and r["leader_party"] == "DEM")
    sen_gop_lead = sum(1 for r in senate_26 if not r["called"] and r["leader_party"] == "GOP")
    sen_flips = [r for r in senate_26 if r.get("party_flip") or (r["incumbent_party"] in ("DEM", "GOP") and (r["winner_party"] or r["leader_party"]) != r["incumbent_party"])]

    house_dem_called = sum(1 for r in house_26 if r["called"] and r["winner_party"] == "DEM")
    house_gop_called = sum(1 for r in house_26 if r["called"] and r["winner_party"] == "GOP")
    house_dem_lead = sum(1 for r in house_26 if not r["called"] and r["leader_party"] == "DEM")
    house_gop_lead = sum(1 for r in house_26 if not r["called"] and r["leader_party"] == "GOP")
    house_flips = [r for r in house_26 if r.get("party_flip") or (r["incumbent_party"] in ("DEM", "GOP") and (r["winner_party"] or r["leader_party"]) in ("DEM", "GOP") and (r["winner_party"] or r["leader_party"]) != r["incumbent_party"])]

    gov_dem_no_el = sum(1 for p in GOV_NO_ELECTION_2026.values() if p == "DEM")
    gov_gop_no_el = sum(1 for p in GOV_NO_ELECTION_2026.values() if p == "GOP")
    gov_dem_called = sum(1 for r in governor_26 if r["called"] and r["winner_party"] == "DEM")
    gov_gop_called = sum(1 for r in governor_26 if r["called"] and r["winner_party"] == "GOP")
    gov_dem_lead = sum(1 for r in governor_26 if not r["called"] and r["leader_party"] == "DEM")
    gov_gop_lead = sum(1 for r in governor_26 if not r["called"] and r["leader_party"] == "GOP")
    gov_flips = [r for r in governor_26 if r.get("party_flip") or (r["incumbent_party"] in ("DEM", "GOP") and (r["winner_party"] or r["leader_party"]) != r["incumbent_party"])]

    # Collect state legislative chamber balances
    state_chambers = []
    for p in sorted((DATA_DIR / "nyt_2026").glob("results-*.json")):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        for res in (d.get("partyControlData") or {}).get("results", []):
            st = res.get("state_postal")
            if st and st != "US":
                for k, v in (res.get("offices") or {}).items():
                    pb = v.get("party_balance") or {}
                    dem = pb.get("DEM", {})
                    gop = pb.get("GOP", {})
                    state_chambers.append({
                        "state": st,
                        "chamber_id": k,
                        "office": v.get("office"),
                        "total": v.get("total"),
                        "called": v.get("num_races_called"),
                        "dem_seats": dem.get("seats", 0),
                        "dem_flips": dem.get("flip_count", 0),
                        "dem_winner": bool(dem.get("winner")),
                        "gop_seats": gop.get("seats", 0),
                        "gop_flips": gop.get("flip_count", 0),
                        "gop_winner": bool(gop.get("winner")),
                    })

    # Build county-by-county shifts across 2024 President, 2026 Senate, 2026 Governor, 2026 House, 2026 AG
    print("Building county-level shift dataset...")
    c_p24 = extract_county_office_data(races_24, "President")
    c_s24 = extract_county_office_data(races_24, "U.S. Senate")
    c_s26 = extract_county_office_data(races_26, "U.S. Senate")
    c_g26 = extract_county_office_data(races_26, "Governor")
    c_h26 = extract_county_office_data(races_26, "U.S. House")
    c_ag26 = extract_county_office_data(races_26, "Attorney General")

    all_fips = sorted(set(c_p24.keys()) | set(c_s26.keys()) | set(c_g26.keys()) | set(c_h26.keys()))
    counties_payload = {}
    for fips in all_fips:
        p24 = c_p24.get(fips)
        s24 = c_s24.get(fips)
        s26 = c_s26.get(fips)
        g26 = c_g26.get(fips)
        h26 = c_h26.get(fips)
        ag26 = c_ag26.get(fips)

        state_code = (
            (p24 and p24["state"])
            or (h26 and h26["state"])
            or (s26 and s26["state"])
            or (g26 and g26["state"])
            or STATE_FIPS_TO_POSTAL.get(fips[:2], "")
        )
        cname = (
            topo_county_names.get(fips)
            or (p24 and p24["name"])
            or (s26 and s26["name"])
            or (h26 and h26["name"])
            or fips
        )

        entry = {
            "fips": fips,
            "state": state_code,
            "name": cname,
        }
        if p24 and p24["tot_v"] > 0:
            entry["p24"] = {
                "d": p24["dem_pct"],
                "r": p24["gop_pct"],
                "m": p24["margin"],
                "v": p24["tot_v"],
            }
        if s24 and s24["tot_v"] > 0:
            entry["s24"] = {
                "d": s24["dem_pct"],
                "r": s24["gop_pct"],
                "m": s24["margin"],
                "v": s24["tot_v"],
            }
        for key, rec in [("s26", s26), ("g26", g26), ("h26", h26), ("ag26", ag26)]:
            if rec and rec["tot_v"] > 0:
                has_both_parties = rec["dem_v"] > 0 and rec["gop_v"] > 0
                shift_p24 = (
                    round(rec["margin"] - p24["margin"], 2)
                    if (p24 and p24["tot_v"] > 0 and has_both_parties)
                    else None
                )
                entry[key] = {
                    "d": rec["dem_pct"],
                    "r": rec["gop_pct"],
                    "i": rec["ind_pct"],
                    "m": rec["margin"],
                    "v": rec["tot_v"],
                    "ev": rec["exp_v"],
                    "rem": max(0, rec["exp_v"] - rec["tot_v"]),
                    "eevp": rec["eevp"],
                    "dn": rec["dem_n"],
                    "rn": rec["gop_n"],
                    "in": rec["ind_n"],
                    "sp24": shift_p24,
                }
        counties_payload[fips] = entry

    with open(SITE_DATA_DIR / "county_shifts.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "count": len(counties_payload),
                "ap_abbr": AP_STATE_ABBR,
                "state_fips_to_postal": STATE_FIPS_TO_POSTAL,
                "counties": counties_payload,
            },
            f,
            separators=(",", ":"),
        )

    # Process civicAPI 39,474 races (data/latest.json)
    print("Indexing civicAPI 39,474 races by state & category...")
    with open(DATA_DIR / "latest.json", encoding="utf-8") as f:
        civic_data = json.load(f)
    civic_races = civic_data.get("races", [])
    fetched_at = civic_data.get("fetched_at") or datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

    civic_by_state = collections.defaultdict(list)
    civic_type_counts = collections.Counter()
    civic_called_total = 0
    close_races_all = []

    for r in civic_races:
        st = r.get("province") or "US"
        rtype = r.get("type") or "Other"
        civic_type_counts[rtype] += 1
        cands = sorted(r.get("candidates") or [], key=lambda c: c.get("votes", 0), reverse=True)
        called = any(c.get("winner") for c in cands)
        if called:
            civic_called_total += 1
        tot_v = sum(c.get("votes", 0) for c in cands)
        margin_pct = (
            round((cands[0].get("percent", 0) or 0) - (cands[1].get("percent", 0) or 0), 2)
            if len(cands) >= 2
            else 100.0
        )
        margin_votes = (
            (cands[0].get("votes", 0) or 0) - (cands[1].get("votes", 0) or 0)
            if len(cands) >= 2
            else tot_v
        )
        compact_r = {
            "id": r.get("id"),
            "type": rtype,
            "state": st,
            "district": r.get("district"),
            "municipality": r.get("municipality"),
            "name": r.get("election_name"),
            "election_type": r.get("election_type"),
            "rep": r.get("percent_reporting", 0),
            "called": called,
            "tot_v": tot_v,
            "m_pct": margin_pct,
            "m_v": margin_votes,
            "cands": [
                {
                    "n": c.get("name"),
                    "p": c.get("party"),
                    "v": c.get("votes", 0),
                    "pct": c.get("percent", 0),
                    "w": bool(c.get("winner")),
                }
                for c in cands[:4]
            ],
        }
        civic_by_state[st].append(compact_r)
        if not called and len(cands) >= 2 and tot_v >= 1000 and margin_pct <= 2.0:
            close_races_all.append(compact_r)

    close_races_all.sort(key=lambda x: (x["m_pct"], -x["tot_v"]))

    state_counts_index = {}
    for st, rlist in civic_by_state.items():
        rlist.sort(key=lambda x: (-x["tot_v"], x["name"] or ""))
        state_counts_index[st] = {
            "total": len(rlist),
            "called": sum(1 for x in rlist if x["called"]),
        }
        safe_st = "".join(ch for ch in st if ch.isalnum() or ch in ("_", "-")) or "OTHER"
        with open(STATES_RACES_DIR / f"{safe_st}.json", "w", encoding="utf-8") as f:
            json.dump({"state": st, "count": len(rlist), "races": rlist}, f, separators=(",", ":"))

    overview = {
        "fetched_at": fetched_at,
        "summary_counts": {
            "civic_total_races": len(civic_races),
            "civic_called_races": civic_called_total,
            "civic_uncalled_races": len(civic_races) - civic_called_total,
            "nyt_2026_races": len(summaries_26),
            "nyt_2024_races": len(summaries_24),
            "counties_tracked": len(counties_payload),
            "top_race_types": civic_type_counts.most_common(40),
            "states_index": state_counts_index,
        },
        "chamber_control": {
            "senate": {
                "total": 100,
                "majority": 51,
                "gop_control_threshold": 50,
                "up_in_2026": 35,
                "dem_no_election": 34,
                "gop_no_election": 31,
                "dem_called": sen_dem_called,
                "gop_called": sen_gop_called,
                "dem_leading": sen_dem_lead,
                "gop_leading": sen_gop_lead,
                "dem_total_called": 34 + sen_dem_called,
                "gop_total_called": 31 + sen_gop_called,
                "dem_projected_total": 34 + sen_dem_called + sen_dem_lead,
                "gop_projected_total": 31 + sen_gop_called + sen_gop_lead,
                "dem_flips": sen_pc.get("party_balance", {}).get("DEM", {}).get("flip_count", len(sen_flips)),
                "gop_flips": sen_pc.get("party_balance", {}).get("GOP", {}).get("flip_count", 0),
                "model_estimates": sen_pc.get("nyt_model_estimates", []),
                "seat_probabilities": (sen_pc.get("nyt_model_chamber") or {}).get("seat_combination_probabilities", []),
            },
            "house": {
                "total": 435,
                "majority": 218,
                "dem_called": house_dem_called,
                "gop_called": house_gop_called,
                "dem_leading": house_dem_lead,
                "gop_leading": house_gop_lead,
                "uncalled": 435 - (house_dem_called + house_gop_called),
                "dem_projected_total": house_dem_called + house_dem_lead,
                "gop_projected_total": house_gop_called + house_gop_lead,
                "dem_flips": house_pc.get("party_balance", {}).get("DEM", {}).get("flip_count", 0),
                "gop_flips": house_pc.get("party_balance", {}).get("GOP", {}).get("flip_count", 0),
                "model_estimates": house_pc.get("nyt_model_estimates", []),
            },
            "governor": {
                "total": 50,
                "majority": 26,
                "up_in_2026": 36,
                "dem_no_election": gov_dem_no_el,
                "gop_no_election": gov_gop_no_el,
                "dem_called": gov_dem_called,
                "gop_called": gov_gop_called,
                "dem_leading": gov_dem_lead,
                "gop_leading": gov_gop_lead,
                "dem_total_called": gov_dem_no_el + gov_dem_called,
                "gop_total_called": gov_gop_no_el + gov_gop_called,
                "dem_projected_total": gov_dem_no_el + gov_dem_called + gov_dem_lead,
                "gop_projected_total": gov_gop_no_el + gov_gop_called + gov_gop_lead,
                "no_election_map": GOV_NO_ELECTION_2026,
            },
            "state_chambers": state_chambers,
        },
        "senate_races": senate_26,
        "governor_races": governor_26,
        "house_races": house_26,
        "measures_races": measures_26,
        "statewide_exec_races": statewide_exec_26,
        "close_races_all_levels": close_races_all[:150],
    }

    with open(SITE_DATA_DIR / "overview.json", "w", encoding="utf-8") as f:
        json.dump(overview, f, separators=(",", ":"))

    print("Done! Generated site_data/ files:")
    for p in sorted(SITE_DATA_DIR.glob("*.json")):
        print(f"  {p.name}: {p.stat().st_size / 1024:.1f} KB")


if __name__ == "__main__":
    build_all()

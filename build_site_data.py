#!/usr/bin/env python3
"""
Compiles and normalizes 22 years (2004–2026) of U.S. election results and county demographics from:
- data/latest.json (civicAPI 39,474 live 2026 races)
- data/nyt_2026/*.json (NYT 2026 national & 50-state results + county returns + demographic blurbs)
- data/nyt_2024/*.json (NYT 2024 national & 50-state results + county returns)
- data/historical/us_county_results_summary.csv (2004–2024 county-level returns for President, Senate, House)
- data/historical/538_election_results_*.csv (2004–2024 candidate-level results for Governor, Senate, House, President)
- data/historical/county_demographics.csv (U.S. Census county demographics across 3,139 counties)

Strict Data Hygiene & Normalization Rules Enforced:
1. ME & NE Presidential Congressional District sub-races (ME-CD1/CD2, NE-CD1/2/3) are excluded from statewide/county
   Presidential aggregations so they never overwrite statewide totals or double-count counties.
2. Concurrent Regular + Special Senate elections on the same ballot (e.g. CA 2024, NE 2024, GA 2020, OK 2022)
   prefer the Regular full-term election for county maps and never sum two Senate races in the same county.
3. Split-county U.S. House EEVP is weighted by expected vote (100 * tot_v / exp_v) rather than unweighted district means.
4. Uncontested or single-party general elections (e.g. Top-Two Dem-vs-Dem or Rep-vs-Rep) are flagged (`op: 1`)
   so they do not distort two-party shift arrows or median/mean shift metrics.
5. Ranked-Choice Voting (AK, ME) historical feeds filter strictly to Round 1 (`ranked_choice_round in ('', '1')`)
   so RCV tabulation rounds are never summed together.
6. Fusion-ticket voting (NY, CT, SC, VT) aggregates multiple party ballot lines (e.g. DEM + WFP, REP + CON) by candidate
   before computing vote shares, and excludes blank/undervote/overvote rows.
7. civicAPI national summary rollup rows (IDs 87528, 87524) are separated from state/district race counts.
"""
import collections
import csv
import datetime
import json
import re
import shutil
import unicodedata
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
HIST_DIR = DATA_DIR / "historical"
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

STATE_NAME_TO_POSTAL = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "district of columbia": "DC",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
    "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA",
    "maine": "ME", "maryland": "MD", "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD",
    "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT", "virginia": "VA",
    "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}

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

# National rollup race IDs in civicAPI to exclude from individual race/seat counts
CIVIC_NATIONAL_ROLLUP_IDS = {87528, 87524}


def load_nyt_races(folder_name: str) -> tuple[list[dict], dict[str, str]]:
    """Loads deduplicated NYT races and county demographic blurbs."""
    races_by_id = {}
    county_blurbs = {}
    folder = DATA_DIR / folder_name
    for p in sorted(folder.glob("results-*.json")):
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        ds = d.get("demographicSentences")
        if isinstance(ds, list):
            for item in ds:
                if not isinstance(item, dict):
                    continue
                uid = item.get("nyt_reporting_unit_id") or ""
                sent = item.get("string_value") or ""
                m = re.search(r"-county-(\d{2})-(\d{3})$", uid)
                if m and sent:
                    fips = f"{m.group(1)}{m.group(2)}"
                    county_blurbs[fips] = sent
        elif isinstance(ds, dict):
            for fips, sent in ds.items():
                if sent and isinstance(sent, str):
                    county_blurbs[fips] = sent
        for r in d.get("races", []):
            nid = r.get("nyt_id")
            if not nid:
                continue
            existing = races_by_id.get(nid)
            if not existing or len(r.get("reporting_units", [])) >= len(existing.get("reporting_units", [])):
                races_by_id[nid] = r
    return list(races_by_id.values()), county_blurbs


def normalize_party(party_id: str | dict | None, caucus: str | dict | None = None, cand_name: str = "") -> str:
    if isinstance(party_id, dict):
        party_id = party_id.get("nyt_id") or party_id.get("name") or ""
    if isinstance(caucus, dict):
        caucus = caucus.get("nyt_id") or caucus.get("name") or ""
    p = str(party_id or "").upper().strip()
    c = str(caucus or "").upper().strip()
    cn = (cand_name or "").lower()
    if p in ("DEM", "DEMOCRAT", "DEMOCRATIC", "DFL") or c == "DEM":
        return "DEM"
    if p in ("GOP", "REP", "REPUBLICAN") or c == "GOP":
        return "GOP"
    # Independent senators who caucus with Democrats
    if any(k in cn for k in ("bernie sanders", "bernard sanders", "angus king", "kyrsten sinema", "joe manchin")):
        return "DEM"
    if p in ("YES", "APPROVED", "FOR", "MAINTAIN", "RETAIN"):
        return "YES"
    if p in ("NO", "REJECTED", "AGAINST", "REPEAL"):
        return "NO"
    if p in ("IND", "INDEPENDENT", "UNENROLLED", "NOP", "NPA"):
        return "IND"
    if p in ("LIB", "LIBERTARIAN", "LBT"):
        return "LIB"
    if p in ("GRN", "GREEN", "GRE"):
        return "GRN"
    return p or "OTH"


def is_presidential_cd_subrace(r: dict) -> bool:
    """Returns True if a Presidential race is a Congressional District sub-race (ME-CD1/2, NE-CD1/2/3)."""
    if r.get("office") != "President":
        return False
    nid = r.get("nyt_id") or ""
    seat = r.get("seat") or ""
    return bool(seat) or ("-CD_" in nid)


def filter_primary_senate_races_for_counties(races: list[dict]) -> set[str]:
    """
    When a state has BOTH a regular Senate election (-G-S-) and a special Senate election (-S_W-S-)
    in the same cycle (e.g. CA 2024, NE 2024), returns only the regular race nyt_id for county maps
    to prevent double-counting county Senate votes. If a state only has a special Senate election
    (e.g. FL 2026, OH 2026), keeps that special race.
    """
    sen_by_state = collections.defaultdict(list)
    for r in races:
        if r.get("office") == "U.S. Senate":
            st = (r.get("top_reporting_unit") or {}).get("state_postal") or (r.get("nyt_id") or "")[:2]
            sen_by_state[st].append(r)

    allowed_ids = set()
    for st, rlist in sen_by_state.items():
        if len(rlist) == 1:
            allowed_ids.add(rlist[0].get("nyt_id"))
        else:
            reg = [r for r in rlist if "-G-S-" in (r.get("nyt_id") or "") or r.get("type") == "General"]
            chosen = reg[0] if reg else rlist[0]
            allowed_ids.add(chosen.get("nyt_id"))
    return allowed_ids


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
        if cid in ("undervote", "overvote"):
            continue
        m = cmeta.get(cid) or {}
        pty_obj = m.get("party") or {}
        fname = m.get("first_name") or ""
        lname = m.get("last_name") or cid or ""
        full_name = f"{fname} {lname}".strip()
        norm_pty = normalize_party(pty_obj.get("nyt_id"), m.get("party_caucus"), full_name)
        v = (c.get("votes") or {}).get("total") or 0
        pct = round(100.0 * v / total_votes, 2) if total_votes > 0 else 0.0
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

    # Aggregate party vote shares properly; detect single-party / uncontested general elections
    dem_cands = [c for c in candidates if c["party"] == "DEM"]
    gop_cands = [c for c in candidates if c["party"] == "GOP"]
    dem_pct = round(sum(c["percent"] for c in dem_cands), 2) if dem_cands else 0.0
    gop_pct = round(sum(c["percent"] for c in gop_cands), 2) if gop_cands else 0.0
    one_party_race = bool(r.get("uncontested")) or (len(dem_cands) == 0) or (len(gop_cands) == 0)
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

    # Extract exact within-jurisdiction 2024 Presidential margin from top_unit historical_comparison_race_data if present
    hist_comp = top_unit.get("historical_comparison_race_data") or {}
    dist_pres_24 = None
    for hk, hv in hist_comp.items():
        if "-G-P-2024" in hk and isinstance(hv, dict) and hv.get("margin") is not None:
            dist_pres_24 = round(float(hv["margin"]), 2)
            break

    return {
        "nyt_id": r.get("nyt_id"),
        "office": r.get("office"),
        "office_id": r.get("office_id"),
        "state": state_postal,
        "state_fips": POSTAL_TO_STATE_FIPS.get(state_postal, ""),
        "seat": seat,
        "seat_number": seat_num,
        "type": r.get("type"),
        "is_special": "-S_W-" in (r.get("nyt_id") or "") or "Special" in (r.get("type") or ""),
        "uncontested": bool(r.get("uncontested")),
        "one_party": one_party_race,
        "incumbent_party": normalize_party((r.get("party") or {}).get("nyt_id")),
        "rating": r.get("general_rating") or r.get("rating"),
        "called": called,
        "race_call_status": r.get("race_call_status"),
        "party_flip": outcome.get("party_flip"),
        "eevp": min(100, eevp),
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
        "district_pres_2024_margin": dist_pres_24,
    }


def extract_county_office_data(races: list[dict], target_office: str) -> dict[str, dict]:
    """
    Extracts normalized county-level returns for a given office from NYT race objects.
    Guarantees zero double-counting of ME/NE Presidential CD sub-races and CA/NE concurrent Senate races,
    and weights split-county EEVP by expected votes.
    """
    allowed_senate_ids = filter_primary_senate_races_for_counties(races) if target_office == "U.S. Senate" else None
    counties = {}

    # Build Connecticut town -> traditional county FIPS (001..015) lookup so CT House races
    # (which use 2024+ planning region codes 110..190) map cleanly onto the 8 CT counties
    ct_town_to_fc = {}
    for r in races:
        for u in r.get("reporting_units") or []:
            if u.get("fips_state") == "09" and u.get("level") == "township":
                fc = u.get("fips_county") or ""
                if fc in ("001", "003", "005", "007", "009", "011", "013", "015") and u.get("name"):
                    ct_town_to_fc[u["name"]] = fc

    for r in races:
        if r.get("office") != target_office:
            continue
        if target_office == "President" and is_presidential_cd_subrace(r):
            continue
        if target_office == "U.S. Senate" and allowed_senate_ids and r.get("nyt_id") not in allowed_senate_ids:
            continue
        if target_office == "U.S. House" and r.get("nyt_id") in ("US-G-H-2026-11-03", "US-G-H-2024-11-05"):
            continue

        cmeta = r.get("candidate_metadata") or {}
        party_map = {}
        name_map = {}
        for cid, m in cmeta.items():
            full_n = f"{m.get('first_name') or ''} {m.get('last_name') or ''}".strip()
            pty = normalize_party((m.get("party") or {}).get("nyt_id"), m.get("party_caucus"), full_n)
            party_map[cid] = pty
            name_map[cid] = full_n

        units = r.get("reporting_units") or []
        ct_cog_to_fc = {
            "110": ["003", "013"],
            "120": ["001"],
            "130": ["007"],
            "140": ["009"],
            "150": ["015"],
            "160": ["005"],
            "170": ["009"],
            "180": ["011"],
            "190": ["001"],
        }
        has_valid_county = any(
            u.get("level") == "county"
            and (
                u.get("fips_state") != "09"
                or (u.get("fips_county") or "") in ("001", "003", "005", "007", "009", "011", "013", "015")
                or (u.get("fips_county") or "") in ct_cog_to_fc
            )
            for u in units
        )
        for u in units:
            lvl = u.get("level")
            fs = u.get("fips_state")
            fc = u.get("fips_county")
            if fs == "02" and lvl == "state" and not has_valid_county:
                target_fcs = ["020"]
            else:
                if has_valid_county and lvl != "county":
                    continue
                if not has_valid_county and lvl not in ("county", "township"):
                    continue
                if not fs or not fc:
                    continue
                if fs == "09" and fc not in ("001", "003", "005", "007", "009", "011", "013", "015"):
                    if fc in ct_cog_to_fc:
                        target_fcs = ct_cog_to_fc[fc]
                    else:
                        mapped_fc = ct_town_to_fc.get(u.get("name") or "")
                        if not mapped_fc:
                            continue
                        target_fcs = [mapped_fc]
                else:
                    target_fcs = [fc]

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

            for mapped_fc in target_fcs:
                fips = f"{fs}{mapped_fc}"
                if fips not in counties:
                    counties[fips] = {
                        "state": u.get("state_postal"),
                        "name": u.get("name") if (lvl == "county" and fs != "09") else "",
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
                if lvl == "county" and fs != "09" and u.get("name"):
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
        exp = rec["exp_v"]
        dem_pct = round(100.0 * rec["dem_v"] / tot, 2) if tot > 0 else 0.0
        gop_pct = round(100.0 * rec["gop_v"] / tot, 2) if tot > 0 else 0.0
        ind_pct = round(100.0 * rec["ind_v"] / tot, 2) if tot > 0 else 0.0
        margin = round(dem_pct - gop_pct, 2)
        # Vote-weighted EEVP across split-county units
        if exp > 0:
            eevp = round(100.0 * tot / exp)
        elif rec["eevp_cnt"] > 0:
            eevp = round(rec["eevp_sum"] / rec["eevp_cnt"])
        else:
            eevp = 0
        one_party = (rec["dem_v"] == 0) or (rec["gop_v"] == 0)
        out[fips] = {
            "state": rec["state"],
            "name": rec["name"],
            "dem_v": rec["dem_v"],
            "gop_v": rec["gop_v"],
            "ind_v": rec["ind_v"],
            "tot_v": tot,
            "exp_v": exp,
            "dem_pct": dem_pct,
            "gop_pct": gop_pct,
            "ind_pct": ind_pct,
            "margin": margin,
            "eevp": min(100, eevp),
            "dem_n": rec["dem_n"],
            "gop_n": rec["gop_n"],
            "ind_n": rec["ind_n"],
            "one_party": one_party,
        }
    return out


def load_historical_county_results() -> dict[str, dict[str, dict]]:
    """
    Loads 2004–2024 county-level returns from data/historical/us_county_results_summary.csv.
    Returns {fips: {cycle_key: {"d": dem_pct, "r": gop_pct, "m": margin, "v": tot_v, "op": 1 (if one-party)}}}.
    Cycle keys:
      p04, p08, p12, p16, p20, p24
      s04, s06, s08, s10, s12, s14, s16, s18, s20, s22, s24
      h04, h06, h08, h10, h12, h14, h16, h18, h20, h22, h24
    """
    csv_path = HIST_DIR / "us_county_results_summary.csv"
    by_fips = collections.defaultdict(dict)
    if not csv_path.exists():
        print(f"WARNING: {csv_path} not found!")
        return by_fips

    office_prefix = {"president": "p", "senate": "s", "house": "h"}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            yr = int(row["year"])
            if yr < 2004:
                continue
            off = row["office"]
            pref = office_prefix.get(off)
            if not pref:
                continue
            fips = row["county_fips"].zfill(5)
            if fips == "02000":
                fips = "02020"
            tot_v = int(float(row["total_votes"] or 0))
            if tot_v <= 0:
                continue
            dem_v = int(float(row["dem_votes"] or 0))
            rep_v = int(float(row["rep_votes"] or 0))
            d_pct = round(100.0 * dem_v / tot_v, 1)
            r_pct = round(100.0 * rep_v / tot_v, 1)
            margin = round(d_pct - r_pct, 1)
            qflag = row.get("quality_flag") or ""
            one_party = (
                "one_party_race" in qflag
                or "zero_major_party_votes" in qflag
                or dem_v == 0
                or rep_v == 0
            )
            key = f"{pref}{str(yr)[2:]}"
            rec = {"d": d_pct, "r": r_pct, "m": margin, "v": tot_v}
            if one_party:
                rec["op"] = 1
            by_fips[fips][key] = rec
    return by_fips


def parse_538_historical_races() -> dict[str, dict]:
    """
    Parses and normalizes 2004–2024 statewide and district general election results from FiveThirtyEight CSVs:
    - Governor (538_election_results_gubernatorial.csv)
    - U.S. Senate (538_election_results_senate.csv)
    - U.S. House (538_election_results_house.csv)
    - President (538_election_results_presidential.csv)

    Enforces:
    - Ranked-Choice Voting Round 1 filtering (`ranked_choice_round in ('', '1')`)
    - Fusion-ticket aggregation (summing multiple party lines per candidate in NY/CT/SC/VT)
    - Excludes special elections when indexing regular cycle histories
    """
    files = {
        "governor": HIST_DIR / "538_election_results_gubernatorial.csv",
        "senate": HIST_DIR / "538_election_results_senate.csv",
        "house": HIST_DIR / "538_election_results_house.csv",
        "president": HIST_DIR / "538_election_results_presidential.csv",
    }

    # Output structures:
    # gov_by_state[state][year] = summary
    # sen_by_state[state][year] = summary
    # pres_by_state[state][year] = summary
    # house_by_key["ST-num"][year] = summary
    out = {
        "governor": collections.defaultdict(dict),
        "senate": collections.defaultdict(dict),
        "president": collections.defaultdict(dict),
        "house": collections.defaultdict(dict),
    }

    for office_key, path in files.items():
        if not path.exists():
            continue
        # Group rows by race_id
        races_rows = collections.defaultdict(list)
        with open(path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    yr = int(row.get("cycle") or 0)
                except ValueError:
                    continue
                if yr < 2004:
                    continue
                if (row.get("stage") or "").lower() != "general":
                    continue
                if (row.get("special") or "").lower() == "true":
                    continue
                rcv = (row.get("ranked_choice_round") or "").strip()
                if rcv not in ("", "1"):
                    continue
                # For President, ignore ME/NE congressional district sub-races
                st_abbrev = (row.get("state_abbrev") or "").strip().upper()
                if office_key == "president" and len(st_abbrev) > 2:
                    continue
                office_seat = (row.get("office_seat_name") or "").lower()
                if office_key == "president" and "district" in office_seat:
                    continue
                races_rows[row["race_id"]].append(row)

        for race_id, rows in races_rows.items():
            first = rows[0]
            yr = int(first["cycle"])
            st = (first.get("state_abbrev") or "")[:2].upper()
            if not st:
                st = STATE_NAME_TO_POSTAL.get((first.get("state") or "").lower().strip(), "")
            if not st:
                continue

            # Aggregate by candidate to rectify fusion voting (NY, CT, etc.)
            cands_agg = {}
            for r in rows:
                cname = (r.get("candidate_name") or "").strip()
                if not cname:
                    continue
                cn_low = cname.lower()
                if any(bad in cn_low for bad in ("undervote", "overvote", "blank", "scattering", "void", "none of these")):
                    continue
                try:
                    v = int(float(r.get("votes") or 0))
                except ValueError:
                    v = 0
                pty_raw = (r.get("ballot_party") or "").strip().upper()
                norm_p = normalize_party(pty_raw, None, cname)
                w = (r.get("winner") or "").lower() == "true"

                ckey = r.get("candidate_id") or cname
                if ckey not in cands_agg:
                    cands_agg[ckey] = {
                        "name": cname,
                        "votes": 0,
                        "parties": set(),
                        "winner": False,
                    }
                cands_agg[ckey]["votes"] += v
                cands_agg[ckey]["parties"].add(norm_p)
                if w:
                    cands_agg[ckey]["winner"] = True

            if not cands_agg:
                continue

            tot_v = sum(c["votes"] for c in cands_agg.values())
            if tot_v <= 0:
                continue

            # Assign primary party per candidate (DEM/GOP take precedence over minor fusion lines like WFP/CON)
            cand_list = []
            for c in cands_agg.values():
                ptys = c["parties"]
                if "DEM" in ptys:
                    p = "DEM"
                elif "GOP" in ptys:
                    p = "GOP"
                elif "IND" in ptys:
                    p = "IND"
                else:
                    p = next(iter(ptys))
                cand_list.append({
                    "name": c["name"],
                    "party": p,
                    "votes": c["votes"],
                    "pct": round(100.0 * c["votes"] / tot_v, 1),
                    "winner": c["winner"],
                })

            cand_list.sort(key=lambda x: (x["winner"], x["votes"]), reverse=True)
            dem_v = sum(c["votes"] for c in cand_list if c["party"] == "DEM")
            gop_v = sum(c["votes"] for c in cand_list if c["party"] == "GOP")
            d_pct = round(100.0 * dem_v / tot_v, 1)
            r_pct = round(100.0 * gop_v / tot_v, 1)
            margin = round(d_pct - r_pct, 1)
            one_party = (dem_v == 0) or (gop_v == 0)
            win_cand = cand_list[0]

            summary = {
                "year": yr,
                "d": d_pct,
                "r": r_pct,
                "m": margin,
                "v": tot_v,
                "wp": win_cand["party"],
                "wn": win_cand["name"].split()[-1] if win_cand["name"] else "",
                "op": 1 if one_party else 0,
            }

            if office_key in ("governor", "senate", "president"):
                out[office_key][st][yr] = summary
            elif office_key == "house":
                seat_str = first.get("office_seat_name") or ""
                m_num = re.search(r"(\d+)", seat_str)
                dist_num = str(int(m_num.group(1))) if m_num else "1"
                hkey = f"{st}-{dist_num}"
                out["house"][hkey][yr] = summary

    return out


def clean_county_key(name: str, is_city: bool = False) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii").lower()
    for suf in [
        " county", " parish", " borough", " census area",
        " municipality", " city and borough", " district",
    ]:
        if s.endswith(suf):
            s = s[: -len(suf)]
    if not is_city and s.endswith(" city"):
        s = s[: -len(" city")]
    s = re.sub(r"[^a-z0-9]", "", s)
    if s.startswith("st") and not s.startswith("sta") and not s.startswith("ste"):
        s = "saint" + s[2:]
    return s


def load_county_demographics(topo_geoms: list[dict], county_blurbs: dict[str, str]) -> dict[str, dict]:
    """
    Matches all 3,139 counties from data/historical/county_demographics.csv to 5-digit FIPS codes
    and merges NYT county demographic blurbs.
    """
    topo_by_state_and_key = {}
    for g in topo_geoms:
        fips = g["id"]
        st = STATE_FIPS_TO_POSTAL.get(fips[:2])
        if not st:
            continue
        is_ind_city = int(fips[2:]) >= 500 and st in ("VA", "MD", "MO", "NV")
        cname = (g.get("properties") or {}).get("name", "")
        if is_ind_city and not cname.lower().endswith("city"):
            cname = cname + " city"
        k = clean_county_key(cname, is_city=is_ind_city)
        topo_by_state_and_key[(st, k)] = fips

    manual_overrides = {
        ("AK", "chugach"): "02063",
        ("AK", "copperriver"): "02066",
        ("AK", "hoonahangoon"): "02105",
        ("AK", "kusilvak"): "02158",
        ("AK", "petersburg"): "02195",
        ("AK", "princeofwaleshyder"): "02198",
        ("AK", "skagway"): "02230",
        ("AK", "wrangell"): "02275",
        ("DC", "districtofcolumbia"): "11001",
        ("LA", "lasalle"): "22059",
        ("MD", "baltimore"): "24005",
        ("MD", "baltimorecity"): "24510",
        ("MO", "saintlouis"): "29189",
        ("MO", "saintlouiscity"): "29510",
        ("NM", "donaana"): "35013",
        ("SD", "oglala"): "46102",
        ("SD", "oglalalakota"): "46102",
    }

    dem_by_fips = {}
    csv_path = HIST_DIR / "county_demographics.csv"
    if not csv_path.exists():
        print(f"WARNING: {csv_path} not found!")
        return dem_by_fips

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            st = row["State"]
            c_raw = row["County"]
            is_city = c_raw.lower().endswith(" city") and st in ("VA", "MD", "MO", "NV")
            k = clean_county_key(c_raw, is_city=is_city)
            fips = manual_overrides.get((st, k)) or topo_by_state_and_key.get((st, k))
            if not fips:
                for (tst, tk), tfips in topo_by_state_and_key.items():
                    if tst == st and (tk in k or k in tk):
                        fips = tfips
                        break
            if not fips:
                continue

            pop20 = int(float(row.get("Population.2020 Population") or 0))
            dens = round(float(row.get("Population.Population per Square Mile") or 0), 1)
            ba_pct = round(float(row.get("Education.Bachelor's Degree or Higher") or 0), 1)
            hs_pct = round(float(row.get("Education.High School or Higher") or 0), 1)
            inc = int(float(row.get("Income.Median Houseold Income") or 0))
            wnh = round(
                float(
                    row.get("Ethnicities.White Alone\t not Hispanic or Latino")
                    or row.get("Ethnicities.White Alone, not Hispanic or Latino")
                    or row.get("Ethnicities.White Alone")
                    or 0
                ),
                1,
            )
            blk = round(float(row.get("Ethnicities.Black Alone") or 0), 1)
            hisp = round(float(row.get("Ethnicities.Hispanic or Latino") or 0), 1)
            asn = round(float(row.get("Ethnicities.Asian Alone") or 0), 1)
            nat = round(float(row.get("Ethnicities.American Indian and Alaska Native Alone") or 0), 1)
            age65 = round(float(row.get("Age.Percent 65 and Older") or 0), 1)
            home = round(float(row.get("Housing.Homeownership Rate") or 0), 1)

            blurb = county_blurbs.get(fips, "")
            blurb_low = blurb.lower()
            # Classify urbanicity using NYT typology + population density
            if dens >= 1200 or ("urban" in blurb_low and dens >= 500) or pop20 >= 750000:
                urb = "Urban"
            elif dens >= 220 or "suburban" in blurb_low or pop20 >= 180000:
                urb = "Suburban"
            elif dens >= 55 or pop20 >= 45000:
                urb = "Small Metro/Town"
            else:
                urb = "Rural"

            dem_by_fips[fips] = {
                "pop": pop20,
                "dens": dens,
                "urb": urb,
                "ba": ba_pct,
                "hs": hs_pct,
                "inc": inc,
                "wnh": wnh,
                "blk": blk,
                "hisp": hisp,
                "asn": asn,
                "nat": nat,
                "age65": age65,
                "home": home,
            }
            if blurb:
                dem_by_fips[fips]["txt"] = blurb

    return dem_by_fips


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
    topo_geoms = topo["objects"]["counties"]["geometries"]
    topo_county_names = {
        g["id"]: (g.get("properties") or {}).get("name", "")
        for g in topo_geoms
    }

    print("1. Loading NYT 2024 and 2026 races + county demographic blurbs...")
    races_24, blurbs_24 = load_nyt_races("nyt_2024")
    races_26, blurbs_26 = load_nyt_races("nyt_2026")
    county_blurbs = {**blurbs_24, **blurbs_26}

    print("2. Loading 2004–2024 historical county returns & 538 statewide/district histories...")
    hist_counties = load_historical_county_results()
    hist_538 = parse_538_historical_races()

    print("3. Loading and matching U.S. Census county demographics...")
    dem_by_fips = load_county_demographics(topo_geoms, county_blurbs)

    # Extract race summaries (excluding ME/NE Presidential CD sub-races from state-level Presidential index)
    summaries_24 = [extract_race_summary(r) for r in races_24 if not is_presidential_cd_subrace(r)]
    summaries_26 = [extract_race_summary(r) for r in races_26]

    # Index 2024 summaries by (office, state, seat_number/seat)
    house_24_by_key = {}
    senate_24_by_state = {}
    pres_24_by_state = {}
    gov_24_by_state = {}
    for s in summaries_24:
        off = s["office"]
        st = s["state"]
        if off == "U.S. House" and s["nyt_id"] != "US-G-H-2024-11-05":
            key = f"{st}-{s['seat_number'] or s['seat']}"
            house_24_by_key[key] = s
        elif off == "U.S. Senate":
            # Prefer regular over special when indexing 2024 state Senate (CA, NE)
            if st not in senate_24_by_state or not s["is_special"]:
                senate_24_by_state[st] = s
        elif off == "President":
            pres_24_by_state[st] = s
        elif off == "Governor":
            gov_24_by_state[st] = s

    # Build 2026 Senate, Governor, House lists with 20-year Apples-to-Apples comparisons!
    senate_26 = []
    governor_26 = []
    house_26 = []
    measures_26 = []
    statewide_exec_26 = []

    for s in summaries_26:
        off = s["office"]
        st = s["state"]
        p24 = pres_24_by_state.get(st)
        dist_p24 = s.get("district_pres_2024_margin")
        s["pres_2024_margin"] = p24["dem_gop_margin"] if p24 else dist_p24
        if s["pres_2024_margin"] is not None and not s["one_party"]:
            s["shift_vs_pres_2024"] = round(s["dem_gop_margin"] - s["pres_2024_margin"], 2)
        else:
            s["shift_vs_pres_2024"] = None
        if dist_p24 is not None and not s["one_party"]:
            s["shift_vs_district_pres_2024"] = round(s["dem_gop_margin"] - dist_p24, 2)
        else:
            s["shift_vs_district_pres_2024"] = s["shift_vs_pres_2024"]

        # Attach 2004–2024 Presidential state margins
        pres_hist = {}
        for yr in (2024, 2020, 2016, 2012, 2008, 2004):
            if yr == 2024 and p24:
                pres_hist[str(yr)] = p24["dem_gop_margin"]
            elif yr in hist_538["president"].get(st, {}):
                pres_hist[str(yr)] = hist_538["president"][st][yr]["m"]
        s["pres_history"] = pres_hist

        if off == "U.S. Senate":
            # Apples-to-Apples Class II Senate history (2020, 2014, 2008) + recent Senate elections
            st_sen_hist = hist_538["senate"].get(st, {})
            seat_hist = {}
            for yr in sorted(st_sen_hist.keys(), reverse=True):
                seat_hist[str(yr)] = st_sen_hist[yr]
            s["office_history"] = seat_hist
            # For 2026 regular Class II Senate seats, 2020 is the exact same seat; for FL/OH specials, 2024/2022
            same_seat_yr = 2022 if st in ("FL", "OH") and 2022 in st_sen_hist else (2020 if 2020 in st_sen_hist else None)
            if same_seat_yr and not s["one_party"] and not st_sen_hist[same_seat_yr].get("op"):
                prev_m = st_sen_hist[same_seat_yr]["m"]
                s["last_same_office_year"] = same_seat_yr
                s["last_same_office_margin"] = prev_m
                s["shift_vs_same_office"] = round(s["dem_gop_margin"] - prev_m, 2)
            else:
                s["last_same_office_year"] = same_seat_yr
                s["last_same_office_margin"] = st_sen_hist[same_seat_yr]["m"] if same_seat_yr else None
                s["shift_vs_same_office"] = None
            senate_26.append(s)

        elif off == "Governor":
            # Apples-to-Apples Governor history (2022, 2018, 2014, 2010, 2006; or 2024 for NH/VT)
            st_gov_hist = hist_538["governor"].get(st, {})
            gov_hist = {}
            for yr in sorted(st_gov_hist.keys(), reverse=True):
                gov_hist[str(yr)] = st_gov_hist[yr]
            s["office_history"] = gov_hist
            last_gov_yr = 2024 if 2024 in st_gov_hist else (2022 if 2022 in st_gov_hist else None)
            if last_gov_yr and not s["one_party"] and not st_gov_hist[last_gov_yr].get("op"):
                prev_m = st_gov_hist[last_gov_yr]["m"]
                s["last_same_office_year"] = last_gov_yr
                s["last_same_office_margin"] = prev_m
                s["shift_vs_same_office"] = round(s["dem_gop_margin"] - prev_m, 2)
            else:
                s["last_same_office_year"] = last_gov_yr
                s["last_same_office_margin"] = st_gov_hist[last_gov_yr]["m"] if last_gov_yr else None
                s["shift_vs_same_office"] = None
            governor_26.append(s)

        elif off == "U.S. House" and s["nyt_id"] != "US-G-H-2026-11-03":
            dist_num = str(s["seat_number"] or s["seat"] or "1").lstrip("0") or "1"
            if not dist_num.isdigit():
                dist_num = "1"
            key = f"{st}-{s['seat_number'] or s['seat']}"
            hkey_538 = f"{st}-{dist_num}"
            h24 = house_24_by_key.get(key)
            dist_hist_538 = hist_538["house"].get(hkey_538, {})
            house_hist = {}
            for yr in sorted(dist_hist_538.keys(), reverse=True):
                house_hist[str(yr)] = dist_hist_538[yr]
            s["office_history"] = house_hist

            if h24:
                s["margin_2024_house"] = h24["dem_gop_margin"]
                s["winner_2024_party"] = h24["winner_party"] or h24["leader_party"]
                if not s["one_party"] and not h24["one_party"]:
                    s["shift_vs_house_2024"] = round(s["dem_gop_margin"] - h24["dem_gop_margin"], 2)
                else:
                    s["shift_vs_house_2024"] = None
            else:
                s["margin_2024_house"] = None
                s["winner_2024_party"] = s["incumbent_party"]
                s["shift_vs_house_2024"] = None

            # Also compute shift vs. 2022 Midterm House!
            h22 = dist_hist_538.get(2022)
            if h22 and not s["one_party"] and not h22.get("op"):
                s["last_same_office_year"] = 2022
                s["last_same_office_margin"] = h22["m"]
                s["shift_vs_same_office"] = round(s["dem_gop_margin"] - h22["m"], 2)
            else:
                s["last_same_office_year"] = 2024 if h24 else None
                s["last_same_office_margin"] = s["margin_2024_house"]
                s["shift_vs_same_office"] = s["shift_vs_house_2024"]

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

    gov_dem_no_el = sum(1 for p in GOV_NO_ELECTION_2026.values() if p == "DEM")
    gov_gop_no_el = sum(1 for p in GOV_NO_ELECTION_2026.values() if p == "GOP")
    gov_dem_called = sum(1 for r in governor_26 if r["called"] and r["winner_party"] == "DEM")
    gov_gop_called = sum(1 for r in governor_26 if r["called"] and r["winner_party"] == "GOP")
    gov_dem_lead = sum(1 for r in governor_26 if not r["called"] and r["leader_party"] == "DEM")
    gov_gop_lead = sum(1 for r in governor_26 if not r["called"] and r["leader_party"] == "GOP")

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

    # Build county-by-county dataset across 2004–2026 + Census Demographics
    print("4. Building unified 2004–2026 county-level returns & demographics dataset...")
    c_p24 = extract_county_office_data(races_24, "President")
    c_s24 = extract_county_office_data(races_24, "U.S. Senate")
    c_h24 = extract_county_office_data(races_24, "U.S. House")
    c_g24 = extract_county_office_data(races_24, "Governor")
    c_s26 = extract_county_office_data(races_26, "U.S. Senate")
    c_g26 = extract_county_office_data(races_26, "Governor")
    c_h26 = extract_county_office_data(races_26, "U.S. House")
    c_ag26 = extract_county_office_data(races_26, "Attorney General")

    all_fips = sorted(
        set(c_p24.keys())
        | set(c_s26.keys())
        | set(c_g26.keys())
        | set(c_h26.keys())
        | set(hist_counties.keys())
        | set(dem_by_fips.keys())
    )

    counties_payload = {}
    for fips in all_fips:
        p24 = c_p24.get(fips)
        s24 = c_s24.get(fips)
        h24 = c_h24.get(fips)
        g24 = c_g24.get(fips)
        s26 = c_s26.get(fips)
        g26 = c_g26.get(fips)
        h26 = c_h26.get(fips)
        ag26 = c_ag26.get(fips)
        h_rec = hist_counties.get(fips, {})

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

        # Attach demographics if available
        if fips in dem_by_fips:
            entry["dem"] = dem_by_fips[fips]

        # Attach 2004–2024 historical county cycles (p04..p24, s04..s24, h04..h24)
        for cyc_key, cyc_val in h_rec.items():
            entry[cyc_key] = cyc_val

        # For Alaska statewide hub (02020), backfill 2004–2024 statewide historical cycles from 538 archive
        if fips == "02020":
            for yr, s_rec in hist_538["president"].get("AK", {}).items():
                entry.setdefault(f"p{str(yr)[2:]}", {"d": s_rec["d"], "r": s_rec["r"], "m": s_rec["m"], "v": s_rec["v"]})
            for yr, s_rec in hist_538["senate"].get("AK", {}).items():
                entry.setdefault(f"s{str(yr)[2:]}", {"d": s_rec["d"], "r": s_rec["r"], "m": s_rec["m"], "v": s_rec["v"]})
            for yr, s_rec in hist_538["house"].get("AK-1", {}).items():
                entry.setdefault(f"h{str(yr)[2:]}", {"d": s_rec["d"], "r": s_rec["r"], "m": s_rec["m"], "v": s_rec["v"]})

        # Override/enrich 2024 cycles with NYT 2024 county returns where available
        for key, rec in [("p24", p24), ("s24", s24), ("h24", h24), ("g24", g24)]:
            if rec and rec["tot_v"] > 0:
                obj = {
                    "d": round(rec["dem_pct"], 1),
                    "r": round(rec["gop_pct"], 1),
                    "m": round(rec["margin"], 1),
                    "v": rec["tot_v"],
                }
                if rec["one_party"]:
                    obj["op"] = 1
                entry[key] = obj

        # Attach 2026 live county cycles
        p24_obj = entry.get("p24")
        for key, rec in [("s26", s26), ("g26", g26), ("h26", h26), ("ag26", ag26)]:
            if rec and rec["tot_v"] > 0:
                has_both_parties = not rec["one_party"]
                shift_p24 = (
                    round(rec["margin"] - p24_obj["m"], 2)
                    if (p24_obj and p24_obj.get("v", 0) > 0 and not p24_obj.get("op") and has_both_parties)
                    else None
                )
                obj = {
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
                if rec["one_party"]:
                    obj["op"] = 1
                entry[key] = obj

        # Also create `top26` (2026 All-50-State Top-of-Ticket: highest two-party Senate -> Governor -> House)
        top_rec = (
            (entry.get("s26") if entry.get("s26") and not entry["s26"].get("op") else None)
            or (entry.get("g26") if entry.get("g26") and not entry["g26"].get("op") else None)
            or (entry.get("h26") if entry.get("h26") and not entry["h26"].get("op") else None)
            or entry.get("s26")
            or entry.get("g26")
            or entry.get("h26")
        )
        if top_rec:
            entry["top26"] = top_rec

        counties_payload[fips] = entry

    with open(SITE_DATA_DIR / "county_shifts.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "count": len(counties_payload),
                "ap_abbr": AP_STATE_ABBR,
                "state_fips_to_postal": STATE_FIPS_TO_POSTAL,
                "state_histories": {
                    "governor": hist_538["governor"],
                    "senate": hist_538["senate"],
                    "president": hist_538["president"],
                },
                "counties": counties_payload,
            },
            f,
            separators=(",", ":"),
        )

    # Process civicAPI 39,474 races (data/latest.json), excluding national rollups from seat/race tallies
    print("5. Indexing and normalizing civicAPI races by state & category...")
    with open(DATA_DIR / "latest.json", encoding="utf-8") as f:
        civic_data = json.load(f)
    civic_races_raw = civic_data.get("races", [])
    fetched_at = civic_data.get("fetched_at") or datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()

    civic_by_state = collections.defaultdict(list)
    civic_type_counts = collections.Counter()
    civic_called_total = 0
    close_races_all = []
    excluded_rollups = 0

    for r in civic_races_raw:
        rid = r.get("id")
        if rid in CIVIC_NATIONAL_ROLLUP_IDS:
            excluded_rollups += 1
            continue
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
            "id": rid,
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
    civic_clean_total = len(civic_races_raw) - excluded_rollups

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
            "civic_total_races": civic_clean_total,
            "civic_raw_feed_rows": len(civic_races_raw),
            "civic_called_races": civic_called_total,
            "civic_uncalled_races": civic_clean_total - civic_called_total,
            "nyt_2026_races": len(summaries_26),
            "nyt_2024_races": len(summaries_24),
            "counties_tracked": len(counties_payload),
            "counties_with_demographics": len(dem_by_fips),
            "historical_years_span": "2004–2026 (22 Years / 12 Federal Cycles)",
            "top_race_types": civic_type_counts.most_common(40),
            "states_index": state_counts_index,
        },
        "data_hygiene_audit": {
            "me_ne_pres_cd_subraces_filtered": 5,
            "concurrent_special_senate_deduped": ["CA (2024)", "NE (2024)", "GA (2020)", "OK (2022)"],
            "rcv_rounds_deduped": "Filtered strictly to Round 1 (AK, ME)",
            "fusion_tickets_aggregated": "Candidate ballot lines combined (NY, CT, SC, VT)",
            "civic_national_rollups_excluded": excluded_rollups,
            "split_county_eevp_weighting": "Vote-weighted by total_expected_vote",
            "single_party_races_flagged": sum(1 for h in house_26 if h.get("one_party")),
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

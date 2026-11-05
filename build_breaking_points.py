#!/usr/bin/env python3
"""
Builds site_data/breaking_points_2026.json by combining:
1. 2026 Exit Poll / AP Voter Poll / WaPo-Ipsos issue survey data (data/exit_polls_2026.json)
2. Disjoint county-cohort shift comparisons (2020->2024, 2016->2018, 2024->2026 across offices)
3. Down-ballot contagion metrics (federal vs. state executive/legislative cascades and correlations)
"""
import json
import math
import statistics as stats
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
SITE_DATA = BASE_DIR / "site_data"
DATA_DIR = BASE_DIR / "data"


def valid_race(c: dict, k: str) -> bool:
    if k not in c:
        return False
    r = c[k]
    if r.get("v", 0) <= 0 or r.get("op", 0) == 1:
        return False
    if r.get("d", 0) == 0 or r.get("r", 0) == 0:
        return False
    return True


def shift(c: dict, k2: str, k1: str = "p24"):
    if valid_race(c, k2) and valid_race(c, k1):
        return round(c[k2]["m"] - c[k1]["m"], 3)
    return None


def pearson(x: list, y: list) -> float:
    if len(x) < 2:
        return 0.0
    mx, my = stats.mean(x), stats.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return round(num / den, 4) if den else 0.0


def summarize_shifts(arr: list) -> dict:
    if not arr:
        return {"n": 0, "mean": None, "median": None, "stdev": None, "pct_shifting_dem": None}
    return {
        "n": len(arr),
        "mean": round(stats.mean(arr), 2),
        "median": round(stats.median(arr), 2),
        "stdev": round(stats.stdev(arr), 2) if len(arr) > 1 else 0.0,
        "pct_shifting_dem": round(sum(1 for x in arr if x > 0) / len(arr) * 100, 1),
    }


def build_breaking_points() -> dict:
    ov = json.loads((SITE_DATA / "overview.json").read_text(encoding="utf-8"))
    cs = json.loads((SITE_DATA / "county_shifts.json").read_text(encoding="utf-8"))
    ep_path = SITE_DATA / "exit_polls_2026.json"
    if not ep_path.exists():
        ep_path = DATA_DIR / "exit_polls_2026.json"
    exit_polls = json.loads(ep_path.read_text(encoding="utf-8"))

    counties = list(cs["counties"].values()) if isinstance(cs["counties"], dict) else cs["counties"]

    cohorts = [
        ("all_contested", "All Contested Counties", "National Baseline", lambda c: True),
        (
            "majority_hispanic",
            "Majority-Hispanic Counties (>=50% Hispanic)",
            "ICE / Deportations Overreach (57%-60%) & Affordability",
            lambda c: (c.get("dem", {}).get("hisp") or 0) >= 50,
        ),
        (
            "high_hispanic",
            "High-Hispanic Counties (30%-50% Hispanic)",
            "ICE / Deportations Overreach & Cost of Living",
            lambda c: 30 <= (c.get("dem", {}).get("hisp") or 0) < 50,
        ),
        (
            "farm_belt_rural",
            "Plains & Midwest Farm Belt Rural (IA, KS, NE, ND, SD)",
            "Tariffs / Retaliatory Ag Exports (66%) & Iran Diesel Spike",
            lambda c: c.get("state") in {"IA", "KS", "NE", "ND", "SD"}
            and "Rural" in (c.get("dem", {}).get("urb") or ""),
        ),
        (
            "working_class_white",
            "Working-Class Non-College White (>=80% WNH, <22% BA)",
            "Iran War (60%-63% Wrong Decision) & Tariff Inflation",
            lambda c: (c.get("dem", {}).get("wnh") or 0) >= 80
            and (c.get("dem", {}).get("ba") or 100) < 22,
        ),
        (
            "high_ed_suburbs",
            "High-Education Suburban/Urban (>=40% BA)",
            "Corruption (90% Major/Crucial), Ballroom (56%-65%) & Checks on Power",
            lambda c: (c.get("dem", {}).get("ba") or 0) >= 40,
        ),
        (
            "high_black",
            "High-Black Counties (>=30% Black)",
            "Healthcare Costs (60%), Federal Workforce Cuts & Affordability",
            lambda c: (c.get("dem", {}).get("blk") or 0) >= 30,
        ),
        (
            "deep_red_trump40",
            "Deep-Red Trump +40 Counties (2024 Margin <= -40)",
            "Rural Economic Squeeze, Fuel Costs & Broad Incumbent Backlash",
            lambda c: (c.get("p24", {}).get("m") or 0) <= -40,
        ),
    ]

    cohort_results = []
    for cid, label, trigger, pred in cohorts:
        sub = [c for c in counties if pred(c)]
        cohort_results.append(
            {
                "cohort_id": cid,
                "cohort_label": label,
                "primary_issue_trigger": trigger,
                "total_counties_in_cohort": len(sub),
                "shifts": {
                    "pres_2020_to_2024": summarize_shifts(
                        [shift(c, "p24", "p20") for c in sub if shift(c, "p24", "p20") is not None]
                    ),
                    "first_term_midterm_2016_to_2018_house": summarize_shifts(
                        [shift(c, "h18", "p16") for c in sub if shift(c, "h18", "p16") is not None]
                    ),
                    "top_of_ticket_2024_to_2026": summarize_shifts(
                        [shift(c, "top26", "p24") for c in sub if shift(c, "top26", "p24") is not None]
                    ),
                    "us_senate_2024_to_2026": summarize_shifts(
                        [shift(c, "s26", "p24") for c in sub if shift(c, "s26", "p24") is not None]
                    ),
                    "us_house_2024_to_2026": summarize_shifts(
                        [shift(c, "h26", "p24") for c in sub if shift(c, "h26", "p24") is not None]
                    ),
                    "governor_2024_to_2026": summarize_shifts(
                        [shift(c, "g26", "p24") for c in sub if shift(c, "g26", "p24") is not None]
                    ),
                    "attorney_general_2024_to_2026": summarize_shifts(
                        [shift(c, "ag26", "p24") for c in sub if shift(c, "ag26", "p24") is not None]
                    ),
                },
            }
        )

    # Down-ballot statewide executive summary
    by_office = {}
    for r in ov.get("statewide_exec_races", []):
        if r.get("uncontested") or r.get("one_party"):
            continue
        sh = r.get("shift_vs_pres_2024")
        if sh is not None:
            off = r.get("office", "Other")
            by_office.setdefault(off, []).append(sh)

    downballot_exec_summary = {}
    all_exec_shifts = []
    for off, arr in sorted(by_office.items(), key=lambda x: -len(x[1])):
        downballot_exec_summary[off] = summarize_shifts(arr)
        all_exec_shifts.extend(arr)
    downballot_exec_summary["ALL_CONTESTED_STATEWIDE_EXEC"] = summarize_shifts(all_exec_shifts)

    # County-level cross-office correlations (Federal vs State Down-Ballot)
    pairs_s_ag = [
        (shift(c, "s26"), shift(c, "ag26"))
        for c in counties
        if shift(c, "s26") is not None and shift(c, "ag26") is not None
    ]
    pairs_h_ag = [
        (shift(c, "h26"), shift(c, "ag26"))
        for c in counties
        if shift(c, "h26") is not None and shift(c, "ag26") is not None
    ]
    pairs_s_h = [
        (shift(c, "s26"), shift(c, "h26"))
        for c in counties
        if shift(c, "s26") is not None and shift(c, "h26") is not None
    ]

    output = {
        "fetched_at": ov.get("fetched_at"),
        "description": (
            "Empirical test of the 'Disjoint Breaking Points & Jump Discontinuity (Bitch Eating Crackers)' "
            "hypothesis in the 2026 U.S. Midterm Elections, combining national exit/issue polling with "
            "3,143-county cross-ballot shift data."
        ),
        "exit_and_issue_polling": exit_polls,
        "disjoint_county_cohorts": cohort_results,
        "downballot_contagion": {
            "county_correlations": {
                "us_senate_vs_state_ag_shift": {
                    "n_counties": len(pairs_s_ag),
                    "pearson_r": pearson([p[0] for p in pairs_s_ag], [p[1] for p in pairs_s_ag]),
                },
                "us_house_vs_state_ag_shift": {
                    "n_counties": len(pairs_h_ag),
                    "pearson_r": pearson([p[0] for p in pairs_h_ag], [p[1] for p in pairs_h_ag]),
                },
                "us_senate_vs_us_house_shift": {
                    "n_counties": len(pairs_s_h),
                    "pearson_r": pearson([p[0] for p in pairs_s_h], [p[1] for p in pairs_s_h]),
                },
            },
            "statewide_downballot_executive_races": downballot_exec_summary,
        },
    }

    out_path = SITE_DATA / "breaking_points_2026.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return output


if __name__ == "__main__":
    build_breaking_points()

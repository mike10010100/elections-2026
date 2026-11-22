#!/usr/bin/env python3
"""
Builds side-by-side Election Week (Nov. 4-5) vs. Near-Final (Live) faction
comparisons for both U.S. House caucuses (n=418, with 2024 ACS 1-year CD
demographic controls) and U.S. Senate / Statewide ideological quadrants (N=36).

Outputs:
  - data/cd_2024_acs1_caucus_cache.json (local cache, gitignored)
  - site_data/morris_nov4_vs_nov22_comparison.json
  - assets/chart14_house_caucus_nov5_vs_nov22.png
  - assets/chart15_senate_statewide_nov4_vs_nov22.png
"""
import csv
import io
import json
import os
import re
import shutil
import statistics
import subprocess
import tempfile
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from sklearn.linear_model import HuberRegressor

plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
plt.rcParams["text.parse_math"] = False

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"

CACHE_PATH = DATA_DIR / "cd_2024_acs1_caucus_cache.json"
OUT_JSON = SITE_DATA / "morris_nov4_vs_nov22_comparison.json"
CHART14_PATH = ASSETS_DIR / "chart14_house_caucus_nov5_vs_nov22.png"
CHART15_PATH = ASSETS_DIR / "chart15_senate_statewide_nov4_vs_nov22.png"

BASE_CENSUS = "https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

STATE_NAME_TO_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
    "Wisconsin": "WI", "Wyoming": "WY",
}
VALID_STATES = set(STATE_NAME_TO_ABBR.values())

# Morris's Nov. 4 reference groups (reproduced identically to Chart 1 & Chart 2)
MORRIS_HOUSE_NOV4 = {
    "source_date": "2026-11-04",
    "n": 404,
    "party_mean_shift": 14.3,
    "groups": [
        {"key": "blue_dogs", "label": "Blue Dogs", "n": 30, "raw_mean": 18.4, "adj_mean": 16.8, "edge": 2.5, "ci95_edge": [1.2, 3.8]},
        {"key": "blue_dogs_ex_tx", "label": "Blue Dogs\nex-TX-15/28", "n": 28, "raw_mean": 16.5, "adj_mean": 15.7, "edge": 1.4, "ci95_edge": [0.2, 2.6]},
        {"key": "dsa_carveout", "label": "DSA carveout", "n": 7, "raw_mean": 17.5, "adj_mean": 15.2, "edge": 0.9, "ci95_edge": [-1.0, 2.8]},
        {"key": "new_dems", "label": "New Dems", "n": 129, "raw_mean": 14.2, "adj_mean": 14.5, "edge": 0.2, "ci95_edge": [-0.4, 0.8]},
        {"key": "no_caucus", "label": "No caucus", "n": 182, "raw_mean": 14.3, "adj_mean": 14.2, "edge": -0.1, "ci95_edge": [-0.5, 0.3]},
        {"key": "cpc", "label": "CPC /\nprogressives", "n": 84, "raw_mean": 13.0, "adj_mean": 13.6, "edge": -0.7, "ci95_edge": [-1.4, -0.05]},
    ],
}

MORRIS_SENATE_CH2 = [
    ("SC", "Annie Andrews", 7.8, False),
    ("TX", "James Talarico", 7.4, False),
    ("MS", "Scott Colom", 5.9, False),
    ("NC", "Roy Cooper", 5.9, False),
    ("GA", "Jon Ossoff", 5.8, False),
    ("NM", "Ben Ray Luján", 3.4, False),
    ("IA", "Josh Turek", 3.2, False),
    ("OH", "Sherrod Brown", 2.8, False),
    ("AK", "Mary Peltola*", -3.66, False),  # Benchmark from Nov. 7 early partial (national House avg)
    ("MI", "Abdul El-Sayed", -1.4, True),
    ("FL", "Angie Nixon", -1.7, True),
    ("MN", "Peggy Flanagan", -1.8, True),
    ("TN", "Marquita Bradshaw", -1.9, True),
    ("MA", "Ed Markey", -5.0, True),
    ("ME", "Troy Jackson", -9.8, True),
]


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.stem}_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def _optimize_png(path: Path) -> None:
    ffmpeg_bin = shutil.which("ffmpeg") or "/home/linuxbrew/.linuxbrew/bin/ffmpeg"
    if not Path(ffmpeg_bin).exists():
        return
    pal = path.with_name(f".{path.stem}_pal.png")
    opt = path.with_name(f".{path.stem}_opt.png")
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(path), "-vf", "palettegen=max_colors=256", str(pal)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(path), "-i", str(pal), "-lavfi", "paletteuse=dither=sierra2_4a", str(opt)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if opt.exists() and opt.stat().st_size > 0:
        opt.replace(path)
    if pal.exists():
        pal.unlink()


def _fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", errors="ignore")


def _fetch_wiki(page: str) -> str:
    u = f"https://en.wikipedia.org/w/api.php?action=parse&page={page}&prop=wikitext&format=json"
    req = urllib.request.Request(u, headers={"User-Agent": "Elections2026Analyzer/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())["parse"]["wikitext"]["*"]


def _parse_dist_name(s: str):
    m = re.search(
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)'s\s+(?:(\d+)(?:st|nd|rd|th)|at-large)\s+congressional district",
        s, re.I,
    )
    if m and STATE_NAME_TO_ABBR.get(m.group(1)):
        return f"{STATE_NAME_TO_ABBR[m.group(1)]}-{int(m.group(2)) if m.group(2) else 1:02d}"
    m2 = re.search(
        r"U\.S\. House\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:District\s+(\d+)|At-large)",
        s, re.I,
    )
    if m2 and STATE_NAME_TO_ABBR.get(m2.group(1)):
        return f"{STATE_NAME_TO_ABBR[m2.group(1)]}-{int(m2.group(2)) if m2.group(2) else 1:02d}"
    return None


def _extract_abbr_dists(text: str) -> set[str]:
    out = set()
    for st, num in re.findall(r"\b([A-Z]{2})-(AL|\d{1,2})\b", text):
        if st in VALID_STATES:
            out.add(f"{st}-{'01' if num == 'AL' else f'{int(num):02d}'}")
    return out


def _norm_last(name: str) -> str:
    toks = [t for t in re.sub(r"[^a-zA-Z\s-]", "", name).split() if t.lower() not in {"jr", "sr", "ii", "iii", "iv"}]
    return toks[-1].lower() if toks else ""


def _contested_house_map(ov: dict) -> dict[str, dict]:
    out = {}
    for h in ov.get("house_races", []):
        parties = [c.get("party") for c in h.get("candidates", [])]
        if "DEM" in parties and "GOP" in parties and not h.get("uncontested") and not h.get("one_party"):
            out[f"{h['state']}-{int(h['seat_number']):02d}"] = h
    return out


def load_or_build_cache(ov_live: dict) -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))

    # 1. Official 2024 ACS 1-year Congressional District demographics from www2.census.gov
    geos_txt = _fetch_text(f"{BASE_CENSUS}/documentation/Geos20241YR.txt")
    geoid_to_cd = {}
    reader = csv.DictReader(io.StringIO(geos_txt), delimiter="|")
    cd_col = next((c for c in reader.fieldnames if c.startswith("CD")), None)
    for row in reader:
        if row["SUMLEVEL"] == "500" and row["COMPONENT"] == "00":
            st = row["STUSAB"].upper()
            cd_raw = row[cd_col].strip()
            if cd_raw.isdigit():
                cd_num = int(cd_raw) or 1
                geoid_to_cd[row["GEO_ID"]] = f"{st}-{cd_num:02d}"

    def _parse_acs(fname: str, fn) -> dict[str, float]:
        txt = _fetch_text(f"{BASE_CENSUS}/data/1YRData/{fname}")
        out = {}
        for row in csv.DictReader(io.StringIO(txt), delimiter="|"):
            gid = row["GEO_ID"]
            if gid in geoid_to_cd:
                val = fn(row)
                if val is not None:
                    out[geoid_to_cd[gid]] = round(float(val), 4)
        return out

    hisp = _parse_acs("acsdt1y2024-b03003.dat", lambda r: float(r["B03003_E003"]) / float(r["B03003_E001"]) * 100.0 if float(r["B03003_E001"] or 0) > 0 else None)
    pov = _parse_acs("acsdt1y2024-b17001.dat", lambda r: float(r["B17001_E002"]) / float(r["B17001_E001"]) * 100.0 if float(r["B17001_E001"] or 0) > 0 else None)
    ba = _parse_acs("acsdt1y2024-b15003.dat", lambda r: (float(r["B15003_E022"]) + float(r["B15003_E023"]) + float(r["B15003_E024"]) + float(r["B15003_E025"])) / float(r["B15003_E001"]) * 100.0 if float(r["B15003_E001"] or 0) > 0 else None)

    acs_cd = {cd: {"hisp": hisp[cd], "pov": pov[cd], "ba": ba[cd]} for cd in sorted(set(hisp) & set(pov) & set(ba))}

    # 2. Verified 2026 House caucus & endorsement rosters matched to live Democratic nominees
    h_live = _contested_house_map(ov_live)
    dem_name = {k: next(c["name"] for c in h_live[k]["candidates"] if c["party"] == "DEM") for k in h_live}

    bd_wt = _fetch_wiki("Blue_Dog_Coalition")
    bd_set = set()
    for row in re.search(r"=== Current members ===(.*?)(?=\n== )", bd_wt, re.S).group(1).split("|-")[1:]:
        for d in _extract_abbr_dists(row):
            if d in dem_name and _norm_last(dem_name[d]) in row.lower():
                bd_set.add(d)
    for row in re.search(r"=== 2026 ===(.*?)(?=\n== )", bd_wt, re.S).group(1).split("|-")[1:]:
        d = _parse_dist_name(row)
        if d and d in dem_name and _norm_last(dem_name[d]) in row.lower():
            bd_set.add(d)
    for extra_d, extra_last in [("KS-02", "coover"), ("FL-02", "green"), ("CO-03", "romero"), ("UT-04", "mcadams"), ("IL-08", "bean"), ("FL-07", "dalton")]:
        if extra_d in dem_name and extra_last in dem_name[extra_d].lower():
            bd_set.add(extra_d)

    nd_wt = _fetch_wiki("New_Democrat_Coalition")
    nd_inc = {
        d
        for row in re.search(r"== Membership ==(.*?)(?=\n== |\Z)", nd_wt, re.S).group(1).split("|-")[1:]
        for d in _extract_abbr_dists(row)
        if d in dem_name and _norm_last(dem_name[d]) in row.lower()
    }
    nd_html = _fetch_text("https://www.newdemactionfund.com/candidates")
    nd_af = {d for d in _extract_abbr_dists(nd_html) if d in dem_name and _norm_last(dem_name[d]) in nd_html.lower()}
    new_dems = nd_inc | nd_af

    cpc_wt = _fetch_wiki("List_of_members_of_the_Congressional_Progressive_Caucus")
    cpc_inc = {
        d
        for line in re.search(r"== Current House members ==(.*?)(?=\n== Former members ==)", cpc_wt, re.S).group(1).splitlines()
        for d in _extract_abbr_dists(line)
        if d in dem_name and _norm_last(dem_name[d]) in line.lower()
    }
    cpc_html = _fetch_text("https://ballotpedia.org/Endorsements_by_Congressional_Progressive_Caucus_PAC")
    cpc_26 = set()
    for m in re.finditer(r"<tr>(.*?)</tr>", cpc_html, re.S):
        rtxt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1)))
        if "(2026)" in rtxt and ("Won General" in rtxt or "Lost General" in rtxt):
            d = _parse_dist_name(rtxt)
            if d and d in dem_name and _norm_last(dem_name[d]) in rtxt.lower():
                cpc_26.add(d)
    cpc_all = cpc_inc | cpc_26

    dsa_html = _fetch_text("https://ballotpedia.org/Endorsements_by_Democratic_Socialists_of_America,_2026")
    m_dsa_sec = re.search(r"U\.S\. House endorsements by DSA(.*?)State (?:executive|legislative) endorsements", dsa_html, re.S)
    dsa_gen = set()
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", m_dsa_sec.group(1), re.S):
        rtxt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
        if "Won general" in rtxt or "Lost general" in rtxt:
            d = _parse_dist_name(rtxt)
            if d and d in dem_name and _norm_last(dem_name[d]) in rtxt.lower():
                dsa_gen.add(d)

    # 3. Frozen Nov. 5 House margins & Nov. 7 Statewide/Alaska baselines from git history
    ov5 = json.loads(subprocess.check_output(["git", "-C", str(BASE_DIR), "show", "51dc5ab:site_data/overview.json"], text=True))
    h5 = _contested_house_map(ov5)
    nov5_margins = {k: {"dem_gop_margin": h5[k]["dem_gop_margin"], "eevp": h5[k].get("eevp")} for k in sorted(h5)}

    bg_nov7 = json.loads(subprocess.check_output(["git", "-C", str(BASE_DIR), "show", "76ee897:site_data/bonica_grumbach_methodology_test_2026.json"], text=True))
    rh_nov7 = json.loads(subprocess.check_output(["git", "-C", str(BASE_DIR), "show", "cb5c6b3:site_data/rhetoric_vs_record_2026.json"], text=True))
    ak_nov7 = next((c["overperf_vs_benchmark"] for c in rh_nov7["candidates"] if "Peltola" in c.get("name", "")), -3.66)

    cache = {
        "acs_cd": acs_cd,
        "rosters": {
            "blue_dogs": sorted(bd_set),
            "new_dems": sorted(new_dems),
            "cpc": sorted(cpc_all),
            "dsa_2026_endorsed": sorted(dsa_gen),
            "dsa_plus_casar": sorted(dsa_gen | ({"TX-37"} & set(dem_name))),
        },
        "nov5_house_margins": nov5_margins,
        "nov7_statewide_baseline": {
            "ak_peltola_overperf": ak_nov7,
            "quadrants": bg_nov7["test2_quadrant_summary_after_within_district_fix"],
            "statewide36_full_model": bg_nov7["test3_multivariate_regression_models"]["statewide36_full_covariate_model"],
        },
    }
    _atomic_write_json(CACHE_PATH, cache)
    return cache


def run_house_caucus_huber(valid_dists: list[str], margins_by_dist: dict[str, float], h_live: dict[str, dict], acs_cd: dict[str, dict], groups_def: list[tuple[str, str, set[str]]]):
    y = np.array([margins_by_dist[d] - h_live[d]["pres_2024_margin"] for d in valid_dists], dtype=float)
    X_ctrl = np.column_stack([
        [h_live[d]["pres_2024_margin"] for d in valid_dists],
        [1.0 if any(c.get("party") == "DEM" and c.get("incumbent") for c in h_live[d]["candidates"]) else 0.0 for d in valid_dists],
        [1.0 if any(c.get("party") == "GOP" and c.get("incumbent") for c in h_live[d]["candidates"]) else 0.0 for d in valid_dists],
        [acs_cd[d]["hisp"] for d in valid_dists],
        [acs_cd[d]["pov"] for d in valid_dists],
        [acs_cd[d]["ba"] for d in valid_dists],
    ])
    Xc_z = (X_ctrl - X_ctrl.mean(axis=0)) / X_ctrl.std(axis=0)
    party_mean = float(np.mean(y))
    party_median = float(np.median(y))

    rng = np.random.default_rng(42)
    idx_all = np.arange(len(valid_dists))
    out = []
    for key, label, gset in groups_def:
        mask = np.array([1.0 if d in gset else 0.0 for d in valid_dists], dtype=float)
        n_g = int(mask.sum())
        p_g = n_g / len(valid_dists)
        raw_mean = float(np.mean(y[mask == 1]))
        raw_med = float(np.median(y[mask == 1]))
        Xg = np.column_stack([mask, Xc_z])
        hr = HuberRegressor(max_iter=500, alpha=0.0).fit(Xg, y)
        adj_edge = float((1.0 - p_g) * hr.coef_[0])
        adj_mean = party_mean + adj_edge

        boots = []
        for _ in range(800):
            b = rng.choice(idx_all, size=len(valid_dists), replace=True)
            if mask[b].sum() < 2:
                continue
            p_b = float(mask[b].mean())
            hb = HuberRegressor(max_iter=500, alpha=0.0).fit(Xg[b], y[b])
            boots.append(float((1.0 - p_b) * hb.coef_[0]))
        ci_lo = float(np.percentile(boots, 2.5))
        ci_hi = float(np.percentile(boots, 97.5))

        out.append({
            "key": key,
            "label": label,
            "n": n_g,
            "raw_mean": round(raw_mean, 2),
            "raw_median": round(raw_med, 2),
            "adj_edge": round(adj_edge, 2),
            "adj_mean": round(adj_mean, 2),
            "ci95_edge": [round(ci_lo, 2), round(ci_hi, 2)],
            "ci95_mean": [round(party_mean + ci_lo, 2), round(party_mean + ci_hi, 2)],
        })
    return {"n": len(valid_dists), "party_mean": round(party_mean, 2), "party_median": round(party_median, 2), "groups": out}


def generate_chart14(data: dict) -> None:
    BG = "#f4f3ef"
    DARK = "#18181b"
    SUB = "#4b5563"
    MUTED = "#71717a"
    GRID = "#dedcd6"
    COLORS = {
        "blue_dogs": "#1b4f72",
        "blue_dogs_ex_tx": "#2e86c1",
        "dsa_carveout": "#8e44ad",
        "new_dems": "#0f766e",
        "no_caucus": "#64748b",
        "cpc": "#d35400",
        "cpc_only": "#9a3412",
    }

    fig = plt.figure(figsize=(16.5, 9.8), dpi=200, facecolor=BG)
    ax_a = fig.add_axes([0.145, 0.130, 0.340, 0.640], facecolor=BG)
    ax_b = fig.add_axes([0.555, 0.130, 0.420, 0.640], facecolor=BG)

    nov5 = data["house_replicated_nov5"]
    live = data["house_replicated_live"]
    g_n5 = {g["key"]: g for g in nov5["groups"]}
    g_lv = {g["key"]: g for g in live["groups"]}

    dsa_delta = g_lv["dsa_carveout"]["adj_edge"] - g_n5["dsa_carveout"]["adj_edge"]

    fig.text(
        0.028, 0.942,
        f"U.S. House Factions: Morris's Nov. 4 Chart vs. Near-Final Returns (n={live['n']})",
        fontsize=20.0, fontweight="bold", color=DARK,
    )
    fig.text(
        0.028, 0.903,
        f"Left: G. Elliott Morris's Nov. 4 snapshot (n={MORRIS_HOUSE_NOV4['n']}, party avg +{MORRIS_HOUSE_NOV4['party_mean_shift']:.1f}). "
        f"Right: Verified 2026 rosters + 2024 ACS1 CD controls (Nov. 5 +{nov5['party_mean']:.1f} -> Live +{live['party_mean']:.1f}).",
        fontsize=11.0, color=SUB,
    )
    fig.text(
        0.028, 0.871,
        f"Late mail lifted party avg (+{nov5['party_mean']:.1f} -> +{live['party_mean']:.1f}): Blue Dogs widened #1 & #2 ({g_n5['blue_dogs']['adj_edge']:+.2f} -> {g_lv['blue_dogs']['adj_edge']:+.2f}), "
        f"DSA lost {abs(dsa_delta):.2f} pts relative edge, & CPC-only finished last ({g_lv['cpc_only']['adj_edge']:+.2f}).",
        fontsize=10.6, fontweight="bold", color="#1b4f72",
    )

    # Row alignment: y = 6..1 match across Panel A and B; y = 0 is CPC-only in Panel B
    row_keys = ["blue_dogs", "blue_dogs_ex_tx", "dsa_carveout", "new_dems", "no_caucus", "cpc", "cpc_only"]
    y_vals = [6, 5, 4, 3, 2, 1, 0]

    # ---- Panel A: Morris Nov 4 ----
    ax_a.set_title(
        "A. Morris's Nov. 4 Benchmark (n=404)\nAdjusted Edge vs. Party Avg (+14.3 pts) & 95% CIs",
        fontsize=11.0, fontweight="bold", color=DARK, loc="left", pad=10,
    )
    ax_a.axvline(0.0, color="#222222", lw=1.4, zorder=2)

    m_by_key = {g["key"]: g for g in MORRIS_HOUSE_NOV4["groups"]}
    y_labels_a = []
    for k, y in zip(row_keys, y_vals):
        if k not in m_by_key:
            y_labels_a.append("CPC-only\n(ex-New Dem)")
            continue
        g = m_by_key[k]
        y_labels_a.append(f"{g['label']} ({g['n']})")
        col = COLORS[k]
        lo, hi = g["ci95_edge"]
        ax_a.plot([lo, hi], [y, y], color=col, lw=6.0, alpha=0.28, solid_capstyle="round", zorder=3)
        ax_a.scatter([g["edge"]], [y], color=col, s=115, edgecolor="white", lw=0.9, zorder=5)
        if g["edge"] >= 0:
            ax_a.text(hi + 0.16, y, f"{g['edge']:+.1f} (adj +{g['adj_mean']:.1f})", fontsize=8.6, fontweight="bold", color=col, va="center", ha="left")
        else:
            ax_a.text(lo - 0.16, y, f"{g['edge']:+.1f} (adj +{g['adj_mean']:.1f})", fontsize=8.6, fontweight="bold", color=col, va="center", ha="right")

    ax_a.axhline(0.5, color="#cbd5e1", ls="--", lw=1.0, zorder=1)
    ax_a.text(
        0.5, 0.0,
        "Row omitted in Morris's Nov. 4 chart:\n28 dual CPC+New Dem members were double-counted,\npropping up the CPC row above CPC-only",
        fontsize=8.0, style="italic", color=MUTED, ha="center", va="center",
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#ffffff", edgecolor="#cbd5e1", lw=1.0),
    )

    ax_a.set_yticks(y_vals)
    ax_a.set_yticklabels(y_labels_a, fontsize=9.6, fontweight="bold", color=DARK)
    ax_a.set_xlim(-5.2, 6.4)
    ax_a.set_ylim(-0.75, 6.65)
    ax_a.xaxis.grid(True, color=GRID, lw=0.8)
    ax_a.yaxis.grid(True, color=GRID, lw=0.5, alpha=0.5)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.set_xlabel("Adjusted Over/Underperformance vs. House Avg (pts)", fontsize=9.8, fontweight="bold", color=SUB)

    # ---- Panel B: Verified Nov 5 -> Live Replication ----
    ax_b.set_title(
        f"B. Full-Count Replication (n={live['n']}, Verified 2024 ACS1 CD Controls)\nAdjusted Edge: Nov. 5 (Hollow) -> Live Near-Final (Solid + 95% CI)",
        fontsize=11.0, fontweight="bold", color=DARK, loc="left", pad=10,
    )
    ax_b.axvline(0.0, color="#222222", lw=1.4, zorder=2)
    ax_b.axhline(0.5, color="#cbd5e1", ls="--", lw=1.0, zorder=1)

    y_labels_b = []
    for k, y in zip(row_keys, y_vals):
        o = g_n5[k]
        n = g_lv[k]
        y_labels_b.append(f"(n={n['n']})")
        col = COLORS[k]
        lo, hi = n["ci95_edge"]
        ax_b.plot([lo, hi], [y, y], color=col, lw=6.0, alpha=0.28, solid_capstyle="round", zorder=3)
        ax_b.plot([o["adj_edge"], n["adj_edge"]], [y, y], color=col, lw=2.3, zorder=4)
        ax_b.scatter([o["adj_edge"]], [y], color="white", edgecolor=col, s=90, lw=2.1, zorder=5,
                     label="Nov. 5 Snapshot (same model)" if k == "blue_dogs" else "")
        ax_b.scatter([n["adj_edge"]], [y], color=col, s=115, edgecolor="white", lw=0.9, zorder=6,
                     label="Live Near-Final (Nov. 22)" if k == "blue_dogs" else "")

        delta = n["adj_edge"] - o["adj_edge"]
        lbl = f"{o['adj_edge']:+.2f} -> {n['adj_edge']:+.2f} ({delta:+.2f})"
        if k == "cpc_only":
            ax_b.text(n["adj_edge"], y + 0.19, lbl, fontsize=8.3, fontweight="bold", color=col, va="bottom", ha="center")
        elif k in ("no_caucus", "cpc"):
            ax_b.text(lo - 0.14, y, lbl, fontsize=8.3, fontweight="bold", color=col, va="center", ha="right")
        else:
            ax_b.text(hi + 0.14, y, lbl, fontsize=8.3, fontweight="bold", color=col, va="center", ha="left")

    # Informative annotations cleanly tucked in open canvas areas
    ax_b.annotate(
        f"DSA (n={g_lv['dsa_carveout']['n']} w/ Casar): Raw flat (+16.1)\nwhile CA/MD mail lifted party avg (+{live['party_mean']:.1f});\nedge fell {dsa_delta:+.2f} pts (95% CI crosses 0)",
        xy=(g_lv["dsa_carveout"]["adj_edge"] + 0.08, 4.08),
        xytext=(3.1, 4.70),
        arrowprops=dict(arrowstyle="->", color=COLORS["dsa_carveout"], lw=1.4, connectionstyle="arc3,rad=0.15"),
        fontsize=8.1, fontweight="bold", color=COLORS["dsa_carveout"],
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#faf5ff", edgecolor=COLORS["dsa_carveout"], lw=1.1),
        zorder=8,
    )

    ax_b.annotate(
        f"29 dual New Dem+CPC members excluded:\nCPC-only finishes dead last ({g_lv['cpc_only']['adj_edge']:+.2f} pts)",
        xy=(hi + 0.08, 0.0),
        xytext=(2.1, -0.05),
        arrowprops=dict(arrowstyle="->", color=COLORS["cpc_only"], lw=1.4),
        fontsize=8.1, fontweight="bold", color=COLORS["cpc_only"],
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#fff7ed", edgecolor=COLORS["cpc_only"], lw=1.1),
        zorder=8,
    )

    ax_b.legend(loc="lower right", bbox_to_anchor=(0.99, 0.22), fontsize=8.4, framealpha=0.95, facecolor="white", edgecolor="#cbd5e1")
    ax_b.set_yticks(y_vals)
    ax_b.set_yticklabels(y_labels_b, fontsize=9.0, fontweight="bold", color=SUB)
    ax_b.set_xlim(-5.9, 7.6)
    ax_b.set_ylim(-0.75, 6.65)
    ax_b.xaxis.grid(True, color=GRID, lw=0.8)
    ax_b.yaxis.grid(True, color=GRID, lw=0.5, alpha=0.5)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.set_xlabel("Adjusted Over/Underperformance vs. House Avg (pts)", fontsize=9.8, fontweight="bold", color=SUB)

    fig.text(
        0.028, 0.025,
        f"Sources: Left = G. Elliott Morris (@gelliottmorris.com, Nov. 4, 2026). Right = Verified House rosters (Wikipedia 119th Congress, Blue Dog PAC, NewDem Action Fund, CPC PAC, DSA 2026) + U.S. Census 2024 ACS 1-Year\n"
        f"CD controls (% Hispanic, % Poverty, % BA+) + verified within-district Harris 2024 & incumbency (n={live['n']}). Updated {data['fetched_at']}. Group edge = (1 - p_g) * Huber coefficient; 800-draw bootstrap 95% CIs.",
        fontsize=8.5, color=MUTED,
    )

    fig.savefig(CHART14_PATH, dpi=200, facecolor=BG)
    plt.close(fig)
    _optimize_png(CHART14_PATH)


def generate_chart15(data: dict) -> None:
    BG = "#f4f3ef"
    DARK = "#18181b"
    SUB = "#4b5563"
    MUTED = "#71717a"
    GRID = "#dedcd6"
    TEAL = "#0f766e"
    BLUE = "#1b4f72"
    ORANGE = "#d35400"
    GOLD = "#b45309"

    fig = plt.figure(figsize=(16.5, 9.8), dpi=200, facecolor=BG)
    ax_a = fig.add_axes([0.165, 0.130, 0.355, 0.640], facecolor=BG)
    ax_b = fig.add_axes([0.650, 0.315, 0.325, 0.455], facecolor=BG)
    ax_r = fig.add_axes([0.555, 0.130, 0.420, 0.118], facecolor="#ffffff")

    sen_rows = data["senate_nov4_vs_live"]
    q_comp = data["statewide36_quadrant_nov7_vs_live"]
    reg_comp = data["statewide36_regression_nov7_vs_live"]

    fig.text(
        0.028, 0.942,
        "Senate & Statewide Factions: How Late Ballots Strengthened the Moderate Edge",
        fontsize=20.0, fontweight="bold", color=DARK,
    )
    fig.text(
        0.028, 0.903,
        "Left: All 14 Chart-2 Senate races + Mary Peltola (AK*), Election Week (hollow) -> Near-Final Live (solid). Right: N=36 Statewide Quadrants & Regression (Nov. 7 -> Live).",
        fontsize=10.8, color=SUB,
    )
    fig.text(
        0.028, 0.871,
        f"Late rural/mail ballots flipped AK's Peltola ({sen_rows[8]['early']:+.1f} -> {sen_rows[8]['live']:+.2f}, won R1), pushed Committed Moderates to 90% beating benchmark, & lifted R² ({reg_comp['nov7']['r2']:.3f} -> {reg_comp['live']['r2']:.3f}).",
        fontsize=10.4, fontweight="bold", color=BLUE,
    )

    # ---- Panel A: 15 Senate Races Dumbbell ----
    ax_a.set_title(
        "A. Senate Outperformance vs. State House Avg (pts)\nMorris Nov. 4 / Early Partial (Hollow) -> Near-Final Live (Solid)",
        fontsize=10.9, fontweight="bold", color=DARK, loc="left", pad=10,
    )
    n_s = len(sen_rows)
    y_s = np.arange(n_s)[::-1]

    # Shading zones: AK gold highlight (index 8 -> y=6), Progressive 0-for-6 zone (indices 9..14 -> y=5..0)
    ax_a.axhspan(5.52, 6.48, color="#fef3c7", alpha=0.80, zorder=1)
    ax_a.axhspan(-0.55, 5.48, xmin=0, xmax=0.56, color="#fdedec", alpha=0.55, zorder=1)
    ax_a.axvline(0.0, color="#222222", lw=1.4, zorder=2)

    ylabels_a = []
    for y, row in zip(y_s, sen_rows):
        st, nm, early_v, live_v, is_prog = row["state"], row["candidate"], row["early"], row["live"], row["is_prog"]
        tag = f"{st}: {nm}" + (" (Prog)" if is_prog else (" (Mod)" if st == "AK" else ""))
        ylabels_a.append(tag)
        col = ORANGE if is_prog else (GOLD if st == "AK" else BLUE)

        ax_a.plot([early_v, live_v], [y, y], color=col, lw=2.6, zorder=3)
        ax_a.scatter([early_v], [y], color="white", edgecolor=col, s=80, lw=2.0, zorder=4,
                     label="Morris Nov. 4 / Nov. 7 Early" if y == 14 else "")
        ax_a.scatter([live_v], [y], color=col, s=105, edgecolor="white", lw=0.8, zorder=5,
                     label="Live Near-Final (Nov. 22)" if y == 14 else "")

        delta = live_v - early_v
        if st == "ME":
            ax_a.text(max(early_v, live_v) + 0.35, y, f"{early_v:+.1f} -> {live_v:+.1f} ({delta:+.1f})", fontsize=8.1, fontweight="bold", color=col, va="center", ha="left")
        elif st == "AK":
            ax_a.text(live_v + 0.35, y, f"{early_v:+.1f} -> {live_v:+.1f} ({delta:+.1f}, won R1!)", fontsize=8.2, fontweight="bold", color=GOLD, va="center", ha="left")
        elif is_prog:
            ax_a.text(min(early_v, live_v) - 0.35, y, f"{early_v:+.1f} -> {live_v:+.1f} ({delta:+.1f})", fontsize=8.1, fontweight="bold", color=col, va="center", ha="right")
        else:
            ax_a.text(max(early_v, live_v) + 0.35, y, f"{early_v:+.1f} -> {live_v:+.1f} ({delta:+.1f})", fontsize=8.1, fontweight="bold", color=col, va="center", ha="left")

    ax_a.text(
        -11.9, 10.6,
        "Progressive 0-for-6\nheld steady (-0.2 to -9.7);\nMarkey widened -5.0 -> -6.6",
        fontsize=8.2, fontweight="bold", color=ORANGE,
        bbox=dict(boxstyle="round,pad=0.30", facecolor="#fff7ed", edgecolor=ORANGE, lw=1.1),
        zorder=7,
    )

    ax_a.legend(loc="lower right", fontsize=8.1, framealpha=0.95, facecolor="white", edgecolor="#cbd5e1")
    ax_a.set_yticks(y_s)
    ax_a.set_yticklabels(ylabels_a, fontsize=9.0, fontweight="bold", color=DARK)
    ax_a.set_xlim(-12.5, 13.0)
    ax_a.set_ylim(-0.65, n_s - 0.35)
    ax_a.xaxis.grid(True, color=GRID, lw=0.8)
    ax_a.yaxis.grid(True, color=GRID, lw=0.5, alpha=0.45)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    ax_a.set_xlabel("Senate Margin Shift Minus State House Avg Shift (pts)", fontsize=9.7, fontweight="bold", color=SUB)

    # ---- Panel B: N=36 Statewide Quadrants (Nov 7 -> Live) ----
    ax_b.set_title(
        "B. N=36 Statewide Faction Quadrants vs. House Benchmark\nNov. 7 Initial Partial (Hollow) -> Live Near-Final (Solid)",
        fontsize=10.9, fontweight="bold", color=DARK, loc="left", pad=10,
    )
    ax_b.axvline(0.0, color="#222222", lw=1.4, zorder=2)

    q_colors = [BLUE, TEAL, "#b45309", ORANGE]
    q_short = [
        "Committed Moderate\n(Mod Rec + Mod Talk, n=10)",
        "Mainstream / Populist\n(Mainstream Rec, n=15)",
        "Rhetorical Pivoter\n(Prog Rec -> Mod Talk, n=7)",
        "Movement Progressive\n(Prog Rec + Prog Talk, n=4)",
    ]
    y_q = np.arange(len(q_comp))[::-1]
    for y, row, qlbl, col in zip(y_q, q_comp, q_short, q_colors):
        o_m = row["nov7_mean"]
        l_m = row["live_mean"]
        ax_b.plot([o_m, l_m], [y, y], color=col, lw=3.0, zorder=3)
        ax_b.scatter([o_m], [y], color="white", edgecolor=col, s=95, lw=2.2, zorder=4)
        ax_b.scatter([l_m], [y], color=col, s=125, edgecolor="white", lw=0.9, zorder=5)

        beat_txt = f"BeatHouse: {row['nov7_beat_pct']:.0f}% -> {row['live_beat_pct']:.0f}%"
        if l_m >= 0:
            ax_b.text(max(o_m, l_m) + 0.25, y + 0.08, f"{o_m:+.2f} -> {l_m:+.2f} pts", fontsize=8.6, fontweight="bold", color=col, va="bottom", ha="left")
            ax_b.text(max(o_m, l_m) + 0.25, y - 0.12, beat_txt, fontsize=7.9, color=SUB, va="top", ha="left")
        else:
            ax_b.text(min(o_m, l_m) - 0.25, y + 0.08, f"{o_m:+.2f} -> {l_m:+.2f} pts", fontsize=8.6, fontweight="bold", color=col, va="bottom", ha="right")
            ax_b.text(min(o_m, l_m) - 0.25, y - 0.12, beat_txt, fontsize=7.9, color=SUB, va="top", ha="right")

    ax_b.set_yticks(y_q)
    ax_b.set_yticklabels(q_short, fontsize=8.8, fontweight="bold", color=DARK)
    ax_b.set_xlim(-9.2, 9.5)
    ax_b.set_ylim(-0.6, 3.6)
    ax_b.xaxis.grid(True, color=GRID, lw=0.8)
    ax_b.yaxis.grid(True, color=GRID, lw=0.5, alpha=0.5)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    ax_b.set_xlabel("Mean Statewide Overperformance vs. State House Benchmark (pts)", fontsize=9.4, fontweight="bold", color=SUB)

    # ---- Panel C (Inset below Panel B): N=36 Full-Covariate OLS Regression Card ----
    for sp in ax_r.spines.values():
        sp.set_edgecolor("#cbd5e1")
        sp.set_linewidth(1.1)
    ax_r.set_xticks([])
    ax_r.set_yticks([])

    n7m = reg_comp["nov7"]
    lvm = reg_comp["live"]
    ax_r.text(
        0.02, 0.87,
        f"N={lvm['n']} Statewide OLS (HC1 SEs; Controls: Incumbency, Log Spend Ratio, Scandal)",
        transform=ax_r.transAxes, fontsize=8.3, fontweight="bold", color=DARK, va="top",
    )
    ax_r.text(
        0.02, 0.53,
        f"• R²: {n7m['r2']:.3f} -> {lvm['r2']:.3f} (+{lvm['r2'] - n7m['r2']:.3f})   |   "
        f"Past Record (+1 SD Mod): beta {n7m['record_beta']:+.2f} (p={n7m['record_p']:.3f}) -> {lvm['record_beta']:+.2f} (p={lvm['record_p']:.4f})",
        transform=ax_r.transAxes, fontsize=8.0, color=BLUE, fontweight="bold", va="center",
    )
    ax_r.text(
        0.02, 0.21,
        f"• Rhetorical Pivot: beta {n7m['pivot_beta']:+.2f} (p={n7m['pivot_p']:.2f}) -> {lvm['pivot_beta']:+.2f} (p={lvm['pivot_p']:.2f}, NULL — record wins, rebrands don't)",
        transform=ax_r.transAxes, fontsize=7.9, color=ORANGE, fontweight="bold", va="center",
    )

    fig.text(
        0.028, 0.025,
        f"Sources: Morris Nov. 4 Senate-minus-House figures (@gelliottmorris.com), site_data/faction_analysis_2026.json, and site_data/bonica_grumbach_methodology_test_2026.json (updated {data['fetched_at']}).\n"
        "*Note: Single-seat AK-01 had no viable major-party Dem nominee (Eric Hafner), so Mary Peltola's Alaska comparison tracks her live benchmark residual (rhetoric_vs_record_2026.json, Nov. 7 partial -> Live 99%).",
        fontsize=8.5, color=MUTED,
    )

    fig.savefig(CHART15_PATH, dpi=200, facecolor=BG)
    plt.close(fig)
    _optimize_png(CHART15_PATH)


def build_all() -> dict:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    ov_live = json.loads((SITE_DATA / "overview.json").read_text(encoding="utf-8"))
    fa_live = json.loads((SITE_DATA / "faction_analysis_2026.json").read_text(encoding="utf-8"))
    rh_live = json.loads((SITE_DATA / "rhetoric_vs_record_2026.json").read_text(encoding="utf-8"))
    bg_live = json.loads((SITE_DATA / "bonica_grumbach_methodology_test_2026.json").read_text(encoding="utf-8"))

    cache = load_or_build_cache(ov_live)
    acs_cd = cache["acs_cd"]
    rosters = cache["rosters"]
    nov5_raw = cache["nov5_house_margins"]
    nov7_sw = cache["nov7_statewide_baseline"]

    h_live = _contested_house_map(ov_live)
    valid_dists = sorted(
        k for k in set(h_live) & set(nov5_raw)
        if h_live[k].get("pres_2024_margin") is not None and k in acs_cd
    )
    valid_set = set(valid_dists)

    blue_dogs = set(rosters["blue_dogs"]) & valid_set
    new_dems = set(rosters["new_dems"]) & valid_set
    cpc_all = set(rosters["cpc"]) & valid_set
    dsa_endorsed = set(rosters["dsa_2026_endorsed"]) & valid_set
    dsa_plus_casar = set(rosters["dsa_plus_casar"]) & valid_set
    no_caucus = valid_set - blue_dogs - new_dems - cpc_all - dsa_endorsed

    groups_def = [
        ("blue_dogs", "Blue Dogs", blue_dogs),
        ("blue_dogs_ex_tx", "Blue Dogs\nex-TX-15/28", blue_dogs - {"TX-28", "TX-15"}),
        ("dsa_carveout", "DSA carveout\n(+Casar)", dsa_plus_casar),
        ("new_dems", "New Dems", new_dems),
        ("no_caucus", "No caucus", no_caucus),
        ("cpc", "CPC /\nprogressives", cpc_all),
        ("cpc_only", "CPC-only\n(ex-New Dem)", cpc_all - new_dems),
    ]

    margins_nov5 = {d: nov5_raw[d]["dem_gop_margin"] for d in valid_dists}
    margins_live = {d: h_live[d]["dem_gop_margin"] for d in valid_dists}

    house_nov5 = run_house_caucus_huber(valid_dists, margins_nov5, h_live, acs_cd, groups_def)
    house_live = run_house_caucus_huber(valid_dists, margins_live, h_live, acs_cd, groups_def)

    # Also record pure Nov 2026 DSA-endorsed (n=6) for completeness
    dsa6_res = run_house_caucus_huber(valid_dists, margins_live, h_live, acs_cd, [("dsa_2026_6", "DSA 2026 Endorsed (n=6)", dsa_endorsed)])["groups"][0]

    # Senate Nov 4 vs Live
    svh = fa_live["senate_vs_state_house_live"]
    ak_live = next((c["overperf_vs_benchmark"] for c in rh_live["candidates"] if "Peltola" in c.get("name", "")), 0.49)
    senate_rows = []
    for st, nm, early_v, is_prog in MORRIS_SENATE_CH2:
        live_v = ak_live if st == "AK" else svh.get(st, {}).get("senate_minus_house_shift", early_v)
        senate_rows.append({
            "state": st,
            "candidate": nm,
            "early": round(float(early_v), 2),
            "live": round(float(live_v), 2),
            "delta": round(float(live_v) - float(early_v), 2),
            "is_prog": is_prog,
        })

    # N=36 Statewide Quadrants Nov 7 vs Live
    q_old_map = {q["quadrant"]: q for q in nov7_sw["quadrants"]}
    q_comp = []
    for q in bg_live["test2_quadrant_summary_after_within_district_fix"]:
        qo = q_old_map[q["quadrant"]]
        q_comp.append({
            "quadrant": q["quadrant"],
            "n_statewide": q["n_statewide"],
            "nov7_mean": qo["mean_overperf_statewide_vs_house"],
            "live_mean": q["mean_overperf_statewide_vs_house"],
            "nov7_beat_pct": qo["pct_beating_benchmark_statewide"],
            "live_beat_pct": q["pct_beating_benchmark_statewide"],
        })

    def _extract_reg(m: dict) -> dict:
        rec = next(c for c in m["coefficients"] if "Record" in c["term"])
        piv = next(c for c in m["coefficients"] if "Pivot" in c["term"])
        return {
            "n": m["n"],
            "r2": m["r2"],
            "record_beta": rec["beta"],
            "record_p": rec["p_value"],
            "pivot_beta": piv["beta"],
            "pivot_p": piv["p_value"],
        }

    reg_comp = {
        "nov7": _extract_reg(nov7_sw["statewide36_full_model"]),
        "live": _extract_reg(bg_live["test3_multivariate_regression_models"]["statewide36_full_covariate_model"]),
    }

    out_data = {
        "fetched_at": ov_live.get("fetched_at"),
        "morris_house_nov4": MORRIS_HOUSE_NOV4,
        "house_replicated_nov5": house_nov5,
        "house_replicated_live": house_live,
        "dsa_2026_endorsed_only_live": dsa6_res,
        "senate_nov4_vs_live": senate_rows,
        "statewide36_quadrant_nov7_vs_live": q_comp,
        "statewide36_regression_nov7_vs_live": reg_comp,
    }
    _atomic_write_json(OUT_JSON, out_data)
    generate_chart14(out_data)
    generate_chart15(out_data)
    print(f"Saved {OUT_JSON.name}, {CHART14_PATH.name} ({CHART14_PATH.stat().st_size / 1024:.1f} KB), and {CHART15_PATH.name} ({CHART15_PATH.stat().st_size / 1024:.1f} KB)")
    return out_data


if __name__ == "__main__":
    build_all()

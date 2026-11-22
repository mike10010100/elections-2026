#!/usr/bin/env python3
"""Step 5: Compute bootstrap CIs, permutation tests, stratifications, sensitivity checks, and 4 Retina charts."""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Editorial palette
BG_COLOR = "#FAF7F2"
CARD_BG = "#FFFFFF"
BORDER_COL = "#E2DCD2"
TEXT_DARK = "#1A1D21"
TEXT_MUTED = "#5A626D"
COLOM_COLOR = "#1D5B79"     # Deep Atlantic Teal-Blue
ABDUL_COLOR = "#C8553D"     # Terracotta / Burnt Sienna
COLOM_LIGHT = "#D7E8F0"
ABDUL_LIGHT = "#F6DFD9"
CAT_COLORS = {
    "national_tv": "#2B6CB0",
    "national_longform": "#2F855A",
    "local_in_state": "#B7791F",
}
CAT_LABELS = {
    "national_tv": "National TV",
    "national_longform": "National Long-Form",
    "local_in_state": "Local / In-State",
}


def bootstrap_ratio_ci(nums: np.ndarray, denoms: np.ndarray, scale: float = 1.0, n_boot: int = 10000, seed: int = 42) -> tuple[float, float, float]:
    """Cluster bootstrap CI over appearances (each element = one appearance)."""
    if len(nums) == 0 or denoms.sum() <= 0:
        return 0.0, 0.0, 0.0
    obs = float(nums.sum() / denoms.sum() * scale)
    if len(nums) == 1:
        return round(obs, 3), round(obs, 3), round(obs, 3)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(nums), size=(n_boot, len(nums)))
    b_num = nums[idx].sum(axis=1)
    b_den = denoms[idx].sum(axis=1)
    valid = b_den > 0
    rates = (b_num[valid] / b_den[valid]) * scale
    lo, hi = np.percentile(rates, [2.5, 97.5])
    return round(obs, 3), round(float(lo), 3), round(float(hi), 3)


def bootstrap_diff_and_ratio(a_num, a_den, b_num, b_den, scale=3600.0, n_boot=10000, seed=42):
    rng = np.random.default_rng(seed)
    na, nb = len(a_num), len(b_num)
    ia = rng.integers(0, na, size=(n_boot, na))
    ib = rng.integers(0, nb, size=(n_boot, nb))
    ra = (a_num[ia].sum(axis=1) / a_den[ia].sum(axis=1)) * scale
    rb = (b_num[ib].sum(axis=1) / b_den[ib].sum(axis=1)) * scale
    diff = ra - rb
    valid = rb > 0
    ratio = ra[valid] / rb[valid]
    return {
        "diff_obs": round(float((a_num.sum() / a_den.sum() - b_num.sum() / b_den.sum()) * scale), 3),
        "diff_ci95": [round(float(np.percentile(diff, 2.5)), 3), round(float(np.percentile(diff, 97.5)), 3)],
        "ratio_obs": round(float((a_num.sum() / a_den.sum()) / (b_num.sum() / b_den.sum())), 3),
        "ratio_ci95": [round(float(np.percentile(ratio, 2.5)), 3), round(float(np.percentile(ratio, 97.5)), 3)],
    }


def permutation_pvalue(a_num, a_den, b_num, b_den, scale=3600.0, n_perm=10000, seed=42) -> float:
    rng = np.random.default_rng(seed)
    all_n = np.concatenate([a_num, b_num])
    all_d = np.concatenate([a_den, b_den])
    na = len(a_num)
    obs_diff = abs((a_num.sum() / a_den.sum() - b_num.sum() / b_den.sum()) * scale)
    cnt = 0
    for _ in range(n_perm):
        perm = rng.permutation(len(all_n))
        ga, gb = perm[:na], perm[na:]
        d = abs((all_n[ga].sum() / all_d[ga].sum() - all_n[gb].sum() / all_d[gb].sum()) * scale)
        if d >= obs_diff:
            cnt += 1
    return round(float((cnt + 1) / (n_perm + 1)), 4)


def agg_subset(rows: list[dict], seed: int = 42) -> dict:
    if not rows:
        return {"n": 0}
    sp_sec = np.array([r["cand_speaking_sec"] for r in rows], dtype=float)
    act_sec = np.array([r["active_appearance_sec"] for r in rows], dtype=float)
    words = np.array([r["cand_words"] for r in rows], dtype=float)
    strict = np.array([r["strict_mentions"] for r in rows], dtype=float)
    broad = np.array([r["broad_mentions"] for r in rows], dtype=float)

    sp_r, sp_lo, sp_hi = bootstrap_ratio_ci(strict, sp_sec, scale=3600.0, seed=seed)
    act_r, act_lo, act_hi = bootstrap_ratio_ci(strict, act_sec, scale=3600.0, seed=seed + 1)
    w_r, w_lo, w_hi = bootstrap_ratio_ci(strict, words, scale=1000.0, seed=seed + 2)
    br_r, br_lo, br_hi = bootstrap_ratio_ci(broad, sp_sec, scale=3600.0, seed=seed + 3)

    per_ep_rates = np.array([r["rate_per_speaking_hr_strict"] for r in rows], dtype=float)
    per_ep_1k = np.array([r["rate_per_1k_words_strict"] for r in rows], dtype=float)

    return {
        "n": len(rows),
        "speaking_hours": round(float(sp_sec.sum() / 3600.0), 3),
        "active_hours": round(float(act_sec.sum() / 3600.0), 3),
        "cand_words": int(words.sum()),
        "strict_mentions": int(strict.sum()),
        "broad_mentions": int(broad.sum()),
        "noncand_strict_mentions": int(sum(r["noncand_strict_mentions"] for r in rows)),
        "rate_speaking_hr": sp_r,
        "rate_speaking_hr_ci95": [sp_lo, sp_hi],
        "rate_active_hr": act_r,
        "rate_active_hr_ci95": [act_lo, act_hi],
        "rate_per_1k_words": w_r,
        "rate_per_1k_words_ci95": [w_lo, w_hi],
        "rate_broad_speaking_hr": br_r,
        "rate_broad_speaking_hr_ci95": [br_lo, br_hi],
        "median_ep_rate_hr": round(float(np.median(per_ep_rates)), 2),
        "iqr_ep_rate_hr": [round(float(np.percentile(per_ep_rates, 25)), 2), round(float(np.percentile(per_ep_rates, 75)), 2)],
        "median_ep_per_1k": round(float(np.median(per_ep_1k)), 2),
        "iqr_ep_per_1k": [round(float(np.percentile(per_ep_1k, 25)), 2), round(float(np.percentile(per_ep_1k, 75)), 2)],
    }


def main():
    analysis = json.loads((DATA_DIR / "analysis_results.json").read_text())
    apps = analysis["appearances"]
    mentions = analysis["candidate_mentions"]
    non_cand = analysis["non_candidate_mentions"]
    rev_speeches = analysis.get("rev_victory_speeches", {})
    rev_all = analysis.get("rev_all_transcripts", {})

    colom_apps = [a for a in apps if a["candidate"] == "scott_colom"]
    abdul_apps = [a for a in apps if a["candidate"] == "abdul_el_sayed"]

    # Overall aggregates + statistical tests
    overall = {
        "scott_colom": agg_subset(colom_apps, seed=42),
        "abdul_el_sayed": agg_subset(abdul_apps, seed=100),
    }

    c_num = np.array([r["strict_mentions"] for r in colom_apps], dtype=float)
    c_den = np.array([r["cand_speaking_sec"] for r in colom_apps], dtype=float)
    a_num = np.array([r["strict_mentions"] for r in abdul_apps], dtype=float)
    a_den = np.array([r["cand_speaking_sec"] for r in abdul_apps], dtype=float)

    comp = bootstrap_diff_and_ratio(c_num, c_den, a_num, a_den, scale=3600.0)
    comp["perm_p_value_speaking_hr"] = permutation_pvalue(c_num, c_den, a_num, a_den, scale=3600.0)

    c_w = np.array([r["cand_words"] for r in colom_apps], dtype=float)
    a_w = np.array([r["cand_words"] for r in abdul_apps], dtype=float)
    comp_1k = bootstrap_diff_and_ratio(c_num, c_w, a_num, a_w, scale=1000.0)
    comp_1k["perm_p_value_1k_words"] = permutation_pvalue(c_num, c_w, a_num, a_w, scale=1000.0)

    # Raw acoustic vs. context-adjudicated comparison
    raw_vs_adj = {}
    all_checked = mentions + non_cand
    for cand, rows in [("scott_colom", colom_apps), ("abdul_el_sayed", abdul_apps)]:
        hrs = sum(r["cand_speaking_sec"] for r in rows) / 3600.0
        wds = sum(r["cand_words"] for r in rows)
        raw_s = sum(r["raw_acoustic_strict_mentions"] for r in rows)
        raw_b = sum(r["raw_acoustic_broad_mentions"] for r in rows)
        adj_s = sum(r["strict_mentions"] for r in rows)
        adj_b = sum(r["broad_mentions"] for r in rows)
        add_s = sum(1 for m in mentions if m["candidate"] == cand and m.get("adjudicated") and m["is_strict"])
        add_b = sum(1 for m in mentions if m["candidate"] == cand and m.get("adjudicated"))
        rem_s = sum(1 for m in non_cand if m["candidate"] == cand and m.get("adjudicated") and m["is_strict"])
        rem_b = sum(1 for m in non_cand if m["candidate"] == cand and m.get("adjudicated"))
        in_cl_noncand = sum(
            1 for m in all_checked
            if m["candidate"] == cand and (not m["raw_acoustic_is_candidate"])
            and (not m["outside_kept_cluster"]) and (m["sim_local"] >= m["tau"])
        )
        cand_loc_lt = sum(
            1 for m in all_checked
            if m["candidate"] == cand and m["raw_acoustic_is_candidate"] and (m["sim_local"] < m["tau"])
        )
        raw_vs_adj[cand] = {
            "speaking_hours": round(hrs, 3),
            "raw_strict_mentions": raw_s,
            "raw_broad_mentions": raw_b,
            "raw_rate_speaking_hr_strict": round(raw_s / hrs, 2) if hrs else 0.0,
            "raw_rate_speaking_hr_broad": round(raw_b / hrs, 2) if hrs else 0.0,
            "raw_rate_per_1k_words_strict": round(1000.0 * raw_s / wds, 2) if wds else 0.0,
            "adj_strict_mentions": adj_s,
            "adj_broad_mentions": adj_b,
            "adj_rate_speaking_hr_strict": round(adj_s / hrs, 2) if hrs else 0.0,
            "adj_rate_speaking_hr_broad": round(adj_b / hrs, 2) if hrs else 0.0,
            "adj_rate_per_1k_words_strict": round(1000.0 * adj_s / wds, 2) if wds else 0.0,
            "flipped_to_candidate_strict": add_s,
            "flipped_to_candidate_broad": add_b,
            "flipped_to_non_candidate_strict": rem_s,
            "flipped_to_non_candidate_broad": rem_b,
            "borderline_in_cluster_noncand_ge_tau": in_cl_noncand,
            "borderline_cand_loc_lt_tau": cand_loc_lt,
        }
    raw_vs_adj["comparison"] = {
        "raw_ratio_speaking_hr": round(
            raw_vs_adj["scott_colom"]["raw_rate_speaking_hr_strict"]
            / raw_vs_adj["abdul_el_sayed"]["raw_rate_speaking_hr_strict"], 3
        ) if raw_vs_adj["abdul_el_sayed"]["raw_rate_speaking_hr_strict"] else 0.0,
        "adj_ratio_speaking_hr": comp["ratio_obs"],
    }

    # Sub-state geography ("Detroit/Flint vs. Jackson/Delta") + Combined localism
    substate_geo = {}
    sub_arrays = {}
    comb_arrays = {}
    for cand, rows, seed_base in [("scott_colom", colom_apps, 700), ("abdul_el_sayed", abdul_apps, 750)]:
        sp_sec = np.array([r["cand_speaking_sec"] for r in rows], dtype=float)
        wds_arr = np.array([r["cand_words"] for r in rows], dtype=float)
        sub_arr = np.array([r["substate_geo_mentions"] for r in rows], dtype=float)
        comb_arr = np.array([r["strict_mentions"] + r["substate_geo_mentions"] for r in rows], dtype=float)
        sub_arrays[cand] = (sub_arr, sp_sec, wds_arr)
        comb_arrays[cand] = (comb_arr, sp_sec, wds_arr)

        sr, slo, shi = bootstrap_ratio_ci(sub_arr, sp_sec, scale=3600.0, seed=seed_base)
        swr, swlo, swhi = bootstrap_ratio_ci(sub_arr, wds_arr, scale=1000.0, seed=seed_base + 1)
        cr, clo, chi = bootstrap_ratio_ci(comb_arr, sp_sec, scale=3600.0, seed=seed_base + 2)
        cwr, cwlo, cwhi = bootstrap_ratio_ci(comb_arr, wds_arr, scale=1000.0, seed=seed_base + 3)

        breakdown: dict[str, int] = {}
        for r in rows:
            for k, v in r.get("substate_geo_breakdown", {}).items():
                breakdown[k] = breakdown.get(k, 0) + v
        top_places = sorted(breakdown.items(), key=lambda kv: (-kv[1], kv[0]))[:15]

        substate_geo[cand] = {
            "substate_mentions": int(sub_arr.sum()),
            "rate_substate_speaking_hr": sr,
            "rate_substate_speaking_hr_ci95": [slo, shi],
            "rate_substate_per_1k_words": swr,
            "rate_substate_per_1k_words_ci95": [swlo, swhi],
            "combined_local_mentions": int(comb_arr.sum()),
            "rate_combined_speaking_hr": cr,
            "rate_combined_speaking_hr_ci95": [clo, chi],
            "rate_combined_per_1k_words": cwr,
            "rate_combined_per_1k_words_ci95": [cwlo, cwhi],
            "top_places": [{"place": k, "count": v} for k, v in top_places],
        }

    cs, cs_sec, _ = sub_arrays["scott_colom"]
    as_, as_sec, _ = sub_arrays["abdul_el_sayed"]
    comp_sub = bootstrap_diff_and_ratio(cs, cs_sec, as_, as_sec, scale=3600.0, seed=790)
    comp_sub["perm_p_value_speaking_hr"] = permutation_pvalue(cs, cs_sec, as_, as_sec, scale=3600.0, seed=791)
    cc, cc_sec, _ = comb_arrays["scott_colom"]
    ac, ac_sec, _ = comb_arrays["abdul_el_sayed"]
    comp_comb = bootstrap_diff_and_ratio(cc, cc_sec, ac, ac_sec, scale=3600.0, seed=792)
    comp_comb["perm_p_value_speaking_hr"] = permutation_pvalue(cc, cc_sec, ac, ac_sec, scale=3600.0, seed=793)
    substate_geo["comparison_substate_hr"] = comp_sub
    substate_geo["comparison_combined_hr"] = comp_comb

    # By Category & Period
    by_category = {}
    for cat in ["national_tv", "national_longform", "local_in_state"]:
        by_category[cat] = {
            "scott_colom": agg_subset([a for a in colom_apps if a["category"] == cat], seed=200),
            "abdul_el_sayed": agg_subset([a for a in abdul_apps if a["category"] == cat], seed=300),
        }

    by_period = {}
    for per in ["campaign", "post_election"]:
        by_period[per] = {
            "scott_colom": agg_subset([a for a in colom_apps if a["period"] == per], seed=400),
            "abdul_el_sayed": agg_subset([a for a in abdul_apps if a["period"] == per], seed=500),
        }

    # Matched Venues (shows/outlets where both candidates have >= 1 episode)
    VENUE_LABELS = {
        "morning_joe": "Morning Joe (MS NOW)",
        "meet_the_press": "Meet the Press / NBC",
        "nbc_news": "Meet the Press / NBC",
        "kaitlan_collins": "The Source (CNN)",
        "jen_psaki": "The Briefing (MS NOW)",
        "all_in": "All In w/ Chris Hayes",
        "ms_now_beat": "The Beat w/ Ari Melber",
        "ms_now_weekend": "The Weekend (MS NOW)",
        "breakfast_club": "The Breakfast Club",
        "tavis_smiley": "Tavis Smiley",
        "clay_cane": "Clay Cane Extended",
        "scott_macfarlane": "Scott MacFarlane Reports",
        "npr": "NPR (Up First / Newsmakers)",
        "pbs_newshour": "PBS NewsHour",
    }

    def venue_group(r):
        mv = r.get("matched_venue", "")
        if mv in ("meet_the_press", "nbc_news"):
            return "Meet the Press / NBC"
        return VENUE_LABELS.get(mv, "")

    matched_venues = {}
    for cand, rows in [("scott_colom", colom_apps), ("abdul_el_sayed", abdul_apps)]:
        for r in rows:
            vg = venue_group(r)
            if vg:
                matched_venues.setdefault(vg, {"scott_colom": [], "abdul_el_sayed": []})[cand].append(r)

    matched_summary = {}
    for vg, d in matched_venues.items():
        if d["scott_colom"] and d["abdul_el_sayed"]:
            matched_summary[vg] = {
                "scott_colom": agg_subset(d["scott_colom"], seed=600),
                "abdul_el_sayed": agg_subset(d["abdul_el_sayed"], seed=650),
            }

    # Sensitivity checks
    sensitivity = {}
    for tag in ["lo", "mid", "hi"]:
        sensitivity[f"threshold_{tag}"] = {}
        for cand, rows in [("scott_colom", colom_apps), ("abdul_el_sayed", abdul_apps)]:
            tot_sec = sum(r["sensitivity"][tag]["speech_sec"] for r in rows)
            tot_words = sum(r["sensitivity"][tag]["words"] for r in rows)
            tot_s = sum(r["sensitivity"][tag]["strict_mentions"] for r in rows)
            tot_b = sum(r["sensitivity"][tag]["broad_mentions"] for r in rows)
            sensitivity[f"threshold_{tag}"][cand] = {
                "speaking_hours": round(tot_sec / 3600.0, 3),
                "strict_mentions": tot_s,
                "broad_mentions": tot_b,
                "rate_speaking_hr_strict": round(tot_s / (tot_sec / 3600.0), 2) if tot_sec else 0.0,
                "rate_per_1k_words_strict": round(1000.0 * tot_s / tot_words, 2) if tot_words else 0.0,
                "rate_speaking_hr_broad": round(tot_b / (tot_sec / 3600.0), 2) if tot_sec else 0.0,
            }

    # Naive unattributed window comparison (what you'd get from raw captions without speaker verification)
    naive = {}
    for cand, rows in [("scott_colom", colom_apps), ("abdul_el_sayed", abdul_apps)]:
        tot_win_hr = sum(r["transcribed_duration_sec"] for r in rows) / 3600.0
        tot_win_words = sum(r["total_window_words"] for r in rows)
        tot_all_strict = sum(r["strict_mentions"] + r["noncand_strict_mentions"] for r in rows)
        cand_only = sum(r["strict_mentions"] for r in rows)
        noncand_only = sum(r["noncand_strict_mentions"] for r in rows)
        naive[cand] = {
            "total_window_hours": round(tot_win_hr, 2),
            "total_window_words": tot_win_words,
            "unattributed_strict_mentions": tot_all_strict,
            "candidate_only_strict_mentions": cand_only,
            "non_candidate_filtered_mentions": noncand_only,
            "non_candidate_share_pct": round(100.0 * noncand_only / tot_all_strict, 1) if tot_all_strict else 0.0,
            "naive_rate_per_window_hr": round(tot_all_strict / tot_win_hr, 2) if tot_win_hr else 0.0,
            "naive_rate_per_1k_words": round(1000.0 * tot_all_strict / tot_win_words, 2) if tot_win_words else 0.0,
        }

    # Contextual benchmark words
    benchmarks = {}
    for cand, rows in [("scott_colom", colom_apps), ("abdul_el_sayed", abdul_apps)]:
        hrs = sum(r["cand_speaking_sec"] for r in rows) / 3600.0
        wds = sum(r["cand_words"] for r in rows)
        benchmarks[cand] = {
            "state_strict_hr": round(sum(r["strict_mentions"] for r in rows) / hrs, 2),
            "substate_geo_hr": round(sum(r["substate_geo_mentions"] for r in rows) / hrs, 2),
            "america_hr": round(sum(r["bench_america"] for r in rows) / hrs, 2),
            "trump_hr": round(sum(r["bench_trump"] for r in rows) / hrs, 2),
            "healthcare_medicare_hr": round(sum(r["bench_healthcare_medicare"] for r in rows) / hrs, 2),
            "senate_senator_hr": round(sum(r["bench_senate_senator"] for r in rows) / hrs, 2),
            "state_strict_1k": round(1000.0 * sum(r["strict_mentions"] for r in rows) / wds, 2),
            "substate_geo_1k": round(1000.0 * sum(r["substate_geo_mentions"] for r in rows) / wds, 2),
            "america_1k": round(1000.0 * sum(r["bench_america"] for r in rows) / wds, 2),
            "trump_1k": round(1000.0 * sum(r["bench_trump"] for r in rows) / wds, 2),
            "healthcare_medicare_1k": round(1000.0 * sum(r["bench_healthcare_medicare"] for r in rows) / wds, 2),
            "senate_senator_1k": round(1000.0 * sum(r["bench_senate_senator"] for r in rows) / wds, 2),
        }

    summary_stats = {
        "taus": analysis["taus"],
        "adjudications_applied": analysis.get("adjudications_applied", 0),
        "overall": overall,
        "raw_vs_adjudicated": raw_vs_adj,
        "comparison_speaking_hr": comp,
        "comparison_per_1k_words": comp_1k,
        "substate_geography": substate_geo,
        "by_category": by_category,
        "by_period": by_period,
        "matched_venues": matched_summary,
        "rev_victory_speeches": rev_speeches,
        "rev_all_transcripts": rev_all,
        "sensitivity": sensitivity,
        "naive_vs_attributed": naive,
        "benchmarks": benchmarks,
    }
    (OUT_DIR / "summary_stats.json").write_text(json.dumps(summary_stats, indent=2))

    # Save CSV / JSON per-appearance summary
    apps_sorted = sorted(apps, key=lambda r: (r["candidate"], r["pub_date"]), reverse=True)
    app_cols = [
        "episode_id", "candidate", "show", "title", "pub_date", "category", "period",
        "is_full_broadcast", "matched_venue", "audio_duration_sec", "transcribed_duration_sec",
        "active_appearance_sec", "cand_speaking_sec", "cand_words", "total_window_words",
        "raw_acoustic_strict_mentions", "strict_mentions", "broad_mentions", "noncand_strict_mentions",
        "substate_geo_mentions",
        "rate_per_speaking_hr_strict", "rate_per_active_hr_strict", "rate_per_1k_words_strict",
        "rate_per_speaking_hr_substate_geo", "rate_per_speaking_hr_combined_local",
        "bench_america", "bench_trump", "bench_healthcare_medicare", "bench_senate_senator",
    ]
    pd.DataFrame(apps_sorted)[app_cols].to_csv(OUT_DIR / "appearances_summary.csv", index=False)
    (OUT_DIR / "appearances_summary.json").write_text(json.dumps(apps_sorted, indent=2))

    # Save mentions_audit.csv
    m_sorted = sorted(mentions, key=lambda r: (r["candidate"], r["pub_date"], r["episode_id"], r["timestamp_sec"]))
    with open(OUT_DIR / "mentions_audit.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "candidate", "episode_id", "pub_date", "show", "category", "period",
            "timestamp_mmss", "timestamp_sec", "matched_term", "is_strict",
            "sim_utterance", "sim_local", "raw_acoustic_is_candidate",
            "adjudicated", "adjudication_reason", "borderline_or_disagree", "context", "title"
        ], extrasaction="ignore")
        w.writeheader()
        w.writerows(m_sorted)

    print("Saved summary_stats.json, appearances_summary.csv/json, mentions_audit.csv.")
    print(f"Headline: Colom = {overall['scott_colom']['rate_speaking_hr']}/hr (CI {overall['scott_colom']['rate_speaking_hr_ci95']}) | "
          f"El-Sayed = {overall['abdul_el_sayed']['rate_speaking_hr']}/hr (CI {overall['abdul_el_sayed']['rate_speaking_hr_ci95']}) | "
          f"Ratio = {comp['ratio_obs']}x (p = {comp['perm_p_value_speaking_hr']})")

    # ==================== GENERATE 4 RETINA CHARTS ====================
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["DejaVu Sans", "Liberation Sans"],
        "axes.edgecolor": BORDER_COL,
        "axes.linewidth": 0.9,
        "figure.facecolor": BG_COLOR,
        "axes.facecolor": CARD_BG,
        "text.color": TEXT_DARK,
        "xtick.color": TEXT_MUTED,
        "ytick.color": TEXT_MUTED,
    })

    render_chart_1(summary_stats)
    render_chart_2(colom_apps, abdul_apps, summary_stats)
    render_chart_3(summary_stats)
    render_chart_4(summary_stats)


def render_chart_1(st: dict):
    c_ov = st["overall"]["scott_colom"]
    a_ov = st["overall"]["abdul_el_sayed"]
    comp = st["comparison_speaking_hr"]

    fig = plt.figure(figsize=(14.0, 9.6), dpi=220, facecolor=BG_COLOR)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.05, 1.35], hspace=0.40, wspace=0.26, top=0.82, bottom=0.11, left=0.145, right=0.965)

    # Super title & dek
    fig.text(0.04, 0.945, "How Often Do They Say Their State’s Name on Camera / Air?", fontsize=20, fontweight="bold", color=TEXT_DARK)
    fig.text(
        0.04, 0.895,
        f"Speaker-verified 2026 appearances (MS NOW, CNN, NBC, CBS, ABC, PBS, NPR & local/podcast interviews)\n"
        f"Scott Colom: {c_ov['n']} appearances ({c_ov['speaking_hours']:.2f} verified speaking hrs) vs. "
        f"Abdul El-Sayed: {a_ov['n']} appearances ({a_ov['speaking_hours']:.2f} speaking hrs)",
        fontsize=10.3, color=TEXT_MUTED, linespacing=1.35,
    )

    # Top-left & Top-right KPI cards via full-width axis
    ax_top = fig.add_subplot(gs[0, :])
    ax_top.set_xlim(-1.6, 101.6)
    ax_top.set_ylim(-2, 102)
    ax_top.axis("off")

    def draw_kpi_card(x0, w, color, light, name, word, ov):
        rect = mpatches.FancyBboxPatch((x0, 5), w, 90, boxstyle="round,pad=1.2,rounding_size=2.5",
                                       facecolor=CARD_BG, edgecolor=color, linewidth=2.0)
        ax_top.add_patch(rect)
        bar = mpatches.FancyBboxPatch((x0, 82), w, 13, boxstyle="round,pad=1.2,rounding_size=2.0",
                                      facecolor=color, edgecolor=color, linewidth=0)
        ax_top.add_patch(bar)
        ax_top.text(x0 + 2.2, 87.5, f"{name}  •  “{word}”", fontsize=13.0, fontweight="bold", color="#FFFFFF", va="center")
        ax_top.text(x0 + 2.2, 58, f"{ov['rate_speaking_hr']:.1f}", fontsize=29, fontweight="bold", color=color, va="center")
        ax_top.text(x0 + 17.5, 62, "mentions / speaking hr", fontsize=11.5, fontweight="bold", color=TEXT_DARK, va="center")
        ax_top.text(x0 + 17.5, 50, f"95% bootstrap CI: {ov['rate_speaking_hr_ci95'][0]:.1f} – {ov['rate_speaking_hr_ci95'][1]:.1f}",
                    fontsize=9.8, color=TEXT_MUTED, va="center")
        ax_top.text(x0 + 2.2, 29,
                    f"Per active interview hr: {ov['rate_active_hr']:.1f}/hr   •   Per 1,000 words: {ov['rate_per_1k_words']:.2f}",
                    fontsize=9.8, color=TEXT_DARK, va="center")
        ax_top.text(x0 + 2.2, 14,
                    f"{ov['strict_mentions']} strict ({ov['broad_mentions']} w/ demonyms) • {ov['n']} interviews • {ov['cand_words']:,} words",
                    fontsize=8.9, color=TEXT_MUTED, va="center")

    draw_kpi_card(0.2, 43.3, COLOM_COLOR, COLOM_LIGHT, "Scott Colom (D-MS)", "Mississippi", c_ov)
    draw_kpi_card(56.5, 43.3, ABDUL_COLOR, ABDUL_LIGHT, "Abdul El-Sayed (D-MI)", "Michigan", a_ov)

    # Center ratio badge
    badge = mpatches.FancyBboxPatch((45.3, 33), 9.4, 34, boxstyle="round,pad=0.8,rounding_size=2.2",
                                    facecolor="#F3EFE6", edgecolor=BORDER_COL, linewidth=1.4)
    ax_top.add_patch(badge)
    ax_top.text(50.0, 56, f"{comp['ratio_obs']:.2f}×", fontsize=17.5, fontweight="bold", color=TEXT_DARK, ha="center", va="center")
    p_str = "p < 0.001" if comp["perm_p_value_speaking_hr"] < 0.001 else f"p = {comp['perm_p_value_speaking_hr']:.3f}"
    ax_top.text(50.0, 41, f"ratio\n{p_str}", fontsize=9.2, color=TEXT_MUTED, ha="center", va="center")

    # Bottom-left: Venue Category comparison
    ax_cat = fig.add_subplot(gs[1, 0])
    cats = ["national_tv", "national_longform", "local_in_state"]
    y = np.arange(len(cats))[::-1]
    h = 0.34
    c_rates = [st["by_category"][k]["scott_colom"].get("rate_speaking_hr", 0) for k in cats]
    a_rates = [st["by_category"][k]["abdul_el_sayed"].get("rate_speaking_hr", 0) for k in cats]
    c_err_lo = [max(0, st["by_category"][k]["scott_colom"].get("rate_speaking_hr", 0) - st["by_category"][k]["scott_colom"].get("rate_speaking_hr_ci95", [0, 0])[0]) for k in cats]
    c_err_hi = [max(0, st["by_category"][k]["scott_colom"].get("rate_speaking_hr_ci95", [0, 0])[1] - st["by_category"][k]["scott_colom"].get("rate_speaking_hr", 0)) for k in cats]
    a_err_lo = [max(0, st["by_category"][k]["abdul_el_sayed"].get("rate_speaking_hr", 0) - st["by_category"][k]["abdul_el_sayed"].get("rate_speaking_hr_ci95", [0, 0])[0]) for k in cats]
    a_err_hi = [max(0, st["by_category"][k]["abdul_el_sayed"].get("rate_speaking_hr_ci95", [0, 0])[1] - st["by_category"][k]["abdul_el_sayed"].get("rate_speaking_hr", 0)) for k in cats]

    ax_cat.barh(y + h / 2, c_rates, height=h, color=COLOM_COLOR, label="Scott Colom (“Mississippi”)", xerr=[c_err_lo, c_err_hi], capsize=3, error_kw={"elinewidth": 1.2, "ecolor": "#103547"})
    ax_cat.barh(y - h / 2, a_rates, height=h, color=ABDUL_COLOR, label="Abdul El-Sayed (“Michigan”)", xerr=[a_err_lo, a_err_hi], capsize=3, error_kw={"elinewidth": 1.2, "ecolor": "#7C2D1E"})

    max_x = max(c_rates + a_rates + [c + hi for c, hi in zip(c_rates, c_err_hi)] + [a + hi for a, hi in zip(a_rates, a_err_hi)]) * 1.22
    ax_cat.set_xlim(0, max(10, max_x))
    for yi, cr, ar, chi, ahi, k in zip(y, c_rates, a_rates, c_err_hi, a_err_hi, cats):
        cn = st["by_category"][k]["scott_colom"].get("n", 0)
        an = st["by_category"][k]["abdul_el_sayed"].get("n", 0)
        ax_cat.text(cr + chi + max_x * 0.015, yi + h / 2, f"{cr:.1f}/hr (n={cn})", va="center", fontsize=9.2, fontweight="bold", color=COLOM_COLOR)
        ax_cat.text(ar + ahi + max_x * 0.015, yi - h / 2, f"{ar:.1f}/hr (n={an})", va="center", fontsize=9.2, fontweight="bold", color=ABDUL_COLOR)

    ax_cat.set_yticks(y)
    ax_cat.set_yticklabels([CAT_LABELS[k] for k in cats], fontsize=10.5, fontweight="bold", color=TEXT_DARK)
    ax_cat.set_xlabel("Mentions per Verified Candidate Speaking Hour (95% CI)", fontsize=10, color=TEXT_MUTED)
    ax_cat.set_title("By Venue Category", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax_cat.grid(axis="x", linestyle="--", alpha=0.35)
    ax_cat.spines["top"].set_visible(False)
    ax_cat.spines["right"].set_visible(False)

    # Bottom-right: Period comparison
    ax_per = fig.add_subplot(gs[1, 1])
    pers = ["campaign", "post_election"]
    per_labels = {"campaign": "Campaign\n(Jan – Nov 3, 2026)", "post_election": "Post-Election\n(Nov 4 – 21, 2026)"}
    yp = np.arange(len(pers))[::-1]
    cp_rates = [st["by_period"][p]["scott_colom"].get("rate_speaking_hr", 0) for p in pers]
    ap_rates = [st["by_period"][p]["abdul_el_sayed"].get("rate_speaking_hr", 0) for p in pers]
    cp_lo = [max(0, st["by_period"][p]["scott_colom"].get("rate_speaking_hr", 0) - st["by_period"][p]["scott_colom"].get("rate_speaking_hr_ci95", [0, 0])[0]) for p in pers]
    cp_hi = [max(0, st["by_period"][p]["scott_colom"].get("rate_speaking_hr_ci95", [0, 0])[1] - st["by_period"][p]["scott_colom"].get("rate_speaking_hr", 0)) for p in pers]
    ap_lo = [max(0, st["by_period"][p]["abdul_el_sayed"].get("rate_speaking_hr", 0) - st["by_period"][p]["abdul_el_sayed"].get("rate_speaking_hr_ci95", [0, 0])[0]) for p in pers]
    ap_hi = [max(0, st["by_period"][p]["abdul_el_sayed"].get("rate_speaking_hr_ci95", [0, 0])[1] - st["by_period"][p]["abdul_el_sayed"].get("rate_speaking_hr", 0)) for p in pers]

    ax_per.barh(yp + h / 2, cp_rates, height=h, color=COLOM_COLOR, xerr=[cp_lo, cp_hi], capsize=3, error_kw={"elinewidth": 1.2, "ecolor": "#103547"})
    ax_per.barh(yp - h / 2, ap_rates, height=h, color=ABDUL_COLOR, xerr=[ap_lo, ap_hi], capsize=3, error_kw={"elinewidth": 1.2, "ecolor": "#7C2D1E"})

    max_xp = max(cp_rates + ap_rates + [c + hi for c, hi in zip(cp_rates, cp_hi)] + [a + hi for a, hi in zip(ap_rates, ap_hi)]) * 1.24
    ax_per.set_xlim(0, max(10, max_xp))
    for yi, cr, ar, chi, ahi, p in zip(yp, cp_rates, ap_rates, cp_hi, ap_hi, pers):
        cn = st["by_period"][p]["scott_colom"].get("n", 0)
        an = st["by_period"][p]["abdul_el_sayed"].get("n", 0)
        ax_per.text(cr + chi + max_xp * 0.015, yi + h / 2, f"{cr:.1f}/hr (n={cn})", va="center", fontsize=9.2, fontweight="bold", color=COLOM_COLOR)
        ax_per.text(ar + ahi + max_xp * 0.015, yi - h / 2, f"{ar:.1f}/hr (n={an})", va="center", fontsize=9.2, fontweight="bold", color=ABDUL_COLOR)

    ax_per.set_yticks(yp)
    ax_per.set_yticklabels([per_labels[p] for p in pers], fontsize=10.5, fontweight="bold", color=TEXT_DARK)
    ax_per.set_xlabel("Mentions per Verified Candidate Speaking Hour (95% CI)", fontsize=10, color=TEXT_MUTED)
    ax_per.set_title("Campaign vs. Post-Election", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax_per.grid(axis="x", linestyle="--", alpha=0.35)
    ax_per.spines["top"].set_visible(False)
    ax_per.spines["right"].set_visible(False)
    ax_cat.legend(loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=9.5)

    fig.text(
        0.04, 0.022,
        f"Method: Broadcast & podcast audio transcribed via Whisper medium.en; turns speaker-verified via WavLM-SV + borderline transcript adjudication.\n"
        f"Error bars: 95% cluster bootstrap CIs (10,000 resamples). Permutation p-value = {comp['perm_p_value_speaking_hr']:.4f} across all {c_ov['n'] + a_ov['n']} appearances.",
        fontsize=8.6, color=TEXT_MUTED, linespacing=1.35,
    )
    fig.savefig(OUT_DIR / "chart_1_headline_comparison.png", dpi=220)
    plt.close(fig)


def render_chart_2(colom_apps: list[dict], abdul_apps: list[dict], st: dict):
    fig_h = max(12.2, 0.285 * max(len(colom_apps), len(abdul_apps)) + 2.6)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16.0, fig_h), dpi=220, facecolor=BG_COLOR, sharex=True)
    fig.subplots_adjust(top=0.862, bottom=0.080, left=0.19, right=0.97, wspace=0.44)

    total_n = len(colom_apps) + len(abdul_apps)
    fig.text(0.04, 0.955, "Every Appearance Ranked: State-Name Mentions per Speaking Hour", fontsize=19.5, fontweight="bold", color=TEXT_DARK)
    fig.text(
        0.04, 0.922,
        f"Strict state mentions per verified candidate speaking hour across all {total_n} interviews (dot size = speaking minutes; dashed line = pooled rate + 95% CI)",
        fontsize=10.3, color=TEXT_MUTED,
    )

    max_rate = max([r["rate_per_speaking_hr_strict"] for r in colom_apps + abdul_apps] + [10]) * 1.15

    for ax, rows, cand, title, base_col in [
        (ax1, colom_apps, "scott_colom", "Scott Colom — “Mississippi”", COLOM_COLOR),
        (ax2, abdul_apps, "abdul_el_sayed", "Abdul El-Sayed — “Michigan”", ABDUL_COLOR),
    ]:
        rows_s = sorted(rows, key=lambda r: (r["rate_per_speaking_hr_strict"], r["cand_speaking_sec"]))
        y = np.arange(len(rows_s))
        rates = [r["rate_per_speaking_hr_strict"] for r in rows_s]
        mins = [r["cand_speaking_sec"] / 60.0 for r in rows_s]
        cols = [CAT_COLORS[r["category"]] for r in rows_s]
        sizes = [max(35, min(260, m * 8.5)) for m in mins]

        ov = st["overall"][cand]
        lo, hi = ov["rate_speaking_hr_ci95"]
        ax.axvspan(lo, hi, color=base_col, alpha=0.10, zorder=0)
        ax.axvline(ov["rate_speaking_hr"], color=base_col, linestyle="--", linewidth=1.8, zorder=1, label=f"Pooled: {ov['rate_speaking_hr']:.1f}/hr")

        for yi, rt, col, sz in zip(y, rates, cols, sizes):
            ax.plot([0, rt], [yi, yi], color="#D6D1C8", linewidth=1.1, zorder=1)
            ax.scatter(rt, yi, s=sz, color=col, edgecolor="#FFFFFF", linewidth=0.9, zorder=3)
            x_off = max_rate * (0.015 + 0.0020 * float(np.sqrt(sz)))
            ax.text(
                rt + x_off, yi, f"{rt:.1f}", va="center", fontsize=8.0, color=TEXT_DARK, zorder=4,
                bbox=dict(facecolor=CARD_BG, edgecolor="none", alpha=0.78, pad=0.4),
            )

        labels = []
        for r in rows_s:
            sh = r["show"].replace("The Briefing with ", "").replace("The Source with ", "").replace("The Beat with ", "").replace("The Last Word with ", "")
            sh = sh.replace("The Other Side: ", "").replace("The Majority Report with ", "Majority Report ")
            if len(sh) > 22:
                sh = sh[:20] + "…"
            labels.append(f"{sh} ({r['pub_date'][5:]})")
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8.4, color=TEXT_DARK)
        ax.set_xlim(0, max_rate)
        ax.set_title(f"{title} (n={len(rows_s)})", fontsize=12.5, fontweight="bold", color=base_col, loc="left", pad=10)
        ax.set_xlabel("Mentions / Candidate Speaking Hour", fontsize=10, color=TEXT_MUTED)
        ax.grid(axis="x", linestyle="--", alpha=0.35)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.legend(loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=9.2)

    handles = [mpatches.Patch(color=v, label=CAT_LABELS[k]) for k, v in CAT_COLORS.items()]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.04, 0.905), ncol=3, frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=9.5)

    fig.text(
        0.04, 0.016,
        "Note: Each dot represents one distinct non-duplicate broadcast or podcast appearance with ≥60s verified candidate speaking time. Dot area scales with speaking duration.",
        fontsize=8.6, color=TEXT_MUTED,
    )
    fig.savefig(OUT_DIR / "chart_2_appearance_distribution.png", dpi=220)
    plt.close(fig)


def render_chart_3(st: dict):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.5, 8.4), dpi=220, facecolor=BG_COLOR)
    fig.subplots_adjust(top=0.76, bottom=0.12, left=0.175, right=0.96, wspace=0.38)

    fig.text(0.04, 0.94, "Head-to-Head on Shared Venues & Broader Rhetorical Vocabulary", fontsize=19, fontweight="bold", color=TEXT_DARK)
    fig.text(
        0.04, 0.895,
        "Left: Direct comparison on identical shows/formats (plus Rev.com Victory Speeches per 1k words)  •  Right: Key terms per verified speaking hour",
        fontsize=10.3, color=TEXT_MUTED,
    )

    # Left panel: Matched venues + Rev victory speech (normalized per 1k words for apples-to-apples w/ Rev!)
    mv = st["matched_venues"]
    # Sort venues by Colom per-1k-words rate
    venues = sorted(mv.keys(), key=lambda k: mv[k]["scott_colom"]["rate_per_1k_words"], reverse=False)

    # Add Rev.com Victory Speech as a clearly labeled row at top or bottom
    rev = st.get("rev_victory_speeches", {})
    labels = []
    c_vals = []
    a_vals = []
    if rev.get("scott_colom") and rev.get("abdul_el_sayed"):
        labels.append("Victory Speech*\n(Rev.com Verbatim)")
        c_vals.append(rev["scott_colom"]["per_1k_words_strict"])
        a_vals.append(rev["abdul_el_sayed"]["per_1k_words_strict"])
    for v in venues:
        labels.append(v)
        c_vals.append(mv[v]["scott_colom"]["rate_per_1k_words"])
        a_vals.append(mv[v]["abdul_el_sayed"]["rate_per_1k_words"])

    y = np.arange(len(labels))
    for yi, cv, av in zip(y, c_vals, a_vals):
        ax1.plot([min(cv, av), max(cv, av)], [yi, yi], color="#C8C1B6", linewidth=2.4, zorder=1)
    ax1.scatter(c_vals, y, s=110, color=COLOM_COLOR, edgecolor="#FFFFFF", linewidth=1.2, zorder=3, label="Scott Colom (“Mississippi”)")
    ax1.scatter(a_vals, y, s=110, color=ABDUL_COLOR, edgecolor="#FFFFFF", linewidth=1.2, zorder=3, label="Abdul El-Sayed (“Michigan”)")

    max_v = max(c_vals + a_vals + [1]) * 1.18
    ax1.axvline(0, color=BORDER_COL, linewidth=0.9, zorder=0)
    ax1.set_xlim(-max_v * 0.16, max_v * 1.05)
    ax1.set_xticks([t for t in ax1.get_xticks() if 0 <= t <= max_v * 1.05])
    for yi, cv, av in zip(y, c_vals, a_vals):
        if abs(cv - av) < 1e-6:
            ax1.text(cv + max_v * 0.022, yi + 0.14, f"{cv:.2f}", va="center", ha="left", fontsize=8.3, fontweight="bold", color=COLOM_COLOR)
            ax1.text(av + max_v * 0.022, yi - 0.14, f"{av:.2f}", va="center", ha="left", fontsize=8.3, fontweight="bold", color=ABDUL_COLOR)
        else:
            hi_v, hi_c = (cv, COLOM_COLOR) if cv > av else (av, ABDUL_COLOR)
            lo_v, lo_c = (av, ABDUL_COLOR) if cv > av else (cv, COLOM_COLOR)
            ax1.text(hi_v + max_v * 0.022, yi, f"{hi_v:.2f}", va="center", ha="left", fontsize=8.5, fontweight="bold", color=hi_c)
            ax1.text(lo_v - max_v * 0.022, yi, f"{lo_v:.2f}", va="center", ha="right", fontsize=8.5, fontweight="bold", color=lo_c)

    ax1.set_yticks(y)
    ax1.set_yticklabels(labels, fontsize=9.5, fontweight="bold", color=TEXT_DARK)
    ax1.set_xlabel("State-Name Mentions per 1,000 Candidate Words", fontsize=10, color=TEXT_MUTED)
    ax1.set_title(f"{len(venues)} Matched Shows & Victory Speeches", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax1.grid(axis="x", linestyle="--", alpha=0.35)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    leg_handles = [
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=COLOM_COLOR, markeredgecolor="#FFFFFF", markersize=9.5, label="Scott Colom (“Mississippi”)"),
        plt.Line2D([0], [0], marker="o", color="none", markerfacecolor=ABDUL_COLOR, markeredgecolor="#FFFFFF", markersize=9.5, label="Abdul El-Sayed (“Michigan”)"),
    ]
    fig.legend(handles=leg_handles, loc="upper left", bbox_to_anchor=(0.04, 0.868), ncol=2, frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=9.5)

    # Right panel: Benchmark vocabulary per speaking hour
    bm = st["benchmarks"]
    terms = [
        ("State Name (MS / MI)", "state_strict_hr"),
        ("America / American(s)", "america_hr"),
        ("Trump", "trump_hr"),
        ("Healthcare / Medicare", "healthcare_medicare_hr"),
        ("Senate / Senator(s)", "senate_senator_hr"),
    ]
    yb = np.arange(len(terms))[::-1]
    h = 0.34
    cb = [bm["scott_colom"][k] for _, k in terms]
    ab = [bm["abdul_el_sayed"][k] for _, k in terms]

    ax2.barh(yb + h / 2, cb, height=h, color=COLOM_COLOR, label="Scott Colom")
    ax2.barh(yb - h / 2, ab, height=h, color=ABDUL_COLOR, label="Abdul El-Sayed")
    max_b = max(cb + ab + [10]) * 1.20
    ax2.set_xlim(0, max_b)
    for yi, cv, av in zip(yb, cb, ab):
        ax2.text(cv + max_b * 0.015, yi + h / 2, f"{cv:.1f}/hr", va="center", fontsize=9.0, fontweight="bold", color=COLOM_COLOR)
        ax2.text(av + max_b * 0.015, yi - h / 2, f"{av:.1f}/hr", va="center", fontsize=9.0, fontweight="bold", color=ABDUL_COLOR)

    ax2.set_yticks(yb)
    ax2.set_yticklabels([t for t, _ in terms], fontsize=10.0, fontweight="bold", color=TEXT_DARK)
    ax2.set_xlabel("Mentions per Verified Candidate Speaking Hour", fontsize=10, color=TEXT_MUTED)
    ax2.set_title("What Each Candidate Emphasizes on Air", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax2.grid(axis="x", linestyle="--", alpha=0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    col_w = rev.get("scott_colom", {}).get("word_count", 0)
    abd_w = rev.get("abdul_el_sayed", {}).get("word_count", 0)
    fig.text(
        0.04, 0.03,
        f"*Victory speeches (Nov 3–11, 2026) come from Rev.com verbatim transcripts ({col_w:,} words for Colom; {abd_w:,} words for El-Sayed) and are shown separately from the audio-diarized RSS corpus.",
        fontsize=8.5, color=TEXT_MUTED,
    )
    fig.savefig(OUT_DIR / "chart_3_matched_venues_and_context.png", dpi=220)
    plt.close(fig)


def render_chart_4(st: dict):
    sg = st["substate_geography"]
    ov = st["overall"]
    rev = st.get("rev_all_transcripts", {})

    fig = plt.figure(figsize=(15.4, 8.4), dpi=220, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.15], top=0.76, bottom=0.14, left=0.105, right=0.97, wspace=0.49)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    fig.text(0.04, 0.94, "Testing Counter-Explanations: Sub-State Places & Same-Stage Verbatim Events", fontsize=19, fontweight="bold", color=TEXT_DARK)
    fig.text(
        0.04, 0.892,
        "Left: State name + unambiguous in-state city/county/region mentions per speaking hour  •  Right: All 5 Rev.com verbatim events per 1k words\n"
        "Tests whether El-Sayed cites local Michigan cities instead of “Michigan”, or whether venue selection explains the disparity",
        fontsize=10.1, color=TEXT_MUTED, linespacing=1.35,
    )

    # Left panel: Stacked horizontal bar (State Name + Sub-State Cities/Counties/Regions)
    COLOM_SUB = "#6BA3BE"
    ABDUL_SUB = "#E39481"
    ROGERS_COL = "#4A5568"
    ROGERS_SUB = "#9AA5B4"

    y_pos = np.array([1.22, 0.28])
    bar_h = 0.34

    c_state = ov["scott_colom"]["rate_speaking_hr"]
    c_sub = sg["scott_colom"]["rate_substate_speaking_hr"]
    c_comb = sg["scott_colom"]["rate_combined_speaking_hr"]

    a_state = ov["abdul_el_sayed"]["rate_speaking_hr"]
    a_sub = sg["abdul_el_sayed"]["rate_substate_speaking_hr"]
    a_comb = sg["abdul_el_sayed"]["rate_combined_speaking_hr"]

    ax1.barh(y_pos[0], c_state, height=bar_h, color=COLOM_COLOR, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)
    ax1.barh(y_pos[0], c_sub, left=c_state, height=bar_h, color=COLOM_SUB, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)
    ax1.barh(y_pos[1], a_state, height=bar_h, color=ABDUL_COLOR, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)
    ax1.barh(y_pos[1], a_sub, left=a_state, height=bar_h, color=ABDUL_SUB, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)

    max_x1 = max(c_comb, a_comb, 10) * 1.38
    ax1.set_xlim(0, max_x1)
    ax1.set_ylim(-0.42, 1.72)

    # Value labels inside/beside stacked bars
    ax1.text(c_state * 0.5, y_pos[0], f"State: {c_state:.1f}/hr", va="center", ha="center", fontsize=9.3, fontweight="bold", color="#FFFFFF", zorder=4)
    ax1.text(c_comb + max_x1 * 0.02, y_pos[0] + 0.06, f"{c_comb:.1f}/hr combined", va="center", ha="left", fontsize=9.8, fontweight="bold", color=TEXT_DARK)
    ax1.text(c_comb + max_x1 * 0.02, y_pos[0] - 0.08, f"(+{c_sub:.1f}/hr sub-state)", va="center", ha="left", fontsize=8.8, fontweight="bold", color=COLOM_COLOR)

    ax1.text(a_comb + max_x1 * 0.02, y_pos[1] + 0.06, f"{a_comb:.1f}/hr combined", va="center", ha="left", fontsize=9.8, fontweight="bold", color=TEXT_DARK)
    ax1.text(a_comb + max_x1 * 0.02, y_pos[1] - 0.08, f"({a_state:.1f} state + {a_sub:.1f} sub-state)", va="center", ha="left", fontsize=8.8, fontweight="bold", color=ABDUL_COLOR)

    # Top cited places callouts directly below each bar (2 compact lines so they fit comfortably inside ax1)
    def fmt_top_2line(cand_key, label_prefix, limit=5):
        items = sg[cand_key]["top_places"][:limit]
        parts = [f"{x['place'].title().replace(' County', ' Co.')} ({x['count']})" for x in items]
        line1 = f"{label_prefix} ({sg[cand_key]['substate_mentions']}): " + ", ".join(parts[:3]) + ","
        line2 = ", ".join(parts[3:])
        return line1 + "\n" + line2

    ax1.text(
        1.5, y_pos[0] - 0.25,
        fmt_top_2line("scott_colom", "Top MS sub-state", 5),
        va="top", ha="left", fontsize=7.9, color=TEXT_MUTED, linespacing=1.3,
        bbox=dict(facecolor="#F4F1EA", edgecolor=BORDER_COL, boxstyle="round,pad=0.35"),
    )
    ax1.text(
        1.5, y_pos[1] - 0.25,
        fmt_top_2line("abdul_el_sayed", "Top MI sub-state", 5),
        va="top", ha="left", fontsize=7.9, color=TEXT_MUTED, linespacing=1.3,
        bbox=dict(facecolor="#F4F1EA", edgecolor=BORDER_COL, boxstyle="round,pad=0.35"),
    )

    sub_ratio = sg["comparison_substate_hr"]["ratio_obs"]
    comb_ratio = sg["comparison_combined_hr"]["ratio_obs"]
    ax1.text(
        0.98, 0.46,
        f"Sub-state only: {sub_ratio:.2f}× higher for Colom\nCombined localism: {comb_ratio:.2f}× higher",
        transform=ax1.transAxes, ha="right", va="center", fontsize=8.5, fontweight="bold", color=TEXT_DARK,
        bbox=dict(facecolor="#FBF8F3", edgecolor=BORDER_COL, boxstyle="round,pad=0.45"),
    )

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(["Scott Colom\n(D-MS)", "Abdul El-Sayed\n(D-MI)"], fontsize=10.5, fontweight="bold", color=TEXT_DARK)
    ax1.set_xlabel("Verified Mentions per Candidate Speaking Hour", fontsize=10, color=TEXT_MUTED)
    ax1.set_title("State Name + In-State Places (RSS Corpus)", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax1.grid(axis="x", linestyle="--", alpha=0.35)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Right panel: All 5 Rev.com Verbatim Transcripts
    rev_order = [
        ("abdul_primary_presser", "MI Primary Presser (Aug 6)\nAbdul El-Sayed (D-MI)", ABDUL_COLOR, ABDUL_SUB),
        ("abdul_detroit_forum", "Detroit Econ Club Q&A (Oct 21)\nAbdul El-Sayed (D-MI)", ABDUL_COLOR, ABDUL_SUB),
        ("rogers_detroit_forum", "Detroit Econ Club Q&A (Oct 21)\nMike Rogers (R-MI)", ROGERS_COL, ROGERS_SUB),
        ("abdul_victory", "Victory Speech (Nov 2026)\nAbdul El-Sayed (D-MI)", ABDUL_COLOR, ABDUL_SUB),
        ("colom_victory", "Victory Speech (Nov 2026)\nScott Colom (D-MS)", COLOM_COLOR, COLOM_SUB),
    ]
    rev_rows = [r for r in rev_order if r[0] in rev]
    yr = np.arange(len(rev_rows))
    bar_h2 = 0.54

    # Highlight same-stage Oct 21 Detroit Economic Club Q&A rows
    det_idx = [i for i, r in enumerate(rev_rows) if "detroit_forum" in r[0]]
    if len(det_idx) == 2:
        ax2.axhspan(min(det_idx) - 0.43, max(det_idx) + 0.43, color="#ECE7DE", alpha=0.55, zorder=0)

    st_vals = [rev[k]["per_1k_words_strict"] for k, _, _, _ in rev_rows]
    sub_vals = [rev[k]["per_1k_words_substate_geo"] for k, _, _, _ in rev_rows]
    tot_vals = [s + g for s, g in zip(st_vals, sub_vals)]
    max_x2 = max(tot_vals + [5.0]) * 1.44

    for yi, (k, lbl, c_main, c_sub_col), sv_v, gv_v, tv_v in zip(yr, rev_rows, st_vals, sub_vals, tot_vals):
        ax2.barh(yi, sv_v, height=bar_h2, color=c_main, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)
        ax2.barh(yi, gv_v, left=sv_v, height=bar_h2, color=c_sub_col, edgecolor="#FFFFFF", linewidth=1.0, zorder=3)
        ax2.text(
            tv_v + max_x2 * 0.018, yi,
            f"{tv_v:.2f}  ({sv_v:.2f} + {gv_v:.2f})",
            va="center", ha="left", fontsize=8.8, fontweight="bold", color=TEXT_DARK,
        )

    if len(det_idx) == 2:
        ax2.text(
            max_x2 * 0.98, max(det_idx) + 0.35, "Same Oct 21 Forum Stage",
            ha="right", va="top", fontsize=8.0, style="italic", color=TEXT_MUTED,
        )

    ax2.set_xlim(0, max_x2)
    ax2.set_yticks(yr)
    ax2.set_yticklabels([r[1] for r in rev_rows], fontsize=9.2, fontweight="bold", color=TEXT_DARK)
    ax2.set_xlabel("Mentions per 1,000 Candidate Words (State + Sub-State)", fontsize=10, color=TEXT_MUTED)
    ax2.set_title("Official Rev.com Verbatim Transcripts (State + Places)", fontsize=12.5, fontweight="bold", loc="left", pad=10)
    ax2.grid(axis="x", linestyle="--", alpha=0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    leg_handles = [
        mpatches.Patch(color="#2D3748", label="Solid Bar = State Name (“Mississippi” / “Michigan”)"),
        mpatches.Patch(color="#A0AEC0", label="Lighter Bar = Sub-State Cities, Counties & Regions"),
        mpatches.Patch(color=COLOM_COLOR, label="Scott Colom (D-MS)"),
        mpatches.Patch(color=ABDUL_COLOR, label="Abdul El-Sayed (D-MI)"),
        mpatches.Patch(color=ROGERS_COL, label="Mike Rogers (R-MI)"),
    ]
    fig.legend(handles=leg_handles, loc="upper left", bbox_to_anchor=(0.04, 0.858), ncol=3, frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=9.0)

    fig.text(
        0.04, 0.025,
        "Note: Sub-state geography counts unambiguous in-state cities, counties & regions (excluding phrases containing the state name itself, such as 'University of Michigan', to avoid double-counting).\n"
        "Rev.com verbatim transcripts filter strictly to each candidate's dialogue turns (e.g., Detroit Economic Club Q&A: 4,478 words for El-Sayed vs. 3,891 words for Mike Rogers).",
        fontsize=8.4, color=TEXT_MUTED, linespacing=1.35,
    )
    fig.savefig(OUT_DIR / "chart_4_substate_and_rev_forums.png", dpi=220)
    plt.close(fig)


if __name__ == "__main__":
    main()

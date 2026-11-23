#!/usr/bin/env python3
"""Step 5: Compute Platner vs. Fetterman stats, 4-way comparison w/ Colom & El-Sayed, and render charts."""

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from PIL import Image

PF_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = PF_DIR / "data"
OUT_DIR = PF_DIR / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CE_SUMMARY_PATH = Path("/home/mike10010100/state-name-analysis/outputs/summary_stats.json")
CE_APPS_CSV_PATH = Path("/home/mike10010100/state-name-analysis/outputs/appearances_summary.csv")

# Editorial palette
BG_COLOR = "#FAF7F2"
CARD_BG = "#FFFFFF"
BORDER_COL = "#E2DCD2"
TEXT_DARK = "#1A1D21"
TEXT_MUTED = "#5A626D"

CAND_COLORS = {
    "scott_colom": "#1D5B79",     # Deep Atlantic Teal-Blue
    "graham_platner": "#2F855A",  # Maine Pine Green
    "abdul_el_sayed": "#C8553D",  # Terracotta / Burnt Sienna
    "john_fetterman": "#6B4C9A",  # Slate Plum
}
CAND_META = {
    "scott_colom": {"name": "Scott Colom", "label": "Scott Colom (MS)", "word": "Mississippi", "short": "MS"},
    "graham_platner": {"name": "Graham Platner", "label": "Graham Platner (ME)", "word": "Maine", "short": "ME"},
    "abdul_el_sayed": {"name": "Abdul El-Sayed", "label": "Abdul El-Sayed (MI)", "word": "Michigan", "short": "MI"},
    "john_fetterman": {"name": "John Fetterman", "label": "John Fetterman (PA)", "word": "Pennsylvania", "short": "PA"},
}
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
    if na == 0 or nb == 0 or a_den.sum() <= 0 or b_den.sum() <= 0:
        return {"diff_obs": 0.0, "diff_ci95": [0.0, 0.0], "ratio_obs": 0.0, "ratio_ci95": [0.0, 0.0]}
    ia = rng.integers(0, na, size=(n_boot, na))
    ib = rng.integers(0, nb, size=(n_boot, nb))
    ra = (a_num[ia].sum(axis=1) / a_den[ia].sum(axis=1)) * scale
    rb = (b_num[ib].sum(axis=1) / b_den[ib].sum(axis=1)) * scale
    diff = ra - rb
    valid = rb > 0
    ratio = ra[valid] / rb[valid]
    ra_obs = a_num.sum() / a_den.sum()
    rb_obs = b_num.sum() / b_den.sum()
    return {
        "diff_obs": round(float((ra_obs - rb_obs) * scale), 3),
        "diff_ci95": [round(float(np.percentile(diff, 2.5)), 3), round(float(np.percentile(diff, 97.5)), 3)],
        "ratio_obs": round(float(ra_obs / rb_obs), 3) if rb_obs > 0 else 0.0,
        "ratio_ci95": [round(float(np.percentile(ratio, 2.5)), 3), round(float(np.percentile(ratio, 97.5)), 3)] if len(ratio) else [0.0, 0.0],
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


def save_under_limit(fig: plt.Figure, out_path: Path, dpi: int = 190, max_bytes: int = 880_000) -> int:
    fig.savefig(out_path, dpi=dpi)
    plt.close(fig)
    sz = out_path.stat().st_size
    if sz > max_bytes:
        im = Image.open(out_path)
        im_q = im.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        im_q.save(out_path, optimize=True)
        sz = out_path.stat().st_size
    return sz


def render_4way_chart(summary: dict, pf_apps: list[dict], ce_apps_df: pd.DataFrame) -> int:
    fw = summary["four_way_comparison"]
    order = sorted(
        ["scott_colom", "graham_platner", "abdul_el_sayed", "john_fetterman"],
        key=lambda c: fw[c]["rate_speaking_hr"],
        reverse=True,
    )

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(15.8, 7.0), dpi=190, facecolor=BG_COLOR, gridspec_kw={"width_ratios": [1.18, 1.0], "wspace": 0.42})
    fig.subplots_adjust(top=0.80, bottom=0.14, left=0.14, right=0.97)

    fig.text(
        0.035, 0.935,
        "State-Name Mentions per Speaking Hour: 4-Way Senate Comparison",
        fontsize=18.5, fontweight="bold", color=TEXT_DARK,
    )
    fig.text(
        0.035, 0.875,
        "Speaker-verified RSS broadcast & podcast interviews (WavLM-SV + manual adjudication; 95% cluster-bootstrap CIs).\n"
        "Note: Scott Colom (MS), Graham Platner (ME), and Abdul El-Sayed (MI) were 2026 Senate candidates; John Fetterman (PA) is an incumbent U.S. Senator.",
        fontsize=9.6, color=TEXT_MUTED, linespacing=1.35,
    )

    y = np.arange(len(order))[::-1]
    rates = [fw[c]["rate_speaking_hr"] for c in order]
    broad_rates = [fw[c]["rate_broad_speaking_hr"] for c in order]
    los = [max(0.0, fw[c]["rate_speaking_hr"] - fw[c]["rate_speaking_hr_ci95"][0]) for c in order]
    his = [max(0.0, fw[c]["rate_speaking_hr_ci95"][1] - fw[c]["rate_speaking_hr"]) for c in order]
    cols = [CAND_COLORS[c] for c in order]

    ax_l.barh(y, rates, height=0.52, color=cols, alpha=0.90, xerr=[los, his], capsize=4, error_kw={"elinewidth": 1.6, "ecolor": TEXT_DARK}, zorder=2)
    ax_l.scatter(broad_rates, y, marker="D", s=62, facecolor=CARD_BG, edgecolor=TEXT_DARK, linewidth=1.6, zorder=4, label="Broad rate (+ demonyms)")

    max_l = max(broad_rates + [r + hi for r, hi in zip(rates, his)]) * 1.52
    ax_l.set_xlim(0, max_l)
    for yi, c, rt, br, hi in zip(y, order, rates, broad_rates, his):
        ov = fw[c]
        ci0, ci1 = ov["rate_speaking_hr_ci95"]
        x_txt = max(rt + hi, br) + max_l * 0.02
        ax_l.text(
            x_txt, yi + 0.11,
            f"{rt:.1f}/hr (broad {br:.1f})",
            va="center", fontsize=9.8, fontweight="bold", color=CAND_COLORS[c],
        )
        ax_l.text(
            x_txt, yi - 0.15,
            f"95% CI {ci0:.1f}–{ci1:.1f} • N={ov['n']} ({ov['speaking_hours']:.1f}h)",
            va="center", fontsize=8.3, color=TEXT_MUTED,
        )

    ax_l.set_yticks(y)
    ax_l.set_yticklabels([f"{CAND_META[c]['name']}\n“{CAND_META[c]['word']}” ({CAND_META[c]['short']})" for c in order], fontsize=10.2, fontweight="bold", color=TEXT_DARK)
    ax_l.set_xlabel("Pooled Mentions per Verified Speaking Hour", fontsize=10.0, color=TEXT_MUTED)
    ax_l.set_title("A. Pooled Rate (Strict Bar, Broad Diamond)", fontsize=12.0, fontweight="bold", loc="left", pad=10)
    ax_l.grid(axis="x", linestyle="--", alpha=0.35)
    ax_l.spines["top"].set_visible(False)
    ax_l.spines["right"].set_visible(False)
    ax_l.legend(loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=8.8)

    # Right panel: per-appearance strip plot colored by venue category
    rng = np.random.default_rng(123)
    ep_map = {
        "scott_colom": ce_apps_df[ce_apps_df["candidate"] == "scott_colom"].to_dict("records"),
        "abdul_el_sayed": ce_apps_df[ce_apps_df["candidate"] == "abdul_el_sayed"].to_dict("records"),
        "graham_platner": [a for a in pf_apps if a["candidate"] == "graham_platner"],
        "john_fetterman": [a for a in pf_apps if a["candidate"] == "john_fetterman"],
    }
    all_ep_rates = [float(r["rate_per_speaking_hr_strict"]) for c in order for r in ep_map[c]]
    max_r = max(all_ep_rates) * 1.07
    ax_r.set_xlim(-8, max_r)
    for yi, c in zip(y, order):
        rows = ep_map[c]
        vals = np.array([float(r["rate_per_speaking_hr_strict"]) for r in rows])
        cats = [r["category"] for r in rows]
        jitter = rng.uniform(-0.20, 0.20, size=len(vals))
        for v, j, cat in zip(vals, jitter, cats):
            ax_r.scatter(v, yi + j, s=42, color=CAT_COLORS.get(cat, TEXT_MUTED), alpha=0.80, edgecolor="#FFFFFF", linewidth=0.6, zorder=3)
        med = float(np.median(vals))
        p25, p75 = np.percentile(vals, [25, 75])
        ax_r.plot([p25, p75], [yi, yi], color=TEXT_DARK, linewidth=3.2, alpha=0.85, zorder=4)
        ax_r.scatter([med], [yi], color=CARD_BG, edgecolor=TEXT_DARK, s=70, linewidth=2.0, zorder=5)

    handles = [
        mpatches.Patch(color=CAT_COLORS[k], label=CAT_LABELS[k])
        for k in ["national_tv", "national_longform", "local_in_state"]
    ]
    ax_r.legend(handles=handles, loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=8.8)
    ax_r.set_yticks(y)
    ax_r.set_yticklabels([f"Med: {np.median([float(r['rate_per_speaking_hr_strict']) for r in ep_map[c]]):.1f}/hr" for c in order], fontsize=9.5, color=TEXT_MUTED)
    ax_r.set_xlabel("Per-Appearance Strict Rate (Mentions / Speaking Hour)", fontsize=10.0, color=TEXT_MUTED)
    ax_r.set_title("B. Per-Appearance Rates (Dot = 1 Interview, Line = IQR)", fontsize=11.4, fontweight="bold", loc="left", pad=10)
    ax_r.grid(axis="x", linestyle="--", alpha=0.35)
    ax_r.spines["top"].set_visible(False)
    ax_r.spines["right"].set_visible(False)

    pf_ov = summary["overall"]
    pf_comp = summary["comparison_speaking_hr"]
    p_pf = "< 0.001" if pf_comp["perm_p_value_speaking_hr"] < 0.001 else f"= {pf_comp['perm_p_value_speaking_hr']:.4f}"
    fig.text(
        0.04, 0.025,
        f"Total verified corpus: {sum(fw[c]['n'] for c in order)} appearances ({sum(fw[c]['speaking_hours'] for c in order):.1f} verified candidate speaking hours). "
        f"Platner vs. Fetterman ratio: {pf_comp['ratio_obs']:.2f}× (permutation p {p_pf}); "
        f"Colom vs. Platner: {fw['scott_colom']['rate_speaking_hr']/fw['graham_platner']['rate_speaking_hr']:.2f}×.",
        fontsize=8.7, color=TEXT_MUTED,
    )
    out_p = OUT_DIR / "chart_4way_colom_platner_fetterman_elsayed.png"
    sz = save_under_limit(fig, out_p, dpi=190)
    print(f"Rendered {out_p.name}: {sz/1024:.1f} KB")
    return sz


def render_pf_deepdive_chart(summary: dict, pf_apps: list[dict]) -> int:
    gp_ov = summary["overall"]["graham_platner"]
    jf_ov = summary["overall"]["john_fetterman"]
    bm = summary["benchmarks"]
    mv = summary["matched_venues"]

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(15.8, 7.5), dpi=190, facecolor=BG_COLOR, gridspec_kw={"width_ratios": [1.0, 1.20], "wspace": 0.36})
    fig.subplots_adjust(top=0.81, bottom=0.14, left=0.175, right=0.97)

    fig.text(
        0.03, 0.935,
        "Graham Platner (“Maine”) vs. John Fetterman (“Pennsylvania”)",
        fontsize=18.5, fontweight="bold", color=TEXT_DARK,
    )
    fig.text(
        0.03, 0.875,
        f"Platner: {gp_ov['rate_speaking_hr']:.2f}/hr across {gp_ov['n']} interviews ({gp_ov['speaking_hours']:.2f} speaking hrs) vs. "
        f"Fetterman: {jf_ov['rate_speaking_hr']:.2f}/hr across {jf_ov['n']} interviews ({jf_ov['speaking_hours']:.2f} speaking hrs).\n"
        f"Benchmarks, sub-state places (left) and per-episode breakdown with shared-venue & notable-episode callouts (right).",
        fontsize=9.6, color=TEXT_MUTED, linespacing=1.35,
    )

    # Left panel: Lexicon & Benchmark rates per speaking hr
    metrics = [
        ("State Name (Strict)", "state_strict_hr"),
        ("Broad (+ Demonyms)", "state_broad_hr"),
        ("Sub-State Places", "substate_geo_hr"),
        ("“America / American”", "america_hr"),
        ("“Trump”", "trump_hr"),
        ("“Healthcare / Medicare”", "healthcare_medicare_hr"),
        ("“Senate / Senator”", "senate_senator_hr"),
    ]
    ym = np.arange(len(metrics))[::-1]
    h = 0.36
    gp_vals = [bm["graham_platner"][k] for _, k in metrics]
    jf_vals = [bm["john_fetterman"][k] for _, k in metrics]

    ax_l.barh(ym + h / 2, gp_vals, height=h, color=CAND_COLORS["graham_platner"], label="Graham Platner (ME Senate Candidate)")
    ax_l.barh(ym - h / 2, jf_vals, height=h, color=CAND_COLORS["john_fetterman"], label="John Fetterman (PA Senator)")

    max_m = max(gp_vals + jf_vals) * 1.28
    ax_l.set_xlim(0, max_m)
    for yi, gv, jv in zip(ym, gp_vals, jf_vals):
        ax_l.text(gv + max_m * 0.015, yi + h / 2, f"{gv:.1f}/hr", va="center", fontsize=8.8, fontweight="bold", color=CAND_COLORS["graham_platner"])
        ax_l.text(jv + max_m * 0.015, yi - h / 2, f"{jv:.1f}/hr", va="center", fontsize=8.8, fontweight="bold", color=CAND_COLORS["john_fetterman"])

    ax_l.set_yticks(ym)
    ax_l.set_yticklabels([lbl for lbl, _ in metrics], fontsize=9.4, fontweight="bold", color=TEXT_DARK)
    ax_l.set_xlabel("Mentions per Verified Candidate Speaking Hour", fontsize=9.8, color=TEXT_MUTED)
    ax_l.set_title("A. Topic & Geography Benchmark Profile", fontsize=12.0, fontweight="bold", loc="left", pad=10)
    ax_l.grid(axis="x", linestyle="--", alpha=0.35)
    ax_l.spines["top"].set_visible(False)
    ax_l.spines["right"].set_visible(False)
    ax_l.legend(loc="lower right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=8.5)

    # Right panel: Every Platner & Fetterman appearance plotted cleanly by speaking-hr rate + key callouts
    gp_rows = sorted([a for a in pf_apps if a["candidate"] == "graham_platner"], key=lambda r: r["rate_per_speaking_hr_strict"])
    jf_rows = sorted([a for a in pf_apps if a["candidate"] == "john_fetterman"], key=lambda r: r["rate_per_speaking_hr_strict"])

    max_x_r = max([r["rate_per_speaking_hr_strict"] for r in gp_rows + jf_rows]) * 1.14
    ax_r.set_xlim(-4.5, max_x_r)
    ax_r.set_ylim(-0.82, 1.84)

    # Two horizontal lanes: Top = Platner (y=1.0), Bottom = Fetterman (y=0.0)
    rng = np.random.default_rng(77)
    dot_coords = {}
    for base_y, rows, ckey, lbl in [
        (1.0, gp_rows, "graham_platner", f"Graham Platner\n(N={len(gp_rows)}, med={gp_ov['median_ep_rate_hr']:.1f}/hr)"),
        (0.0, jf_rows, "john_fetterman", f"John Fetterman\n(N={len(jf_rows)}, med={jf_ov['median_ep_rate_hr']:.1f}/hr)"),
    ]:
        ov = summary["overall"][ckey]
        lo, hi = ov["rate_speaking_hr_ci95"]
        ax_r.fill_betweenx([base_y - 0.30, base_y + 0.30], lo, hi, color=CAND_COLORS[ckey], alpha=0.12, zorder=0)
        ax_r.plot([ov["rate_speaking_hr"], ov["rate_speaking_hr"]], [base_y - 0.30, base_y + 0.30], color=CAND_COLORS[ckey], linestyle="--", linewidth=2.0, zorder=2)

        jitter = rng.uniform(-0.18, 0.18, size=len(rows))
        for r, jit in zip(rows, jitter):
            sz = max(38, min(200, (r["cand_speaking_sec"] / 60.0) * 5.0))
            x_val = r["rate_per_speaking_hr_strict"]
            y_val = base_y + float(jit)
            dot_coords[r["episode_id"]] = (x_val, y_val)
            ax_r.scatter(
                x_val, y_val,
                s=sz, color=CAT_COLORS[r["category"]], alpha=0.85,
                edgecolor="#FFFFFF", linewidth=0.8, zorder=3,
            )

    # Exact verified callout annotations placed in non-overlapping data coordinates
    lookup = {r["episode_id"]: r for r in pf_apps}
    callouts = [
        ("gp_choose_hard_way_20260421", (6.5, 1.56), f"Choose Hard Way\n({lookup['gp_choose_hard_way_20260421']['rate_per_speaking_hr_strict']:.1f}/hr)"),
        ("gp_new_yorker_20251219", (27.0, 1.58), f"New Yorker ({lookup['gp_new_yorker_20251219']['rate_per_speaking_hr_strict']:.1f})"),
        ("gp_psaki_briefing_20260501", (47.5, 1.56), f"Jen Psaki May 1\n({lookup['gp_psaki_briefing_20260501']['rate_per_speaking_hr_strict']:.1f}/hr)"),
        ("gp_weekly_show_stewart_20260429", (17.5, 0.50), f"Weekly Show ({lookup['gp_weekly_show_stewart_20260429']['rate_per_speaking_hr_strict']:.1f})"),
        ("jf_all_in_pod_20260610", (42.5, 0.50), f"All-In w/ McCormick ({lookup['jf_all_in_pod_20260610']['rate_per_speaking_hr_strict']:.1f})"),
        ("gp_wgan_20260526", (70.0, 0.50), f"WGAN Maine\n({lookup['gp_wgan_20260526']['rate_per_speaking_hr_strict']:.1f}/hr)"),
        ("jf_meet_the_press_20260729", (11.5, -0.56), "9 zero-mention eps\n(8 nat'l TV, 1 pod)"),
        ("jf_weekly_show_stewart_20260805", (32.0, -0.66), f"Weekly Show ({lookup['jf_weekly_show_stewart_20260805']['rate_per_speaking_hr_strict']:.1f})"),
        ("jf_new_yorker_20250221", (53.5, -0.42), f"New Yorker ({lookup['jf_new_yorker_20250221']['rate_per_speaking_hr_strict']:.1f})"),
        ("jf_smerconish_20260702", (76.0, -0.48), f"Smerconish w/ McCormick\n({lookup['jf_smerconish_20260702']['rate_per_speaking_hr_strict']:.1f}/hr)"),
    ]
    for eid, (tx, ty), label_txt in callouts:
        xy_pt = dot_coords[eid]
        ax_r.annotate(
            label_txt, xy=xy_pt, xytext=(tx, ty), textcoords="data",
            fontsize=7.6, fontweight="bold", color=TEXT_DARK, ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.22", facecolor=CARD_BG, edgecolor=BORDER_COL, alpha=0.94),
            arrowprops=dict(arrowstyle="-", color=TEXT_MUTED, lw=0.85, shrinkA=2, shrinkB=3),
            zorder=6,
        )

    ax_r.set_yticks([1.0, 0.0])
    ax_r.set_yticklabels([
        f"Graham Platner\n(Pooled {gp_ov['rate_speaking_hr']:.1f}/hr)",
        f"John Fetterman\n(Pooled {jf_ov['rate_speaking_hr']:.1f}/hr)",
    ], fontsize=9.8, fontweight="bold", color=TEXT_DARK)
    ax_r.set_xlabel("Strict State Mentions per Speaking Hour (dashed = pooled rate; shaded = 95% CI)", fontsize=9.8, color=TEXT_MUTED)
    ax_r.set_title("B. Every PF Interview Distribution & Matched Showdowns", fontsize=12.0, fontweight="bold", loc="left", pad=10)
    ax_r.grid(axis="x", linestyle="--", alpha=0.35)
    ax_r.spines["top"].set_visible(False)
    ax_r.spines["right"].set_visible(False)

    handles = [
        mpatches.Patch(color=CAT_COLORS[k], label=CAT_LABELS[k])
        for k in ["national_tv", "national_longform", "local_in_state"]
    ]
    ax_r.legend(handles=handles, loc="upper right", frameon=True, facecolor=CARD_BG, edgecolor=BORDER_COL, fontsize=8.3)

    # Matched-venue footer note
    ws = mv.get("The Weekly Show w/ Jon Stewart", {})
    ny = mv.get("The New Yorker Radio Hour", {})
    ws_txt = f"Weekly Show (Platner {ws.get('graham_platner', {}).get('rate_speaking_hr', 0):.1f}/hr vs. Fetterman {ws.get('john_fetterman', {}).get('rate_speaking_hr', 0):.1f}/hr)" if ws else ""
    ny_txt = f"New Yorker (Platner {ny.get('graham_platner', {}).get('rate_speaking_hr', 0):.1f}/hr vs. Fetterman {ny.get('john_fetterman', {}).get('rate_speaking_hr', 0):.1f}/hr)" if ny else ""
    fig.text(
        0.03, 0.024,
        f"Matched-show comparisons: {ws_txt}  •  {ny_txt}. "
        f"Fetterman spoke the standalone abbr. “PA” 0 times (all-PA strict vs. strict+PA unchanged at {jf_ov['rate_speaking_hr']:.2f}/hr).",
        fontsize=8.6, color=TEXT_MUTED,
    )
    out_p = OUT_DIR / "chart_pf_appearances_ranked.png"
    sz = save_under_limit(fig, out_p, dpi=190)
    print(f"Rendered {out_p.name}: {sz/1024:.1f} KB")
    return sz


def main():
    analysis = json.loads((DATA_DIR / "analysis_pf_results.json").read_text())
    apps = analysis["appearances"]
    mentions = analysis["candidate_mentions"]
    non_cand = analysis["non_candidate_mentions"]

    gp_apps = [a for a in apps if a["candidate"] == "graham_platner"]
    jf_apps = [a for a in apps if a["candidate"] == "john_fetterman"]

    overall = {
        "graham_platner": agg_subset(gp_apps, seed=42),
        "john_fetterman": agg_subset(jf_apps, seed=100),
    }

    g_num = np.array([r["strict_mentions"] for r in gp_apps], dtype=float)
    g_den = np.array([r["cand_speaking_sec"] for r in gp_apps], dtype=float)
    g_w = np.array([r["cand_words"] for r in gp_apps], dtype=float)
    g_brd = np.array([r["broad_mentions"] for r in gp_apps], dtype=float)

    f_num = np.array([r["strict_mentions"] for r in jf_apps], dtype=float)
    f_den = np.array([r["cand_speaking_sec"] for r in jf_apps], dtype=float)
    f_w = np.array([r["cand_words"] for r in jf_apps], dtype=float)
    f_brd = np.array([r["broad_mentions"] for r in jf_apps], dtype=float)

    comp = bootstrap_diff_and_ratio(g_num, g_den, f_num, f_den, scale=3600.0, seed=42)
    comp["perm_p_value_speaking_hr"] = permutation_pvalue(g_num, g_den, f_num, f_den, scale=3600.0, seed=43)

    comp_1k = bootstrap_diff_and_ratio(g_num, g_w, f_num, f_w, scale=1000.0, seed=44)
    comp_1k["perm_p_value_1k_words"] = permutation_pvalue(g_num, g_w, f_num, f_w, scale=1000.0, seed=45)

    comp_broad = bootstrap_diff_and_ratio(g_brd, g_den, f_brd, f_den, scale=3600.0, seed=46)
    comp_broad["perm_p_value_broad_hr"] = permutation_pvalue(g_brd, g_den, f_brd, f_den, scale=3600.0, seed=47)

    # PA abbreviation sensitivity
    f_pa_plus = np.array([r["strict_mentions"] + r["pa_abbr_mentions"] for r in jf_apps], dtype=float)
    pa_r, pa_lo, pa_hi = bootstrap_ratio_ci(f_pa_plus, f_den, scale=3600.0, seed=50)
    pa_abbr_sensitivity = {
        "john_fetterman_pa_abbr_mentions": int(sum(r["pa_abbr_mentions"] for r in jf_apps)),
        "john_fetterman_strict_plus_pa_mentions": int(f_pa_plus.sum()),
        "john_fetterman_rate_strict_plus_pa_hr": pa_r,
        "john_fetterman_rate_strict_plus_pa_ci95": [pa_lo, pa_hi],
    }

    # Raw acoustic vs adjudicated
    raw_vs_adj = {}
    for cand, rows in [("graham_platner", gp_apps), ("john_fetterman", jf_apps)]:
        hrs = sum(r["cand_speaking_sec"] for r in rows) / 3600.0
        wds = sum(r["cand_words"] for r in rows)
        raw_s = sum(r["raw_acoustic_strict_mentions"] for r in rows)
        raw_b = sum(r["raw_acoustic_broad_mentions"] for r in rows)
        adj_s = sum(r["strict_mentions"] for r in rows)
        adj_b = sum(r["broad_mentions"] for r in rows)
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
            "flipped_to_candidate_strict": sum(1 for m in mentions if m["candidate"] == cand and m.get("adjudicated") and m["is_strict"]),
            "flipped_to_candidate_broad": sum(1 for m in mentions if m["candidate"] == cand and m.get("adjudicated")),
            "flipped_to_non_candidate_strict": sum(1 for m in non_cand if m["candidate"] == cand and m.get("adjudicated") and m["is_strict"]),
            "homophone_promoted_strict": sum(1 for m in mentions if m["candidate"] == cand and "asr_homophone" in m.get("adjudication_reason", "") and m["is_strict"]),
            "homophone_promoted_broad_only": sum(1 for m in mentions if m["candidate"] == cand and "asr_homophone" in m.get("adjudication_reason", "") and not m["is_strict"]),
        }

    # Sub-state geography & combined localism
    substate_geo = {}
    sub_arrays = {}
    comb_arrays = {}
    for cand, rows, sb in [("graham_platner", gp_apps, 700), ("john_fetterman", jf_apps, 750)]:
        sp_sec = np.array([r["cand_speaking_sec"] for r in rows], dtype=float)
        wds_arr = np.array([r["cand_words"] for r in rows], dtype=float)
        sub_arr = np.array([r["substate_geo_mentions"] for r in rows], dtype=float)
        comb_arr = np.array([r["strict_mentions"] + r["substate_geo_mentions"] for r in rows], dtype=float)
        sub_arrays[cand] = (sub_arr, sp_sec)
        comb_arrays[cand] = (comb_arr, sp_sec)

        sr, slo, shi = bootstrap_ratio_ci(sub_arr, sp_sec, scale=3600.0, seed=sb)
        swr, swlo, swhi = bootstrap_ratio_ci(sub_arr, wds_arr, scale=1000.0, seed=sb + 1)
        cr, clo, chi = bootstrap_ratio_ci(comb_arr, sp_sec, scale=3600.0, seed=sb + 2)
        cwr, cwlo, cwhi = bootstrap_ratio_ci(comb_arr, wds_arr, scale=1000.0, seed=sb + 3)

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

    gs, gs_sec = sub_arrays["graham_platner"]
    fs, fs_sec = sub_arrays["john_fetterman"]
    comp_sub = bootstrap_diff_and_ratio(gs, gs_sec, fs, fs_sec, scale=3600.0, seed=790)
    comp_sub["perm_p_value_speaking_hr"] = permutation_pvalue(gs, gs_sec, fs, fs_sec, scale=3600.0, seed=791)
    gc_a, gc_sec = comb_arrays["graham_platner"]
    fc_a, fc_sec = comb_arrays["john_fetterman"]
    comp_comb = bootstrap_diff_and_ratio(gc_a, gc_sec, fc_a, fc_sec, scale=3600.0, seed=792)
    comp_comb["perm_p_value_speaking_hr"] = permutation_pvalue(gc_a, gc_sec, fc_a, fc_sec, scale=3600.0, seed=793)
    substate_geo["comparison_substate_hr"] = comp_sub
    substate_geo["comparison_combined_hr"] = comp_comb

    # By category
    by_category = {}
    for cat in ["national_tv", "national_longform", "local_in_state"]:
        by_category[cat] = {
            "graham_platner": agg_subset([a for a in gp_apps if a["category"] == cat], seed=200),
            "john_fetterman": agg_subset([a for a in jf_apps if a["category"] == cat], seed=300),
        }

    # Matched venues (PF + 4-way join with Colom & El-Sayed)
    VENUE_LABELS = {
        "weekly_show": "The Weekly Show w/ Jon Stewart",
        "new_yorker": "The New Yorker Radio Hour",
        "meet_the_press": "Meet the Press / NBC",
        "nbc_news": "Meet the Press / NBC",
        "kaitlan_collins": "The Source (CNN)",
        "jen_psaki": "The Briefing (MS NOW)",
        "all_in": "All In w/ Chris Hayes",
        "morning_joe": "Morning Joe (MS NOW)",
        "pod_save_america": "Pod Save America",
        "mehdi_unfiltered": "Mehdi Unfiltered",
        "lever_time": "Lever Time",
        "cnn_sotu": "State of the Union (CNN)",
        "real_time": "Real Time w/ Bill Maher",
        "all_in_pod": "All-In Podcast",
        "smerconish": "The Smerconish Podcast",
        "cbs_takeout": "The Takeout w/ Major Garrett",
    }

    def infer_ce_venue(row: dict) -> str:
        mv = str(row.get("matched_venue", "") or "")
        sh = str(row.get("show", "") or "").lower()
        if mv:
            return VENUE_LABELS.get(mv, "")
        if "weekly show" in sh:
            return "The Weekly Show w/ Jon Stewart"
        if "new yorker" in sh:
            return "The New Yorker Radio Hour"
        if "pod save america" in sh:
            return "Pod Save America"
        if "mehdi unfiltered" in sh:
            return "Mehdi Unfiltered"
        if "lever time" in sh:
            return "Lever Time"
        if "state of the union" in sh:
            return "State of the Union (CNN)"
        return ""

    pf_matched_venues = {}
    for cand, rows in [("graham_platner", gp_apps), ("john_fetterman", jf_apps)]:
        for r in rows:
            vg = VENUE_LABELS.get(r.get("matched_venue", ""), "")
            if vg:
                pf_matched_venues.setdefault(vg, {"graham_platner": [], "john_fetterman": []})[cand].append(r)
    matched_summary = {
        vg: {"graham_platner": agg_subset(d["graham_platner"], seed=600), "john_fetterman": agg_subset(d["john_fetterman"], seed=650)}
        for vg, d in pf_matched_venues.items()
        if d["graham_platner"] and d["john_fetterman"]
    }

    # Sensitivity & Naive vs Attributed
    sensitivity = {}
    for tag in ["lo", "mid", "hi"]:
        sensitivity[f"threshold_{tag}"] = {}
        for cand, rows in [("graham_platner", gp_apps), ("john_fetterman", jf_apps)]:
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

    naive = {}
    for cand, rows in [("graham_platner", gp_apps), ("john_fetterman", jf_apps)]:
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

    benchmarks = {}
    for cand, rows in [("graham_platner", gp_apps), ("john_fetterman", jf_apps)]:
        hrs = sum(r["cand_speaking_sec"] for r in rows) / 3600.0
        wds = sum(r["cand_words"] for r in rows)
        benchmarks[cand] = {
            "state_strict_hr": round(sum(r["strict_mentions"] for r in rows) / hrs, 2),
            "state_broad_hr": round(sum(r["broad_mentions"] for r in rows) / hrs, 2),
            "substate_geo_hr": round(sum(r["substate_geo_mentions"] for r in rows) / hrs, 2),
            "america_hr": round(sum(r["bench_america"] for r in rows) / hrs, 2),
            "trump_hr": round(sum(r["bench_trump"] for r in rows) / hrs, 2),
            "healthcare_medicare_hr": round(sum(r["bench_healthcare_medicare"] for r in rows) / hrs, 2),
            "senate_senator_hr": round(sum(r["bench_senate_senator"] for r in rows) / hrs, 2),
            "state_strict_1k": round(1000.0 * sum(r["strict_mentions"] for r in rows) / wds, 2),
            "america_1k": round(1000.0 * sum(r["bench_america"] for r in rows) / wds, 2),
            "trump_1k": round(1000.0 * sum(r["bench_trump"] for r in rows) / wds, 2),
            "healthcare_medicare_1k": round(1000.0 * sum(r["bench_healthcare_medicare"] for r in rows) / wds, 2),
            "senate_senator_1k": round(1000.0 * sum(r["bench_senate_senator"] for r in rows) / wds, 2),
        }

    # Build 4-way comparison joining existing Colom & El-Sayed stats + matched venues
    ce_summary = json.loads(CE_SUMMARY_PATH.read_text())
    ce_apps_df = pd.read_csv(CE_APPS_CSV_PATH)

    four_way = {}
    for c in ["scott_colom", "abdul_el_sayed"]:
        four_way[c] = {
            **ce_summary["overall"][c],
            "substate_geo_hr": ce_summary["benchmarks"][c]["substate_geo_hr"],
            "combined_local_hr": ce_summary["substate_geography"][c]["rate_combined_speaking_hr"],
            "america_hr": ce_summary["benchmarks"][c]["america_hr"],
            "trump_hr": ce_summary["benchmarks"][c]["trump_hr"],
            "healthcare_medicare_hr": ce_summary["benchmarks"][c]["healthcare_medicare_hr"],
            "senate_senator_hr": ce_summary["benchmarks"][c]["senate_senator_hr"],
            "role": "2026 Senate Candidate",
            "state": "Mississippi" if c == "scott_colom" else "Michigan",
        }
    for c in ["graham_platner", "john_fetterman"]:
        four_way[c] = {
            **overall[c],
            "substate_geo_hr": benchmarks[c]["substate_geo_hr"],
            "combined_local_hr": substate_geo[c]["rate_combined_speaking_hr"],
            "america_hr": benchmarks[c]["america_hr"],
            "trump_hr": benchmarks[c]["trump_hr"],
            "healthcare_medicare_hr": benchmarks[c]["healthcare_medicare_hr"],
            "senate_senator_hr": benchmarks[c]["senate_senator_hr"],
            "role": "2026 Senate Candidate (withdrew Jul 2026)" if c == "graham_platner" else "Incumbent U.S. Senator",
            "state": "Maine" if c == "graham_platner" else "Pennsylvania",
        }

    four_way_venues: dict[str, dict[str, list[dict]]] = {}
    for row in apps:
        vg = VENUE_LABELS.get(row.get("matched_venue", ""), "")
        if vg:
            four_way_venues.setdefault(vg, {}).setdefault(row["candidate"], []).append(row)
    for row in ce_apps_df.to_dict("records"):
        vg = infer_ce_venue(row)
        if vg:
            four_way_venues.setdefault(vg, {}).setdefault(row["candidate"], []).append(row)

    four_way_matched_venues = {}
    for vg, by_c in four_way_venues.items():
        if len(by_c) >= 2 and ("graham_platner" in by_c or "john_fetterman" in by_c):
            four_way_matched_venues[vg] = {
                c: agg_subset(rs, seed=800 + i)
                for i, (c, rs) in enumerate(sorted(by_c.items()))
            }

    summary_stats = {
        "taus_cen": analysis["taus_cen"],
        "taus_res": analysis["taus_res"],
        "adjudications_applied": analysis.get("adjudications_applied", 0),
        "overall": overall,
        "comparison_speaking_hr": comp,
        "comparison_per_1k_words": comp_1k,
        "comparison_broad_speaking_hr": comp_broad,
        "pa_abbr_sensitivity": pa_abbr_sensitivity,
        "raw_vs_adjudicated": raw_vs_adj,
        "substate_geography": substate_geo,
        "by_category": by_category,
        "matched_venues": matched_summary,
        "sensitivity": sensitivity,
        "naive_vs_attributed": naive,
        "benchmarks": benchmarks,
        "four_way_comparison": four_way,
        "four_way_matched_venues": four_way_matched_venues,
    }
    (OUT_DIR / "summary_stats_pf.json").write_text(json.dumps(summary_stats, indent=2))

    # Export CSV / JSON tables
    apps_sorted = sorted(apps, key=lambda r: (r["candidate"], r["pub_date"]), reverse=True)
    app_cols = [
        "episode_id", "candidate", "show", "title", "pub_date", "category", "period",
        "is_full_broadcast", "matched_venue", "audio_duration_sec", "transcribed_duration_sec",
        "active_appearance_sec", "cand_speaking_sec", "cand_words", "total_window_words",
        "raw_acoustic_strict_mentions", "strict_mentions", "broad_mentions", "pa_abbr_mentions",
        "noncand_strict_mentions", "substate_geo_mentions",
        "rate_per_speaking_hr_strict", "rate_per_speaking_hr_broad", "rate_per_active_hr_strict",
        "rate_per_1k_words_strict", "rate_per_speaking_hr_substate_geo", "rate_per_speaking_hr_combined_local",
        "bench_america", "bench_trump", "bench_healthcare_medicare", "bench_senate_senator",
    ]
    pd.DataFrame(apps_sorted)[app_cols].to_csv(OUT_DIR / "appearances_summary_pf.csv", index=False)
    (OUT_DIR / "appearances_summary_pf.json").write_text(json.dumps(apps_sorted, indent=2))

    # Export mentions_audit_pf.csv (both candidate & filtered non-candidate mentions)
    all_audit_rows = sorted(mentions + non_cand, key=lambda r: (r["candidate"], r["pub_date"], r["episode_id"], r["timestamp_sec"]))
    with open(OUT_DIR / "mentions_audit_pf.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "candidate", "episode_id", "pub_date", "show", "category", "period",
            "timestamp_mmss", "timestamp_sec", "matched_term", "clean_raw", "is_strict", "is_broad",
            "sim_utterance", "sim_local", "sim_res_local", "raw_acoustic_is_candidate", "is_candidate",
            "adjudicated", "adjudication_reason", "borderline_or_disagree", "context", "title",
        ], extrasaction="ignore")
        w.writeheader()
        w.writerows(all_audit_rows)

    print("Saved summary_stats_pf.json, appearances_summary_pf.csv/json, mentions_audit_pf.csv.")
    print(f"Headline PF: Platner = {overall['graham_platner']['rate_speaking_hr']}/hr (CI {overall['graham_platner']['rate_speaking_hr_ci95']}) | "
          f"Fetterman = {overall['john_fetterman']['rate_speaking_hr']}/hr (CI {overall['john_fetterman']['rate_speaking_hr_ci95']}) | "
          f"Ratio = {comp['ratio_obs']}x (p = {comp['perm_p_value_speaking_hr']})")

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

    render_4way_chart(summary_stats, apps, ce_apps_df)
    render_pf_deepdive_chart(summary_stats, apps)


if __name__ == "__main__":
    main()

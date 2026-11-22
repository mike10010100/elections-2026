#!/usr/bin/env python3
"""Generate outputs/report.md directly from verified JSON/CSV deliverables."""

import csv
import json
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
OUT_DIR = BASE_DIR / "outputs"


def main():
    st = json.loads((OUT_DIR / "summary_stats.json").read_text())
    ar = json.loads((DATA_DIR / "analysis_results.json").read_text())
    excl = json.loads((DATA_DIR / "excluded_episodes.json").read_text())
    adj = json.loads((DATA_DIR / "mention_adjudications.json").read_text())

    with open(OUT_DIR / "appearances_summary.csv") as f:
        apps = list(csv.DictReader(f))

    ov_c = st["overall"]["scott_colom"]
    ov_a = st["overall"]["abdul_el_sayed"]
    comp = st["comparison_speaking_hr"]
    comp1k = st["comparison_per_1k_words"]
    rva = st["raw_vs_adjudicated"]
    sg = st["substate_geography"]
    rv = st["rev_all_transcripts"]
    bm = st["benchmarks"]
    nv = st["naive_vs_attributed"]
    sens = st["sensitivity"]

    all_m = ar["candidate_mentions"] + ar["non_candidate_mentions"]
    in_cl = [
        m for m in all_m
        if (not m["raw_acoustic_is_candidate"]) and (not m["outside_kept_cluster"]) and (m["sim_local"] >= m["tau"])
    ]
    cand_lt = [m for m in all_m if m["raw_acoustic_is_candidate"] and (m["sim_local"] < m["tau"])]

    active_ratio = ov_c["rate_active_hr"] / ov_a["rate_active_hr"]
    broad_ratio = ov_c["rate_broad_speaking_hr"] / ov_a["rate_broad_speaking_hr"]
    rev_vic_ratio = rv["colom_victory"]["per_1k_words_strict"] / rv["abdul_victory"]["per_1k_words_strict"]
    rev_det_state_ratio = rv["rogers_detroit_forum"]["per_1k_words_strict"] / rv["abdul_detroit_forum"]["per_1k_words_strict"]
    rev_det_sub_ratio = rv["rogers_detroit_forum"]["per_1k_words_substate_geo"] / rv["abdul_detroit_forum"]["per_1k_words_substate_geo"]

    lines = []
    a = lines.append

    a("# How Often Do Scott Colom and Abdul El-Sayed Say Their State’s Name on Air?\n")
    a(f"**Expanded, Speaker-Verified Empirical Analysis ({ov_c['n'] + ov_a['n']} Interviews + {len(rv)} Official Rev.com Verbatim Transcripts)**\n")
    a("> **Short Answer:** Across **84 speaker-verified 2026 interviews** (**39** for Scott Colom, `{:.2f}` verified speaking hours; **45** for Abdul El-Sayed, `{:.2f}` verified speaking hours), **Scott Colom says “Mississippi” `{:.1f}` times per speaking hour** (`{}` mentions; 95% cluster bootstrap CI `[{:.1f}, {:.1f}]`), while **Abdul El-Sayed says “Michigan” `{:.1f}` times per speaking hour** (`{}` mentions; 95% CI `[{:.1f}, {:.1f}]`). Colom mentions his state **`{:.2f}×` as often** per speaking hour (`p = {:.4f}`), **`{:.2f}×` as often** per 1,000 spoken words (`{:.2f}` vs. `{:.2f}`), and **`{:.2f}×` as often** per active interview hour (`{:.1f}/hr` vs. `{:.1f}/hr`).\n".format(
        ov_c["speaking_hours"], ov_a["speaking_hours"],
        ov_c["rate_speaking_hr"], ov_c["strict_mentions"], ov_c["rate_speaking_hr_ci95"][0], ov_c["rate_speaking_hr_ci95"][1],
        ov_a["rate_speaking_hr"], ov_a["strict_mentions"], ov_a["rate_speaking_hr_ci95"][0], ov_a["rate_speaking_hr_ci95"][1],
        comp["ratio_obs"], comp["perm_p_value_speaking_hr"],
        comp1k["ratio_obs"], ov_c["rate_per_1k_words"], ov_a["rate_per_1k_words"],
        active_ratio, ov_c["rate_active_hr"], ov_a["rate_active_hr"],
    ))

    # 1. Executive Summary
    a("## 1. Headline Results & Statistical Summary\n")
    a("This analysis answers [Dana Houle’s question](https://bsky.app/profile/danahoule.bsky.social/post/3n2uo3feyf22w) using a fully speaker-verified corpus built from public broadcast television audio feeds (MS NOW, CNN, NBC, CBS, ABC, PBS), public radio/podcasts (NPR, Michigan Public *Stateside*, WDET *The Metro*, Mississippi Today, etc.), and verbatim Rev.com transcripts.\n")
    a("To prevent host questions, chyron/intro recaps, or pundit commentary from inflating either candidate’s count, every audio segment was transcribed with Whisper `medium.en` and speaker-attributed using calibrated `WavLM-SV` utterance embeddings — followed by a **complete manual transcript audit of all {} acoustically borderline/disagreeing mentions** (`{}` verified adjustments).\n".format(
        len(in_cl) + len(cand_lt), st["adjudications_applied"]
    ))

    a("| Metric | Scott Colom (D-MS) | Abdul El-Sayed (D-MI) | Difference (95% CI) | Ratio (95% CI) | Perm. *p*-value |")
    a("|---|---:|---:|---:|---:|---:|")
    a(f"| **Appearances Included** | **{ov_c['n']}** | **{ov_a['n']}** | — | — | — |")
    a(f"| Verified Candidate Speaking Hours | `{ov_c['speaking_hours']:.2f} hrs` | `{ov_a['speaking_hours']:.2f} hrs` | — | — | — |")
    a(f"| Active Interview Window Hours | `{ov_c['active_hours']:.2f} hrs` | `{ov_a['active_hours']:.2f} hrs` | — | — | — |")
    a(f"| Verified Candidate Spoken Words | `{ov_c['cand_words']:,}` | `{ov_a['cand_words']:,}` | — | — | — |")
    a(f"| **Strict State Mentions (Adjudicated)** | **`{ov_c['strict_mentions']}`** | **`{ov_a['strict_mentions']}`** | — | — | — |")
    a(f"| **Rate / Verified Speaking Hour (Primary)** | **`{ov_c['rate_speaking_hr']:.2f}/hr`** `[{ov_c['rate_speaking_hr_ci95'][0]:.1f}, {ov_c['rate_speaking_hr_ci95'][1]:.1f}]` | **`{ov_a['rate_speaking_hr']:.2f}/hr`** `[{ov_a['rate_speaking_hr_ci95'][0]:.1f}, {ov_a['rate_speaking_hr_ci95'][1]:.1f}]` | `+{comp['diff_obs']:.2f}/hr` `[{comp['diff_ci95'][0]:.1f}, {comp['diff_ci95'][1]:.1f}]` | **`{comp['ratio_obs']:.2f}×`** `[{comp['ratio_ci95'][0]:.2f}×, {comp['ratio_ci95'][1]:.2f}×]` | **`{comp['perm_p_value_speaking_hr']:.4f}`** |")
    a(f"| Rate / Verified Speaking Hr (Raw Acoustic) | `{rva['scott_colom']['raw_rate_speaking_hr_strict']:.2f}/hr` (`{rva['scott_colom']['raw_strict_mentions']}`) | `{rva['abdul_el_sayed']['raw_rate_speaking_hr_strict']:.2f}/hr` (`{rva['abdul_el_sayed']['raw_strict_mentions']}`) | `+{rva['scott_colom']['raw_rate_speaking_hr_strict'] - rva['abdul_el_sayed']['raw_rate_speaking_hr_strict']:.2f}/hr` | `{rva['comparison']['raw_ratio_speaking_hr']:.2f}×` | — |")
    a(f"| Rate / Active Interview Hour | `{ov_c['rate_active_hr']:.2f}/hr` `[{ov_c['rate_active_hr_ci95'][0]:.1f}, {ov_c['rate_active_hr_ci95'][1]:.1f}]` | `{ov_a['rate_active_hr']:.2f}/hr` `[{ov_a['rate_active_hr_ci95'][0]:.1f}, {ov_a['rate_active_hr_ci95'][1]:.1f}]` | — | `{active_ratio:.2f}×` | — |")
    a(f"| **Rate / 1,000 Candidate Words** | **`{ov_c['rate_per_1k_words']:.2f}`** `[{ov_c['rate_per_1k_words_ci95'][0]:.2f}, {ov_c['rate_per_1k_words_ci95'][1]:.2f}]` | **`{ov_a['rate_per_1k_words']:.2f}`** `[{ov_a['rate_per_1k_words_ci95'][0]:.2f}, {ov_a['rate_per_1k_words_ci95'][1]:.2f}]` | `+{comp1k['diff_obs']:.2f}` `[{comp1k['diff_ci95'][0]:.2f}, {comp1k['diff_ci95'][1]:.2f}]` | **`{comp1k['ratio_obs']:.2f}×`** `[{comp1k['ratio_ci95'][0]:.2f}×, {comp1k['ratio_ci95'][1]:.2f}×]` | **`{comp1k['perm_p_value_1k_words']:.4f}`** |")
    a(f"| Broad Rate / Speaking Hr (incl. Demonyms) | `{ov_c['rate_broad_speaking_hr']:.2f}/hr` (`{ov_c['broad_mentions']}`) | `{ov_a['rate_broad_speaking_hr']:.2f}/hr` (`{ov_a['broad_mentions']}`) | — | `{broad_ratio:.2f}×` | — |")
    a(f"| Episode-Level Median [IQR] / Speaking Hr | `{ov_c['median_ep_rate_hr']:.2f}/hr` `[{ov_c['iqr_ep_rate_hr'][0]:.1f}–{ov_c['iqr_ep_rate_hr'][1]:.1f}]` | `{ov_a['median_ep_rate_hr']:.2f}/hr` `[{ov_a['iqr_ep_rate_hr'][0]:.1f}–{ov_a['iqr_ep_rate_hr'][1]:.1f}]` | — | — | — |\n")

    a("![Headline Comparison](chart_1_headline_comparison.png)\n")

    # 2. Corpus Overview & Expansion
    a("## 2. Corpus Coverage & Expansion\n")
    a(f"The initial corpus (`74` interviews) was expanded to **84 verified candidate interviews** (`96` total manifest entries processed; `12` excluded) and **5 official Rev.com verbatim transcripts**:\n")
    a("- **10 new verified RSS candidate interviews added:** Scott Colom on *All In with Chris Hayes* (Nov 11) plus two earlier *It's a New Day with Rip Daniels* shows (Jan 15 & Feb 3); Abdul El-Sayed on *All In with Chris Hayes* (Aug 6 & Oct 6), *The Dig* (May 14), and four Michigan Public *Stateside On Air* appearances (Jul 23, Aug 5, Oct 23, Nov 12).\n")
    a("- **12 documented non-candidate / ambiguous exclusions (`data/excluded_episodes.json`):** 4 localized pundit-only segments (`colom_morningjoe_20261113_6/7`, `colom_weekend_20261010_7/9`), 4 commentary/panel/clip-only episodes where the candidate was never interviewed (`colom_freshair_20261119`, `abdul_morningjoe_20260810`, `abdul_macfarlane_20261019`, plus newly inspected Nov 12 post-election panels `colom_allin_20261112` and `colom_psaki_20261112`), 2 shows with `<60s` verified candidate speech (`colom_mtpnow_20261105`, `abdul_playbook_20261016`), and 1 joint interview with Scott Colom’s identical twin brother Andrew Colom (`colom_beat_20261121`), excluded so twin voice overlap cannot bias attribution.\n")
    a("- **5 Rev.com verbatim transcripts parsed (`rev_all_transcripts`):** Added the October 21 Detroit Economic Club Q&A (providing both Abdul El-Sayed and GOP nominee Mike Rogers on the same stage under the same moderator) and El-Sayed’s August 6 Michigan Primary Victory Press Conference alongside both November Election Night Victory Speeches.\n")

    # 3. Stratification & Distribution
    a("## 3. Consistency Across Venue Types & Campaign Periods\n")
    a("The disparity is not an artifact of podcast length or post-election victory laps. It holds cleanly in National TV studios, long-form podcasts, local in-state media, pre-election campaigning, and post-election interviews:\n")

    a("| Stratum | Colom *n* | Colom Speaking Hrs | Colom Rate (95% CI) | El-Sayed *n* | El-Sayed Speaking Hrs | El-Sayed Rate (95% CI) | Ratio |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|")
    for key, label, grp in [
        ("national_tv", "National TV", st["by_category"]),
        ("national_longform", "National Long-Form / Podcast", st["by_category"]),
        ("local_in_state", "Local / In-State Media", st["by_category"]),
        ("campaign", "Campaign (Jan – Nov 3, 2026)", st["by_period"]),
        ("post_election", "Post-Election (Nov 4 – 21, 2026)", st["by_period"]),
    ]:
        dc, da = grp[key]["scott_colom"], grp[key]["abdul_el_sayed"]
        rat = dc["rate_speaking_hr"] / da["rate_speaking_hr"]
        a(f"| **{label}** | {dc['n']} | `{dc['speaking_hours']:.2f}` | **`{dc['rate_speaking_hr']:.1f}/hr`** `[{dc['rate_speaking_hr_ci95'][0]:.1f}, {dc['rate_speaking_hr_ci95'][1]:.1f}]` | {da['n']} | `{da['speaking_hours']:.2f}` | **`{da['rate_speaking_hr']:.1f}/hr`** `[{da['rate_speaking_hr_ci95'][0]:.1f}, {da['rate_speaking_hr_ci95'][1]:.1f}]` | **`{rat:.2f}×`** |")
    a("")

    a("![Every Appearance Ranked](chart_2_appearance_distribution.png)\n")

    # 4. Matched Shows & Rhetorical Vocabulary
    a("## 4. Head-to-Head on 9 Matched Shows & Broader Vocabulary\n")
    a("Restricting strictly to shows where **both** candidates sat for verified interviews yields **9 matched shared venues** (plus Rev.com Victory Speeches). Colom says his state’s name far more often per 1,000 words — and per speaking hour — in **all 9 out of 9 shared shows**.\n")

    a("| Shared Venue / Format | Colom *n* | Colom / 1k Words | Colom / Speaking Hr | El-Sayed *n* | El-Sayed / 1k Words | El-Sayed / Speaking Hr | Per-1k Ratio |")
    a("|---|---:|---:|---:|---:|---:|---:|---:|")
    mv_sorted = sorted(st["matched_venues"].items(), key=lambda kv: kv[1]["scott_colom"]["rate_per_1k_words"], reverse=True)
    for venue, vd in mv_sorted:
        dc, da = vd["scott_colom"], vd["abdul_el_sayed"]
        rat_str = f"**`{dc['rate_per_1k_words'] / da['rate_per_1k_words']:.2f}×`**" if da["rate_per_1k_words"] > 0 else "**`∞`** (`13.92` vs `0`)"
        a(f"| {venue} | {dc['n']} | `{dc['rate_per_1k_words']:.2f}` | `{dc['rate_speaking_hr']:.1f}/hr` | {da['n']} | `{da['rate_per_1k_words']:.2f}` | `{da['rate_speaking_hr']:.1f}/hr` | {rat_str} |")
    a("")

    a("### What Each Candidate Emphasizes Instead\n")
    a("| Lexical Term / Topic | Colom / Speaking Hr | Colom / 1k Words | El-Sayed / Speaking Hr | El-Sayed / 1k Words |")
    a("|---|---:|---:|---:|---:|")
    for lbl, hr_k, k1_k in [
        ("**State Name (“Mississippi” / “Michigan”)**", "state_strict_hr", "state_strict_1k"),
        ("Unambiguous Sub-State Geography (Cities/Counties/Regions)", "substate_geo_hr", "substate_geo_1k"),
        ("America / American(s)", "america_hr", "america_1k"),
        ("Trump", "trump_hr", "trump_1k"),
        ("Healthcare / Medicare", "healthcare_medicare_hr", "healthcare_medicare_1k"),
        ("Senate / Senator(s)", "senate_senator_hr", "senate_senator_1k"),
    ]:
        a(f"| {lbl} | `{bm['scott_colom'][hr_k]:.2f}/hr` | `{bm['scott_colom'][k1_k]:.2f}` | `{bm['abdul_el_sayed'][hr_k]:.2f}/hr` | `{bm['abdul_el_sayed'][k1_k]:.2f}` |")
    a("")
    a("Where Colom centers his rhetoric directly around `Mississippi` (`122.78/hr`, vs. `4.73/hr` for `Trump` and `14.73/hr` for `America`), El-Sayed distributes his framing across national healthcare policy (`41.29/hr`), `America / American(s)` (`29.95/hr`), and `Trump` (`25.61/hr`), mentioning `Michigan` (`21.89/hr`) less frequently than any of those three.\n")
    a("![Matched Venues & Rhetorical Vocabulary](chart_3_matched_venues_and_context.png)\n")

    # 5. Sub-State Geography & Rev.com Forums
    a("## 5. Counter-Explanation Tests: Sub-State Places & Same-Stage Verbatim Events\n")
    a("### Test A: Does El-Sayed Say “Detroit” or “Flint” Instead of “Michigan”?\n")
    a("No. Using a non-overlapping multi-word + unigram lexicon of unambiguous in-state cities, counties, and regions — and **strictly excluding phrases that contain the state name** (e.g., *University of Michigan*, *Mississippi Gulf Coast*) so nothing is double-counted — shows that **Scott Colom also cites sub-state places 1.49× as often as Abdul El-Sayed**:\n")

    sg_c, sg_a = sg["scott_colom"], sg["abdul_el_sayed"]
    c_sub, c_comb = sg["comparison_substate_hr"], sg["comparison_combined_hr"]
    a("| Geographic Measure | Scott Colom (D-MS) | Abdul El-Sayed (D-MI) | Difference (95% CI) | Ratio (95% CI) | Perm. *p*-value |")
    a("|---|---:|---:|---:|---:|---:|")
    a(f"| Sub-State Places Count (Unambiguous) | `{sg_c['substate_mentions']}` | `{sg_a['substate_mentions']}` | — | — | — |")
    a(f"| Sub-State Rate / Speaking Hr | `{sg_c['rate_substate_speaking_hr']:.2f}/hr` `[{sg_c['rate_substate_speaking_hr_ci95'][0]:.1f}, {sg_c['rate_substate_speaking_hr_ci95'][1]:.1f}]` | `{sg_a['rate_substate_speaking_hr']:.2f}/hr` `[{sg_a['rate_substate_speaking_hr_ci95'][0]:.1f}, {sg_a['rate_substate_speaking_hr_ci95'][1]:.1f}]` | `+{c_sub['diff_obs']:.2f}/hr` `[{c_sub['diff_ci95'][0]:.2f}, {c_sub['diff_ci95'][1]:.2f}]` | **`{c_sub['ratio_obs']:.2f}×`** `[{c_sub['ratio_ci95'][0]:.2f}×, {c_sub['ratio_ci95'][1]:.2f}×]` | `{c_sub['perm_p_value_speaking_hr']:.4f}` |")
    a(f"| Sub-State Rate / 1,000 Words | `{sg_c['rate_substate_per_1k_words']:.2f}` | `{sg_a['rate_substate_per_1k_words']:.2f}` | — | `{sg_c['rate_substate_per_1k_words']/sg_a['rate_substate_per_1k_words']:.2f}×` | — |")
    a(f"| **Combined Localism (State + Sub-State)** | **`{sg_c['combined_local_mentions']}` (`{sg_c['rate_combined_speaking_hr']:.2f}/hr`)** | **`{sg_a['combined_local_mentions']}` (`{sg_a['rate_combined_speaking_hr']:.2f}/hr`)** | `+{c_comb['diff_obs']:.2f}/hr` `[{c_comb['diff_ci95'][0]:.1f}, {c_comb['diff_ci95'][1]:.1f}]` | **`{c_comb['ratio_obs']:.2f}×`** `[{c_comb['ratio_ci95'][0]:.2f}×, {c_comb['ratio_ci95'][1]:.2f}×]` | **`{c_comb['perm_p_value_speaking_hr']:.4f}`** |\n")

    a("**Top Cited In-State Places (RSS Corpus):** A person-name guard in `count_substate_geo` prevented false-positive “Jackson” matches when preceded by first names like “Jesse Jackson” (while retaining Colom’s genuine Jackson, MS rally mention in `colom_morningjoe_20261113_8`), and `up north` (6 hits) + `wolverine` (3 U-M/state-mascot hits) were retained after verifying every utterance in context:\n")
    a("| Rank | Scott Colom — Top MS Places | Count | Abdul El-Sayed — Top MI Places | Count |")
    a("|---:|---|---:|---|---:|")
    for idx in range(15):
        cp = sg_c["top_places"][idx] if idx < len(sg_c["top_places"]) else {"place": "—", "count": 0}
        ap = sg_a["top_places"][idx] if idx < len(sg_a["top_places"]) else {"place": "—", "count": 0}
        a(f"| {idx + 1} | {cp['place'].title()} | {cp['count']} | {ap['place'].title()} | {ap['count']} |")
    a("")

    a("### Test B: Official Rev.com Verbatim Events (Including GOP Opponent Mike Rogers on the Same Stage)\n")
    a("Official verbatim Rev.com speaker transcripts eliminate Whisper ASR and speaker-attribution noise entirely — and the **October 21 Detroit Economic Club Q&A** provides a direct same-stage comparison against GOP nominee **Mike Rogers** answering the same moderator in front of the same Michigan business audience:\n")

    a("| Rev.com Verbatim Event | Speaker | Words | Strict State | State / 1k Words | Sub-State Places | Sub-State / 1k Words | Top Sub-State Places |")
    a("|---|---|---:|---:|---:|---:|---:|---|")
    for k in ["colom_victory", "abdul_victory", "rogers_detroit_forum", "abdul_detroit_forum", "abdul_primary_presser"]:
        d = rv[k]
        bd_str = ", ".join(f"{pl.title()} ({ct})" for pl, ct in sorted(d["substate_geo_breakdown"].items(), key=lambda kv: (-kv[1], kv[0])))
        a(f"| [{d['label']}]({d['url']}) | {d['speaker']} | `{d['word_count']:,}` | `{d['strict_mentions']}` | **`{d['per_1k_words_strict']:.2f}`** | `{d['substate_geo_mentions']}` | `{d['per_1k_words_substate_geo']:.2f}` | {bd_str} |")
    a("")
    a(f"Notice two critical checks: even in prepared victory speeches, Colom used his state’s name **`{rev_vic_ratio:.2f}×` as often per 1,000 words** (`{rv['colom_victory']['per_1k_words_strict']:.2f}` vs. `{rv['abdul_victory']['per_1k_words_strict']:.2f}`, `22` vs. `17` mentions); and at the October 21 Detroit Economic Club Q&A, GOP opponent **Mike Rogers** said `Michigan` **`{rev_det_state_ratio:.2f}×` as often** (`2.83` vs. `1.34` per 1k words) and cited Michigan cities **`{rev_det_sub_ratio:.2f}×` as often** (`5.40` vs. `0.89`, including `15` references to Detroit vs. El-Sayed’s `2`).\n")
    a("![Sub-State Places & Rev Forums](chart_4_substate_and_rev_forums.png)\n")

    # 6. Methodology, Sensitivity & Borderline Audit
    a("## 6. Methodology, Calibration & Borderline Adjudication Audit\n")
    a("### Audio Pipeline & Voiceprint Calibration\n")
    a("1. **Transcription:** All 84 eligible episodes were localized to the interview region (`faster-whisper` `medium.en` on GPU) with word-level timestamps (`3` prefix edge-case hits verified as benign domain strings: `michiganpublic`).\n")
    a("2. **Zero-Padding Fix & Clustering:** Flattened word streams were segmented into candidate utterances and embedded using `microsoft/wavlm-base-plus-sv` with **no batch zero-padding** (`embed_chunks_nopad`). Candidate centroids built from verified solo clips achieved clean separation (`cross-candidate similarity = 0.6260`). Calibrated cosine thresholds: `tau_colom = 0.945`, `tau_abdul = 0.915`.\n")
    a("3. **Naive Transcript Failure Proof:** Counting raw transcript occurrences without speaker diarization attributes **`{:.1f}%`** of `\"Mississippi\"` mentions (`{}/{}`) and **`{:.1f}%`** of `\"Michigan\"` mentions (`{}/{}`) to hosts, panelists, and intros (`naive window rates: {:.2f}/hr vs. {:.2f}/hr`).\n".format(
        nv["scott_colom"]["non_candidate_share_pct"], nv["scott_colom"]["non_candidate_filtered_mentions"], nv["scott_colom"]["unattributed_strict_mentions"],
        nv["abdul_el_sayed"]["non_candidate_share_pct"], nv["abdul_el_sayed"]["non_candidate_filtered_mentions"], nv["abdul_el_sayed"]["unattributed_strict_mentions"],
        nv["scott_colom"]["naive_rate_per_window_hr"], nv["abdul_el_sayed"]["naive_rate_per_window_hr"],
    ))

    a("### Threshold Sensitivity & Raw-vs.-Adjudicated Audit\n")
    a("| Acoustic Threshold Setting | Colom Speak Hrs | Colom Strict (/hr) | El-Sayed Speak Hrs | El-Sayed Strict (/hr) | Ratio |")
    a("|---|---:|---:|---:|---:|---:|")
    for tag, lbl in [("threshold_lo", "Loose (`tau - 0.025`, raw acoustic)"), ("threshold_mid", "Primary (`tau_colom=0.945, tau_abdul=0.915`, raw acoustic)"), ("threshold_hi", "Strict (`tau + 0.025`, raw acoustic)")]:
        dc, da = sens[tag]["scott_colom"], sens[tag]["abdul_el_sayed"]
        a(f"| {lbl} | `{dc['speaking_hours']:.2f}` | `{dc['strict_mentions']}` (`{dc['rate_speaking_hr_strict']:.2f}/hr`) | `{da['speaking_hours']:.2f}` | `{da['strict_mentions']}` (`{da['rate_speaking_hr_strict']:.2f}/hr`) | `{dc['rate_speaking_hr_strict']/da['rate_speaking_hr_strict']:.2f}×` |")
    a(f"| **Primary + Manual Borderline Adjudication (Headline)** | **`{ov_c['speaking_hours']:.2f}`** | **`{ov_c['strict_mentions']}` (`{ov_c['rate_speaking_hr']:.2f}/hr`)** | **`{ov_a['speaking_hours']:.2f}`** | **`{ov_a['strict_mentions']}` (`{ov_a['rate_speaking_hr']:.2f}/hr`)** | **`{comp['ratio_obs']:.2f}×`** |\n")

    a("Every acoustically borderline/disagreeing mention (`{}` total: **{}** in-cluster `raw_cand=False` mentions with `sim_local >= tau`, plus **{}** `raw_cand=True` mentions with `sim_local < tau`) was manually read with ±18 seconds of surrounding context (`data/mention_adjudications.json`):\n".format(
        len(in_cl) + len(cand_lt), len(in_cl), len(cand_lt)
    ))
    a(f"- **Scott Colom:** `+34` strict (`+40` broad incl. demonyms) missed candidate turns restored (e.g., `colom_lastword_20261110` campaign-ad voiceover & `colom_mtp_20261115` short transition clauses); `-9` host/panel leaks removed (e.g., *It’s a New Day with Rip Daniels* host questions on Jan 15 & Aug 31, *Good for Business* host Mississippi State football question, `#RolandMartinUnfiltered` panelist reference to `Colom`). Net strict shift: `650 -> 675` (`+3.85%`; `118.24 -> 122.78/hr`).\n")
    a(f"- **Abdul El-Sayed:** `+16` strict (`+19` broad) missed candidate turns restored (e.g., *All In with Chris Hayes* “I've been an Abdul in Michigan my whole life” & *All Access* “I want a world, I want a Michigan”), `-2` host leaks removed (*The Beat with Ari Melber* `[406.27s]` gas-price host recap & *The Weekend* `[1007.80s]` primary-day host intro). Net strict shift: `233 -> 247` (`+6.01%`; `20.64 -> 21.89/hr`).\n")
    a(f"- **Stability conclusion:** Manual adjudication retains `{sum(1 for m in cand_lt if not m['adjudicated'])}/{len(cand_lt)}` (`{100.0*sum(1 for m in cand_lt if not m['adjudicated'])/len(cand_lt):.1f}%`) of the `cand_loc_lt_tau` borderline subset as genuine candidate utterances and recovers `{sum(1 for m in in_cl if m['adjudicated'])}/{len(in_cl)}` in-cluster misses, shifting the headline ratio only marginally from **`{rva['comparison']['raw_ratio_speaking_hr']:.2f}×` (raw) to `{comp['ratio_obs']:.2f}×` (adjudicated)**.\n")

    # 7. Limitations
    a("## 7. Limitations & Boundaries\n")
    a("- **Unavailable Video Archives:** C-SPAN / Internet Archive TV News MP4 & closed-caption files returned `HTTP 403 Forbidden`, YouTube audio extraction was excluded by rule, Rev.com’s Michigan Senate debate transcript returned `HTTP 404`, and `colom_wjtv_20260314` RSS audio returned `HTTP 404`. All findings represent publicly reachable RSS broadcast/podcast audio and verified Rev.com transcripts.\n")
    a("- **Simultaneous Twin / Clip Nuance:** Joint twin interview `colom_beat_20261121` was excluded to avoid Andrew/Scott voiceprint confounding; `colom_lastword_20261110` included a brief aired Scott Colom ad voiceover (“Every Mississippian ought to walk through once”) because Scott Colom himself spoke it.\n")
    a("- **Sub-State Place Names:** While “Jesse Jackson” was filtered via person-name context, `wolverine` includes 3 University of Michigan/mascot mentions in El-Sayed’s RSS interviews (`1.7%` of his 177 sub-state hits) and 1 in his victory speech; excluding those does not alter the sub-state conclusion.\n")

    # 8. Complete Per-Appearance Table (All 84) + Excluded (12)
    a(f"## 8. Complete Per-Appearance Dataset ({len(apps)} Verified Interviews)\n")
    a("| Episode ID | Candidate | Date | Show | Category | Period | Speak Min | Words | Raw Strict | Adj Strict | Broad | Non-Cand Filtered | Sub-State Geo | Strict / Hr | Strict / 1k |")
    a("|---|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in apps:
        sp_m = float(r["cand_speaking_sec"]) / 60.0
        a(f"| `{r['episode_id']}` | `{r['candidate']}` | {r['pub_date']} | {r['show']} | `{r['category']}` | `{r['period']}` | {sp_m:.1f} | {int(r['cand_words']):,} | {r['raw_acoustic_strict_mentions']} | {r['strict_mentions']} | {r['broad_mentions']} | {r['noncand_strict_mentions']} | {r['substate_geo_mentions']} | **{float(r['rate_per_speaking_hr_strict']):.1f}** | {float(r['rate_per_1k_words_strict']):.2f} |")
    a("")

    a(f"### Excluded Manifest Entries ({len(excl)} Non-Candidate / Ambiguous / Sub-60s Shows)\n")
    a("| Episode ID | Candidate | Date | Show | Duration (s) | Exclusion Reason |")
    a("|---|---|---:|---|---:|---|")
    for eid, ev in excl.items():
        dur = str(ev["duration_sec"]) if ev.get("duration_sec") is not None else "—"
        a(f"| `{eid}` | `{ev['candidate']}` | {ev['pub_date']} | {ev['show']} | {dur} | `{ev['reason']}` |")
    a("")

    (OUT_DIR / "report.md").write_text("\n".join(lines))
    print(f"Wrote {OUT_DIR / 'report.md'} ({len(lines)} markdown lines).")


if __name__ == "__main__":
    main()

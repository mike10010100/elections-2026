#!/usr/bin/env python3
"""Curate and HTTP-verify the Platner vs. Fetterman direct-interview RSS manifest."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

PF_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = PF_DIR / "data"
RAW_PATH = DATA_DIR / "raw_candidates_pf.json"
OUT_PATH = DATA_DIR / "rss_manifest_pf.json"

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PodcastCorpusResearch/1.0)"}

# Selection tuples from raw_candidates_pf.json:
# (candidate, idx_in_cand_list, episode_id, category, period, is_full_broadcast, matched_venue)
RAW_SELECTIONS = [
    # Graham Platner (24 from raw_candidates_pf.json + 2 from iTunes probe)
    ("graham_platner", 327, "gp_why_is_this_happening_20250909", "national_longform", "campaign", False, ""),
    ("graham_platner", 306, "gp_psaki_briefing_20251029", "national_tv", "campaign", True, "jen_psaki"),
    ("graham_platner", 305, "gp_breaking_points_20251031", "national_longform", "campaign", True, ""),
    ("graham_platner", 304, "gp_lever_time_20251101", "national_longform", "campaign", False, "lever_time"),
    ("graham_platner", 302, "gp_beacon_20251212", "local_in_state", "campaign", False, ""),
    ("graham_platner", 300 if False else 287, "gp_death_sex_money_20260303", "national_longform", "campaign", False, ""),
    ("graham_platner", 299, "gp_daily_beast_20260120", "national_longform", "campaign", True, ""),
    ("graham_platner", 297, "gp_david_pakman_20260129", "national_longform", "campaign", True, ""),
    ("graham_platner", 294, "gp_meidas_20260221", "national_longform", "campaign", True, ""),
    ("graham_platner", 293, "gp_office_hours_20260226", "national_longform", "campaign", True, ""),
    ("graham_platner", 269, "gp_mehdi_unfiltered_20260416", "national_longform", "campaign", False, "mehdi_unfiltered"),
    ("graham_platner", 267, "gp_choose_hard_way_20260421", "national_longform", "campaign", False, ""),
    ("graham_platner", 266, "gp_weekly_show_stewart_20260429", "national_longform", "campaign", False, "weekly_show"),
    ("graham_platner", 261, "gp_psaki_briefing_20260501", "national_tv", "campaign", True, "jen_psaki"),
    ("graham_platner", 258, "gp_lever_time_20260508", "national_longform", "campaign", False, "lever_time"),
    ("graham_platner", 253, "gp_wgan_20260526", "local_in_state", "campaign", True, ""),
    ("graham_platner", 252, "gp_all_in_hayes_20260526", "national_tv", "campaign", True, "all_in"),
    ("graham_platner", 223, "gp_11th_hour_velshi_20260605", "national_tv", "campaign", True, "ms_now_11th"),
    ("graham_platner", 216, "gp_beacon_townhall_20260605", "local_in_state", "campaign", True, ""),
    ("graham_platner", 211, "gp_all_in_hayes_20260605", "national_tv", "campaign", True, "all_in"),
    ("graham_platner", 174, "gp_morning_joe_20260610", "national_tv", "post_primary", True, "morning_joe"),

    # John Fetterman (26 from raw_candidates_pf.json)
    ("john_fetterman", 132, "jf_new_yorker_20250221", "national_longform", "senator", True, "new_yorker"),
    ("john_fetterman", 131, "jf_call_me_back_20250227", "national_longform", "senator", False, ""),
    ("john_fetterman", 121, "jf_real_time_maher_20250614", "national_tv", "senator", True, "real_time"),
    ("john_fetterman", 118, "jf_state_of_the_union_20250921", "national_tv", "senator", True, "cnn_sotu"),
    ("john_fetterman", 117, "jf_collins_20250930", "national_tv", "senator", True, "kaitlan_collins"),
    ("john_fetterman", 116, "jf_state_of_the_union_20251102", "national_tv", "senator", True, "cnn_sotu"),
    ("john_fetterman", 115, "jf_meet_the_press_20251110", "national_tv", "senator", True, "meet_the_press"),
    ("john_fetterman", 114, "jf_honestly_weiss_20251111", "national_longform", "senator", False, ""),
    ("john_fetterman", 112, "jf_next_question_couric_20251113", "national_longform", "senator", False, ""),
    ("john_fetterman", 111, "jf_meet_the_press_20251212", "national_tv", "senator", True, "meet_the_press"),
    ("john_fetterman", 107, "jf_conversation_burns_20260213", "national_longform", "senator", False, ""),
    ("john_fetterman", 104, "jf_takeout_garrett_20260312", "national_tv", "senator", True, "cbs_takeout"),
    ("john_fetterman", 103, "jf_all_in_pod_20260318", "national_longform", "senator", False, "all_in_pod"),
    ("john_fetterman", 101, "jf_smerconish_20260420", "national_longform", "senator", True, "smerconish"),
    ("john_fetterman", 97, "jf_citizen_mccain_20260423", "national_longform", "senator", True, ""),
    ("john_fetterman", 84, "jf_real_time_maher_20260509", "national_tv", "senator", True, "real_time"),
    ("john_fetterman", 83, "jf_club_random_maher_20260511", "national_longform", "senator", False, ""),
    ("john_fetterman", 80, "jf_reason_interview_20260513", "national_longform", "senator", False, ""),
    ("john_fetterman", 75, "jf_all_in_pod_20260610", "national_longform", "senator", False, "all_in_pod"),
    ("john_fetterman", 74, "jf_meet_the_press_20260612", "national_tv", "senator", True, "meet_the_press"),
    ("john_fetterman", 72, "jf_smerconish_20260702", "national_longform", "senator", True, "smerconish"),
    ("john_fetterman", 71, "jf_takeout_garrett_20260707", "national_tv", "senator", True, "cbs_takeout"),
    ("john_fetterman", 64, "jf_squawk_pod_20260728", "national_tv", "senator", True, ""),
    ("john_fetterman", 62, "jf_meet_the_press_20260729", "national_tv", "senator", True, "meet_the_press"),
    ("john_fetterman", 60, "jf_weekly_show_stewart_20260805", "national_longform", "senator", False, "weekly_show"),
    ("john_fetterman", 57, "jf_make_it_make_sense_20260807", "national_longform", "senator", False, ""),
]

# Missing Platner indices from raw_candidates_pf.json (verified above by title match)
RAW_BY_TITLE_HINTS = [
    ("graham_platner", "gp_new_yorker_20251219", "The New Yorker Radio Hour", "2025-12-19", "national_longform", "campaign", True, "new_yorker"),
    ("graham_platner", "gp_zero_hour_20260207", "The Zero Hour with RJ Eskow", "2026-02-07", "national_longform", "campaign", True, ""),
    ("graham_platner", "gp_pod_save_america_20260301", "Pod Save America", "2026-03-01", "national_longform", "campaign", True, "pod_save_america"),
]

# Direct iTunes Additions not in raw_candidates_pf.json
EXTRA_ITUNES_EPISODES = [
    {
        "episode_id": "gp_find_out_pod_20251114",
        "candidate": "graham_platner",
        "show": "The Find Out Podcast",
        "title": "Graham Platner Joins the Find Out Pod",
        "pub_date": "2025-11-14",
        "category": "national_longform",
        "period": "campaign",
        "is_full_broadcast": False,
        "matched_venue": "",
        "duration_sec": 4188,
        "audio_url": "https://pdst.fm/e/mgln.ai/e/135/verifi.podscribe.com/rss/p/tracking.swap.fm/track/i7NUCPwi3tJP053nG6mP/traffic.megaphone.fm/STU7124865073.mp3?updated=1773339247",
        "description": "Graham walks us through why he's jumping into the race to take on Susan Collins and how he thinks Democrats can win by actually fighting for working people.",
    },
    {
        "episode_id": "gp_left_reckoning_20251218",
        "candidate": "graham_platner",
        "show": "Left Reckoning",
        "title": "250 - Graham Platner joins Left Reckoning",
        "pub_date": "2025-12-18",
        "category": "national_longform",
        "period": "campaign",
        "is_full_broadcast": True,
        "matched_venue": "",
        "duration_sec": 4476,
        "audio_url": "https://anchor.fm/s/d691ac7c/podcast/play/112844113/https%3A%2F%2Fd3ctxlq1ktw2nl.cloudfront.net%2Fstaging%2F2025-11-18%2F414654570-44100-2-e4617a6a472af.mp3",
        "description": "Maine Senate candidate Graham Platner joins us to talk about his run for Senate. Maine, far right hate, military contracting, healthcare and more.",
    },
]


def probe_http(entry: dict) -> dict:
    url = entry["audio_url"]
    try:
        r = requests.get(
            url,
            headers={**HEADERS, "Range": "bytes=0-1023"},
            timeout=25,
            allow_redirects=True,
            stream=True,
        )
        status = r.status_code
        cl = r.headers.get("Content-Range") or r.headers.get("Content-Length") or ""
        ctype = r.headers.get("Content-Type", "")
        r.close()
        return {**entry, "http_status": status, "http_len": cl, "http_type": ctype, "http_ok": status in (200, 206)}
    except Exception as e:
        return {**entry, "http_status": 0, "http_len": "", "http_type": str(e)[:100], "http_ok": False}


def main():
    raw = json.loads(RAW_PATH.read_text())
    by_cand = {
        "graham_platner": [r for r in raw if r.get("candidate") == "graham_platner"],
        "john_fetterman": [r for r in raw if r.get("candidate") == "john_fetterman"],
    }

    entries = []
    seen_ids = set()
    for cand, idx, eid, cat, per, is_fb, mv in RAW_SELECTIONS:
        r = by_cand[cand][idx]
        entries.append({
            "episode_id": eid,
            "candidate": cand,
            "show": r.get("show", ""),
            "title": r.get("title", ""),
            "pub_date": str(r.get("pub_date", ""))[:10],
            "category": cat,
            "period": per,
            "is_full_broadcast": is_fb,
            "matched_venue": mv,
            "duration_sec": r.get("duration_sec"),
            "audio_url": r["audio_url"],
            "description": (r.get("description") or "").replace("\n", " ").strip()[:500],
        })
        seen_ids.add(eid)

    for cand, eid, show_hint, date_hint, cat, per, is_fb, mv in RAW_BY_TITLE_HINTS:
        matches = [
            r for r in by_cand[cand]
            if show_hint.lower() in (r.get("show") or "").lower()
            and str(r.get("pub_date") or "").startswith(date_hint)
        ]
        assert len(matches) == 1, f"Expected 1 match for {eid}, got {len(matches)}"
        r = matches[0]
        entries.append({
            "episode_id": eid,
            "candidate": cand,
            "show": r.get("show", ""),
            "title": r.get("title", ""),
            "pub_date": str(r.get("pub_date", ""))[:10],
            "category": cat,
            "period": per,
            "is_full_broadcast": is_fb,
            "matched_venue": mv,
            "duration_sec": r.get("duration_sec"),
            "audio_url": r["audio_url"],
            "description": (r.get("description") or "").replace("\n", " ").strip()[:500],
        })
        seen_ids.add(eid)

    for ex in EXTRA_ITUNES_EPISODES:
        assert ex["episode_id"] not in seen_ids
        entries.append(ex)
        seen_ids.add(ex["episode_id"])

    # Sort chronologically newest first per candidate
    entries.sort(key=lambda x: (x["candidate"], x["pub_date"], x["episode_id"]))

    verified = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = [ex.submit(probe_http, e) for e in entries]
        for fut in as_completed(futs):
            verified.append(fut.result())

    verified.sort(key=lambda x: (x["candidate"], x["pub_date"], x["episode_id"]))
    OUT_PATH.write_text(json.dumps(verified, indent=2))

    for cand in ["graham_platner", "john_fetterman"]:
        sub = [v for v in verified if v["candidate"] == cand]
        ok = sum(1 for v in sub if v["http_ok"])
        print(f"\n=== {cand}: {ok}/{len(sub)} HTTP OK ===")
        for v in sub:
            mark = "OK " if v["http_ok"] else "BAD"
            print(f"  [{mark} {v['http_status']}] {v['pub_date']} | {v['episode_id']:32s} | fb={str(v['is_full_broadcast']):5s} | {v['show'][:28]:28s} | {v['title'][:52]}")


if __name__ == "__main__":
    main()

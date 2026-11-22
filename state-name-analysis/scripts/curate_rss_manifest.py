#!/usr/bin/env python3
"""Curate a clean, deduplicated, balanced 2026 RSS episode manifest for both candidates."""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"

raw = json.loads((DATA_DIR / "rss_raw_candidates.json").read_text())
extra = json.loads((DATA_DIR / "rss_extra_local.json").read_text())

# Build lookup pool of all episodes across feed_results, direct_itunes_episodes, and extra_local
ALL_EPS = []
for fr in raw["feed_results"]:
    sh = fr.get("show", "")
    furl = fr.get("feed_url", "")
    for m in fr.get("matches", []) + fr.get("recent_2026", []):
        if m.get("audio_url"):
            ALL_EPS.append({**m, "show": m.get("show") or sh, "feed_url": m.get("feed_url") or furl})

for ep in raw["direct_itunes_episodes"] + extra:
    if ep.get("audio_url"):
        ALL_EPS.append(ep)


def find_ep(show_sub: str, pub_date: str, title_sub: str = "") -> dict | None:
    show_l = show_sub.lower()
    title_l = title_sub.lower()
    cands = []
    for ep in ALL_EPS:
        if show_l in (ep.get("show") or "").lower() and ep.get("pub_date") == pub_date:
            if not title_l or title_l in (ep.get("title") or "").lower():
                cands.append(ep)
    if not cands:
        return None
    # Prefer entries with description & duration
    cands.sort(key=lambda x: (len(x.get("description") or ""), x.get("duration_sec") or 0), reverse=True)
    return cands[0]


# Curated candidate list: (slug, candidate, show_sub, pub_date, title_sub, category, is_full_broadcast, matched_venue, note)
SPEC = [
    # ==================== SCOTT COLOM ====================
    # National TV (post-election & campaign)
    ("colom_beat_20261121", "scott_colom", "The Beat with Ari Melber", "2026-11-21", "Colom Twins", "national_tv", True, "ms_now_beat", "Ari Melber interview w/ Colom twins"),
    ("colom_mtp_20261115", "scott_colom", "Meet the Press", "2026-11-15", "Sean Duffy, Scott Colom", "national_tv", True, "meet_the_press", "Meet the Press w/ Kristen Welker"),
    ("colom_weeknight_20261113", "scott_colom", "The Weeknight", "2026-11-13", "Take Our Power Back", "national_tv", True, "ms_now_weeknight", "Symone Sanders exclusive sit-down"),
    ("colom_morningjoe_20261113_6", "scott_colom", "Morning Joe", "2026-11-13", "GOP Midterm Fallout", "national_tv", True, "morning_joe", "Morning Joe Nov 13 6am check"),
    ("colom_morningjoe_20261113_7", "scott_colom", "Morning Joe", "2026-11-13", "big challenges", "national_tv", True, "morning_joe", "Morning Joe Nov 13 7am check"),
    ("colom_morningjoe_20261113_8", "scott_colom", "Morning Joe", "2026-11-13", "Key takeaways", "national_tv", True, "morning_joe", "Morning Joe Nov 13 8am check"),
    ("colom_ac360_20261110", "scott_colom", "Anderson Cooper 360", "2026-11-10", "Acceptance to Denial", "national_tv", True, "cnn_ac360", "Anderson Cooper Nov 10"),
    ("colom_lastword_20261110", "scott_colom", "The Last Word", "2026-11-10", "Hakeem Jeffries", "national_tv", True, "ms_now_lastword", "Lawrence O'Donnell Nov 10"),
    ("colom_psaki_20261107", "scott_colom", "The Briefing with Jen Psaki", "2026-11-07", "MAGA IN DISARRAY", "national_tv", True, "jen_psaki", "Jen Psaki Nov 6/7"),
    ("colom_mtpnow_20261105", "scott_colom", "Meet the Press", "2026-11-05", "Meet the Press NOW", "national_tv", True, "nbc_news", "MTP NOW Nov 5"),
    ("colom_mtpnow_20261030", "scott_colom", "Meet the Press", "2026-10-30", "Meet the Press NOW", "national_tv", True, "nbc_news", "MTP NOW Oct 30"),
    ("colom_weeknight_20261024", "scott_colom", "The Weeknight", "2026-10-24", "This Is the Steal", "national_tv", True, "ms_now_weeknight", "The Weeknight Oct 23/24"),
    ("colom_psaki_20261023", "scott_colom", "The Briefing with Jen Psaki", "2026-10-23", "Trump Corruption", "national_tv", True, "jen_psaki", "Jen Psaki Oct 22/23"),
    ("colom_outfront_20261022", "scott_colom", "Erin Burnett OutFront", "2026-10-22", "Ramaswamy", "national_tv", True, "cnn_outfront", "Erin Burnett Oct 22"),
    ("colom_collins_20261014", "scott_colom", "The Source with Kaitlan Collins", "2026-10-14", "Maine and Georgia", "national_tv", True, "kaitlan_collins", "Kaitlan Collins Oct 14"),
    ("colom_weekend_20261010_7", "scott_colom", "The Weekend", "2026-10-10", "GOP in", "national_tv", True, "ms_now_weekend", "The Weekend Oct 10 7am check"),
    ("colom_weekend_20261010_8", "scott_colom", "The Weekend", "2026-10-10", "Next Target", "national_tv", True, "ms_now_weekend", "The Weekend Oct 10 8am check"),
    ("colom_weekend_20261010_9", "scott_colom", "The Weekend", "2026-10-10", "Election Monitors", "national_tv", True, "ms_now_weekend", "The Weekend Oct 10 9am check"),
    ("colom_stateofplay_20261005", "scott_colom", "State of Play", "2026-10-05", "Red-State Tour", "national_tv", True, "nbc_news", "Peter Alexander Oct 5"),
    ("colom_politicsnation_20260913", "scott_colom", "PoliticsNation", "2026-09-13", "Defending Democracy", "national_tv", True, "ms_now_politicsnation", "Al Sharpton Sep 13"),
    ("colom_weeknight_20260729", "scott_colom", "The Weeknight", "2026-07-29", "Wholly Unqualified", "national_tv", True, "ms_now_weeknight", "The Weeknight Jul 28/29"),
    ("colom_insidepol_20260729", "scott_colom", "CNN Inside Politics", "2026-07-29", "Fauci", "national_tv", True, "cnn_insidepol", "Dana Bash Jul 29"),
    ("colom_weekendpt_20260504", "scott_colom", "The Weekend Primetime", "2026-05-04", "Can Mississippi go blue", "national_tv", True, "ms_now_weekend", "The Weekend Primetime May 4"),

    # National Long-Form (Scott Colom)
    ("colom_freshair_20261119", "scott_colom", "Fresh Air", "2026-11-19", "reflection of the nation", "national_longform", False, "npr", "Fresh Air 1-on-1"),
    ("colom_breakfastclub_20261102", "scott_colom", "The Breakfast Club", "2026-11-02", "INTERVIEW: Scott Colom", "national_longform", False, "breakfast_club", "Breakfast Club dedicated ep"),
    ("colom_watch_20261029", "scott_colom", "The Watch with Radley Balko", "2026-10-29", "Scott Colom", "national_longform", False, "", "The Watch Podcast ep 2"),
    ("colom_tavissmiley_20261028", "scott_colom", "Tavis Smiley", "2026-10-28", "Scott Colom", "national_longform", False, "tavis_smiley", "Tavis Smiley 1-on-1"),
    ("colom_urbanview_20261022", "scott_colom", "Urban View Mornings", "2026-10-22", "Voices of Change", "national_longform", False, "", "Urban View Mornings w/ Greg Carr"),
    ("colom_longplay_20261008", "scott_colom", "Long Play", "2026-10-08", "Finally Paying Attention", "national_longform", False, "", "Long Play Bonus w/ Colom"),
    ("colom_macfarlane_20260929", "scott_colom", "Scott MacFarlane Reports", "2026-09-29", "Mississipi in Play", "national_longform", False, "scott_macfarlane", "Scott MacFarlane Reports"),
    ("colom_roland_20260903", "scott_colom", "#RolandMartinUnfiltered", "2026-09-03", "Black Woman Cleared", "national_longform", True, "roland_martin", "Roland Martin Sep 3"),
    ("colom_claycane_20260721", "scott_colom", "Clay Cane Extended", "2026-07-21", "Scott Colom", "national_longform", False, "clay_cane", "Clay Cane Extended"),
    ("colom_beyondcampaign_20260604", "scott_colom", "Beyond The Campaign", "2026-06-04", "Scott Colom", "national_longform", False, "", "Beyond The Campaign"),
    ("colom_canweplease_20260407", "scott_colom", "Can We Please Talk?", "2026-04-07", "Scott Colom", "national_longform", False, "", "Can We Please Talk?"),
    ("colom_realpatriotism_20260305", "scott_colom", "Real Patriotism", "2026-03-05", "Scott Colom", "national_longform", False, "", "Real Patriotism"),

    # Local / In-State Media (Scott Colom)
    ("colom_ripdaniels_20261027", "scott_colom", "It's a New Day with Rip Daniels", "2026-10-27", "Scott Colom", "local_in_state", True, "", "Biloxi/Gulfport MS radio"),
    ("colom_ripdaniels_20261007", "scott_colom", "It's a New Day with Rip Daniels", "2026-10-07", "Scott Colom", "local_in_state", True, "", "Biloxi/Gulfport MS radio"),
    ("colom_mstoday_20261006", "scott_colom", "The Other Side: Mississippi Today", "2026-10-06", "running the roads", "local_in_state", False, "", "Mississippi Today Ep 446"),
    ("colom_mshappenings_20261005", "scott_colom", "Mississippi Happenings", "2026-10-05", "Scott Colom", "local_in_state", False, "", "Mississippi Happenings"),
    ("colom_goodforbiz_20261001", "scott_colom", "The Good for Business", "2026-10-01", "Scott Colom", "local_in_state", False, "", "Columbus MS Good for Business"),
    ("colom_ripdaniels_20260831", "scott_colom", "It's a New Day with Rip Daniels", "2026-08-31", "Scott Colom", "local_in_state", True, "", "Biloxi/Gulfport MS radio"),
    ("colom_giveadamn_20260723", "scott_colom", "Those Who Give A Damn", "2026-07-23", "Scott Colom", "local_in_state", False, "", "MS Dr. Duvalier Malone podcast"),
    ("colom_mstoday_20260505", "scott_colom", "The Other Side: Mississippi Today", "2026-05-05", "why he's running", "local_in_state", False, "", "Mississippi Today Ep 424"),
    ("colom_ripdaniels_20260203", "scott_colom", "It's a New Day with Rip Daniels", "2026-02-03", "Scott Colom", "local_in_state", True, "", "Biloxi/Gulfport MS radio"),

    # ==================== ABDUL EL-SAYED ====================
    # National TV (post-election & campaign)
    ("abdul_psaki_20261118", "abdul_el_sayed", "The Briefing with Jen Psaki", "2026-11-18", "Confusing response", "national_tv", True, "jen_psaki", "Jen Psaki Nov 17/18 RFK Jr clip"),
    ("abdul_pbs_20261112", "abdul_el_sayed", "PBS News Hour - Segments", "2026-11-12", "Abdul El-Sayed on Democratic leadership", "national_tv", False, "pbs_newshour", "PBS NewsHour standalone segment"),
    ("abdul_collins_20261111", "abdul_el_sayed", "The Source with Kaitlan Collins", "2026-11-11", "Hegseth Impeachment", "national_tv", True, "kaitlan_collins", "Kaitlan Collins Nov 11"),
    ("abdul_thisweek_20261108", "abdul_el_sayed", "This Week with George", "2026-11-08", "November 8", "national_tv", True, "abc_news", "ABC This Week w/ Jon Karl"),
    ("abdul_morningjoe_20261105", "abdul_el_sayed", "Morning Joe", "2026-11-05", "Abdul El-Sayed joins Morning Joe", "national_tv", True, "morning_joe", "Morning Joe Nov 5"),
    ("abdul_allaccess_20261020", "abdul_el_sayed", "All Access with Linsey Davis", "2026-10-20", "Abdul El-Sayed", "national_tv", False, "abc_news", "ABC News All Access 1-on-1"),
    ("abdul_mtp_20261011", "abdul_el_sayed", "Meet the Press", "2026-10-11", "massive numbers", "national_tv", False, "meet_the_press", "Meet the Press standalone ep"),
    ("abdul_beat_20261001", "abdul_el_sayed", "The Beat with Ari Melber", "2026-10-01", "Abdul El-Sayed", "national_tv", True, "ms_now_beat", "Ari Melber Oct 1"),
    ("abdul_facethenation_20260913", "abdul_el_sayed", "Face the Nation", "2026-09-13", "Anthropic", "national_tv", True, "cbs_news", "Face the Nation Sep 13"),
    ("abdul_bloomberg_20260908", "abdul_el_sayed", "Bloomberg Talks", "2026-09-08", "Abdul El-Sayed", "national_tv", False, "", "Bloomberg Talks"),
    ("abdul_collins_20260901", "abdul_el_sayed", "The Source with Kaitlan Collins", "2026-09-01", "Data Centers", "national_tv", True, "kaitlan_collins", "Kaitlan Collins Sep 1"),
    ("abdul_morningjoe_20260810", "abdul_el_sayed", "Morning Joe", "2026-08-10", "El-Sayed dodges", "national_tv", True, "morning_joe", "Morning Joe Aug 10"),
    ("abdul_mtp_20260809", "abdul_el_sayed", "Meet the Press", "2026-08-09", "Abdul El-Sayed", "national_tv", True, "meet_the_press", "Meet the Press Aug 9"),
    ("abdul_sotu_20260809", "abdul_el_sayed", "State of the Union", "2026-08-09", "Midterm Countdown", "national_tv", True, "cnn_sotu", "CNN State of the Union Aug 9"),
    ("abdul_collins_20260806", "abdul_el_sayed", "The Source with Kaitlan Collins", "2026-08-06", "Marquee Primary Win", "national_tv", True, "kaitlan_collins", "Kaitlan Collins Aug 6"),
    ("abdul_morningjoe_20260805", "abdul_el_sayed", "Morning Joe", "2026-08-05", "Abdul El-Sayed joins Morning Joe", "national_tv", True, "morning_joe", "Morning Joe Aug 5"),
    ("abdul_11thhour_20260804", "abdul_el_sayed", "The 11th Hour", "2026-08-04", "Control the Senate", "national_tv", True, "ms_now_11th", "11th Hour Aug 4"),
    ("abdul_weekend_20260802", "abdul_el_sayed", "The Weekend", "2026-08-02", "Michigan Lookahead", "national_tv", True, "ms_now_weekend", "The Weekend Aug 2"),
    ("abdul_sotu_20260719", "abdul_el_sayed", "State of the Union", "2026-07-19", "Deadly Attack", "national_tv", True, "cnn_sotu", "CNN State of the Union Jul 19"),

    # National Long-Form (Abdul El-Sayed)
    ("abdul_claycane_20261120", "abdul_el_sayed", "Clay Cane Extended", "2026-11-20", "Abdul El-Sayed", "national_longform", False, "clay_cane", "Clay Cane Extended"),
    ("abdul_majority_20261116", "abdul_el_sayed", "The Majority Report", "2026-11-16", "El-Sayed on His Senate Agenda", "national_longform", True, "", "Majority Report Nov 16"),
    ("abdul_newsmakers_20261112", "abdul_el_sayed", "NPR's Newsmakers", "2026-11-12", "Abdul El-Sayed", "national_longform", False, "npr", "NPR Newsmakers 1-on-1"),
    ("abdul_psa_20261106", "abdul_el_sayed", "Pod Save America", "2026-11-06", "Storming the Capital", "national_longform", True, "", "Pod Save America live DC"),
    ("abdul_mehdi_20261106", "abdul_el_sayed", "Mehdi Unfiltered", "2026-11-06", "Historic Victory", "national_longform", False, "", "Zeteo / Mehdi Unfiltered"),
    ("abdul_60min_20261102", "abdul_el_sayed", "60 Minutes", "2026-11-02", "Extended Interview: Abdul El-Sayed", "national_longform", False, "", "60 Minutes Extended Interview"),
    ("abdul_hasanminhaj_20261028", "abdul_el_sayed", "Hasan Minhaj Doesn't Know", "2026-10-28", "Abdul El-Sayed", "national_longform", False, "", "Hasan Minhaj 1-on-1"),
    ("abdul_tavissmiley_20261028", "abdul_el_sayed", "Tavis Smiley", "2026-10-28", "Abdul El-Sayed", "national_longform", False, "tavis_smiley", "Tavis Smiley 1-on-1"),
    ("abdul_jonstewart_20261021", "abdul_el_sayed", "The Weekly Show with Jon Stewart", "2026-10-21", "Abdul El-Sayed", "national_longform", False, "", "Jon Stewart 1-on-1"),
    ("abdul_macfarlane_20261019", "abdul_el_sayed", "Scott MacFarlane Reports", "2026-10-19", "Closing Strong", "national_longform", False, "scott_macfarlane", "Scott MacFarlane Reports"),
    ("abdul_playbook_20261016", "abdul_el_sayed", "The Playbook Podcast", "2026-10-16", "new coalition", "national_longform", False, "", "POLITICO Playbook"),
    ("abdul_ragingmod_20260923", "abdul_el_sayed", "Raging Moderates", "2026-09-23", "Canada Trade War", "national_longform", True, "", "Raging Moderates"),
    ("abdul_psa_20260913", "abdul_el_sayed", "Pod Save America", "2026-09-13", "On the Ground in Michigan", "national_longform", False, "", "PSA Detroit sit-down"),
    ("abdul_breakfastclub_20260831", "abdul_el_sayed", "The Breakfast Club", "2026-08-31", "INTERVIEW: Abdul El-Sayed", "national_longform", False, "breakfast_club", "Breakfast Club dedicated ep"),
    ("abdul_jimacosta_20260807", "abdul_el_sayed", "The Jim Acosta Show", "2026-08-07", "Abdul El-Sayed", "national_longform", True, "", "Jim Acosta Show"),
    ("abdul_newyorker_20260731", "abdul_el_sayed", "The New Yorker Radio Hour", "2026-07-31", "Abdul El-Sayed", "national_longform", False, "", "New Yorker Radio Hour"),
    ("abdul_levertime_20260702", "abdul_el_sayed", "Lever Time", "2026-07-02", "Abdul El-Sayed", "national_longform", False, "", "Lever Time w/ David Sirota"),

    # Local / In-State Media (Abdul El-Sayed)
    ("abdul_metro_20261119", "abdul_el_sayed", "The Metro", "2026-11-19", "Arab problem", "local_in_state", True, "", "WDET Detroit The Metro"),
    ("abdul_michmash_20260904", "abdul_el_sayed", "MichMash Politics", "2026-09-04", "Abdul El-Sayed", "local_in_state", False, "", "WDET MichMash Politics"),
    ("abdul_metro_20260811", "abdul_el_sayed", "The Metro", "2026-08-11", "winning Michigan", "local_in_state", True, "", "WDET Detroit The Metro"),
    ("abdul_dailydetroit_20260507", "abdul_el_sayed", "Daily Detroit", "2026-05-07", "Medicare for All", "local_in_state", False, "", "Daily Detroit"),
    ("abdul_detroitdiff_20260212", "abdul_el_sayed", "Detroit is Different", "2026-02-12", "Abdul El-Sayed", "local_in_state", False, "", "Detroit is Different"),
]


def test_url(item: dict) -> tuple[str, int, str]:
    try:
        r = requests.get(
            item["audio_url"],
            headers={"Range": "bytes=0-1023", "User-Agent": "Mozilla/5.0"},
            timeout=15,
            allow_redirects=True,
        )
        return item["episode_id"], r.status_code, ""
    except Exception as e:
        return item["episode_id"], 0, str(e)[:80]


def main():
    manifest = []
    missing = []
    for slug, cand, show_sub, dt, tsub, cat, is_fb, mv, note in SPEC:
        ep = find_ep(show_sub, dt, tsub)
        if not ep:
            missing.append((slug, show_sub, dt, tsub))
            continue
        period = "post_election" if dt >= "2026-11-04" else "campaign"
        manifest.append({
            "episode_id": slug,
            "candidate": cand,
            "show": ep.get("show"),
            "title": ep.get("title"),
            "pub_date": dt,
            "duration_sec": ep.get("duration_sec"),
            "category": cat,
            "period": period,
            "is_full_broadcast": is_fb,
            "matched_venue": mv,
            "audio_url": ep.get("audio_url"),
            "description": ep.get("description", ""),
            "note": note,
        })

    print(f"Found {len(manifest)}/{len(SPEC)} episodes. Missing: {len(missing)}")
    for m in missing:
        print("  MISSING:", m)

    # Check audio URL reachability in parallel
    with ThreadPoolExecutor(max_workers=10) as ex:
        statuses = list(ex.map(test_url, manifest))
    status_map = {eid: (code, err) for eid, code, err in statuses}

    clean = []
    for item in manifest:
        code, err = status_map[item["episode_id"]]
        item["http_check"] = code
        if code in (200, 206):
            clean.append(item)
        else:
            print(f"  [URL DEAD] {item['episode_id']} ({item['show']} {item['pub_date']}): code={code} err={err}")

    for cand in ["scott_colom", "abdul_el_sayed"]:
        sub = [x for x in clean if x["candidate"] == cand]
        cats = {}
        pers = {}
        for x in sub:
            cats[x["category"]] = cats.get(x["category"], 0) + 1
            pers[x["period"]] = pers.get(x["period"], 0) + 1
        print(f"FINAL {cand}: {len(sub)} reachable episodes | cats={cats} | periods={pers}")

    (DATA_DIR / "rss_corpus_manifest.json").write_text(json.dumps(clean, indent=2))
    print(f"Saved {DATA_DIR / 'rss_corpus_manifest.json'}")


if __name__ == "__main__":
    main()

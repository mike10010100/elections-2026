#!/usr/bin/env python3
"""Phase 1: Expand RSS corpus manifest with newly discovered 2026 interviews + fetch extra Rev.com transcripts."""

import json
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/state-name-analysis")
DATA_DIR = BASE_DIR / "data"
MANIFEST_PATH = DATA_DIR / "rss_corpus_manifest.json"
REV_EXTRA_PATH = DATA_DIR / "rev_extra_transcripts.json"

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


class PParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_p = False
        self.cur = []
        self.ps = []

    def handle_starttag(self, tag, attrs):
        if tag == "p":
            self.in_p = True
            self.cur = []

    def handle_endtag(self, tag):
        if tag == "p" and self.in_p:
            txt = " ".join("".join(self.cur).split())
            if txt:
                self.ps.append(txt)
            self.in_p = False

    def handle_data(self, data):
        if self.in_p:
            self.cur.append(data)


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", errors="ignore")


def check_range(url: str) -> int:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Range": "bytes=0-1023"})
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read(256)
        return r.status


def lookup_wjtv() -> tuple[str, int, str]:
    url = "https://itunes.apple.com/search?" + urllib.parse.urlencode(
        {"term": "Scott Colom WJTV", "media": "podcast", "entity": "podcastEpisode", "limit": 10}
    )
    res = json.loads(fetch_text(url))
    for ep in res.get("results", []):
        if "WJTV" in ep.get("collectionName", "") and "Mississippi Insight" in ep.get("trackName", ""):
            return (
                ep["episodeUrl"],
                int(ep.get("trackTimeMillis", 0) // 1000),
                ep.get("description", ""),
            )
    raise RuntimeError("Could not resolve WJTV episodeUrl from Apple Podcasts Search API")


def main():
    manifest = json.loads(MANIFEST_PATH.read_text())
    existing_ids = {x["episode_id"] for x in manifest}
    existing_urls = {x["audio_url"] for x in manifest}

    wjtv_url, wjtv_dur, wjtv_desc = lookup_wjtv()

    new_candidates = [
        # Scott Colom (6)
        {
            "episode_id": "colom_allin_20261111",
            "candidate": "scott_colom",
            "show": "All In with Chris Hayes",
            "title": "Trump’s Iran War Backlash and the Growing Democratic Blue Wave",
            "pub_date": "2026-11-11",
            "duration_sec": 2532,
            "category": "national_tv",
            "period": "post_election",
            "is_full_broadcast": True,
            "matched_venue": "all_in",
            "audio_url": "https://dts.podtrac.com/redirect.mp3/pdst.fm/e/injector.simplecastaudio.com/24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b/episodes/d163d2bf-f401-46bd-b318-2e663e037f53/audio/128/default.mp3?aid=rss_feed&awCollectionId=24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b&awEpisodeId=d163d2bf-f401-46bd-b318-2e663e037f53&feed=K5Wu8vub",
            "description": "November 10, 2026; 8pm: Ro Khanna, Ben Rhodes, Kabir Khanna, and Scott Colom join to discuss the political fallout.",
            "note": "All In with Chris Hayes Nov 11",
        },
        {
            "episode_id": "colom_allin_20261112",
            "candidate": "scott_colom",
            "show": "All In with Chris Hayes",
            "title": "Scott Colom’s Historic Mississippi Senate Win Reshapes the South",
            "pub_date": "2026-11-12",
            "duration_sec": 2943,
            "category": "national_tv",
            "period": "post_election",
            "is_full_broadcast": True,
            "matched_venue": "all_in",
            "audio_url": "https://dts.podtrac.com/redirect.mp3/pdst.fm/e/injector.simplecastaudio.com/24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b/episodes/cbd5c6b7-97c7-4b9f-8a81-02c51aac7e01/audio/128/default.mp3?aid=rss_feed&awCollectionId=24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b&awEpisodeId=cbd5c6b7-97c7-4b9f-8a81-02c51aac7e01&feed=K5Wu8vub",
            "description": "November 11, 2026; 8pm: Chris Hayes covers the AP call in Mississippi’s Senate race.",
            "note": "All In with Chris Hayes Nov 12",
        },
        {
            "episode_id": "colom_psaki_20261112",
            "candidate": "scott_colom",
            "show": "The Briefing with Jen Psaki",
            "title": "Scott Colom’s Mississippi Senate upset changes the political playbook in the South",
            "pub_date": "2026-11-12",
            "duration_sec": 2508,
            "category": "national_tv",
            "period": "post_election",
            "is_full_broadcast": True,
            "matched_venue": "jen_psaki",
            "audio_url": "https://dts.podtrac.com/redirect.mp3/injector.simplecastaudio.com/baa4ace2-8807-480d-a25a-3d9f92a5abf1/episodes/8b65fb79-12fe-4798-ae94-0e775152be82/audio/128/default.mp3?aid=rss_feed&awCollectionId=baa4ace2-8807-480d-a25a-3d9f92a5abf1&awEpisodeId=8b65fb79-12fe-4798-ae94-0e775152be82&feed=vA1gc2kQ",
            "description": "November 11, 2026; 9pm: Jen Psaki breaks down Democrat Scott Colom’s stunning Mississippi Senate victory.",
            "note": "Briefing with Jen Psaki Nov 12",
        },
        {
            "episode_id": "colom_ripdaniels_20260203",
            "candidate": "scott_colom",
            "show": "It's a New Day with Rip Daniels",
            "title": "It's a New Day: 2-3-26 Nationalizing Elections",
            "pub_date": "2026-02-03",
            "duration_sec": 8805,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://audioboom.com/posts/8856629.mp3?modified=1770161143&sid=5078295&source=rss",
            "description": "Exclusive interview with Senate Candidate and District Attorney Scott Colom.",
            "note": "Rip Daniels Feb 3",
        },
        {
            "episode_id": "colom_ripdaniels_20260115",
            "candidate": "scott_colom",
            "show": "It's a New Day with Rip Daniels",
            "title": "It's a New Day: 1-12-26 Senate Candidate Scott Colom",
            "pub_date": "2026-01-15",
            "duration_sec": 8839,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://audioboom.com/posts/8835084.mp3?modified=1768521551&sid=5078295&source=rss",
            "description": "Exclusive interview with Democratic Senate Candidate Scott Colom.",
            "note": "Rip Daniels Jan 15",
        },
        {
            "episode_id": "colom_wjtv_20260314",
            "candidate": "scott_colom",
            "show": "WJTV 12 Podcasts",
            "title": "Mississippi Insight for March 15, 2026",
            "pub_date": "2026-03-14",
            "duration_sec": wjtv_dur,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": False,
            "matched_venue": "",
            "audio_url": wjtv_url,
            "description": wjtv_desc[:400],
            "note": "WJTV Mississippi Insight Mar 14",
        },
        # Abdul El-Sayed (7)
        {
            "episode_id": "abdul_allin_20261006",
            "candidate": "abdul_el_sayed",
            "show": "All In with Chris Hayes",
            "title": "‘I DARE you’: El-Sayed says Trump is ‘too afraid’ to campaign in Michigan",
            "pub_date": "2026-10-06",
            "duration_sec": 2500,
            "category": "national_tv",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "all_in",
            "audio_url": "https://dts.podtrac.com/redirect.mp3/pdst.fm/e/injector.simplecastaudio.com/24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b/episodes/fad96186-d521-4ccf-a19f-be9b25ad2741/audio/128/default.mp3?aid=rss_feed&awCollectionId=24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b&awEpisodeId=fad96186-d521-4ccf-a19f-be9b25ad2741&feed=K5Wu8vub",
            "description": "Monday, October 5, 2026; 8pm: Chris Hayes interviews Dr. Abdul El-Sayed about his challenge to Donald Trump and the fight for Michigan.",
            "note": "All In with Chris Hayes Oct 6",
        },
        {
            "episode_id": "abdul_allin_20260806",
            "candidate": "abdul_el_sayed",
            "show": "All In with Chris Hayes",
            "title": "Abdul El-Sayed FIRES BACK at anti-Muslim attacks after Michigan win",
            "pub_date": "2026-08-06",
            "duration_sec": 2500,
            "category": "national_tv",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "all_in",
            "audio_url": "https://dts.podtrac.com/redirect.mp3/pdst.fm/e/injector.simplecastaudio.com/24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b/episodes/bc19f11d-b952-457c-8124-50a3e5b3608a/audio/128/default.mp3?aid=rss_feed&awCollectionId=24c4a3b6-ddfb-4d0f-8ec1-c3b138ade05b&awEpisodeId=bc19f11d-b952-457c-8124-50a3e5b3608a&feed=K5Wu8vub",
            "description": "Wednesday, August 5, 2026; 8pm: an interview with Abdul El-Sayed.",
            "note": "All In with Chris Hayes Aug 6",
        },
        {
            "episode_id": "abdul_thedig_20260514",
            "candidate": "abdul_el_sayed",
            "show": "The Dig",
            "title": "Primary Struggle w/ Abdul El-Sayed and other insurgent candidates",
            "pub_date": "2026-05-14",
            "duration_sec": 7337,
            "category": "national_longform",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://media.blubrry.com/thedig/content.blubrry.com/thedig/The_Dig-EP_526-El-Sayed.mp3",
            "description": "Featuring Michigan U.S. Senate candidate Abdul El-Sayed.",
            "note": "The Dig May 14",
        },
        {
            "episode_id": "abdul_stateside_20261112",
            "candidate": "abdul_el_sayed",
            "show": "Stateside On Air",
            "title": "Stateside: Thursday, Nov. 12, 2026",
            "pub_date": "2026-11-12",
            "duration_sec": 3000,
            "category": "local_in_state",
            "period": "post_election",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://cpa.ds.npr.org/s665/audio/2026/11/ss-20261112-full-show-thurs.mp3",
            "description": "Interviews with Rep.-elect Sean McCann and Senator-elect Abdul El-Sayed.",
            "note": "Stateside Nov 12",
        },
        {
            "episode_id": "abdul_stateside_20261023",
            "candidate": "abdul_el_sayed",
            "show": "Stateside On Air",
            "title": "Stateside: Friday, Oct. 23",
            "pub_date": "2026-10-23",
            "duration_sec": 3000,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://cpa.ds.npr.org/s665/audio/2026/10/ss-20261023-full-show-fri.mp3",
            "description": "Interviews with Abdul El-Sayed and Eli Savit.",
            "note": "Stateside Oct 23",
        },
        {
            "episode_id": "abdul_stateside_20260805",
            "candidate": "abdul_el_sayed",
            "show": "Stateside On Air",
            "title": "Stateside: Wednesday, Aug. 5, 2026",
            "pub_date": "2026-08-05",
            "duration_sec": 3000,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://cpa.ds.npr.org/s665/audio/2026/08/ss-20260805-full-show-wed.mp3",
            "description": "A conversation with Dr. Abdul El-Sayed after primary win.",
            "note": "Stateside Aug 5",
        },
        {
            "episode_id": "abdul_stateside_20260723",
            "candidate": "abdul_el_sayed",
            "show": "Stateside On Air",
            "title": "Stateside: Thursday, July 23, 2026",
            "pub_date": "2026-07-23",
            "duration_sec": 3000,
            "category": "local_in_state",
            "period": "campaign",
            "is_full_broadcast": True,
            "matched_venue": "",
            "audio_url": "https://cpa.ds.npr.org/s665/audio/2026/07/ss-20260723-full-show-thur.mp3",
            "description": "An interview with Michigan U.S. Senate candidate Abdul El-Sayed.",
            "note": "Stateside Jul 23",
        },
    ]

    added = 0
    for item in new_candidates:
        eid = item["episode_id"]
        if eid in existing_ids or item["audio_url"] in existing_urls:
            print(f"  [SKIP EXISTING] {eid}")
            continue
        try:
            st = check_range(item["audio_url"])
            item["http_check"] = st
            manifest.append(item)
            existing_ids.add(eid)
            existing_urls.add(item["audio_url"])
            added += 1
            print(f"  [ADDED HTTP {st}] {eid} ({item['show']} {item['pub_date']})")
        except Exception as e:
            print(f"  [HTTP ERR] {eid}: {e}")

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    print(f"Manifest updated: +{added} episodes -> total {len(manifest)}.")

    # Fetch 2 extra Rev.com transcripts
    rev_extra = {}
    for key, url, title, date_str in [
        (
            "abdul_detroit_forum",
            "https://www.rev.com/blog/transcripts/el-sayed-and-rogers-take-questions",
            "Detroit Economic Club Joint Q&A (Abdul El-Sayed & Mike Rogers)",
            "2026-10-21",
        ),
        (
            "abdul_primary_presser",
            "https://www.rev.com/blog/transcripts/abdul-el-sayed-wins-michigan-senate-primary",
            "Abdul El-Sayed Wins Michigan Senate Primary Press Conference",
            "2026-08-06",
        ),
    ]:
        html = fetch_text(url)
        pp = PParser()
        pp.feed(html)
        rev_extra[key] = {
            "url": url,
            "title": title,
            "pub_date": date_str,
            "paragraph_count": len(pp.ps),
            "paragraphs": pp.ps,
        }
        print(f"  [REV OK] {key}: {len(pp.ps)} paragraphs")

    REV_EXTRA_PATH.write_text(json.dumps(rev_extra, indent=2))
    print(f"Saved {REV_EXTRA_PATH}.")


if __name__ == "__main__":
    main()

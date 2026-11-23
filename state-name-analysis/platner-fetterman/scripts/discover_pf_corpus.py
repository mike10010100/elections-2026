#!/usr/bin/env python3
"""Step 1: Discover 2025-2026 RSS interview episodes for Graham Platner and John Fetterman."""

import html
import json
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

BASE_DIR = Path("/home/mike10010100/state-name-analysis/platner_fetterman")
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PodcastCorpusResearch/1.0)"}

SEED_SHOW_FEEDS = {
    "Morning Joe": "https://feeds.simplecast.com/5EFCkAYb",
    "Meet the Press": "https://podcastfeeds.nbcnews.com/yf3E6y7x",
    "The Source with Kaitlan Collins": "https://feeds.megaphone.fm/WMHY9548726236",
    "Anderson Cooper 360": "https://feeds.megaphone.fm/WMHY1640189360",
    "Erin Burnett OutFront": "https://feeds.megaphone.fm/WMHY3156145666",
    "State of the Union": "https://feeds.megaphone.fm/WMHY9982360035",
    "The Briefing with Jen Psaki": "https://feeds.simplecast.com/vA1gc2kQ",
    "All In with Chris Hayes": "https://feeds.simplecast.com/K5Wu8vub",
    "The Beat with Ari Melber": "https://feeds.simplecast.com/TA5rXVG0",
    "The Weekend MSNBC": "https://feeds.simplecast.com/0B62y4k7",
    "The Last Word with Lawrence O'Donnell": "https://feeds.simplecast.com/lQR7LFLn",
    "This Week with George Stephanopoulos": "https://feeds.megaphone.fm/ESP8760518499",
    "Face the Nation": "https://rss.amperwave.net/v2/feed/audacynetwork/1f7cbcf4fc75edeae6e4b9",
    "PBS News Hour - Full Show": "https://www.pbs.org/newshour/feeds/rss/podcasts/show",
    "The View": "https://feeds.megaphone.fm/ESP2875423997",
    "60 Minutes": "https://feeds.megaphone.fm/CBS5266692038",
}

SHOW_LOOKUPS = [
    "The Weekly Show with Jon Stewart",
    "All-In with Chamath, Jason, Sacks & Friedberg",
    "Club Random with Bill Maher",
    "Real Time with Bill Maher",
    "The Takeout with Major Garrett",
    "Honestly with Bari Weiss",
    "Next Question with Katie Couric",
    "Pod Save America",
    "The New Yorker Radio Hour",
    "Why Is This Happening Chris Hayes",
    "Death, Sex & Money",
    "Lever Time",
    "Mehdi Unfiltered",
    "Majority 54",
    "Up First NPR",
    "NPR Newsmakers",
    "Newsradio WGAN",
    "Maine Calling",
    "Maine Beacon",
    "The Smerconish Podcast",
    "Make It Make Sense Washington Post",
    "WHYY Studio 2",
    "The Ezra Klein Show",
    "The Run-Up New York Times",
    "Fresh Air NPR",
    "1A NPR",
    "Special Report with Bret Baier",
    "Fox News Sunday",
    "CNN NewsNight",
    "CNN Inside Politics",
    "On Point WBUR",
    "PoliticsNation",
    "Breaking Points",
    "The Bulwark Podcast",
    "The Lead with Jake Tapper",
    "The Gist Mike Pesca",
    "Left, Right & Center",
    "Pod Force One",
]

EPISODE_QUERIES = [
    ("graham_platner", "Graham Platner", "2025-08-01", "2026-08-05"),
    ("graham_platner", "Platner Maine Senate", "2025-08-01", "2026-08-05"),
    ("graham_platner", "Platner oyster Maine", "2025-08-01", "2026-08-05"),
    ("john_fetterman", "John Fetterman", "2025-01-01", "2026-11-23"),
    ("john_fetterman", "Senator John Fetterman", "2025-01-01", "2026-11-23"),
    ("john_fetterman", "Fetterman Pennsylvania Senate", "2025-01-01", "2026-11-23"),
]


def itunes_search(params: dict) -> list[dict]:
    try:
        r = requests.get("https://itunes.apple.com/search", params=params, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.json().get("results", [])
    except Exception as e:
        print(f"iTunes err {params}: {e}")
    return []


def parse_pub_date(raw: str) -> str:
    if not raw:
        return ""
    try:
        return parsedate_to_datetime(raw.strip()).strftime("%Y-%m-%d")
    except Exception:
        m = re.search(r"(\d{4}-\d{2}-\d{2})", raw)
        return m.group(1) if m else ""


def parse_dur_sec(raw: str) -> int:
    if not raw:
        return 0
    s = raw.strip()
    if s.isdigit():
        return int(s)
    parts = [int(p) for p in s.split(":") if p.isdigit()]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def match_candidate(title: str, desc: str, pub_date: str) -> list[str]:
    blob = f"{title} {desc}".lower()
    hits = []
    if ("platner" in blob) and ("graham platner" in blob or "maine" in blob or "senate" in blob or "oyster" in blob):
        if not pub_date or ("2025-08-01" <= pub_date <= "2026-08-15"):
            hits.append("graham_platner")
    if "fetterman" in blob:
        if not pub_date or ("2025-01-01" <= pub_date <= "2026-11-23"):
            hits.append("john_fetterman")
    return hits


def scan_feed(show_name: str, feed_url: str) -> list[dict]:
    out = []
    try:
        r = requests.get(feed_url, headers=HEADERS, timeout=25)
        if r.status_code != 200:
            return out
        root = ET.fromstring(r.content)
        ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
        chan = root.find("channel")
        if chan is None:
            return out
        chan_title = (chan.findtext("title") or show_name).strip()
        for item in chan.findall("item"):
            title = strip_html(item.findtext("title") or "")
            desc = strip_html(item.findtext("description") or "")
            pub_date = parse_pub_date(item.findtext("pubDate") or "")
            enc = item.find("enclosure")
            audio_url = enc.get("url", "").strip() if enc is not None else ""
            if not audio_url:
                continue
            cands = match_candidate(title, desc, pub_date)
            if not cands:
                continue
            dur_txt = item.findtext("itunes:duration", namespaces=ns) or ""
            for cand in cands:
                out.append({
                    "source": "rss_feed",
                    "candidate": cand,
                    "show": chan_title,
                    "feed_url": feed_url,
                    "title": title,
                    "pub_date": pub_date,
                    "duration_sec": parse_dur_sec(dur_txt),
                    "audio_url": audio_url,
                    "description": desc[:400],
                })
    except Exception as e:
        print(f"Feed err {show_name}: {e}")
    return out


def check_url(url: str) -> int:
    try:
        r = requests.get(url, headers={**HEADERS, "Range": "bytes=0-1024"}, timeout=15, allow_redirects=True, stream=True)
        code = r.status_code
        r.close()
        return code
    except Exception:
        return 0


def main():
    feed_map = dict(SEED_SHOW_FEEDS)
    for q in SHOW_LOOKUPS:
        for res in itunes_search({"term": q, "media": "podcast", "entity": "podcast", "limit": 4}):
            fu = res.get("feedUrl")
            cn = res.get("collectionName") or q
            if fu and fu not in feed_map.values():
                feed_map[cn] = fu
    print(f"Collected {len(feed_map)} podcast/broadcast feeds to scan.")

    all_hits = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(scan_feed, sn, fu): sn for sn, fu in feed_map.items()}
        for fut in as_completed(futs):
            all_hits.extend(fut.result())

    for cand, q, dmin, dmax in EPISODE_QUERIES:
        for res in itunes_search({"term": q, "media": "podcast", "entity": "podcastEpisode", "limit": 80}):
            eu = res.get("episodeUrl") or ""
            if not eu:
                continue
            pub_date = (res.get("releaseDate") or "")[:10]
            if pub_date and not (dmin <= pub_date <= dmax):
                continue
            title = (res.get("trackName") or "").strip()
            desc = strip_html(res.get("description") or "")
            if cand == "graham_platner" and "platner" not in f"{title} {desc}".lower():
                continue
            if cand == "john_fetterman" and "fetterman" not in f"{title} {desc}".lower():
                continue
            all_hits.append({
                "source": "itunes_episode",
                "candidate": cand,
                "show": (res.get("collectionName") or "").strip(),
                "feed_url": res.get("feedUrl", ""),
                "title": title,
                "pub_date": pub_date,
                "duration_sec": round((res.get("trackTimeMillis") or 0) / 1000),
                "audio_url": eu,
                "description": desc[:400],
            })

    # Deduplicate by (candidate, audio_url_base) & (candidate, show_norm, pub_date, title[:35])
    seen = set()
    dedup = []
    for h in all_hits:
        ubase = h["audio_url"].split("?")[0]
        key1 = (h["candidate"], ubase)
        key2 = (h["candidate"], re.sub(r"\W+", "", h["show"].lower()), h["pub_date"], re.sub(r"\W+", "", h["title"].lower())[:35])
        if key1 in seen or key2 in seen:
            continue
        seen.add(key1)
        seen.add(key2)
        dedup.append(h)

    dedup.sort(key=lambda x: (x["candidate"], x["pub_date"]), reverse=True)
    with ThreadPoolExecutor(max_workers=12) as ex:
        codes = list(ex.map(lambda x: check_url(x["audio_url"]), dedup))
    for h, c in zip(dedup, codes):
        h["http_check"] = c

    (DATA_DIR / "raw_candidates_pf.json").write_text(json.dumps(dedup, indent=2))
    lines = []
    for cand in ["graham_platner", "john_fetterman"]:
        sub = [x for x in dedup if x["candidate"] == cand]
        ok = [x for x in sub if x["http_check"] in (200, 206)]
        lines.append(f"=== {cand}: total_dedup={len(sub)}, http_ok={len(ok)} ===")
        for idx, x in enumerate(sub):
            dur_m = x["duration_sec"] / 60.0 if x["duration_sec"] else 0.0
            lines.append(f"  [{idx:02d}] HTTP={x['http_check']} | {x['pub_date']} | {dur_m:5.1f}m | {x['show']} | {x['title']} | DESC: {x['description'][:160]}")
    dump_txt = "\n".join(lines)
    (DATA_DIR / "_pf_discovery_dump.txt").write_text(dump_txt)
    print(f"Saved {len(dedup)} deduplicated candidates to raw_candidates_pf.json.")


if __name__ == "__main__":
    main()

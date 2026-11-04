#!/usr/bin/env python3
"""
Downloads all 2024-11-05 and 2026-11-03 election results from:
1. civicAPI (2024-11-05 and 2026-11-03)
2. The New York Times static JSON API (national + all 50 states & DC for both 2024-11-05 and 2026-11-03)
and builds unified race catalogs for 2024 vs 2026 comparisons.
"""
import concurrent.futures
import gzip
import json
import urllib.request
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/git/elections-2026/data")

STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
    "maine", "maryland", "massachusetts", "michigan", "minnesota",
    "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new-hampshire", "new-jersey", "new-mexico", "new-york",
    "north-carolina", "north-dakota", "ohio", "oklahoma", "oregon",
    "pennsylvania", "rhode-island", "south-carolina", "south-dakota",
    "tennessee", "texas", "utah", "vermont", "virginia", "washington",
    "west-virginia", "wisconsin", "wyoming", "washington-dc",
]

NATIONAL_2024 = ["results-president", "results-senate", "results-house", "results-governor", "results-abortion"]
NATIONAL_2026 = ["results-senate", "results-house", "results-governor"]


def fetch_url(url: str, dest: Path) -> tuple[str, bool, int]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Elections2026Tracker/1.0",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if resp.info().get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        data = json.loads(raw.decode("utf-8"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f)
        return (dest.name, True, len(data.get("races", [])))
    except Exception as e:
        return (dest.name, False, 0)


def download_nyt_cycle(date_str: str, folder_name: str, extra_slugs: list[str]):
    out_dir = BASE_DIR / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)
    slugs = list(extra_slugs) + [f"results-{s}" for s in STATES]

    tasks = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for slug in slugs:
            url = f"https://static01.nyt.com/elections-assets/pages/data/{date_str}/{slug}.json"
            dest = out_dir / f"{slug}.json"
            tasks.append(pool.submit(fetch_url, url, dest))

    all_races_by_id = {}
    ok_files = 0
    for fut in concurrent.futures.as_completed(tasks):
        name, ok, count = fut.result()
        if ok:
            ok_files += 1
            with open(out_dir / name, encoding="utf-8") as f:
                d = json.load(f)
            for r in d.get("races", []):
                nid = r.get("nyt_id")
                if nid:
                    # Keep the version with more reporting_units if duplicate across national/state files
                    existing = all_races_by_id.get(nid)
                    if not existing or len(r.get("reporting_units", [])) >= len(existing.get("reporting_units", [])):
                        all_races_by_id[nid] = r

    combined_path = BASE_DIR / f"{folder_name}_all_races.json.gz"
    with gzip.open(combined_path, "wt", encoding="utf-8") as f:
        json.dump(
            {
                "election_date": date_str,
                "count": len(all_races_by_id),
                "races": list(all_races_by_id.values()),
            },
            f,
        )
    print(
        f"[{folder_name}] Downloaded {ok_files}/{len(slugs)} files -> "
        f"{len(all_races_by_id):,} unique races saved to {combined_path.name}"
    )


if __name__ == "__main__":
    download_nyt_cycle("2024-11-05", "nyt_2024", NATIONAL_2024)
    download_nyt_cycle("2026-11-03", "nyt_2026", NATIONAL_2026)

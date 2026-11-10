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
import os
import re
import tempfile
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
        fd, tmp_path = tempfile.mkstemp(dir=str(dest.parent), prefix=f".{dest.name}.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, dest)
        return (dest.name, True, len(data.get("races", [])))
    except Exception as e:
        return (dest.name, False, 0)


def hydrate_house_district_counties(date_str: str, out_dir: Path) -> int:
    """
    Post-election week, NYT strips county-level reporting_units from national results-house.json
    and serves them at per-district endpoints (e.g. results-alabama-us-house-1.json).
    Caches per-district files in out_dir/house_districts/ (re-fetching only when updated_at changes)
    and stitches full county reporting_units back into results-house.json atomically.
    """
    house_path = out_dir / "results-house.json"
    if not house_path.exists():
        return 0

    with open(house_path, encoding="utf-8") as f:
        house_doc = json.load(f)

    races = house_doc.get("races", [])
    dist_dir = out_dir / "house_districts"
    dist_dir.mkdir(parents=True, exist_ok=True)

    to_fetch = []
    slug_by_idx = {}
    for idx, r in enumerate(races):
        if r.get("nyt_id", "").startswith("US-G-H-"):
            continue
        has_counties = any(u.get("level") == "county" for u in (r.get("reporting_units") or []))
        if has_counties:
            continue
        u = r.get("url") or ""
        m = re.search(r"/([^/]+)\.html$", u)
        if not m:
            continue
        d_slug = m.group(1)
        slug_by_idx[idx] = d_slug
        cache_file = dist_dir / f"{d_slug}.json"
        need_dl = True
        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as cf:
                    cdoc = json.load(cf)
                cr = (cdoc.get("races") or [{}])[0]
                if cr.get("updated_at") == r.get("updated_at") and cr.get("reporting_units"):
                    need_dl = False
            except Exception:
                need_dl = True
        if need_dl:
            url = f"https://static01.nyt.com/elections-assets/pages/data/{date_str}/{d_slug}.json"
            to_fetch.append((url, cache_file))

    if to_fetch:
        with concurrent.futures.ThreadPoolExecutor(max_workers=24) as pool:
            futs = [pool.submit(fetch_url, u, dest) for u, dest in to_fetch]
            for fut in concurrent.futures.as_completed(futs):
                fut.result()

    stitched = 0
    for idx, d_slug in slug_by_idx.items():
        cache_file = dist_dir / f"{d_slug}.json"
        if not cache_file.exists():
            continue
        try:
            with open(cache_file, encoding="utf-8") as cf:
                cdoc = json.load(cf)
            cr = (cdoc.get("races") or [None])[0]
            if cr and cr.get("reporting_units"):
                races[idx]["reporting_units"] = cr["reporting_units"]
                if cr.get("top_reporting_unit"):
                    races[idx]["top_reporting_unit"] = cr["top_reporting_unit"]
                stitched += 1
        except Exception:
            pass

    if stitched > 0:
        fd, tmp_path = tempfile.mkstemp(dir=str(out_dir), prefix=".results-house.json.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(house_doc, f)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, house_path)

    return stitched


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
        for fut in concurrent.futures.as_completed(tasks):
            fut.result()

    stitched_house = hydrate_house_district_counties(date_str, out_dir)

    all_races_by_id = {}
    ok_files = 0
    for slug in slugs:
        fpath = out_dir / f"{slug}.json"
        if fpath.exists():
            ok_files += 1
            with open(fpath, encoding="utf-8") as f:
                d = json.load(f)
            for r in d.get("races", []):
                nid = r.get("nyt_id")
                if nid:
                    existing = all_races_by_id.get(nid)
                    new_key = (len(r.get("reporting_units", [])), bool(r.get("historical_comparison_race_data")))
                    old_key = (len(existing.get("reporting_units", [])), bool(existing.get("historical_comparison_race_data"))) if existing else (-1, False)
                    if new_key > old_key:
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
        f"[{folder_name}] Downloaded {ok_files}/{len(slugs)} files "
        f"(hydrated {stitched_house} House district county feeds) -> "
        f"{len(all_races_by_id):,} unique races saved to {combined_path.name}"
    )


if __name__ == "__main__":
    download_nyt_cycle("2024-11-05", "nyt_2024", NATIONAL_2024)
    download_nyt_cycle("2026-11-03", "nyt_2026", NATIONAL_2026)

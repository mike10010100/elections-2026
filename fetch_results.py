#!/usr/bin/env python3
"""
Fetches the full 2026-11-03 election results dataset from civicAPI
and saves both a timestamped snapshot and data/latest.json.
"""
import datetime
import gzip
import json
import os
import shutil
import tempfile
import urllib.request
from pathlib import Path

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
LATEST_FILE = DATA_DIR / "latest.json"
LOG_FILE = DATA_DIR / "fetch.log"

URL = "https://civicapi.org/api/v2/race/search?startDate=2026-11-03&endDate=2026-11-03&limit=50000"


def fetch_snapshot() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    now = datetime.datetime.now(datetime.timezone.utc).astimezone()
    ts_str = now.strftime("%Y%m%d_%H%M%S")
    iso_str = now.isoformat()

    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Elections2026Tracker/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        raw_bytes = resp.read()
        if resp.info().get("Content-Encoding") == "gzip":
            raw_bytes = gzip.decompress(raw_bytes)

    payload = json.loads(raw_bytes.decode("utf-8"))
    races = payload.get("races", [])
    payload["fetched_at"] = iso_str

    # Write atomically to latest.json
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), prefix=".latest_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, LATEST_FILE)

    # Save compressed snapshot to save disk space over 5-min intervals
    snap_path = SNAPSHOT_DIR / f"races_{ts_str}.json.gz"
    with gzip.open(snap_path, "wt", encoding="utf-8") as gz:
        json.dump(payload, gz)

    called_count = sum(
        1 for r in races if any(c.get("winner") for c in (r.get("candidates") or []))
    )
    msg = (
        f"[{iso_str}] Fetched {len(races)} races "
        f"(called: {called_count}, uncalled: {len(races) - called_count}) "
        f"-> {LATEST_FILE.name} & {snap_path.name}"
    )
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(msg + "\n")

    return payload


if __name__ == "__main__":
    fetch_snapshot()
    try:
        from fetch_2024_and_2026_nyt import download_nyt_cycle, NATIONAL_2026
        download_nyt_cycle("2026-11-03", "nyt_2026", NATIONAL_2026)
    except Exception as e:
        print(f"Warning: NYT 2026 update failed: {e}")
    try:
        from build_site_data import build_all
        build_all()
    except Exception as e:
        print(f"Warning: build_site_data failed: {e}")
    # Auto-commit and push updated site_data to GitHub Pages ONLY if actual election results changed
    try:
        import subprocess
        # Check if county_shifts.json or states/ changed, or if overview.json changed outside fetched_at
        shifts_diff = subprocess.run(
            ["git", "-C", str(BASE_DIR), "diff", "--quiet", "site_data/county_shifts.json", "site_data/states"],
            check=False,
        )
        ov_diff_lines = subprocess.run(
            ["git", "-C", str(BASE_DIR), "diff", "-U0", "site_data/overview.json"],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.splitlines()
        meaningful_ov_diff = any(
            line.startswith(("+", "-"))
            and not line.startswith(("+++", "---"))
            and '"fetched_at"' not in line
            for line in ov_diff_lines
        )
        if shifts_diff.returncode != 0 or meaningful_ov_diff:
            subprocess.run(
                ["git", "-C", str(BASE_DIR), "add", "site_data/overview.json", "site_data/county_shifts.json", "site_data/states"],
                check=False,
            )
            diff_res = subprocess.run(
                ["git", "-C", str(BASE_DIR), "diff", "--cached", "--quiet"],
                check=False,
            )
            if diff_res.returncode != 0:
                subprocess.run(
                    ["git", "-C", str(BASE_DIR), "commit", "-m", "chore(data): auto-update live 2026 election results snapshot"],
                    check=False,
                )
                subprocess.run(
                    ["git", "-C", str(BASE_DIR), "push", "origin", "main"],
                    check=False,
                )
        else:
            # Revert timestamp-only change in overview.json so working tree stays clean
            subprocess.run(
                ["git", "-C", str(BASE_DIR), "checkout", "--", "site_data/overview.json"],
                check=False,
            )
    except Exception as e:
        print(f"Warning: git auto-push skipped: {e}")


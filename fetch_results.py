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
    races = sorted(payload.get("races", []), key=lambda r: r.get("id") or 0)
    payload["races"] = races
    payload["fetched_at"] = iso_str

    # Check if civicAPI races actually changed vs previous latest.json before writing another 3MB .json.gz snapshot
    races_changed = True
    if LATEST_FILE.exists():
        try:
            with open(LATEST_FILE, encoding="utf-8") as prev_f:
                prev_payload = json.load(prev_f)
            prev_sorted = sorted(prev_payload.get("races", []), key=lambda r: r.get("id") or 0)
            races_changed = (prev_sorted != races)
        except Exception:
            races_changed = True

    # Write atomically to latest.json
    fd, tmp_path = tempfile.mkstemp(dir=str(DATA_DIR), prefix=".latest_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.chmod(tmp_path, 0o644)
    os.replace(tmp_path, LATEST_FILE)

    snap_note = "unchanged (skipped duplicate archive)"
    if races_changed:
        snap_path = SNAPSHOT_DIR / f"races_{ts_str}.json.gz"
        with gzip.open(snap_path, "wt", encoding="utf-8") as gz:
            json.dump(payload, gz)
        snap_note = snap_path.name

    called_count = sum(
        1 for r in races if any(c.get("winner") for c in (r.get("candidates") or []))
    )
    msg = (
        f"[{iso_str}] Fetched {len(races)} races "
        f"(called: {called_count}, uncalled: {len(races) - called_count}) "
        f"-> {LATEST_FILE.name} & {snap_note}"
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
    # and no GitHub Pages build is currently in progress.
    try:
        import subprocess
        # Check if overview.json had actual vote/call changes (not just fetched_at)
        old_ov_proc = subprocess.run(
            ["git", "-C", str(BASE_DIR), "show", "HEAD:site_data/overview.json"],
            capture_output=True,
            text=True,
            check=False,
        )
        meaningful_change = False
        if old_ov_proc.returncode == 0 and old_ov_proc.stdout:
            old_ov = json.loads(old_ov_proc.stdout)
            new_ov = json.loads((BASE_DIR / "site_data" / "overview.json").read_text(encoding="utf-8"))
            old_ov.pop("fetched_at", None)
            new_ov.pop("fetched_at", None)
            meaningful_change = (old_ov != new_ov)

        if meaningful_change:
            venv_python = "/home/mike10010100/git/synology-drive-trays/.venv/bin/python"
            child_env = dict(
                os.environ,
                PATH=f"/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:{os.environ.get('PATH', '/usr/bin:/bin')}",
            )
            for script_name in [
                "build_fec_moneyball.py",
                "build_breaking_points.py",
                "build_analysis_charts.py",
                "build_rhetoric_vs_record.py",
                "build_texas_split_ticket.py",
                "build_texas_housing_edpol.py",
                "build_talarico_record_verification.py",
                "build_bonica_grumbach_panel_test.py",
            ]:
                try:
                    subprocess.run(
                        [venv_python, str(BASE_DIR / script_name)],
                        env=child_env,
                        check=False,
                    )
                except Exception as e:
                    print(f"Warning: {script_name} failed: {e}")

            subprocess.run(
                [
                    "git",
                    "-C",
                    str(BASE_DIR),
                    "add",
                    "site_data/overview.json",
                    "site_data/county_shifts.json",
                    "site_data/states",
                    "site_data/fec_moneyball_2026.json",
                    "site_data/fec_moneyball_senate_2026.csv",
                    "site_data/fec_moneyball_house_2026.csv",
                    "site_data/faction_analysis_2026.json",
                    "site_data/breaking_points_2026.json",
                    "site_data/rhetoric_vs_record_2026.json",
                    "site_data/rhetoric_vs_record_2026.csv",
                    "site_data/texas_split_ticket_2026.json",
                    "site_data/texas_housing_edpol_2026.json",
                    "site_data/texas_legislative_ideology_2019_2025.json",
                    "site_data/bonica_grumbach_methodology_test_2026.json",
                    "assets/chart1_house_carveout.png",
                    "assets/chart2_senate_0for6.png",
                    "assets/chart3_same_ballot_natural_experiment.png",
                    "assets/chart4_disjoint_cohorts_2018_vs_2026.png",
                    "assets/chart5_60pct_convergence_ceiling.png",
                    "assets/chart6_downballot_contagion.png",
                    "assets/chart7_senate_moneyball_counterspend.png",
                    "assets/chart8_rhetoric_vs_record_2026.png",
                    "assets/chart9_texas_split_ticket_2026.png",
                    "assets/chart10_texas_housing_edpol_2026.png",
                    "assets/chart11_talarico_baker_rollcall_record_2026.png",
                    "assets/chart12_bonica_grumbach_panel_test_2026.png",
                    "assets/chart13_economic_vs_cultural_moderation_2026.png",
                ],
                check=False,
            )
            diff_res = subprocess.run(
                ["git", "-C", str(BASE_DIR), "diff", "--cached", "--quiet"],
                check=False,
            )
            if diff_res.returncode != 0:
                subprocess.run(
                    ["git", "-C", str(BASE_DIR), "commit", "-m", "chore(data): auto-update live 2026 election results & analysis charts"],
                    check=False,
                )
                subprocess.run(
                    ["git", "-C", str(BASE_DIR), "push", "origin", "main"],
                    check=False,
                )
        else:
            # Revert timestamp-only updates in site_data so we don't trigger redundant Pages builds
            subprocess.run(
                ["git", "-C", str(BASE_DIR), "checkout", "--", "site_data/"],
                check=False,
            )
    except Exception as e:
        print(f"Warning: git auto-push skipped: {e}")


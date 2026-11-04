#!/usr/bin/env python3
"""
Analyzes called and uncalled federal races (US Senate and US House)
from data/latest.json, sorted by margin.
"""
import json
import collections
from pathlib import Path

LATEST_FILE = Path("/home/mike10010100/git/elections-2026/data/latest.json")
NATIONAL_ROLLUP_IDS = {87528, 87524}


def main():
    with open(LATEST_FILE, encoding="utf-8") as f:
        payload = json.load(f)

    races = payload.get("races", [])
    fetched_at = payload.get("fetched_at", "unknown")
    print(f"Dataset snapshot: {fetched_at} (Total races in file: {len(races):,})\n")

    for rtype in ["US Senate", "House of Representatives"]:
        sub = [
            r for r in races
            if r.get("type") == rtype and r.get("id") not in NATIONAL_ROLLUP_IDS
        ]
        called_party = collections.Counter()
        leading_party = collections.Counter()
        uncalled_list = []

        for r in sub:
            cands = sorted(
                r.get("candidates") or [],
                key=lambda c: c.get("votes", 0),
                reverse=True,
            )
            winners = [c for c in cands if c.get("winner")]
            if winners:
                called_party[winners[0].get("party", "Unknown")] += 1
            else:
                if cands:
                    leading_party[cands[0].get("party", "Unknown")] += 1
                if len(cands) >= 2:
                    m_pct = (cands[0].get("percent", 0) or 0) - (cands[1].get("percent", 0) or 0)
                    m_votes = (cands[0].get("votes", 0) or 0) - (cands[1].get("votes", 0) or 0)
                else:
                    m_pct = 100.0
                    m_votes = cands[0].get("votes", 0) if cands else 0
                uncalled_list.append((m_pct, m_votes, r, cands))

        uncalled_list.sort(key=lambda x: (x[0], x[1]))

        print(f"======================================================================")
        print(f" {rtype.upper()} ({len(sub)} seats on ballot)")
        print(f" Called: {sum(called_party.values())} {dict(called_party)}")
        print(f" Uncalled / Too Close to Call: {len(uncalled_list)} (Leading: {dict(leading_party)})")
        print(f"======================================================================")
        for m_pct, m_votes, r, cands in uncalled_list:
            c1 = cands[0] if len(cands) > 0 else {}
            c2 = cands[1] if len(cands) > 1 else {}
            loc = r.get("district") or r.get("province") or ""
            rep = r.get("percent_reporting", 0)
            print(
                f"  [{r.get('id')}] {loc:<8} | {rep:>3}% rep | "
                f"Margin: {m_pct:>5.2f}% ({m_votes:>7,}v) | "
                f"{c1.get('name')} ({str(c1.get('party',''))[:3]}) {c1.get('percent',0):.2f}% ({c1.get('votes',0):,}) vs. "
                f"{c2.get('name')} ({str(c2.get('party',''))[:3]}) {c2.get('percent',0):.2f}% ({c2.get('votes',0):,})"
            )
        print()


if __name__ == "__main__":
    main()

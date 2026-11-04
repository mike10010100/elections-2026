# 2026 U.S. Election Results & 2024 Shift Explorer

Live interactive election results explorer and county-by-county 2024 → 2026 shift arrow map, powered by 5-minute automated pulls from **civicAPI** (39,474 federal, state, and local races) and **NYT 2024/2026 county-level returns** (3,121 counties).

## Features

- **Google Search-Style Balance of Power & Race Cards**:
  - U.S. Senate (35 seats on ballot), U.S. House (435 seats), State Governors (36 seats), 90 State Legislative Chambers, 169 Statewide Ballot Measures, and all 39,474 down-ballot local races.
- **3 Interactive Map Modes**:
  1. **By winner**: State-level and county-level winner/margin choropleth map with diagonal hatching for uncalled races and flip badges.
  2. **Shift from 2024**: Directional arrow map (`↖ More Dem.` in blue, `↗ More Rep.` in red) comparing 2026 U.S. Senate, U.S. House, Governor, or Attorney General vote margins against the 2024 Presidential vote across every reporting county.
  3. **Live forecast**: Proportional uncounted-ballot bubble map and chamber model projections.

## Scripts

- `fetch_results.py`: Pulls the latest 39,474-race dataset from `civicapi.org` and updates the 2026 state/county files, rebuilds `site_data/`, and syncs changes every 5 minutes via cron.
- `fetch_2024_and_2026_nyt.py`: Downloads 2024-11-05 and 2026-11-03 national and 50-state+DC JSON feeds.
- `build_site_data.py`: Compiles `site_data/overview.json`, `site_data/county_shifts.json`, and `site_data/states/*.json`.
- `analyze_federal.py`: CLI report of called and uncalled ("too close to call") U.S. Senate and U.S. House races sorted by margin.

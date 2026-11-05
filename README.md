# 2026 U.S. Election Results, 2024 Shift Explorer & Comparative Faction Analysis

Live interactive election results explorer, county-by-county 2024 → 2026 shift arrow map, FEC Campaign Finance ("Moneyball") dataset, and Democratic faction comparative analysis, powered by **5-minute automated cron pulls** from **civicAPI** (39,474 federal, state, and local races), **NYT 2024/2026 county-level returns** (3,121 counties), and **FEC 2026 bulk campaign finance + independent expenditure disclosures**.

* **Live Interactive Map & Dashboard:** [https://mike10010100.github.io/elections-2026/](https://mike10010100.github.io/elections-2026/)

---

## Live-Updating Comparative Faction & Same-Ballot Charts

Every 5 minutes, when new election returns arrive, [`fetch_results.py`](fetch_results.py) rebuilds the site datasets and invokes [`build_analysis_charts.py`](build_analysis_charts.py) and [`build_fec_moneyball.py`](build_fec_moneyball.py) to regenerate the open-source datasets and charts below:

### 1. U.S. House Caucus Performance & The `DSA (n=7)` Carveout
![How DSA Beat the Average Was Manufactured in the U.S. House](assets/chart1_house_carveout.png)

### 2. U.S. Senate: `0-for-6` Progressive Record & Non-Linear GAM vs. Linear Slope
![In Morris's Own Senate Data, Progressive Nominees Went 0-for-6](assets/chart2_senate_0for6.png)

### 3. Same-Ballot Statewide Natural Experiment (`MI, MN, ME, NM, FL` — `276 of 286 Counties`)
![The Natural Experiment Morris Left Out: Same-Ballot Statewide Races](assets/chart3_same_ballot_natural_experiment.png)

---

## Open-Source Data Files (`site_data/`)

All processed JSON and CSV datasets are committed directly to [`site_data/`](site_data/) and updated automatically whenever live vote counts change:

* **[`site_data/overview.json`](site_data/overview.json):** Full national & state-by-state summary of 2026 U.S. Senate (35 seats), U.S. House (435 seats), Governors (36 seats), 139 Statewide Executive races (AG, SoS, Auditor, Treasurer), and 169 Ballot Measures, joined with 2004–2024 Presidential and same-office baselines.
* **[`site_data/county_shifts.json`](site_data/county_shifts.json):** County-by-county 2004–2026 vote margins and shifts across 3,121 counties (`s26`, `g26`, `h26`, `ag26`, `p24`, etc.).
* **[`site_data/faction_analysis_2026.json`](site_data/faction_analysis_2026.json):** Live-computed Senate-minus-House shifts, same-ballot statewide executive comparisons (`MI, MN, ME, NM, FL`), and county head-to-head tallies (`276/286 counties`).
* **[`site_data/fec_moneyball_2026.json`](site_data/fec_moneyball_2026.json) / [`fec_moneyball_senate_2026.csv`](site_data/fec_moneyball_senate_2026.csv) / [`fec_moneyball_house_2026.csv`](site_data/fec_moneyball_house_2026.csv):** Complete 2026 FEC candidate disbursements + Super PAC / Independent Expenditures (`support Dem + oppose GOP` vs. `support GOP + oppose Dem` counter-spend) joined with 2026 vote shifts and net votes shifted per dollar.
* **[`site_data/breaking_points_2026.json`](site_data/breaking_points_2026.json) & [`site_data/exit_polls_2026.json`](site_data/exit_polls_2026.json):** 2026 Exit Poll / AP Voter Poll / WaPo-Ipsos issue disapproval compilation (Iran war, tariffs, ICE/deportation overreach, White House East Wing ballroom, government corruption) joined with live 3,143-county disjoint-cohort shift comparisons (`2016→2018` vs. `2020→2024` vs. `2024→2026`) and federal-to-state down-ballot contagion metrics.

---

## Pipeline Scripts

* [`fetch_results.py`](fetch_results.py): Runs every 5 minutes via cron (`*/5 * * * *`), pulls the latest 39,474-race dataset from `civicapi.org` and NYT 2026 county feeds, rebuilds `site_data/` and `assets/`, and auto-commits/pushes to GitHub when returns update.
* [`fetch_2024_and_2026_nyt.py`](fetch_2024_and_2026_nyt.py): Downloads 2024-11-05 and 2026-11-03 national and 50-state+DC JSON feeds.
* [`build_site_data.py`](build_site_data.py): Compiles `site_data/overview.json`, `site_data/county_shifts.json`, and `site_data/states/*.json`.
* [`build_fec_moneyball.py`](build_fec_moneyball.py): Joins FEC `weball26.txt`, `cn.txt`, and `independent_expenditure_2026.csv` with 2026 election returns and computes candidate + Super PAC spend and counter-spend per point of swing.
* [`build_breaking_points.py`](build_breaking_points.py): Combines [`data/exit_polls_2026.json`](data/exit_polls_2026.json) with live county-cohort shifts and down-ballot contagion correlations into [`site_data/breaking_points_2026.json`](site_data/breaking_points_2026.json).
* [`build_analysis_charts.py`](build_analysis_charts.py): Computes live same-ballot and Senate-vs-House metrics from `overview.json` / `county_shifts.json`, writes `site_data/faction_analysis_2026.json`, and renders the three charts in `assets/`.
* [`analyze_federal.py`](analyze_federal.py): CLI report of called and uncalled U.S. Senate and U.S. House races sorted by margin.

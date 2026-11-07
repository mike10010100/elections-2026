# 2026 U.S. Election Results, 20-Year Historical Shift (2004–2026), Demographics & Moneyball Explorer

> ### **[Launch Live Interactive Dashboard → `https://mike10010100.github.io/elections-2026/`](https://mike10010100.github.io/elections-2026/)**

Live interactive election results explorer, county-by-county **2004 → 2026** shift arrow map, **U.S. Census ACS county demographic coalition analyzer**, **FEC Campaign Finance ("Moneyball")** dataset, and **Democratic faction / breaking-points comparative analysis**, powered by **15-minute automated cron pulls (`*/15 * * * *`)** from **civicAPI** (39,483 federal, state, and local races), **NYT 2024/2026 county-level returns** (3,152 counties/equivalents), **MIT/Heideman & FiveThirtyEight 2004–2024 historical archives**, and **FEC 2026 bulk campaign finance + independent expenditure disclosures**.

---

## Live Dashboard Views & Features (`index.html` / `app.js`)

* **9 Context-Aware Top-Level Tabs:**
  * **U.S. Senate (35 seats)**, **U.S. House (435 seats)**, & **Governors (36 seats):** Live chamber Balance of Power bars, 2026 → 2004–2024 county shift arrow map, By-Winner state/county choropleth, and Uncounted-Vote bubble forecast map.
  * **Demographics & 20-Yr History (2004–2026):** Apples-to-apples comparisons across 22 years of Presidential, Senate, and House cycles (`p24..p04`, `s26..s04`, `h26..h04`, `g26`, `ag26`, `top26`) broken down by U.S. Census county Urbanicity, College Education, Household Income, and Race/Ethnicity.
  * **Too Close to Call:** Isolates uncalled and razor-thin ($\le 2\%$) federal and gubernatorial races on the map and card explorer.
  * **Analysis & Moneyball (`FEC · RCV · Cohorts`):**
    1. **Mississippi Plurality Law (`Miss. Code Ann. § 23-15-605`) & Late-Ballot Tracker** + **Alaska RCV & Same-Name Spoiler Breakdown**
    2. **Interactive FEC Moneyball Explorer** (sortable/searchable Senate & House Candidate + Super PAC IE spend, counter-spend, and `$/pt` of shift)
    3. **Ideological Factions & 5-State Same-Ballot Natural Experiments** (`MI, MN, ME, NM, FL` — `276 of 286 counties`)
    4. **Disjoint Breaking Points & Cross-Ballot Contagion** (`3,143 counties`, demographic vs. cross-ballot PCA)
    5. **Live-Regenerated Research Charts Gallery (Charts 1–9)**
  * **Ballot Measures (169 statewide measures)** & **State Legislatures (90 chambers)**
  * **All 39,483 Races:** Searchable/filterable explorer across every federal, state, county, municipal, judicial, and school-board contest on the 2026 ballot.
* **Smart Map Context & Data Hygiene:** Greys out irrelevant/off-cycle states with a diagonal hatch pattern and explanatory legend/tooltips on every view; enforces strict deduplication for concurrent regular+special Senate races, ME/NE Congressional Districts, RCV Round 1 normalization, and NY/CT fusion ballot lines.

---

## Live-Updating Comparative Faction, Breaking-Points & Moneyball Charts (`assets/`)

Every 15 minutes, when new election returns arrive, [`fetch_results.py`](fetch_results.py) rebuilds the site datasets and invokes [`build_fec_moneyball.py`](build_fec_moneyball.py), [`build_breaking_points.py`](build_breaking_points.py), [`build_analysis_charts.py`](build_analysis_charts.py), [`build_rhetoric_vs_record.py`](build_rhetoric_vs_record.py), and [`build_texas_split_ticket.py`](build_texas_split_ticket.py) to regenerate the open-source datasets and all 9 charts below:

### 1. U.S. House Caucus Performance & The `DSA (n=7)` Carveout
![How DSA Beat the Average Was Manufactured in the U.S. House](assets/chart1_house_carveout.png)

### 2. U.S. Senate: `0-for-6` Progressive Record & Non-Linear GAM vs. Linear Slope
![In Morris's Own Senate Data, Progressive Nominees Went 0-for-6](assets/chart2_senate_0for6.png)

### 3. Same-Ballot Statewide Natural Experiment (`MI, MN, ME, NM, FL` — `276 of 286 Counties`)
![The Natural Experiment Morris Left Out: Same-Ballot Statewide Races](assets/chart3_same_ballot_natural_experiment.png)

### 4. Disjoint Breaking Points: 2018 Midterm vs. 2026 Midterm Shifts Across 8 County Cohorts
![Disjoint Breaking Points Cohort Comparison](assets/chart4_disjoint_cohorts_2018_vs_2026.png)

### 5. The 60% Disapproval Convergence Ceiling Across Issue Breaking Points
![60% Disapproval Convergence Ceiling](assets/chart5_60pct_convergence_ceiling.png)

### 6. Down-Ballot Contagion: U.S. Senate vs. State Attorney General County Shift (`r = 0.86`)
![Down-Ballot Contagion](assets/chart6_downballot_contagion.png)

### 7. 2026 Senate 'Moneyball': Diminishing Returns & Endogenous GOP Counterspend
![2026 Senate Moneyball & Endogenous GOP Counterspend](assets/chart7_senate_moneyball_counterspend.png)

### 8. Rhetoric vs. Record in 2026: Blinded LLM Campaign/Interview Rhetoric vs. Past Record (`N=49`)
![Rhetoric vs. Record in 2026](assets/chart8_rhetoric_vs_record_2026.png)

### 9. Anatomy of a 490,000-Vote Split Ticket: Talarico (+12.1%) vs. Hinojosa (+7.1%) in Texas (`254 Counties`)
![Anatomy of a 490,000-Vote Split Ticket in Texas](assets/chart9_texas_split_ticket_2026.png)

---

## Open-Source Data Files (`site_data/`)

All processed JSON and CSV datasets are committed directly to [`site_data/`](site_data/) and updated automatically whenever live vote counts change:

* **[`site_data/overview.json`](site_data/overview.json):** Full national & state-by-state summary of 2026 U.S. Senate (35 seats), U.S. House (435 seats), Governors (36 seats), 139 Statewide Executive races (AG, SoS, Auditor, Treasurer), 90 State Legislative chambers, and 169 Ballot Measures, joined with 2004–2024 Presidential and same-office baselines.
* **[`site_data/county_shifts.json`](site_data/county_shifts.json):** County-by-county 2004–2026 vote margins, two-party shifts, and U.S. Census ACS demographics across 3,152 counties/equivalents (`s26`, `g26`, `h26`, `ag26`, `top26`, `p24..p04`, `s24..s04`, `h24..h04`).
* **[`site_data/states/*.json`](site_data/states):** Per-state full race breakdowns across all 39,483 federal, state, and local contests.
* **[`site_data/faction_analysis_2026.json`](site_data/faction_analysis_2026.json):** Live-computed House caucus benchmark comparisons, Senate-minus-State-House shifts, same-ballot statewide executive comparisons (`MI, MN, ME, NM, FL`), and county head-to-head tallies (`276/286 counties`).
* **[`site_data/rhetoric_vs_record_2026.json`](site_data/rhetoric_vs_record_2026.json) / [`rhetoric_vs_record_2026.csv`](site_data/rhetoric_vs_record_2026.csv):** Multi-channel 2026 candidate campaign, interview, podcast, debate, and social rhetoric corpus scored blind via `opencode/deepseek-v4.1-flash-free` (`N=49` Senate, Governor, AG, and competitive House candidates), joined with Voteview DW-NOMINATE roll-call records, FEC ideological PAC IEs, and live 2026 vote returns across 4 Record × Rhetoric quadrants.
* **[`site_data/texas_split_ticket_2026.json`](site_data/texas_split_ticket_2026.json):** Complete 18-race Texas 2026 statewide ballot comparison and 254-county ticket-splitting decomposition between U.S. Senate (`James Talarico +12.10%` vs. `Ken Paxton`), Governor (`Gina Hinojosa +7.13%` vs. `Greg Abbott`), Attorney General (`Nathan Johnson +6.44%`), and Lt. Governor (`Vikki Goodwin +6.10%`), joined with U.S. Census ACS county demographics (`% BA+`, `% Hispanic`, `% White`, `% Black`, median income) and regional cohort summaries.
* **[`site_data/fec_moneyball_2026.json`](site_data/fec_moneyball_2026.json) / [`fec_moneyball_senate_2026.csv`](site_data/fec_moneyball_senate_2026.csv) / [`fec_moneyball_house_2026.csv`](site_data/fec_moneyball_house_2026.csv):** Complete 2026 FEC candidate disbursements + Super PAC / Independent Expenditures (`support Dem + oppose GOP` vs. `support GOP + oppose Dem` counter-spend) joined with 2026 vote shifts and marginal cost per shifted vote/point.
* **[`site_data/breaking_points_2026.json`](site_data/breaking_points_2026.json) & [`site_data/exit_polls_2026.json`](site_data/exit_polls_2026.json):** 2026 Exit Poll / AP Voter Poll / WaPo-Ipsos issue disapproval compilation joined with live 3,143-county disjoint-cohort shift comparisons (`2016→2018` vs. `2020→2024` vs. `2024→2026`), demographic & cross-ballot PCA decompositions, and federal-to-state down-ballot contagion metrics.

---

## Pipeline Scripts

* [`fetch_results.py`](fetch_results.py): Runs every 15 minutes via cron (`*/15 * * * *`), pulls the latest 39,483-race dataset from `civicapi.org` and NYT 2026 county feeds, rebuilds `site_data/` and `assets/chart1..chart9.png`, and auto-commits/pushes to GitHub only when actual vote counts or race calls change.
* [`fetch_2024_and_2026_nyt.py`](fetch_2024_and_2026_nyt.py): Atomically downloads 2024-11-05 and 2026-11-03 national and 50-state+DC JSON feeds.
* [`build_site_data.py`](build_site_data.py): Compiles and normalizes `site_data/overview.json`, `site_data/county_shifts.json`, and `site_data/states/*.json`.
* [`build_fec_moneyball.py`](build_fec_moneyball.py): Joins FEC `weball26.txt`, `cn.txt`, and `independent_expenditure_2026.csv` with 2026 election returns, outputs `site_data/fec_moneyball_2026.json` + CSVs, and renders `assets/chart7_senate_moneyball_counterspend.png`.
* [`build_rhetoric_vs_record.py`](build_rhetoric_vs_record.py): Scrapes multi-channel 2026 candidate campaign/interview/podcast/social rhetoric, scores blinded candidate dossiers via `opencode/deepseek-v4.1-flash-free`, joins with Voteview DW-NOMINATE and FEC PAC spending into `site_data/rhetoric_vs_record_2026.json` + `.csv`, and renders `assets/chart8_rhetoric_vs_record_2026.png`.
* [`build_texas_split_ticket.py`](build_texas_split_ticket.py): Joins 2026 Texas statewide and 254-county returns (`data/nyt_2026/results-texas.json`) with U.S. Census ACS demographics (`site_data/county_shifts.json`), outputs `site_data/texas_split_ticket_2026.json`, and renders `assets/chart9_texas_split_ticket_2026.png`.
* [`build_breaking_points.py`](build_breaking_points.py): Combines [`data/exit_polls_2026.json`](data/exit_polls_2026.json) with live county-cohort shifts, PCA decompositions, and down-ballot contagion correlations into [`site_data/breaking_points_2026.json`](site_data/breaking_points_2026.json), and renders `assets/chart4..chart6.png`.
* [`build_analysis_charts.py`](build_analysis_charts.py): Computes live same-ballot and Senate-vs-House metrics from `overview.json` / `county_shifts.json`, writes `site_data/faction_analysis_2026.json`, and renders `assets/chart1..chart3.png`.
* [`analyze_federal.py`](analyze_federal.py): CLI report of called and uncalled U.S. Senate and U.S. House races sorted by margin.

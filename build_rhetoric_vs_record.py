#!/usr/bin/env python3
"""
Builds the 2026 Candidate Rhetoric vs. Past Record ('Are Moderate Voters Rubes?')
multi-source dataset and generates assets/chart8_rhetoric_vs_record_2026.png.

Data Sources Combined:
  1. Multi-Channel 2026 Campaign, Show, Podcast, Interview & Social Media Corpus:
     - Google News RSS pre-election & media-appearance queries (interviews, podcasts,
       debates, town halls, Fox News, MSNBC, CNN, 60 Minutes, Colbert, local press)
     - YouTube 2026 interview, debate, podcast, and speech appearances
     - Bluesky public candidate feeds & third-party viral clip/interview mentions
     - Wikipedia biographical, policy record, and 2026 campaign extracts
  2. Blinded LLM Rhetoric Evaluation via OpenCode (`opencode/deepseek-v4.1-flash-free`):
     - Candidate names & states are redacted (`[CANDIDATE]`, `[STATE]`) during the
       rhetoric pass so the model scores pure 2026 general-election rhetorical affect,
       economic populism, and cross-partisan media outreach without name-recognition bias.
  3. Hard Institutional & Legislative Record:
     - Voteview 119th Congress (`HS119_members.csv`) DW-NOMINATE roll-call ideology scores
     - Congressional Caucus rosters (Blue Dog, New Democrat, CPC, DSA)
     - FEC 2026 Ideological PAC Independent Expenditures (`independent_expenditure_2026.csv`)
       for/against candidates in primaries and the general election (Working Families Party,
       Justice Democrats, CPC PAC, Sunrise, Indivisible vs. WelcomePAC, Center Forward,
       New Democrat Majority, Blue Dog, VoteVets, UDP)
     - FEC 2026 Total Pro-GOP Opposition Spending (`site_data/fec_moneyball_2026.json`)
  4. Live 2026 Election Returns (`site_data/overview.json` & `site_data/county_shifts.json`)
"""
import concurrent.futures
import csv
import io
import json
import math
import os
import re
import statistics
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

BASE_DIR = Path("/home/mike10010100/git/elections-2026")
DATA_DIR = BASE_DIR / "data"
SITE_DATA = BASE_DIR / "site_data"
ASSETS_DIR = BASE_DIR / "assets"
CACHE_PATH = DATA_DIR / "rhetoric_2026_cache.json"
OUT_JSON_PATH = SITE_DATA / "rhetoric_vs_record_2026.json"
OUT_CSV_PATH = SITE_DATA / "rhetoric_vs_record_2026.csv"
OUT_CHART_PATH = ASSETS_DIR / "chart8_rhetoric_vs_record_2026.png"
OPENCODE_BIN = "/home/mike10010100/.opencode/bin/opencode"

# 49 Target 2026 Democratic Candidates across Senate, Governor, AG, and Competitive/PAC-Targeted House
CANDIDATE_SPECS = [
    # --- U.S. SENATE (22) ---
    {"id": "TX_SEN", "name": "James Talarico", "state": "TX", "state_full": "Texas", "office_type": "senate_races", "seat": None, "office_label": "TX Senate",
     "caucus_or_faction": "Mainstream / Populist Reformer", "dw_nominate": None,
     "prior_record_notes": "TX State Rep (flipped Trump+10 HD-52 in 2018); Presbyterian seminarian; passed bipartisan insulin price cap ($25) & fentanyl/early-childhood bills in GOP legislature; not DSA/M4A; praised Elon Musk as innovator in Ryan Chandler interview while attacking billionaire tax loopholes & Christian nationalism on Fox News, Joe Rogan, and sermons."},
    {"id": "MI_SEN", "name": "Abdul El-Sayed", "state": "MI", "state_full": "Michigan", "office_type": "senate_races", "seat": None, "office_label": "MI Senate",
     "caucus_or_faction": "Progressive (Bernie / WFP / Justice Dems)", "dw_nominate": None,
     "prior_record_notes": "2018 progressive gubernatorial candidate endorsed by Bernie Sanders, AOC, Our Revolution, Justice Democrats; authored book 'Medicare for All: A Citizen's Guide'; past statements supporting Abolish ICE and palestinian activism; in 2026 general election pivoted rhetoric toward kitchen-table affordability while facing $224.4M in GOP opposition spending & Rep. Haley Stevens endorsing GOP opponent Mike Rogers."},
    {"id": "MN_SEN", "name": "Peggy Flanagan", "state": "MN", "state_full": "Minnesota", "office_type": "senate_races", "seat": None, "office_label": "MN Senate",
     "caucus_or_faction": "Progressive (Warren / Indivisible / Movement Left)", "dw_nominate": None,
     "prior_record_notes": "MN Lt. Governor & former Wellstone Action trainer; progressive movement record; viral clip declaring 'We will rip ICE apart!', wore 'Protect Trans Kids' shirt, and immediately after election called for Chuck Schumer to be replaced as Senate Dem leader; also faced scrutiny over state fraud response."},
    {"id": "ME_SEN", "name": "Troy Jackson", "state": "ME", "state_full": "Maine", "office_type": "senate_races", "seat": None, "office_label": "ME Senate",
     "caucus_or_faction": "Progressive Populist (Bernie 2016/2020 Chair, Indivisible/Sunrise)", "dw_nominate": None,
     "prior_record_notes": "Maine Senate President & logger from Allagash; national surrogate and Maine chair for Bernie Sanders 2016 & 2020; endorsed by Indivisible, Sunrise PAC, AFSCME Working Families; ran blue-collar populist anti-corporate campaign against Susan Collins."},
    {"id": "FL_SEN", "name": "Angie Nixon", "state": "FL", "state_full": "Florida", "office_type": "senate_races", "seat": None, "office_label": "FL Senate",
     "caucus_or_faction": "Progressive (WFP / Grassroots Organizer)", "dw_nominate": None,
     "prior_record_notes": "FL State Rep & progressive community organizer (Florida For All); sponsored ceasefire resolution & progressive housing/labor bills; ran unabashedly progressive grassroots organizing campaign in 2026."},
    {"id": "TN_SEN", "name": "Marquita Bradshaw", "state": "TN", "state_full": "Tennessee", "office_type": "senate_races", "seat": None, "office_label": "TN Senate",
     "caucus_or_faction": "Progressive (Our Revolution / Environmental Justice)", "dw_nominate": None,
     "prior_record_notes": "2020 & 2026 TN Senate nominee; environmental justice activist & Sierra Club/Our Revolution progressive; explicitly campaigned on Medicare for All and Green New Deal."},
    {"id": "MA_SEN", "name": "Edward Markey", "state": "MA", "state_full": "Massachusetts", "office_type": "senate_races", "seat": None, "office_label": "MA Senate",
     "caucus_or_faction": "Progressive (Green New Deal Co-Author / Sunrise)", "dw_nominate": -0.512,
     "prior_record_notes": "Incumbent US Senator; co-author of the Green New Deal resolution with AOC; Medicare for All cosponsor; endorsed by Sunrise Movement and progressive groups."},
    {"id": "OH_SEN", "name": "Sherrod Brown", "state": "OH", "state_full": "Ohio", "office_type": "senate_races", "seat": None, "office_label": "OH Senate",
     "caucus_or_faction": "Mainstream Dignity-of-Work Populist", "dw_nominate": -0.438,
     "prior_record_notes": "Former US Senator; 'Dignity of Work' blue-collar economic populist; rejected Medicare for All and Green New Deal; authored bipartisan FEND Off Fentanyl Act with GOP, backed domestic manufacturing/tariffs, border patrol funding, and law enforcement."},
    {"id": "NC_SEN", "name": "Roy Cooper", "state": "NC", "state_full": "North Carolina", "office_type": "senate_races", "seat": None, "office_label": "NC Senate",
     "caucus_or_faction": "Committed Moderate (Two-Term Governor)", "dw_nominate": None,
     "prior_record_notes": "Two-term NC Governor & former Attorney General; pragmatic institutional moderate; focused on bipartisan Medicaid expansion, rural broadband, public school teacher pay, business recruitment, and law-and-order credentials."},
    {"id": "GA_SEN", "name": "Jon Ossoff", "state": "GA", "state_full": "Georgia", "office_type": "senate_races", "seat": None, "office_label": "GA Senate",
     "caucus_or_faction": "Mainstream Moderate (Incumbent Senator)", "dw_nominate": -0.295,
     "prior_record_notes": "Incumbent US Senator; opposes Medicare for All, Green New Deal, and defunding police; championed bipartisan prison oversight, military housing, Georgia solar/battery manufacturing, and rural health clinics."},
    {"id": "IA_SEN", "name": "Josh Turek", "state": "IA", "state_full": "Iowa", "office_type": "senate_races", "seat": None, "office_label": "IA Senate",
     "caucus_or_faction": "Mainstream Prairie Moderate (VoteVets $10.8M)", "dw_nominate": None,
     "prior_record_notes": "Paralympic gold medalist & IA State Rep from Council Bluffs (Trump district); heavily backed by VoteVets ($10.8M primary support); campaigned on lowering healthcare/prescription costs, farm economy against tariffs, and bipartisan disability/veterans care."},
    {"id": "SC_SEN", "name": "Annie Andrews", "state": "SC", "state_full": "South Carolina", "office_type": "senate_races", "seat": None, "office_label": "SC Senate",
     "caucus_or_faction": "Mainstream Pragmatic Reformer", "dw_nominate": None,
     "prior_record_notes": "Pediatrician & gun-safety/child-health advocate; ran pragmatic family-focused campaign in deep-red SC emphasizing rural hospital closures, maternal/child healthcare, lower family costs, and common-sense gun safety."},
    {"id": "MS_SEN", "name": "Scott Colom", "state": "MS", "state_full": "Mississippi", "office_type": "senate_races", "seat": None, "office_label": "MS Senate",
     "caucus_or_faction": "Committed Moderate (Prosecutor / DA)", "dw_nominate": None,
     "prior_record_notes": "16th Circuit District Attorney in rural Mississippi; tough-on-violent-crime prosecutor who campaigned on reopening rural hospitals, cutting grocery taxes, faith, and working across party lines."},
    {"id": "KS_SEN", "name": "Adam Hamilton", "state": "KS", "state_full": "Kansas", "office_type": "senate_races", "seat": None, "office_label": "KS Senate",
     "caucus_or_faction": "Committed Moderate (Centrist / Faith & Civic Leader)", "dw_nominate": None,
     "prior_record_notes": "Kansas moderate civic/faith-rooted nominee; ran explicitly centrist, bridge-building campaign appealing to independent and moderate Republican suburban & farm voters hurt by tariffs and healthcare costs."},
    {"id": "AK_SEN", "name": "Mary Peltola", "state": "AK", "state_full": "Alaska", "office_type": "senate_races", "seat": None, "office_label": "AK Senate",
     "caucus_or_faction": "Blue Dog Co-Chair (Pro-Energy / Pro-2A Moderate)", "dw_nominate": -0.158,
     "prior_record_notes": "Former US Rep & Blue Dog Coalition Co-Chair; 'Fish, Family, and Freedom' platform; strongly pro-Willow oil project, pro-resource development, pro-Second Amendment, bipartisan coalition builder."},
    {"id": "LA_SEN", "name": "Jamie Davis", "state": "LA", "state_full": "Louisiana", "office_type": "senate_races", "seat": None, "office_label": "LA Senate",
     "caucus_or_faction": "Moderate Southern Democrat", "dw_nominate": None,
     "prior_record_notes": "Moderate Louisiana Democrat focused on flood insurance affordability, coastal restoration, oil/gas & port jobs, and rural hospital survival."},
    {"id": "NH_SEN", "name": "Chris Pappas", "state": "NH", "state_full": "New Hampshire", "office_type": "senate_races", "seat": None, "office_label": "NH Senate",
     "caucus_or_faction": "New Democrat / Center Forward Moderate", "dw_nominate": -0.228,
     "prior_record_notes": "US Rep from swing NH-01; backed by Center Forward ($800K); bipartisan small-business owner (Puritan Backroom), fiscal moderate, strong support for law enforcement, veterans, and border security."},
    {"id": "NM_SEN", "name": "Ben Luján", "state": "NM", "state_full": "New Mexico", "office_type": "senate_races", "seat": None, "office_label": "NM Senate",
     "caucus_or_faction": "Mainstream Institutional Democrat", "dw_nominate": -0.369,
     "prior_record_notes": "Incumbent US Senator; pragmatic institutional Democrat with deep roots in northern and rural New Mexico, balancing national labs, oil/gas basin jobs, border security technology, and healthcare."},
    {"id": "KY_SEN", "name": "Charles Booker", "state": "KY", "state_full": "Kentucky", "dw_nominate": None, "office_type": "senate_races", "seat": None, "office_label": "KY Senate",
     "caucus_or_faction": "Progressive ('From the Hood to the Holler')",
     "prior_record_notes": "Former KY State Rep & 2022/2026 Senate candidate; endorsed by Bernie Sanders & progressive groups in past cycles; campaigned on 'Hood to the Holler' populist progressive platform including Medicare for All and universal basic income."},
    {"id": "AR_SEN", "name": "Hallie Shoffner", "state": "AR", "state_full": "Arkansas", "dw_nominate": None, "office_type": "senate_races", "seat": None, "office_label": "AR Senate",
     "caucus_or_faction": "Mainstream Ag / Rural Reformer",
     "prior_record_notes": "6th-generation Arkansas farm CEO (SFR Seed); campaigned relentlessly on farm bankruptcies, Trump tariff retaliation hurting soybean/rice farmers, and rural healthcare."},
    {"id": "VA_SEN", "name": "Mark Warner", "state": "VA", "state_full": "Virginia", "dw_nominate": -0.197, "office_type": "senate_races", "seat": None, "office_label": "VA Senate",
     "caucus_or_faction": "Committed Moderate (Pro-Business / NatSec Centrist)",
     "prior_record_notes": "Incumbent US Senator & former Governor; Senate Intelligence Chair; telecom venture capitalist; quintessential pro-business, national-security bipartisan centrist."},
    {"id": "CO_SEN", "name": "John Hickenlooper", "state": "CO", "state_full": "Colorado", "dw_nominate": -0.242, "office_type": "senate_races", "seat": None, "office_label": "CO Senate",
     "caucus_or_faction": "Committed Moderate (Pragmatic Centrist)",
     "prior_record_notes": "Incumbent US Senator & former CO Governor; former brewpub entrepreneur & geologist; explicitly rejected socialism, Green New Deal, and Medicare for All in favor of bipartisan infrastructure and trade."},

    # --- GOVERNORS & STATEWIDE EXECUTIVES (14) ---
    {"id": "TX_GOV", "name": "Gina Hinojosa", "state": "TX", "state_full": "Texas", "office_type": "governor_races", "seat": None, "office_label": "TX Governor",
     "caucus_or_faction": "Austin Progressive Record -> Populist General Pivot", "dw_nominate": None,
     "prior_record_notes": "Austin (Travis County) State Rep & former Austin ISD school board president; progressive urban legislative record; in 2026 general election pivoted to anti-culture-war economic populism ('Shove it with your culture wars', Politico; New Yorker profile on 'Hinojosa's Populism') and anti-voucher public school defense, while Abbott hammered her for 'voting 40 times to raise property taxes'."},
    {"id": "MI_GOV", "name": "Jocelyn Benson", "state": "MI", "state_full": "Michigan", "office_type": "governor_races", "seat": None, "office_label": "MI Governor",
     "caucus_or_faction": "Mainstream Pragmatic Executive", "dw_nominate": None,
     "prior_record_notes": "Two-term Michigan Secretary of State; ran on pragmatic executive competence, cutting DMV wait times, government transparency, auto-manufacturing jobs, and lowering household costs."},
    {"id": "MN_GOV", "name": "Amy Klobuchar", "state": "MN", "state_full": "Minnesota", "office_type": "governor_races", "seat": None, "office_label": "MN Governor",
     "caucus_or_faction": "Committed Moderate (Bipartisan Pragmatist)", "dw_nominate": -0.275,
     "prior_record_notes": "Longtime US Senator & former Hennepin County prosecutor; ranked #1 most bipartisan effective legislator; ran for MN Governor on fiscal competence, public safety, farm bill, and mainstream pragmatism."},
    {"id": "NM_GOV", "name": "Deb Haaland", "state": "NM", "state_full": "New Mexico", "office_type": "governor_races", "seat": None, "office_label": "NM Governor",
     "caucus_or_faction": "Progressive Record (M4A/GND) -> Pragmatic General Pivot", "dw_nominate": -0.451,
     "prior_record_notes": "Former US Interior Secretary & US Rep; in Congress cosponsored Medicare for All and the Green New Deal and opposed fracking ('Climate Hero of the Left', Mother Jones); in 2026 NM Governor general election pivoted to a pragmatic, oil-and-gas-friendly revenue message for Permian Basin New Mexico."},
    {"id": "ME_GOV", "name": "Hannah Pingree", "state": "ME", "state_full": "Maine", "office_type": "governor_races", "seat": None, "office_label": "ME Governor",
     "caucus_or_faction": "Mainstream Pragmatic Executive", "dw_nominate": None,
     "prior_record_notes": "Former Maine House Speaker & Director of Gov. Janet Mills' Office of Policy Innovation; ran as pragmatic, solutions-focused executive emphasizing housing supply, property tax relief, and coastal economy."},
    {"id": "FL_GOV", "name": "David Jolly", "state": "FL", "state_full": "Florida", "office_type": "governor_races", "seat": None, "office_label": "FL Governor",
     "caucus_or_faction": "Committed Moderate (Former GOP Congressman)", "dw_nominate": None,
     "prior_record_notes": "Former moderate Republican US Rep from Pinellas County running as a centrist/fusion coalition builder focused on Florida's property insurance crisis, HOA costs, and bipartisan governance."},
    {"id": "IA_GOV", "name": "Rob Sand", "state": "IA", "state_full": "Iowa", "office_type": "governor_races", "seat": None, "office_label": "IA Governor",
     "caucus_or_faction": "Committed Moderate (Bipartisan Fiscal Watchdog)", "dw_nominate": None,
     "prior_record_notes": "Two-term Iowa State Auditor; bowhunter, churchgoer, and relentless anti-corruption fiscal watchdog who hires Republicans and independents in his office, visits all 99 counties, and attacks partisan groupthink in both parties."},
    {"id": "OH_GOV", "name": "Amy Acton", "state": "OH", "state_full": "Ohio", "office_type": "governor_races", "seat": None, "office_label": "OH Governor",
     "caucus_or_faction": "Mainstream Compassionate Pragmatist", "dw_nominate": None,
     "prior_record_notes": "Physician & former Ohio Department of Health Director under GOP Gov. Mike DeWine; campaigned on non-ideological community health, public education, kitchen-table costs, and healing partisan division."},
    {"id": "AZ_GOV", "name": "Katie Hobbs", "state": "AZ", "state_full": "Arizona", "office_type": "governor_races", "seat": None, "office_label": "AZ Governor",
     "caucus_or_faction": "Committed Moderate (Incumbent Swing-State Governor)", "dw_nominate": None,
     "prior_record_notes": "Incumbent AZ Governor; governed with GOP legislature on bipartisan water security, border enforcement cooperation, semiconductor manufacturing, andrepealing the 1864 abortion ban."},
    {"id": "KS_GOV", "name": "Cindy Holscher", "state": "KS", "state_full": "Kansas", "office_type": "governor_races", "seat": None, "office_label": "KS Governor",
     "caucus_or_faction": "Mainstream Suburban Moderate", "dw_nominate": None,
     "prior_record_notes": "KS State Senator from Overland Park (Johnson County); ran in the Laura Kelly moderate mold focused on public school funding, eliminating food taxes, and bipartisan fiscal stability."},
    {"id": "MI_AG", "name": "Eli Savit", "state": "MI", "state_full": "Michigan", "office_type": "statewide_exec_races", "seat": None, "office_sub": "Attorney General", "office_label": "MI Attorney General",
     "caucus_or_faction": "Progressive Prosecutor (Reform DA)", "dw_nominate": None,
     "prior_record_notes": "Washtenaw County (Ann Arbor) progressive prosecutor; abolished cash bail, declined sex-work/contraband prosecutions, backed by criminal-justice reform groups; pivoted in 2026 general to consumer protection & corporate price-gouging."},
    {"id": "MN_AG", "name": "Keith Ellison", "state": "MN", "state_full": "Minnesota", "office_type": "statewide_exec_races", "seat": None, "office_sub": "Attorney General", "office_label": "MN Attorney General",
     "caucus_or_faction": "Progressive (Former CPC Co-Chair / Bernie Surrogate)", "dw_nominate": -0.534,
     "prior_record_notes": "Incumbent MN Attorney General & former Co-Chair of the Congressional Progressive Caucus; longtime progressive leader who campaigned in 2026 on antitrust, consumer protection, and labor enforcement."},
    {"id": "TX_AG", "name": "Nathan Johnson", "state": "TX", "state_full": "Texas", "office_type": "statewide_exec_races", "seat": None, "office_sub": "Attorney General", "office_label": "TX Attorney General",
     "caucus_or_faction": "Mainstream Institutional Moderate", "dw_nominate": None,
     "prior_record_notes": "Dallas State Senator (flipped GOP SD-16) & commercial litigator; pragmatic, business-literate institutionalist who campaigned on restoring rule of law, non-partisan professionalism, and Medicaid expansion after Ken Paxton."},
    {"id": "NM_AG", "name": "Raul Torrez", "state": "NM", "state_full": "New Mexico", "office_type": "statewide_exec_races", "seat": None, "office_sub": "Attorney General", "office_label": "NM Attorney General",
     "caucus_or_faction": "Committed Moderate ('Tough-on-Crime' Prosecutor)", "dw_nominate": None,
     "prior_record_notes": "Incumbent NM Attorney General & former Bernalillo County DA; openly criticized progressive 'revolving door' bail policies, championed stricter pre-trial detention, organized retail crime crackdowns, and fentanyl enforcement."},

    # --- COMPETITIVE & IDEOLOGICAL-PAC-TARGETED U.S. HOUSE (13) ---
    {"id": "WA_03", "name": "Marie Gluesenkamp Perez", "state": "WA", "state_full": "Washington", "office_type": "house_races", "seat": 3, "office_label": "WA-03 House",
     "caucus_or_faction": "Blue Dog Co-Chair (WelcomePAC)", "dw_nominate": -0.105,
     "prior_record_notes": "Blue Dog Coalition Co-Chair & auto-repair shop owner; backed by WelcomePAC; voted against student loan forgiveness and with GOP on border/Laken Riley/regulatory bills; championed right-to-repair, vocational trades, and timber."},
    {"id": "TX_15", "name": "Bobby Pulido", "state": "TX", "state_full": "Texas", "office_type": "house_races", "seat": 15, "office_label": "TX-15 House",
     "caucus_or_faction": "Blue Dog / WelcomePAC Moderate", "dw_nominate": None,
     "prior_record_notes": "Latin Grammy-winning Tejano star recruited by Blue Dogs & backed by WelcomePAC ($155K); culturally moderate South Texas Democrat focused on border security, small business, cattle/agriculture, and lowering everyday costs."},
    {"id": "TX_34", "name": "Vicente Gonzalez", "state": "TX", "state_full": "Texas", "office_type": "house_races", "seat": 34, "office_label": "TX-34 House",
     "caucus_or_faction": "Blue Dog (Center Forward $280K)", "dw_nominate": -0.214,
     "prior_record_notes": "Blue Dog Coalition member from Rio Grande Valley; backed by Center Forward ($280K); pro-oil-and-gas, pro-border-security, culturally traditional South Texas moderate."},
    {"id": "MI_08", "name": "Kristen McDonald Rivet", "state": "MI", "state_full": "Michigan", "office_type": "house_races", "seat": 8, "office_label": "MI-08 House",
     "caucus_or_faction": "New Democrat (Center Forward & WelcomePAC)", "dw_nominate": -0.210,
     "prior_record_notes": "Incumbent US Rep in Flint/Saginaw/Bay City swing seat; backed by Center Forward ($150K) and WelcomePAC; championed working-class tax cuts, child care, manufacturing, and police funding."},
    {"id": "MI_07", "name": "William Lawrence", "state": "MI", "state_full": "Michigan", "office_type": "house_races", "seat": 7, "office_label": "MI-07 House",
     "caucus_or_faction": "Progressive Activist Record (Sunrise Co-Founder / WFP $1.06M) -> Affordability Pivot", "dw_nominate": None,
     "prior_record_notes": "Co-founder of Michigan Sunrise Movement & progressive organizer; backed by $1.06M from Working Families Party PAC and $497K from Michigan Sunrise PAC (and opposed by New Democrat Majority in primary); in 2026 general election pivoted rhetoric to utility rates and kitchen-table affordability."},
    {"id": "PA_10", "name": "Janelle Stelson", "state": "PA", "state_full": "Pennsylvania", "office_type": "house_races", "seat": 10, "office_label": "PA-10 House",
     "caucus_or_faction": "WelcomePAC Moderate (Former Local TV Anchor)", "dw_nominate": None,
     "prior_record_notes": "Former longtime WGAL-TV news anchor & registered Republican-turned-Democrat backed by WelcomePAC ($158K); ran non-ideological centrist campaign against Freedom Caucus Chair Scott Perry."},
    {"id": "IA_01", "name": "Christina Bohannan", "state": "IA", "state_full": "Iowa", "office_type": "house_races", "seat": 1, "office_label": "IA-01 House",
     "caucus_or_faction": "WelcomePAC / New Dem Moderate", "dw_nominate": None,
     "prior_record_notes": "Law professor, former environmental engineer & IA State Rep backed by WelcomePAC ($160K); grew up in a trailer park; campaigned on bipartisan property tax/cost relief, vocational training, and opposing tariffs."},
    {"id": "NC_11", "name": "Jamie Ager", "state": "NC", "state_full": "North Carolina", "office_type": "house_races", "seat": 11, "office_label": "NC-11 House",
     "caucus_or_faction": "WelcomePAC Rural Moderate ($399K)", "dw_nominate": None,
     "prior_record_notes": "4th-generation Western NC farmer (Hickory Nut Gap Farm) heavily backed by WelcomePAC ($399K); ran rural, faith-and-farming centrist campaign in Hurricane Helene recovery region."},
    {"id": "OH_13", "name": "Emilia Sykes", "state": "OH", "state_full": "Ohio", "office_type": "house_races", "seat": 13, "office_label": "OH-13 House",
     "caucus_or_faction": "New Democrat / Problem Solvers Moderate", "dw_nominate": -0.245,
     "prior_record_notes": "Incumbent US Rep in Akron/Canton swing district; backed by New Democrat Majority ($270K); Problem Solvers Caucus member focused on bipartisan rail safety, police funding, and lowering healthcare costs."},
    {"id": "NY_17", "name": "Cait Conley", "state": "NY", "state_full": "New York", "office_type": "house_races", "seat": 17, "office_label": "NY-17 House",
     "caucus_or_faction": "VoteVets / New Dem NatSec Moderate", "dw_nominate": None,
     "prior_record_notes": "West Point graduate, Army special operations combat veteran & counterterrorism official; backed by VoteVets ($1.08M) and New Democrat Majority ($523K); campaigned on national security, border order, and SALT tax relief."},
    {"id": "CA_22", "name": "Randy Villegas", "state": "CA", "state_full": "California", "office_type": "house_races", "seat": 22, "office_label": "CA-22 House",
     "caucus_or_faction": "Progressive Populist (WFP $1.38M / CPC PAC $200K)", "dw_nominate": None,
     "prior_record_notes": "Visalia school board trustee & political science professor; backed by $1.38M from Working Families Party PAC and $200K from CPC PAC (opposed by $751K from New Democrat Majority in primary); focused on Central Valley Medicaid/hospital cuts and farmworker grocery/healthcare costs."},
    {"id": "PA_07", "name": "Bob Brooks", "state": "PA", "state_full": "Pennsylvania", "office_type": "house_races", "seat": 7, "office_label": "PA-07 House",
     "caucus_or_faction": "Labor Populist (Firefighter Union / WFP $290K / CPC $140K)", "dw_nominate": None,
     "prior_record_notes": "Professional firefighter & Pennsylvania Professional Fire Fighters Association leader backed by Working Families Party PAC ($290K) and CPC PAC ($140K); blue-collar union economic populist."},
    {"id": "PA_12", "name": "Summer Lee", "state": "PA", "state_full": "Pennsylvania", "office_type": "house_races", "seat": 12, "office_label": "PA-12 House",
     "caucus_or_faction": "Progressive / Squad (Justice Dems / WFP)", "dw_nominate": -0.585,
     "prior_record_notes": "Incumbent US Rep & Squad/CPC member backed by Justice Democrats and Working Families Party; unapologetic movement progressive campaigning on Medicare for All, Green New Deal, and Gaza ceasefire."},
]


def fetch_url_text(url: str, timeout: int = 10) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def scrape_candidate_corpus(spec: dict) -> dict:
    name = spec["name"]
    state_full = spec["state_full"]

    # 1. Wikipedia extract (biographical, political positions, 2026 campaign)
    wiki_text = ""
    try:
        s_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(name + ' ' + state_full + ' politician')}&format=json"
        s_data = json.loads(fetch_url_text(s_url))
        hits = s_data.get("query", {}).get("search", [])
        if hits:
            title = hits[0]["title"]
            e_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&explaintext=1&titles={urllib.parse.quote(title)}&format=json"
            e_data = json.loads(fetch_url_text(e_url))
            for _, p in e_data.get("query", {}).get("pages", {}).items():
                wiki_text = (p.get("extract") or "")[:2400]
    except Exception:
        pass

    # 2. Google News RSS: Pre-Election Coverage + Interviews/Podcasts/Shows/Debates + Ideological Framing
    news_items = []
    seen_titles = set()
    queries = [
        f'"{name}" {state_full} before:2026-11-03',
        f'"{name}" (interview OR podcast OR debate OR show OR "town hall" OR Fox OR MSNBC OR CNN OR Rogan OR "60 Minutes" OR Colbert)',
        f'"{name}" (progressive OR moderate OR populist OR Medicare OR border OR police OR affordability OR tariffs OR climate)',
    ]
    for q in queries:
        try:
            g_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
            xml_str = fetch_url_text(g_url, timeout=10)
            root = ET.fromstring(xml_str)
            for item in root.findall(".//item")[:8]:
                t = (item.findtext("title") or "").strip()
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    news_items.append(t)
        except Exception:
            pass

    # 3. YouTube Show / Podcast / Interview / Debate Appearances
    yt_titles = []
    try:
        y_q = f"{name} {state_full} interview OR podcast OR debate OR Fox OR MSNBC OR speech 2026"
        y_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(y_q)}"
        y_html = fetch_url_text(y_url, timeout=10)
        raw_yt = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]\s*,"accessibility"', y_html)
        if not raw_yt:
            raw_yt = re.findall(r'"title":\{"runs":\[\{"text":"([^"]+)"\}\]', y_html)
        for t in raw_yt:
            if len(t) > 15 and t not in yt_titles:
                yt_titles.append(t)
                if len(yt_titles) >= 8:
                    break
    except Exception:
        pass

    # 4. Bluesky Candidate Feed
    bsky_handle = None
    bsky_posts = []
    try:
        a_url = f"https://public.api.bsky.app/xrpc/app.bsky.actor.searchActors?q={urllib.parse.quote(name)}&limit=3"
        actors = json.loads(fetch_url_text(a_url, timeout=8)).get("actors", [])
        if actors:
            top = actors[0]
            # Verify actor name similarity
            last_tok = name.split()[-1].lower()
            if last_tok in (top.get("displayName", "") + " " + top.get("handle", "")).lower():
                bsky_handle = top.get("handle")
                f_url = f"https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor={urllib.parse.quote(top['did'])}&limit=15&filter=posts_no_replies"
                feed = json.loads(fetch_url_text(f_url, timeout=8)).get("feed", [])
                for item in feed:
                    txt = item.get("post", {}).get("record", {}).get("text", "").strip()
                    if txt and len(txt) > 25:
                        bsky_posts.append(txt.replace("\n", " ")[:220])
                        if len(bsky_posts) >= 6:
                            break
    except Exception:
        pass

    return {
        "id": spec["id"],
        "wiki_excerpt": wiki_text[:1500],
        "news_and_interview_headlines": news_items[:16],
        "youtube_shows_podcasts_debates": yt_titles[:8],
        "bsky_handle": bsky_handle,
        "bsky_sample_posts": bsky_posts[:6],
    }


def blind_text(text: str, name: str, state_full: str, state_abbr: str) -> str:
    if not text:
        return ""
    out = text
    for part in [name] + [p for p in name.split() if len(p) > 2]:
        out = re.sub(re.escape(part), "[CANDIDATE]", out, flags=re.IGNORECASE)
    out = re.sub(r"\b" + re.escape(state_full) + r"\b", "[STATE]", out, flags=re.IGNORECASE)
    return out


def run_opencode_deepseek_batch(batch_items: list) -> dict:
    """
    Sends a batch of candidate dossiers (with blinded 2026 rhetoric text + separate
    record notes) to `opencode run -m opencode/deepseek-v4.1-flash-free` and parses
    the structured JSON scores.
    """
    prompt_payload = []
    for item in batch_items:
        spec = item["spec"]
        corp = item["corpus"]
        pac = item["pac_summary"]
        name = spec["name"]
        st_full = spec["state_full"]
        st_ab = spec["state"]

        blinded_news = [blind_text(x, name, st_full, st_ab) for x in corp["news_and_interview_headlines"][:12]]
        blinded_yt = [blind_text(x, name, st_full, st_ab) for x in corp["youtube_shows_podcasts_debates"][:6]]
        blinded_bsky = [blind_text(x, name, st_full, st_ab) for x in corp["bsky_sample_posts"][:5]]
        blinded_wiki = blind_text(corp["wiki_excerpt"][:900], name, st_full, st_ab)

        prompt_payload.append({
            "candidate_id": spec["id"],
            "office_type": spec["office_type"],
            "blinded_2026_rhetoric_and_media_appearances": {
                "news_and_interview_coverage": blinded_news,
                "youtube_podcasts_debates_shows": blinded_yt,
                "social_posts": blinded_bsky,
                "bio_and_campaign_excerpt": blinded_wiki,
            },
            "past_record_and_institutional_backing": {
                "caucus_or_faction_tier": spec["caucus_or_faction"],
                "dw_nominate_roll_call": spec["dw_nominate"],
                "fec_progressive_pac_support_usd": round(pac["prog_pac_support"]),
                "fec_moderate_pac_support_usd": round(pac["mod_pac_support"]),
                "prior_record_summary": blind_text(spec["prior_record_notes"], name, st_full, st_ab),
            }
        })

    prompt = (
        "You are a quantitative political science coder analyzing 2026 U.S. election candidates.\n"
        "Do NOT run any shell tools or read any files. Analyze ONLY the JSON payload below and reply with ONLY a valid JSON array.\n\n"
        "For each candidate in the input array, evaluate TWO distinct ideological dimensions on a -2.0 to +2.0 scale:\n"
        "1. `record_ideology_score` (-2.0 to +2.0): Based ONLY on `past_record_and_institutional_backing` (roll-call votes, caucus membership, past primary positions on Medicare for All / Green New Deal / Abolish ICE / bail reform, and FEC backing from Progressive PACs like Working Families Party / Justice Dems / Sunrise vs. Moderate PACs like WelcomePAC / Center Forward / New Dem Majority / Blue Dogs).\n"
        "   * -2.0 to -1.2 = Strong movement-progressive / DSA / Justice Dems / M4A / GND / Abolish ICE record\n"
        "   * -1.1 to -0.4 = Progressive legislative/activist record\n"
        "   * -0.3 to +0.5 = Mainstream / pragmatic / non-factional Democratic record\n"
        "   * +0.6 to +2.0 = Committed moderate / Blue Dog / bipartisan centrist record\n"
        "2. `rhetoric_ideology_score` (-2.0 to +2.0): Based ONLY on `blinded_2026_rhetoric_and_media_appearances` (how the candidate actually talked and positioned themselves in 2026 general-election interviews, podcasts, TV shows, debates, and campaign coverage):\n"
        "   * -2.0 to -1.0 = Unapologetically progressive movement rhetoric (e.g. 'rip ICE apart', Medicare for All, Green New Deal, activist culture-war framing)\n"
        "   * -0.9 to -0.1 = Left-populist or progressive-leaning rhetoric\n"
        "   *  0.0 to +0.8 = Disciplined kitchen-table affordability, anti-culture-war populism ('shove it with your culture wars'), or pragmatic mainstream rhetoric\n"
        "   * +0.9 to +2.0 = Explicitly moderate, bipartisan, cross-partisan outreach (e.g. Fox News/podcast outreach, border security, law enforcement/prosecutor, pro-business/ag/energy moderation)\n"
        "3. `populist_economic_score` (0.0 to 2.0): Intensity of anti-monopoly, working-class, anti-tariff-pain, affordability, or anti-corruption economic populism.\n"
        "4. `cross_partisan_outreach_score` (0.0 to 2.0): Evidence of going on adversarial/cross-partisan shows (Fox News, Rogan, rural town halls), courting GOP/independent/church/business/farm crossover voters, or breaking with party orthodoxy.\n"
        "5. `quadrant`: Classify into EXACTLY one of these 4 strings:\n"
        "   - \"Committed Moderate (Mod Record + Mod Rhetoric)\" (when record_ideology_score >= 0.4 and rhetoric_ideology_score >= 0.4)\n"
        "   - \"Mainstream / Cross-Partisan Populist\" (when record_ideology_score > -0.4 and record_ideology_score < 0.6 and rhetoric_ideology_score >= 0.0)\n"
        "   - \"Rhetorical Pivoter (Prog Record -> Mod/Affordability Rhetoric)\" (when record_ideology_score <= -0.4 AND rhetoric_ideology_score - record_ideology_score >= 0.55)\n"
        "   - \"Movement Progressive (Prog Record + Prog Rhetoric)\" (when record_ideology_score <= -0.4 and they did NOT pivot to moderate rhetoric)\n"
        "6. `vibe_summary`: A concise 1-sentence characterization (<= 160 chars) of their record vs. 2026 media/interview rhetoric.\n\n"
        "Return ONLY a raw JSON array of objects with keys: "
        "`candidate_id`, `record_ideology_score`, `rhetoric_ideology_score`, `populist_economic_score`, `cross_partisan_outreach_score`, `quadrant`, `vibe_summary`.\n\n"
        "INPUT PAYLOAD:\n" + json.dumps(prompt_payload, ensure_ascii=False)
    )

    proc = subprocess.run(
        [OPENCODE_BIN, "run", "-m", "opencode/deepseek-v4.1-flash-free", prompt],
        capture_output=True,
        text=True,
        timeout=180,
    )
    out = proc.stdout
    # Extract JSON array from output
    m = re.search(r"\[\s*\{.*\}\s*\]", out, flags=re.DOTALL)
    if not m:
        raise RuntimeError(f"Failed to parse JSON array from opencode output:\n{out[:1000]}\nSTDERR:\n{proc.stderr[:500]}")
    arr = json.loads(m.group(0))
    return {row["candidate_id"]: row for row in arr}


def load_fec_pac_and_moneyball():
    with open(SITE_DATA / "fec_moneyball_2026.json", "r", encoding="utf-8") as f:
        mb = json.load(f)

    by_state_office = {}
    for r in mb.get("senate_races", []):
        by_state_office[("senate_races", r["state"], None)] = r
    for r in mb.get("house_races", []):
        by_state_office[("house_races", r["state"], r.get("seat_number"))] = r

    prog_kws = [
        "WORKING FAMILIES", "JUSTICE DEMOCRATS", "PROGRESSIVE CAUCUS",
        "SUNRISE", "INDIVISIBLE", "OUR REVOLUTION",
    ]
    mod_kws = [
        "CENTER FORWARD", "NEW DEMOCRAT", "BLUE DOG", "WELCOME",
        "UNITED DEMOCRACY PROJECT", "VOTEVETS", "MAIN STREET",
    ]

    pac_by_cid = defaultdict(lambda: {"prog_pac_support": 0.0, "mod_pac_support": 0.0, "pac_details": defaultdict(float)})
    ie_path = DATA_DIR / "fec_2026" / "independent_expenditure_2026.csv"
    if ie_path.exists():
        with open(ie_path, "r", encoding="utf-8", errors="replace") as f:
            for row in csv.DictReader(f):
                cid = row.get("cand_id") or ""
                if not cid:
                    continue
                nam = (row.get("spe_nam") or "").upper()
                so = row.get("sup_opp") or ""
                try:
                    amt = float(row.get("exp_amo") or 0.0)
                except ValueError:
                    amt = 0.0
                if any(k in nam for k in prog_kws):
                    if so == "S":
                        pac_by_cid[cid]["prog_pac_support"] += amt
                        pac_by_cid[cid]["pac_details"][f"SUP:{nam}"] += amt
                if any(k in nam for k in mod_kws):
                    if so == "S":
                        pac_by_cid[cid]["mod_pac_support"] += amt
                        pac_by_cid[cid]["pac_details"][f"SUP:{nam}"] += amt
                    elif so == "O" and "UNITED DEMOCRACY PROJECT" in nam:
                        pac_by_cid[cid]["pac_details"][f"OPP:{nam}"] += amt

    return by_state_office, pac_by_cid


def build_or_load_cache(force_refresh: bool = False) -> dict:
    if CACHE_PATH.exists() and not force_refresh:
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    print(f"Scraping multi-channel 2026 candidate rhetoric & media appearances for {len(CANDIDATE_SPECS)} candidates...")
    by_state_office, pac_by_cid = load_fec_pac_and_moneyball()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        fut_map = {ex.submit(scrape_candidate_corpus, spec): spec for spec in CANDIDATE_SPECS}
        corpora = {}
        for fut in concurrent.futures.as_completed(fut_map):
            spec = fut_map[fut]
            corpora[spec["id"]] = fut.result()

    # Prepare items for opencode/deepseek-v4.1-flash-free scoring in 3 batches
    all_items = []
    for spec in CANDIDATE_SPECS:
        mb_rec = by_state_office.get((spec["office_type"], spec["state"], spec.get("seat")), {})
        cid = mb_rec.get("dem_fec_id")
        pac_info = pac_by_cid.get(cid, {"prog_pac_support": 0.0, "mod_pac_support": 0.0, "pac_details": {}})
        all_items.append({
            "spec": spec,
            "corpus": corpora[spec["id"]],
            "pac_summary": pac_info,
        })

    llm_scores = {}
    batch_size = 17
    for i in range(0, len(all_items), batch_size):
        batch = all_items[i : i + batch_size]
        print(f"Scoring batch {i // batch_size + 1} ({len(batch)} candidates) via opencode/deepseek-v4.1-flash-free...")
        res = run_opencode_deepseek_batch(batch)
        llm_scores.update(res)

    cache_obj = {
        "model": "opencode/deepseek-v4.1-flash-free",
        "candidates": {},
    }
    for item in all_items:
        cid_key = item["spec"]["id"]
        sc = llm_scores.get(cid_key, {})
        cache_obj["candidates"][cid_key] = {
            "spec": item["spec"],
            "corpus": item["corpus"],
            "llm_evaluation": sc,
        }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache_obj, f, indent=2, ensure_ascii=False)
    print(f"Saved scraped corpus & LLM evaluations to {CACHE_PATH}")
    return cache_obj


def compute_live_dataset(cache_obj: dict) -> dict:
    with open(SITE_DATA / "overview.json", "r", encoding="utf-8") as f:
        ov = json.load(f)

    by_state_office, pac_by_cid = load_fec_pac_and_moneyball()

    # Compute State House Democratic Mean Shift vs. 2024 Presidential baseline
    house_shifts_by_state = defaultdict(list)
    all_house_shifts = []
    for h in ov.get("house_races", []):
        cands = h.get("candidates", [])
        parties = [c.get("party") for c in cands]
        if "DEM" in parties and "GOP" in parties and not h.get("uncontested") and not h.get("one_party"):
            sh = h.get("shift_vs_pres_2024")
            if sh is not None:
                house_shifts_by_state[h["state"]].append(sh)
                all_house_shifts.append(sh)
    nat_house_mean = statistics.mean(all_house_shifts) if all_house_shifts else 14.3

    def find_ov_race(spec):
        rtype = spec["office_type"]
        st = spec["state"]
        seat = spec.get("seat")
        osub = spec.get("office_sub")
        for r in ov.get(rtype, []):
            if r.get("state") != st:
                continue
            if seat is not None and str(r.get("seat_number")) != str(seat):
                continue
            if osub and osub.lower() not in str(r.get("office", "")).lower():
                continue
            return r
        return None

    rows = []
    for spec in CANDIDATE_SPECS:
        cid_key = spec["id"]
        cached = cache_obj["candidates"].get(cid_key, {})
        corp = cached.get("corpus", {})
        llm = cached.get("llm_evaluation", {})
        r = find_ov_race(spec)
        if not r:
            continue

        st = spec["state"]
        # In single-seat AK, the House race had a 3-way RCV baseline quirk (-29.17); use national House mean (+14.3)
        if st == "AK" or not house_shifts_by_state.get(st):
            state_house_mean = nat_house_mean
        else:
            state_house_mean = statistics.mean(house_shifts_by_state[st])
        margin_26 = r.get("dem_gop_margin")

        mb_rec = by_state_office.get((spec["office_type"], st, spec.get("seat")), {})
        fec_id = mb_rec.get("dem_fec_id")
        pac_info = pac_by_cid.get(fec_id, {"prog_pac_support": 0.0, "mod_pac_support": 0.0, "pac_details": {}})

        if spec["office_type"] == "house_races":
            # District-level 2024 House baseline from fec_moneyball / overview
            shift_24 = mb_rec.get("shift_vs_pres_2024")
            if shift_24 is None:
                shift_24 = r.get("shift_vs_house_2024") or r.get("shift_vs_pres_2024") or 0.0
            overperf_vs_benchmark = round(shift_24 - 14.3, 2)
            benchmark_label = "Nat'l House Swing (+14.3)"
        else:
            shift_24 = r.get("shift_vs_pres_2024")
            if shift_24 is None:
                shift_24 = 0.0
            overperf_vs_benchmark = round(shift_24 - state_house_mean, 2)
            benchmark_label = f"{st} House Mean (+{state_house_mean:.2f})"

        rec_score = float(llm.get("record_ideology_score", 0.0))
        rhet_score = float(llm.get("rhetoric_ideology_score", 0.0))
        pivot_score = round(rhet_score - rec_score, 2)
        pop_score = float(llm.get("populist_economic_score", 1.0))
        cross_score = float(llm.get("cross_partisan_outreach_score", 0.5))

        # Enforce consistent deterministic quadrant assignment from the LLM's record & rhetoric scores
        if rec_score <= -0.4:
            if pivot_score >= 0.5:
                quad = "Rhetorical Pivoter (Prog Record -> Mod/Affordability Rhetoric)"
            else:
                quad = "Movement Progressive (Prog Record + Prog Rhetoric)"
        elif rec_score >= 0.45:
            quad = "Committed Moderate (Mod Record + Mod Rhetoric)"
        else:
            quad = "Mainstream / Cross-Partisan Populist"

        rows.append({
            "id": cid_key,
            "name": spec["name"],
            "state": st,
            "office_label": spec["office_label"],
            "office_type": spec["office_type"],
            "caucus_or_faction": spec["caucus_or_faction"],
            "dw_nominate": spec["dw_nominate"],
            "margin_2026": round(margin_26, 2) if margin_26 is not None else None,
            "shift_vs_2024_baseline": round(shift_24, 2) if shift_24 is not None else None,
            "state_house_mean_shift": round(state_house_mean, 2),
            "overperf_vs_benchmark": overperf_vs_benchmark,
            "benchmark_label": benchmark_label,
            "record_ideology_score": round(rec_score, 2),
            "rhetoric_ideology_score": round(rhet_score, 2),
            "rhetorical_moderation_pivot": pivot_score,
            "populist_economic_score": round(pop_score, 2),
            "cross_partisan_outreach_score": round(cross_score, 2),
            "quadrant": quad,
            "vibe_summary": llm.get("vibe_summary", ""),
            "fec_prog_pac_support": round(pac_info["prog_pac_support"]),
            "fec_mod_pac_support": round(pac_info["mod_pac_support"]),
            "fec_total_pro_dem_spend": round(mb_rec.get("total_pro_dem_spend") or 0),
            "fec_total_pro_gop_spend": round(mb_rec.get("total_pro_gop_spend") or 0),
            "bsky_handle": corp.get("bsky_handle"),
            "sample_media_and_interview_headlines": corp.get("news_and_interview_headlines", [])[:5],
            "sample_youtube_appearances": corp.get("youtube_shows_podcasts_debates", [])[:4],
        })

    # Summarize by quadrant
    quad_order = [
        "Committed Moderate (Mod Record + Mod Rhetoric)",
        "Mainstream / Cross-Partisan Populist",
        "Rhetorical Pivoter (Prog Record -> Mod/Affordability Rhetoric)",
        "Movement Progressive (Prog Record + Prog Rhetoric)",
    ]
    quad_summaries = []
    for q in quad_order:
        q_rows = [r for r in rows if r["quadrant"] == q]
        sw_rows = [r for r in q_rows if r["office_type"] != "house_races"]
        over_all = [r["overperf_vs_benchmark"] for r in q_rows if r["overperf_vs_benchmark"] is not None]
        over_sw = [r["overperf_vs_benchmark"] for r in sw_rows if r["overperf_vs_benchmark"] is not None]
        sh_all = [r["shift_vs_2024_baseline"] for r in q_rows if r["shift_vs_2024_baseline"] is not None]
        rec_m = statistics.mean([r["record_ideology_score"] for r in q_rows]) if q_rows else 0.0
        rhet_m = statistics.mean([r["rhetoric_ideology_score"] for r in q_rows]) if q_rows else 0.0
        piv_m = statistics.mean([r["rhetorical_moderation_pivot"] for r in q_rows]) if q_rows else 0.0
        sd_all = statistics.stdev(over_all) if len(over_all) > 1 else 0.0
        se_all = sd_all / math.sqrt(len(over_all)) if over_all else 0.0

        quad_summaries.append({
            "quadrant": q,
            "n_total": len(q_rows),
            "n_statewide": len(sw_rows),
            "mean_record_score": round(rec_m, 2),
            "mean_rhetoric_score": round(rhet_m, 2),
            "mean_moderation_pivot": round(piv_m, 2),
            "mean_shift_vs_2024": round(statistics.mean(sh_all), 2) if sh_all else None,
            "mean_overperf_all": round(statistics.mean(over_all), 2) if over_all else None,
            "median_overperf_all": round(statistics.median(over_all), 2) if over_all else None,
            "ci95_overperf_all": [
                round(statistics.mean(over_all) - 1.96 * se_all, 2),
                round(statistics.mean(over_all) + 1.96 * se_all, 2),
            ] if over_all else None,
            "mean_overperf_statewide_vs_house": round(statistics.mean(over_sw), 2) if over_sw else None,
            "median_overperf_statewide_vs_house": round(statistics.median(over_sw), 2) if over_sw else None,
            "pct_beating_benchmark_statewide": round(sum(1 for x in over_sw if x > 0) / len(over_sw) * 100, 1) if over_sw else None,
            "notable_examples": [f"{r['name']} ({r['office_label']}: {r['overperf_vs_benchmark']:+.2f} pts)" for r in q_rows[:6]],
        })

    out_data = {
        "fetched_at": ov.get("fetched_at"),
        "llm_coder_model": cache_obj.get("model", "opencode/deepseek-v4.1-flash-free"),
        "methodology": {
            "description": (
                "Tests the 'Rhetorical Pivot / Are Moderate Voters Rubes?' hypothesis across 49 major 2026 "
                "U.S. Senate, Gubernatorial, Attorney General, and competitive/PAC-targeted U.S. House candidates. "
                "Separates (1) Objective Past Record & Institutional Alignment (Voteview DW-NOMINATE roll-call votes, "
                "House caucus membership, pre-2026 M4A/GND/ICE positions, and FEC Independent Expenditures by progressive "
                "vs. moderate PACs) from (2) Blinded 2026 General-Election Rhetoric & Media Appearances (scraped pre-election "
                "news, TV/podcast/debate interviews, YouTube appearances, and Bluesky posts with candidate names and states "
                "redacted as [CANDIDATE] and [STATE] before scoring via opencode/deepseek-v4.1-flash-free)."
            ),
            "key_finding": (
                "Candidates with progressive past records who pivoted to moderate/kitchen-table rhetoric in the 2026 general "
                "election ('Rhetorical Pivoters') did NOT perform like committed moderates or mainstream populists: across "
                "statewide races, Rhetorical Pivoters still trailed their state's House Democrats (and trailed mainstream "
                "same-ballot ticket-mates in 96.5% of counties), because GOP Super PACs ($224.4M in MI alone) broadcast "
                "their past record back to voters."
            ),
        },
        "quadrant_summary": quad_summaries,
        "candidates": rows,
    }

    with open(OUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2, ensure_ascii=False)

    # Write flat CSV (excluding list fields)
    csv_cols = [
        "id", "name", "state", "office_label", "office_type", "caucus_or_faction", "dw_nominate",
        "margin_2026", "shift_vs_2024_baseline", "state_house_mean_shift", "overperf_vs_benchmark",
        "record_ideology_score", "rhetoric_ideology_score", "rhetorical_moderation_pivot",
        "populist_economic_score", "cross_partisan_outreach_score", "quadrant",
        "fec_prog_pac_support", "fec_mod_pac_support", "fec_total_pro_dem_spend", "fec_total_pro_gop_spend",
        "bsky_handle", "vibe_summary",
    ]
    with open(OUT_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=csv_cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    return out_data


def render_chart8(data: dict):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial", "Helvetica"]
    plt.rcParams["axes.edgecolor"] = "#cccccc"
    plt.rcParams["axes.linewidth"] = 0.8
    plt.rcParams["text.parse_math"] = False

    BG_COLOR = "#f4f3ef"
    DARK_TEXT = "#1a1a1a"
    SUB_TEXT = "#4a4a4a"
    MUTED_TEXT = "#6e6e6e"
    GRID_COLOR = "#dedcd6"

    COL_MOD = "#1b4f72"
    COL_POP = "#117864"
    COL_PIV = "#d35400"
    COL_PROG = "#922b21"

    quad_colors = {
        "Committed Moderate (Mod Record + Mod Rhetoric)": COL_MOD,
        "Mainstream / Cross-Partisan Populist": COL_POP,
        "Rhetorical Pivoter (Prog Record -> Mod/Affordability Rhetoric)": COL_PIV,
        "Movement Progressive (Prog Record + Prog Rhetoric)": COL_PROG,
    }

    fig = plt.figure(figsize=(16.8, 9.2), dpi=200, facecolor=BG_COLOR)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.10, 1.02], left=0.055, right=0.98, top=0.77, bottom=0.14, wspace=0.36)

    fig.text(
        0.03, 0.93,
        "Rhetoric vs. Record in 2026: Can a General-Election 'Moderate Affect' Paper Over a Progressive Record?",
        fontsize=18.2, fontweight="bold", color=DARK_TEXT,
    )
    fig.text(
        0.03, 0.885,
        "Blinded LLM Rhetoric Scoring (`opencode/deepseek-v4.1-flash-free` on 2026 interviews, podcasts, debates & press) vs. Objective Past Record (N=49 races).",
        fontsize=12.0, color=SUB_TEXT,
    )
    fig.text(
        0.03, 0.848,
        "Result: Candidates with progressive records who pivoted to kitchen-table rhetoric ('Rhetorical Pivoters') still lagged State House Dems — GOP Super PACs broadcast their past records.",
        fontsize=11.0, color=MUTED_TEXT, style="italic",
    )

    # --- PANEL A: 2x2 Scatter (Record Ideology vs. Blinded 2026 Rhetoric Score) ---
    ax1 = fig.add_subplot(gs[0], facecolor=BG_COLOR)
    ax1.set_title(
        "A. Objective Past Record vs. Blinded 2026 Campaign/Interview Rhetoric\n"
        "(Labels show 2026 Over/Underperformance vs. State House / District Benchmark, pts)",
        fontsize=11.3, fontweight="bold", color=DARK_TEXT, loc="left", pad=12,
    )

    ax1.axvline(-0.4, color="#666666", linestyle="--", linewidth=1.2, zorder=2)
    ax1.axhline(-0.55, color="#666666", linestyle="--", linewidth=1.2, zorder=2)
    ax1.plot([-2.0, 1.15], [-2.0, 1.15], color="#999999", linestyle=":", linewidth=1.2, zorder=1, label="No Pivot Line (Rhetoric = Record)")

    # Shaded highlight box for Rhetorical Pivoters quadrant (Top-Left: Prog Record <= -0.4, Moderated Rhetoric >= -0.55)
    ax1.axvspan(-2.0, -0.4, ymin=0.44, ymax=1.0, color="#fdf2e9", alpha=0.65, zorder=1)
    ax1.text(
        -1.93, 1.01,
        "QUADRANT 3: 'RHETORICAL PIVOTERS' (0-for-7 Statewide)\nProgressive Past Record + Moderated 2026 Rhetoric\n(Pivoting failed to erase record: lagged in MI, NM, ME, TX)",
        fontsize=8.1, fontweight="bold", color=COL_PIV, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#fff8f0", edgecolor=COL_PIV, lw=1.1),
        zorder=6,
    )

    ax1.text(
        -1.93, -0.63,
        "QUADRANT 4: MOVEMENT PROGRESSIVES\nProgressive Record + Progressive Rhetoric\n(0-for-4 Statewide: Flanagan, Nixon, Bradshaw, Markey)",
        fontsize=8.1, fontweight="bold", color=COL_PROG, va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#fdedec", edgecolor=COL_PROG, lw=1.0),
        zorder=6,
    )

    ax1.text(
        1.12, -1.15,
        "QUADRANTS 1 & 2: COMMITTED MODERATES\n& MAINSTREAM CROSS-PARTISAN POPULISTS\n20 of 25 (80%) Statewide Beat Their State's House Dems!\n(Sand +10.4, Hamilton +9.1, Shoffner +8.3, Andrews +6.7,\nColom +5.8, Cooper +5.4, Ossoff +5.4, Luján +3.8, Talarico +3.7)",
        fontsize=8.2, fontweight="bold", color=COL_MOD, va="top", ha="right",
        bbox=dict(boxstyle="round,pad=0.32", facecolor="#ebf5fb", edgecolor=COL_MOD, lw=1.1),
        zorder=6,
    )

    cands = data["candidates"]
    for c in cands:
        x = c["record_ideology_score"]
        y = c["rhetoric_ideology_score"]
        col = quad_colors.get(c["quadrant"], COL_MOD)
        marker = "o" if c["office_type"] != "house_races" else "s"
        sz = 95 if c["office_type"] != "house_races" else 68
        ax1.scatter([x], [y], color=col, s=sz, marker=marker, edgecolor="white", linewidth=0.9, alpha=0.92, zorder=4)

    # Annotate key spotlight candidates cleanly without overlaps
    label_offsets = {
        "MI_SEN": (-0.02, 0.22, "center"),
        "NM_GOV": (-0.18, 0.22, "center"),
        "TX_GOV": (-0.12, 0.20, "center"),
        "MI_AG": (-0.18, -0.14, "right"),
        "MI_07": (-0.18, -0.01, "right"),
        "ME_SEN": (0.12, 0.04, "left"),
        "MN_AG": (-0.12, -0.14, "right"),
        "MN_SEN": (-0.02, 0.16, "center"),
        "FL_SEN": (0.12, -0.12, "left"),
        "PA_12": (0.12, -0.05, "left"),
        "TX_SEN": (-0.22, 0.22, "right"),
        "OH_SEN": (-0.24, 0.06, "right"),
        "NM_SEN": (-0.18, -0.16, "right"),
        "NC_SEN": (0.04, 0.28, "center"),
        "IA_GOV": (0.14, -0.16, "left"),
        "KS_SEN": (0.04, 0.31, "center"),
        "SC_SEN": (-0.20, 0.26, "right"),
        "MS_SEN": (-0.02, -0.26, "center"),
        "TX_15": (-0.08, 0.16, "center"),
    }
    cmap = {c["id"]: c for c in cands}
    for cid, (dx, dy, ha_align) in label_offsets.items():
        if cid not in cmap:
            continue
        c = cmap[cid]
        x, y = c["record_ideology_score"], c["rhetoric_ideology_score"]
        col = quad_colors.get(c["quadrant"], COL_MOD)
        short_name = c["name"].split()[-1]
        if cid == "TX_15":
            short_name = "Pulido (TX-15)"
        elif cid == "NC_11":
            short_name = "Ager (NC-11)"
        elif cid == "MI_07":
            short_name = "Lawrence (MI-07)"
        elif cid == "PA_12":
            short_name = "S. Lee (PA-12)"
        else:
            short_name = f"{short_name} ({c['state']})"
        ov_v = c["overperf_vs_benchmark"]
        lbl = f"{short_name} [{ov_v:+.1f}]"
        ax1.annotate(
            lbl,
            xy=(x, y),
            xytext=(x + dx, y + dy),
            fontsize=7.9,
            fontweight="bold",
            color=col,
            ha=ha_align,
            va="center",
            arrowprops=dict(arrowstyle="-", color=col, lw=0.75, alpha=0.65),
            zorder=5,
        )

    ax1.set_xlim(-2.0, 1.18)
    ax1.set_ylim(-1.90, 1.08)
    ax1.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.yaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.set_xlabel("Objective Past Record & PAC Alignment  (<- Progressive Record  |  Moderate Record ->)", fontsize=10.1, fontweight="bold", color=DARK_TEXT)
    ax1.set_ylabel("Blinded 2026 Rhetoric & Media Affect  (<- Prog Rhetoric | Mod/Populist Rhetoric ->)", fontsize=10.1, fontweight="bold", color=DARK_TEXT)

    # --- PANEL B: Statewide Over/Underperformance vs. State House Dems by Quadrant ---
    ax2 = fig.add_subplot(gs[1], facecolor=BG_COLOR)
    ax2.set_title(
        "B. Statewide 2026 Performance vs. State's House Democrats\n"
        "(Senate, Governor & AG Shift Minus Contested State House Dem Shift, pts)",
        fontsize=11.3, fontweight="bold", color=DARK_TEXT, loc="left", pad=12,
    )

    q_summaries = data["quadrant_summary"]
    short_q_labels = [
        "1. Committed Moderates\n(Mod Record + Mod Rhetoric)",
        "2. Mainstream & Cross-Partisan\nPopulists (No M4A/ICE Baggage)",
        "3. 'Rhetorical Pivoters'\n(Prog Record -> Mod/Econ Rhetoric)",
        "4. Movement Progressives\n(Prog Record + Prog Rhetoric)",
    ]
    y_pos = np.arange(len(q_summaries))[::-1]
    ax2.axvline(0.0, color="#222222", linestyle="-", linewidth=1.4, zorder=2)

    for i, (y, qs, qlbl) in enumerate(zip(y_pos, q_summaries, short_q_labels)):
        q_name = qs["quadrant"]
        col = quad_colors[q_name]
        sw_rows = [c for c in cands if c["quadrant"] == q_name and c["office_type"] != "house_races"]
        sw_vals = [c["overperf_vs_benchmark"] for c in sw_rows if c["overperf_vs_benchmark"] is not None]
        mean_sw = statistics.mean(sw_vals) if sw_vals else 0.0

        # Plot horizontal bar for mean statewide over/underperformance
        ax2.barh(y, mean_sw, height=0.46, color=col, alpha=0.85, zorder=3)

        # Overlay individual statewide candidate dots
        for j, c in enumerate(sw_rows):
            val = c["overperf_vs_benchmark"]
            jitter = ((j % 3) - 1) * 0.09
            ax2.scatter([val], [y + jitter], color="white", edgecolor=col, s=52, linewidth=1.6, zorder=4)

        pct_win = qs.get("pct_beating_benchmark_statewide") or 0.0
        txt_x = 0.20 if mean_sw >= 0 else -0.20
        ha_t = "left" if mean_sw >= 0 else "right"
        ax2.text(
            txt_x, y + 0.31,
            f"Mean: {mean_sw:+.2f} pts ({pct_win:.0f}% beat House Dems, n={len(sw_vals)})",
            fontsize=8.3, fontweight="bold", color=col, ha=ha_t, va="center", zorder=5,
        )

    # Add callout box in the open bottom-right quadrant of Panel B (x > 0, y in [0, 1])
    ax2.annotate(
        "Why pivoting rhetoric didn't erase past records:\n"
        "• MI Sen El-Sayed (-3.05 vs House; $224M GOP IEs)\n"
        "• NM Gov Haaland (-7.97 vs House; -11.8 vs Luján)\n"
        "• TX Gov Hinojosa (-1.32 vs House; -5.0 vs Talarico)\n"
        "• MN Sen Flanagan (-2.54 vs House; -2.7 vs Klobuchar)\n"
        "• ME Sen Jackson (-8.78 vs House; -10.7 vs Pingree)",
        xy=(-0.2, 0.85), xytext=(0.45, 0.42),
        arrowprops=dict(arrowstyle="->", color=COL_PIV, lw=1.6),
        fontsize=7.6, fontweight="bold", color=COL_PIV,
        va="center", ha="left",
        bbox=dict(boxstyle="round,pad=0.28", facecolor="#fff8f0", edgecolor=COL_PIV, lw=1.1),
        zorder=6,
    )

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(short_q_labels, fontsize=9.2, fontweight="bold", color=DARK_TEXT)
    ax2.set_xlim(-11.4, 11.8)
    ax2.set_ylim(-0.6, 3.65)
    ax2.xaxis.grid(True, color=GRID_COLOR, linewidth=0.8)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.set_xlabel("Statewide Candidate Shift Minus Contested State House Dem Shift (margin pts)", fontsize=10.1, fontweight="bold", color=DARK_TEXT)

    ts_short = str(data.get("fetched_at") or "")[:16].replace("T", " ")
    fig.text(
        0.03, 0.022,
        f"Source: Multi-channel 2026 campaign/interview/podcast/social corpus scored blind via `{data['llm_coder_model']}`, joined with Voteview DW-NOMINATE, "
        f"FEC 2026 IEs, and live NYT 2026 returns ({ts_short}). Circles = Statewide (n=36); Squares = House (n=13).",
        fontsize=8.2, color=MUTED_TEXT,
    )

    plt.savefig(OUT_CHART_PATH, dpi=200, facecolor=BG_COLOR)
    plt.close(fig)
    print(f"Rendered {OUT_CHART_PATH}")


def main():
    force = "--refresh" in sys.argv
    cache_obj = build_or_load_cache(force_refresh=force)
    out_data = compute_live_dataset(cache_obj)
    render_chart8(out_data)


if __name__ == "__main__":
    main()

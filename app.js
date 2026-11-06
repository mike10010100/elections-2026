/* global d3, topojson */
(function () {
  "use strict";

  const STATE_NAMES = {
    AL: "Alabama", AK: "Alaska", AZ: "Arizona", AR: "Arkansas", CA: "California",
    CO: "Colorado", CT: "Connecticut", DE: "Delaware", DC: "District of Columbia",
    FL: "Florida", GA: "Georgia", HI: "Hawaii", ID: "Idaho", IL: "Illinois",
    IN: "Indiana", IA: "Iowa", KS: "Kansas", KY: "Kentucky", LA: "Louisiana",
    ME: "Maine", MD: "Maryland", MA: "Massachusetts", MI: "Michigan", MN: "Minnesota",
    MS: "Mississippi", MO: "Missouri", MT: "Montana", NE: "Nebraska", NV: "Nevada",
    NH: "New Hampshire", NJ: "New Jersey", NM: "New Mexico", NY: "New York",
    NC: "North Carolina", ND: "North Dakota", OH: "Ohio", OK: "Oklahoma", OR: "Oregon",
    PA: "Pennsylvania", RI: "Rhode Island", SC: "South Carolina", SD: "South Dakota",
    TN: "Tennessee", TX: "Texas", UT: "Utah", VT: "Vermont", VA: "Virginia",
    WA: "Washington", WV: "West Virginia", WI: "Wisconsin", WY: "Wyoming"
  };

  const CYCLE_LABELS = {
    s26: "2026 U.S. Senate",
    top26: "2026 All-50-State Top Ticket (Sen/Gov/House)",
    h26: "2026 U.S. House",
    g26: "2026 Governors",
    ag26: "2026 Attorneys General",
    p24: "2024 President",
    p20: "2020 President",
    p16: "2016 President",
    p12: "2012 President",
    p08: "2008 President",
    p04: "2004 President",
    s24: "2024 U.S. Senate (Class I)",
    s22: "2022 U.S. Senate (Class III)",
    s20: "2020 U.S. Senate (Class II)",
    s18: "2018 U.S. Senate (Class I)",
    s16: "2016 U.S. Senate (Class III)",
    s14: "2014 U.S. Senate (Class II)",
    s12: "2012 U.S. Senate (Class I)",
    s10: "2010 U.S. Senate (Class III)",
    s08: "2008 U.S. Senate (Class II)",
    s06: "2006 U.S. Senate (Class I)",
    s04: "2004 U.S. Senate (Class III)",
    h24: "2024 U.S. House",
    h22: "2022 U.S. House (Midterm)",
    h20: "2020 U.S. House",
    h18: "2018 U.S. House (Midterm)",
    h16: "2016 U.S. House",
    h14: "2014 U.S. House (Midterm)",
    h12: "2012 U.S. House",
    h10: "2010 U.S. House (Midterm)",
    h08: "2008 U.S. House",
    h06: "2006 U.S. House (Midterm)",
    h04: "2004 U.S. House",
    g24: "2024 Governors"
  };

  const AUTO_APPLES_PREDECESSOR = {
    p24: ["p20"],
    p20: ["p16"],
    p16: ["p12"],
    p12: ["p08"],
    p08: ["p04"],
    p04: ["p04"],
    s26: ["s20", "s22"],
    top26: ["s20", "s22", "h24", "p24"],
    s24: ["s18", "s20"],
    s22: ["s16", "s18"],
    s20: ["s14", "s16"],
    s18: ["s12", "s14"],
    s16: ["s10", "s12"],
    s14: ["s08", "s10"],
    s12: ["s06", "s08"],
    s10: ["s04", "s06"],
    s08: ["p08"],
    s06: ["p04"],
    s04: ["p04"],
    h26: ["h24", "h22"],
    h24: ["h22", "h20"],
    h22: ["h20", "h18"],
    h20: ["h18", "h16"],
    h18: ["h16", "h14"],
    h16: ["h14", "h12"],
    h14: ["h12", "h10"],
    h12: ["h10", "h08"],
    h10: ["h08", "h06"],
    h08: ["h06", "h04"],
    h06: ["h04"],
    h04: ["p04"],
    g26: ["g24", "s22", "h22", "p24"],
    ag26: ["s22", "h22", "p24"]
  };

  // App state
  const state = {
    overview: null,
    countyShifts: null,
    topo: null,
    stateFeatures: [],
    countyFeatures: [],
    countyCentroids: {},
    stateCentroids: {},
    stateRelevanceMap: {},
    loadedStateCivicRaces: {},

    theme: document.documentElement.getAttribute("data-theme") || "dark",
    activeOfficeTab: "senate",      // senate | house | governor | demographics | close | measures | legislatures | all-local
    mapMode: "shift",               // shift | winner | forecast
    mapDataset: "s26",              // s26 | h26 | g26 | ag26 | p24..p04 | s24..s04 | h24..h04
    baselineCycle: "AUTO_APPLES",   // AUTO_APPLES | AUTO_MIDTERM | p24..p04 | s24..s04 | h24..h04
    winnerLevel: "state",           // state | county
    minEevp: 1,
    selectedState: "ALL",
    inspectedCountyFips: null,
    searchQuery: "",
    callStatusFilter: "ALL",
    sortBy: "uncalled-first",
    civicTypeFilter: "ALL",
    page: 1,
    pageSize: 48,
    fecMoneyball: null,
    factionAnalysis: null,
    breakingPoints: null,
    moneyballOffice: "senate",
    moneyballSort: "spend-desc",
    moneyballSearch: ""
  };

  const fmtInt = d3.format(",");
  const fmtPct = (v) => `${Number(v || 0).toFixed(1)}%`;
  const fmtMargin = (m) => {
    if (m === null || m === undefined || Number.isNaN(Number(m))) return "—";
    const num = Number(m);
    if (Math.abs(num) < 0.05) return "Even";
    return num > 0 ? `D+${num.toFixed(1)}%` : `R+${Math.abs(num).toFixed(1)}%`;
  };

  let svg, gMap, zoomBehavior;

  async function init() {
    syncThemeButtonUI();
    setupMapSvg();
    bindEvents();
    await loadAllData();
  }

  function isDark() {
    return (document.documentElement.getAttribute("data-theme") || "dark") === "dark";
  }

  function isLive2026Dataset(ds) {
    return ds === "s26" || ds === "top26" || ds === "h26" || ds === "g26" || ds === "ag26";
  }

  function isPartisanTab(tab) {
    return tab === "senate" || tab === "house" || tab === "governor" || tab === "demographics";
  }

  function syncThemeButtonUI() {
    const dark = isDark();
    state.theme = dark ? "dark" : "light";
    const iconEl = document.getElementById("theme-toggle-icon");
    const labelEl = document.getElementById("theme-toggle-label");
    if (iconEl) iconEl.textContent = dark ? "☀️" : "🌙";
    if (labelEl) labelEl.textContent = dark ? "Light Mode" : "Dark Mode";
  }

  function toggleTheme() {
    const next = isDark() ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("elections2026-theme", next);
    } catch (e) {}
    syncThemeButtonUI();
    updateHatchPatterns();
    renderMap();
  }

  function setupMapSvg() {
    svg = d3.select("#us-election-map");
    svg.selectAll("*").remove();

    svg.append("defs");
    updateHatchPatterns();

    gMap = svg.append("g").attr("class", "map-root-g");
    gMap.append("g").attr("class", "layer-states");
    gMap.append("g").attr("class", "layer-counties");
    gMap.append("g").attr("class", "layer-state-borders");
    gMap.append("g").attr("class", "layer-bubbles");
    gMap.append("g").attr("class", "layer-arrows");
    gMap.append("g").attr("class", "layer-labels");

    zoomBehavior = d3.zoom()
      .scaleExtent([1, 12])
      .on("zoom", (event) => {
        gMap.attr("transform", event.transform);
      });

    svg.call(zoomBehavior);
  }

  function updateHatchPatterns() {
    if (!svg) return;
    const defs = svg.select("defs");
    defs.selectAll("*").remove();

    const dark = isDark();
    const mkPattern = (id, bg, stripe, sw = 4) => {
      const p = defs.append("pattern")
        .attr("id", id)
        .attr("patternUnits", "userSpaceOnUse")
        .attr("width", 8)
        .attr("height", 8)
        .attr("patternTransform", "rotate(45)");
      p.append("rect").attr("width", 8).attr("height", 8).attr("fill", bg);
      p.append("line")
        .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 8)
        .attr("stroke", stripe).attr("stroke-width", sw);
    };
    mkPattern("pat-dem-lead", dark ? "#172554" : "#dbeafe", dark ? "#3b82f6" : "#2563eb", 4);
    mkPattern("pat-gop-lead", dark ? "#450a0a" : "#fee2e2", dark ? "#ef4444" : "#dc2626", 4);
    mkPattern("pat-inactive-state", dark ? "#0f1521" : "#d4dce4", dark ? "#182234" : "#bcc6d2", 2.2);
  }

  async function loadAllData(bustCache = false) {
    const qs = bustCache ? `?t=${Date.now()}` : "?v=20261106a";
    const btn = document.getElementById("btn-live-refresh");
    if (btn) btn.disabled = true;

    try {
      const [overview, countyShifts, topo] = await Promise.all([
        fetch(`site_data/overview.json${qs}`).then((r) => r.json()),
        fetch(`site_data/county_shifts.json${qs}`).then((r) => r.json()),
        state.topo
          ? Promise.resolve(state.topo)
          : fetch("site_data/counties-albers-10m.json").then((r) => r.json())
      ]);

      state.overview = overview;
      state.countyShifts = countyShifts;
      if (bustCache) {
        state.fecMoneyball = null;
        state.factionAnalysis = null;
        state.breakingPoints = null;
      }

      if (!state.topo) {
        state.topo = topo;
        prepareGeometries(topo, countyShifts);
        populateStateDropdowns(overview);
        populateCivicTypesDropdown(overview);
      }

      updateHeaderMeta();
      await syncActiveView();
    } catch (err) {
      console.error("Failed loading election data:", err);
      document.getElementById("last-updated-text").textContent =
        "Error loading election data snapshot. Check console.";
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // =========================================================================
  // APPLES-TO-APPLES HISTORICAL BASELINE RESOLUTION (2004–2026)
  // =========================================================================
  function resolveBaselineKeyAndRecord(cData, targetCycle, baselinePref) {
    if (!cData) return { key: null, rec: null, label: "Prior Cycle" };

    if (baselinePref === "AUTO_APPLES") {
      const candidates = AUTO_APPLES_PREDECESSOR[targetCycle] || ["p24"];
      for (const k of candidates) {
        const r = cData[k];
        if (r && r.v > 0 && !r.op) {
          return { key: k, rec: r, label: CYCLE_LABELS[k] || k };
        }
      }
      // Fallback if only one-party exists
      for (const k of candidates) {
        if (cData[k] && cData[k].v > 0) {
          return { key: k, rec: cData[k], label: CYCLE_LABELS[k] || k };
        }
      }
      return { key: candidates[0], rec: null, label: CYCLE_LABELS[candidates[0]] || "Prior Cycle" };
    }

    if (baselinePref === "AUTO_MIDTERM") {
      const candidates = targetCycle.startsWith("s") ? ["s22", "h22"] : ["h22", "s22"];
      for (const k of candidates) {
        const r = cData[k];
        if (r && r.v > 0 && !r.op) {
          return { key: k, rec: r, label: CYCLE_LABELS[k] || k };
        }
      }
      return { key: "h22", rec: cData.h22 || null, label: CYCLE_LABELS.h22 };
    }

    const r = cData[baselinePref] || null;
    return { key: baselinePref, rec: r, label: CYCLE_LABELS[baselinePref] || baselinePref };
  }

  function getBaselineDescriptionLabel(targetCycle, baselinePref) {
    if (baselinePref === "AUTO_APPLES") {
      if (targetCycle === "s26") return "2020 U.S. Senate (Class II — Same Seats)";
      if (targetCycle === "h26") return "2024 U.S. House (Same Districts)";
      if (targetCycle === "g26") return "2022 Midterm / Prior Cycle";
      const preds = AUTO_APPLES_PREDECESSOR[targetCycle] || ["p24"];
      return CYCLE_LABELS[preds[0]] || "Last Same-Office Election";
    }
    if (baselinePref === "AUTO_MIDTERM") {
      return "2022 Midterm Election (Senate / House)";
    }
    return CYCLE_LABELS[baselinePref] || baselinePref;
  }

  function computeCountyShift(cData, targetCycle, baselinePref) {
    const rec = cData[targetCycle];
    if (!rec || !rec.v || rec.op) return null;
    const { key, rec: baseRec } = resolveBaselineForCounty(cData, targetCycle, baselinePref);
    if (!baseRec || !baseRec.v || baseRec.op || key === targetCycle) return null;
    return Number((rec.m - baseRec.m).toFixed(2));
  }

  function resolveBaselineForCounty(cData, targetCycle, baselinePref) {
    return resolveBaselineKeyAndRecord(cData, targetCycle, baselinePref);
  }

  async function syncActiveView() {
    const tab = state.activeOfficeTab;
    const balanceSec = document.getElementById("balance-section");
    const mapSec = document.getElementById("map-section");
    const forecastSec = document.getElementById("forecast-panel");
    const demSec = document.getElementById("demographics-section");
    const analysisSec = document.getElementById("analysis-section");
    const explorerSec = document.getElementById("results-explorer-section");

    if (tab === "analysis") {
      if (balanceSec) balanceSec.style.display = "none";
      if (mapSec) mapSec.style.display = "none";
      if (forecastSec) forecastSec.style.display = "none";
      if (demSec) demSec.style.display = "none";
      if (explorerSec) explorerSec.style.display = "none";
      if (analysisSec) {
        analysisSec.style.display = "flex";
        await renderAnalysisSection();
      }
      return;
    }

    if (analysisSec) analysisSec.style.display = "none";
    if (explorerSec) explorerSec.style.display = "block";

    if (tab === "all-local") {
      balanceSec.style.display = "none";
      mapSec.style.display = "none";
      forecastSec.style.display = "none";
      demSec.style.display = "none";
      await renderRaceExplorer();
      return;
    }

    balanceSec.style.display = "block";
    mapSec.style.display = "block";
    demSec.style.display = isPartisanTab(tab) ? "block" : "none";

    renderBalanceOfPower();
    renderMap();
    renderForecastPanel();
    if (isPartisanTab(tab)) {
      renderDemographicsSection();
      if (state.inspectedCountyFips && state.countyShifts) {
        const cData = state.countyShifts.counties[state.inspectedCountyFips];
        if (cData) renderCountyInspectorDrawer(cData);
      }
    }
    await renderRaceExplorer();
  }

  function prepareGeometries(topo, countyShifts) {
    const pathGen = d3.geoPath();
    const fipsToPostal = countyShifts.state_fips_to_postal || {};

    state.stateFeatures = topojson.feature(topo, topo.objects.states).features;
    state.countyFeatures = topojson.feature(topo, topo.objects.counties).features;

    for (const sf of state.stateFeatures) {
      const postal = fipsToPostal[sf.id] || "";
      sf.properties = sf.properties || {};
      sf.properties.postal = postal;
      const c = pathGen.centroid(sf);
      if (c && !Number.isNaN(c[0]) && !Number.isNaN(c[1])) {
        state.stateCentroids[postal] = c;
      }
    }

    for (const cf of state.countyFeatures) {
      const c = pathGen.centroid(cf);
      if (c && !Number.isNaN(c[0]) && !Number.isNaN(c[1])) {
        state.countyCentroids[cf.id] = c;
      }
    }
    if (!state.countyCentroids["02020"] && state.stateCentroids["AK"]) {
      state.countyCentroids["02020"] = state.stateCentroids["AK"];
    }
    if (!state.countyCentroids["02000"] && state.stateCentroids["AK"]) {
      state.countyCentroids["02000"] = state.stateCentroids["AK"];
    }
  }

  function populateStateDropdowns(overview) {
    const statesIdx = (overview.summary_counts && overview.summary_counts.states_index) || {};
    const codes = Object.keys(STATE_NAMES).sort((a, b) =>
      STATE_NAMES[a].localeCompare(STATE_NAMES[b])
    );

    for (const selId of ["select-state-filter", "filter-state-inline"]) {
      const sel = document.getElementById(selId);
      if (!sel) continue;
      sel.innerHTML = `<option value="ALL">All 50 States + D.C.</option>`;
      for (const code of codes) {
        const cnt = statesIdx[code] ? ` (${fmtInt(statesIdx[code].total)} races)` : "";
        const opt = document.createElement("option");
        opt.value = code;
        opt.textContent = `${STATE_NAMES[code]} (${code})${cnt}`;
        sel.appendChild(opt);
      }
    }
  }

  function populateCivicTypesDropdown(overview) {
    const sel = document.getElementById("filter-civic-type");
    const topTypes = (overview.summary_counts && overview.summary_counts.top_race_types) || [];
    sel.innerHTML = `<option value="ALL">All Office / Ballot Types (${fmtInt(overview.summary_counts.civic_total_races)})</option>`;
    for (const [tName, count] of topTypes) {
      const opt = document.createElement("option");
      opt.value = tName;
      opt.textContent = `${tName} (${fmtInt(count)})`;
      sel.appendChild(opt);
    }
  }

  function updateHeaderMeta() {
    const ov = state.overview;
    const sc = ov.summary_counts;
    const dt = new Date(ov.fetched_at);
    const timeStr = Number.isNaN(dt.getTime())
      ? ov.fetched_at
      : dt.toLocaleString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          hour: "numeric",
          minute: "2-digit",
          second: "2-digit"
        });

    document.getElementById("last-updated-text").textContent =
      `Snapshot: ${timeStr} · Auto-updating every 5 min · ${fmtInt(sc.civic_called_races)} called / ${fmtInt(sc.civic_uncalled_races)} uncalled · 2004–2026 normalized archive`;
    document.getElementById("global-races-pill").textContent =
      `${fmtInt(sc.civic_total_races)} Races · ${fmtInt(sc.counties_tracked)} Counties · 2004–2026`;

    const senUncalled = ov.senate_races.filter((r) => !r.called).length;
    const houseUncalled = ov.house_races.filter((r) => !r.called).length;
    const govUncalled = ov.governor_races.filter((r) => !r.called).length;

    document.getElementById("tab-badge-senate").textContent =
      `35 (${senUncalled} uncalled)`;
    document.getElementById("tab-badge-house").textContent =
      `435 (${houseUncalled} uncalled)`;
    document.getElementById("tab-badge-governor").textContent =
      `36 (${govUncalled} uncalled)`;
    document.getElementById("tab-badge-close").textContent =
      `${senUncalled + houseUncalled + govUncalled} uncalled`;
    document.getElementById("tab-badge-measures").textContent =
      `${ov.measures_races.length} statewide`;
    document.getElementById("tab-badge-all").textContent =
      fmtInt(sc.civic_total_races);
  }

  // =========================================================================
  // BALANCE OF POWER / SUMMARY BAR (Tailored to Active Tab!)
  // =========================================================================
  function renderBalanceOfPower() {
    const ov = state.overview;
    const cc = ov.chamber_control;
    const tab = state.activeOfficeTab;

    const leftDot = document.getElementById("balance-left-dot");
    const rightDot = document.getElementById("balance-right-dot");
    const leftSeatsEl = document.getElementById("balance-dem-seats");
    const rightSeatsEl = document.getElementById("balance-gop-seats");
    const leftLabelEl = document.getElementById("balance-dem-label");
    const rightLabelEl = document.getElementById("balance-gop-label");
    const leftFlipsEl = document.getElementById("balance-dem-flips");
    const rightFlipsEl = document.getElementById("balance-gop-flips");
    const leftSubEl = document.getElementById("balance-dem-sub");
    const rightSubEl = document.getElementById("balance-gop-sub");
    const titleEl = document.getElementById("balance-chamber-title");
    const majLabelEl = document.getElementById("balance-majority-label");
    const popVoteEl = document.getElementById("balance-pop-vote");
    const track = document.getElementById("seat-bar-track");
    const legend = document.getElementById("seat-bar-legend");
    const majLine = document.getElementById("majority-line");

    leftDot.className = "party-dot dem-bg";
    rightDot.className = "party-dot gop-bg";
    leftSeatsEl.className = "seat-big-num dem-text";
    rightSeatsEl.className = "seat-big-num gop-text";
    majLine.style.display = "block";

    // Case 1: Ballot Measures Tab
    if (tab === "measures") {
      const measures = ov.measures_races || [];
      let yesCalled = 0, yesLead = 0, noCalled = 0, noLead = 0;
      for (const m of measures) {
        const p = m.winner_party || m.leader_party;
        if (m.called) {
          if (p === "YES") yesCalled++;
          else if (p === "NO") noCalled++;
        } else {
          if (p === "YES") yesLead++;
          else if (p === "NO") noLead++;
        }
      }
      const total = Math.max(1, measures.length);
      const other = Math.max(0, total - (yesCalled + yesLead + noCalled + noLead));
      const pct = (n) => `${((100 * n) / total).toFixed(2)}%`;

      leftDot.className = "party-dot yes-bg";
      rightDot.className = "party-dot no-bg";
      leftSeatsEl.className = "seat-big-num yes-text";
      rightSeatsEl.className = "seat-big-num no-text";

      leftLabelEl.textContent = "Approved / Yes";
      rightLabelEl.textContent = "Rejected / No";
      leftFlipsEl.textContent = `${yesCalled} called`;
      rightFlipsEl.textContent = `${noCalled} called`;
      leftSeatsEl.textContent = yesCalled + yesLead;
      rightSeatsEl.textContent = noCalled + noLead;
      leftSubEl.textContent = `${yesCalled} approved · ${yesLead} leading Yes`;
      rightSubEl.textContent = `${noCalled} rejected · ${noLead} leading No`;
      titleEl.textContent = `2026 STATEWIDE BALLOT MEASURES (${measures.length} MEASURES)`;
      majLabelEl.textContent = "Constitutional amendments, citizen initiatives, bond issues & referendums";
      popVoteEl.textContent = "";
      majLine.style.display = "none";

      track.innerHTML = `
        <div class="seat-seg seg-yes-solid" style="width:${pct(yesCalled + yesLead)}" title="Yes / Passing: ${yesCalled + yesLead}"></div>
        <div class="seat-seg seg-tossup" style="width:${pct(other)}" title="Pending: ${other}"></div>
        <div class="seat-seg seg-no-solid" style="width:${pct(noCalled + noLead)}" title="No / Failing: ${noCalled + noLead}"></div>
      `;
      legend.innerHTML = `
        <span class="leg-item"><i class="swatch yes-solid"></i> Yes (Approved / Leading)</span>
        <span class="leg-item"><i class="swatch tossup-swatch"></i> Unreported</span>
        <span class="leg-item"><i class="swatch no-solid"></i> No (Rejected / Leading)</span>
      `;
      return;
    }

    // Case 2: State Legislatures Tab
    if (tab === "legislatures") {
      const chs = cc.state_chambers || [];
      let demCtrl = 0, gopCtrl = 0, splitOrPending = 0, demSeatFlips = 0, gopSeatFlips = 0;
      for (const c of chs) {
        demSeatFlips += c.dem_flips || 0;
        gopSeatFlips += c.gop_flips || 0;
        if (c.dem_winner || c.dem_seats > c.gop_seats) demCtrl++;
        else if (c.gop_winner || c.gop_seats > c.dem_seats) gopCtrl++;
        else splitOrPending++;
      }
      const total = Math.max(1, chs.length);
      const pct = (n) => `${((100 * n) / total).toFixed(2)}%`;

      leftLabelEl.textContent = "Dem. Chambers";
      rightLabelEl.textContent = "Rep. Chambers";
      leftFlipsEl.textContent = demSeatFlips > 0 ? `+${demSeatFlips} seat flips` : "Chambers";
      rightFlipsEl.textContent = gopSeatFlips > 0 ? `+${gopSeatFlips} seat flips` : "Chambers";
      leftSeatsEl.textContent = demCtrl;
      rightSeatsEl.textContent = gopCtrl;
      leftSubEl.textContent = `Leading or called majority in ${demCtrl} chambers`;
      rightSubEl.textContent = `Leading or called majority in ${gopCtrl} chambers`;
      titleEl.textContent = "STATE LEGISLATIVE CHAMBERS (90 CHAMBERS ON 2026 BALLOT)";
      majLabelEl.textContent = "State Senates & State Houses / Assemblies across the United States";
      popVoteEl.textContent = "";

      track.innerHTML = `
        <div class="seat-seg seg-dem-solid" style="width:${pct(demCtrl)}"></div>
        <div class="seat-seg seg-tossup" style="width:${pct(splitOrPending)}"></div>
        <div class="seat-seg seg-gop-solid" style="width:${pct(gopCtrl)}"></div>
      `;
      legend.innerHTML = `
        <span class="leg-item"><i class="swatch dem-solid"></i> Democratic Chamber Majority</span>
        <span class="leg-item"><i class="swatch tossup-swatch"></i> Tied / Uncalled</span>
        <span class="leg-item"><i class="swatch gop-solid"></i> Republican Chamber Majority</span>
      `;
      return;
    }

    // Case 3: Too Close to Call Tab
    if (tab === "close") {
      const uncalledAll = [
        ...ov.senate_races.filter((r) => !r.called),
        ...ov.governor_races.filter((r) => !r.called),
        ...ov.house_races.filter((r) => !r.called)
      ];
      const demLead = uncalledAll.filter((r) => r.leader_party === "DEM").length;
      const gopLead = uncalledAll.filter((r) => r.leader_party === "GOP").length;
      const othLead = Math.max(0, uncalledAll.length - demLead - gopLead);
      const total = Math.max(1, uncalledAll.length);
      const pct = (n) => `${((100 * n) / total).toFixed(2)}%`;

      leftLabelEl.textContent = "Dem. Leading";
      rightLabelEl.textContent = "Rep. Leading";
      leftFlipsEl.textContent = "Uncalled";
      rightFlipsEl.textContent = "Uncalled";
      leftSeatsEl.textContent = demLead;
      rightSeatsEl.textContent = gopLead;
      leftSubEl.textContent = `Leading in ${demLead} uncalled federal/gov races`;
      rightSubEl.textContent = `Leading in ${gopLead} uncalled federal/gov races`;
      titleEl.textContent = `TOO CLOSE TO CALL (${uncalledAll.length} UNCALLED FEDERAL & GOVERNOR RACES)`;
      majLabelEl.textContent = `2 U.S. Senate · 75 U.S. House · 2 Governor races still awaiting final race calls`;
      popVoteEl.textContent = "Closest right now: MS Senate (43 votes, 0.01%) · AZ-02 (86 votes, 0.03%) · NC-05 (99 votes, 0.04%)";

      track.innerHTML = `
        <div class="seat-seg seg-dem-lead" style="width:${pct(demLead)}"></div>
        <div class="seat-seg seg-tossup" style="width:${pct(othLead)}"></div>
        <div class="seat-seg seg-gop-lead" style="width:${pct(gopLead)}"></div>
      `;
      legend.innerHTML = `
        <span class="leg-item"><i class="swatch dem-lead"></i> Democrat Currently Leading</span>
        <span class="leg-item"><i class="swatch gop-lead"></i> Republican Currently Leading</span>
      `;
      return;
    }

    // Case 4: Standard Senate, House, or Governor Balance of Power Bar
    const chamberKey =
      tab === "house" || state.mapDataset.startsWith("h")
        ? "house"
        : tab === "governor" || state.mapDataset.startsWith("g")
        ? "governor"
        : "senate";
    const data = cc[chamberKey];
    const total = data.total;

    let demSolid = 0, demLead = 0, gopSolid = 0, gopLead = 0;
    let demSub = "", gopSub = "", title = "", majLabel = "", popVoteText = "";

    leftLabelEl.textContent = "Democrats";
    rightLabelEl.textContent = "Republicans";

    if (chamberKey === "senate") {
      demSolid = data.dem_total_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_total_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_no_election} not up · ${data.dem_called} called · ${data.dem_leading} leading`;
      gopSub = `${data.gop_no_election} not up · ${data.gop_called} called · ${data.gop_leading} leading`;
      title = "U.S. SENATE BALANCE OF POWER (100 SEATS)";
      majLabel = "51 for Democratic majority · 50 for Republican control (with VP tiebreaker)";
      leftFlipsEl.textContent = data.dem_flips > 0 ? `+${data.dem_flips} flips` : "0 flips";
      rightFlipsEl.textContent = data.gop_flips > 0 ? `+${data.gop_flips} flips` : "0 flips";
    } else if (chamberKey === "house") {
      demSolid = data.dem_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_called} called · ${data.dem_leading} leading (proj. ${data.dem_projected_total})`;
      gopSub = `${data.gop_called} called · ${data.gop_leading} leading (proj. ${data.gop_projected_total})`;
      title = "U.S. HOUSE BALANCE OF POWER (435 SEATS)";
      majLabel = "218 seats needed for majority";
      leftFlipsEl.textContent = data.dem_flips > 0 ? `+${data.dem_flips} flips` : "0 flips";
      rightFlipsEl.textContent = data.gop_flips > 0 ? `+${data.gop_flips} flips` : "0 flips";
    } else {
      demSolid = data.dem_total_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_total_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_no_election} not up · ${data.dem_called} called · ${data.dem_leading} leading`;
      gopSub = `${data.gop_no_election} not up · ${data.gop_called} called · ${data.gop_leading} leading`;
      title = "STATE GOVERNORS BALANCE OF POWER (50 STATES)";
      majLabel = "36 states holding gubernatorial elections in 2026";
      leftFlipsEl.textContent = `Proj: ${data.dem_projected_total}`;
      rightFlipsEl.textContent = `Proj: ${data.gop_projected_total}`;
    }

    if (data.model_estimates && data.model_estimates.length) {
      const demEst = data.model_estimates.find((e) => e.nyt_party_id === "DEM");
      const gopEst = data.model_estimates.find((e) => e.nyt_party_id === "GOP");
      if (demEst && gopEst && demEst.popular_vote && gopEst.popular_vote) {
        const marginPts = ((demEst.voteshare_margin || 0) * 100).toFixed(1);
        popVoteText = `Est. National Popular Vote: Dem. ${fmtInt(demEst.popular_vote)} vs. Rep. ${fmtInt(gopEst.popular_vote)} (${marginPts >= 0 ? "D+" + marginPts : "R+" + Math.abs(marginPts)}%)`;
      }
    }

    leftSeatsEl.textContent = demSolid;
    rightSeatsEl.textContent = gopSolid;
    leftSubEl.textContent = demSub;
    rightSubEl.textContent = gopSub;
    titleEl.textContent = title;
    majLabelEl.textContent = majLabel;
    popVoteEl.textContent = popVoteText;

    const tossup = Math.max(0, total - (demSolid + demLead + gopSolid + gopLead));
    const pct = (n) => `${((100 * n) / total).toFixed(2)}%`;

    track.innerHTML = `
      <div class="seat-seg seg-dem-solid" style="width:${pct(demSolid)}" title="Dem Called/Held: ${demSolid}"></div>
      <div class="seat-seg seg-dem-lead" style="width:${pct(demLead)}" title="Dem Leading: ${demLead}"></div>
      <div class="seat-seg seg-tossup" style="width:${pct(tossup)}" title="Other/Tossup: ${tossup}"></div>
      <div class="seat-seg seg-gop-lead" style="width:${pct(gopLead)}" title="Rep Leading: ${gopLead}"></div>
      <div class="seat-seg seg-gop-solid" style="width:${pct(gopSolid)}" title="Rep Called/Held: ${gopSolid}"></div>
    `;
    legend.innerHTML = `
      <span class="leg-item"><i class="swatch dem-solid"></i> Dem. Called / Held</span>
      <span class="leg-item"><i class="swatch dem-lead"></i> Dem. Leading</span>
      <span class="leg-item"><i class="swatch tossup-swatch"></i> Uncalled / Other</span>
      <span class="leg-item"><i class="swatch gop-lead"></i> Rep. Leading</span>
      <span class="leg-item"><i class="swatch gop-solid"></i> Rep. Called / Held</span>
    `;
  }

  // =========================================================================
  // INTERACTIVE MAP RENDERING (Context-Aware + 2004–2026 Historical Support!)
  // =========================================================================
  function computeStateRelevanceMap(
    effectiveMode,
    stateRaceByPostal,
    measuresByState,
    legByState,
    uncalledByState
  ) {
    const relMap = {};
    const ds = state.mapDataset;
    const isLive26 = isLive2026Dataset(ds);

    // Precompute county-level presence and shift availability by state for current dataset
    const stateHasVotes = {};
    const stateHasShift = {};
    const stateOnlyOneParty = {};
    for (const cData of Object.values(state.countyShifts.counties || {})) {
      const st = cData.state;
      if (!st) continue;
      const rec = cData[ds];
      if (rec && rec.v > 0) {
        stateHasVotes[st] = true;
        if (!rec.op) {
          stateOnlyOneParty[st] = false;
        } else if (stateOnlyOneParty[st] === undefined) {
          stateOnlyOneParty[st] = true;
        }
        const eevpOk = !isLive26 || (rec.eevp !== undefined ? rec.eevp >= state.minEevp : true);
        if (eevpOk && computeCountyShift(cData, ds, state.baselineCycle) !== null) {
          stateHasShift[st] = true;
        }
      }
    }

    let inactiveStatesCount = 0;
    let hasDCInactive = false;

    for (const postal of Object.keys(STATE_NAMES)) {
      let relevant = true;
      let shortTag = "";
      let reason = "";

      if (effectiveMode === "measures") {
        if (!measuresByState[postal] || !measuresByState[postal].length) {
          relevant = false;
          shortTag = "No 2026 Ballot Measures";
          reason = `${STATE_NAMES[postal]} has no statewide ballot measures on the 2026 ballot.`;
        }
      } else if (effectiveMode === "legislatures") {
        if (!legByState[postal] || !legByState[postal].length) {
          relevant = false;
          shortTag = "No 2026 Chamber Election";
          reason = `${STATE_NAMES[postal]} does not hold regular partisan state legislative chamber elections in 2026.`;
        }
      } else if (effectiveMode === "close") {
        if (!uncalledByState[postal] || !uncalledByState[postal].length) {
          relevant = false;
          shortTag = "All Races Called";
          reason = `All 2026 U.S. Senate, U.S. House, and Governor races in ${STATE_NAMES[postal]} have already been called.`;
        }
      } else {
        // Partisan / Historical Modes (shift | winner | forecast)
        if (ds === "s26") {
          if (!stateRaceByPostal[postal]) {
            relevant = false;
            shortTag = "No 2026 U.S. Senate Election";
            reason = `${STATE_NAMES[postal]} does not have a U.S. Senate seat on the 2026 ballot (Class I & III seats are not up in 2026).`;
          } else if (effectiveMode === "shift" && !stateHasShift[postal]) {
            relevant = false;
            shortTag = stateRaceByPostal[postal].one_party
              ? "No Dem. vs. Rep. Contest"
              : "No County Shift Data";
            reason = stateRaceByPostal[postal].one_party
              ? `${STATE_NAMES[postal]}'s 2026 U.S. Senate race is GOP vs. Independent (no Democratic candidate on ballot), so two-party Dem/Rep margin shift is not applicable.`
              : `Sub-state county shift data is not reported for ${STATE_NAMES[postal]}.`;
          }
        } else if (ds === "g26") {
          if (!stateRaceByPostal[postal]) {
            relevant = false;
            shortTag = "No 2026 Governor Election";
            reason = `${STATE_NAMES[postal]} is not holding a gubernatorial election in 2026.`;
          } else if (effectiveMode === "shift" && !stateHasShift[postal]) {
            relevant = false;
            shortTag = "No Two-Party Shift Data";
            reason = `Two-party county shift data is not applicable for ${STATE_NAMES[postal]}.`;
          }
        } else if (ds === "ag26") {
          if (!stateHasVotes[postal]) {
            relevant = false;
            shortTag = "No 2026 Attorney General Race";
            reason = `${STATE_NAMES[postal]} does not have an Attorney General election on the 2026 ballot.`;
          } else if (effectiveMode === "shift" && !stateHasShift[postal]) {
            relevant = false;
            shortTag = "Single-Party / Uncontested Race";
            reason = `${STATE_NAMES[postal]}'s 2026 Attorney General race had no two-party competition.`;
          }
        } else {
          // Historical Senate (s24..s04), House (h26, h24..h04), President (p24..p04), or top26
          if (!stateHasVotes[postal]) {
            relevant = false;
            if (ds.startsWith("s")) {
              shortTag = "No Senate Race in Cycle";
              reason = `${STATE_NAMES[postal]} did not have a U.S. Senate seat on the ballot in this election cycle.`;
            } else if (postal === "DC") {
              shortTag = "Non-Voting Delegate Only";
              reason = `Washington, D.C. does not elect voting members of the U.S. Senate or U.S. House.`;
            } else {
              shortTag = "No Race Data in Cycle";
              reason = `No county returns for this office/cycle in ${STATE_NAMES[postal]}.`;
            }
          } else if (effectiveMode === "shift" && !stateHasShift[postal]) {
            relevant = false;
            shortTag = stateOnlyOneParty[postal]
              ? "Single-Party / Uncontested"
              : "No Two-Party Shift";
            reason = stateOnlyOneParty[postal]
              ? `${STATE_NAMES[postal]} had an uncontested or single-party general election in this cycle, so two-party Dem/Rep shift is not applicable.`
              : `No comparable two-party baseline shift available for ${STATE_NAMES[postal]} in this cycle.`;
          }
        }
      }

      if (!relevant) {
        if (postal === "DC") hasDCInactive = true;
        else inactiveStatesCount++;
      }
      relMap[postal] = { relevant, shortTag, reason };
    }

    const legendInactiveRow = document.getElementById("legend-inactive-row");
    const legendInactiveText = document.getElementById("legend-inactive-text");
    if (legendInactiveRow && legendInactiveText) {
      const totalInactive = inactiveStatesCount + (hasDCInactive ? 1 : 0);
      if (totalInactive === 0) {
        legendInactiveRow.style.display = "none";
      } else {
        legendInactiveRow.style.display = "flex";
        const countLabel =
          inactiveStatesCount > 0 && hasDCInactive
            ? `${inactiveStatesCount} state${inactiveStatesCount === 1 ? "" : "s"} + D.C.`
            : inactiveStatesCount > 0
            ? `${inactiveStatesCount} state${inactiveStatesCount === 1 ? "" : "s"}`
            : "D.C.";

        let whyText = "not on ballot / N/A for map";
        if (effectiveMode === "measures") whyText = "no 2026 statewide ballot measures";
        else if (effectiveMode === "legislatures") whyText = "no 2026 partisan chamber election";
        else if (effectiveMode === "close") whyText = "all federal & gov races called";
        else if (ds === "s26") {
          whyText =
            effectiveMode === "shift"
              ? "no 2026 Senate race (15) or no Dem/Rep contest (3)"
              : "no 2026 U.S. Senate election on ballot";
        } else if (ds === "g26") whyText = "no 2026 Governor election on ballot";
        else if (ds === "ag26") whyText = "no 2026 Attorney General election";
        else if (ds.startsWith("s")) whyText = "no U.S. Senate race in this cycle";

        legendInactiveText.textContent = `Greyed out (${countLabel}): ${whyText}.`;
      }
    }

    return relMap;
  }

  function renderMap() {
    if (!state.topo || !state.countyShifts || state.activeOfficeTab === "all-local") return;

    const tab = state.activeOfficeTab;
    const isPartisan = isPartisanTab(tab);
    const dark = isDark();
    const neutralStateFill = dark ? "#243247" : "#f1f5f9";
    const inactiveStateFill = "url(#pat-inactive-state)";
    const selectedStateFill = dark ? "#334155" : "#e2e8f0";

    const modeCardsEl = document.getElementById("view-mode-cards");
    modeCardsEl.style.display = isPartisan ? "flex" : "none";

    const effectiveMode = isPartisan ? state.mapMode : tab; // 'close' | 'measures' | 'legislatures'
    const isLive26 = isLive2026Dataset(state.mapDataset);

    document.getElementById("ctrl-target-cycle-wrap").style.display = isPartisan ? "flex" : "none";
    document.getElementById("ctrl-baseline-cycle-wrap").style.display =
      isPartisan && effectiveMode === "shift" ? "flex" : "none";
    document.getElementById("ctrl-winner-level-wrap").style.display =
      isPartisan && effectiveMode === "winner" ? "flex" : "none";
    document.getElementById("ctrl-eevp-wrap").style.display =
      isPartisan && effectiveMode === "shift" && isLive26 ? "flex" : "none";

    document.getElementById("legend-shift-content").style.display =
      effectiveMode === "shift" ? "block" : "none";
    document.getElementById("legend-winner-content").style.display =
      effectiveMode === "winner" || !isPartisan ? "block" : "none";
    document.getElementById("legend-forecast-content").style.display =
      effectiveMode === "forecast" ? "block" : "none";

    const dsLabel = CYCLE_LABELS[state.mapDataset] || "2026 Election";
    const baseDesc = getBaselineDescriptionLabel(state.mapDataset, state.baselineCycle);

    configureMapHeaderAndLegend(effectiveMode, dsLabel, baseDesc, isLive26);

    const pathGen = d3.geoPath();
    const apAbbr = state.countyShifts.ap_abbr || {};

    // Precompute state-level lookups
    const stateRaceByPostal = {};
    const raceList =
      state.mapDataset === "g26"
        ? state.overview.governor_races
        : state.mapDataset === "s26"
        ? state.overview.senate_races
        : [];
    for (const r of raceList) {
      stateRaceByPostal[r.state] = r;
    }

    const measuresByState = {};
    for (const m of state.overview.measures_races || []) {
      if (!measuresByState[m.state]) measuresByState[m.state] = [];
      measuresByState[m.state].push(m);
    }

    const legByState = {};
    for (const c of state.overview.chamber_control.state_chambers || []) {
      if (!legByState[c.state]) legByState[c.state] = [];
      legByState[c.state].push(c);
    }

    const uncalledByState = {};
    for (const r of [
      ...state.overview.senate_races,
      ...state.overview.governor_races,
      ...state.overview.house_races
    ]) {
      if (!r.called) {
        if (!uncalledByState[r.state]) uncalledByState[r.state] = [];
        uncalledByState[r.state].push(r);
      }
    }

    state.stateRelevanceMap = computeStateRelevanceMap(
      effectiveMode,
      stateRaceByPostal,
      measuresByState,
      legByState,
      uncalledByState
    );

    const isHistoricalCountyWinner =
      effectiveMode === "winner" &&
      (state.winnerLevel === "county" || !isLive26 || state.mapDataset === "h26" || state.mapDataset === "ag26");

    // 1. Render Base States Layer
    const gStates = gMap.select(".layer-states");
    gStates
      .selectAll("path.state-fill")
      .data(state.stateFeatures, (d) => d.id)
      .join("path")
      .attr("class", (d) => {
        const postal = d.properties.postal;
        const rel = state.stateRelevanceMap[postal];
        return rel && !rel.relevant ? "state-fill state-inactive" : "state-fill";
      })
      .attr("d", pathGen)
      .attr("fill", (d) => {
        const postal = d.properties.postal;
        const rel = state.stateRelevanceMap[postal];
        if (rel && !rel.relevant) {
          return inactiveStateFill;
        }
        if (effectiveMode === "winner" && !isHistoricalCountyWinner) {
          return getStateWinnerFill(postal, stateRaceByPostal[postal], inactiveStateFill);
        }
        if (effectiveMode === "measures") {
          return getMeasuresStateFill(postal, measuresByState[postal], inactiveStateFill);
        }
        if (effectiveMode === "legislatures") {
          return getLegislatureStateFill(postal, legByState[postal], inactiveStateFill);
        }
        if (effectiveMode === "close") {
          return getCloseStateFill(postal, uncalledByState[postal], inactiveStateFill);
        }
        if (state.selectedState !== "ALL" && postal === state.selectedState) {
          return selectedStateFill;
        }
        return neutralStateFill;
      })
      .attr("opacity", (d) => {
        const postal = d.properties.postal;
        if (state.selectedState !== "ALL" && postal !== state.selectedState) {
          return 0.4;
        }
        return 1;
      })
      .on("mousemove", (event, d) => {
        const postal = d.properties.postal;
        if (effectiveMode === "measures") {
          showMeasuresStateTooltip(event, postal, measuresByState[postal]);
        } else if (effectiveMode === "legislatures") {
          showLegislaturesStateTooltip(event, postal, legByState[postal]);
        } else if (effectiveMode === "close") {
          showCloseStateTooltip(event, postal, uncalledByState[postal]);
        } else if (effectiveMode === "winner" && !isHistoricalCountyWinner) {
          showStateTooltip(event, postal, stateRaceByPostal[postal]);
        }
      })
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => {
        const postal = d.properties.postal;
        if (postal) selectStateFilter(postal);
      });

    // 2. Render Counties Layer
    const gCounties = gMap.select(".layer-counties");
    gCounties
      .selectAll("path.county-path")
      .data(state.countyFeatures, (d) => d.id)
      .join("path")
      .attr("class", "county-path")
      .attr("d", pathGen)
      .style("pointer-events", isPartisan ? "auto" : "none")
      .attr("fill", (d) => {
        if (!isHistoricalCountyWinner) return "transparent";
        const cData = state.countyShifts.counties[d.id];
        if (!cData) return "transparent";
        const rel = state.stateRelevanceMap[cData.state];
        if (rel && !rel.relevant) return "transparent";
        const rec = cData[state.mapDataset];
        if (!rec || !rec.v) return "transparent";
        return getMarginColor(rec.m);
      })
      .attr(
        "stroke",
        isHistoricalCountyWinner
          ? dark
            ? "rgba(15,23,42,0.45)"
            : "rgba(255,255,255,0.28)"
          : dark
          ? "rgba(255,255,255,0.03)"
          : "rgba(0,0,0,0.03)"
      )
      .on("mousemove", (event, d) => {
        if (!isPartisan) return;
        const cData = state.countyShifts.counties[d.id];
        if (cData) showCountyTooltip(event, cData);
      })
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => {
        const cData = state.countyShifts.counties[d.id];
        if (cData) {
          state.inspectedCountyFips = d.id;
          renderCountyInspectorDrawer(cData);
        }
      });

    // 3. State Borders Mesh
    const gBorders = gMap.select(".layer-state-borders");
    gBorders.selectAll("*").remove();
    gBorders
      .append("path")
      .datum(topojson.mesh(state.topo, state.topo.objects.states, (a, b) => a !== b))
      .attr("class", "state-border-mesh")
      .attr("d", pathGen);

    // 4. Render Shift Arrows OR Forecast Bubbles
    const gArrows = gMap.select(".layer-arrows");
    gArrows.selectAll("*").remove();

    const gBubbles = gMap.select(".layer-bubbles");
    gBubbles.selectAll("*").remove();

    const arrowsData = [];
    const bubblesData = [];
    const shiftsList = [];
    let demShiftCount = 0;
    let gopShiftCount = 0;
    let totalVotesInView = 0;
    let totalRemVotes = 0;
    let weightedShiftNum = 0;
    let weightedShiftDen = 0;

    if (isPartisan) {
      for (const [fips, cData] of Object.entries(state.countyShifts.counties)) {
        if (state.selectedState !== "ALL" && cData.state !== state.selectedState) {
          continue;
        }
        const rec = cData[state.mapDataset];
        if (!rec || !rec.v) continue;

        totalVotesInView += rec.v || 0;
        totalRemVotes += rec.rem || 0;
        const centroid = state.countyCentroids[fips];
        if (!centroid) continue;

        if (rec.rem > 100) {
          bubblesData.push({ fips, cData, rec, cx: centroid[0], cy: centroid[1] });
        }

        const eevpOk = !isLive26 || (rec.eevp !== undefined ? rec.eevp >= state.minEevp : true);
        if (eevpOk) {
          const shift = computeCountyShift(cData, state.mapDataset, state.baselineCycle);
          if (shift !== null && !Number.isNaN(shift)) {
            shiftsList.push(shift);
            weightedShiftNum += shift * rec.v;
            weightedShiftDen += rec.v;
            if (shift > 0) demShiftCount++;
            else if (shift < 0) gopShiftCount++;

            arrowsData.push({
              fips,
              cData,
              rec,
              shift,
              cx: centroid[0],
              cy: centroid[1]
            });
          }
        }
      }
    }

    if (effectiveMode === "shift") {
      arrowsData.sort((a, b) => Math.abs(a.shift) - Math.abs(b.shift));
      const demArrowColor = dark ? "#38bdf8" : "#1b6ec2";
      const gopArrowColor = dark ? "#f87171" : "#c9312b";

      gArrows
        .selectAll("path.shift-arrow")
        .data(arrowsData, (d) => d.fips)
        .join("path")
        .attr("class", "shift-arrow")
        .attr("d", (d) => buildArrowPath(d.cx, d.cy, d.shift))
        .attr("fill", (d) => (d.shift >= 0 ? demArrowColor : gopArrowColor))
        .attr("opacity", dark ? 0.9 : 0.86)
        .on("mousemove", (event, d) => showCountyTooltip(event, d.cData))
        .on("mouseleave", hideTooltip)
        .on("click", (event, d) => {
          if (d.cData) {
            state.inspectedCountyFips = d.fips;
            renderCountyInspectorDrawer(d.cData);
          }
        });
    } else if (effectiveMode === "forecast") {
      bubblesData.sort((a, b) => b.rec.rem - a.rec.rem);
      const rScale = d3.scaleSqrt().domain([0, 150000]).range([1.5, 22]).clamp(true);

      gBubbles
        .selectAll("circle.rem-bubble")
        .data(bubblesData, (d) => d.fips)
        .join("circle")
        .attr("class", "rem-bubble")
        .attr("cx", (d) => d.cx)
        .attr("cy", (d) => d.cy)
        .attr("r", (d) => rScale(d.rec.rem))
        .attr("fill", (d) =>
          d.rec.m >= 0 ? "rgba(59,130,246,0.55)" : "rgba(239,68,68,0.55)"
        )
        .attr("stroke", (d) => (d.rec.m >= 0 ? "#60a5fa" : "#f87171"))
        .attr("stroke-width", 1)
        .style("cursor", "pointer")
        .on("mousemove", (event, d) => showCountyTooltip(event, d.cData))
        .on("mouseleave", hideTooltip)
        .on("click", (event, d) => {
          if (d.cData) {
            state.inspectedCountyFips = d.fips;
            renderCountyInspectorDrawer(d.cData);
          }
        });
    }

    // 5. Render State Labels Layer
    const gLabels = gMap.select(".layer-labels");
    const skipSmallLabels = new Set(["DC", "RI", "DE", "CT", "NJ", "MD", "MA", "NH", "VT", "HI"]);
    const labelFeatures = state.stateFeatures.filter((sf) => {
      const p = sf.properties.postal;
      return p && state.stateCentroids[p] && !skipSmallLabels.has(p);
    });

    gLabels
      .selectAll("text.state-label")
      .data(labelFeatures, (d) => d.properties.postal)
      .join("text")
      .attr("class", (d) => {
        const rel = state.stateRelevanceMap[d.properties.postal];
        return rel && !rel.relevant ? "state-label state-label-inactive" : "state-label";
      })
      .attr("x", (d) => state.stateCentroids[d.properties.postal][0])
      .attr("y", (d) => state.stateCentroids[d.properties.postal][1])
      .text((d) => apAbbr[d.properties.postal] || d.properties.postal);

    const weightedMeanShift = weightedShiftDen > 0 ? weightedShiftNum / weightedShiftDen : null;

    // 6. Update KPI Strip under Map
    updateMapKpis(
      effectiveMode,
      shiftsList,
      weightedMeanShift,
      demShiftCount,
      gopShiftCount,
      totalVotesInView,
      totalRemVotes,
      isLive26,
      baseDesc,
      measuresByState,
      legByState,
      uncalledByState
    );
  }

  function configureMapHeaderAndLegend(effectiveMode, dsLabel, baseDesc, isLive26) {
    const hEl = document.getElementById("map-heading-text");
    const subEl = document.getElementById("map-subheading-text");
    const wHead = document.getElementById("legend-winner-heading");
    const wLabels = document.getElementById("legend-winner-labels");
    const wNote = document.getElementById("legend-winner-note");

    if (effectiveMode === "shift") {
      hEl.textContent = `Shift in Margin: ${baseDesc} → ${dsLabel}`;
      subEl.textContent =
        `Blue arrows (↖) show counties shifting toward Democrats; red arrows (↗) show counties shifting toward Republicans compared with ${baseDesc}. Tap any county arrow for its 2004–2026 history & Census demographics.`;
      document.getElementById("legend-shift-note").textContent = isLive26
        ? `Compared with ${baseDesc} in counties with ≥${state.minEevp}% estimated votes reported.`
        : `Compared with ${baseDesc} across all reporting counties with two-party competition.`;
    } else if (effectiveMode === "winner") {
      const isCounty = state.winnerLevel === "county" || !isLive26 || state.mapDataset === "h26";
      hEl.textContent = `${dsLabel} Results — By ${isCounty ? "County Two-Party Vote Margin" : "State Winner & Call Status"}`;
      subEl.textContent =
        "Solid colors indicate called winners or county margins; striped patterns indicate current leader in uncalled races.";
      wHead.textContent = "MARGIN / CALL STATUS";
      wLabels.innerHTML = "<span>Dem.</span><span>Rep.</span>";
      wNote.textContent = "Tap or click any county or state to inspect detailed returns & demographics.";
    } else if (effectiveMode === "forecast") {
      hEl.textContent = `${dsLabel} — Remaining Uncounted Votes & Live Forecast`;
      subEl.textContent =
        "Circle sizes show where uncounted ballots remain across counties, colored by current 2026 vote margin.";
    } else if (effectiveMode === "close") {
      hEl.textContent = "Too Close to Call — States with Uncalled Federal & Governor Races";
      subEl.textContent =
        "Highlighted states still have uncalled U.S. Senate, U.S. House, or Governor races. Click any state to inspect its razor-thin races.";
      wHead.textContent = "UNCALLED RACES";
      wLabels.innerHTML = "<span>Dem. Lead</span><span>Rep. Lead</span>";
      wNote.textContent = "States shaded by party leading in their closest uncalled race.";
    } else if (effectiveMode === "measures") {
      hEl.textContent = "2026 Statewide Ballot Measures & Constitutional Amendments by State";
      subEl.textContent =
        "States colored by majority Yes (Approved) vs. No (Rejected) across their 2026 statewide ballot measures. Click any state to inspect its measures.";
      wHead.textContent = "BALLOT MEASURES";
      wLabels.innerHTML = "<span style='color:var(--yes-main)'>Yes Majority</span><span style='color:var(--no-main)'>No Majority</span>";
      wNote.textContent = "Green states have a majority of 2026 measures passing (Yes); red/amber states have more failing (No).";
    } else if (effectiveMode === "legislatures") {
      hEl.textContent = "2026 State Legislative Chamber Control Map";
      subEl.textContent =
        "States colored by 2026 party control across their State Senate and State House/Assembly chambers. Click any state to view chamber tallies.";
      wHead.textContent = "CHAMBER CONTROL";
      wLabels.innerHTML = "<span>Dem. Control</span><span>Rep. Control</span>";
      wNote.textContent = "Purple indicates split legislative chambers between parties.";
    }
  }

  function buildArrowPath(cx, cy, shift) {
    const absShift = Math.abs(shift);
    if (absShift < 0.15) return "";

    const len = Math.min(42, Math.max(4.5, absShift * 1.45));
    const angleDeg = shift >= 0 ? -152 : -28;
    const rad = (angleDeg * Math.PI) / 180;
    const ux = Math.cos(rad);
    const uy = Math.sin(rad);
    const px = -uy;
    const py = ux;

    const tipX = cx + ux * len;
    const tipY = cy + uy * len;

    const headLen = Math.min(5.2, Math.max(3.0, len * 0.34));
    const headHalfW = headLen * 0.56;
    const shaftHalfW = 0.72;

    const baseX = tipX - ux * headLen;
    const baseY = tipY - uy * headLen;

    const p1x = cx + px * shaftHalfW;
    const p1y = cy + py * shaftHalfW;
    const p2x = baseX + px * shaftHalfW;
    const p2y = baseY + py * shaftHalfW;
    const p3x = baseX + px * headHalfW;
    const p3y = baseY + py * headHalfW;
    const p4x = baseX - px * headHalfW;
    const p4y = baseY - py * headHalfW;
    const p5x = baseX - px * shaftHalfW;
    const p5y = baseY - py * shaftHalfW;
    const p6x = cx - px * shaftHalfW;
    const p6y = cy - py * shaftHalfW;

    return `M${p1x.toFixed(1)},${p1y.toFixed(1)}L${p2x.toFixed(1)},${p2y.toFixed(1)}L${p3x.toFixed(1)},${p3y.toFixed(1)}L${tipX.toFixed(1)},${tipY.toFixed(1)}L${p4x.toFixed(1)},${p4y.toFixed(1)}L${p5x.toFixed(1)},${p5y.toFixed(1)}L${p6x.toFixed(1)},${p6y.toFixed(1)}Z`;
  }

  function getStateWinnerFill(postal, race, neutralFill) {
    if (state.mapDataset === "h26") return neutralFill;
    const dark = isDark();
    if (!race) {
      return neutralFill;
    }
    const party = race.winner_party || race.leader_party;
    if (race.called) {
      if (party === "DEM") return dark ? "#2563eb" : "#1b6ec2";
      if (party === "GOP") return dark ? "#dc2626" : "#c9312b";
      return "#7c3aed";
    } else {
      if (party === "DEM") return "url(#pat-dem-lead)";
      if (party === "GOP") return "url(#pat-gop-lead)";
      return "#d97706";
    }
  }

  function getMeasuresStateFill(postal, list, neutralFill) {
    if (!list || !list.length) return neutralFill;
    let yes = 0, no = 0;
    for (const m of list) {
      const p = m.winner_party || m.leader_party;
      if (p === "YES") yes++;
      else if (p === "NO") no++;
    }
    if (yes > no) return isDark() ? "#15803d" : "#22c55e";
    if (no > yes) return isDark() ? "#b91c1c" : "#ef4444";
    return "#d97706";
  }

  function getLegislatureStateFill(postal, list, neutralFill) {
    if (!list || !list.length) return neutralFill;
    let dem = 0, gop = 0;
    for (const c of list) {
      if (c.dem_winner || c.dem_seats > c.gop_seats) dem++;
      else if (c.gop_winner || c.gop_seats > c.dem_seats) gop++;
    }
    if (dem > 0 && gop === 0) return isDark() ? "#2563eb" : "#1b6ec2";
    if (gop > 0 && dem === 0) return isDark() ? "#dc2626" : "#c9312b";
    return "#7c3aed";
  }

  function getCloseStateFill(postal, list, neutralFill) {
    if (!list || !list.length) return neutralFill;
    const sorted = [...list].sort((a, b) => a.top_margin_pct - b.top_margin_pct);
    const closest = sorted[0];
    if (closest.leader_party === "DEM") return "url(#pat-dem-lead)";
    if (closest.leader_party === "GOP") return "url(#pat-gop-lead)";
    return "#d97706";
  }

  function getMarginColor(margin) {
    if (margin >= 25) return "#1e40af";
    if (margin >= 10) return "#2563eb";
    if (margin >= 3) return "#60a5fa";
    if (margin > 0) return "#93c5fd";
    if (margin <= -25) return "#991b1b";
    if (margin <= -10) return "#dc2626";
    if (margin <= -3) return "#f87171";
    return "#fca5a5";
  }

  function updateMapKpis(
    effectiveMode,
    shiftsList,
    weightedMeanShift,
    demCount,
    gopCount,
    totalVotesInView,
    totalRemVotes,
    isLive26,
    baseDesc,
    measuresByState,
    legByState,
    uncalledByState
  ) {
    const l1 = document.getElementById("kpi-label-1");
    const l2 = document.getElementById("kpi-label-2");
    const l3 = document.getElementById("kpi-label-3");
    const l4 = document.getElementById("kpi-label-4");
    const l5 = document.getElementById("kpi-label-5");

    const v1 = document.getElementById("kpi-dem-counties");
    const v2 = document.getElementById("kpi-gop-counties");
    const v3 = document.getElementById("kpi-median-shift");
    const v4 = document.getElementById("kpi-mean-shift");
    const v5 = document.getElementById("kpi-rem-votes");

    if (effectiveMode === "measures") {
      const allM = state.overview.measures_races || [];
      const statesWithM = Object.keys(measuresByState).length;
      const yesCount = allM.filter((m) => (m.winner_party || m.leader_party) === "YES").length;
      const noCount = allM.filter((m) => (m.winner_party || m.leader_party) === "NO").length;
      const calledM = allM.filter((m) => m.called).length;
      l1.textContent = "Measures Passing (Yes)";
      v1.textContent = `${yesCount} (${((100 * yesCount) / Math.max(1, allM.length)).toFixed(1)}%)`;
      v1.className = "kpi-val yes-text";
      l2.textContent = "Measures Failing (No)";
      v2.textContent = `${noCount} (${((100 * noCount) / Math.max(1, allM.length)).toFixed(1)}%)`;
      v2.className = "kpi-val no-text";
      l3.textContent = "States with 2026 Measures";
      v3.textContent = `${statesWithM} states`;
      v3.className = "kpi-val";
      l4.textContent = "Called Measures";
      v4.textContent = `${calledM} of ${allM.length}`;
      v4.className = "kpi-val";
      l5.textContent = "Local Referendums (civicAPI)";
      v5.textContent = "2,322";
      return;
    }

    if (effectiveMode === "legislatures") {
      const chs = state.overview.chamber_control.state_chambers || [];
      let demBoth = 0, gopBoth = 0, splitSt = 0;
      for (const list of Object.values(legByState)) {
        const d = list.filter((c) => c.dem_winner || c.dem_seats > c.gop_seats).length;
        const r = list.filter((c) => c.gop_winner || c.gop_seats > c.dem_seats).length;
        if (d > 0 && r === 0) demBoth++;
        else if (r > 0 && d === 0) gopBoth++;
        else if (d > 0 && r > 0) splitSt++;
      }
      l1.textContent = "Dem-Controlled States";
      v1.textContent = `${demBoth} states`;
      v1.className = "kpi-val dem-text";
      l2.textContent = "Rep-Controlled States";
      v2.textContent = `${gopBoth} states`;
      v2.className = "kpi-val gop-text";
      l3.textContent = "Split-Chamber States";
      v3.textContent = `${splitSt} states`;
      v3.className = "kpi-val";
      l4.textContent = "Total Chambers Tracked";
      v4.textContent = `${chs.length} chambers`;
      v4.className = "kpi-val";
      l5.textContent = "Total State Leg. Races";
      v5.textContent = "5,758";
      return;
    }

    if (effectiveMode === "close") {
      const statesCnt = Object.keys(uncalledByState).length;
      const senU = state.overview.senate_races.filter((r) => !r.called).length;
      const houseU = state.overview.house_races.filter((r) => !r.called).length;
      const govU = state.overview.governor_races.filter((r) => !r.called).length;
      l1.textContent = "Uncalled U.S. Senate";
      v1.textContent = `${senU} (MS, AK)`;
      v1.className = "kpi-val dem-text";
      l2.textContent = "Uncalled U.S. House";
      v2.textContent = `${houseU} districts`;
      v2.className = "kpi-val gop-text";
      l3.textContent = "Uncalled Governors";
      v3.textContent = `${govU} states`;
      v3.className = "kpi-val";
      l4.textContent = "States with Uncalled Races";
      v4.textContent = `${statesCnt} states`;
      v4.className = "kpi-val";
      l5.textContent = "Razor-Thin (≤0.5% margin)";
      v5.textContent = "12 federal races";
      return;
    }

    // Partisan / Historical KPIs
    l1.textContent = "Counties Shifting Dem. (↖)";
    l2.textContent = "Counties Shifting Rep. (↗)";
    l3.textContent = `Median Shift vs. ${baseDesc.split("(")[0].trim()}`;
    l4.textContent = `Vote-Weighted Shift`;
    l5.textContent = isLive26 ? "Est. Remaining Votes in View" : "Total Votes in View";

    const totalShiftCounties = demCount + gopCount;
    const demPct = totalShiftCounties > 0 ? ((100 * demCount) / totalShiftCounties).toFixed(1) : "0.0";
    const gopPct = totalShiftCounties > 0 ? ((100 * gopCount) / totalShiftCounties).toFixed(1) : "0.0";

    v1.textContent = `${fmtInt(demCount)} (${demPct}%)`;
    v1.className = "kpi-val dem-text";
    v2.textContent = `${fmtInt(gopCount)} (${gopPct}%)`;
    v2.className = "kpi-val gop-text";

    if (shiftsList.length > 0) {
      const sorted = [...shiftsList].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      const median =
        sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;

      v3.textContent =
        median >= 0 ? `↖ Dem +${median.toFixed(1)} pts` : `↗ Rep +${Math.abs(median).toFixed(1)} pts`;
      v3.className = `kpi-val ${median >= 0 ? "dem-text" : "gop-text"}`;

      const wm = weightedMeanShift !== null ? weightedMeanShift : 0;
      v4.textContent =
        wm >= 0 ? `↖ Dem +${wm.toFixed(1)} pts` : `↗ Rep +${Math.abs(wm).toFixed(1)} pts`;
      v4.className = `kpi-val ${wm >= 0 ? "dem-text" : "gop-text"}`;
    } else {
      v3.textContent = "—";
      v4.textContent = "—";
    }

    v5.textContent = fmtInt(isLive26 ? totalRemVotes : totalVotesInView);
  }

  // =========================================================================
  // TOOLTIPS & MOBILE/CLICK COUNTY INSPECTOR DRAWER
  // =========================================================================
  function showCountyTooltip(event, cData) {
    const tt = document.getElementById("map-tooltip");
    const rec = cData[state.mapDataset];
    const { key: baseKey, rec: baseRec, label: baseLabel } = resolveBaselineKeyAndRecord(
      cData,
      state.mapDataset,
      state.baselineCycle
    );

    if (!rec && !baseRec) {
      hideTooltip();
      return;
    }

    const rel = state.stateRelevanceMap[cData.state];
    const eevpText =
      rec && rec.eevp !== undefined
        ? `${rec.eevp}% reported`
        : rel && !rel.relevant
        ? rel.shortTag
        : CYCLE_LABELS[state.mapDataset] || "";
    const shift = computeCountyShift(cData, state.mapDataset, state.baselineCycle);
    let shiftBannerHtml = "";
    if (shift !== null) {
      const isDem = shift >= 0;
      shiftBannerHtml = `
        <div class="tt-shift-banner ${isDem ? "tt-shift-dem" : "tt-shift-gop"}">
          <span>Shift vs. ${baseLabel.split("(")[0].trim()}:</span>
          <span>${isDem ? "↖ Dem +" + shift.toFixed(1) : "↗ Rep +" + Math.abs(shift).toFixed(1)} pts</span>
        </div>
      `;
    } else if (rel && !rel.relevant) {
      shiftBannerHtml = `
        <div class="tt-inactive-badge">
          <strong>Greyed Out — ${rel.shortTag}</strong>
          ${rel.reason}
        </div>
      `;
    }

    const dem = cData.dem;
    const demSummary = dem
      ? `<div style="margin-top:6px;padding-top:5px;border-top:1px solid var(--border-light);font-size:11px;color:var(--text-secondary);">
           <strong>${dem.urb}</strong> · BA+: ${dem.ba}% · Inc: $${fmtInt(dem.inc)} · White NH: ${dem.wnh}% · Black: ${dem.blk}% · Hisp: ${dem.hisp}%
         </div>`
      : "";

    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${cData.name} County, ${cData.state}</span>
        <span class="tt-rep">${eevpText}</span>
      </div>
      ${shiftBannerHtml}
      <table class="tt-table">
        <thead>
          <tr>
            <th>Election Cycle</th>
            <th class="num">Dem.</th>
            <th class="num">Rep.</th>
            <th class="num">Margin</th>
          </tr>
        </thead>
        <tbody>
          ${
            rec
              ? `<tr>
                  <td><strong>${(CYCLE_LABELS[state.mapDataset] || state.mapDataset).split("(")[0].trim()}</strong></td>
                  <td class="num">${rec.d.toFixed(1)}%</td>
                  <td class="num">${rec.r.toFixed(1)}%</td>
                  <td class="num"><strong>${fmtMargin(rec.m)}</strong></td>
                </tr>`
              : ""
          }
          ${
            !rec && cData.g26
              ? `<tr>
                  <td><strong>2026 Governor (${cData.g26.eevp}% rep)</strong></td>
                  <td class="num">${cData.g26.d.toFixed(1)}%</td>
                  <td class="num">${cData.g26.r.toFixed(1)}%</td>
                  <td class="num"><strong>${fmtMargin(cData.g26.m)}</strong></td>
                </tr>`
              : ""
          }
          ${
            !rec && cData.h26
              ? `<tr>
                  <td><strong>2026 U.S. House (${cData.h26.eevp}% rep)</strong></td>
                  <td class="num">${cData.h26.d.toFixed(1)}%</td>
                  <td class="num">${cData.h26.r.toFixed(1)}%</td>
                  <td class="num"><strong>${fmtMargin(cData.h26.m)}</strong></td>
                </tr>`
              : ""
          }
          ${
            baseRec && baseKey !== state.mapDataset
              ? `<tr>
                  <td>${baseLabel.split("(")[0].trim()}</td>
                  <td class="num">${baseRec.d.toFixed(1)}%</td>
                  <td class="num">${baseRec.r.toFixed(1)}%</td>
                  <td class="num">${fmtMargin(baseRec.m)}</td>
                </tr>`
              : ""
          }
          ${
            cData.p24 && baseKey !== "p24" && state.mapDataset !== "p24"
              ? `<tr>
                  <td>2024 Pres</td>
                  <td class="num">${cData.p24.d.toFixed(1)}%</td>
                  <td class="num">${cData.p24.r.toFixed(1)}%</td>
                  <td class="num">${fmtMargin(cData.p24.m)}</td>
                </tr>`
              : ""
          }
        </tbody>
      </table>
      ${demSummary}
      <div style="margin-top:4px;font-size:10.5px;color:var(--accent-blue);font-weight:600;">
        Click/tap county for full 2004–2026 history &amp; Census profile →
      </div>
    `;

    positionTooltip(event, tt);
  }

  function renderCountyInspectorDrawer(cData) {
    const drawer = document.getElementById("county-inspector-drawer");
    if (!drawer || !cData) return;
    drawer.style.display = "block";

    const stName = STATE_NAMES[cData.state] || cData.state;
    const dem = cData.dem || {};
    const blurbHtml = dem.txt
      ? `<p class="cid-blurb">${dem.txt}</p>`
      : `<p class="cid-blurb">2004–2026 County Election Returns &amp; U.S. Census Demographic Profile</p>`;

    const formatCycleChip = (key, shortLabel) => {
      const r = cData[key];
      if (!r || !r.v) return "";
      const cls = r.m >= 0 ? "dem" : "gop";
      return `<span class="hist-pill ${cls}" title="${CYCLE_LABELS[key] || key}: Dem ${r.d}% vs Rep ${r.r}% (${fmtInt(r.v)} votes)"><strong>${shortLabel}:</strong> ${fmtMargin(r.m)}</span>`;
    };

    const presChips = [
      formatCycleChip("p24", "'24"),
      formatCycleChip("p20", "'20"),
      formatCycleChip("p16", "'16"),
      formatCycleChip("p12", "'12"),
      formatCycleChip("p08", "'08"),
      formatCycleChip("p04", "'04")
    ].filter(Boolean).join("");

    const senChips = [
      formatCycleChip("s26", "'26"),
      formatCycleChip("s24", "'24"),
      formatCycleChip("s22", "'22"),
      formatCycleChip("s20", "'20"),
      formatCycleChip("s18", "'18"),
      formatCycleChip("s16", "'16"),
      formatCycleChip("s14", "'14"),
      formatCycleChip("s12", "'12"),
      formatCycleChip("s10", "'10"),
      formatCycleChip("s08", "'08"),
      formatCycleChip("s06", "'06"),
      formatCycleChip("s04", "'04")
    ].filter(Boolean).join("");

    const houseChips = [
      formatCycleChip("h26", "'26"),
      formatCycleChip("h24", "'24"),
      formatCycleChip("h22", "'22"),
      formatCycleChip("h20", "'20"),
      formatCycleChip("h18", "'18"),
      formatCycleChip("h16", "'16"),
      formatCycleChip("h14", "'14"),
      formatCycleChip("h12", "'12"),
      formatCycleChip("h10", "'10"),
      formatCycleChip("h08", "'08"),
      formatCycleChip("h06", "'06"),
      formatCycleChip("h04", "'04")
    ].filter(Boolean).join("");

    drawer.innerHTML = `
      <div class="cid-header">
        <div>
          <div class="cid-title">${cData.name} County, ${stName} (FIPS ${cData.fips})</div>
          ${blurbHtml}
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <button type="button" class="btn-secondary" id="cid-btn-focus-state">Filter to ${stName} Races</button>
          <button type="button" class="cid-close-btn" id="cid-btn-close">× Close</button>
        </div>
      </div>

      <div class="cid-grid">
        <div class="cid-box">
          <h4>U.S. Census County Demographics</h4>
          <div class="cid-dem-pills">
            ${dem.urb ? `<span class="cid-dem-pill">Type: <strong>${dem.urb}</strong></span>` : ""}
            ${dem.pop ? `<span class="cid-dem-pill">2020 Pop: <strong>${fmtInt(dem.pop)}</strong></span>` : ""}
            ${dem.dens ? `<span class="cid-dem-pill">Density: <strong>${fmtInt(Math.round(dem.dens))}/sq mi</strong></span>` : ""}
            ${dem.ba !== undefined ? `<span class="cid-dem-pill">Bachelor's+: <strong>${dem.ba}%</strong></span>` : ""}
            ${dem.inc ? `<span class="cid-dem-pill">Median Income: <strong>$${fmtInt(dem.inc)}</strong></span>` : ""}
            ${dem.home ? `<span class="cid-dem-pill">Homeownership: <strong>${dem.home}%</strong></span>` : ""}
            ${dem.age65 ? `<span class="cid-dem-pill">Age 65+: <strong>${dem.age65}%</strong></span>` : ""}
          </div>
          <div class="cid-dem-pills" style="margin-bottom:0;">
            ${dem.wnh !== undefined ? `<span class="cid-dem-pill">White (NH): <strong>${dem.wnh}%</strong></span>` : ""}
            ${dem.blk !== undefined ? `<span class="cid-dem-pill">Black: <strong>${dem.blk}%</strong></span>` : ""}
            ${dem.hisp !== undefined ? `<span class="cid-dem-pill">Hispanic: <strong>${dem.hisp}%</strong></span>` : ""}
            ${dem.asn !== undefined ? `<span class="cid-dem-pill">Asian: <strong>${dem.asn}%</strong></span>` : ""}
            ${dem.nat !== undefined ? `<span class="cid-dem-pill">Native: <strong>${dem.nat}%</strong></span>` : ""}
          </div>
        </div>

        <div class="cid-box">
          <h4>Presidential History (2004–2024)</h4>
          <div class="cid-hist-chips">${presChips || "No county presidential returns"}</div>
          <h4 style="margin-top:10px;">U.S. Senate History (2004–2026)</h4>
          <div class="cid-hist-chips">${senChips || "No county Senate returns"}</div>
        </div>

        <div class="cid-box">
          <h4>U.S. House History (2004–2026)</h4>
          <div class="cid-hist-chips">${houseChips || "No county House returns"}</div>
          ${
            cData.g26
              ? `<h4 style="margin-top:10px;">2026 Governor</h4>
                 <div class="cid-hist-chips">${formatCycleChip("g26", "'26 Gov")} ${formatCycleChip("g24", "'24 Gov")}</div>`
              : ""
          }
        </div>
      </div>
    `;

    const closeBtn = document.getElementById("cid-btn-close");
    if (closeBtn) {
      closeBtn.addEventListener("click", () => {
        state.inspectedCountyFips = null;
        drawer.style.display = "none";
      });
    }
    const focusBtn = document.getElementById("cid-btn-focus-state");
    if (focusBtn) {
      focusBtn.addEventListener("click", () => {
        selectStateFilter(cData.state);
      });
    }
  }

  // =========================================================================
  // DEMOGRAPHIC BREAKDOWNS ENGINE (Live Vote-Weighted Coalition Analysis!)
  // =========================================================================
  function renderDemographicsSection() {
    if (!state.countyShifts) return;
    const targetCycle = state.mapDataset;
    const baselinePref = state.baselineCycle;
    const isLive26 = isLive2026Dataset(targetCycle);
    const targetLabel = CYCLE_LABELS[targetCycle] || targetCycle;
    const baseDesc = getBaselineDescriptionLabel(targetCycle, baselinePref);
    const scopeLabel =
      state.selectedState === "ALL"
        ? "All Reporting States"
        : `${STATE_NAMES[state.selectedState] || state.selectedState} (${state.selectedState})`;

    document.getElementById("demographics-heading").textContent =
      `Demographic & Community Breakdown: ${targetLabel}`;
    document.getElementById("demographics-scope-pill").textContent =
      `Scope: ${scopeLabel}`;
    document.getElementById("demographics-baseline-pill").textContent =
      `Shift Baseline: ${baseDesc}`;

    const mkBucket = (id, label) => ({
      id,
      label,
      counties: 0,
      demV: 0,
      gopV: 0,
      totV: 0,
      shiftWeightedNum: 0,
      shiftWeightedDen: 0
    });

    const urbBuckets = [
      mkBucket("Urban", "Urban Core Counties"),
      mkBucket("Suburban", "Suburban Counties"),
      mkBucket("Small Metro/Town", "Small Metro & Town Counties"),
      mkBucket("Rural", "Rural Counties")
    ];
    const urbMap = Object.fromEntries(urbBuckets.map((b) => [b.id, b]));

    const eduBuckets = [
      mkBucket("ba_high", "High College (≥ 35% Bachelor's+)"),
      mkBucket("ba_um", "Upper-Middle College (25%–34.9% BA+)"),
      mkBucket("ba_ml", "Moderate College (18%–24.9% BA+)"),
      mkBucket("ba_low", "Non-College / Working Class (< 18% BA+)")
    ];

    const incBuckets = [
      mkBucket("inc_high", "Higher Income (≥ $70,000 Median)"),
      mkBucket("inc_um", "Upper-Middle Income ($55,000–$69,999)"),
      mkBucket("inc_mid", "Middle Income ($45,000–$54,999)"),
      mkBucket("inc_low", "Lower Income (< $45,000)")
    ];

    const raceBuckets = [
      mkBucket("r_blk", "Majority / High-Black Counties (≥ 40% Black)"),
      mkBucket("r_hisp", "Majority / High-Hispanic Counties (≥ 40% Hispanic)"),
      mkBucket("r_div", "Diverse Multi-Ethnic Counties (< 65% White NH)"),
      mkBucket("r_mix", "Mixed White-Majority (65%–81.9% White NH)"),
      mkBucket("r_wnh", "Predominantly White Counties (≥ 82% White NH)")
    ];

    const feedBucket = (b, rec, shift) => {
      if (!b) return;
      b.counties++;
      const dv = (rec.d / 100) * rec.v;
      const rv = (rec.r / 100) * rec.v;
      b.demV += dv;
      b.gopV += rv;
      b.totV += rec.v;
      if (shift !== null && !Number.isNaN(shift)) {
        b.shiftWeightedNum += shift * rec.v;
        b.shiftWeightedDen += rec.v;
      }
    };

    for (const cData of Object.values(state.countyShifts.counties)) {
      if (state.selectedState !== "ALL" && cData.state !== state.selectedState) continue;
      const dem = cData.dem;
      const rec = cData[targetCycle];
      if (!dem || !rec || !rec.v || rec.op) continue;
      if (isLive26 && rec.eevp !== undefined && rec.eevp < state.minEevp) continue;

      const shift = computeCountyShift(cData, targetCycle, baselinePref);

      // 1. Urbanicity
      feedBucket(urbMap[dem.urb] || urbMap.Rural, rec, shift);

      // 2. Education
      const ba = dem.ba || 0;
      if (ba >= 35) feedBucket(eduBuckets[0], rec, shift);
      else if (ba >= 25) feedBucket(eduBuckets[1], rec, shift);
      else if (ba >= 18) feedBucket(eduBuckets[2], rec, shift);
      else feedBucket(eduBuckets[3], rec, shift);

      // 3. Income
      const inc = dem.inc || 0;
      if (inc >= 70000) feedBucket(incBuckets[0], rec, shift);
      else if (inc >= 55000) feedBucket(incBuckets[1], rec, shift);
      else if (inc >= 45000) feedBucket(incBuckets[2], rec, shift);
      else feedBucket(incBuckets[3], rec, shift);

      // 4. Race / Ethnicity
      if ((dem.blk || 0) >= 40) feedBucket(raceBuckets[0], rec, shift);
      else if ((dem.hisp || 0) >= 40) feedBucket(raceBuckets[1], rec, shift);
      else if ((dem.wnh || 0) < 65) feedBucket(raceBuckets[2], rec, shift);
      else if ((dem.wnh || 0) < 82) feedBucket(raceBuckets[3], rec, shift);
      else feedBucket(raceBuckets[4], rec, shift);
    }

    const renderGroupCard = (title, sub, buckets) => {
      const rowsHtml = buckets
        .filter((b) => b.counties > 0 && b.totV > 0)
        .map((b) => {
          const dPct = (100 * b.demV) / b.totV;
          const rPct = (100 * b.gopV) / b.totV;
          const oPct = Math.max(0, 100 - dPct - rPct);
          const margin = dPct - rPct;
          const wShift = b.shiftWeightedDen > 0 ? b.shiftWeightedNum / b.shiftWeightedDen : null;

          const shiftChipHtml =
            wShift !== null
              ? `<span class="shift-chip ${wShift >= 0 ? "dem" : "gop"}">${
                  wShift >= 0 ? "↖ D+" + wShift.toFixed(1) : "↗ R+" + Math.abs(wShift).toFixed(1)
                } pts</span>`
              : "";

          return `
            <div class="dem-cohort-row">
              <div class="dem-cohort-top">
                <div>
                  <span class="dem-cohort-name">${b.label}</span>
                  <span class="dem-cohort-meta">(${fmtInt(b.counties)} counties · ${fmtInt(Math.round(b.totV))} votes)</span>
                </div>
                <div class="dem-cohort-metrics">
                  <span class="dem-text">D ${dPct.toFixed(1)}%</span>
                  <span class="gop-text">R ${rPct.toFixed(1)}%</span>
                  <strong class="${margin >= 0 ? "dem-text" : "gop-text"}">${fmtMargin(margin)}</strong>
                  ${shiftChipHtml}
                </div>
              </div>
              <div class="dem-bar-track">
                <div class="dem-bar-d" style="width:${dPct.toFixed(1)}%"></div>
                <div class="dem-bar-o" style="width:${oPct.toFixed(1)}%"></div>
                <div class="dem-bar-r" style="width:${rPct.toFixed(1)}%"></div>
                <div class="dem-bar-midline" title="50% Midline"></div>
              </div>
            </div>
          `;
        })
        .join("");

      return `
        <div class="dem-card">
          <div class="dem-card-title">${title}</div>
          <div class="dem-card-sub">${sub}</div>
          <div class="dem-cohort-list">
            ${rowsHtml || `<div style="font-size:12px;color:var(--text-secondary);">No reporting counties in current filter.</div>`}
          </div>
        </div>
      `;
    };

    const grid = document.getElementById("demographics-grid");
    grid.innerHTML = [
      renderGroupCard(
        "By Urbanicity & Community Density",
        "Vote-weighted margin & shift across Urban Core, Suburban, Small Metro/Town, and Rural counties",
        urbBuckets
      ),
      renderGroupCard(
        "By Educational Attainment (% Bachelor's Degree+)",
        "Vote-weighted margin & shift by county college graduation rate (U.S. Census)",
        eduBuckets
      ),
      renderGroupCard(
        "By Median Household Income",
        "Vote-weighted margin & shift across county household income tiers (U.S. Census)",
        incBuckets
      ),
      renderGroupCard(
        "By Racial & Ethnic Composition",
        "Vote-weighted margin & shift across county racial/ethnic profiles (U.S. Census)",
        raceBuckets
      )
    ].join("");
  }

  function showStateTooltip(event, postal, race) {
    const tt = document.getElementById("map-tooltip");
    const stName = STATE_NAMES[postal] || postal;
    const rel = state.stateRelevanceMap[postal];
    if (!race) {
      tt.innerHTML = `
        <div class="tt-header">
          <span class="tt-title">${stName}</span>
          <span class="tt-rep">${rel && rel.shortTag ? rel.shortTag : "Not on ballot"}</span>
        </div>
        <div class="tt-inactive-badge">
          <strong>Greyed Out — ${rel && rel.shortTag ? rel.shortTag : "No Race on Ballot"}</strong>
          ${rel && rel.reason ? rel.reason : `No race in ${stName} for this map view.`}
        </div>
        <div style="font-size:11.5px;color:var(--text-secondary);">Click state to inspect U.S. House &amp; local races in ${stName}.</div>
      `;
      positionTooltip(event, tt);
      return;
    }

    const c1 = race.candidates[0] || {};
    const c2 = race.candidates[1] || {};
    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${stName} — ${race.office}</span>
        <span class="tt-rep">${race.eevp}% rep</span>
      </div>
      <div style="font-size:12px;margin-bottom:6px;font-weight:700;color:${race.called ? "var(--yes-main)" : "#f59e0b"}">
        ${race.called ? `✓ Called for ${c1.name} (${c1.party})` : `Too Close to Call · ${c1.name} leads by ${race.top_margin_pct.toFixed(2)}%`}
      </div>
      <table class="tt-table">
        <tbody>
          <tr>
            <td><strong>${c1.name || "—"} (${c1.party || ""})</strong></td>
            <td class="num">${fmtInt(c1.votes || 0)}</td>
            <td class="num"><strong>${fmtPct(c1.percent)}</strong></td>
          </tr>
          ${
            c2.name
              ? `<tr>
                  <td>${c2.name} (${c2.party || ""})</td>
                  <td class="num">${fmtInt(c2.votes || 0)}</td>
                  <td class="num">${fmtPct(c2.percent)}</td>
                </tr>`
              : ""
          }
        </tbody>
      </table>
    `;
    positionTooltip(event, tt);
  }

  function showMeasuresStateTooltip(event, postal, list) {
    const tt = document.getElementById("map-tooltip");
    const stName = STATE_NAMES[postal] || postal;
    if (!list || !list.length) {
      tt.innerHTML = `
        <div class="tt-header"><span class="tt-title">${stName}</span><span class="tt-rep">No 2026 Measures</span></div>
        <div class="tt-inactive-badge"><strong>Greyed Out — No Statewide Ballot Measures</strong>${stName} has no statewide ballot measures on the 2026 ballot.</div>
      `;
      positionTooltip(event, tt);
      return;
    }
    const rows = list
      .slice(0, 5)
      .map((m) => {
        const c1 = m.candidates[0] || {};
        return `<tr><td>${m.seat || m.office}</td><td class="num"><strong>${c1.name || ""} (${fmtPct(c1.percent)})</strong></td></tr>`;
      })
      .join("");
    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${stName} Ballot Measures</span>
        <span class="tt-rep">${list.length} measures</span>
      </div>
      <table class="tt-table"><tbody>${rows}</tbody></table>
      <div style="margin-top:6px;font-size:11px;color:var(--text-secondary);">Click state to filter ballot measure cards below.</div>
    `;
    positionTooltip(event, tt);
  }

  function showLegislaturesStateTooltip(event, postal, list) {
    const tt = document.getElementById("map-tooltip");
    const stName = STATE_NAMES[postal] || postal;
    if (!list || !list.length) {
      tt.innerHTML = `
        <div class="tt-header"><span class="tt-title">${stName}</span><span class="tt-rep">No Chamber Election</span></div>
        <div class="tt-inactive-badge"><strong>Greyed Out — No 2026 Chamber Election</strong>${stName} does not hold regular partisan state legislative chamber elections in 2026.</div>
      `;
      positionTooltip(event, tt);
      return;
    }
    const rows = list
      .map(
        (c) =>
          `<tr><td><strong>${c.office}</strong></td><td class="num dem-text">Dem: ${c.dem_seats}</td><td class="num gop-text">Rep: ${c.gop_seats}</td></tr>`
      )
      .join("");
    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${stName} Legislature</span>
        <span class="tt-rep">${list.length} chambers</span>
      </div>
      <table class="tt-table"><tbody>${rows}</tbody></table>
    `;
    positionTooltip(event, tt);
  }

  function showCloseStateTooltip(event, postal, list) {
    const tt = document.getElementById("map-tooltip");
    const stName = STATE_NAMES[postal] || postal;
    if (!list || !list.length) {
      tt.innerHTML = `
        <div class="tt-header"><span class="tt-title">${stName}</span><span class="tt-rep">All Races Called</span></div>
        <div class="tt-inactive-badge"><strong>Greyed Out — All Races Called</strong>All 2026 U.S. Senate, U.S. House, and Governor races in ${stName} have been called.</div>
      `;
      positionTooltip(event, tt);
      return;
    }
    const rows = list
      .slice(0, 5)
      .map((r) => {
        const c1 = r.candidates[0] || {};
        return `<tr><td><strong>${r.office === "U.S. House" ? r.seat : r.office}</strong></td><td class="num">${c1.last_name || c1.name} (${c1.party})</td><td class="num">+${r.top_margin_pct.toFixed(2)}%</td></tr>`;
      })
      .join("");
    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${stName} Uncalled Races</span>
        <span class="tt-rep">${list.length} uncalled</span>
      </div>
      <table class="tt-table"><tbody>${rows}</tbody></table>
    `;
    positionTooltip(event, tt);
  }

  function positionTooltip(event, tt) {
    tt.style.display = "block";
    const container = document.getElementById("map-svg-container");
    const rect = container.getBoundingClientRect();
    let x = event.clientX - rect.left + 16;
    let y = event.clientY - rect.top + 16;
    if (x + 290 > rect.width) x = Math.max(10, event.clientX - rect.left - 295);
    if (y + 180 > rect.height) y = Math.max(10, event.clientY - rect.top - 185);
    tt.style.left = `${x}px`;
    tt.style.top = `${y}px`;
  }

  function hideTooltip() {
    const tt = document.getElementById("map-tooltip");
    if (tt) tt.style.display = "none";
  }

  // =========================================================================
  // LIVE FORECAST & SEAT FLIPS PANEL
  // =========================================================================
  function renderForecastPanel() {
    const panel = document.getElementById("forecast-panel");
    const show = isPartisanTab(state.activeOfficeTab) && state.mapMode === "forecast";
    panel.style.display = show ? "block" : "none";
    if (!show) return;

    const cc = state.overview.chamber_control;
    const senProbs = (cc.senate.seat_probabilities || [])
      .map(
        (p) =>
          `<div style="display:flex;justify-content:space-between;font-size:12.5px;padding:3px 0;border-bottom:1px solid var(--border-light);">
             <span><strong>${p.DEM} Dem. / ${p.GOP} Rep.</strong></span>
             <span>${(p.prop_sims * 100).toFixed(1)}% probability</span>
           </div>`
      )
      .join("");

    const flippedSen = state.overview.senate_races.filter(
      (r) => r.party_flip || (r.incumbent_party && (r.winner_party || r.leader_party) !== r.incumbent_party)
    );
    const flippedHouse = state.overview.house_races.filter(
      (r) => r.party_flip || (r.incumbent_party && (r.winner_party || r.leader_party) !== r.incumbent_party)
    );

    const grid = document.getElementById("forecast-grid");
    grid.innerHTML = `
      <div class="forecast-box">
        <h3>U.S. Senate Model Seat Probabilities</h3>
        ${senProbs || "<p>Model complete — 33 of 35 seats called.</p>"}
      </div>
      <div class="forecast-box">
        <h3>Senate Seats Flipping Party (${flippedSen.length})</h3>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px;">
          ${flippedSen
            .map(
              (r) =>
                `<span class="rc-badge ${
                  (r.winner_party || r.leader_party) === "DEM" ? "badge-flip-dem" : "badge-flip-gop"
                }">${r.state}: ${r.incumbent_party} → ${r.winner_party || r.leader_party}</span>`
            )
            .join("")}
        </div>
      </div>
      <div class="forecast-box">
        <h3>U.S. House Flipped / Flipping Districts (${flippedHouse.length})</h3>
        <div style="display:flex;flex-wrap:wrap;gap:5px;max-height:110px;overflow-y:auto;">
          ${flippedHouse
            .slice(0, 36)
            .map(
              (r) =>
                `<span class="rc-badge ${
                  (r.winner_party || r.leader_party) === "DEM" ? "badge-flip-dem" : "badge-flip-gop"
                }">${r.state}-${r.seat_number || r.seat}: ${r.incumbent_party}→${r.winner_party || r.leader_party}</span>`
            )
            .join("")}
        </div>
      </div>
    `;
  }

  // =========================================================================
  // GOOGLE SEARCH-STYLE RACE CARDS EXPLORER (With 20-Year Race Histories!)
  // =========================================================================
  async function renderRaceExplorer() {
    const ov = state.overview;
    if (!ov) return;

    const civicTypeSel = document.getElementById("filter-civic-type");
    civicTypeSel.style.display = state.activeOfficeTab === "all-local" ? "inline-block" : "none";

    const banner = document.getElementById("selected-state-banner");
    if (state.selectedState !== "ALL") {
      banner.style.display = "flex";
      const stName = STATE_NAMES[state.selectedState] || state.selectedState;
      const stCounts = ov.summary_counts.states_index[state.selectedState] || { total: 0, called: 0 };
      document.getElementById("banner-state-name").textContent = `${stName} (${state.selectedState})`;
      document.getElementById("banner-state-summary").textContent =
        `${fmtInt(stCounts.total)} total federal, state & local races on the 2026 ballot (${fmtInt(stCounts.called)} called)`;
    } else {
      banner.style.display = "none";
    }

    let items = [];
    let isCivicFormat = false;
    let heading = "";

    if (state.activeOfficeTab === "senate" || (state.activeOfficeTab === "demographics" && state.mapDataset.startsWith("s"))) {
      items = [...ov.senate_races];
      heading = "U.S. Senate Races (With 2004–2024 Same-Seat & Presidential History)";
    } else if (state.activeOfficeTab === "house" || (state.activeOfficeTab === "demographics" && state.mapDataset.startsWith("h"))) {
      items = [...ov.house_races];
      heading = "U.S. House of Representatives (435 Districts · Multi-Cycle History)";
    } else if (state.activeOfficeTab === "governor" || (state.activeOfficeTab === "demographics" && state.mapDataset.startsWith("g"))) {
      items = [...ov.governor_races];
      heading = "State Gubernatorial Races (With 2006–2024 Governor History)";
    } else if (state.activeOfficeTab === "demographics") {
      items = [...ov.senate_races];
      heading = "U.S. Senate Races (With 2004–2024 Same-Seat & Presidential History)";
    } else if (state.activeOfficeTab === "measures") {
      items = [...ov.measures_races];
      heading = "Statewide Ballot Measures & Constitutional Amendments";
    } else if (state.activeOfficeTab === "legislatures") {
      renderStateLegislaturesGrid(ov.chamber_control.state_chambers);
      return;
    } else if (state.activeOfficeTab === "close") {
      items = [
        ...ov.senate_races.filter((r) => !r.called),
        ...ov.governor_races.filter((r) => !r.called),
        ...ov.house_races.filter((r) => !r.called)
      ];
      heading = "Too Close to Call — Uncalled Federal & Governor Races";
    } else if (state.activeOfficeTab === "all-local") {
      isCivicFormat = true;
      if (state.selectedState !== "ALL") {
        items = await ensureStateCivicRacesLoaded(state.selectedState);
        heading = `All 2026 Ballot Races in ${STATE_NAMES[state.selectedState] || state.selectedState}`;
      } else {
        items = [...(ov.close_races_all_levels || [])];
        heading = "Closest Uncalled Federal, State & Local Races Nationwide (Select Any State for All 39,472 Races)";
      }
    }

    if (state.selectedState !== "ALL" && !isCivicFormat) {
      items = items.filter((r) => r.state === state.selectedState);
    }

    if (isCivicFormat && state.civicTypeFilter !== "ALL") {
      items = items.filter((r) => r.type === state.civicTypeFilter);
    }

    if (state.callStatusFilter === "UNCALLED") {
      items = items.filter((r) => !r.called);
    } else if (state.callStatusFilter === "CLOSE_2") {
      items = items.filter((r) => {
        const m = isCivicFormat ? r.m_pct : r.top_margin_pct;
        return m <= 2.0;
      });
    } else if (state.callStatusFilter === "CALLED") {
      items = items.filter((r) => r.called);
    } else if (state.callStatusFilter === "FLIPPED" && !isCivicFormat) {
      items = items.filter(
        (r) =>
          r.party_flip ||
          (r.incumbent_party in { DEM: 1, GOP: 1 } &&
            (r.winner_party || r.leader_party) in { DEM: 1, GOP: 1 } &&
            (r.winner_party || r.leader_party) !== r.incumbent_party)
      );
    }

    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      items = items.filter((r) => {
        if (isCivicFormat) {
          const candNames = (r.cands || []).map((c) => c.n).join(" ");
          const hay = `${r.state} ${STATE_NAMES[r.state] || ""} ${r.type} ${r.name} ${r.municipality || ""} ${r.district || ""} ${candNames}`.toLowerCase();
          return hay.includes(q);
        } else {
          const candNames = (r.candidates || []).map((c) => c.name).join(" ");
          const hay = `${r.state} ${STATE_NAMES[r.state] || ""} ${r.office} ${r.seat} ${r.nyt_id} ${candNames} ${r.ballot_measure_text || ""}`.toLowerCase();
          return hay.includes(q);
        }
      });
    }

    items.sort((a, b) => {
      const mA = isCivicFormat ? a.m_pct : a.top_margin_pct;
      const mB = isCivicFormat ? b.m_pct : b.top_margin_pct;
      const vA = isCivicFormat ? a.tot_v : a.total_votes;
      const vB = isCivicFormat ? b.tot_v : b.total_votes;

      if (state.sortBy === "margin-asc") return mA - mB;
      if (state.sortBy === "votes-desc") return vB - vA;
      if (state.sortBy === "state-asc") {
        return String(a.state).localeCompare(String(b.state)) || mA - mB;
      }
      if (state.sortBy === "shift-apples-desc" && !isCivicFormat) {
        const sA = Math.abs(a.shift_vs_same_office ?? a.shift_vs_house_2024 ?? 0);
        const sB = Math.abs(b.shift_vs_same_office ?? b.shift_vs_house_2024 ?? 0);
        return sB - sA;
      }
      if (state.sortBy === "shift-desc" && !isCivicFormat) {
        const sA = Math.abs(a.shift_vs_pres_2024 ?? a.shift_vs_house_2024 ?? 0);
        const sB = Math.abs(b.shift_vs_pres_2024 ?? b.shift_vs_house_2024 ?? 0);
        return sB - sA;
      }
      if (a.called !== b.called) return a.called ? 1 : -1;
      return mA - mB;
    });

    document.getElementById("explorer-heading").textContent = heading;
    document.getElementById("explorer-count-badge").textContent = `${fmtInt(items.length)} races`;

    const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
    if (state.page > totalPages) state.page = 1;
    const startIdx = (state.page - 1) * state.pageSize;
    const pageItems = items.slice(startIdx, startIdx + state.pageSize);

    const grid = document.getElementById("races-grid");
    if (pageItems.length === 0) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:28px;text-align:center;color:var(--text-secondary);">No races match the current filters. Try clearing your search or selecting "All 50 States".</div>`;
    } else {
      grid.innerHTML = pageItems
        .map((r) => (isCivicFormat ? renderCivicRaceCard(r) : renderNytRaceCard(r)))
        .join("");
    }

    const pagBar = document.getElementById("pagination-bar");
    if (totalPages > 1) {
      pagBar.style.display = "flex";
      document.getElementById("page-info").textContent =
        `Page ${state.page} of ${totalPages} (${fmtInt(items.length)} races)`;
      document.getElementById("page-prev").disabled = state.page <= 1;
      document.getElementById("page-next").disabled = state.page >= totalPages;
    } else {
      pagBar.style.display = "none";
    }
  }

  function renderNytRaceCard(r) {
    const stName = STATE_NAMES[r.state] || r.state;
    const isMeasure = state.activeOfficeTab === "measures" || r.ballot_measure_text;
    const title =
      r.office === "U.S. House"
        ? `${stName} ${r.seat || `District ${r.seat_number}`}`
        : r.office === "U.S. Senate" || r.office === "Governor"
        ? `${stName} — ${r.office}${r.is_special ? " (Special)" : ""}`
        : `${stName} — ${r.office} ${r.seat || ""}`;

    const winParty = r.winner_party || r.leader_party || "OTH";
    const cardBorderClass = !r.called
      ? "uncalled-card"
      : winParty === "DEM"
      ? "called-dem-card"
      : winParty === "GOP"
      ? "called-gop-card"
      : winParty === "YES"
      ? "called-yes-card"
      : winParty === "NO"
      ? "called-no-card"
      : "";

    const isFlipped =
      !isMeasure &&
      (r.party_flip ||
        (r.incumbent_party in { DEM: 1, GOP: 1 } &&
          winParty in { DEM: 1, GOP: 1 } &&
          winParty !== r.incumbent_party));

    let badgesHtml = "";
    if (isFlipped) {
      badgesHtml += `<span class="rc-badge ${winParty === "DEM" ? "badge-flip-dem" : "badge-flip-gop"}">${
        r.called ? "FLIP" : "LEADING FLIP"
      }: ${r.incumbent_party} → ${winParty}</span>`;
    }
    if (!r.called) {
      badgesHtml += `<span class="rc-badge badge-tctc">Too Close · ±${r.top_margin_pct.toFixed(2)}% (${fmtInt(r.top_margin_votes)}v)</span>`;
    } else {
      const bCls =
        winParty === "DEM"
          ? "badge-called-dem"
          : winParty === "GOP"
          ? "badge-called-gop"
          : winParty === "YES"
          ? "badge-called-yes"
          : winParty === "NO"
          ? "badge-called-no"
          : "";
      badgesHtml += `<span class="rc-badge ${bCls}">✓ Called</span>`;
    }

    const candsHtml = (r.candidates || [])
      .slice(0, 3)
      .map((c) => {
        const avatarHtml = c.img_url
          ? `<img class="cand-avatar" src="${c.img_url}" alt="${c.name}" loading="lazy"/>`
          : "";
        const checkHtml = c.winner
          ? `<span class="win-check ${c.party}" title="Called Winner">✓</span>`
          : "";
        const incText = c.incumbent ? ` <span title="Incumbent" style="color:var(--text-muted);font-size:11px;">(i)</span>` : "";

        return `
          <div class="cand-row ${c.winner ? "cand-winner-winner" : ""}">
            <div class="cand-info-line">
              <div class="cand-left">
                ${avatarHtml}
                ${checkHtml}
                <span class="cand-party-pill pty-${c.party}">${c.party_label}</span>
                <span class="cand-name">${c.name}${incText}</span>
              </div>
              <div class="cand-right">
                <span class="cand-votes">${fmtInt(c.votes)}</span>
                <span class="cand-pct">${fmtPct(c.percent)}</span>
              </div>
            </div>
            <div class="cand-bar-bg">
              <div class="cand-bar-fill fill-${c.party}" style="width:${Math.min(100, c.percent)}%"></div>
            </div>
          </div>
        `;
      })
      .join("");

    let shiftHtml = "";
    let histStripHtml = "";
    if (!isMeasure) {
      const chips = [];
      // 1. Apples-to-Apples Same-Office Shift (e.g. vs 2020 Sen, vs 2022 Gov, vs 2024/2022 House)
      if (r.office === "U.S. House" && r.shift_vs_house_2024 !== null && r.shift_vs_house_2024 !== undefined) {
        const s = r.shift_vs_house_2024;
        chips.push(
          `<span class="shift-chip ${s >= 0 ? "dem" : "gop"}">${
            s >= 0 ? "↖ D+" + s.toFixed(1) : "↗ R+" + Math.abs(s).toFixed(1)
          } vs '24 House</span>`
        );
      } else if (r.shift_vs_same_office !== null && r.shift_vs_same_office !== undefined && r.last_same_office_year) {
        const s = r.shift_vs_same_office;
        const shortYr = String(r.last_same_office_year).slice(2);
        const offShort = r.office === "U.S. Senate" ? "Sen" : r.office === "Governor" ? "Gov" : "House";
        chips.push(
          `<span class="shift-chip ${s >= 0 ? "dem" : "gop"}">${
            s >= 0 ? "↖ D+" + s.toFixed(1) : "↗ R+" + Math.abs(s).toFixed(1)
          } vs '${shortYr} ${offShort}</span>`
        );
      }

      // 2. Shift vs 2024 Pres
      if (r.shift_vs_pres_2024 !== null && r.shift_vs_pres_2024 !== undefined) {
        const sp = r.shift_vs_pres_2024;
        chips.push(
          `<span class="shift-chip ${sp >= 0 ? "dem" : "gop"}">${
            sp >= 0 ? "↖ D+" + sp.toFixed(1) : "↗ R+" + Math.abs(sp).toFixed(1)
          } vs '24 Pres</span>`
        );
      }
      shiftHtml = `<div style="display:flex;flex-wrap:wrap;gap:4px;">${chips.join("")}</div>`;

      // Build 20-year historical strip for this seat/state
      const offHist = r.office_history || {};
      const histYears = Object.keys(offHist)
        .sort((a, b) => Number(b) - Number(a))
        .slice(0, 5);
      if (histYears.length > 0) {
        const pills = histYears
          .map((yr) => {
            const h = offHist[yr];
            const cls = h.m >= 0 ? "dem" : "gop";
            const wn = h.wn ? ` ${h.wn}` : "";
            return `<span class="hist-pill ${cls}" title="${yr} ${r.office}: ${h.wn || h.wp} (${fmtMargin(h.m)})">'${yr.slice(2)}${wn}: ${fmtMargin(h.m)}</span>`;
          })
          .join("");
        histStripHtml = `
          <div class="rc-hist-strip">
            <span class="rc-hist-label">20-Yr Seat History:</span>
            ${pills}
          </div>
        `;
      }
    }

    return `
      <article class="race-card ${cardBorderClass}">
        <div>
          <div class="rc-top">
            <div class="rc-title-group">
              <div class="rc-title">${title}</div>
              <div class="rc-sub">${r.eevp}% Est. Votes Reported · ${fmtInt(r.total_votes)} votes${
      r.remaining_votes > 0 ? ` (${fmtInt(r.remaining_votes)} est. left)` : ""
    }</div>
            </div>
            <div class="rc-badges">${badgesHtml}</div>
          </div>
          ${
            r.ballot_measure_text
              ? `<p style="font-size:12px;color:var(--text-secondary);margin:6px 0 8px;">${r.ballot_measure_text}</p>`
              : `<div style="height:8px"></div>`
          }
          <div class="rc-candidates">${candsHtml}</div>
          ${histStripHtml}
        </div>
        <div class="rc-footer">
          <span>Margin: <strong>${r.top_margin_pct.toFixed(2)}%</strong> (${fmtInt(r.top_margin_votes)}v)</span>
          ${shiftHtml}
        </div>
      </article>
    `;
  }

  function renderCivicRaceCard(r) {
    const candsHtml = (r.cands || [])
      .map((c) => {
        const pNorm =
          c.p === "Democratic"
            ? "DEM"
            : c.p === "Republican"
            ? "GOP"
            : c.n === "Yes"
            ? "YES"
            : c.n === "No"
            ? "NO"
            : "OTH";
        const checkHtml = c.w ? `<span class="win-check ${pNorm}">✓</span>` : "";
        return `
          <div class="cand-row ${c.w ? "cand-winner-winner" : ""}">
            <div class="cand-info-line">
              <div class="cand-left">
                ${checkHtml}
                <span class="cand-party-pill pty-${pNorm}">${(c.p || "NP").slice(0, 3).toUpperCase()}</span>
                <span class="cand-name">${c.n}</span>
              </div>
              <div class="cand-right">
                <span class="cand-votes">${fmtInt(c.v)}</span>
                <span class="cand-pct">${fmtPct(c.pct)}</span>
              </div>
            </div>
            <div class="cand-bar-bg">
              <div class="cand-bar-fill fill-${pNorm}" style="width:${Math.min(100, c.pct || 0)}%"></div>
            </div>
          </div>
        `;
      })
      .join("");

    return `
      <article class="race-card ${r.called ? "" : "uncalled-card"}">
        <div>
          <div class="rc-top">
            <div class="rc-title-group">
              <div class="rc-title">${r.name}</div>
              <div class="rc-sub">${r.state} · ${r.type}${r.municipality ? ` · ${r.municipality}` : ""} · ${r.rep}% reporting</div>
            </div>
            <div class="rc-badges">
              <span class="rc-badge ${r.called ? "badge-called-dem" : "badge-tctc"}">${
      r.called ? "✓ Called" : `±${r.m_pct.toFixed(2)}% (${fmtInt(r.m_v)}v)`
    }</span>
            </div>
          </div>
          <div style="height:8px"></div>
          <div class="rc-candidates">${candsHtml}</div>
        </div>
        <div class="rc-footer">
          <span>Total Votes: <strong>${fmtInt(r.tot_v)}</strong></span>
          <span>civicAPI ID #${r.id}</span>
        </div>
      </article>
    `;
  }

  function renderStateLegislaturesGrid(chambers) {
    let items = [...(chambers || [])];
    if (state.selectedState !== "ALL") {
      items = items.filter((c) => c.state === state.selectedState);
    }
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      items = items.filter((c) =>
        `${c.state} ${STATE_NAMES[c.state] || ""} ${c.office}`.toLowerCase().includes(q)
      );
    }

    document.getElementById("explorer-heading").textContent =
      "State Legislative Chambers Balance of Power (90 Chambers)";
    document.getElementById("explorer-count-badge").textContent = `${items.length} chambers`;
    document.getElementById("pagination-bar").style.display = "none";

    const grid = document.getElementById("races-grid");
    grid.innerHTML = items
      .map((c) => {
        const stName = STATE_NAMES[c.state] || c.state;
        const tot = c.total || 1;
        const demPct = ((100 * c.dem_seats) / tot).toFixed(1);
        const gopPct = ((100 * c.gop_seats) / tot).toFixed(1);
        return `
          <article class="race-card ${c.dem_winner ? "called-dem-card" : c.gop_winner ? "called-gop-card" : ""}">
            <div class="rc-top">
              <div class="rc-title-group">
                <div class="rc-title">${stName} — ${c.office}</div>
                <div class="rc-sub">${c.total} total seats · ${c.called || 0} races called</div>
              </div>
              <div class="rc-badges">
                ${c.dem_flips > 0 ? `<span class="rc-badge badge-flip-dem">Dem +${c.dem_flips}</span>` : ""}
                ${c.gop_flips > 0 ? `<span class="rc-badge badge-flip-gop">Rep +${c.gop_flips}</span>` : ""}
              </div>
            </div>
            <div class="seat-bar-track" style="height:16px;margin:8px 0;">
              <div class="seat-seg seg-dem-solid" style="width:${demPct}%"></div>
              <div class="seat-seg seg-tossup" style="width:${Math.max(0, 100 - demPct - gopPct)}%"></div>
              <div class="seat-seg seg-gop-solid" style="width:${gopPct}%"></div>
            </div>
            <div class="rc-footer">
              <span class="dem-text"><strong>Dem: ${c.dem_seats} seats</strong></span>
              <span>Majority: ${Math.floor(tot / 2) + 1}</span>
              <span class="gop-text"><strong>Rep: ${c.gop_seats} seats</strong></span>
            </div>
          </article>
        `;
      })
      .join("");
  }

  async function ensureStateCivicRacesLoaded(stateCode) {
    if (state.loadedStateCivicRaces[stateCode]) {
      return state.loadedStateCivicRaces[stateCode];
    }
    try {
      const res = await fetch(`site_data/states/${stateCode}.json`);
      if (!res.ok) return [];
      const data = await res.json();
      state.loadedStateCivicRaces[stateCode] = data.races || [];
      return state.loadedStateCivicRaces[stateCode];
    } catch (e) {
      console.error("Failed loading state civic races:", e);
      return [];
    }
  }

  function selectStateFilter(postal) {
    state.selectedState = postal;
    state.page = 1;
    const s1 = document.getElementById("select-state-filter");
    const s2 = document.getElementById("filter-state-inline");
    if (s1) s1.value = postal;
    if (s2) s2.value = postal;
    renderMap();
    if (isPartisanTab(state.activeOfficeTab)) {
      renderDemographicsSection();
    }
    renderRaceExplorer();
  }

  // =========================================================================
  // DEEP-DIVE ANALYSIS & MONEYBALL VIEW (MS PLURALITY / AK RCV / FEC / COHORTS)
  // =========================================================================
  async function ensureAnalysisDataLoaded() {
    if (state.fecMoneyball && state.factionAnalysis && state.breakingPoints) return;
    const qs = `?t=${Date.now()}`;
    const [fec, fac, bp] = await Promise.all([
      fetch(`site_data/fec_moneyball_2026.json${qs}`).then((r) => r.json()),
      fetch(`site_data/faction_analysis_2026.json${qs}`).then((r) => r.json()),
      fetch(`site_data/breaking_points_2026.json${qs}`).then((r) => r.json()),
    ]);
    state.fecMoneyball = fec;
    state.factionAnalysis = fac;
    state.breakingPoints = bp;
  }

  function fmtDollarsM(v) {
    if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
    const n = Number(v);
    if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
    if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
    return `$${n.toFixed(0)}`;
  }

  async function renderAnalysisSection() {
    const container = document.getElementById("analysis-section");
    if (!container) return;
    if (!state.fecMoneyball) {
      container.innerHTML = `<div class="analysis-block"><p>Loading FEC Moneyball, RCV/Plurality simulations, and county cohort data…</p></div>`;
    }
    try {
      await ensureAnalysisDataLoaded();
    } catch (e) {
      console.error("Failed loading analysis JSONs:", e);
      container.innerHTML = `<div class="analysis-block"><p>Error loading analysis datasets.</p></div>`;
      return;
    }

    const ov = state.overview || {};
    const msSen = (ov.senate_races || []).find((r) => r.state === "MS") || {};
    const akSen = (ov.senate_races || []).find((r) => r.state === "AK") || {};
    const akGov = (ov.governor_races || []).find((r) => r.state === "AK") || {};
    const ksGov = (ov.governor_races || []).find((r) => r.state === "KS") || {};

    const msCands = msSen.candidates || [];
    const msColom = msCands.find((c) => c.party === "DEM") || { votes: 466959, percent: 49.05 };
    const msHyde = msCands.find((c) => c.party === "GOP") || { votes: 465023, percent: 48.85 };
    const msPink = msCands.find((c) => c.party !== "DEM" && c.party !== "GOP") || { votes: 20010, percent: 2.10 };
    const msLead = (msColom.votes || 0) - (msHyde.votes || 0);

    const akCands = akSen.candidates || [];
    const akPeltola = akCands.find((c) => c.party === "DEM") || { votes: 102962, percent: 48.17 };
    const akSullivan = akCands.find((c) => c.party === "GOP") || { votes: 102325, percent: 47.88 };
    const akLead = (akPeltola.votes || 0) - (akSullivan.votes || 0);

    const fac = state.factionAnalysis || {};
    const caucusGroups = (fac.house_caucus_comparison_morris_benchmark && fac.house_caucus_comparison_morris_benchmark.groups) || [];
    const h2h = fac.county_head_to_head_live || {};
    const sameBallot = fac.same_ballot_statewide_live || {};

    const bp = state.breakingPoints || {};
    const cohorts = bp.disjoint_county_cohorts || [];
    const pcaDem = (bp.pca_decomposition && bp.pca_decomposition.high_swing_counties_demographic_pca && bp.pca_decomposition.high_swing_counties_demographic_pca.variance_explained_pct) || {};
    const pcaCross = (bp.pca_decomposition && bp.pca_decomposition.cross_ballot_shift_pca && bp.pca_decomposition.cross_ballot_shift_pca.variance_explained_pct) || {};

    container.innerHTML = `
      <!-- 1. MS Plurality Law & Late-Ballot Math + AK Ranked-Choice Voting Simulator -->
      <div class="analysis-block">
        <div class="analysis-block-header">
          <div>
            <h2>1. Uncalled Statewide Legal &amp; Ballot-Math Tracker: Mississippi Plurality vs. Alaska RCV</h2>
            <p class="section-sub">Statutory election rules, late-arriving absentee/affidavit ballot splits, and RCV second-choice transfer thresholds.</p>
          </div>
          <span class="stat-pill">Live Updated · 15-Min Feed</span>
        </div>

        <div class="analysis-grid-2">
          <div class="analysis-subcard">
            <h3>
              <span>Mississippi U.S. Senate (${fmtPct(msSen.eevp || 95.8)} EEVP)</span>
              <span class="rc-badge badge-tctc">Colom +${fmtInt(msLead)} votes</span>
            </h3>
            <div class="analysis-law-callout">
              <strong>Statutory Rule — No General Election Runoff (<code>Miss. Code Ann. § 23-15-605</code>):</strong>
              While Mississippi requires a 50%+1 majority (or runoff) for <em>state executive</em> offices under Miss. Const. § 140 (amended 2020) and for <em>nonpartisan special elections</em> (such as the 2018 Senate special under § 23-15-833), <strong>regularly scheduled U.S. Senate and U.S. House general elections are decided by simple plurality</strong> ("the person having the largest number of votes"). Mississippi also has <strong>no statutory statewide recount mechanism</strong>—meaning whoever leads after timely postmarked absentee ballots (5 business days) and cured affidavit ballots are canvassed wins outright, even under 50%.
            </div>
            <div class="analysis-table-wrap">
              <table class="analysis-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th class="num">Counted Votes</th>
                    <th class="num">Share</th>
                    <th class="num">Wed–Fri Late Split</th>
                    <th class="num">County-Wtd Rem. (+41.7K)</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong class="dem-text">Scott Colom (DEM)</strong></td>
                    <td class="num"><strong>${fmtInt(msColom.votes)}</strong></td>
                    <td class="num"><strong>${Number(msColom.percent).toFixed(2)}%</strong></td>
                    <td class="num dem-text">+4,138 (64.1%)</td>
                    <td class="num dem-text">+22,173 (~489.1K final)</td>
                  </tr>
                  <tr>
                    <td><strong class="gop-text">Cindy Hyde-Smith (GOP)</strong></td>
                    <td class="num">${fmtInt(msHyde.votes)}</td>
                    <td class="num">${Number(msHyde.percent).toFixed(2)}%</td>
                    <td class="num gop-text">+2,245 (34.8%)</td>
                    <td class="num gop-text">+18,744 (~483.8K final)</td>
                  </tr>
                  <tr>
                    <td>Ty Pinkins (IND)</td>
                    <td class="num">${fmtInt(msPink.votes)}</td>
                    <td class="num">${Number(msPink.percent).toFixed(2)}%</td>
                    <td class="num">+75 (1.2%)</td>
                    <td class="num">+808 (80.2% from GOP cos.)</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="analysis-subcard">
            <h3>
              <span>Alaska U.S. Senate &amp; Governor RCV (${fmtPct(akSen.eevp || 74.1)} EEVP)</span>
              <span class="rc-badge badge-tctc">Peltola +${fmtInt(akLead)} votes</span>
            </h3>
            <div class="analysis-law-callout">
              <strong>Alaska Top-Four RCV Dynamics &amp; Same-Name Spoiler Effect:</strong>
              In Round 1 (${fmtPct(akSen.eevp || 74.1)} reporting, ~74.7K late mail/rural bush ballots remaining), <strong>Mary Peltola (DEM, 48.17%)</strong> leads <strong>Sen. Dan Sullivan (GOP, 47.88%)</strong> by <strong>+${fmtInt(akLead)} votes</strong>. The NYT model projects remaining first-choice ballots to expand Peltola's lead to <strong>~+8,042 votes (137.3K vs. 129.2K, 83% win prob)</strong> before RCV transfers. Crucially, the 3.95% third-party pool is split between Republican <strong>Gerald Heikes (2.27%, 4,846v)</strong> and Undeclared candidate <strong>Daniel Sullivan (1.68%, 3,600v)</strong>—whose shared name with incumbent Dan Sullivan created a 3,600-vote ballot confusion pool.
            </div>
            <div class="analysis-table-wrap">
              <table class="analysis-table">
                <thead>
                  <tr>
                    <th>Alaska Race / Candidate</th>
                    <th class="num">Round 1 Votes</th>
                    <th class="num">Round 1 %</th>
                    <th>RCV / Late-Ballot Outlook</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><strong class="dem-text">Sen: Mary Peltola (DEM)</strong></td>
                    <td class="num"><strong>${fmtInt(akPeltola.votes)}</strong></td>
                    <td class="num"><strong>${Number(akPeltola.percent).toFixed(2)}%</strong></td>
                    <td>NYT Est: ~137.3K (+8.0K pre-RCV lead)</td>
                  </tr>
                  <tr>
                    <td><strong class="gop-text">Sen: Dan Sullivan (GOP)</strong></td>
                    <td class="num">${fmtInt(akSullivan.votes)}</td>
                    <td class="num">${Number(akSullivan.percent).toFixed(2)}%</td>
                    <td>Needs >75% of net RCV transfers if trailing by 5K+</td>
                  </tr>
                  <tr>
                    <td>Sen: Gerald Heikes (GOP) &amp; Daniel Sullivan (UDC)</td>
                    <td class="num">8,446</td>
                    <td class="num">3.95%</td>
                    <td>4,846 Heikes (GOP) + 3,600 Daniel Sullivan (UDC)</td>
                  </tr>
                  <tr>
                    <td><strong class="dem-text">Gov: Jonathan Kreiss-Tomkins (DEM)</strong></td>
                    <td class="num"><strong>103,837</strong></td>
                    <td class="num"><strong>49.13%</strong></td>
                    <td>Vs. 3 split GOPs: Wilson 29.2%, Bronson 14.2%, Taylor 7.5%</td>
                  </tr>
                  <tr>
                    <td><strong class="dem-text">KS Gov: Cindy Holscher (DEM)</strong></td>
                    <td class="num"><strong>${fmtInt((ksGov.candidates && ksGov.candidates[0] && ksGov.candidates[0].votes) || 547198)}</strong></td>
                    <td class="num"><strong>50.32%</strong></td>
                    <td>Leads Ty Masterson (GOP, 49.68%) by +7,045v at 98.7% EEVP</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. Interactive FEC Moneyball Explorer (Senate & House) -->
      <div class="analysis-block">
        <div class="analysis-block-header">
          <div>
            <h2>2. 2026 FEC 'Moneyball' &amp; Counterspend Explorer (Candidate + Super PAC IEs)</h2>
            <p class="section-sub">Compare total Pro-Dem and Pro-GOP spending (Candidate Disbursements + Independent Expenditures) against actual 2024→2026 vote shifts and marginal cost per point of swing.</p>
          </div>
          <div class="moneyball-controls">
            <select id="mb-office-select" class="ctrl-select">
              <option value="senate" ${state.moneyballOffice === "senate" ? "selected" : ""}>U.S. Senate (35 Races)</option>
              <option value="house-close" ${state.moneyballOffice === "house-close" ? "selected" : ""}>U.S. House — Closest &amp; Shock Upsets (≤ 3% Margin)</option>
              <option value="house-all" ${state.moneyballOffice === "house-all" ? "selected" : ""}>U.S. House — All 418 Tracked Races</option>
            </select>
            <select id="mb-sort-select" class="ctrl-select">
              <option value="spend-desc" ${state.moneyballSort === "spend-desc" ? "selected" : ""}>Sort: Total Race Spend (High → Low)</option>
              <option value="cost-pt-desc" ${state.moneyballSort === "cost-pt-desc" ? "selected" : ""}>Sort: Pro-Dem $/Pt of Shift (Most Expensive)</option>
              <option value="cost-pt-asc" ${state.moneyballSort === "cost-pt-asc" ? "selected" : ""}>Sort: Pro-Dem $/Pt of Shift (Best Value ROI)</option>
              <option value="margin-asc" ${state.moneyballSort === "margin-asc" ? "selected" : ""}>Sort: Closest 2026 Margin First</option>
              <option value="shift-desc" ${state.moneyballSort === "shift-desc" ? "selected" : ""}>Sort: Largest Pro-Dem Shift vs. 2024</option>
            </select>
            <input type="search" id="mb-search-input" class="search-input" style="min-width:210px;" placeholder="Filter state or candidate…" value="${state.moneyballSearch || ""}" />
          </div>
        </div>
        <div id="moneyball-table-container" class="analysis-table-wrap"></div>
      </div>

      <!-- 3. Ideological Factions & 5-State Same-Ballot Natural Experiments -->
      <div class="analysis-block">
        <div class="analysis-block-header">
          <div>
            <h2>3. Ideological Factions &amp; Same-Ballot Natural Experiments</h2>
            <p class="section-sub">Empirical test of candidate moderation across U.S. House caucuses (controlling for district baseline &amp; spending) and 5 states with simultaneous Governor &amp; Senate races on the same ballot.</p>
          </div>
          <span class="stat-pill">276 / 286 Counties (${h2h.all_5_states_total ? h2h.all_5_states_total.pct : 96.5}%) Won by Mainstream Ticket-Mate</span>
        </div>

        <div class="analysis-grid-2">
          <div class="analysis-subcard">
            <h3>U.S. House Swing vs. 2024 by Caucus (Morris Benchmark)</h3>
            <div class="analysis-table-wrap">
              <table class="analysis-table">
                <thead>
                  <tr>
                    <th>Caucus / Faction</th>
                    <th class="num">N</th>
                    <th class="num">Raw Mean Swing</th>
                    <th class="num">Adjusted Mean (95% CI)</th>
                    <th class="num">Adj. Median Overperf.</th>
                  </tr>
                </thead>
                <tbody>
                  ${caucusGroups
                    .map(
                      (g) => `
                    <tr>
                      <td><strong>${g.group}</strong></td>
                      <td class="num">${g.n}</td>
                      <td class="num dem-text">+${g.raw_mean.toFixed(1)}%</td>
                      <td class="num"><strong>+${g.adjusted_mean.toFixed(1)}%</strong> <span class="rc-sub">[+${g.adj_ci_95[0].toFixed(1)}, +${g.adj_ci_95[1].toFixed(1)}]</span></td>
                      <td class="num ${g.adj_median_overperf >= 0 ? "dem-text" : "gop-text"}"><strong>${g.adj_median_overperf >= 0 ? "+" : ""}${g.adj_median_overperf.toFixed(1)} pts</strong></td>
                    </tr>`
                    )
                    .join("")}
                </tbody>
              </table>
            </div>
          </div>

          <div class="analysis-subcard">
            <h3>5-State Same-Ballot Natural Experiment (Gov vs. Senate)</h3>
            <div class="analysis-table-wrap">
              <table class="analysis-table">
                <thead>
                  <tr>
                    <th>State</th>
                    <th class="num">Gov 2026 Margin (Shift)</th>
                    <th class="num">Sen 2026 Margin (Shift)</th>
                    <th class="num">Ticket Split</th>
                    <th class="num">County Head-to-Head</th>
                  </tr>
                </thead>
                <tbody>
                  ${["MI", "MN", "ME", "NM", "FL"]
                    .map((st) => {
                      const sb = sameBallot[st] || {};
                      const g = sb.governor || {};
                      const s = sb.senate || {};
                      const diff = st === "NM" ? (s.margin || 0) - (g.margin || 0) : (g.margin || 0) - (s.margin || 0);
                      const hKey = st === "NM" ? "NM_sen_vs_gov" : `${st}_gov_vs_sen`;
                      const hh = h2h[hKey] || { wins: 0, total: 0, pct: 0 };
                      return `
                      <tr>
                        <td><strong>${st}</strong></td>
                        <td class="num">${fmtMargin(g.margin)} <span class="rc-sub">(+${(g.shift_24 || 0).toFixed(1)})</span></td>
                        <td class="num">${fmtMargin(s.margin)} <span class="rc-sub">(${(s.shift_24 || 0) >= 0 ? "+" : ""}${(s.shift_24 || 0).toFixed(1)})</span></td>
                        <td class="num dem-text"><strong>+${diff.toFixed(2)} pts</strong></td>
                        <td class="num"><strong>${hh.wins}/${hh.total} cos. (${hh.pct}%)</strong></td>
                      </tr>`;
                    })
                    .join("")}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- 4. Disjoint Breaking Points & County Cohort Analysis -->
      <div class="analysis-block">
        <div class="analysis-block-header">
          <div>
            <h2>4. Disjoint Breaking Points &amp; Cross-Ballot Contagion (3,143 Counties)</h2>
            <p class="section-sub">Demographic PCA shows high-swing counties are split across 3 orthogonal demographic dimensions (PC1=${pcaDem.PC1 || 35.0}%, PC2=${pcaDem.PC2 || 29.9}%, PC3=${pcaDem.PC3 || 21.9}%), yet Cross-Ballot Shift PCA loads ${pcaCross.PC1 || 82.0}% onto a single unified wave.</p>
          </div>
          <span class="stat-pill">Sen↔AG Shift r = +0.862 (1,352 counties)</span>
        </div>

        <div class="analysis-table-wrap">
          <table class="analysis-table">
            <thead>
              <tr>
                <th>County Cohort</th>
                <th>Primary Issue Trigger</th>
                <th class="num">Counties</th>
                <th class="num">2020→2024 Pres</th>
                <th class="num">2016→2018 Midterm</th>
                <th class="num">2024→2026 Top Ticket</th>
                <th class="num">2024→2026 Senate</th>
                <th class="num">2024→2026 State AG</th>
                <th class="num">% Shifting Dem (2026)</th>
              </tr>
            </thead>
            <tbody>
              ${cohorts
                .map((c) => {
                  const sh = c.shifts || {};
                  const p24 = sh.pres_2020_to_2024 || {};
                  const h18 = sh.first_term_midterm_2016_to_2018_house || {};
                  const top26 = sh.top_of_ticket_2024_to_2026 || {};
                  const s26 = sh.us_senate_2024_to_2026 || {};
                  const ag26 = sh.attorney_general_2024_to_2026 || {};
                  return `
                  <tr>
                    <td><strong>${c.cohort_label}</strong></td>
                    <td>${c.primary_issue_trigger}</td>
                    <td class="num">${fmtInt(c.total_counties_in_cohort)}</td>
                    <td class="num ${(p24.mean || 0) >= 0 ? "dem-text" : "gop-text"}">${(p24.mean || 0) >= 0 ? "+" : ""}${(p24.mean || 0).toFixed(2)} pts</td>
                    <td class="num ${(h18.mean || 0) >= 0 ? "dem-text" : "gop-text"}">${(h18.mean || 0) >= 0 ? "+" : ""}${(h18.mean || 0).toFixed(2)} pts</td>
                    <td class="num dem-text"><strong>+${(top26.mean || 0).toFixed(2)} pts</strong></td>
                    <td class="num dem-text">${s26.mean !== undefined ? `+${s26.mean.toFixed(2)} pts` : "—"}</td>
                    <td class="num dem-text">${ag26.mean !== undefined ? `+${ag26.mean.toFixed(2)} pts` : "—"}</td>
                    <td class="num"><strong>${(top26.pct_shifting_dem || 0).toFixed(1)}%</strong></td>
                  </tr>`;
                })
                .join("")}
            </tbody>
          </table>
        </div>
      </div>

      <!-- 5. High-Resolution Live-Updating Research Charts Gallery -->
      <div class="analysis-block">
        <div class="analysis-block-header">
          <div>
            <h2>5. Live-Regenerated Research Charts Gallery (Charts 1–7)</h2>
            <p class="section-sub">Automatically regenerated by the live pipeline as county and statewide vote totals update. Click any chart to open full-resolution PNG in a new tab.</p>
          </div>
        </div>
        <div class="analysis-charts-grid">
          ${[
            ["chart7_senate_moneyball_counterspend.png", "Chart 7: 2026 Senate 'Moneyball' — Diminishing Returns & Endogenous GOP Counterspend"],
            ["chart1_house_carveout.png", "Chart 1: U.S. House 2024→2026 Swing by Ideological Faction (Blue Dogs vs. New Dems vs. CPC)"],
            ["chart2_senate_0for6.png", "Chart 2: U.S. Senate Swing vs. State House Baseline Across Competitive States"],
            ["chart3_same_ballot_natural_experiment.png", "Chart 3: 5-State Same-Ballot Natural Experiment (MI, MN, ME, NM, FL County Head-to-Head)"],
            ["chart4_disjoint_cohorts_2018_vs_2026.png", "Chart 4: Disjoint Breaking Points — 2018 Midterm vs. 2026 Midterm Shifts Across 8 Cohorts"],
            ["chart5_60pct_convergence_ceiling.png", "Chart 5: The 60% Disapproval Convergence — Issue Breaking Points vs. 2026 Electoral Swing"],
            ["chart6_downballot_contagion.png", "Chart 6: Down-Ballot Contagion — U.S. Senate vs. State Attorney General County Shift (r = 0.86)"],
          ]
            .map(
              ([file, title]) => `
            <div class="chart-card">
              <div class="chart-card-title">${title}</div>
              <a href="assets/${file}" target="_blank" rel="noopener">
                <img src="assets/${file}?v=20261106a" alt="${title}" loading="lazy" />
              </a>
            </div>`
            )
            .join("")}
        </div>
      </div>
    `;

    renderMoneyballTable();

    document.getElementById("mb-office-select").addEventListener("change", (e) => {
      state.moneyballOffice = e.target.value;
      renderMoneyballTable();
    });
    document.getElementById("mb-sort-select").addEventListener("change", (e) => {
      state.moneyballSort = e.target.value;
      renderMoneyballTable();
    });
    document.getElementById("mb-search-input").addEventListener("input", (e) => {
      state.moneyballSearch = e.target.value.trim();
      renderMoneyballTable();
    });
  }

  function renderMoneyballTable() {
    const wrap = document.getElementById("moneyball-table-container");
    if (!wrap || !state.fecMoneyball) return;

    let rows = [];
    if (state.moneyballOffice === "senate") {
      rows = (state.fecMoneyball.senate_races || []).slice();
    } else if (state.moneyballOffice === "house-close") {
      rows = (state.fecMoneyball.house_races || []).filter(
        (r) => Math.abs(r.margin_2026 ?? 999) <= 3.0 || ((r.pres_2024_margin ?? 0) <= -15 && (r.margin_2026 ?? -99) > 0)
      );
    } else {
      rows = (state.fecMoneyball.house_races || []).slice();
    }

    const q = (state.moneyballSearch || "").toLowerCase();
    if (q) {
      rows = rows.filter(
        (r) =>
          (r.state || "").toLowerCase().includes(q) ||
          (r.seat || "").toLowerCase().includes(q) ||
          (r.dem_name || "").toLowerCase().includes(q) ||
          (r.gop_name || "").toLowerCase().includes(q)
      );
    }

    const sort = state.moneyballSort;
    rows.sort((a, b) => {
      if (sort === "spend-desc") return (b.total_race_spend || 0) - (a.total_race_spend || 0);
      if (sort === "cost-pt-desc") return (b.total_pro_dem_per_shift_pt || -1) - (a.total_pro_dem_per_shift_pt || -1);
      if (sort === "cost-pt-asc") {
        const av = a.total_pro_dem_per_shift_pt > 0 ? a.total_pro_dem_per_shift_pt : 1e18;
        const bv = b.total_pro_dem_per_shift_pt > 0 ? b.total_pro_dem_per_shift_pt : 1e18;
        return av - bv;
      }
      if (sort === "margin-asc") return Math.abs(a.margin_2026 ?? 999) - Math.abs(b.margin_2026 ?? 999);
      if (sort === "shift-desc") return (b.shift_vs_pres_2024 ?? -999) - (a.shift_vs_pres_2024 ?? -999);
      return 0;
    });

    const displayRows = rows.slice(0, 75);
    wrap.innerHTML = `
      <table class="analysis-table">
        <thead>
          <tr>
            <th>Race</th>
            <th>Dem Candidate vs. GOP Candidate</th>
            <th class="num">2026 Margin</th>
            <th class="num">2024 Pres</th>
            <th class="num">2024→2026 Shift</th>
            <th class="num">Pro-Dem Spend (Cand + IE)</th>
            <th class="num">Pro-GOP Spend (Cand + IE)</th>
            <th class="num">Total Race Spend</th>
            <th class="num">Pro-Dem $/Shift Pt</th>
          </tr>
        </thead>
        <tbody>
          ${displayRows
            .map((r) => {
              const vdiff = (r.dem_votes || 0) - (r.gop_votes || 0);
              const m26 = r.margin_2026;
              const sh = r.shift_vs_pres_2024;
              return `
              <tr>
                <td><strong>${r.state}${r.seat ? " " + r.seat : ""}</strong></td>
                <td><span class="dem-text">${r.dem_name || "—"}</span> vs. <span class="gop-text">${r.gop_name || "—"}</span></td>
                <td class="num ${(m26 || 0) >= 0 ? "dem-text" : "gop-text"}"><strong>${fmtMargin(m26)}</strong> <span class="rc-sub">(${vdiff >= 0 ? "+" : ""}${fmtInt(vdiff)}v)</span></td>
                <td class="num">${fmtMargin(r.pres_2024_margin)}</td>
                <td class="num ${(sh || 0) >= 0 ? "dem-text" : "gop-text"}"><strong>${sh !== null && sh !== undefined ? (sh >= 0 ? "+" : "") + sh.toFixed(2) + " pts" : "—"}</strong></td>
                <td class="num">${fmtDollarsM(r.total_pro_dem_spend)} <span class="rc-sub">(${fmtDollarsM(r.ie_pro_dem_total)} IE)</span></td>
                <td class="num">${fmtDollarsM(r.total_pro_gop_spend)} <span class="rc-sub">(${fmtDollarsM(r.ie_pro_gop_total)} IE)</span></td>
                <td class="num"><strong>${fmtDollarsM(r.total_race_spend)}</strong></td>
                <td class="num"><strong>${r.total_pro_dem_per_shift_pt ? fmtDollarsM(r.total_pro_dem_per_shift_pt) + "/pt" : "—"}</strong></td>
              </tr>`;
            })
            .join("")}
        </tbody>
      </table>
    `;
  }

  // =========================================================================
  // EVENT BINDINGS
  // =========================================================================
  function bindEvents() {
    // Dark / Light Mode Toggle
    const themeBtn = document.getElementById("btn-theme-toggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", toggleTheme);
    }

    // Top Office Tabs
    document.querySelectorAll(".office-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".office-tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const off = btn.getAttribute("data-office");
        state.activeOfficeTab = off;
        state.page = 1;

        const targetSel = document.getElementById("select-target-cycle");
        if (off === "senate") {
          state.mapDataset = "s26";
          if (targetSel) targetSel.value = "s26";
        } else if (off === "house") {
          state.mapDataset = "h26";
          if (targetSel) targetSel.value = "h26";
        } else if (off === "governor") {
          state.mapDataset = "g26";
          if (targetSel) targetSel.value = "g26";
        }

        syncActiveView().then(() => {
          if (off === "demographics") {
            const demEl = document.getElementById("demographics-section");
            if (demEl) demEl.scrollIntoView({ behavior: "smooth" });
          }
        });
      });
    });

    // Target Election Cycle Selector (2004–2026)
    const targetCycleSel = document.getElementById("select-target-cycle");
    if (targetCycleSel) {
      targetCycleSel.addEventListener("change", (e) => {
        state.mapDataset = e.target.value;
        renderBalanceOfPower();
        renderMap();
        renderDemographicsSection();
        renderRaceExplorer();
      });
    }

    // Baseline Comparison Cycle Selector (2004–2024)
    const baselineCycleSel = document.getElementById("select-baseline-cycle");
    if (baselineCycleSel) {
      baselineCycleSel.addEventListener("change", (e) => {
        state.baselineCycle = e.target.value;
        renderMap();
        renderDemographicsSection();
      });
    }

    // Left Overlay Mode Switcher Cards
    document.querySelectorAll(".mode-card").forEach((card) => {
      card.addEventListener("click", () => {
        document.querySelectorAll(".mode-card").forEach((c) => {
          c.classList.remove("active");
          c.setAttribute("aria-selected", "false");
        });
        card.classList.add("active");
        card.setAttribute("aria-selected", "true");
        state.mapMode = card.getAttribute("data-mode");
        renderMap();
        renderForecastPanel();
      });
    });

    // Winner level selector
    document.getElementById("select-winner-level").addEventListener("change", (e) => {
      state.winnerLevel = e.target.value;
      renderMap();
    });

    // Min EEVP selector
    document.getElementById("select-min-eevp").addEventListener("change", (e) => {
      state.minEevp = Number(e.target.value);
      renderMap();
      renderDemographicsSection();
    });

    // State focus selectors (both map & toolbar)
    document.getElementById("select-state-filter").addEventListener("change", (e) => {
      selectStateFilter(e.target.value);
    });
    document.getElementById("filter-state-inline").addEventListener("change", (e) => {
      selectStateFilter(e.target.value);
    });

    // Zoom buttons
    document.getElementById("zoom-in").addEventListener("click", () => {
      svg.transition().duration(250).call(zoomBehavior.scaleBy, 1.5);
    });
    document.getElementById("zoom-out").addEventListener("click", () => {
      svg.transition().duration(250).call(zoomBehavior.scaleBy, 1 / 1.5);
    });
    document.getElementById("zoom-reset").addEventListener("click", () => {
      svg.transition().duration(300).call(zoomBehavior.transform, d3.zoomIdentity);
    });

    // Explorer filters
    document.getElementById("race-search-input").addEventListener("input", (e) => {
      state.searchQuery = e.target.value.trim();
      state.page = 1;
      renderRaceExplorer();
    });

    document.getElementById("filter-call-status").addEventListener("change", (e) => {
      state.callStatusFilter = e.target.value;
      state.page = 1;
      renderRaceExplorer();
    });

    document.getElementById("filter-sort-by").addEventListener("change", (e) => {
      state.sortBy = e.target.value;
      state.page = 1;
      renderRaceExplorer();
    });

    document.getElementById("filter-civic-type").addEventListener("change", (e) => {
      state.civicTypeFilter = e.target.value;
      state.page = 1;
      renderRaceExplorer();
    });

    // Selected state banner buttons
    document.getElementById("btn-clear-state-filter").addEventListener("click", () => {
      selectStateFilter("ALL");
    });

    document.getElementById("btn-load-all-state-local").addEventListener("click", () => {
      document.querySelectorAll(".office-tab").forEach((b) => b.classList.remove("active"));
      const allTab = document.querySelector('.office-tab[data-office="all-local"]');
      if (allTab) allTab.classList.add("active");
      state.activeOfficeTab = "all-local";
      state.page = 1;
      syncActiveView();
    });

    // Pagination buttons
    document.getElementById("page-prev").addEventListener("click", () => {
      if (state.page > 1) {
        state.page--;
        renderRaceExplorer();
        document.getElementById("results-explorer-section").scrollIntoView({ behavior: "smooth" });
      }
    });
    document.getElementById("page-next").addEventListener("click", () => {
      state.page++;
      renderRaceExplorer();
      document.getElementById("results-explorer-section").scrollIntoView({ behavior: "smooth" });
    });

    // Refresh Live Feed button
    document.getElementById("btn-live-refresh").addEventListener("click", () => {
      loadAllData(true);
    });
  }

  document.addEventListener("DOMContentLoaded", init);
})();

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

  // App state
  const state = {
    overview: null,
    countyShifts: null,
    topo: null,
    stateFeatures: [],
    countyFeatures: [],
    countyCentroids: {},
    stateCentroids: {},
    loadedStateCivicRaces: {},

    activeOfficeTab: "senate",      // senate | house | governor | close | measures | legislatures | all-local
    mapMode: "shift",               // shift | winner | forecast
    mapDataset: "s26",              // s26 | h26 | g26 | ag26
    winnerLevel: "state",           // state | county
    minEevp: 95,
    selectedState: "ALL",
    searchQuery: "",
    callStatusFilter: "ALL",
    sortBy: "uncalled-first",
    civicTypeFilter: "ALL",
    page: 1,
    pageSize: 48
  };

  const fmtInt = d3.format(",");
  const fmtPct = (v) => `${Number(v || 0).toFixed(1)}%`;

  let svg, gMap, zoomBehavior;

  async function init() {
    setupMapSvg();
    bindEvents();
    await loadAllData();
  }

  function setupMapSvg() {
    svg = d3.select("#us-election-map");
    svg.selectAll("*").remove();

    // Define diagonal hatch patterns for leading/uncalled states
    const defs = svg.append("defs");

    const mkPattern = (id, bg, stripe) => {
      const p = defs.append("pattern")
        .attr("id", id)
        .attr("patternUnits", "userSpaceOnUse")
        .attr("width", 8)
        .attr("height", 8)
        .attr("patternTransform", "rotate(45)");
      p.append("rect").attr("width", 8).attr("height", 8).attr("fill", bg);
      p.append("line")
        .attr("x1", 0).attr("y1", 0).attr("x2", 0).attr("y2", 8)
        .attr("stroke", stripe).attr("stroke-width", 4);
    };
    mkPattern("pat-dem-lead", "#dbeafe", "#3b82f6");
    mkPattern("pat-gop-lead", "#fee2e2", "#ef4444");

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

  async function loadAllData(bustCache = false) {
    const qs = bustCache ? `?t=${Date.now()}` : "";
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

      if (!state.topo) {
        state.topo = topo;
        prepareGeometries(topo, countyShifts);
        populateStateDropdown(overview);
        populateCivicTypesDropdown(overview);
      }

      updateHeaderMeta();
      renderBalanceOfPower();
      renderMap();
      renderForecastPanel();
      await renderRaceExplorer();
    } catch (err) {
      console.error("Failed loading election data:", err);
      document.getElementById("last-updated-text").textContent =
        "Error loading election data snapshot. Check console.";
    } finally {
      if (btn) btn.disabled = false;
    }
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
  }

  function populateStateDropdown(overview) {
    const sel = document.getElementById("select-state-filter");
    const statesIdx = (overview.summary_counts && overview.summary_counts.states_index) || {};
    const codes = Object.keys(STATE_NAMES).sort((a, b) =>
      STATE_NAMES[a].localeCompare(STATE_NAMES[b])
    );
    sel.innerHTML = `<option value="ALL">All 50 States + D.C.</option>`;
    for (const code of codes) {
      const cnt = statesIdx[code] ? ` (${fmtInt(statesIdx[code].total)} races)` : "";
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = `${STATE_NAMES[code]} (${code})${cnt}`;
      sel.appendChild(opt);
    }
  }

  function populateCivicTypesDropdown(overview) {
    const sel = document.getElementById("filter-civic-type");
    const topTypes = (overview.summary_counts && overview.summary_counts.top_race_types) || [];
    sel.innerHTML = `<option value="ALL">All Office / Ballot Types (39,474)</option>`;
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
      `Snapshot: ${timeStr} · Auto-updating every 5 minutes · ${fmtInt(sc.civic_called_races)} called / ${fmtInt(sc.civic_uncalled_races)} uncalled across all levels`;
    document.getElementById("global-races-pill").textContent =
      `${fmtInt(sc.civic_total_races)} Races · ${fmtInt(sc.counties_tracked)} Counties`;

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
      `${senUncalled + houseUncalled + govUncalled} federal/gov`;
    document.getElementById("tab-badge-measures").textContent =
      `${ov.measures_races.length} statewide`;
    document.getElementById("tab-badge-all").textContent =
      fmtInt(sc.civic_total_races);
  }

  // =========================================================================
  // BALANCE OF POWER BAR (Google Search Top Card)
  // =========================================================================
  function renderBalanceOfPower() {
    const ov = state.overview;
    const cc = ov.chamber_control;

    let chamberKey = "senate";
    if (state.activeOfficeTab === "house") chamberKey = "house";
    else if (state.activeOfficeTab === "governor") chamberKey = "governor";
    else if (state.mapDataset === "h26" && state.activeOfficeTab !== "senate") chamberKey = "house";
    else if (state.mapDataset === "g26" && state.activeOfficeTab !== "senate") chamberKey = "governor";

    const data = cc[chamberKey];
    const total = data.total;

    let demSolid = 0, demLead = 0, gopSolid = 0, gopLead = 0;
    let demSub = "", gopSub = "", title = "", majLabel = "", popVoteText = "";

    if (chamberKey === "senate") {
      demSolid = data.dem_total_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_total_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_no_election} not up · ${data.dem_called} called · ${data.dem_leading} leading`;
      gopSub = `${data.gop_no_election} not up · ${data.gop_called} called · ${data.gop_leading} leading`;
      title = "U.S. SENATE BALANCE OF POWER (100 SEATS)";
      majLabel = "51 for Democratic majority · 50 for Republican control (with VP tiebreaker)";
      document.getElementById("balance-dem-flips").textContent =
        data.dem_flips > 0 ? `+${data.dem_flips} flips` : "0 flips";
      document.getElementById("balance-gop-flips").textContent =
        data.gop_flips > 0 ? `+${data.gop_flips} flips` : "0 flips";
    } else if (chamberKey === "house") {
      demSolid = data.dem_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_called} called · ${data.dem_leading} leading (proj. ${data.dem_projected_total})`;
      gopSub = `${data.gop_called} called · ${data.gop_leading} leading (proj. ${data.gop_projected_total})`;
      title = "U.S. HOUSE BALANCE OF POWER (435 SEATS)";
      majLabel = "218 seats needed for majority";
      document.getElementById("balance-dem-flips").textContent =
        data.dem_flips > 0 ? `+${data.dem_flips} flips` : "0 flips";
      document.getElementById("balance-gop-flips").textContent =
        data.gop_flips > 0 ? `+${data.gop_flips} flips` : "0 flips";
    } else {
      demSolid = data.dem_total_called;
      demLead = data.dem_leading;
      gopSolid = data.gop_total_called;
      gopLead = data.gop_leading;
      demSub = `${data.dem_no_election} not up · ${data.dem_called} called · ${data.dem_leading} leading`;
      gopSub = `${data.gop_no_election} not up · ${data.gop_called} called · ${data.gop_leading} leading`;
      title = "STATE GOVERNORS BALANCE OF POWER (50 STATES)";
      majLabel = "36 states holding gubernatorial elections in 2026";
      document.getElementById("balance-dem-flips").textContent = `Proj: ${data.dem_projected_total}`;
      document.getElementById("balance-gop-flips").textContent = `Proj: ${data.gop_projected_total}`;
    }

    // Check popular vote from model_estimates if available
    if (data.model_estimates && data.model_estimates.length) {
      const demEst = data.model_estimates.find((e) => e.nyt_party_id === "DEM");
      const gopEst = data.model_estimates.find((e) => e.nyt_party_id === "GOP");
      if (demEst && gopEst && demEst.popular_vote && gopEst.popular_vote) {
        const marginPts = ((demEst.voteshare_margin || 0) * 100).toFixed(1);
        popVoteText = `Est. National Popular Vote: Dem. ${fmtInt(demEst.popular_vote)} vs. Rep. ${fmtInt(gopEst.popular_vote)} (${marginPts >= 0 ? "D+" + marginPts : "R+" + Math.abs(marginPts)}%)`;
      }
    }

    document.getElementById("balance-dem-seats").textContent = demSolid;
    document.getElementById("balance-gop-seats").textContent = gopSolid;
    document.getElementById("balance-dem-sub").textContent = demSub;
    document.getElementById("balance-gop-sub").textContent = gopSub;
    document.getElementById("balance-chamber-title").textContent = title;
    document.getElementById("balance-majority-label").textContent = majLabel;
    document.getElementById("balance-pop-vote").textContent = popVoteText;

    const tossup = Math.max(0, total - (demSolid + demLead + gopSolid + gopLead));
    const track = document.getElementById("seat-bar-track");
    const pct = (n) => `${((100 * n) / total).toFixed(2)}%`;

    track.innerHTML = `
      <div class="seat-seg seg-dem-solid" style="width:${pct(demSolid)}" title="Dem Called/Held: ${demSolid}"></div>
      <div class="seat-seg seg-dem-lead" style="width:${pct(demLead)}" title="Dem Leading: ${demLead}"></div>
      <div class="seat-seg seg-tossup" style="width:${pct(tossup)}" title="Other/Tossup: ${tossup}"></div>
      <div class="seat-seg seg-gop-lead" style="width:${pct(gopLead)}" title="Rep Leading: ${gopLead}"></div>
      <div class="seat-seg seg-gop-solid" style="width:${pct(gopSolid)}" title="Rep Called/Held: ${gopSolid}"></div>
    `;
  }

  // =========================================================================
  // INTERACTIVE MAP RENDERING (Shift Arrow Map, Winner Map, Forecast Map)
  // =========================================================================
  function renderMap() {
    if (!state.topo || !state.countyShifts) return;

    const pathGen = d3.geoPath();
    const apAbbr = state.countyShifts.ap_abbr || {};

    // Update visibility of map controls & legend based on mode
    document.getElementById("ctrl-winner-level-wrap").style.display =
      state.mapMode === "winner" ? "flex" : "none";
    document.getElementById("ctrl-eevp-wrap").style.display =
      state.mapMode === "shift" ? "flex" : "none";

    document.getElementById("legend-shift-content").style.display =
      state.mapMode === "shift" ? "block" : "none";
    document.getElementById("legend-winner-content").style.display =
      state.mapMode === "winner" ? "block" : "none";
    document.getElementById("legend-forecast-content").style.display =
      state.mapMode === "forecast" ? "block" : "none";

    const dsNames = {
      s26: "2026 U.S. Senate",
      h26: "2026 U.S. House",
      g26: "2026 Governor",
      ag26: "2026 Attorney General"
    };
    const dsLabel = dsNames[state.mapDataset] || "2026 Election";

    if (state.mapMode === "shift") {
      document.getElementById("map-heading-text").textContent =
        `Shift in Margin: 2024 Presidential Vote → ${dsLabel}`;
      document.getElementById("map-subheading-text").textContent =
        `Blue arrows (↖) show counties shifting toward Democrats; red arrows (↗) show counties shifting toward Republicans compared with the 2024 presidential election.`;
      document.getElementById("legend-shift-note").textContent =
        state.minEevp >= 90
          ? `Compared with the 2024 presidential vote in counties that have reported almost all (≥${state.minEevp}%) of their votes.`
          : `Compared with the 2024 presidential vote in counties with ≥${state.minEevp}% estimated votes reported.`;
    } else if (state.mapMode === "winner") {
      document.getElementById("map-heading-text").textContent =
        `${dsLabel} Results — By ${state.winnerLevel === "county" ? "County Margin" : "State Winner & Call Status"}`;
      document.getElementById("map-subheading-text").textContent =
        `Solid colors indicate called winners; striped patterns indicate current leader in uncalled races.`;
    } else {
      document.getElementById("map-heading-text").textContent =
        `${dsLabel} — Live Remaining Uncounted Vote & Forecast`;
      document.getElementById("map-subheading-text").textContent =
        `Circle sizes show where uncounted ballots remain across counties, colored by current 2026 vote margin.`;
    }

    // Build lookup of state-level race results for current dataset
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

    // 1. Render Base States Layer
    const gStates = gMap.select(".layer-states");
    const statePaths = gStates
      .selectAll("path.state-fill")
      .data(state.stateFeatures, (d) => d.id);

    statePaths
      .join("path")
      .attr("class", "state-fill")
      .attr("d", pathGen)
      .attr("fill", (d) => {
        const postal = d.properties.postal;
        if (state.mapMode === "winner" && state.winnerLevel === "state") {
          return getStateWinnerFill(postal, stateRaceByPostal[postal]);
        }
        if (state.selectedState !== "ALL" && postal === state.selectedState) {
          return "#e2e8f0";
        }
        return "#efefef";
      })
      .attr("opacity", (d) => {
        const postal = d.properties.postal;
        if (state.selectedState !== "ALL" && postal !== state.selectedState) {
          return 0.45;
        }
        return 1;
      })
      .on("mousemove", (event, d) => {
        const postal = d.properties.postal;
        if (state.mapMode === "winner" && state.winnerLevel === "state") {
          showStateTooltip(event, postal, stateRaceByPostal[postal]);
        }
      })
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => {
        const postal = d.properties.postal;
        if (postal) selectStateFilter(postal);
      });

    // 2. Render Counties Layer (Visible in County Winner mode, or transparent hover targets in Shift/Forecast mode)
    const gCounties = gMap.select(".layer-counties");
    const showCountyChoropleth =
      state.mapMode === "winner" &&
      (state.winnerLevel === "county" || state.mapDataset === "h26");

    const countyPaths = gCounties
      .selectAll("path.county-path")
      .data(state.countyFeatures, (d) => d.id);

    countyPaths
      .join("path")
      .attr("class", "county-path")
      .attr("d", pathGen)
      .attr("fill", (d) => {
        const cData = state.countyShifts.counties[d.id];
        if (!cData) return "transparent";
        if (showCountyChoropleth) {
          const rec = cData[state.mapDataset];
          if (!rec || !rec.v) return "#efefef";
          return getMarginColor(rec.m);
        }
        return "transparent";
      })
      .attr("stroke", showCountyChoropleth ? "rgba(255,255,255,0.28)" : "rgba(0,0,0,0.03)")
      .on("mousemove", (event, d) => {
        const cData = state.countyShifts.counties[d.id];
        if (cData) showCountyTooltip(event, cData);
      })
      .on("mouseleave", hideTooltip)
      .on("click", (event, d) => {
        const cData = state.countyShifts.counties[d.id];
        if (cData && cData.state) selectStateFilter(cData.state);
      });

    // 3. State Borders Mesh
    const gBorders = gMap.select(".layer-state-borders");
    gBorders.selectAll("*").remove();
    gBorders
      .append("path")
      .datum(topojson.mesh(state.topo, state.topo.objects.states, (a, b) => a !== b))
      .attr("class", "state-border-mesh")
      .attr("d", pathGen);

    // 4. Render Shift Arrows Layer (Mode === 'shift') AND Compute KPIs
    const gArrows = gMap.select(".layer-arrows");
    gArrows.selectAll("*").remove();

    const gBubbles = gMap.select(".layer-bubbles");
    gBubbles.selectAll("*").remove();

    const arrowsData = [];
    const bubblesData = [];
    const shiftsList = [];
    let demShiftCount = 0;
    let gopShiftCount = 0;
    let totalRemVotes = 0;

    for (const [fips, cData] of Object.entries(state.countyShifts.counties)) {
      if (state.selectedState !== "ALL" && cData.state !== state.selectedState) {
        continue;
      }
      const rec = cData[state.mapDataset];
      if (!rec || !rec.v) continue;

      totalRemVotes += rec.rem || 0;
      const centroid = state.countyCentroids[fips];
      if (!centroid) continue;

      if (rec.rem > 100) {
        bubblesData.push({ fips, cData, rec, cx: centroid[0], cy: centroid[1] });
      }

      if (rec.sp24 !== null && rec.sp24 !== undefined && rec.eevp >= state.minEevp) {
        const shift = rec.sp24;
        shiftsList.push(shift);
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

    if (state.mapMode === "shift") {
      // Sort arrows so larger arrows render on top cleanly
      arrowsData.sort((a, b) => Math.abs(a.shift) - Math.abs(b.shift));

      gArrows
        .selectAll("path.shift-arrow")
        .data(arrowsData, (d) => d.fips)
        .join("path")
        .attr("class", "shift-arrow")
        .attr("d", (d) => buildArrowPath(d.cx, d.cy, d.shift))
        .attr("fill", (d) => (d.shift >= 0 ? "#1b6ec2" : "#c9312b"))
        .attr("opacity", 0.86)
        .on("mousemove", (event, d) => showCountyTooltip(event, d.cData))
        .on("mouseleave", hideTooltip)
        .on("click", (event, d) => {
          if (d.cData && d.cData.state) selectStateFilter(d.cData.state);
        });
    } else if (state.mapMode === "forecast") {
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
        .attr("fill", (d) => (d.rec.m >= 0 ? "rgba(27,110,194,0.55)" : "rgba(201,49,43,0.55)"))
        .attr("stroke", (d) => (d.rec.m >= 0 ? "#134e9b" : "#991b1b"))
        .attr("stroke-width", 1)
        .style("cursor", "pointer")
        .on("mousemove", (event, d) => showCountyTooltip(event, d.cData))
        .on("mouseleave", hideTooltip)
        .on("click", (event, d) => {
          if (d.cData && d.cData.state) selectStateFilter(d.cData.state);
        });
    }

    // 5. Render State Labels Layer (Matches Screenshot AP State Labels)
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
      .attr("class", "state-label")
      .attr("x", (d) => state.stateCentroids[d.properties.postal][0])
      .attr("y", (d) => state.stateCentroids[d.properties.postal][1])
      .text((d) => apAbbr[d.properties.postal] || d.properties.postal);

    // Update KPI Strip under Map
    updateMapKpis(shiftsList, demShiftCount, gopShiftCount, totalRemVotes);
  }

  /**
   * Builds a single crisp SVG path (shaft + triangular arrowhead) for a county shift arrow.
   * Positive shift (More Dem.) points up-left (-152 deg in SVG screen coords).
   * Negative shift (More Rep.) points up-right (-28 deg in SVG screen coords).
   */
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

  function getStateWinnerFill(postal, race) {
    if (state.mapDataset === "h26") {
      return "#efefef";
    }
    if (!race) {
      if (state.mapDataset === "g26") {
        const noElMap = state.overview.chamber_control.governor.no_election_map || {};
        if (noElMap[postal] === "DEM") return "#bfdbfe";
        if (noElMap[postal] === "GOP") return "#fecaca";
      }
      return "#e5e7eb";
    }
    const party = race.winner_party || race.leader_party;
    if (race.called) {
      if (party === "DEM") return "#1b6ec2";
      if (party === "GOP") return "#c9312b";
      return "#7c3aed";
    } else {
      if (party === "DEM") return "url(#pat-dem-lead)";
      if (party === "GOP") return "url(#pat-gop-lead)";
      return "#fde68a";
    }
  }

  function getMarginColor(margin) {
    if (margin >= 25) return "#134e9b";
    if (margin >= 10) return "#2563eb";
    if (margin >= 3) return "#60a5fa";
    if (margin > 0) return "#93c5fd";
    if (margin <= -25) return "#991b1b";
    if (margin <= -10) return "#dc2626";
    if (margin <= -3) return "#f87171";
    return "#fca5a5";
  }

  function updateMapKpis(shiftsList, demCount, gopCount, totalRemVotes) {
    const totalShiftCounties = demCount + gopCount;
    const demPct = totalShiftCounties > 0 ? ((100 * demCount) / totalShiftCounties).toFixed(1) : "0.0";
    const gopPct = totalShiftCounties > 0 ? ((100 * gopCount) / totalShiftCounties).toFixed(1) : "0.0";

    document.getElementById("kpi-dem-counties").textContent =
      `${fmtInt(demCount)} (${demPct}%)`;
    document.getElementById("kpi-gop-counties").textContent =
      `${fmtInt(gopCount)} (${gopPct}%)`;

    if (shiftsList.length > 0) {
      const sorted = [...shiftsList].sort((a, b) => a - b);
      const mid = Math.floor(sorted.length / 2);
      const median =
        sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
      const mean = sorted.reduce((acc, v) => acc + v, 0) / sorted.length;

      const medEl = document.getElementById("kpi-median-shift");
      medEl.textContent =
        median >= 0 ? `↖ Dem +${median.toFixed(1)} pts` : `↗ Rep +${Math.abs(median).toFixed(1)} pts`;
      medEl.className = `kpi-val ${median >= 0 ? "dem-text" : "gop-text"}`;

      const meanEl = document.getElementById("kpi-mean-shift");
      meanEl.textContent =
        mean >= 0 ? `↖ Dem +${mean.toFixed(1)} pts` : `↗ Rep +${Math.abs(mean).toFixed(1)} pts`;
      meanEl.className = `kpi-val ${mean >= 0 ? "dem-text" : "gop-text"}`;
    } else {
      document.getElementById("kpi-median-shift").textContent = "—";
      document.getElementById("kpi-mean-shift").textContent = "—";
    }

    document.getElementById("kpi-rem-votes").textContent = fmtInt(totalRemVotes);
  }

  // =========================================================================
  // TOOLTIPS (County & State Hover)
  // =========================================================================
  function showCountyTooltip(event, cData) {
    const tt = document.getElementById("map-tooltip");
    const rec = cData[state.mapDataset];
    const p24 = cData.p24;

    if (!rec && !p24) {
      hideTooltip();
      return;
    }

    const eevpText = rec ? `${rec.eevp}% reported` : "";
    let shiftBannerHtml = "";
    if (rec && rec.sp24 !== null && rec.sp24 !== undefined) {
      const s = rec.sp24;
      const isDem = s >= 0;
      shiftBannerHtml = `
        <div class="tt-shift-banner ${isDem ? "tt-shift-dem" : "tt-shift-gop"}">
          <span>Shift vs. 2024 Pres:</span>
          <span>${isDem ? "↖ Dem +" + s.toFixed(1) : "↗ Rep +" + Math.abs(s).toFixed(1)} pts</span>
        </div>
      `;
    }

    const demName = (rec && rec.dn) || "Democrat";
    const gopName = (rec && rec.rn) || "Republican";

    tt.innerHTML = `
      <div class="tt-header">
        <span class="tt-title">${cData.name} County, ${cData.state}</span>
        <span class="tt-rep">${eevpText}</span>
      </div>
      ${shiftBannerHtml}
      <table class="tt-table">
        <thead>
          <tr>
            <th>Candidate / Cycle</th>
            <th class="num">Dem.</th>
            <th class="num">Rep.</th>
            <th class="num">Margin</th>
          </tr>
        </thead>
        <tbody>
          ${
            rec
              ? `<tr>
                  <td><strong>2026 (${demName.split(" ").pop()} vs ${gopName.split(" ").pop()})</strong></td>
                  <td class="num">${rec.d.toFixed(1)}%</td>
                  <td class="num">${rec.r.toFixed(1)}%</td>
                  <td class="num"><strong>${rec.m >= 0 ? "D+" + rec.m.toFixed(1) : "R+" + Math.abs(rec.m).toFixed(1)}</strong></td>
                </tr>`
              : ""
          }
          ${
            p24
              ? `<tr>
                  <td>2024 Pres (Harris/Trump)</td>
                  <td class="num">${p24.d.toFixed(1)}%</td>
                  <td class="num">${p24.r.toFixed(1)}%</td>
                  <td class="num">${p24.m >= 0 ? "D+" + p24.m.toFixed(1) : "R+" + Math.abs(p24.m).toFixed(1)}</td>
                </tr>`
              : ""
          }
        </tbody>
      </table>
      ${
        rec
          ? `<div style="margin-top:6px;font-size:11px;color:#5f6368;">
               2026 Votes: ${fmtInt(rec.v)} ${rec.rem > 0 ? `· Est. remaining: ${fmtInt(rec.rem)}` : ""}
             </div>`
          : ""
      }
    `;

    positionTooltip(event, tt);
  }

  function showStateTooltip(event, postal, race) {
    const tt = document.getElementById("map-tooltip");
    const stName = STATE_NAMES[postal] || postal;
    if (!race) {
      tt.innerHTML = `
        <div class="tt-header">
          <span class="tt-title">${stName}</span>
          <span class="tt-rep">No race on 2026 ballot</span>
        </div>
        <div style="font-size:12px;color:#5f6368;">Click to inspect U.S. House &amp; local races in ${stName}.</div>
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
      <div style="font-size:12px;margin-bottom:6px;font-weight:700;color:${race.called ? "#15803d" : "#b45309"}">
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

  function positionTooltip(event, tt) {
    tt.style.display = "block";
    const container = document.getElementById("map-svg-container");
    const rect = container.getBoundingClientRect();
    let x = event.clientX - rect.left + 16;
    let y = event.clientY - rect.top + 16;
    if (x + 280 > rect.width) x = Math.max(10, event.clientX - rect.left - 285);
    if (y + 160 > rect.height) y = Math.max(10, event.clientY - rect.top - 165);
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
    panel.style.display = state.mapMode === "forecast" ? "block" : "none";
    if (state.mapMode !== "forecast") return;

    const cc = state.overview.chamber_control;
    const senProbs = (cc.senate.seat_probabilities || [])
      .map(
        (p) =>
          `<div style="display:flex;justify-content:space-between;font-size:12.5px;padding:3px 0;border-bottom:1px solid #f1f3f4;">
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
  // GOOGLE SEARCH-STYLE RACE CARDS EXPLORER
  // =========================================================================
  async function renderRaceExplorer() {
    const ov = state.overview;
    if (!ov) return;

    const civicTypeSel = document.getElementById("filter-civic-type");
    civicTypeSel.style.display = state.activeOfficeTab === "all-local" ? "inline-block" : "none";

    // Selected state banner
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

    if (state.activeOfficeTab === "senate") {
      items = [...ov.senate_races];
      heading = "U.S. Senate Races";
    } else if (state.activeOfficeTab === "house") {
      items = [...ov.house_races];
      heading = "U.S. House of Representatives (435 Districts)";
    } else if (state.activeOfficeTab === "governor") {
      items = [...ov.governor_races];
      heading = "State Gubernatorial Races";
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
        // Load top close races + allow loading any state
        items = [...(ov.close_races_all_levels || [])];
        heading = "Closest Uncalled Federal, State & Local Races Nationwide (Select a State for All 39,474 Races)";
      }
    }

    // Apply State Filter
    if (state.selectedState !== "ALL" && !isCivicFormat) {
      items = items.filter((r) => r.state === state.selectedState);
    }

    // Apply Civic Type Filter
    if (isCivicFormat && state.civicTypeFilter !== "ALL") {
      items = items.filter((r) => r.type === state.civicTypeFilter);
    }

    // Apply Call Status Filter
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

    // Apply Search Query Filter
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

    // Sort items
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
      if (state.sortBy === "shift-desc" && !isCivicFormat) {
        const sA = Math.abs(a.shift_vs_house_2024 ?? a.shift_vs_pres_2024 ?? 0);
        const sB = Math.abs(b.shift_vs_house_2024 ?? b.shift_vs_pres_2024 ?? 0);
        return sB - sA;
      }
      // default: uncalled-first, then closest margin
      if (a.called !== b.called) return a.called ? 1 : -1;
      return mA - mB;
    });

    document.getElementById("explorer-heading").textContent = heading;
    document.getElementById("explorer-count-badge").textContent = `${fmtInt(items.length)} races`;

    // Pagination
    const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
    if (state.page > totalPages) state.page = 1;
    const startIdx = (state.page - 1) * state.pageSize;
    const pageItems = items.slice(startIdx, startIdx + state.pageSize);

    const grid = document.getElementById("races-grid");
    if (pageItems.length === 0) {
      grid.innerHTML = `<div style="grid-column:1/-1;padding:28px;text-align:center;color:#5f6368;">No races match the current filters. Try clearing your search or selecting "All 50 States".</div>`;
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
    const title =
      r.office === "U.S. House"
        ? `${stName} ${r.seat || `District ${r.seat_number}`}`
        : r.office === "U.S. Senate" || r.office === "Governor"
        ? `${stName} — ${r.office}`
        : `${stName} — ${r.office} ${r.seat || ""}`;

    const winParty = r.winner_party || r.leader_party || "OTH";
    const cardBorderClass = !r.called
      ? "uncalled-card"
      : winParty === "DEM"
      ? "called-dem-card"
      : winParty === "GOP"
      ? "called-gop-card"
      : "";

    const isFlipped =
      r.party_flip ||
      (r.incumbent_party in { DEM: 1, GOP: 1 } &&
        winParty in { DEM: 1, GOP: 1 } &&
        winParty !== r.incumbent_party);

    let badgesHtml = "";
    if (isFlipped) {
      badgesHtml += `<span class="rc-badge ${winParty === "DEM" ? "badge-flip-dem" : "badge-flip-gop"}">${
        r.called ? "FLIP" : "LEADING FLIP"
      }: ${r.incumbent_party} → ${winParty}</span>`;
    }
    if (!r.called) {
      badgesHtml += `<span class="rc-badge badge-tctc">Too Close · ±${r.top_margin_pct.toFixed(2)}% (${fmtInt(r.top_margin_votes)}v)</span>`;
    } else {
      badgesHtml += `<span class="rc-badge ${
        winParty === "DEM" ? "badge-called-dem" : winParty === "GOP" ? "badge-called-gop" : ""
      }">✓ Called</span>`;
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
        const incText = c.incumbent ? ` <span title="Incumbent" style="color:#70757a;font-size:11px;">(i)</span>` : "";

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

    // Shift vs 2024 footer
    const shiftVal = r.shift_vs_house_2024 ?? r.shift_vs_pres_2024;
    const shiftType = r.shift_vs_house_2024 !== null && r.shift_vs_house_2024 !== undefined ? "vs. '24 House" : "vs. '24 Pres";
    let shiftHtml = "";
    if (shiftVal !== null && shiftVal !== undefined) {
      const isDem = shiftVal >= 0;
      shiftHtml = `<span class="shift-chip ${isDem ? "dem" : "gop"}">${
        isDem ? "↖ Dem +" + shiftVal.toFixed(1) : "↗ Rep +" + Math.abs(shiftVal).toFixed(1)
      } pts ${shiftType}</span>`;
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
              ? `<p style="font-size:12px;color:#5f6368;margin:6px 0 8px;">${r.ballot_measure_text}</p>`
              : `<div style="height:8px"></div>`
          }
          <div class="rc-candidates">${candsHtml}</div>
        </div>
        <div class="rc-footer">
          <span>Margin: <strong>${r.top_margin_pct.toFixed(2)}%</strong> (${fmtInt(r.top_margin_votes)} votes)</span>
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
    document.getElementById("select-state-filter").value = postal;
    renderMap();
    renderRaceExplorer();
  }

  // =========================================================================
  // EVENT BINDINGS
  // =========================================================================
  function bindEvents() {
    // Top Office Tabs
    document.querySelectorAll(".office-tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".office-tab").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        const off = btn.getAttribute("data-office");
        state.activeOfficeTab = off;
        state.page = 1;

        if (off === "senate") {
          state.mapDataset = "s26";
          document.getElementById("select-map-dataset").value = "s26";
        } else if (off === "house") {
          state.mapDataset = "h26";
          document.getElementById("select-map-dataset").value = "h26";
        } else if (off === "governor") {
          state.mapDataset = "g26";
          document.getElementById("select-map-dataset").value = "g26";
        }

        renderBalanceOfPower();
        renderMap();
        renderRaceExplorer();
      });
    });

    // Left Overlay Mode Switcher Cards (By winner | Shift from 2024 | Live forecast)
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

    // Map dataset selector
    document.getElementById("select-map-dataset").addEventListener("change", (e) => {
      state.mapDataset = e.target.value;
      renderBalanceOfPower();
      renderMap();
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
    });

    // State focus selector
    document.getElementById("select-state-filter").addEventListener("change", (e) => {
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
      renderRaceExplorer();
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

/**
 * RAIL-ETA // Dynamic Coaching Train Forecasting System (SIH 26028)
 * Frontend Operations Control Script
 * 
 * Features:
 * - Real-time and Replay (Time-Travel) Telemetry Scrubbing
 * - LightGBM Multi-Quantile ETA Forecasting (p10, p50, p90)
 * - TreeSHAP Causal Factor Attribution Breakdown
 * - Live Train Search Autocomplete & Quick Presets
 * - Operational Audit & Ministry of Railways Calibration Metrics
 */

(function () {
  'use strict';

  // --- APPLICATION STATE ---
  const state = {
    trainNumber: '16558',
    journeyDate: '2026-10-15',
    trainInfo: null,
    routeStops: [],
    fullEvents: [],
    scrubIndex: 0, // 0 = origin pre-departure; 1..N = after stop i
    isPlaying: false,
    playInterval: null,
    snapshot: null,
    selectedStationCode: null,
    isLoading: false,
    accuracyData: null,
    calibrationData: null,
  };

  // --- DOM CACHE ---
  const dom = {
    // Search & Header
    searchInput: document.getElementById('train-search-input'),
    searchDropdown: document.getElementById('search-dropdown'),
    dateInput: document.getElementById('journey-date-input'),
    presetChips: document.querySelectorAll('.preset-chip'),
    lastUpdated: document.getElementById('header-last-updated'),
    btnOpenAccuracy: document.getElementById('btn-open-accuracy'),

    // Scrubber
    scrubberTime: document.getElementById('scrubber-display-time'),
    btnScrubPrev: document.getElementById('btn-scrub-prev'),
    btnScrubPlay: document.getElementById('btn-scrub-play'),
    btnScrubNext: document.getElementById('btn-scrub-next'),
    btnScrubLive: document.getElementById('btn-scrub-live'),
    scrubberSlider: document.getElementById('scrubber-slider'),
    sliderStopCount: document.getElementById('slider-stop-count'),

    // Hero Summary
    heroTrainNum: document.getElementById('hero-train-num'),
    heroTrainName: document.getElementById('hero-train-name'),
    heroTrainClass: document.getElementById('hero-train-class'),
    heroCorridor: document.getElementById('hero-corridor'),
    heroProgressFill: document.getElementById('hero-progress-fill'),
    heroCurrentDelay: document.getElementById('hero-current-delay'),
    heroProgressPct: document.getElementById('hero-progress-pct'),
    heroStatusTag: document.getElementById('hero-status-tag'),

    // Route Table
    routeTableBody: document.getElementById('route-table-body'),

    // Quantile Card
    targetStnBadge: document.getElementById('target-stn-badge'),
    targetStnName: document.getElementById('target-stn-name'),
    targetStnDist: document.getElementById('target-stn-dist'),
    targetSchedTime: document.getElementById('target-sched-time'),
    qP10Delay: document.getElementById('q-p10-delay'),
    qP10Time: document.getElementById('q-p10-time'),
    qP50Delay: document.getElementById('q-p50-delay'),
    qP50Time: document.getElementById('q-p50-time'),
    qP90Delay: document.getElementById('q-p90-delay'),
    qP90Time: document.getElementById('q-p90-time'),
    uncertaintySpreadVal: document.getElementById('uncertainty-spread-val'),

    // TreeSHAP Card
    shapList: document.getElementById('shap-list'),

    // Modal
    accuracyModal: document.getElementById('accuracy-modal'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    mMae: document.getElementById('m-mae'),
    mLift: document.getElementById('m-lift'),
    mCoverage: document.getElementById('m-coverage'),
    mCalGap: document.getElementById('m-cal-gap'),
  };

  // --- API SERVICE HELPERS ---
  const API_BASE = '/api/v1';

  async function apiFetch(endpoint) {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (err) {
      console.warn(`[API] Error querying ${endpoint}:`, err);
      return null;
    }
  }

  // --- TIME & FORMATTING HELPERS ---
  function formatDelayText(delayMin) {
    const d = parseFloat(delayMin) || 0.0;
    if (Math.abs(d) < 0.5) return '0.0m (RT)';
    return d > 0 ? `+${d.toFixed(1)}m` : `${d.toFixed(1)}m`;
  }

  function formatIsoTime(isoStr) {
    if (!isoStr) return '--:--';
    try {
      const parts = isoStr.split('T');
      if (parts.length > 1) {
        return parts[1].substring(0, 5);
      }
      return isoStr.substring(0, 5);
    } catch (e) {
      return isoStr;
    }
  }

  function formatDateTimeReadable(isoStr) {
    if (!isoStr) return 'Pre-Departure / Scheduled';
    try {
      const d = new Date(isoStr);
      if (isNaN(d.getTime())) return isoStr;
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }) +
        ' (' + d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ')';
    } catch (e) {
      return isoStr;
    }
  }

  function getDelayColor(delayMin) {
    const d = parseFloat(delayMin) || 0.0;
    if (d <= 5.0) return 'var(--signal-green)';
    if (d <= 15.0) return 'var(--signal-amber)';
    return 'var(--signal-red)';
  }

  // --- MAIN CONTROLLER WORKFLOWS ---

  /**
   * Loads initial journey metadata, full simulation events, and initializes the scrubber.
   */
  async function loadTrainJourney(trainNumber, journeyDate) {
    state.isLoading = true;
    stopPlayback();

    // 1. Fetch train metadata
    const trainInfo = await apiFetch(`/trains/${trainNumber}`);
    if (!trainInfo) {
      console.error(`Train ${trainNumber} not found.`);
      state.isLoading = false;
      return;
    }
    state.trainInfo = trainInfo;

    // 2. Fetch full simulated journey events
    const events = await apiFetch(`/trains/${trainNumber}/history?journey_date=${journeyDate}`);
    state.fullEvents = events || [];

    // Configure scrubber bounds
    const totalEvents = state.fullEvents.length;
    dom.scrubberSlider.min = 0;
    dom.scrubberSlider.max = totalEvents;
    
    // Default to mid-journey or 3rd station if available, otherwise terminus
    const initialIndex = totalEvents > 5 ? Math.min(5, totalEvents) : totalEvents;
    state.scrubIndex = initialIndex;
    dom.scrubberSlider.value = initialIndex;

    // Update Presets styling
    dom.presetChips.forEach(chip => {
      chip.classList.toggle('active', chip.dataset.train === String(trainNumber));
    });

    // Reset selected target station to allow auto-selection
    state.selectedStationCode = null;

    // 3. Render current point in time
    await updateTelemetryAtCurrentScrub();
    state.isLoading = false;
  }

  /**
   * Refreshes the dynamic ETA forecast and telemetry for the current scrubber position.
   */
  async function updateTelemetryAtCurrentScrub() {
    const totalEvents = state.fullEvents.length;
    const currentIdx = state.scrubIndex;

    // Determine as_of timestamp from scrubbed event
    let asOf = null;
    let currentStationCode = null;
    let currentDelay = 0;

    if (totalEvents > 0) {
      if (currentIdx === 0) {
        // Pre-departure: 5 minutes before origin departure
        const firstTime = new Date(state.fullEvents[0].event_time);
        firstTime.setMinutes(firstTime.getMinutes() - 5);
        asOf = firstTime.toISOString();
        dom.scrubberTime.textContent = `${formatDateTimeReadable(asOf)} [Origin Depot]`;
        dom.sliderStopCount.textContent = `0 / ${totalEvents} Stations Traversed`;
      } else {
        const lastEv = state.fullEvents[Math.min(currentIdx - 1, totalEvents - 1)];
        asOf = lastEv.event_time;
        currentStationCode = lastEv.last_station_code;
        currentDelay = parseFloat(lastEv.delay_minutes) || 0;

        dom.scrubberTime.textContent = `${formatDateTimeReadable(asOf)} [At: ${currentStationCode}]`;
        dom.sliderStopCount.textContent = `${currentIdx} / ${totalEvents} Stations Traversed`;
      }
    } else {
      dom.scrubberTime.textContent = 'No telemetry events available';
      dom.sliderStopCount.textContent = '0 / 0 Stations';
    }

    // Call dynamic ETA API with as_of parameter
    let etaUrl = `/trains/${state.trainNumber}/eta?journey_date=${state.journeyDate}`;
    if (asOf) {
      etaUrl += `&as_of=${encodeURIComponent(asOf)}`;
    }

    const snapshot = await apiFetch(etaUrl);
    if (!snapshot) {
      console.warn('Failed to retrieve ETA snapshot.');
      return;
    }
    state.snapshot = snapshot;

    // Render Dashboard Sections
    renderHeroBanner(snapshot, currentIdx, totalEvents);
    renderRouteTable(snapshot);
    renderTargetStationQuantiles(snapshot);
    dom.lastUpdated.textContent = `SYNC: ${new Date().toLocaleTimeString()}`;
  }

  /**
   * Renders the Train Hero Summary card with progress and corridor stats.
   */
  function renderHeroBanner(snapshot, currentIdx, totalEvents) {
    const info = state.trainInfo || {};
    dom.heroTrainNum.textContent = snapshot.train_number || state.trainNumber;
    dom.heroTrainName.textContent = snapshot.train_name || info.train_name || 'Express Service';
    
    // Train class badge
    const tClass = (snapshot.train_type || info.train_type || 'EXP').toUpperCase();
    dom.heroTrainClass.textContent = tClass;
    if (tClass.includes('PREM') || tClass.includes('RAJ') || tClass.includes('VANDE')) {
      dom.heroTrainClass.style.background = 'rgba(56, 189, 248, 0.15)';
      dom.heroTrainClass.style.color = '#38bdf8';
    } else if (tClass.includes('PASS') || tClass.includes('MEMU')) {
      dom.heroTrainClass.style.background = 'rgba(245, 158, 11, 0.15)';
      dom.heroTrainClass.style.color = 'var(--signal-amber)';
    } else {
      dom.heroTrainClass.style.background = 'rgba(239, 68, 68, 0.15)';
      dom.heroTrainClass.style.color = 'var(--accent-primary)';
    }

    // Corridor
    const src = info.source_station_name || info.source_station_code || 'Origin';
    const dst = info.destination_station_name || info.destination_station_code || 'Terminus';
    dom.heroCorridor.innerHTML = `<span><strong>${src}</strong> &rarr; <strong>${dst}</strong></span>`;

    // Progress percentage
    const pct = totalEvents > 0 ? ((currentIdx / totalEvents) * 100).toFixed(1) : '0.0';
    dom.heroProgressPct.textContent = `${pct}%`;
    dom.heroProgressFill.style.width = `${pct}%`;

    // Current delay
    const delay = snapshot.current_delay_minutes || 0;
    dom.heroCurrentDelay.textContent = formatDelayText(delay);
    dom.heroCurrentDelay.style.color = getDelayColor(delay);

    // Operational Status
    if (currentIdx === 0) {
      dom.heroStatusTag.textContent = 'SCHEDULED';
      dom.heroStatusTag.style.color = 'var(--text-muted)';
    } else if (currentIdx >= totalEvents) {
      dom.heroStatusTag.textContent = 'TERMINATED';
      dom.heroStatusTag.style.color = 'var(--signal-green)';
    } else {
      dom.heroStatusTag.textContent = 'IN TRANSIT';
      dom.heroStatusTag.style.color = 'var(--signal-cyan)';
    }
  }

  /**
   * Renders the station-by-station schedule table with live delay states.
   */
  function renderRouteTable(snapshot) {
    const forecasts = snapshot.forecasts || [];
    if (forecasts.length === 0) {
      dom.routeTableBody.innerHTML = `
        <tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-muted);">
          No station schedule found for this route.
        </td></tr>`;
      return;
    }

    // Auto-select target station if not explicitly picked
    if (!state.selectedStationCode) {
      const firstUpcoming = forecasts.find(f => f.status === 'CURRENT' || f.status === 'UPCOMING');
      state.selectedStationCode = firstUpcoming ? firstUpcoming.station_code : forecasts[forecasts.length - 1].station_code;
    }

    let rowsHtml = '';
    forecasts.forEach(f => {
      const isSelected = f.station_code === state.selectedStationCode;
      const isPassed = f.status === 'PASSED';
      const isCurrent = f.status === 'CURRENT';

      let rowClass = '';
      if (isSelected) rowClass += ' selected';
      if (isPassed) rowClass += ' passed';
      if (isCurrent) rowClass += ' active-live';

      // Status Badge
      let badgeClass = 'badge-upcoming';
      let badgeLabel = 'UPCOMING';
      if (isPassed) {
        badgeClass = 'badge-passed';
        badgeLabel = 'PASSED';
      } else if (isCurrent) {
        badgeClass = 'badge-active';
        badgeLabel = 'CURRENT';
      }

      // Format arrival time
      const schedTime = f.scheduled_arrival || f.scheduled_departure || '--:--';
      const estTime = isPassed ? (f.estimated_arrival_p50 || schedTime) : (f.estimated_arrival_p50 || schedTime);
      const delay = f.predicted_delay_p50 || 0;
      const delayColor = getDelayColor(delay);

      rowsHtml += `
        <tr class="${rowClass.trim()}" data-stn="${f.station_code}">
          <td style="font-family:var(--font-mono); color:var(--text-muted); font-size:11px;">${f.sequence}</td>
          <td><span class="stn-code">${f.station_code}</span></td>
          <td><span class="stn-name">${f.station_name}</span></td>
          <td style="font-family:var(--font-mono); color:var(--text-secondary);">${formatIsoTime(schedTime)}</td>
          <td style="font-family:var(--font-mono); font-weight:600; color:var(--text-primary);">${formatIsoTime(estTime)}</td>
          <td style="font-family:var(--font-mono); font-weight:700; color:${delayColor};">${formatDelayText(delay)}</td>
          <td><span class="badge-status ${badgeClass}">${badgeLabel}</span></td>
        </tr>
      `;
    });

    dom.routeTableBody.innerHTML = rowsHtml;

    // Bind row click handler for selecting station
    dom.routeTableBody.querySelectorAll('tr[data-stn]').forEach(tr => {
      tr.addEventListener('click', () => {
        state.selectedStationCode = tr.dataset.stn;
        dom.routeTableBody.querySelectorAll('tr').forEach(r => r.classList.remove('selected'));
        tr.classList.add('selected');
        renderTargetStationQuantiles(state.snapshot);
      });
    });
  }

  /**
   * Renders the Quantile ETA Card and TreeSHAP drawer for the selected station.
   */
  function renderTargetStationQuantiles(snapshot) {
    if (!snapshot || !snapshot.forecasts) return;

    const forecasts = snapshot.forecasts;
    const target = forecasts.find(f => f.station_code === state.selectedStationCode) || forecasts[forecasts.length - 1];
    if (!target) return;

    // Update Target Station Details
    dom.targetStnName.textContent = `${target.station_name} (${target.station_code})`;
    dom.targetSchedTime.textContent = `Scheduled Arrival: ${formatIsoTime(target.scheduled_arrival || target.scheduled_departure)}`;

    // Distance calculation
    const currDist = snapshot.forecasts
      .filter(f => f.status === 'PASSED')
      .reduce((max, f) => Math.max(max, f.distance_km || 0), 0);
    const distAhead = Math.max(0, (target.distance_km || 0) - currDist);
    dom.targetStnDist.textContent = `${distAhead.toFixed(1)} km ahead`;

    // Badge
    dom.targetStnBadge.className = `badge-status badge-${target.status.toLowerCase()}`;
    dom.targetStnBadge.textContent = target.status;

    // Quantile Delays & Times
    const p10d = target.predicted_delay_p10 || 0;
    const p50d = target.predicted_delay_p50 || 0;
    const p90d = target.predicted_delay_p90 || 0;

    dom.qP10Delay.textContent = formatDelayText(p10d);
    dom.qP10Delay.style.color = getDelayColor(p10d);
    dom.qP10Time.textContent = formatIsoTime(target.estimated_arrival_p10);

    dom.qP50Delay.textContent = formatDelayText(p50d);
    dom.qP50Delay.style.color = getDelayColor(p50d);
    dom.qP50Time.textContent = formatIsoTime(target.estimated_arrival_p50);

    dom.qP90Delay.textContent = formatDelayText(p90d);
    dom.qP90Delay.style.color = getDelayColor(p90d);
    dom.qP90Time.textContent = formatIsoTime(target.estimated_arrival_p90);

    // Uncertainty Spread
    const spread = Math.max(0, p90d - p10d);
    dom.uncertaintySpreadVal.textContent = `${spread.toFixed(1)} min`;

    // Render TreeSHAP Explanation Card
    renderTreeShapCard(target);
  }

  /**
   * Renders the TreeSHAP causal drivers list with animated relative impact meters.
   */
  function renderTreeShapCard(target) {
    const reasons = target.shap_explanations || [];
    
    if (target.status === 'PASSED') {
      dom.shapList.innerHTML = `
        <div style="color:var(--text-muted); font-size:12px; padding:24px; text-align:center; border:1px dashed var(--border-subtle); border-radius:6px;">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-bottom:8px; display:inline-block; opacity:0.6;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
          <div style="font-weight:600; color:var(--text-primary); margin-bottom:4px;">Station Already Traversed</div>
          <div>Actual arrival delay of ${formatDelayText(target.predicted_delay_p50)} was recorded by trackside telemetry. TreeSHAP decomposition applies only to upcoming predictive sections.</div>
        </div>
      `;
      return;
    }

    if (reasons.length === 0) {
      dom.shapList.innerHTML = `
        <div style="color:var(--text-muted); font-size:12px; padding:20px; text-align:center;">
          No dominant causal delay factors detected for this section. Expected to run near standard timetable tempo.
        </div>
      `;
      return;
    }

    // Find maximum absolute impact for relative meter scaling
    const maxAbs = Math.max(...reasons.map(r => Math.abs(r.shap_value || 0)), 1.0);

    let html = '';
    reasons.forEach(r => {
      const val = parseFloat(r.shap_value) || 0.0;
      const isPositive = val >= 0;
      const impactMin = Math.abs(val).toFixed(1);
      const sign = isPositive ? '+' : '-';
      const pctWidth = Math.min(100, Math.max(12, (Math.abs(val) / maxAbs) * 100));

      const meterClass = isPositive ? 'shap-fill pos' : 'shap-fill neg';
      const title = r.display_name || r.feature || 'Operational Factor';
      const desc = r.description || (isPositive ? `Adds estimated ${impactMin} min delay` : `Recovers estimated ${impactMin} min schedule buffer`);

      html += `
        <div class="shap-item">
          <div class="shap-header">
            <span class="shap-title">${title}</span>
            <span class="shap-val" style="color:${isPositive ? 'var(--signal-amber)' : 'var(--signal-green)'};">${sign}${impactMin} min</span>
          </div>
          <div class="shap-meter">
            <div class="${meterClass}" style="width: ${pctWidth}%;"></div>
          </div>
          <div class="shap-desc">${desc}</div>
        </div>
      `;
    });

    dom.shapList.innerHTML = html;
  }

  // --- TIME TRAVEL PLAYBACK CONTROLS ---

  function startPlayback() {
    if (state.isPlaying) return;
    state.isPlaying = true;
    dom.btnScrubPlay.textContent = '⏸ Pause';
    dom.btnScrubPlay.style.background = 'var(--signal-amber)';
    dom.btnScrubPlay.style.borderColor = 'var(--signal-amber)';
    dom.btnScrubPlay.style.color = '#000';

    state.playInterval = setInterval(async () => {
      const totalEvents = state.fullEvents.length;
      if (state.scrubIndex >= totalEvents) {
        stopPlayback();
        return;
      }
      state.scrubIndex += 1;
      dom.scrubberSlider.value = state.scrubIndex;
      await updateTelemetryAtCurrentScrub();
    }, 2000);
  }

  function stopPlayback() {
    state.isPlaying = false;
    if (state.playInterval) {
      clearInterval(state.playInterval);
      state.playInterval = null;
    }
    dom.btnScrubPlay.textContent = '▶ Play';
    dom.btnScrubPlay.style.background = '';
    dom.btnScrubPlay.style.borderColor = '';
    dom.btnScrubPlay.style.color = '';
  }

  // --- SEARCH AUTOCOMPLETE ---
  let searchDebounce = null;

  function initSearch() {
    dom.searchInput.addEventListener('input', (e) => {
      clearTimeout(searchDebounce);
      const query = e.target.value.trim();
      if (query.length < 2) {
        dom.searchDropdown.classList.remove('open');
        dom.searchDropdown.innerHTML = '';
        return;
      }

      searchDebounce = setTimeout(async () => {
        const results = await apiFetch(`/trains?q=${encodeURIComponent(query)}&limit=8`);
        renderSearchResults(results || []);
      }, 250);
    });

    dom.searchInput.addEventListener('focus', () => {
      if (dom.searchDropdown.children.length > 0) {
        dom.searchDropdown.classList.add('open');
      }
    });

    document.addEventListener('click', (e) => {
      if (!dom.searchInput.contains(e.target) && !dom.searchDropdown.contains(e.target)) {
        dom.searchDropdown.classList.remove('open');
      }
    });
  }

  function renderSearchResults(trains) {
    if (trains.length === 0) {
      dom.searchDropdown.innerHTML = `<div style="padding:12px; color:var(--text-muted); font-size:12px; text-align:center;">No matching trains found</div>`;
      dom.searchDropdown.classList.add('open');
      return;
    }

    let html = '';
    trains.forEach(t => {
      const tClass = (t.train_type || 'EXP').toUpperCase();
      html += `
        <div class="search-item" data-train="${t.train_number}">
          <div>
            <div style="display:flex; align-items:center; gap:8px;">
              <span class="stn-code" style="color:var(--signal-cyan);">${t.train_number}</span>
              <span style="font-weight:600; color:var(--text-primary);">${t.train_name}</span>
            </div>
            <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
              ${t.source_station_code || 'SRC'} &rarr; ${t.destination_station_code || 'DST'}
            </div>
          </div>
          <span class="badge-status badge-upcoming" style="font-size:10px;">${tClass}</span>
        </div>
      `;
    });

    dom.searchDropdown.innerHTML = html;
    dom.searchDropdown.classList.add('open');

    dom.searchDropdown.querySelectorAll('.search-item').forEach(item => {
      item.addEventListener('click', () => {
        const trainNo = item.dataset.train;
        state.trainNumber = trainNo;
        dom.searchInput.value = '';
        dom.searchDropdown.classList.remove('open');
        loadTrainJourney(state.trainNumber, state.journeyDate);
      });
    });
  }

  // --- MODEL ACCURACY MODAL ---
  async function loadAccuracyModal() {
    if (!state.accuracyData) {
      state.accuracyData = await apiFetch('/analytics/accuracy');
    }
    if (!state.calibrationData) {
      state.calibrationData = await apiFetch('/analytics/calibration');
    }

    if (state.accuracyData && state.accuracyData.ml_metrics) {
      dom.mMae.textContent = `${state.accuracyData.ml_metrics.mae_minutes.toFixed(2)} min`;
      dom.mLift.textContent = `+${state.accuracyData.lift.mae_reduction_pct.toFixed(1)}%`;
      dom.mCoverage.textContent = `${state.accuracyData.ml_metrics.coverage_p10_p90_pct.toFixed(1)}%`;
    }

    if (state.calibrationData && state.calibrationData.classes && state.calibrationData.classes.Passenger) {
      const passGap = state.calibrationData.classes.Passenger.gap_points || 0.0;
      dom.mCalGap.textContent = `${passGap.toFixed(1)}%`;
    }

    dom.accuracyModal.classList.add('open');
  }

  function closeModal() {
    dom.accuracyModal.classList.remove('open');
  }

  // --- EVENT LISTENERS INITIALIZATION ---
  function initEventListeners() {
    // Preset train buttons
    dom.presetChips.forEach(chip => {
      chip.addEventListener('click', () => {
        state.trainNumber = chip.dataset.train;
        loadTrainJourney(state.trainNumber, state.journeyDate);
      });
    });

    // Date picker
    dom.dateInput.addEventListener('change', (e) => {
      state.journeyDate = e.target.value;
      loadTrainJourney(state.trainNumber, state.journeyDate);
    });

    // Scrubber Range Slider
    dom.scrubberSlider.addEventListener('input', (e) => {
      stopPlayback();
      state.scrubIndex = parseInt(e.target.value, 10);
      updateTelemetryAtCurrentScrub();
    });

    // Scrubber Step Prev
    dom.btnScrubPrev.addEventListener('click', () => {
      stopPlayback();
      state.scrubIndex = Math.max(0, state.scrubIndex - 1);
      dom.scrubberSlider.value = state.scrubIndex;
      updateTelemetryAtCurrentScrub();
    });

    // Scrubber Play / Pause
    dom.btnScrubPlay.addEventListener('click', () => {
      if (state.isPlaying) {
        stopPlayback();
      } else {
        startPlayback();
      }
    });

    // Scrubber Step Next
    dom.btnScrubNext.addEventListener('click', () => {
      stopPlayback();
      const totalEvents = state.fullEvents.length;
      state.scrubIndex = Math.min(totalEvents, state.scrubIndex + 1);
      dom.scrubberSlider.value = state.scrubIndex;
      updateTelemetryAtCurrentScrub();
    });

    // Scrubber Live / Terminus
    dom.btnScrubLive.addEventListener('click', () => {
      stopPlayback();
      state.scrubIndex = state.fullEvents.length;
      dom.scrubberSlider.value = state.scrubIndex;
      updateTelemetryAtCurrentScrub();
    });

    // Accuracy Modal Triggers
    dom.btnOpenAccuracy.addEventListener('click', loadAccuracyModal);
    dom.btnCloseModal.addEventListener('click', closeModal);
    dom.accuracyModal.addEventListener('click', (e) => {
      if (e.target === dom.accuracyModal) closeModal();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && dom.accuracyModal.classList.contains('open')) {
        closeModal();
      }
    });

    initSearch();
  }

  // --- BOOTSTRAP ---
  document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadTrainJourney(state.trainNumber, state.journeyDate);
  });

})();

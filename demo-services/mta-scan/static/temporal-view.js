/* Independent offline-history pane. No raw-feed requests or model calls. */
(function () {
  'use strict';
  var panel = document.getElementById('temporalPanel');
  if (!panel) return;
  var latest = null, loading = false;
  var names = {persistence: 'Persistence', seasonal_24h: '24-hour seasonal', online_linear: 'Online linear', selected: 'Validation-selected'};
  var states = {collecting: 'Collecting history', short_window_feasibility: 'Early feasibility only', ready: 'Proxy forecasts ready', temporarily_unavailable: 'Temporarily unavailable', error: 'Worker unavailable'};
  function el(tag, text) { var node = document.createElement(tag); if (text != null) node.textContent = String(text); return node; }
  function set(id, text) { document.getElementById(id).textContent = text; }
  function number(value, digits) { return typeof value === 'number' && Number.isFinite(value) ? value.toLocaleString('en-US', {maximumFractionDigits: digits == null ? 1 : digits}) : '—'; }
  function date(value) { return typeof value === 'number' ? new Date(value * 1000).toLocaleString() : '—'; }
  function row(values) { var tr = el('tr'); values.forEach(function (v) { tr.appendChild(el('td', v)); }); return tr; }
  function list(id, values) { var node = document.getElementById(id); node.replaceChildren(); (values || []).forEach(function (v) { node.appendChild(el('li', v)); }); }
  function clearForecasts(note) { document.getElementById('temporalForecastRows').replaceChildren(); document.getElementById('temporalForecastTable').hidden = true; set('temporalForecastNote', note); }
  function render(value) {
    latest = value;
    var ready = value.readiness || {}, coverage = value.coverage || {};
    set('temporalStatus', states[ready.status] || 'Temporarily unavailable');
    set('temporalUpdated', value.generated_ts ? 'Worker snapshot · ' + date(value.generated_ts) : 'Waiting for a validated worker snapshot');
    set('temporalSpan', coverage.span_seconds == null ? '—' : number(coverage.span_seconds / 86400, 2) + ' days');
    set('temporalCoverage', coverage.complete_fresh_window_fraction == null ? '—' : number(100 * coverage.complete_fresh_window_fraction) + '%');
    set('temporalWindows', number(coverage.retained_windows, 0));
    set('temporalGroups', number(coverage.stable_groups_evaluated, 0));
    list('temporalReasons', ready.reasons);
    var feeds = document.getElementById('temporalFeeds'); feeds.replaceChildren();
    (value.feeds || []).forEach(function (f) { var item = el('li'); item.appendChild(el('strong', f.feed + ' · ')); item.appendChild(el('span', (f.latest_poll_status || 'pending') + ' · source age ' + number(f.source_age_seconds, 0) + ' s')); feeds.appendChild(item); });
    var body = document.getElementById('temporalMetricRows'); body.replaceChildren();
    (value.metrics || []).filter(function (m) { return m.partition === 'test'; }).forEach(function (m) {
      ['persistence', 'seasonal_24h', 'online_linear', 'selected'].forEach(function (key) {
        var data = key === 'selected' ? m.selected_from_validation : (m.models || {})[key];
        if (!data) return;
        var tr = row([m.horizon_seconds / 60 + ' min', names[key], number(data.mae_seconds) + (data.mae_seconds == null ? '' : ' s'), number(data.rmse_seconds) + (data.rmse_seconds == null ? '' : ' s'), number(data.n, 0) + ' / ' + number(data.eligible_pairs, 0), data.coverage_fraction == null ? '—' : number(100 * data.coverage_fraction) + '%']);
        if (key === 'selected') tr.className = 'temporal-selected'; body.appendChild(tr);
      });
    });
    document.getElementById('temporalMetrics').hidden = !body.children.length;
    set('temporalEvaluationNote', body.children.length ? (coverage.span_seconds < 14 * 86400 ? 'Short-window feasibility; not a longitudinal forecasting result. ' : 'Chronological held-out test results. ') + 'Evaluation cutoff: ' + date(value.evaluation_cutoff_ts) + '. Algorithms are selected on validation only; held-out errors are shown for all methods.' : 'No measured temporal evaluation is available yet. Missing results are not shown as zero.');
    list('temporalLimitations', value.limitations);
    set('temporalArtifact', value.artifact_id ? 'Evidence ID · ' + value.artifact_id : 'No evaluation artifact yet');
    var pipeline = value.pipeline || {};
    set('temporalExports', 'Completed-day exports ingested: ' + number(pipeline.ingested_export_days, 0) + ' · pending: ' + number(pipeline.pending_export_days, 0));
    renderForecasts();
  }
  function renderForecasts() {
    var now = Date.now() / 1000, value = latest;
    if (!value || !value.readiness || !value.readiness.public_forecasts_ready || !value.valid_until_ts || now >= value.valid_until_ts || now - value.generated_ts > 900) {
      clearForecasts('No current forecast is published. At least 14 days of history, comparable platform coverage and fresh validated inputs are required.'); return;
    }
    var forecasts = (value.forecasts || []).filter(function (f) { return f.target_ts > now && now - f.origin_ts >= 0 && now - f.origin_ts <= 600; });
    if (!forecasts.length) { clearForecasts('The previous proxy forecasts have expired. Waiting for a fresh worker snapshot.'); return; }
    var body = document.getElementById('temporalForecastRows'); body.replaceChildren();
    forecasts.forEach(function (f) { body.appendChild(row([f.route_id, f.direction, f.horizon_seconds / 60 + ' min', number(f.predicted_proxy_seconds) + ' s', names[f.algorithm], date(f.target_ts)])); });
    document.getElementById('temporalForecastTable').hidden = false;
    set('temporalForecastNote', 'Future feed-predicted arrival-spacing proxy. These are not measured train headways, passenger wait times or official incident predictions.');
  }
  async function refresh() {
    if (loading || document.hidden) return;
    loading = true; var controller = new AbortController(), timeout = setTimeout(function () { controller.abort(); }, 6000);
    try { var response = await fetch('api/temporal', {cache: 'no-store', signal: controller.signal}); if (!response.ok) throw new Error('Unavailable'); var value = await response.json(); if (value.schema !== 'mta-temporal-evaluation-v1') throw new Error('Unknown schema'); render(value); }
    catch (_) { latest = null; render({readiness: {status: 'temporarily_unavailable', reasons: ['History summary is unavailable. Live map monitoring remains separate.']}, metrics: [], forecasts: []}); }
    finally { clearTimeout(timeout); loading = false; }
  }
  document.getElementById('temporalRefresh').addEventListener('click', refresh);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) { renderForecasts(); refresh(); } });
  refresh(); setInterval(refresh, 60000); setInterval(renderForecasts, 15000);
})();

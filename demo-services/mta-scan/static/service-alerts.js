/* Official MTA context is independent of anomaly scores and temporal forecasts. */
(function () {
  'use strict';
  var panel = document.getElementById('serviceAlertsPanel');
  if (!panel) return;
  var latest = null, loading = false, expanded = false;
  var route = document.getElementById('serviceAlertRoute');
  var more = document.getElementById('serviceAlertsMore');
  var list = document.getElementById('serviceAlertList');
  function el(tag, text) { var n = document.createElement(tag); if (text != null) n.textContent = String(text); return n; }
  function set(id, text) { document.getElementById(id).textContent = text; }
  function date(value) { return typeof value === 'number' && Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : 'not yet available'; }
  function render() {
    var now = Date.now() / 1000, v = latest;
    var openIds = new Set(Array.from(list.querySelectorAll("details[open]")).map(function (n) { return n.dataset.alertId; }));
    list.replaceChildren(); more.hidden = true;
    var fresh = v && v.schema === 'mta-official-service-alerts-v1' && v.status === 'ok' &&
      typeof v.generated_ts === 'number' && now >= v.generated_ts && now - v.generated_ts <= 180 &&
      typeof v.source_ts === 'number' && now - v.source_ts >= -30 && now - v.source_ts <= 600 &&
      typeof v.valid_until_ts === 'number' && now < v.valid_until_ts && v.valid_until_ts <= v.generated_ts + 600;
    set('serviceAlertsStatus', fresh ? 'Official MTA feed available' : 'Official alert context unavailable');
    set('serviceAlertsUpdated', v ? 'Source timestamp: ' + date(v.source_ts) + ' · Received: ' + date(v.generated_ts) : 'Waiting for the independent collector');
    var a = v && v.archive;
    set('serviceAlertsArchive', a ? 'Archive: ' + a.retained_polls + ' receipts · ' + a.retained_revisions + ' revisions · first retained receipt ' + date(a.first_receipt_ts) : 'No archive status available.');
    if (!fresh) { set('serviceAlertsCount', 'Stale or missing messages are withheld. Live observations and forecasts remain separate.'); return; }
    var items = (Array.isArray(v.alerts) ? v.alerts : []).filter(function (x) {
      var p = x.active_period || {};
      return (p.start == null || p.start <= now) && (p.end == null || now < p.end);
    });
    var selected = route.value, routes = new Set();
    items.forEach(function (x) { (x.routes || []).forEach(function (r) { routes.add(r); }); });
    if (selected) routes.add(selected);
    var routeNames = Array.from(routes).sort(), signature = routeNames.join('|');
    if (route.dataset.sourceRoutes !== signature) {
      route.replaceChildren(); var all = el('option', 'All routes'); all.value = ''; route.appendChild(all);
      routeNames.forEach(function (r) { var option = el('option', r); option.value = r; route.appendChild(option); });
      route.value = selected; route.dataset.sourceRoutes = signature;
    }
    var matching = selected ? items.filter(function (x) { return x.routes.indexOf(selected) !== -1; }) : items;
    var shown = expanded ? matching : matching.slice(0, 10);
    set('serviceAlertsCount', matching.length ? 'Showing ' + shown.length + ' of ' + matching.length + ' active messages' + (selected ? ' for route ' + selected : '') + (v.display_truncated ? '. The source summary is capped; check MTA for the complete feed.' : '.') : 'No active messages match this view. This does not certify normal service.');
    shown.forEach(function (x) {
      var details = el('details'); details.className = 'temporal-details'; details.dataset.alertId = x.id; details.open = openIds.has(x.id);
      details.appendChild(el('summary', (x.routes.length ? x.routes.join(', ') + ' · ' : '') + (x.header || 'Service update')));
      var kind = x.kind === 'planned_work' ? 'Planned work' : x.kind === 'service_alert' ? 'Service alert' : 'Other message';
      var meta = el('p', kind + ' · Active from ' + date(x.active_period.start) + ' · End ' + date(x.active_period.end)); meta.className = 'source-meta'; details.appendChild(meta);
      var description = el('p', x.description || 'No additional plain-text description.'); description.className = 'note'; details.appendChild(description);
      if (x.description_truncated) details.appendChild(el('p', 'Description excerpt; consult MTA for the complete message.'));
      var source = el('p', 'MTA alert ID: ' + x.id); source.className = 'source-meta'; details.appendChild(source);
      list.appendChild(details);
    });
    more.hidden = matching.length <= 10;
    more.textContent = expanded ? 'Show fewer messages' : 'Show all ' + matching.length + ' messages';
  }
  async function refresh() {
    if (loading || document.hidden) return;
    loading = true;
    var controller = new AbortController(), timeout = setTimeout(function () { controller.abort(); }, 6000);
    try {
      var response = await fetch('api/service-alerts', {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw new Error('unavailable');
      var value = await response.json();
      if (value.schema !== 'mta-official-service-alerts-v1') throw new Error('unknown schema');
      latest = value;
    } catch (_) { latest = null; }
    finally { clearTimeout(timeout); loading = false; render(); }
  }
  route.addEventListener('change', function () { expanded = false; render(); });
  more.addEventListener('click', function () { expanded = !expanded; render(); });
  document.getElementById('serviceAlertsRefresh').addEventListener('click', refresh);
  document.addEventListener('visibilitychange', function () { if (!document.hidden) { render(); refresh(); } });
  refresh(); setInterval(refresh, 60000); setInterval(render, 15000);
})();

/* SmartRescue AI - website logic: navigation, live refresh, maps, charts, algorithm lab. */
const state = { nodes: {}, edges: [], ambulances: [], hospitals: [], algorithms: [], types: [], summary: null };
const charts = {};
const ALGO_COLORS = { BFS: "#0284c7", DFS: "#d97706", UCS: "#7c3aed", "A*": "#059669" };
const PALETTE = ["#1d4ed8", "#0284c7", "#059669", "#d97706", "#dc2626"];
const TITLES = { dashboard: "Dashboard", dispatch: "Emergency Dispatch", lab: "Algorithm Lab",
                 incidents: "Incident Records", resources: "Resources & Road Network" };
let currentPage = "dashboard", drawnSig = "", labToken = 0, labNext = "from";

/* ---------- helpers ---------- */
const $ = (id) => document.getElementById(id);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

async function api(url, options) {
  const res = await fetch(url, options);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Request failed");
  return data;
}
const post = (url, body) => api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });

let toastTimer;
function toast(message, isError = false) {
  const t = $("toast");
  t.textContent = message;
  t.className = "toast show" + (isError ? " error" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = "toast"), 3500);
}

const nodeName = (id) => (state.nodes[id] ? state.nodes[id].name : id);
const pathText = (path) => path.map(nodeName).join(" → ");
const latlng = (id) => [state.nodes[id].lat, state.nodes[id].lng];
const statusTag = (s) => el("span", "tag " + s.toLowerCase(), s);
const pin = (cls, label) => L.divIcon({ className: "", html: `<div class="pin ${cls}">${label}</div>`, iconSize: [28, 28], iconAnchor: [14, 14] });

/* ---------- theme ---------- */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem("sr-theme", theme); } catch (e) { /* storage blocked */ }
  $("theme").textContent = theme === "dark" ? "☀" : "☾";
  if (typeof Chart !== "undefined") {
    Chart.defaults.color = cssVar("--muted");
    Chart.defaults.borderColor = cssVar("--border");
    Object.values(charts).forEach((c) => c.update());
  }
}

/* ---------- maps ---------- */
function createMap(id) {
  const map = L.map(id).setView([33.703, 73.05], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 18, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
  return { map, network: L.layerGroup().addTo(map), assets: L.layerGroup().addTo(map), routes: L.layerGroup().addTo(map), marks: L.layerGroup().addTo(map) };
}
const dm = createMap("map-dispatch");
const lm = createMap("map-lab");

function drawNetwork(ctx, kind) {
  ctx.network.clearLayers();
  ctx.assets.clearLayers();
  state.edges.forEach((e) => {
    const line = L.polyline([latlng(e.a), latlng(e.b)], {
      color: e.blocked ? "#dc2626" : "#94a3b8", weight: e.blocked ? 5 : 3, dashArray: e.blocked ? "8 8" : null,
    }).addTo(ctx.network);
    line.bindTooltip(`${nodeName(e.a)} ↔ ${nodeName(e.b)} · cost ${e.cost}${e.blocked ? " · BLOCKED" : ""}`, { sticky: true });
    if (kind === "dispatch") line.on("click", () => toggleRoad(e.a, e.b));
  });
  Object.entries(state.nodes).forEach(([id, n]) => {
    L.circleMarker([n.lat, n.lng], { radius: 6, color: "#fff", weight: 2, fillColor: "#1e3a8a", fillOpacity: 1 })
      .bindTooltip(n.name).addTo(ctx.network)
      .on("click", () => (kind === "dispatch" ? ($("location").value = id) : pickLabNode(id)));
  });
  if (kind !== "dispatch") return;
  state.hospitals.forEach((h) => L.marker(latlng(h.node), { icon: pin("hospital", "H"), zIndexOffset: 500 })
    .bindTooltip(`${h.name} · ${h.beds}/${h.capacity} beds free`).addTo(ctx.assets));
  state.ambulances.forEach((a) => L.marker(latlng(a.node), { icon: pin("amb" + (a.available ? "" : " busy"), "A"), zIndexOffset: 600 })
    .bindTooltip(`${a.name} · ${a.available ? "Available" : "Unavailable"}`).addTo(ctx.assets));
}

/* ---------- navigation ---------- */
function showPage(name) {
  if (!TITLES[name]) name = "dashboard";
  currentPage = name;
  document.querySelectorAll(".page").forEach((p) => p.classList.toggle("active", p.id === "page-" + name));
  document.querySelectorAll(".nav-btn").forEach((b) => b.classList.toggle("active", b.dataset.page === name));
  $("page-title").textContent = TITLES[name];
  history.replaceState(null, "", "#" + name);
  dm.map.invalidateSize();
  lm.map.invalidateSize();
  if (name === "incidents") loadIncidents();
}

/* ---------- dashboard ---------- */
function renderKpis() {
  const s = state.summary, st = s.stats;
  const cards = [
    ["Total emergencies", st.total, `${st.active} active now`, "primary"],
    ["Average route cost", st.avg_cost, "per dispatch (both legs)", "info"],
    ["Ambulances available", `${s.ambulances_available}/${s.ambulances_total}`, "ready to dispatch", s.ambulances_available ? "success" : "danger"],
    ["Hospital beds free", `${s.beds_free}/${s.beds_total}`, `across ${state.hospitals.length} hospitals`, s.beds_free < 10 ? "warn" : "success"],
    ["Blocked roads", s.blocked_roads, "closures affecting routes", s.blocked_roads ? "danger" : "info"],
  ];
  const box = $("kpis");
  box.replaceChildren();
  cards.forEach(([label, value, sub, tone]) => {
    const c = el("div", "kpi " + tone);
    c.append(el("span", "kpi-label", label), el("strong", "kpi-value", String(value)), el("small", "kpi-sub", sub));
    box.append(c);
  });
}

function upsertChart(key, canvasId, type, labels, data) {
  if (typeof Chart === "undefined") return;
  if (!charts[key]) {
    charts[key] = new Chart($(canvasId), {
      type,
      data: { labels, datasets: [{ data, backgroundColor: PALETTE, borderWidth: 0, borderRadius: type === "bar" ? 6 : 0 }] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: type === "doughnut", position: "bottom" } },
        scales: type === "bar" ? { y: { beginAtZero: true, ticks: { precision: 0 } } } : {},
      },
    });
  } else {
    const c = charts[key];
    c.data.labels = labels;
    c.data.datasets[0].data = data;
    c.update();
  }
}

function renderCharts() {
  const st = state.summary.stats;
  upsertChart("type", "chart-type", "doughnut", state.types, state.types.map((t) => st.by_type[t] || 0));
  upsertChart("algo", "chart-algo", "bar", state.algorithms, state.algorithms.map((a) => st.by_algorithm[a] || 0));
}

function renderActivity(items) {
  const box = $("activity");
  box.replaceChildren();
  if (!items.length) { box.append(el("p", "empty", "No emergencies yet. Open Dispatch to create one.")); return; }
  items.forEach((i) => {
    const row = el("div", "activity-row"), left = el("div");
    left.append(el("b", "", `#${i.id} ${i.emergency_type}`), el("small", "", `${i.location} · ${i.ambulance} → ${i.hospital}`));
    row.append(left, statusTag(i.status), el("small", "", i.created_at));
    box.append(row);
  });
}

/* ---------- dispatch ---------- */
function comparisonTable(rows) {
  const costs = rows.filter((x) => x.found).map((x) => x.cost), min = Math.min(...costs);
  const table = el("table"), head = el("tr");
  ["Algorithm", "Cost", "Hops", "Visited", "Time (ms)"].forEach((h) => head.append(el("th", "", h)));
  table.append(head);
  rows.forEach((x) => {
    const tr = el("tr", x.found && x.cost === min ? "best" : "");
    [x.algorithm, x.found ? x.cost : "No route", x.found ? x.hops : "-", x.visited, x.time_ms].forEach((v) => tr.append(el("td", "", String(v))));
    table.append(tr);
  });
  return [table, el("p", "note", "Green = lowest cost. BFS minimises roads, DFS returns any path, UCS and A* minimise total cost; A* visits fewer nodes thanks to its heuristic.")];
}

function showDispatch(r) {
  dm.routes.clearLayers();
  dm.marks.clearLayers();
  L.marker(latlng(r.incident.node), { icon: pin("incident", "!"), zIndexOffset: 700 }).addTo(dm.marks);
  const a = L.polyline(r.route_to_incident.path.map(latlng), { color: "#1d4ed8", weight: 7, opacity: .9 }).addTo(dm.routes);
  const b = L.polyline(r.route_to_hospital.path.map(latlng), { color: "#059669", weight: 7, opacity: .9 }).addTo(dm.routes);
  dm.map.invalidateSize();
  dm.map.fitBounds(L.featureGroup([a, b]).getBounds().pad(0.25));

  const card = $("result-card"), kv = el("dl", "kv");
  card.replaceChildren(el("h3", "", `Dispatch result · incident #${r.incident_id}`));
  [["Emergency", r.incident.type], ["Location", r.incident.name], ["Ambulance", `${r.ambulance.name} (from ${nodeName(r.ambulance.node)})`],
   ["Hospital", r.hospital.name], ["Algorithm", r.algorithm], ["Total cost", String(r.total_cost)]]
    .forEach(([k, v]) => kv.append(el("dt", "", k), el("dd", "", v)));
  const r1 = el("div", "route"), r2 = el("div", "route green");
  r1.append(el("b", "", `Ambulance → Incident (cost ${r.route_to_incident.cost})`), el("span", "", pathText(r.route_to_incident.path)));
  r2.append(el("b", "", `Incident → Hospital (cost ${r.route_to_hospital.cost})`), el("span", "", pathText(r.route_to_hospital.path)));
  card.append(kv, r1, r2, el("p", "note", "Hospital ranking (lower is better): " + r.hospital_ranking.map((h) => `${h.name} (${h.score})`).join(", ")));
  $("comparison").replaceChildren(...comparisonTable(r.comparison));
}

async function dispatch() {
  const btn = $("dispatch");
  btn.disabled = true;
  try {
    const r = await post("/api/dispatch", { location: $("location").value, emergency_type: $("etype").value, algorithm: $("algo").value });
    showDispatch(r);
    toast(`Ambulance ${r.ambulance.name} dispatched`);
    await refresh();
  } catch (err) { toast(err.message, true); } finally { btn.disabled = false; }
}

function randomEmergency() {
  const pick = (id) => { const o = $(id).options; $(id).selectedIndex = Math.floor(Math.random() * o.length); };
  pick("etype"); pick("location");
  dispatch();
}

async function toggleRoad(a, b) {
  try {
    const res = await post("/api/roads/toggle", { a, b });
    toast(`Road ${nodeName(a)} ↔ ${nodeName(b)} ${res.blocked ? "blocked" : "reopened"}`);
    await refresh();
  } catch (err) { toast(err.message, true); }
}

/* ---------- algorithm lab ---------- */
function pickLabNode(id) {
  $(labNext === "from" ? "lab-from" : "lab-to").value = id;
  $("lab-status").textContent = `${labNext === "from" ? "Start" : "Destination"} set to ${nodeName(id)}.`;
  labNext = labNext === "from" ? "to" : "from";
}

async function runLab() {
  const start = $("lab-from").value, end = $("lab-to").value, algo = $("lab-algo").value;
  if (start === end) { toast("Choose two different locations.", true); return; }
  const token = ++labToken, btn = $("lab-run");
  btn.disabled = true;
  try {
    const rows = (await post("/api/lab", { start, end })).results;
    $("lab-table").replaceChildren(...comparisonTable(rows));
    const r = rows.find((x) => x.algorithm === algo), delay = Number($("lab-speed").value);
    lm.routes.clearLayers();
    lm.marks.clearLayers();
    L.marker(latlng(start), { icon: pin("amb", "S"), zIndexOffset: 700 }).addTo(lm.marks);
    L.marker(latlng(end), { icon: pin("incident", "E"), zIndexOffset: 700 }).addTo(lm.marks);
    for (let i = 0; i < r.visited_order.length; i++) {
      if (token !== labToken) return;
      const icon = L.divIcon({ className: "", html: `<div class="step">${i + 1}</div>`, iconSize: [22, 22], iconAnchor: [11, 11] });
      L.marker(latlng(r.visited_order[i]), { icon, zIndexOffset: 400 }).addTo(lm.routes);
      $("lab-status").textContent = `${algo}: exploring ${nodeName(r.visited_order[i])} (${i + 1}/${r.visited_order.length})`;
      await sleep(delay);
    }
    if (r.found) {
      L.polyline(r.path.map(latlng), { color: ALGO_COLORS[algo], weight: 7, opacity: .9 }).addTo(lm.routes);
      $("lab-status").textContent = `${algo} explored ${r.visited} nodes and found a path with cost ${r.cost} (${r.hops} roads).`;
    } else {
      $("lab-status").textContent = `${algo} explored ${r.visited} nodes: no route exists (check blocked roads).`;
    }
  } catch (err) { toast(err.message, true); } finally { btn.disabled = false; }
}

/* ---------- incidents ---------- */
async function loadIncidents() {
  const q = encodeURIComponent($("inc-search").value.trim());
  const data = await api(`/api/incidents?q=${q}&status=${$("inc-status").value}`);
  const body = $("inc-body");
  body.replaceChildren();
  $("inc-count").textContent = `${data.items.length} record(s)`;
  if (!data.items.length) {
    const tr = el("tr"), td = el("td", "empty", "No matching emergencies.");
    td.colSpan = 10;
    tr.append(td);
    body.append(tr);
    return;
  }
  data.items.forEach((i) => {
    const tr = el("tr");
    [`#${i.id}`, i.created_at, i.emergency_type, i.location, i.ambulance, i.hospital, i.algorithm, i.total_cost]
      .forEach((v) => tr.append(el("td", "", String(v))));
    const st = el("td");
    st.append(statusTag(i.status));
    const act = el("td", "actions"), view = el("button", "btn sm ghost", "View");
    view.onclick = () => { showPage("dispatch"); showDispatch(i.payload); };
    act.append(view);
    if (i.status === "Active") {
      const res = el("button", "btn sm", "Resolve");
      res.onclick = () => resolveIncident(i.id);
      act.append(res);
    }
    tr.append(st, act);
    body.append(tr);
  });
}

async function resolveIncident(id) {
  try {
    await post(`/api/incidents/${id}/resolve`);
    toast(`Incident #${id} resolved. Ambulance is back in service at the hospital.`);
    await refresh();
  } catch (err) { toast(err.message, true); }
}

async function resetAll(clearHistory) {
  const msg = clearHistory ? "Delete ALL incident history and reset fleet, beds and roads?" : "Reset fleet, hospital beds and road closures? Incident history is kept.";
  if (!confirm(msg)) return;
  await post("/api/reset", { clear_history: clearHistory });
  dm.routes.clearLayers();
  dm.marks.clearLayers();
  toast(clearHistory ? "All data cleared" : "Simulation reset");
  await refresh();
}

/* ---------- resources ---------- */
async function action(url) {
  try { await post(url); await refresh(); } catch (err) { toast(err.message, true); }
}

function renderResources() {
  const fleet = $("res-fleet"), hosp = $("res-hosp"), roads = $("res-roads");
  [fleet, hosp, roads].forEach((b) => b.replaceChildren());

  state.ambulances.forEach((a) => {
    const row = el("div", "res-row"), info = el("div"), right = el("div", "res-actions");
    info.append(el("b", "", a.name), el("small", "", nodeName(a.node)));
    const btn = el("button", "btn sm ghost", a.available ? "Take offline" : "Bring online");
    btn.onclick = () => action(`/api/ambulances/${a.id}/toggle`);
    right.append(el("span", "tag " + (a.available ? "ok" : "busy"), a.available ? "Available" : "Unavailable"), btn);
    row.append(info, right);
    fleet.append(row);
  });

  state.hospitals.forEach((h) => {
    const row = el("div", "res-row"), info = el("div"), right = el("div", "res-actions");
    const pct = Math.round((100 * h.beds) / h.capacity), bar = el("div", "bar"), fill = el("i", pct <= 10 ? "low" : pct <= 35 ? "mid" : "");
    fill.style.width = pct + "%";
    bar.append(fill);
    info.append(el("b", "", h.name), el("small", "", `${h.beds}/${h.capacity} beds free`), bar);
    const btn = el("button", "btn sm ghost", "Discharge patient");
    btn.disabled = h.beds >= h.capacity;
    btn.onclick = () => action(`/api/hospitals/${h.id}/discharge`);
    right.append(btn);
    row.append(info, right);
    hosp.append(row);
  });

  const blocked = state.edges.filter((e) => e.blocked);
  if (!blocked.length) roads.append(el("p", "empty", "No roads are blocked. Click a road on the Dispatch map to close it."));
  blocked.forEach((e) => {
    const row = el("div", "res-row"), btn = el("button", "btn sm ghost", "Reopen");
    btn.onclick = () => toggleRoad(e.a, e.b);
    row.append(el("span", "", `${nodeName(e.a)} ↔ ${nodeName(e.b)}`), btn);
    roads.append(row);
  });
}

/* ---------- live refresh ---------- */
function fillSelect(id, items, labelFn) {
  const sel = $(id);
  if (sel.options.length) return;
  items.forEach((v) => sel.append(new Option(labelFn ? labelFn(v) : v, Array.isArray(v) ? v[0] : v)));
}

async function refresh() {
  const [net, summary, recent] = await Promise.all([api("/api/network"), api("/api/summary"), api("/api/incidents?limit=6")]);
  Object.assign(state, net, { summary, types: net.emergency_types });

  const nodeList = Object.entries(state.nodes);
  fillSelect("location", nodeList, (e) => e[1].name);
  fillSelect("lab-from", nodeList, (e) => e[1].name);
  fillSelect("lab-to", nodeList, (e) => e[1].name);
  fillSelect("etype", state.types);
  fillSelect("algo", state.algorithms);
  fillSelect("lab-algo", state.algorithms);
  if (!$("algo").dataset.init) { $("algo").value = "A*"; $("lab-algo").value = "A*"; $("lab-to").selectedIndex = 5; $("algo").dataset.init = "1"; }

  const sig = JSON.stringify([state.edges.map((e) => e.blocked), state.ambulances.map((a) => [a.node, a.available]), state.hospitals.map((h) => h.beds)]);
  if (sig !== drawnSig) { drawNetwork(dm, "dispatch"); drawNetwork(lm, "lab"); drawnSig = sig; }

  renderKpis();
  renderCharts();
  renderActivity(recent.items);
  renderResources();
  if (currentPage === "incidents") loadIncidents();
  $("updated").textContent = new Date().toLocaleTimeString();
}

/* ---------- start ---------- */
let searchTimer;
document.querySelectorAll(".nav-btn").forEach((b) => b.addEventListener("click", () => showPage(b.dataset.page)));
$("theme").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
$("dispatch").addEventListener("click", dispatch);
$("random").addEventListener("click", randomEmergency);
$("lab-run").addEventListener("click", runLab);
$("reset").addEventListener("click", () => resetAll(false));
$("clear-all").addEventListener("click", () => resetAll(true));
$("inc-status").addEventListener("change", loadIncidents);
$("inc-search").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadIncidents, 250); });

let savedTheme = "light";
try { savedTheme = localStorage.getItem("sr-theme") || "light"; } catch (e) { /* ignore */ }
applyTheme(savedTheme);
showPage(location.hash.slice(1));
refresh().catch((e) => toast(e.message, true));
setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 5000);

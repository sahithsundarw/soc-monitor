// SOC Monitor dashboard. Polls the Flask JSON API once a second (plain HTTP GET,
// no websockets) and sends control actions with POST. No external libraries.
"use strict";

const POLL_MS = 1000;
const SLOW_POLL_MS = 5000;
const STALE_AFTER_MS = 5000;
const TAB_TITLES = {
  overview: "Overview",
  topology: "Topology",
  controls: "Controls",
  inspector: "Packet Inspector",
  reports: "Reports",
  emails: "Emails",
  diagnostics: "Diagnostics",
};
const SEVERITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
const SEVERITY_NAMES = { CRITICAL: "Critical", HIGH: "High", MEDIUM: "Medium", LOW: "Low" };
const METHOD_NAMES = { character: "Character stuffing", bit: "Bit stuffing" };
const SVG_NS = "http://www.w3.org/2000/svg";

const view = {
  tab: "overview",
  routeSensor: "S1",
  floodSensor: "S1",
  alertFilter: "ALL",
  selectedEvent: null,
  selectedMail: null,
  seenAlerts: new Set(),
  firstAlertRender: true,
  lastSlowPoll: 0,
  lastUpdate: 0,
  status: null,
  chartHover: null,
  diagnosticsLoaded: false,
  // Lists hold still while the pointer is on them, so a poll can't swallow a click.
  pointerOnEvents: false,
  pointerOnLinks: false,
  pointerOnInbox: false,
  // An unapplied slider value is never overwritten by the poll.
  noiseEdited: false,
};

// ---------- helpers ----------

function $(id) {
  return document.getElementById(id);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function svg(tag, attrs) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs || {})) node.setAttribute(key, value);
  return node;
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleTimeString([], { hour12: false });
}

function formatNumber(value) {
  return Number(value).toLocaleString();
}

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.floor(minutes / 60)}h ${String(minutes % 60).padStart(2, "0")}m`;
}

function plural(count, word) {
  return count === 1 ? word : `${word}s`;
}

function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}

function routeText(path) {
  return path.join(" → ");
}

function storageGet(key) {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
}

function storageSet(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Storage can be unavailable (private mode); the setting just isn't remembered.
  }
}

function isNetworkError(error) {
  return error instanceof TypeError && /fetch/i.test(error.message);
}

async function api(path, payload) {
  const options = payload === undefined
    ? {}
    : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) };
  const response = await fetch(path, options);
  const body = await response.json();
  if (body.error) throw new Error(body.error);
  return body.data;
}

function toast(message, isError) {
  const node = el("div", isError ? "toast is-error" : "toast", message);
  $("toasts").appendChild(node);
  setTimeout(() => node.remove(), 2800);
}

async function runAction(button, request, successMessage) {
  if (button) button.disabled = true;
  try {
    const data = await request();
    toast(typeof successMessage === "function" ? successMessage(data) : successMessage);
    return data;
  } catch (error) {
    toast(error.message, true);
    return null;
  } finally {
    if (button) button.disabled = false;
  }
}

function setActive(container, attribute, value) {
  for (const button of container.querySelectorAll("button")) {
    button.classList.toggle("is-active", button.dataset[attribute] === value);
  }
}

function holdWhileHovered(element, flag) {
  element.addEventListener("mouseenter", () => { view[flag] = true; });
  element.addEventListener("mouseleave", () => { view[flag] = false; });
}

function keyValues(pairs, monoKeys) {
  const list = el("dl", "kv");
  for (const [key, value] of pairs) {
    list.appendChild(el("dt", "", key));
    list.appendChild(el("dd", (monoKeys || []).includes(key) ? "mono" : "", value));
  }
  return list;
}

// ---------- theme and tabs ----------

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  $("theme-toggle").textContent = theme === "dark" ? "Light mode" : "Dark mode";
  if (view.status) drawQosChart(view.status.qos.timeline);
}

function initTheme() {
  const saved = storageGet("theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  applyTheme(saved || (prefersDark ? "dark" : "light"));
  $("theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    storageSet("theme", next);
    applyTheme(next);
  });
}

function showTab(tab) {
  view.tab = tab;
  for (const button of document.querySelectorAll(".nav-item")) {
    button.classList.toggle("is-active", button.dataset.tab === tab);
  }
  for (const section of document.querySelectorAll(".tab")) {
    section.classList.toggle("is-active", section.id === `tab-${tab}`);
  }
  $("page-title").textContent = TAB_TITLES[tab];
  storageSet("tab", tab);
  view.chartHover = null; // the pointer is no longer on the chart
  $("qos-tip").hidden = true;
  view.lastSlowPoll = 0;
  if (view.status) renderStatus(view.status);
  refreshTab();
}

function initTabs() {
  for (const button of document.querySelectorAll(".nav-item")) {
    button.addEventListener("click", () => showTab(button.dataset.tab));
  }
  const saved = storageGet("tab");
  if (saved && TAB_TITLES[saved]) showTab(saved);
}

// ---------- top bar and sidebar ----------

function setStatus(state, text) {
  const status = $("top-status");
  status.dataset.state = state;
  status.textContent = text;
}

function renderTopbar(status) {
  if (status.running) {
    setStatus("running", status.uptime_s === null ? "Running" : `Running ${formatDuration(status.uptime_s)}`);
  } else {
    setStatus("stopped", "Stopped");
  }
  $("top-events").textContent = formatNumber(status.tiles.events);
  $("top-alerts").textContent = formatNumber(status.tiles.alerts);
  const route = status.routes.S1;
  $("top-route").textContent = route && route.path.length ? routeText(route.path) : "no route";
}

function renderSidebar(status) {
  const { settings } = status;
  $("side-method").textContent = settings.method === "bit" ? "Bit" : "Character";
  $("side-crc").textContent = settings.crc_type;
  $("side-noise").textContent = `${Math.round(settings.error_rate * 100)}%`;
  const count = $("nav-email-count");
  count.hidden = status.email_count === 0;
  count.textContent = status.email_count;
}

function renderFreshness() {
  if (!view.lastUpdate) return;
  const age = Date.now() - view.lastUpdate;
  if (age > STALE_AFTER_MS) setStatus("stale", `Stale ${Math.round(age / 1000)}s`);
}

// ---------- overview: stat strip ----------

function renderTiles(status) {
  for (const [key, value] of Object.entries(status.tiles)) {
    $(`tile-${key}`).textContent = formatNumber(value);
    // Show the per-minute rate only when it says something the total does not.
    const lastMinute = sum(status.trends[key] || []);
    $(`rate-${key}`).textContent = lastMinute && lastMinute !== value ? `+${formatNumber(lastMinute)}/min` : "";
  }
}

// ---------- overview: alerts ----------

function alertKey(alert) {
  return `${alert.ts}|${alert.rule}|${alert.source}`;
}

function renderSeverityChips(counts) {
  $("chip-ALL").textContent = formatNumber(sum(Object.values(counts)));
  for (const severity of SEVERITIES) {
    $(`chip-${severity}`).textContent = formatNumber(counts[severity] || 0);
  }
  setActive($("severity-chips"), "severity", view.alertFilter);
}

function alertItem(alert) {
  const item = el("li", "alert-item");
  const key = alertKey(alert);
  if (!view.seenAlerts.has(key) && !view.firstAlertRender) item.classList.add("is-new");
  view.seenAlerts.add(key);
  item.appendChild(el("span", "alert-time", formatTime(alert.ts)));
  item.appendChild(el("span", `alert-severity sev-${alert.severity}`, SEVERITY_NAMES[alert.severity]));
  const text = el("div");
  text.appendChild(el("div", "alert-title", alert.title));
  text.appendChild(el("div", "alert-detail", alert.detail));
  item.appendChild(text);
  return item;
}

function renderAlerts(alerts) {
  const shown = view.alertFilter === "ALL" ? alerts : alerts.filter((a) => a.severity === view.alertFilter);
  const empty = $("alert-empty");
  empty.hidden = shown.length > 0;
  if (!alerts.length) {
    empty.textContent = "No alerts yet";
  } else if (view.alertFilter !== "ALL") {
    empty.textContent = `No ${SEVERITY_NAMES[view.alertFilter].toLowerCase()} alerts`;
  }
  const feed = $("alert-feed");
  feed.hidden = shown.length === 0;
  feed.replaceChildren(...shown.map(alertItem));
  view.firstAlertRender = false;
}

function initAlertFilter() {
  for (const button of $("severity-chips").querySelectorAll("button")) {
    button.addEventListener("click", () => {
      view.alertFilter = button.dataset.severity;
      if (view.status) {
        renderSeverityChips(view.status.severity_counts);
        renderAlerts(view.status.alerts);
      }
    });
  }
}

// ---------- overview: token bucket chart ----------

function chartGeometry(canvas, count) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  const left = 40;
  const top = 40; // room for the unit label above the highest tick
  const bottom = height - 24;
  return { width, height, left, top, bottom, plotHeight: bottom - top, slot: (width - left) / count };
}

// The axis never drops below 10 frames/s, so routine traffic sits low and a
// flood visibly spikes instead of every second filling the plot.
const CHART_MIN_TOP = 10;

function niceTop(peak) {
  const step = peak <= 10 ? 2 : peak <= 50 ? 10 : peak <= 200 ? 50 : 100;
  const top = Math.ceil(peak / (2 * step)) * 2 * step; // even, so the midline is whole
  return Math.max(CHART_MIN_TOP, top);
}

function fillBar(ctx, x, y, width, height, roundTop) {
  if (height <= 0) return;
  ctx.beginPath();
  if (roundTop && ctx.roundRect) ctx.roundRect(x, y, width, height, [2, 2, 0, 0]);
  else ctx.rect(x, y, width, height);
  ctx.fill();
}

function drawQosChart(timeline) {
  const canvas = $("qos-chart");
  const ratio = window.devicePixelRatio || 1;
  const geo = chartGeometry(canvas, timeline.length);
  if (!geo.width) return;
  canvas.width = geo.width * ratio;
  canvas.height = geo.height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, geo.width, geo.height);

  const top = niceTop(Math.max(0, ...timeline.map((s) => s.allowed + s.dropped)));
  const muted = cssVar("--muted");
  ctx.font = `14px ${cssVar("--font-ui")}`;
  ctx.fillStyle = muted;
  ctx.textAlign = "left";
  ctx.fillText("frames per second", 0, 14);
  for (const fraction of [0, 0.5, 1]) {
    const y = Math.round(geo.bottom - geo.plotHeight * fraction) + 0.5;
    ctx.strokeStyle = cssVar("--line");
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(geo.left, y);
    ctx.lineTo(geo.width, y);
    ctx.stroke();
    ctx.fillStyle = muted;
    ctx.textAlign = "right";
    ctx.fillText(String(top * fraction), geo.left - 8, y + 5);
  }
  ctx.textAlign = "left";
  ctx.fillText("60 s ago", geo.left, geo.height - 4);
  ctx.textAlign = "right";
  ctx.fillText("now", geo.width, geo.height - 4);

  if (view.chartHover !== null) {
    ctx.fillStyle = cssVar("--fill-strong");
    ctx.fillRect(geo.left + view.chartHover * geo.slot, geo.top, geo.slot, geo.plotHeight);
  }

  const accent = cssVar("--series-primary");
  const neutral = cssVar("--neutral-series");
  const barWidth = Math.max(1, Math.round(geo.slot * 0.6));
  timeline.forEach((second, index) => {
    const x = geo.left + index * geo.slot + (geo.slot - barWidth) / 2;
    const allowedHeight = (second.allowed / top) * geo.plotHeight;
    const droppedHeight = (second.dropped / top) * geo.plotHeight;
    ctx.fillStyle = accent;
    fillBar(ctx, x, geo.bottom - allowedHeight, barWidth, allowedHeight, droppedHeight === 0);
    // A 2px gap separates the stacked segments.
    const droppedTop = geo.bottom - allowedHeight - droppedHeight - (allowedHeight ? 2 : 0);
    ctx.fillStyle = neutral;
    fillBar(ctx, x, droppedTop, barWidth, droppedHeight, true);
  });
}

function showChartTip(index) {
  const timeline = view.status.qos.timeline;
  const second = timeline[index];
  const tip = $("qos-tip");
  const row = (swatch, label, value) => {
    const line = el("div", "tip-row");
    line.appendChild(el("i", `swatch ${swatch}`));
    line.appendChild(el("span", "", label));
    line.appendChild(el("strong", "", value));
    return line;
  };
  tip.replaceChildren(
    el("div", "tip-time", formatTime(second.t)),
    row("swatch-allowed", "Allowed", second.allowed),
    row("swatch-dropped", "Dropped", second.dropped),
  );
  tip.hidden = false;
  const geo = chartGeometry($("qos-chart"), timeline.length);
  const x = geo.left + (index + 0.5) * geo.slot;
  const flip = x > geo.width / 2;
  tip.style.left = flip ? "" : `${x + 16}px`;
  tip.style.right = flip ? `${geo.width - x + 16}px` : "";
}

function hideChartTip() {
  view.chartHover = null;
  $("qos-tip").hidden = true;
  if (view.status) drawQosChart(view.status.qos.timeline);
}

function initChartHover() {
  const canvas = $("qos-chart");
  canvas.addEventListener("mousemove", (event) => {
    if (!view.status) return;
    const timeline = view.status.qos.timeline;
    const geo = chartGeometry(canvas, timeline.length);
    const x = event.clientX - canvas.getBoundingClientRect().left;
    // The hit area is the whole column slot, wider than the bar itself.
    const index = Math.floor((x - geo.left) / geo.slot);
    if (index < 0 || index >= timeline.length) {
      hideChartTip();
      return;
    }
    view.chartHover = index;
    drawQosChart(timeline);
    showChartTip(index);
  });
  canvas.addEventListener("mouseleave", hideChartTip);
}

// ---------- overview: split and sensor table ----------

function renderSplit(protocols) {
  const total = protocols.udp + protocols.tcp;
  const udpShare = total ? Math.round((protocols.udp / total) * 100) : 0;
  const tcpShare = total ? 100 - udpShare : 0;
  $("split-bar").children[0].style.width = `${total ? udpShare : 50}%`;
  $("split-bar").children[1].style.width = `${total ? tcpShare : 50}%`;
  $("share-udp").textContent = `${udpShare}%`;
  $("share-tcp").textContent = `${tcpShare}%`;
  $("split-udp").textContent = `(${formatNumber(protocols.udp)})`;
  $("split-tcp").textContent = `(${formatNumber(protocols.tcp)})`;
}

function sensorRow(name, values, cellTag) {
  const row = el("tr");
  row.appendChild(el(cellTag, "", name));
  for (const value of values) row.appendChild(el(cellTag, value ? "num" : "num cell-quiet", formatNumber(value)));
  return row;
}

function renderSensorTable(perSensor) {
  const totals = [0, 0, 0, 0, 0];
  const rows = Object.entries(perSensor).map(([sensor, byProtocol]) => {
    const { udp, tcp } = byProtocol;
    const values = [
      udp.good,
      tcp.good,
      udp.corrupted + tcp.corrupted,
      udp.retransmitted + tcp.retransmitted,
      udp.lost + tcp.lost,
    ];
    values.forEach((value, index) => { totals[index] += value; });
    return sensorRow(sensor === "unknown" ? "Unreadable" : sensor, values, "td");
  });
  const table = $("sensor-table");
  table.querySelector("tbody").replaceChildren(...rows);
  table.querySelector("tfoot").replaceChildren(sensorRow("All sensors", totals, "td"));
}

function renderControlsState(settings) {
  setActive($("method-picker"), "method", settings.method);
  setActive($("crc-picker"), "crc", settings.crc_type);
  if (!view.noiseEdited) {
    const percent = Math.round(settings.error_rate * 100);
    $("noise-slider").value = percent;
    $("noise-value").textContent = `${percent}%`;
  }
}

function renderStatus(status) {
  renderTopbar(status);
  renderSidebar(status);
  if (view.tab === "overview") {
    renderTiles(status);
    renderSeverityChips(status.severity_counts);
    renderAlerts(status.alerts);
    drawQosChart(status.qos.timeline);
    if (view.chartHover !== null) showChartTip(view.chartHover);
    renderSplit(status.protocols);
    renderSensorTable(status.per_sensor);
  }
  if (view.tab === "controls") renderControlsState(status.settings);
}

async function refreshStatus() {
  let status;
  try {
    status = await api("/api/status");
  } catch (error) {
    // Only a failed request means "disconnected"; rendering errors must surface.
    if (!view.lastUpdate) setStatus("stopped", "Disconnected");
    renderFreshness();
    return;
  }
  view.status = status;
  view.lastUpdate = Date.now();
  document.body.classList.remove("is-loading");
  renderStatus(status);
  renderFreshness();
}

// ---------- topology ----------

function linkKey(a, b) {
  return a < b ? `${a}-${b}` : `${b}-${a}`;
}

function routeLinks(path) {
  const keys = new Set();
  for (let i = 0; i + 1 < path.length; i += 1) keys.add(linkKey(path[i], path[i + 1]));
  return keys;
}

function drawTopology(topology) {
  const canvas = $("topology");
  const route = topology.routes[view.routeSensor] || { path: [], cost: null };
  const onRoute = routeLinks(route.path);
  const position = Object.fromEntries(topology.nodes.map((n) => [n.id, n]));
  canvas.replaceChildren();

  for (const link of topology.links) {
    const a = position[link.a];
    const b = position[link.b];
    const classes = ["topo-link"];
    if (!link.up) classes.push("is-down");
    if (link.up && onRoute.has(linkKey(link.a, link.b))) classes.push("is-route");
    canvas.appendChild(svg("line", { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: classes.join(" ") }));
    const midX = (a.x + b.x) / 2;
    const midY = (a.y + b.y) / 2;
    const label = link.up ? String(link.cost) : "down";
    const labelWidth = label.length * 8 + 12;
    canvas.appendChild(svg("rect", { x: midX - labelWidth / 2, y: midY - 10, width: labelWidth, height: 18, rx: 4, class: "topo-cost-bg" }));
    const cost = svg("text", { x: midX, y: midY + 4, class: "topo-cost" });
    cost.textContent = label;
    canvas.appendChild(cost);
  }

  for (const node of topology.nodes) {
    const classes = ["topo-node", `role-${node.role}`];
    if (route.path.includes(node.id)) classes.push("is-route");
    const group = svg("g", { class: classes.join(" "), transform: `translate(${node.x} ${node.y})` });
    group.appendChild(svg("rect", { x: -66, y: -25, width: 132, height: 50, rx: 8 }));
    const label = svg("text", { x: -52, y: -3, class: "node-id" });
    label.textContent = node.id;
    if (node.role === "sensor") {
      const name = svg("tspan", { class: "node-name", dx: 6 });
      name.textContent = node.name;
      label.appendChild(name);
    }
    const ip = svg("text", { x: -52, y: 15, class: "node-ip" });
    ip.textContent = node.sim_ip;
    group.append(label, ip);
    canvas.appendChild(group);
  }

  $("route-line").textContent = route.path.length
    ? `${routeText(route.path)}, cost ${route.cost}`
    : "no route to the SOC";
}

function renderLinkTable(links) {
  const rows = links.map((link) => {
    const row = el("tr");
    row.appendChild(el("td", "mono", `${link.a} – ${link.b}`));
    row.appendChild(el("td", "num", link.cost));
    row.appendChild(el("td", link.up ? "" : "state-down", link.up ? "Up" : "Down"));
    const cell = el("td", "num");
    const action = link.up ? "fail" : "restore";
    const button = el("button", "btn btn-ghost btn-action", link.up ? "Fail" : "Restore");
    button.type = "button";
    button.setAttribute("aria-label", `${link.up ? "Fail" : "Restore"} link ${link.a}-${link.b}`);
    button.addEventListener("click", async () => {
      const done = await runAction(
        button,
        () => api(`/api/links/${action}`, { a: link.a, b: link.b }),
        `Link ${link.a}-${link.b} ${link.up ? "failed" : "restored"}. Routes recomputed.`,
      );
      if (done) {
        view.pointerOnLinks = false;
        await refreshTopology();
        view.pointerOnLinks = $("link-table").matches(":hover");
      }
    });
    cell.appendChild(button);
    row.appendChild(cell);
    return row;
  });
  $("link-table").querySelector("tbody").replaceChildren(...rows);
}

function renderForwardingTables(topology) {
  const table = $("fwd-table");
  const head = el("tr");
  head.appendChild(el("th", "", "Router"));
  for (const destination of topology.destinations) head.appendChild(el("th", "", destination));
  table.querySelector("thead").replaceChildren(head);
  const rows = Object.entries(topology.tables).map(([router, nextHops]) => {
    const row = el("tr");
    row.appendChild(el("td", "cell-strong", router));
    for (const destination of topology.destinations) {
      const isSelf = destination === router;
      row.appendChild(el("td", isSelf ? "cell-quiet" : "", isSelf ? "—" : nextHops[destination] || "-"));
    }
    return row;
  });
  table.querySelector("tbody").replaceChildren(...rows);
}

async function refreshTopology() {
  const topology = await api("/api/topology");
  drawTopology(topology);
  if (!view.pointerOnLinks) renderLinkTable(topology.links);
  renderForwardingTables(topology);
}

function initTopology() {
  for (const button of $("route-picker").querySelectorAll("button")) {
    button.addEventListener("click", () => {
      view.routeSensor = button.dataset.sensor;
      setActive($("route-picker"), "sensor", view.routeSensor);
      refreshTopology();
    });
  }
  holdWhileHovered($("link-table"), "pointerOnLinks");
}

// ---------- controls ----------

function initControls() {
  const slider = $("noise-slider");
  slider.addEventListener("input", () => {
    view.noiseEdited = true;
    $("noise-value").textContent = `${slider.value}%`;
  });
  $("noise-apply").addEventListener("click", async (event) => {
    const rate = Number(slider.value) / 100;
    await runAction(event.currentTarget, () => api("/api/noise", { error_rate: rate }), `Line noise set to ${slider.value}% per link`);
    view.noiseEdited = false;
  });

  for (const button of $("method-picker").querySelectorAll("button")) {
    button.addEventListener("click", () =>
      runAction(button, () => api("/api/settings", { method: button.dataset.method }), `Framing switched to ${button.textContent.toLowerCase()}`),
    );
  }
  for (const button of $("crc-picker").querySelectorAll("button")) {
    button.addEventListener("click", () =>
      runAction(button, () => api("/api/settings", { crc_type: button.dataset.crc }), `CRC switched to ${button.dataset.crc}`),
    );
  }

  const attackNames = { brute_force: "Brute force", port_scan: "Port scan", beacon: "Malware beacon" };
  for (const button of document.querySelectorAll("[data-attack]")) {
    button.addEventListener("click", () =>
      runAction(
        button,
        () => api("/api/attack", { attack: button.dataset.attack }),
        (data) => `${attackNames[data.attack]} launched from ${data.sensor}`,
      ),
    );
  }

  for (const button of $("flood-picker").querySelectorAll("button")) {
    button.addEventListener("click", () => {
      view.floodSensor = button.dataset.sensor;
      setActive($("flood-picker"), "sensor", view.floodSensor);
    });
  }
  $("flood-btn").addEventListener("click", (event) =>
    runAction(
      event.currentTarget,
      () => api("/api/flood", { sensor: view.floodSensor, spoof: false }),
      (data) => `Flooding ${data.frames} frames from ${data.sensor}`,
    ),
  );
  $("spoof-btn").addEventListener("click", (event) =>
    runAction(
      event.currentTarget,
      () => api("/api/flood", { sensor: view.floodSensor, spoof: true }),
      (data) => `Sent ${data.frames} spoofed frames via ${data.sensor}`,
    ),
  );
}

// ---------- packet inspector ----------

function renderEventList(events) {
  $("event-empty").hidden = events.length > 0;
  const rows = events.map((event) => {
    const row = el("tr");
    row.tabIndex = 0;
    row.dataset.id = event.id;
    if (event.id === view.selectedEvent) row.classList.add("is-active");
    row.appendChild(el("td", "mono", formatTime(event.received_at)));
    row.appendChild(el("td", "", event.type.replace(/_/g, " ")));
    row.appendChild(el("td", "", event.sensor));
    row.appendChild(el("td", "mono", event.protocol.toUpperCase()));
    row.addEventListener("click", () => selectEvent(event.id));
    row.addEventListener("keydown", (keyEvent) => {
      if (keyEvent.key === "Enter" || keyEvent.key === " ") {
        keyEvent.preventDefault();
        selectEvent(event.id);
      }
    });
    return row;
  });
  $("event-list").replaceChildren(...rows);
}

function layerSection(number, title, children) {
  const section = el("section", "layer");
  const heading = el("h3", "layer-title");
  heading.append(el("span", "layer-number", number), title);
  section.appendChild(heading);
  for (const child of children) section.appendChild(child);
  return section;
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to the clipboard");
  } catch (error) {
    toast("Copy is not available here. Select the text instead.", true);
  }
}

function codeBlock(label, text) {
  const wrapper = el("div");
  const head = el("div", "code-head");
  head.appendChild(el("span", "", label));
  const copy = el("button", "btn btn-ghost", "Copy");
  copy.type = "button";
  copy.setAttribute("aria-label", `Copy ${label.toLowerCase()}`);
  copy.addEventListener("click", () => copyText(text));
  head.appendChild(copy);
  wrapper.append(head, el("pre", "code", text));
  return wrapper;
}

function renderLayers(layers) {
  const { application, transport, network, datalink } = layers;
  const priorities = ["normal", "high", "critical"];
  const head = el("header", "panel-head");
  head.append(el("h2", "panel-title", "Frame"), el("span", "muted mono", layers.id));
  $("layers").replaceChildren(
    head,
    layerSection(7, "Application", [el("pre", "code", application.json)]),
    layerSection(4, "Transport", [
      keyValues(
        [
          ["Protocol", transport.protocol],
          ["Source port", transport.src_port],
          ["Destination port", transport.dst_port],
          ["Delivery", transport.note],
        ],
        ["Source port", "Destination port"],
      ),
    ]),
    layerSection(3, "Network", [
      keyValues(
        [
          ["Source IP", network.src_ip],
          ["Destination IP", network.dst_ip],
          ["TTL on arrival", `${network.ttl}, after ${network.hops} router ${plural(network.hops, "hop")}`],
          ["Path taken", network.path.length ? routeText(network.path) : "unknown"],
          ["Priority", `${network.priority} (${priorities[network.priority]})`],
        ],
        ["Source IP", "Destination IP", "Path taken"],
      ),
    ]),
    layerSection(2, "Data link", [
      keyValues(
        [
          ["Framing", METHOD_NAMES[datalink.method]],
          ["CRC", datalink.crc_type],
          ["Header", datalink.header_text],
          ["Frame type, seq", `${datalink.frame_type}, ${datalink.seq_no}`],
          ["CRC remainder", `${datalink.crc_hex} (${datalink.crc_bits})`],
          ["Size", `${datalink.body_bytes} bytes before stuffing, ${datalink.wire_bytes} on the wire`],
        ],
        ["Header", "CRC remainder"],
      ),
      codeBlock("Stuffed frame with flags, hex", datalink.wire_hex),
      codeBlock("Stuffed frame with flags, binary", datalink.wire_binary),
    ]),
  );
}

async function selectEvent(eventId) {
  view.selectedEvent = eventId;
  for (const row of $("event-list").querySelectorAll("tr")) {
    row.classList.toggle("is-active", row.dataset.id === eventId);
  }
  try {
    renderLayers(await api(`/api/events/${encodeURIComponent(eventId)}`));
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshEvents() {
  if (view.pointerOnEvents) return;
  renderEventList(await api("/api/events"));
}

// ---------- reports, emails, diagnostics ----------

function formatBytes(size) {
  return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB`;
}

async function refreshReports() {
  const files = await api("/api/reports");
  $("ftp-empty").hidden = files.length > 0;
  const rows = files.map((file) => {
    const row = el("tr");
    row.appendChild(el("td", "mono", file.name));
    row.appendChild(el("td", "num", formatBytes(file.size)));
    row.appendChild(el("td", "mono", file.modified));
    return row;
  });
  $("ftp-table").querySelector("tbody").replaceChildren(...rows);
  // The listing is newest first, so its first file is the latest upload.
  $("report-last").textContent = files.length ? files[0].modified : "never";
}

function initReports() {
  $("report-btn").addEventListener("click", async (event) => {
    const result = await runAction(
      event.currentTarget,
      () => api("/api/reports", {}),
      (data) => `Uploaded ${data.uploaded.join(" and ")}`,
    );
    if (result) refreshReports();
  });
}

// Alert emails have subjects like "[HIGH] Brute-force login".
function splitSubject(subject) {
  const match = /^\[(\w+)\]\s*(.*)$/.exec(subject);
  return match ? { severity: match[1], title: match[2] } : { severity: "", title: subject };
}

function showMail(mail) {
  view.selectedMail = mail.id;
  const { title } = splitSubject(mail.subject);
  $("mail-subject").textContent = title;
  $("mail-meta").replaceWith(
    Object.assign(
      keyValues(
        [
          ["From", mail.sender],
          ["To", mail.recipient],
          ["Received", formatTime(mail.received_at)],
        ],
        ["From", "To"],
      ),
      { id: "mail-meta" },
    ),
  );
  $("mail-body").textContent = mail.body;
}

async function refreshInbox() {
  if (view.pointerOnInbox) return;
  const mails = await api("/api/emails");
  $("inbox-empty").hidden = mails.length > 0;
  const items = mails.map((mail) => {
    const item = el("li");
    const button = el("button", "mail-row");
    button.type = "button";
    if (mail.id === view.selectedMail) button.classList.add("is-active");
    const { severity, title } = splitSubject(mail.subject);
    button.append(
      el("span", `alert-severity sev-${severity}`, SEVERITY_NAMES[severity] || severity),
      el("span", "mail-subject", title),
      el("span", "mail-time", formatTime(mail.received_at)),
    );
    button.addEventListener("click", () => {
      showMail(mail);
      for (const row of document.querySelectorAll(".mail-row")) row.classList.remove("is-active");
      button.classList.add("is-active");
    });
    item.appendChild(button);
    return item;
  });
  $("inbox").replaceChildren(...items);
}

async function runCommand(command, button) {
  const target = $("diag-target").value;
  for (const other of $("diag-buttons").querySelectorAll(".btn")) other.classList.remove("is-active");
  button.classList.add("is-active");
  $("terminal-title").textContent = command.label;
  $("terminal-meta").textContent = "running…";
  $("terminal").textContent = "Running…";
  const started = performance.now();
  const result = await runAction(
    button,
    () => api("/api/diagnostics", { command: command.id, target }),
    `${command.label} finished`,
  );
  const seconds = ((performance.now() - started) / 1000).toFixed(1);
  if (result) {
    const exit = result.returncode === null ? "timed out" : `exit ${result.returncode}`;
    $("terminal-meta").textContent = `${exit}, ${seconds} s`;
    $("terminal").textContent = `$ ${result.command}\n\n${result.output}`;
  } else {
    $("terminal-meta").textContent = "";
    $("terminal").textContent = "The command could not run. See the message in the corner.";
  }
}

async function loadDiagnostics() {
  const options = await api("/api/diagnostics");
  const target = $("diag-target");
  target.replaceChildren();
  for (const entry of options.targets) {
    const option = el("option", "", `${entry.label} (${entry.ip})`);
    option.value = entry.ip;
    target.appendChild(option);
  }
  const buttons = options.commands.map((command) => {
    const button = el("button", "btn", command.label.replace(" (SOC Monitor ports)", ""));
    button.type = "button";
    button.title = command.summary;
    button.addEventListener("click", () => runCommand(command, button));
    return button;
  });
  $("diag-buttons").replaceChildren(...buttons);
  view.diagnosticsLoaded = true;
}

// ---------- polling ----------

async function refreshTab() {
  try {
    if (view.tab === "topology") await refreshTopology();
    if (view.tab === "inspector") await refreshEvents();
    const now = Date.now();
    const slowDue = now - view.lastSlowPoll >= SLOW_POLL_MS;
    if (view.tab === "reports" && slowDue) {
      view.lastSlowPoll = now;
      await refreshReports();
    }
    if (view.tab === "emails") await refreshInbox();
    if (view.tab === "diagnostics" && !view.diagnosticsLoaded) await loadDiagnostics();
  } catch (error) {
    // A failed request is already shown by the status cell; anything else is a bug.
    if (!isNetworkError(error)) console.error(error);
  }
}

async function poll() {
  try {
    await refreshStatus();
    await refreshTab();
  } catch (error) {
    console.error(error); // keep polling, but never hide a bug
  }
  setTimeout(poll, POLL_MS);
}

initTheme();
initTabs();
initAlertFilter();
initChartHover();
initTopology();
initControls();
initReports();
holdWhileHovered($("event-table"), "pointerOnEvents");
holdWhileHovered($("inbox"), "pointerOnInbox");
window.addEventListener("resize", () => view.status && drawQosChart(view.status.qos.timeline));
setInterval(renderFreshness, 1000);
poll();

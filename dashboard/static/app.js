// SOC Monitor dashboard. Polls the Flask JSON API once a second (plain HTTP GET,
// no websockets) and sends control actions with POST. No external libraries.
"use strict";

const POLL_MS = 1000;
const SLOW_POLL_MS = 5000;
const TAB_TITLES = {
  overview: "Overview",
  topology: "Topology",
  controls: "Controls",
  inspector: "Packet Inspector",
  reports: "Reports",
  emails: "Emails",
  diagnostics: "Diagnostics",
};
const SVG_NS = "http://www.w3.org/2000/svg";

const view = {
  tab: "overview",
  routeSensor: "S1",
  selectedEvent: null,
  selectedMail: null,
  seenAlerts: new Set(),
  firstAlertRender: true,
  lastSlowPoll: 0,
  status: null,
  diagnosticsLoaded: false,
  pointerOnEvents: false,
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
  view.lastSlowPoll = 0;
  refreshTab();
}

function initTabs() {
  for (const button of document.querySelectorAll(".nav-item")) {
    button.addEventListener("click", () => showTab(button.dataset.tab));
  }
  const saved = storageGet("tab");
  if (saved && TAB_TITLES[saved]) showTab(saved);
}

// ---------- top bar and overview ----------

function renderTopbar(status) {
  const pill = $("status-pill");
  pill.dataset.state = status.running ? "running" : "stopped";
  pill.textContent = status.running ? "Running" : "Stopped";
  $("top-events").textContent = formatNumber(status.tiles.events);
  $("top-events-label").textContent = status.tiles.events === 1 ? "event" : "events";
  $("top-alerts").textContent = formatNumber(status.tiles.alerts);
  $("top-alerts-label").textContent = status.tiles.alerts === 1 ? "alert" : "alerts";
  const route = status.routes.S1;
  $("top-route").textContent = route && route.path.length ? route.path.join(" > ") : "no route";
}

function renderTiles(tiles) {
  for (const [key, value] of Object.entries(tiles)) {
    const tile = $(`tile-${key}`);
    if (tile) tile.textContent = formatNumber(value);
  }
}

function alertKey(alert) {
  return `${alert.ts}|${alert.rule}|${alert.source}`;
}

function renderAlerts(alerts) {
  const feed = $("alert-feed");
  $("alert-empty").hidden = alerts.length > 0;
  feed.replaceChildren();
  for (const alert of alerts) {
    const key = alertKey(alert);
    const item = el("li", "alert-item");
    if (!view.seenAlerts.has(key) && !view.firstAlertRender) item.classList.add("is-new");
    view.seenAlerts.add(key);
    item.appendChild(el("span", `badge badge-${alert.severity}`, alert.severity));
    const text = el("div");
    text.appendChild(el("div", "alert-title", alert.title));
    text.appendChild(el("div", "alert-detail", alert.detail));
    item.appendChild(text);
    item.appendChild(el("span", "alert-time", formatTime(alert.ts)));
    feed.appendChild(item);
  }
  view.firstAlertRender = false;
}

function drawQosChart(timeline) {
  const canvas = $("qos-chart");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (!width) return;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);

  const peak = Math.max(4, ...timeline.map((s) => s.allowed + s.dropped));
  const step = peak <= 20 ? 2 : peak <= 100 ? 10 : 50;
  const top = Math.ceil(peak / (2 * step)) * 2 * step; // even, so the midline is whole
  const left = 32;
  const bottom = height - 20;
  const plotHeight = bottom - 8;
  const slot = (width - left) / timeline.length;

  ctx.strokeStyle = cssVar("--border");
  ctx.fillStyle = cssVar("--text-muted");
  ctx.font = `12px ${cssVar("--font-ui")}`;
  ctx.lineWidth = 1;
  for (const fraction of [0, 0.5, 1]) {
    const y = Math.round(bottom - plotHeight * fraction) + 0.5;
    ctx.beginPath();
    ctx.moveTo(left, y);
    ctx.lineTo(width, y);
    ctx.stroke();
    ctx.fillText(String(Math.round(top * fraction)), 0, y + 4);
  }
  ctx.fillText("60 s ago", left, height - 4);
  ctx.fillText("now", width - 24, height - 4);

  const barWidth = Math.max(1, slot - 2);
  timeline.forEach((second, index) => {
    const x = left + index * slot + 1;
    const allowedHeight = (second.allowed / top) * plotHeight;
    const droppedHeight = (second.dropped / top) * plotHeight;
    ctx.fillStyle = cssVar("--accent");
    ctx.fillRect(x, bottom - allowedHeight, barWidth, allowedHeight);
    ctx.fillStyle = cssVar("--neutral-series");
    ctx.fillRect(x, bottom - allowedHeight - droppedHeight, barWidth, droppedHeight);
  });
}

function renderSplit(protocols) {
  const total = protocols.udp + protocols.tcp;
  const udpShare = total ? (protocols.udp / total) * 100 : 50;
  $("split-bar").children[0].style.width = `${udpShare}%`;
  $("split-bar").children[1].style.width = `${100 - udpShare}%`;
  $("split-udp").textContent = formatNumber(protocols.udp);
  $("split-tcp").textContent = formatNumber(protocols.tcp);
}

function renderSensorTable(perSensor) {
  const body = $("sensor-table").querySelector("tbody");
  body.replaceChildren();
  for (const [sensor, byProtocol] of Object.entries(perSensor)) {
    for (const protocol of ["udp", "tcp"]) {
      const counts = byProtocol[protocol];
      const row = el("tr");
      row.appendChild(el("td", "", sensor === "unknown" ? "Unreadable" : sensor));
      row.appendChild(el("td", "", protocol.toUpperCase()));
      for (const key of ["good", "corrupted", "retransmitted", "lost"]) {
        row.appendChild(el("td", "num", formatNumber(counts[key])));
      }
      body.appendChild(row);
    }
  }
}

function renderControlsState(settings) {
  setActive($("method-picker"), "method", settings.method);
  setActive($("crc-picker"), "crc", settings.crc_type);
  if (document.activeElement !== $("noise-slider")) {
    const percent = Math.round(settings.error_rate * 100);
    $("noise-slider").value = percent;
    $("noise-value").textContent = `${percent}%`;
  }
}

async function refreshStatus() {
  try {
    const status = await api("/api/status");
    view.status = status;
    renderTopbar(status);
    if (view.tab === "overview") {
      renderTiles(status.tiles);
      renderAlerts(status.alerts);
      drawQosChart(status.qos.timeline);
      renderSplit(status.protocols);
      renderSensorTable(status.per_sensor);
    }
    if (view.tab === "controls") renderControlsState(status.settings);
  } catch (error) {
    const pill = $("status-pill");
    pill.dataset.state = "stopped";
    pill.textContent = "Disconnected";
  }
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
    const cost = svg("text", { x: midX, y: midY + 3, class: "topo-cost" });
    cost.textContent = label;
    canvas.appendChild(cost);
  }

  for (const node of topology.nodes) {
    const classes = ["topo-node", `role-${node.role}`];
    if (route.path.includes(node.id)) classes.push("is-route");
    const group = svg("g", { class: classes.join(" "), transform: `translate(${node.x} ${node.y})` });
    group.appendChild(svg("rect", { x: -54, y: -24, width: 108, height: 48, rx: 8 }));
    const label = svg("text", { y: -3, class: "node-id" });
    label.textContent = node.role === "sensor" ? `${node.id} ${node.name}` : node.id;
    const ip = svg("text", { y: 14, class: "node-ip" });
    ip.textContent = node.sim_ip;
    group.appendChild(label);
    group.appendChild(ip);
    canvas.appendChild(group);
  }

  const line = $("route-line");
  line.replaceChildren();
  if (route.path.length) {
    line.append(`Current route from ${view.routeSensor}: `);
    line.appendChild(el("strong", "", route.path.join(" > ")));
    line.append(`, cost ${route.cost}`);
  } else {
    line.textContent = `${view.routeSensor} has no route to the SOC. Restore a link.`;
  }
}

function renderLinkTable(links) {
  const body = $("link-table").querySelector("tbody");
  body.replaceChildren();
  for (const link of links) {
    const row = el("tr");
    row.appendChild(el("td", "mono", `${link.a} - ${link.b}`));
    row.appendChild(el("td", "num", link.cost));
    row.appendChild(el("td", link.up ? "state-up" : "state-down", link.up ? "Up" : "Down"));
    const cell = el("td", "num");
    const action = link.up ? "fail" : "restore";
    const button = el("button", "btn btn-small", link.up ? "Fail link" : "Restore link");
    button.type = "button";
    button.addEventListener("click", async () => {
      const done = await runAction(
        button,
        () => api(`/api/links/${action}`, { a: link.a, b: link.b }),
        `Link ${link.a}-${link.b} ${link.up ? "failed" : "restored"}. Routes recomputed.`,
      );
      if (done) refreshTab();
    });
    cell.appendChild(button);
    row.appendChild(cell);
    body.appendChild(row);
  }
}

function renderForwardingTables(topology) {
  const table = $("fwd-table");
  const head = el("tr");
  head.appendChild(el("th", "", "Router"));
  for (const destination of topology.destinations) head.appendChild(el("th", "", destination));
  table.querySelector("thead").replaceChildren(head);
  const body = table.querySelector("tbody");
  body.replaceChildren();
  for (const [router, nextHops] of Object.entries(topology.tables)) {
    const row = el("tr");
    row.appendChild(el("td", "", router));
    for (const destination of topology.destinations) {
      const hop = destination === router ? "self" : nextHops[destination] || "-";
      row.appendChild(el("td", "", hop));
    }
    body.appendChild(row);
  }
}

async function refreshTopology() {
  const topology = await api("/api/topology");
  drawTopology(topology);
  renderLinkTable(topology.links);
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
}

// ---------- controls ----------

function initControls() {
  const slider = $("noise-slider");
  slider.addEventListener("input", () => {
    $("noise-value").textContent = `${slider.value}%`;
  });
  $("noise-apply").addEventListener("click", (event) => {
    const rate = Number(slider.value) / 100;
    runAction(event.currentTarget, () => api("/api/noise", { error_rate: rate }), `Noise set to ${slider.value}% per link`);
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

  $("flood-btn").addEventListener("click", (event) =>
    runAction(
      event.currentTarget,
      () => api("/api/flood", { sensor: $("flood-sensor").value, spoof: false }),
      (data) => `Flooding ${data.frames} frames from ${data.sensor}`,
    ),
  );
  $("spoof-btn").addEventListener("click", (event) =>
    runAction(
      event.currentTarget,
      () => api("/api/flood", { sensor: $("flood-sensor").value, spoof: true }),
      (data) => `Sent ${data.frames} frames from an unknown IP via ${data.sensor}`,
    ),
  );
}

// ---------- packet inspector ----------

function renderEventList(events) {
  const list = $("event-list");
  $("event-empty").hidden = events.length > 0;
  list.replaceChildren();
  for (const event of events) {
    const item = el("li");
    const button = el("button", "event-row");
    button.type = "button";
    button.dataset.id = event.id;
    if (event.id === view.selectedEvent) button.classList.add("is-active");
    const left = el("span");
    left.appendChild(el("span", "event-type", event.type.replace(/_/g, " ")));
    left.appendChild(el("span", "event-meta", ` ${event.sensor}`));
    button.appendChild(left);
    button.appendChild(el("span", "event-meta", `${event.protocol.toUpperCase()} ${formatTime(event.received_at)}`));
    button.addEventListener("click", () => selectEvent(event.id));
    item.appendChild(button);
    list.appendChild(item);
  }
}

function keyValues(pairs) {
  const list = el("dl", "kv");
  for (const [key, value] of pairs) {
    list.appendChild(el("dt", "", key));
    list.appendChild(el("dd", "", value));
  }
  return list;
}

function layerCard(title, concept, children) {
  const card = el("article", "card");
  const heading = el("h2", "layer-title", title);
  heading.appendChild(el("span", "layer-concept", concept));
  card.appendChild(heading);
  for (const child of children) card.appendChild(child);
  return card;
}

function codeBlock(label, text) {
  const wrapper = el("div");
  wrapper.appendChild(el("p", "code-label", label));
  wrapper.appendChild(el("pre", "code", text));
  return wrapper;
}

function renderLayers(layers) {
  const { application, transport, network, datalink } = layers;
  const frameTypes = ["normal", "high", "critical"];
  $("layers").replaceChildren(
    layerCard("Application", "Event JSON from the sensor", [el("pre", "code", application.json)]),
    layerCard("Transport", transport.note, [
      keyValues([
        ["Protocol", transport.protocol],
        ["Source port", transport.src_port],
        ["Destination port", transport.dst_port],
      ]),
    ]),
    layerCard("Network", "Routed hop by hop with Dijkstra", [
      keyValues([
        ["Source IP", network.src_ip],
        ["Destination IP", network.dst_ip],
        ["TTL on arrival", `${network.ttl} (${network.hops} router hop${network.hops === 1 ? "" : "s"})`],
        ["Path taken", network.path.join(" > ") || "unknown"],
        ["Priority", `${network.priority} (${frameTypes[network.priority]})`],
      ]),
    ]),
    layerCard("Data link", `${datalink.method === "bit" ? "Bit" : "Character"} stuffing, ${datalink.crc_type}`, [
      keyValues([
        ["Header", datalink.header_text],
        ["Frame type, seq", `${datalink.frame_type}, ${datalink.seq_no}`],
        ["CRC (hex)", datalink.crc_hex],
        ["CRC (binary)", datalink.crc_bits],
        ["Size", `${datalink.body_bytes} bytes before stuffing, ${datalink.wire_bytes} on the wire`],
      ]),
      codeBlock("Stuffed frame with flags (hex)", datalink.wire_hex),
      codeBlock("Stuffed frame with flags (binary)", datalink.wire_binary),
    ]),
  );
}

async function selectEvent(eventId) {
  view.selectedEvent = eventId;
  for (const row of document.querySelectorAll(".event-row")) {
    row.classList.toggle("is-active", row.dataset.id === eventId);
  }
  try {
    renderLayers(await api(`/api/events/${encodeURIComponent(eventId)}`));
  } catch (error) {
    toast(error.message, true);
  }
}

async function refreshEvents() {
  // Hold the list still while the pointer is on it, so rows don't move under a click.
  if (view.pointerOnEvents) return;
  renderEventList(await api("/api/events"));
}

function initInspector() {
  const list = $("event-list");
  list.addEventListener("mouseenter", () => { view.pointerOnEvents = true; });
  list.addEventListener("mouseleave", () => { view.pointerOnEvents = false; });
}

// ---------- reports, emails, diagnostics ----------

function formatBytes(size) {
  return size < 1024 ? `${size} B` : `${(size / 1024).toFixed(1)} KB`;
}

async function refreshReports() {
  const files = await api("/api/reports");
  $("ftp-empty").hidden = files.length > 0;
  const body = $("ftp-table").querySelector("tbody");
  body.replaceChildren();
  for (const file of files) {
    const row = el("tr");
    row.appendChild(el("td", "mono", file.name));
    row.appendChild(el("td", "num", formatBytes(file.size)));
    row.appendChild(el("td", "", file.modified));
    body.appendChild(row);
  }
}

function showMail(mail) {
  view.selectedMail = mail.id;
  $("mail-subject").textContent = mail.subject;
  $("mail-meta").textContent = `From ${mail.sender} to ${mail.recipient}, ${formatTime(mail.received_at)}`;
  $("mail-body").textContent = mail.body;
}

async function refreshInbox() {
  const mails = await api("/api/emails");
  $("inbox-empty").hidden = mails.length > 0;
  const inbox = $("inbox");
  inbox.replaceChildren();
  for (const mail of mails) {
    const item = el("li");
    const button = el("button", "mail-row");
    button.type = "button";
    if (mail.id === view.selectedMail) button.classList.add("is-active");
    button.appendChild(el("span", "mail-subject", mail.subject));
    button.appendChild(el("span", "mail-from", `${mail.sender}, ${formatTime(mail.received_at)}`));
    button.addEventListener("click", () => {
      showMail(mail);
      refreshInbox();
    });
    item.appendChild(button);
    inbox.appendChild(item);
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
  const buttons = $("diag-buttons");
  buttons.replaceChildren();
  for (const command of options.commands) {
    const button = el("button", "btn", command.label);
    button.type = "button";
    button.addEventListener("click", async () => {
      $("terminal-title").textContent = command.label;
      $("terminal").textContent = "Running ...";
      const result = await runAction(
        button,
        () => api("/api/diagnostics", { command: command.id, target: target.value }),
        `${command.label} finished`,
      );
      if (result) $("terminal").textContent = `$ ${result.command}\n\n${result.output}`;
      else $("terminal").textContent = "The command could not run. See the message in the corner.";
    });
    buttons.appendChild(button);
  }
  view.diagnosticsLoaded = true;
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
    // The status pill already shows when the server is unreachable.
  }
}

async function poll() {
  await refreshStatus();
  await refreshTab();
  setTimeout(poll, POLL_MS);
}

initTheme();
initTabs();
initTopology();
initControls();
initInspector();
initReports();
window.addEventListener("resize", () => view.status && drawQosChart(view.status.qos.timeline));
poll();

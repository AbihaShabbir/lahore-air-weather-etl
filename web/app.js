/* Dashboard code. No libraries: charts are drawn as SVG by the small
   helper functions below (lineChart, barChart, scatterChart).
   The numbers come from data.js, which export_web_data.py creates from the database. */
"use strict";

const D = window.DATA;
const C = { ink: "#1f2937", muted: "#6b7280", grid: "#e5e7eb", accent: "#2563eb", warn: "#c2410c" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const NS = "http://www.w3.org/2000/svg";
const $ = (sel) => document.querySelector(sel);

/* ---------- small helpers ---------- */
function el(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs || {}) e.setAttribute(k, attrs[k]);
  if (text !== undefined) e.textContent = text;
  return e;
}
function html(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}
const fmt = (v) => (Number.isInteger(v) ? String(v) : v.toFixed(1));
const monthName = (ym, long) => {            // "2026-01" -> "Jan 2026" / "Jan 26"
  const [y, m] = ym.split("-");
  return MONTHS[+m - 1] + " " + (long ? y : y.slice(2));
};
function niceStep(raw) {                      // 7.3 -> 10, 1.8 -> 2 ... (pretty axis steps)
  const p = Math.pow(10, Math.floor(Math.log10(raw)));
  const f = raw / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p;
}

/* ---------- tooltip ---------- */
const tip = $("#tip");
function showTip(text, ev) {
  tip.textContent = text;
  tip.hidden = false;
  const w = tip.offsetWidth;
  tip.style.left = Math.max(8, Math.min(ev.clientX + 14, window.innerWidth - w - 8)) + "px";
  tip.style.top = Math.max(8, ev.clientY - 44) + "px";
}
const hideTip = () => { tip.hidden = true; };

/* ---------- chart frame + y axis ---------- */
function frame(box, label, height) {
  box.innerHTML = "";
  const w = Math.max(box.clientWidth, 280), h = height || 300;
  const m = { t: 10, r: 14, b: 34, l: 52 };
  const svg = el("svg", { width: w, height: h, viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": label });
  box.appendChild(svg);
  const g = el("g", { transform: `translate(${m.l},${m.t})` });
  svg.appendChild(g);
  return { svg, g, m, iw: w - m.l - m.r, ih: h - m.t - m.b };
}

function yAxis(f, yMax, title) {
  const step = niceStep(yMax / 5);
  const top = Math.ceil(yMax / step) * step;
  const Y = (v) => f.ih - (v / top) * f.ih;
  for (let v = 0; v <= top + 1e-9; v += step) {
    f.g.appendChild(el("line", { x1: 0, x2: f.iw, y1: Y(v), y2: Y(v), stroke: v === 0 ? C.muted : C.grid }));
    f.g.appendChild(el("text", { x: -8, y: Y(v) + 4, "text-anchor": "end", fill: C.muted, "font-size": 11 }, fmt(+v.toFixed(6))));
  }
  if (title) {
    f.g.appendChild(el("text", {
      transform: `translate(${-f.m.l + 12},${f.ih / 2}) rotate(-90)`,
      "text-anchor": "middle", fill: C.muted, "font-size": 11,
    }, title));
  }
  return Y;
}

function xTickLabels(f, ticks, X) {               // ticks = [{x, text}]
  const need = 46;                                  // px per label, so they never overlap
  const keep = Math.max(1, Math.ceil((ticks.length * need) / f.iw));
  ticks.forEach((t, i) => {
    if (i % keep) return;
    f.g.appendChild(el("text", { x: X(t.x), y: f.ih + 20, "text-anchor": "middle", fill: C.muted, "font-size": 11 }, t.text));
  });
}

function refLine(f, Y, value) {                     // dashed WHO line
  f.g.appendChild(el("line", { x1: 0, x2: f.iw, y1: Y(value), y2: Y(value), stroke: C.warn, "stroke-width": 1.5, "stroke-dasharray": "6 4" }));
}

/* ---------- line chart (with hover) ---------- */
function lineChart(box, pts, o) {
  // pts: [{x: number, y: number, tip: string}], sorted by x
  const f = frame(box, o.label, o.height);
  const xlo = pts[0].x, xhi = pts[pts.length - 1].x;
  const X = (v) => ((v - xlo) / (xhi - xlo || 1)) * f.iw;
  const Y = yAxis(f, Math.max(...pts.map((p) => p.y), o.ref || 0) * 1.05, o.yTitle);
  xTickLabels(f, o.xTicks, X);
  if (o.ref) refLine(f, Y, o.ref);

  const d = pts.map((p, i) => (i ? "L" : "M") + X(p.x).toFixed(1) + "," + Y(p.y).toFixed(1)).join("");
  f.g.appendChild(el("path", { d, fill: "none", stroke: C.accent, "stroke-width": 2, "stroke-linejoin": "round" }));
  if (o.dots) pts.forEach((p) => f.g.appendChild(el("circle", { cx: X(p.x), cy: Y(p.y), r: 3.5, fill: C.accent, stroke: "#fff", "stroke-width": 1.5 })));

  // hover layer: a vertical guide + a dot on the nearest point
  const guide = el("line", { y1: 0, y2: f.ih, stroke: C.muted, "stroke-dasharray": "3 3", visibility: "hidden" });
  const dot = el("circle", { r: 5, fill: C.accent, stroke: "#fff", "stroke-width": 2, visibility: "hidden" });
  const hit = el("rect", { x: 0, y: 0, width: f.iw, height: f.ih, fill: "transparent" });
  f.g.append(guide, dot, hit);
  hit.addEventListener("pointermove", (ev) => {
    const r = hit.getBoundingClientRect();
    const target = xlo + Math.min(1, Math.max(0, (ev.clientX - r.left) / r.width)) * (xhi - xlo);
    let best = pts[0];
    for (const p of pts) if (Math.abs(p.x - target) < Math.abs(best.x - target)) best = p;
    guide.setAttribute("x1", X(best.x)); guide.setAttribute("x2", X(best.x));
    dot.setAttribute("cx", X(best.x)); dot.setAttribute("cy", Y(best.y));
    guide.setAttribute("visibility", "visible"); dot.setAttribute("visibility", "visible");
    showTip(best.tip, ev);
  });
  hit.addEventListener("pointerleave", () => {
    guide.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); hideTip();
  });
}

/* ---------- bar chart (with hover) ---------- */
function barChart(box, items, o) {
  // items: [{label, value, tip, text}]
  const f = frame(box, o.label, o.height);
  const Y = yAxis(f, Math.max(...items.map((i) => i.value), o.ref || 0, 1) * 1.08, o.yTitle);
  const band = f.iw / items.length;
  const bw = Math.min(band * 0.7, 46);
  const keep = Math.max(1, Math.ceil(46 / band));      // show every 2nd/3rd label when bars are narrow
  items.forEach((it, i) => {
    const x = i * band + (band - bw) / 2, y = Y(it.value), h = f.ih - y, r = Math.min(4, bw / 2, h);
    // top corners rounded, bottom sits flat on the axis
    const bar = el("path", {
      d: `M${x},${f.ih} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${f.ih} Z`,
      fill: C.accent,
    });
    bar.addEventListener("pointermove", (ev) => { bar.setAttribute("opacity", 0.75); showTip(it.tip, ev); });
    bar.addEventListener("pointerleave", () => { bar.removeAttribute("opacity"); hideTip(); });
    f.g.appendChild(bar);
    if (band >= 30) f.g.appendChild(el("text", { x: x + bw / 2, y: y - 5, "text-anchor": "middle", fill: C.muted, "font-size": 11 }, it.text));
    if (i % keep === 0) f.g.appendChild(el("text", { x: x + bw / 2, y: f.ih + 20, "text-anchor": "middle", fill: C.muted, "font-size": 11 }, it.label));
  });
  if (o.ref) refLine(f, Y, o.ref);
}

/* ---------- scatter chart + median line ---------- */
function scatterChart(box, pts, o) {
  const f = frame(box, o.label, o.height);
  const xs = pts.map((p) => p[0]);
  const xlo = Math.min(...xs), xhi = Math.max(...xs);
  const X = (v) => ((v - xlo) / (xhi - xlo || 1)) * f.iw;
  const Y = yAxis(f, Math.max(...pts.map((p) => p[1])) * 1.05, "PM2.5 (µg/m³)");

  const step = niceStep((xhi - xlo) / 6);
  const ticks = [];
  for (let v = Math.ceil(xlo / step) * step; v <= xhi; v += step) ticks.push({ x: v, text: fmt(+v.toFixed(6)) });
  xTickLabels(f, ticks, X);
  f.g.appendChild(el("text", { x: f.iw / 2, y: f.ih + 32, "text-anchor": "middle", fill: C.ink, "font-size": 12 }, o.xTitle));

  pts.forEach((p) => f.g.appendChild(el("circle", { cx: X(p[0]), cy: Y(p[1]), r: 2.4, fill: C.accent, opacity: 0.16 })));

  // median PM2.5 inside 15 equal slices of the x variable
  const n = 15, bins = Array.from({ length: n }, () => []);
  pts.forEach((p) => bins[Math.min(n - 1, Math.floor(((p[0] - xlo) / (xhi - xlo || 1)) * n))].push(p));
  const line = bins.filter((b) => b.length >= 5).map((b) => {
    const ys = b.map((p) => p[1]).sort((a, c) => a - c);
    const mx = b.reduce((s, p) => s + p[0], 0) / b.length;
    return [mx, ys[Math.floor(ys.length / 2)]];
  });
  const d = line.map((p, i) => (i ? "L" : "M") + X(p[0]).toFixed(1) + "," + Y(p[1]).toFixed(1)).join("");
  f.g.appendChild(el("path", { d, fill: "none", stroke: C.ink, "stroke-width": 2.5, "stroke-linejoin": "round" }));
}

/* ---------- correlation table ---------- */
const mix = (a, b, t) => a.map((v, i) => Math.round(v + (b[i] - v) * t));
function corrColor(v) {                              // blue (-1) - grey (0) - orange (+1)
  const grey = [243, 244, 246], blue = [37, 99, 235], orange = [194, 65, 12];
  return "rgb(" + mix(grey, v < 0 ? blue : orange, Math.abs(v)).join(",") + ")";
}
const NICE = { pm2_5: "PM2.5", pm10: "PM10", temperature_2m: "Temperature", relative_humidity_2m: "Humidity",
               wind_speed_10m: "Wind speed", surface_pressure: "Pressure", precipitation: "Rain" };

function renderCorrTable() {
  const t = $("#t-corr");
  t.innerHTML = "";
  const head = html("tr");
  head.appendChild(html("th"));
  D.corr.cols.forEach((c) => head.appendChild(html("th", "", NICE[c])));
  t.appendChild(head);
  D.corr.matrix.forEach((row, i) => {
    const tr = html("tr");
    tr.appendChild(html("th", "row", NICE[D.corr.cols[i]]));
    row.forEach((v) => {
      const td = html("td", "", v.toFixed(2));
      td.style.background = corrColor(v);
      td.style.color = Math.abs(v) > 0.6 ? "#fff" : C.ink;
      tr.appendChild(td);
    });
    t.appendChild(tr);
  });
}

/* ---------- page sections ---------- */
function renderKpis() {
  const k = D.kpis;
  const cards = [
    ["Average PM2.5", k.mean, "µg/m³", `Median ${k.median}. WHO daily guideline: ${D.meta.who_pm25}`],
    ["Highest hour", k.max, "µg/m³", k.max_time],
    ["Days above WHO limit", `${k.days_over_who}`, `of ${k.days_measured}`, `${Math.round((k.days_over_who / k.days_measured) * 100)}% of measured days`],
    ["Worst month", monthName(k.worst_month.month, true), "", `Average PM2.5 ${k.worst_month.mean} µg/m³`],
  ];
  if (k.winter_mean !== null && k.other_mean !== null) {
    cards.push(["Winter vs other months", `${k.winter_mean} vs ${k.other_mean}`, "µg/m³", "Nov-Feb compared with the rest"]);
  }
  const box = $("#kpis");
  cards.forEach(([label, value, unit, hint]) => {
    const c = html("div", "kpi");
    c.appendChild(html("div", "label", label));
    const v = html("div", "value", String(value));
    if (unit) v.appendChild(html("small", "", " " + unit));
    c.appendChild(v);
    c.appendChild(html("div", "hint", hint));
    box.appendChild(c);
  });
}

function renderCharts() {
  const W = D.meta.who_pm25;
  // daily line: x = number of days since the first day
  const t0 = Date.UTC(...D.daily[0].d.split("-").map((v, i) => (i === 1 ? +v - 1 : +v)));
  const dayNo = (s) => { const [y, m, d] = s.split("-").map(Number); return (Date.UTC(y, m - 1, d) - t0) / 864e5; };
  const dailyPts = D.daily.map((r) => ({
    x: dayNo(r.d), y: r.pm25,
    tip: `${r.d}\nPM2.5: ${r.pm25} µg/m³\nPM10: ${r.pm10} µg/m³`,
  }));
  const monthTicks = D.daily.filter((r) => r.d.endsWith("-01")).map((r) => ({ x: dayNo(r.d), text: monthName(r.d.slice(0, 7)) }));
  lineChart($("#c-daily"), dailyPts, { label: "Daily average PM2.5 over the year", yTitle: "PM2.5 (µg/m³)", ref: W, xTicks: monthTicks });

  barChart($("#c-monthly"), D.monthly.map((m) => ({
    label: monthName(m.month), value: m.pm25, text: String(Math.round(m.pm25)),
    tip: `${monthName(m.month, true)}\nAverage PM2.5: ${m.pm25} µg/m³`,
  })), { label: "Average PM2.5 by month", yTitle: "PM2.5 (µg/m³)", ref: W, height: 280 });

  lineChart($("#c-hourly"), D.hourly.map((h) => ({
    x: h.hour, y: h.pm25, tip: `${String(h.hour).padStart(2, "0")}:00\nAverage PM2.5: ${h.pm25} µg/m³`,
  })), { label: "Average PM2.5 by hour of day", yTitle: "PM2.5 (µg/m³)", dots: true, height: 280,
         xTicks: D.hourly.filter((h) => h.hour % 3 === 0).map((h) => ({ x: h.hour, text: String(h.hour).padStart(2, "0") + ":00" })) });

  barChart($("#c-who"), D.monthly.map((m) => ({
    label: monthName(m.month), value: m.days_over, text: `${m.days_over}/${m.days}`,
    tip: `${monthName(m.month, true)}\n${m.days_over} of ${m.days} days above the WHO limit`,
  })), { label: "Days above the WHO PM2.5 guideline, by month", yTitle: "Days", height: 280 });

  renderScatter();
}

function renderScatter() {
  const sel = $("#wx");
  const col = sel.value;
  const label = sel.options[sel.selectedIndex].text;
  const r = D.corr.matrix[0][D.corr.cols.indexOf(col)];
  $("#wx-corr").textContent = `Correlation with PM2.5: ${r > 0 ? "+" : ""}${r.toFixed(2)}`;
  scatterChart($("#c-scatter"), D.scatter[col], { label: `PM2.5 against ${label}`, xTitle: label, height: 340 });
}

function renderTables() {
  const t = $("#t-monthly");
  t.innerHTML = "<tr><th>Month</th><th>Avg PM2.5 (µg/m³)</th><th>Days over WHO</th></tr>";
  D.monthly.forEach((m) => {
    const tr = html("tr");
    [monthName(m.month, true), m.pm25, `${m.days_over} / ${m.days}`].forEach((v) => tr.appendChild(html("td", "", String(v))));
    t.appendChild(tr);
  });
  renderCorrTable();
}

function renderText() {
  $("#subtitle").textContent = `${D.meta.location} · ${D.meta.start} to ${D.meta.end} · ${D.meta.hours.toLocaleString()} hourly records`;
  $("#generated").textContent = "Dashboard data generated " + D.meta.generated + ".";
  document.querySelectorAll(".who-val").forEach((e) => { e.textContent = D.meta.who_pm25; });
  const ul = $("#findings");
  D.findings.forEach((f) => ul.appendChild(html("li", "", f)));

  const p = D.pipeline || {};
  const n = (v) => (v === undefined ? "?" : Number(v).toLocaleString());
  const steps = [
    ["Extract", `<code>extract.py</code> calls two free Open-Meteo APIs (air quality and weather) with Python <code>requests</code> and saves the raw JSON unchanged. ${n(p.air_rows_raw)} hourly rows came back.`],
    ["Transform", `<code>transform.py</code> turns the JSON into <code>pandas</code> tables, merges them on time, removes ${n(p.duplicates_removed)} duplicate rows and fills gaps of up to 3 hours. ${n(p.rows_after_merge)} rows after merging.`],
    ["Validate", `<code>schema.py</code> defines a <code>Pydantic</code> model (for example humidity must be 0-100). Every row is checked: ${n(p.rows_valid)} valid, ${n(p.rows_rejected)} rejected.`],
    ["Load", `<code>load.py</code> writes the valid rows into a SQLite database (<code>air_weather</code> table, ${n(p.rows_in_database)} rows) using SQLAlchemy.`],
    ["EDA", `<code>eda.py</code> reads the data back from the database and produces statistics, charts, correlations and the WHO-limit analysis.`],
    ["Website", `<code>export_web_data.py</code> summarises the database into <code>data.js</code>. This page is plain HTML, CSS and JavaScript that draws the charts from it.`],
  ];
  const ol = $("#steps");
  steps.forEach(([title, body]) => {
    const li = html("li");
    li.appendChild(html("h3", "", title));
    const para = html("p");
    para.innerHTML = body;          // the text above is written by us, not user input
    li.appendChild(para);
    ol.appendChild(li);
  });
}

/* ---------- start ---------- */
if (!D) {
  const e = $("#error");
  e.hidden = false;
  e.textContent = "data.js was not found. Run  python run_all.py  (or  python export_web_data.py ) to create it, then reload this page.";
} else {
  renderKpis();
  renderText();
  renderTables();
  renderCharts();
  $("#wx").addEventListener("change", renderScatter);
  let timer;
  window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(renderCharts, 150); });
}

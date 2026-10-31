const NS = "http://www.w3.org/2000/svg";
const PIPELINE = new Set(["Title checked", "Bid set", "Won", "Buyer assigned", "Closed"]);
const BANDS = [["excellent", "Excellent"], ["good", "Good"], ["fair", "Fair"], ["risky", "Risky"], ["thin", "Not enough data"]];
const sky = document.getElementById("sky");
const plates = document.getElementById("plates");
const note = document.getElementById("collect-note");
const narrow = matchMedia("(max-width: 860px)");
let selected = null;
let opener = null;
const scrim = document.querySelector(".scrim");
let scale = 1;

const radius = (score) => (score ? 1.5 + score * 0.8 * scale : 2.5);
const short = (n) => (n >= 1e6 ? `$${+(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `$${Math.round(n / 1e3)}K` : `$${Math.round(n)}`);

function el(name, attrs = {}, text) {
  const node = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}

function stars() {
  return [...plates.querySelectorAll(".plate")].map((plate) => ({
    id: plate.dataset.id,
    name: plate.dataset.name,
    bid: parseFloat(plate.dataset.bid),
    roll: parseFloat(plate.dataset.roll),
    score: parseInt(plate.dataset.score, 10) || 0,
    band: plate.dataset.band || "",
    status: plate.dataset.status,
  }));
}

let place = null;

function draw() {
  const width = sky.clientWidth;
  const height = sky.clientHeight;
  scale = Math.min(1, Math.max(0.55, width / 900));
  const steps = width < 560 ? [1] : [1, 3];
  sky.setAttribute("viewBox", `0 0 ${width} ${height}`);
  sky.replaceChildren();
  const all = stars();
  const plotted = all.filter((s) => s.bid > 0 && s.roll > 0);
  const missing = all.length - plotted.length;
  const bright = plotted.filter((s) => ["excellent", "good", "fair"].includes(s.band) && s.roll > s.bid);
  const view = width < 560 && bright.length >= 5 ? bright : plotted;
  const outside = plotted.length - view.length;
  const notes = [];
  if (outside) notes.push(`Showing the ${view.length} brightest. ${outside} more are on the wider chart.`);
  if (missing) notes.push(`${missing} ${missing === 1 ? "deal is" : "deals are"} off the chart: no bid or no tax roll value yet.`);
  document.getElementById("off-chart").textContent = notes.join(" ");
  if (!plotted.length) {
    sky.append(el("text", { x: 24, y: 40, class: "axis" }, "Nothing to chart until a deal has a bid and a tax roll value."));
    place = null;
    return;
  }
  const m = { l: 52, r: 16, t: 16, b: 40 };
  const lx = view.map((s) => Math.log10(s.bid));
  const ly = view.map((s) => Math.log10(s.roll));
  const x0 = Math.min(...lx) - 0.15, x1 = Math.max(...lx) + 0.15;
  const y0 = Math.min(...ly) - 0.15, y1 = Math.max(...ly) + 0.15;
  const X = (v) => m.l + ((v - x0) / (x1 - x0)) * (width - m.l - m.r);
  const Y = (v) => height - m.b - ((v - y0) / (y1 - y0)) * (height - m.t - m.b);
  place = (s) => [X(Math.log10(s.bid)), Y(Math.log10(s.roll))];

  const defs = el("defs");
  const clip = el("clipPath", { id: "plot" });
  clip.append(el("rect", { x: m.l, y: m.t, width: width - m.l - m.r, height: height - m.t - m.b }));
  const glow = el("radialGradient", { id: "glow" });
  glow.append(el("stop", { offset: "0", "stop-color": "#f2e2c9", "stop-opacity": "0.4" }));
  glow.append(el("stop", { offset: "1", "stop-color": "#f2e2c9", "stop-opacity": "0" }));
  defs.append(clip, glow);
  sky.append(defs);

  for (let k = Math.floor(x0); k <= Math.ceil(x1); k++) {
    for (const step of steps) {
      const v = k + Math.log10(step);
      if (v < x0 || v > x1) continue;
      sky.append(el("line", { x1: X(v), x2: X(v), y1: m.t, y2: height - m.b, class: "grid" }));
      sky.append(el("text", { x: X(v), y: height - m.b + 18, "text-anchor": "middle", class: "tick" }, short(10 ** v)));
    }
  }
  for (let k = Math.floor(y0); k <= Math.ceil(y1); k++) {
    for (const step of steps) {
      const v = k + Math.log10(step);
      if (v < y0 || v > y1) continue;
      sky.append(el("line", { x1: m.l, x2: width - m.r, y1: Y(v), y2: Y(v), class: "grid" }));
      sky.append(el("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end", class: "tick" }, short(10 ** v)));
    }
  }
  sky.append(el("text", { x: width - m.r, y: height - 4, "text-anchor": "end", class: "axis" }, "Bid"));
  sky.append(el("text", { x: m.l + 6, y: m.t + 14, class: "axis" }, "Tax roll value"));

  const lines = el("g", { "clip-path": "url(#plot)" });
  for (const [times, label] of [[1, "worth what it costs"], [2, "worth twice the bid"]]) {
    const lift = Math.log10(times);
    const a = Math.max(x0, y0 - lift), b = Math.min(x1, y1 - lift);
    if (a >= b) continue;
    lines.append(el("line", { x1: X(a), y1: Y(a + lift), x2: X(b), y2: Y(b + lift), class: "line" }));
    if (width < 560) {
      lines.append(el("text", { x: X(b) - 4, y: Y(b + lift) + 16, "text-anchor": "end", class: "line-label" }, `${times}×`));
      continue;
    }
    const angle = (Math.atan2(Y(b + lift) - Y(a + lift), X(b) - X(a)) * 180) / Math.PI;
    const at = a + (b - a) * 0.3;
    const tx = X(at), ty = Y(at + lift);
    lines.append(el("text", { x: tx, y: ty, "text-anchor": "middle", transform: `rotate(${angle} ${tx} ${ty}) translate(0 ${times === 1 ? 16 : -7})`, class: "line-label" }, label));
  }
  sky.append(lines);

  const legend = el("g", { class: "legend" });
  const present = new Set(plotted.map((s) => s.band));
  let ly0 = height - m.b - 10;
  for (const [band, label] of [...BANDS].reverse()) {
    if (!present.has(band)) continue;
    legend.append(el("circle", { cx: width - m.r - 12, cy: ly0 - 4, r: 4.5, class: `legend-dot band-${band}` }));
    legend.append(el("text", { x: width - m.r - 22, y: ly0, "text-anchor": "end" }, label));
    ly0 -= 17;
  }
  sky.append(legend);

  const field = el("g", { "clip-path": "url(#plot)" });
  for (const s of [...plotted].sort((a, b) => a.score - b.score)) {
    const [cx, cy] = place(s);
    const r = radius(s.score);
    const hit = el("g", { class: "hit", "data-id": s.id });
    const label = (BANDS.find(([band]) => band === s.band) || [, "Unscored"])[1];
    hit.append(el("title", {}, `${s.name} · ${label} · score ${s.score || "—"} · bid ${short(s.bid)} · roll ${short(s.roll)}`));
    if (PIPELINE.has(s.status)) hit.append(el("circle", { cx, cy, r: r + 4, class: "ring" }));
    hit.append(el("circle", { cx, cy, r: Math.max(r * 2.6, 8), fill: s.score && s.band !== "thin" ? "url(#glow)" : "transparent" }));
    hit.append(el("circle", { cx, cy, r, class: `star${s.score ? ` band-${s.band}` : " unscored"}${s.status === "Passed" ? " pass" : ""}` }));
    field.append(hit);
  }
  sky.append(field);

  const discs = plotted.map((s) => {
    const [cx, cy] = place(s);
    const r = radius(s.score);
    return { id: s.id, x: cx - r, y: cy - r, w: 2 * r, h: 2 * r };
  });
  const hits = (box, list) => list.some((t) => box.x < t.x + t.w && t.x < box.x + box.w && box.y < t.y + t.h && t.y < box.y + box.h);
  const taken = [{ x: m.l, y: m.t, w: 110, h: 20 }];
  const limit = width < 560 ? 2 : 5;
  const ranked = view.filter((s) => ["excellent", "good"].includes(s.band)).sort((a, b) => b.score - a.score || b.roll / b.bid - a.roll / a.bid);
  for (const s of ranked) {
    if (taken.length > limit) break;
    const [cx, cy] = place(s);
    const r = radius(s.score);
    const w = s.name.length * 7 + 4;
    for (const left of [false, true]) {
      const bx = left ? cx - r - 6 - w : cx + r + 6;
      const box = { x: bx, y: cy - 12, w, h: 18 };
      const clear = bx > m.l && bx + w < width - m.r && !hits(box, taken) && !hits(box, discs.filter((d) => d.id !== s.id));
      if (!clear) continue;
      taken.push(box);
      sky.append(el("text", { x: bx, y: cy + 5, class: "name" }, s.name));
      break;
    }
  }
  sky.append(el("g", { id: "reticle", "clip-path": "url(#plot)" }));
  if (selected) mark(selected);
}

function mark(id) {
  const holder = document.getElementById("reticle");
  if (!holder || !place) return;
  holder.replaceChildren();
  const s = stars().find((item) => item.id === id);
  if (!s || !(s.bid > 0 && s.roll > 0)) return;
  const [cx, cy] = place(s);
  const r = radius(s.score) + 7;
  const g = el("g", { class: "reticle reticle-in" });
  g.append(el("circle", { cx, cy, r }));
  for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
    g.append(el("line", { x1: cx + dx * r, y1: cy + dy * r, x2: cx + dx * (r + 7), y2: cy + dy * (r + 7) }));
  }
  holder.append(g);
}

function select(id, { open = true } = {}) {
  const plate = document.getElementById(`d${id}`);
  if (!plate) return;
  selected = id;
  for (const node of plates.querySelectorAll(".plate.on")) node.classList.remove("on");
  plate.classList.add("on");
  for (const row of document.querySelectorAll(".index tr[data-id]")) {
    row.toggleAttribute("aria-current", false);
    if (row.dataset.id === id) row.setAttribute("aria-current", "true");
  }
  history.replaceState(null, "", `${location.pathname}${location.search}#deal-${id}`);
  mark(id);
  if (narrow.matches && open) {
    plates.scrollTop = 0;
    plates.classList.add("open");
    scrim.hidden = false;
    plate.querySelector(".star-name").focus({ preventScroll: true });
  } else if (!narrow.matches) {
    plates.closest(".side").scrollTop = 0;
  }
}

document.addEventListener("click", (event) => {
  const target = event.target.closest(".index tr[data-id], .pipeline a[data-id], #sky .hit");
  if (target) {
    event.preventDefault();
    opener = target.matches("tr") ? target.querySelector("a") : target.matches("a") ? target : null;
    select(target.dataset.id);
    return;
  }
  if (event.target.closest("[data-close]")) closeSheet();
});

function closeSheet() {
  if (!plates.classList.contains("open")) return;
  plates.classList.remove("open");
  scrim.hidden = true;
  if (opener) opener.focus();
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !document.querySelector(".help-pop:popover-open")) closeSheet();
});

new ResizeObserver(draw).observe(sky);

const fromHash = (location.hash.match(/^#(?:deal-|d)(\d+)$/) || [])[1] || "";
const first = document.querySelector(".index tr[data-id]") || plates.querySelector(".plate");
const start = document.getElementById(`d${fromHash}`) ? fromHash : first && first.dataset.id;
if (start) select(start, { open: Boolean(fromHash) });

const latestApp = parseInt(document.documentElement.dataset.appVersion, 10) || 0;
const inApp = /; wv[)]/.test(navigator.userAgent);
const appVersion = parseInt((navigator.userAgent.match(/HestiaApp\/(\d+)/) || [])[1], 10) || 0;
if (inApp && latestApp > appVersion) {
  const banner = document.getElementById("app-update");
  if (!appVersion) {
    banner.textContent = "A new version of the Hestia app is ready. This copy cannot update itself: open hestia.trading/static/hestia.apk in Chrome once to install it.";
  }
  banner.hidden = false;
}

const saved = sessionStorage.getItem("hestia-note");
if (saved) {
  note.textContent = saved;
  sessionStorage.removeItem("hestia-note");
}

async function post(path) {
  const response = await fetch(path, { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "" });
  return response.json();
}

function finish(message) {
  sessionStorage.setItem("hestia-note", message);
  location.reload();
}

document.getElementById("score").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  note.textContent = "Checking the tax rolls, code cases, the flood map, and nearby sales…";
  let last = "";
  try {
    let left = 1;
    while (left > 0) {
      const result = await post("/api/score");
      note.textContent = last = result.note;
      left = result.scored ? result.left : 0;
    }
    finish(last);
  } catch (error) {
    note.textContent = "Scoring stopped before it finished. Press Score unchecked again to pick up where it left off.";
    button.disabled = false;
  }
});

document.getElementById("collect").addEventListener("click", async (event) => {
  const button = event.currentTarget;
  button.disabled = true;
  note.textContent = "Collecting Broward, Miami-Dade, and Lee. This takes about a minute…";
  try {
    const result = await post("/api/collect");
    finish(`Added ${result.added}, updated ${result.updated}. ${result.notes.join(" ")}`);
  } catch (error) {
    note.textContent = "The collect request did not finish. Check the connection and press Collect again.";
    button.disabled = false;
  }
});

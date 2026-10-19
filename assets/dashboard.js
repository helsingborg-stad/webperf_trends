const scoreNames = { rating: "Totalt", rating_perf: "Prestanda", rating_a11y: "Tillgänglighet", rating_sec: "Integritet & säkerhet", rating_stand: "Webbstandard" };
const colors = { rating:"#17221e", rating_perf:"#bc4b15", rating_a11y:"#285ea8", rating_sec:"#7b3f88", rating_stand:"#007f78" };
const metricNames = { "mobile:TTFB":"TTFB", "mobile:FCP":"FCP", "mobile:LCP":"LCP", "mobile:SpeedIndex":"Speed Index", "mobile:Load":"Laddtid", "mobile:TBT":"TBT", "mobile:CLS":"CLS" };
const metricColors = { "mobile:TTFB":"#126f8b", "mobile:FCP":"#b24b16", "mobile:LCP":"#7653a6", "mobile:SpeedIndex":"#007b63", "mobile:Load":"#9d304d", "mobile:TBT":"#6e5b16", "mobile:CLS":"#303f9f" };
const formatScore = value => typeof value === "number" ? `${value.toFixed(2)} / 5` : "–";
const escapeHtml = value => String(value).replace(/[&<>"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[character]);

function chart(target, series, options = {}) {
  const available = series.filter(item => item.values.some(value => typeof value === "number"));
  if (!available.length) { target.innerHTML = '<p class="empty-chart">Det behövs minst en körning med detta värde för att rita en trend.</p>'; return; }
  const count = Math.max(...available.map(item => item.values.length)); const width = Math.max(560, count * 90); const height = 280; const pad = { top:18, right:18, bottom:42, left:42 };
  const all = available.flatMap(item => item.values).filter(value => typeof value === "number"); const min = options.min ?? Math.min(...all); const max = options.max ?? Math.max(...all); const range = Math.max(max - min, options.minRange ?? .1);
  const x = index => pad.left + index * ((width - pad.left - pad.right) / Math.max(count - 1, 1)); const y = value => height - pad.bottom - ((value - min) / range) * (height - pad.top - pad.bottom);
  let svg = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">`;
  for (let index = 0; index < 5; index++) { const value = min + range * index / 4; const yy = y(value); svg += `<line class="grid" x1="${pad.left}" x2="${width-pad.right}" y1="${yy}" y2="${yy}"/><text x="4" y="${yy+4}">${options.label ? options.label(value) : value.toFixed(1)}</text>`; }
  svg += `<line class="axis" x1="${pad.left}" x2="${width-pad.right}" y1="${height-pad.bottom}" y2="${height-pad.bottom}"/>`;
  available.forEach(item => { const points = item.values.map((value,index) => typeof value === "number" ? `${x(index)},${y(value)}` : null).filter(Boolean).join(" "); svg += `<polyline class="line" stroke="${item.color}" points="${points}"/>`; item.values.forEach((value,index) => { if (typeof value === "number") svg += `<circle class="dot" fill="${item.color}" cx="${x(index)}" cy="${y(value)}" r="4"><title>${escapeHtml(item.name)}: ${options.label ? options.label(value) : value.toFixed(2)}</title></circle>`; }); });
  svg += "</svg>"; target.innerHTML = svg;
}

function metricOverview(target, legend, runs) {
  const keys = Object.keys(metricNames).filter(key => runs.some(run => typeof run.metrics?.[key] === "number"));
  if (!keys.length) { target.innerHTML = '<p class="empty-chart">Det behövs minst en körning med prestandamått för att rita en översikt.</p>'; legend.innerHTML = ""; return; }
  const primaryKeys = keys.filter(key => key !== "mobile:CLS"); const clsKey = keys.includes("mobile:CLS") ? "mobile:CLS" : null;
  const valuesFor = selectedKeys => selectedKeys.flatMap(key => runs.map(run => run.metrics?.[key])).filter(value => typeof value === "number");
  const primaryValues = valuesFor(primaryKeys); const clsValues = clsKey ? valuesFor([clsKey]) : [];
  const primaryMax = Math.max(...primaryValues, 1); const clsMax = Math.max(...clsValues, .01); const width = Math.max(620, runs.length * 105); const height = 320; const pad = { top:20, right:58, bottom:54, left:58 };
  const x = index => pad.left + index * ((width - pad.left - pad.right) / Math.max(runs.length - 1, 1));
  const y = (value, max) => height - pad.bottom - (value / max) * (height - pad.top - pad.bottom);
  const lineFor = (key, max) => runs.reduce((path, run, index) => { const value = run.metrics?.[key]; return typeof value === "number" ? `${path}${path && !path.endsWith("M ") ? "L" : "M"}${x(index).toFixed(1)} ${y(value, max).toFixed(1)} ` : `${path}M `; }, "").replace(/M\s*$/, "");
  const timeLabel = value => value.includes(", ") ? value.split(", ").at(-1) : value;
  let svg = `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">`;
  for (let index = 0; index < 5; index++) { const ratio = index / 4; const yy = y(primaryMax * ratio, primaryMax); svg += `<line class="grid" x1="${pad.left}" x2="${width-pad.right}" y1="${yy}" y2="${yy}"/><text x="4" y="${yy+4}">${Math.round(primaryMax * ratio)} ms</text>`; if (clsKey) svg += `<text x="${width-pad.right+7}" y="${yy+4}">${(clsMax * ratio).toFixed(3)}</text>`; }
  svg += `<line class="axis" x1="${pad.left}" x2="${width-pad.right}" y1="${height-pad.bottom}" y2="${height-pad.bottom}"/>`;
  runs.forEach((run, index) => { const xx = x(index); svg += `<text class="x-label" x="${xx}" y="${height-16}" text-anchor="middle">${escapeHtml(timeLabel(run.display_date))}</text>`; });
  keys.forEach(key => { const max = key === clsKey ? clsMax : primaryMax; const color = metricColors[key]; svg += `<path class="line" stroke="${color}" d="${lineFor(key, max)}"/>`; runs.forEach((run, index) => { const value = run.metrics?.[key]; if (typeof value === "number") { const display = key === clsKey ? value.toFixed(3) : `${Math.round(value)} ms`; svg += `<circle class="dot" fill="${color}" cx="${x(index)}" cy="${y(value, max)}" r="3.5"><title>${metricNames[key]}: ${display}</title></circle>`; } }); });
  target.innerHTML = `${svg}</svg>`;
  legend.innerHTML = keys.map(key => `<span style="color:${metricColors[key]}">${metricNames[key]}${key === clsKey ? " (CLS, höger axel)" : ""}</span>`).join("");
}

function render(data) {
  const runs = data.runs || []; const latest = runs.at(-1); const status = document.querySelector("#status"); document.querySelector("#site-name").textContent = data.site?.name || "Webperf Core";
  if (!latest) { status.textContent = "Inga mätningar har publicerats ännu. Kör workflowet Webperf trend report i Webperf Core-forken för att skapa den första datapunkten."; return; }
  status.hidden = true; document.querySelector("#last-updated").textContent = `Senaste data: ${latest.display_date}`; const box = document.querySelector("#latest"); box.hidden = false; document.querySelector("#latest-title").textContent = latest.display_date; document.querySelector("#latest-url").textContent = latest.url; document.querySelector("#latest-detail").href = latest.detail;
  const progress = latest.progress || {completed:[], failed:[], total:[], active:""}; const active = progress.active ? ` · test ${progress.active} körs` : ""; const failed = progress.failed.length ? ` · fel i test ${progress.failed.join(", ")}` : ""; document.querySelector("#latest-progress").textContent = `${progress.completed.length} av ${progress.total.length} tester klara${active}${failed}`;
  document.querySelector("#score-cards").innerHTML = Object.entries(scoreNames).map(([key,label]) => `<div><dt>${label}</dt><dd>${formatScore(latest.scores[key])}</dd></div>`).join("");
  chart(document.querySelector("#score-chart"), Object.entries(scoreNames).map(([key,name]) => ({ name, color: colors[key], values:runs.map(run => run.scores[key]) })), { min:1, max:5, minRange:4 });
  metricOverview(document.querySelector("#metrics-overview-chart"), document.querySelector("#metrics-overview-legend"), runs);
  const metricKeys = [...new Set(runs.flatMap(run => Object.keys(run.metrics || {})))].sort(); const metricSelect = document.querySelector("#metric-select");
  if (!metricKeys.length) { metricSelect.disabled = true; metricSelect.innerHTML = "<option>Inga prestandamått ännu</option>"; chart(document.querySelector("#metric-chart"), []); } else { metricSelect.innerHTML = metricKeys.map(key => `<option value="${key}">${key.replace(":", " · ")}</option>`).join(""); const redraw = () => { const key = metricSelect.value; chart(document.querySelector("#metric-chart"), [{ name:key, color:colors.rating_perf, values:runs.map(run => run.metrics[key]) }], { min:0, label:value => key.endsWith(":CLS") ? value.toFixed(3) : `${Math.round(value)} ms` }); }; metricSelect.addEventListener("change", redraw); redraw(); }
  document.querySelector("#history-body").innerHTML = [...runs].reverse().map(run => `<tr><td>${escapeHtml(run.display_date)}</td><td>${formatScore(run.scores.rating)}</td><td>${formatScore(run.scores.rating_perf)}</td><td>${formatScore(run.scores.rating_a11y)}</td><td><a href="${run.detail}">Öppna</a></td></tr>`).join("");
}
fetch("data/summary.json").then(response => { if (!response.ok) throw new Error("Kunde inte läsa summary.json"); return response.json(); }).then(render).catch(() => { document.querySelector("#status").textContent = "Resultaten kunde inte laddas. Försök igen eller kontrollera att den automatiska rapportbyggnaden har lyckats."; });

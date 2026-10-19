const scoreNames = { rating: "Totalt", rating_perf: "Prestanda", rating_a11y: "Tillgänglighet", rating_sec: "Integritet & säkerhet", rating_stand: "Webbstandard" };
const colors = { rating:"#17221e", rating_perf:"#bc4b15", rating_a11y:"#285ea8", rating_sec:"#7b3f88", rating_stand:"#007f78" };
const formatScore = value => typeof value === "number" ? `${value.toFixed(2)} / 5` : "–";
const escapeHtml = value => String(value).replace(/[&<>"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"})[character]);

function chart(target, series, options = {}) {
  const available = series.filter(item => item.values.some(value => typeof value === "number"));
  if (!available.length) { target.innerHTML = '<p class="empty-chart">Det behövs minst en körning med detta värde för att rita en trend.</p>'; return; }
  const count = Math.max(...available.map(item => item.values.length)); const width = Math.max(560, count * 90); const height = 280; const pad = { top:18, right:18, bottom:42, left:42 };
  const all = available.flatMap(item => item.values).filter(value => typeof value === "number"); const min = options.min ?? Math.min(...all); const max = options.max ?? Math.max(...all); const range = Math.max(max - min, options.minRange ?? .1);
  const x = index => pad.left + index * ((width - pad.left - pad.right) / Math.max(count - 1, 1)); const y = value => height - pad.bottom - ((value - min) / range) * (height - pad.top - pad.bottom);
  let svg = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">`;
  for (let index = 0; index < 5; index++) { const value = min + range * index / 4; const yy = y(value); svg += `<line class="grid" x1="${pad.left}" x2="${width-pad.right}" y1="${yy}" y2="${yy}"/><text x="4" y="${yy+4}">${options.label ? options.label(value) : value.toFixed(1)}</text>`; }
  svg += `<line class="axis" x1="${pad.left}" x2="${width-pad.right}" y1="${height-pad.bottom}" y2="${height-pad.bottom}"/>`;
  available.forEach(item => { const points = item.values.map((value,index) => typeof value === "number" ? `${x(index)},${y(value)}` : null).filter(Boolean).join(" "); svg += `<polyline class="line" stroke="${item.color}" points="${points}"/>`; item.values.forEach((value,index) => { if (typeof value === "number") svg += `<circle class="dot" fill="${item.color}" cx="${x(index)}" cy="${y(value)}" r="4"><title>${escapeHtml(item.name)}: ${options.label ? options.label(value) : value.toFixed(2)}</title></circle>`; }); });
  svg += "</svg>"; target.innerHTML = svg;
}

function render(data) {
  const runs = data.runs || []; const latest = runs.at(-1); const status = document.querySelector("#status"); document.querySelector("#site-name").textContent = data.site?.name || "Webperf Core";
  if (!latest) { status.textContent = "Inga mätningar har publicerats ännu. Kör workflowet Webperf trend report i Webperf Core-forken för att skapa den första datapunkten."; return; }
  status.hidden = true; document.querySelector("#last-updated").textContent = `Senaste data: ${latest.display_date}`; const box = document.querySelector("#latest"); box.hidden = false; document.querySelector("#latest-title").textContent = latest.display_date; document.querySelector("#latest-url").textContent = latest.url; document.querySelector("#latest-detail").href = latest.detail;
  const progress = latest.progress || {completed:[], failed:[], total:[]}; const failed = progress.failed.length ? ` · fel i test ${progress.failed.join(", ")}` : ""; document.querySelector("#latest-progress").textContent = `${progress.completed.length} av ${progress.total.length} tester klara${failed}`;
  document.querySelector("#score-cards").innerHTML = Object.entries(scoreNames).map(([key,label]) => `<div><dt>${label}</dt><dd>${formatScore(latest.scores[key])}</dd></div>`).join("");
  chart(document.querySelector("#score-chart"), Object.entries(scoreNames).map(([key,name]) => ({ name, color: colors[key], values:runs.map(run => run.scores[key]) })), { min:1, max:5, minRange:4 });
  const metricKeys = [...new Set(runs.flatMap(run => Object.keys(run.metrics || {})))].sort(); const metricSelect = document.querySelector("#metric-select");
  if (!metricKeys.length) { metricSelect.disabled = true; metricSelect.innerHTML = "<option>Inga prestandamått ännu</option>"; chart(document.querySelector("#metric-chart"), []); } else { metricSelect.innerHTML = metricKeys.map(key => `<option value="${key}">${key.replace(":", " · ")}</option>`).join(""); const redraw = () => { const key = metricSelect.value; chart(document.querySelector("#metric-chart"), [{ name:key, color:colors.rating_perf, values:runs.map(run => run.metrics[key]) }], { min:0, label:value => key.endsWith(":CLS") ? value.toFixed(3) : `${Math.round(value)} ms` }); }; metricSelect.addEventListener("change", redraw); redraw(); }
  document.querySelector("#history-body").innerHTML = [...runs].reverse().map(run => `<tr><td>${escapeHtml(run.display_date)}</td><td>${formatScore(run.scores.rating)}</td><td>${formatScore(run.scores.rating_perf)}</td><td>${formatScore(run.scores.rating_a11y)}</td><td><a href="${run.detail}">Öppna</a></td></tr>`).join("");
}
fetch("data/summary.json").then(response => { if (!response.ok) throw new Error("Kunde inte läsa summary.json"); return response.json(); }).then(render).catch(() => { document.querySelector("#status").textContent = "Resultaten kunde inte laddas. Försök igen eller kontrollera att den automatiska rapportbyggnaden har lyckats."; });

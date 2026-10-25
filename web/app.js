"use strict";
const $ = id => document.getElementById(id);
const state = { dataset: null, datasetId: null, result: null, bits: [], timer: null, job: null };
const svgNS = "http://www.w3.org/2000/svg";
const int = id => Number($(id).value);
const presetLabels = { mul: "MUL(2,2,4)" };

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function svg(tag, attributes, text) {
  const node = document.createElementNS(svgNS, tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function error(err) { $("notice").hidden = false; $("notice").textContent = err.message || String(err); }
function clearError() { $("notice").hidden = true; }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
function action(id, fn) {
  $(id).addEventListener("click", async () => { clearError(); try { await fn(); } catch (err) { error(err); } });
}
function download(name, obj) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" }));
  const link = el("a"); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function stopAnimation() {
  clearInterval(state.timer); state.timer = null; $("play").textContent = "▶ Abspielen";
}
function evaluate(c, input) {
  const wires = [...input];
  for (const [a, b] of c.gates) wires.push(1 - (wires[a] & wires[b]));
  return { wires, outputs: c.outputs.map(o => wires[o]) };
}
function compatible() {
  return state.dataset && state.result && state.dataset.inputs === state.result.circuit.inputs && state.dataset.outputs === state.result.circuit.outputs.length;
}
async function setDataset(obj) {
  const saved = await api("/api/datasets", obj);
  state.dataset = saved.dataset; state.datasetId = saved.id;
  $("dataset-summary").textContent = `${saved.dataset.rows.length} Vektoren · ${saved.dataset.inputs}:${saved.dataset.outputs} · ${saved.dataset.exhaustive ? "vollständige Wahrheitstabelle" : "Stichprobe"}`;
  $("export-dataset").disabled = false;
  renderTable();
}
async function refresh() {
  const catalog = await api("/api/catalog");
  if (!$("preset").options.length) {
    for (const name of Object.keys(catalog.presets)) $("preset").add(new Option(presetLabels[name] || name.toUpperCase(), name));
    $("preset").add(new Option("Eigener Ausdruck", "custom"));
    $("preset").value = "xor";
    $("preset").addEventListener("change", () => {
      const name = $("preset").value, p = catalog.presets[name];
      $("mul-hint").hidden = name !== "mul";
      if (!p) return;
      $("inputs").value = p.inputs; $("outputs").value = p.outputs;
      $("dataset-name").value = presetLabels[name] || name; $("expression").value = p.expression;
    });
    if (!catalog.tiny_available) {
      $("backend").value = "python";
      $("job-status").textContent = "TinyLanguage ist noch nicht eingerichtet. Python ist bereit.";
    }
  }
  $("library").replaceChildren();
  if (!catalog.programs.length) $("library").append(el("p", "Deine Bibliothek wächst mit jedem Suchlauf.", "hint"));
  for (const program of catalog.programs) {
    const button = el("button");
    button.append(el("strong", `${program.dataset_name} · ${program.circuit.inputs}:${program.circuit.outputs.length}`));
    button.append(el("small", `${program.fitness.gates} Gatter · Tiefe ${program.fitness.depth} · ${(program.fitness.accuracy * 100).toFixed(1)} %`));
    button.append(el("span", verification(program.fitness), `badge${program.fitness.verified_truth_table ? "" : " warn"}`));
    button.append(el("small", program.id));
    button.addEventListener("click", async () => {
      clearError();
      try {
        const data = await api(`/api/datasets/${program.dataset_id}`);
        state.dataset = data; state.datasetId = program.dataset_id;
        $("dataset-summary").textContent = `${data.name} · ${data.rows.length} Vektoren · ${data.inputs}:${data.outputs}`;
        $("export-dataset").disabled = false;
        showProgram(program);
      } catch (err) { error(err); }
    });
    $("library").append(button);
  }
}
function verification(f) {
  return f.verified_truth_table ? "Vollständig geprüft" : f.exact_on_dataset ? "Passt zur Stichprobe" : "Annäherung";
}
function showProgram(result) {
  stopAnimation(); state.result = result;
  const c = result.circuit;
  state.bits = Array(c.inputs).fill(0);
  $("empty").hidden = true; $("program").hidden = false; $("export-program").disabled = false;
  $("step").max = c.gates.length; $("step").value = c.gates.length;
  $("metrics").replaceChildren();
  const metrics = [[c.gates.length, "NAND-Gatter"], [depths(c).depth, "Gattertiefe"], [`${c.inputs}:${c.outputs.length}`, "Ein- / Ausgänge"]];
  if (result.fitness) metrics.push([`${(result.fitness.accuracy * 100).toFixed(1)} %`, "Korrekte Vektorbits"]);
  for (const [value, label] of metrics) {
    const cell = el("div", undefined, "metric"); cell.append(el("strong", value), el("span", label)); $("metrics").append(cell);
  }
  $("program-name").textContent = result.fitness ? `${verification(result.fitness)} · ${result.id || "Suchergebnis"}` : "Eigenes Klammerprogramm · NAND verknüpft jeweils beide Argumente.";
  $("notation").textContent = result.expressions ? result.expressions.map((s, i) => `y${i} = ${s}`).join("  ;  ") : "Gatterliste im JSON-Export verfügbar.";
  renderSimulation(); renderTable(); renderHistory();
}
function depths(c) {
  const d = Array(c.inputs).fill(0);
  for (const [a, b] of c.gates) d.push(1 + Math.max(d[a], d[b]));
  return { d, depth: Math.max(...c.outputs.map(o => d[o])) };
}
function renderSimulation() {
  if (!state.result) return;
  const c = state.result.circuit, step = int("step");
  const result = evaluate(c, state.bits);
  $("bit-switches").replaceChildren();
  state.bits.forEach((bit, i) => {
    const button = el("button", `${i + 1}: ${bit}`, bit ? "on" : "");
    button.setAttribute("aria-label", `Eingang ${i + 1}: ${bit}`);
    button.setAttribute("aria-pressed", String(Boolean(bit)));
    button.addEventListener("click", () => { state.bits[i] ^= 1; renderSimulation(); });
    $("bit-switches").append(button);
  });
  const ready = ref => ref < c.inputs + step;
  $("output-values").replaceChildren(el("small", "AUSGANG · LSB ZUERST"), document.createTextNode(c.outputs.map(o => ready(o) ? result.wires[o] : "·").join(" ")));
  $("step-label").textContent = `${step}/${c.gates.length}`;
  const { d } = depths(c), levels = new Map(), positions = [];
  d.forEach((level, ref) => { if (!levels.has(level)) levels.set(level, []); levels.get(level).push(ref); });
  const maxLevel = Math.max(...d), height = Math.max(210, ...[...levels.values()].map(v => v.length * 64 + 40));
  for (const [level, refs] of levels) refs.forEach((ref, index) => { positions[ref] = { x: 28 + level * 155, y: (index + 1) * height / (refs.length + 1) }; });
  const outX = 28 + (maxLevel + 1) * 155, width = outX + 100;
  const graph = $("graph"); graph.replaceChildren(); graph.setAttribute("viewBox", `0 0 ${width} ${height}`); graph.setAttribute("width", width); graph.setAttribute("height", height);
  function wire(ref, end, offset = 0) {
    const start = positions[ref], color = !ready(ref) ? "#d8dfd4" : result.wires[ref] ? "#3e8c54" : "#99a8a0";
    graph.append(svg("path", { d: `M ${start.x + 82} ${start.y} C ${start.x + 120} ${start.y}, ${end.x - 40} ${end.y + offset}, ${end.x} ${end.y + offset}`, fill: "none", stroke: color, "stroke-width": result.wires[ref] && ready(ref) ? 2.5 : 1.5 }));
  }
  c.gates.forEach(([a, b], i) => { wire(a, positions[c.inputs + i], -9); wire(b, positions[c.inputs + i], 9); });
  c.outputs.forEach((ref, i) => wire(ref, { x: outX, y: (i + 1) * height / (c.outputs.length + 1) }));
  d.forEach((_, ref) => {
    const { x, y } = positions[ref], known = ready(ref), bit = result.wires[ref];
    graph.append(svg("rect", { x, y: y - 20, width: 82, height: 40, rx: ref < c.inputs ? 20 : 7, fill: !known ? "#f3f5f0" : bit ? "#d6ed95" : "#fff", stroke: known ? "#98b397" : "#dbe4d7" }));
    graph.append(svg("text", { x: x + 41, y: y + 4, "text-anchor": "middle", fill: known ? "#183e31" : "#abb7aa" }, `${ref < c.inputs ? `i${ref + 1}` : `⊼${ref - c.inputs + 1}`}  ${known ? bit : "·"}`));
  });
  c.outputs.forEach((ref, i) => {
    const y = (i + 1) * height / (c.outputs.length + 1);
    graph.append(svg("text", { x: outX + 4, y: y + 4, fill: "#146653" }, `y${i} = ${ready(ref) ? result.wires[ref] : "·"}`));
  });
}
function renderTable() {
  $("vectors").replaceChildren();
  if (!state.dataset) return;
  const ds = state.dataset, matches = compatible();
  $("table-info").textContent = `${ds.name} · ${ds.rows.length} Vektoren${ds.rows.length > 128 ? " · die ersten 128 werden angezeigt" : ""} · ${ds.exhaustive ? "alle Eingaben" : "Stichprobe"}${state.result && !matches ? " · Programm und Datensatz haben verschiedene Bitbreiten" : ""}. Zeile anklicken zum Testen.`;
  for (const row of ds.rows.slice(0, 128)) {
    const tr = el("tr"), input = row.slice(0, ds.inputs), output = row.slice(ds.inputs);
    const actual = matches ? evaluate(state.result.circuit, input).outputs : null;
    const ok = actual && actual.every((v, i) => v === output[i]);
    tr.append(el("td", input.join(" ")), el("td", output.join(" ")), el("td", actual ? actual.join(" ") : "–"), el("td", actual ? ok ? "✓" : "✕" : "–", actual ? ok ? "ok" : "bad" : ""));
    if (state.result && state.result.circuit.inputs === ds.inputs) tr.addEventListener("click", () => {
      stopAnimation(); state.bits = input; $("step").value = state.result.circuit.gates.length; renderSimulation();
    });
    $("vectors").append(tr);
  }
}
function renderHistory() {
  const target = $("history"), search = state.result.search;
  target.replaceChildren();
  if (!search) { $("search-summary").textContent = "Für ein eingegebenes Programm gibt es keinen Suchverlauf."; return; }
  const points = search.history, maxGen = Math.max(1, search.generation), maxErr = Math.max(1, ...points.map(p => p.errors));
  const px = g => 40 + g / maxGen * 610, py = e => 100 - e / maxErr * 78;
  target.append(svg("path", { d: "M 40 15 V 100 H 650", fill: "none", stroke: "#d6dfd0" }));
  target.append(svg("text", { x: 8, y: 25, fill: "#63777a", "font-size": 11 }, maxErr));
  target.append(svg("text", { x: 18, y: 104, fill: "#63777a", "font-size": 11 }, "0"));
  target.append(svg("text", { x: 40, y: 123, fill: "#63777a", "font-size": 10 }, "Generation 0"));
  target.append(svg("text", { x: 650, y: 123, fill: "#63777a", "font-size": 10, "text-anchor": "end" }, maxGen));
  const coords = [];
  points.forEach((p, i) => {
    if (i) coords.push(`${px(p.generation)},${py(points[i - 1].errors)}`);
    coords.push(`${px(p.generation)},${py(p.errors)}`);
  });
  if (points.length) coords.push(`${px(maxGen)},${py(points[points.length - 1].errors)}`);
  target.append(svg("polyline", { points: coords.join(" "), fill: "none", stroke: "#146653", "stroke-width": 2.5 }));
  for (const p of points) target.append(svg("circle", { cx: px(p.generation), cy: py(p.errors), r: 3, fill: "#146653" }));
  $("search-summary").textContent = `${search.backend === "tiny" ? "TinyLanguage" : "Python"} · ${search.evaluations} Kandidaten · ${search.generation} Generationen · ${search.elapsed_seconds} s · ${search.library_candidates} verwendbare Bibliotheksbausteine · Seed ${search.seed}`;
}

action("generate", () => setDataset({ name: $("dataset-name").value, inputs: int("inputs"), outputs: int("outputs"), expression: $("expression").value, samples: int("samples"), seed: int("seed") }));
action("import-rows", () => setDataset({ name: $("dataset-name").value, inputs: int("inputs"), outputs: int("outputs"), rows: JSON.parse($("raw-rows").value) }));
$("import").addEventListener("change", async event => { clearError(); try { if (event.target.files[0]) await setDataset(JSON.parse(await event.target.files[0].text())); } catch (err) { error(err); } });
action("evolve", async () => {
  if (!state.datasetId) throw new Error("Bitte zuerst Zuordnungsvektoren erzeugen.");
  const config = { gates: int("gates"), population: int("population"), generations: int("generations"), seed: int("seed"), backend: $("backend").value };
  const { job_id } = await api("/api/search", { dataset_id: state.datasetId, config });
  state.job = job_id; $("evolve").disabled = true;
  $("job-status").textContent = "Suche läuft …";
  async function poll() {
    try {
      const job = await api(`/api/jobs/${job_id}`);
      $("job-status").textContent = `Suche läuft · ${job.elapsed_seconds} s`;
      if (job.status === "done") {
        state.job = null; $("evolve").disabled = false;
        showProgram(job.result); await refresh();
        $("job-status").textContent = `${verification(job.result.fitness)} · Programm gespeichert.`;
      } else if (job.status === "failed") {
        state.job = null; $("evolve").disabled = false; $("job-status").textContent = "Suche fehlgeschlagen."; error(new Error(job.error));
      } else setTimeout(poll, 700);
    } catch (err) {
      state.job = null; $("evolve").disabled = false; $("job-status").textContent = "Verbindung zur Suche unterbrochen."; error(err);
    }
  }
  setTimeout(poll, 250);
});
action("parse", async () => {
  const { circuit } = await api("/api/parse", { expression: $("nand-expression").value, inputs: int("nand-inputs") });
  showProgram({ circuit, expressions: [$("nand-expression").value] });
});
action("refresh", refresh);
action("export-program", () => download(`${state.result.id || "nand-programm"}.json`, state.result));
action("export-dataset", () => download(`${state.datasetId}.json`, state.dataset));
$("step").addEventListener("input", () => { stopAnimation(); renderSimulation(); });
$("play").addEventListener("click", () => {
  if (state.timer) { stopAnimation(); return; }
  $("step").value = 0; renderSimulation(); $("play").textContent = "Ⅱ Pause";
  state.timer = setInterval(() => {
    $("step").value = int("step") + 1; renderSimulation();
    if (int("step") >= state.result.circuit.gates.length) stopAnimation();
  }, 450);
});
refresh().catch(error);

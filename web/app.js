"use strict";
const $ = id => document.getElementById(id);
const state = { dataset: null, datasetId: null, result: null, bits: [], timer: null, job: null, librarySignature: null,
  positions: [], selectedRef: 0, layoutToken: 0, layoutDirty: false, routing: null, drag: null,
  camera: null, cameraTouched: false, wires: {}, selectedWire: null, wireNotice: "", operations: {}, presets: {}, referenceCircuit: null, formMode: "legacy", autoName: false, functionSignature: null,
  referenceBlock: null, blockSignature: null };
const svgNS = "http://www.w3.org/2000/svg";
const int = id => Number($(id).value);
const presetLabels = { mul: "MUL(2,2,4)" };

function portRow(side, port, expression = "0") {
  const row = el("div", undefined, "port-editor"); row.dataset.side = side;
  function field(label, key, value, type = "text") {
    const wrap = el("label", label), input = el("input"); input.type = type; input.value = value;
    input.dataset.field = key;
    if (type === "number") { input.min = 1; input.max = 32; }
    wrap.append(input); row.append(wrap);
    input.addEventListener("input", updateDefinition);
  }
  field(side === "inputs" ? "Eingangsname" : "Ergebnisname", "name", port.name);
  field("Bits", "bits", port.bits, "number");
  const signed = el("label", undefined, "check-label"), check = el("input");
  check.type = "checkbox"; check.checked = Boolean(port.signed); check.dataset.field = "signed";
  signed.append(check, document.createTextNode("Zweierkomplement")); row.append(signed);
  check.addEventListener("change", updateDefinition);
  if (side === "outputs") {
    const label = el("label", "Überlauf"), select = el("select"); select.dataset.field = "overflow";
    select.add(new Option("Fehler", "error")); select.add(new Option("Abschneiden", "wrap"));
    select.value = port.overflow || "error"; label.append(select); row.append(label);
    const exprLabel = el("label", "Referenzausdruck"), expr = el("textarea");
    expr.rows = 2; expr.value = expression; expr.dataset.field = "expression"; expr.spellcheck = false;
    exprLabel.className = "port-expression"; exprLabel.append(expr); row.append(exprLabel);
  }
  const remove = el("button", "Port entfernen", "text-button remove-port");
  remove.addEventListener("click", () => { row.remove(); updateDefinition(); }); row.append(remove);
  return row;
}
function editPorts(spec, expressions = {}) {
  for (const side of ["inputs", "outputs"]) {
    const container = $(side === "inputs" ? "input-ports" : "output-ports");
    container.replaceChildren(...spec[side].map(p => portRow(side, p, expressions[p.name] || "0")));
  }
}
function editLegacyPorts(inputs, outputs, expression) {
  let ports;
  if (/\b[ab]\b/.test(expression) && inputs >= 2) {
    ports = [{ name: "a", bits: Math.floor(inputs / 2) }, { name: "b", bits: Math.ceil(inputs / 2) }];
  } else {
    ports = Array.from({ length: inputs }, (_, i) => ({ name: `in${i}`, bits: 1 }));
    expression = expression.replace(/\bx(\d+)\b/g, (_, i) => `in${i}`);
  }
  editPorts({ inputs: ports, outputs: [{ name: "c", bits: outputs, overflow: "error" }] }, { c: expression });
}
function readPorts() {
  const spec = { inputs: [], outputs: [] }, expressions = {};
  for (const row of document.querySelectorAll(".port-editor")) {
    const get = key => row.querySelector(`[data-field="${key}"]`);
    const port = { name: get("name").value, bits: Number(get("bits").value), signed: get("signed").checked };
    if (row.dataset.side === "outputs") {
      port.overflow = get("overflow").value; expressions[port.name] = get("expression").value;
    }
    spec[row.dataset.side].push(port);
  }
  return { spec, expressions };
}
function operationRequest() {
  const definition = $("operation").value, op = state.operations[definition];
  const params = { a_bits: int("a-bits"), result_bits: int("result-bits"), signed: $("signed").checked,
    overflow: $("overflow").value, flag: $("result-flag").checked && Boolean(op?.flag) };
  if (op?.shift && $("shift-mode").value === "fixed") params.shift = int("shift");
  else if (op?.operands >= 2) params.b_bits = int("b-bits");
  return { definition, version: 1, parameters: params };
}
function operationLabel(definition, p) {
  const widths = [p.a_bits];
  if (p.b_bits) widths.push(p.b_bits);
  if (state.operations[definition]?.operands === 3) widths.push(1);
  widths.push(p.result_bits);
  return `${definition}(${widths.join(",")})${p.shift !== undefined ? ` [n=${p.shift}]` : ""}`;
}
function chooseOperation(definition, parameters = null) {
  const op = state.operations[definition]; if (!op) return;
  $("operation").value = definition;
  const p = parameters || { a_bits: op.defaults[0], b_bits: op.operands >= 2 ? op.defaults[1] : undefined,
    result_bits: op.defaults[2], signed: Boolean(op.default_signed) };
  $("a-bits").value = p.a_bits; $("b-bits").value = p.b_bits || 1; $("result-bits").value = p.result_bits;
  $("signed").checked = Boolean(p.signed); $("overflow").value = p.overflow || "wrap"; $("result-flag").checked = Boolean(p.flag);
  $("shift-mode").value = p.shift !== undefined ? "fixed" : "input"; $("shift").value = p.shift ?? 1;
  const label = operationLabel(definition, p);
  state.autoName = !parameters || [label, definition.toLowerCase(), definition].includes($("dataset-name").value);
  $("task-mode").value = "operation"; updateDefinition();
}
function updateDefinition() {
  const mode = $("task-mode").value, formula = mode === "formula", named = formula || mode === "named" || mode === "circuit";
  $("formula-editor").hidden = !formula;
  const options = $("named-options"); options.classList.toggle("formula-mode", formula);
  if (formula) { if (options.parentNode !== $("formula-ports")) $("formula-ports").append(options); }
  else if (options.parentNode === $("formula-ports")) $("ports-home").after(options);
  $("operation-options").hidden = mode !== "operation"; $("named-options").hidden = !named;
  $("expression").closest("label").hidden = mode !== "legacy";
  $("expression-hint").hidden = mode !== "legacy"; $("mul-hint").hidden = true;
  $("inputs").readOnly = $("outputs").readOnly = mode !== "legacy";
  $("circuit-reference-hint").hidden = mode !== "circuit";
  for (const node of document.querySelectorAll(".port-expression, .remove-port, #add-input-port, #add-output-port")) node.hidden = mode === "circuit";
  if (formula) for (const node of document.querySelectorAll(".port-expression")) node.hidden = true;
  let n = int("inputs"), m = int("outputs"), description = "";
  if (mode === "operation") {
    const def = state.operations[$("operation").value];
    if (def?.predicate) $("result-bits").value = 1;
    $("result-bits").readOnly = Boolean(def?.predicate);
    const op = operationRequest(), p = op.parameters, label = operationLabel(op.definition, p);
    if (state.autoName) $("dataset-name").value = label;
    n = p.a_bits + (p.b_bits || 0) + Number(def?.operands === 3);
    m = p.result_bits + Number(p.flag) + (op.definition === "DIV" ? 2 : 0);
    $("b-bits-label").hidden = !p.b_bits;
    $("shift-options").hidden = !def?.shift; $("shift-label").hidden = p.shift === undefined;
    $("flag-label").hidden = !def?.flag;
    $("operation-hint").textContent = def?.description || "";
    description = `${label} · ${p.signed ? "Zweierkomplement" : "unsigned"} · ${p.overflow === "wrap" ? "Ergebnis modulo 2^Breite" : "Überlauf wird abgelehnt"}.`;
    if (def?.predicate) description += " Ergebnis c ist ein unsigned Wahrheitsbit.";
    if (op.definition === "IsNegative") description += " Ohne Vorzeichen ist das Ergebnis immer 0.";
    if (op.definition === "DIV") description += " b=0: c=0, valid=0, div0=1; sonst valid=1, div0=0. Ergebnisüberlauf folgt der gewählten Regel.";
    if (p.flag) description += ["SUB", "DEC"].includes(op.definition) && !p.signed ? " Borrow: Ergebnis < 0; Abschneiden positiver hoher Bits setzt Borrow nicht." : ` Statusbit: ausserhalb des Ergebnisbereichs (${p.signed || op.definition === "MUL" ? "Overflow" : "Carry"}).`;
  } else if (named) {
    const { spec } = readPorts();
    n = spec.inputs.reduce((v, p) => v + p.bits, 0); m = spec.outputs.reduce((v, p) => v + p.bits, 0);
    description = `${spec.inputs.map(p => `${p.name}[${p.bits}]`).join(", ")} → ${spec.outputs.map(p => `${p.name}[${p.bits}]`).join(", ")} · LSB zuerst.`;
  } else if (mode === "block") {
    const root = state.referenceBlock?.definitions[state.referenceBlock.root];
    if (root) {
      n = root.interface.inputs.reduce((v, p) => v + p.bits, 0);
      m = root.interface.outputs.reduce((v, p) => v + p.bits, 0);
      description = `${root.name} · Version ${root.version} · Feste Bausteinreferenz mit gespeicherten Unterbausteinen.`;
    } else description = "Unterprogramm-Baustein öffnen, um seine Referenz zu verwenden.";
  }
  if (mode !== "legacy") { $("inputs").value = n; $("outputs").value = m; }
  $("variant-description").textContent = description + (mode === "legacy" ? "" : ` Diese Breitenkombination wird als eigene Funktion gespeichert. ${n <= 16 ? `Vollständige Tabelle: ${2 ** n} Eingaben möglich.` : `2^${n} Eingaben: maximal 65536 Vektoren als Stichprobe.`}`);
  state.formMode = mode;
}
function restoreDefinition(ds) {
  $("dataset-name").value = ds.name; $("inputs").value = ds.inputs; $("outputs").value = ds.outputs;
  const meta = ds.metadata || {};
  $("preset").value = meta.operation ? (state.presets[meta.operation.definition.toLowerCase()] ? meta.operation.definition.toLowerCase() : `op:${meta.operation.definition}`) : "custom";
  if (meta.hierarchy) {
    state.referenceBlock = meta.hierarchy; $("task-mode").value = "block"; updateDefinition();
  } else if (meta.operation && state.operations[meta.operation.definition]) chooseOperation(meta.operation.definition, meta.operation.parameters);
  else if (meta.interface) {
    state.referenceCircuit = meta.reference_circuit || null;
    editPorts(meta.interface, typeof meta.expression === "object" ? meta.expression : { [meta.interface.outputs[0].name]: meta.expression || "0" });
    $("task-mode").value = meta.formula ? "formula" : meta.reference_circuit ? "circuit" : "named";
    if (meta.formula) $("formula-source").value = meta.formula.source;
    updateDefinition();
  } else {
    $("task-mode").value = "legacy";
    if (typeof meta.expression === "string") $("expression").value = meta.expression;
    updateDefinition();
  }
}
function datasetSummary(ds) {
  const ports = ds.metadata?.interface;
  const mapping = ports ? ` · ${ports.inputs.map(p => `${p.name}[${p.bits}]`).join(" + ")} → ${ports.outputs.map(p => `${p.name}[${p.bits}]`).join(" + ")}` : "";
  $("dataset-summary").textContent = `${ds.name} · ${ds.rows.length} Vektoren · ${ds.inputs}:${ds.outputs} · ${ds.exhaustive ? "vollständige Wahrheitstabelle" : "Stichprobe"}${mapping}`;
}

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
  datasetSummary(saved.dataset); restoreDefinition(saved.dataset);
  $("export-dataset").disabled = false;
  renderTable();
  await refresh();
}
function renderFunctions(catalog) {
  const signature = JSON.stringify([catalog.datasets, catalog.programs.map(p => [p.id, p.dataset_id, p.task_id])]);
  if (signature === state.functionSignature) return;
  state.functionSignature = signature;
  const groups = new Map();
  for (const dataset of catalog.datasets) {
    const key = dataset.function_id || dataset.id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(dataset);
  }
  $("functions").replaceChildren();
  if (!groups.size) $("functions").append(el("p", "Noch keine Funktion gespeichert. Links eine Operation und ihre Bitbreiten wählen und speichern.", "hint"));
  for (const datasets of [...groups.values()].sort((a, b) => a[0].function_name.localeCompare(b[0].function_name))) {
    datasets.sort((a, b) => b.count - a.count || a.id.localeCompare(b.id));
    const first = datasets[0], entry = el("div", undefined, "library-entry function-entry");
    const p = first.metadata?.operation?.parameters;
    entry.append(el("strong", first.function_name));
    if (p) entry.append(el("small", `${p.signed ? "Zweierkomplement" : "unsigned"} · ${p.overflow === "wrap" ? "Abschneiden" : "Überlauffehler"}${p.flag ? " · Statusausgang" : ""}`));
    if (first.metadata?.formula) entry.append(el("code", first.metadata.formula.source, "function-formula"));
    const select = el("select"); select.setAttribute("aria-label", `Vektorsatz für ${first.function_name}`);
    for (const ds of datasets) select.add(new Option(`${ds.count} Vektoren · ${ds.exhaustive ? "vollständig" : "Stichprobe"} · ${ds.name} · ${ds.id.slice(-12)}`, ds.id));
    if (datasets.some(ds => ds.id === state.datasetId)) select.value = state.datasetId;
    entry.append(select);
    const info = el("small"), button = el("button", "Funktion öffnen", "secondary function-open");
    function selected() { return datasets.find(d => d.id === select.value); }
    function program() { return catalog.programs.find(p => p.task_id === selected().task_id); }
    function describe() {
      const ds = selected(), implementation = program();
      info.textContent = `${ds.inputs} Eingangsbits → ${ds.outputs} Ausgangsbits · ${implementation ? `Schaltung: ${verification(implementation.fitness)}` : "Funktion definiert · keine Schaltung für diesen Vektorsatz"}`;
    }
    select.addEventListener("change", describe); describe();
    button.addEventListener("click", async () => {
      clearError();
      try {
        const ds = selected(), data = await api(`/api/datasets/${ds.id}`);
        stopAnimation(); state.dataset = data; state.datasetId = ds.id;
        datasetSummary(data); restoreDefinition(data); $("export-dataset").disabled = false;
        const implementation = program();
        if (implementation) showProgram(implementation);
        else {
          state.result = null; $("program").hidden = true; $("empty").hidden = false;
          $("save-block-program").disabled = true;
          $("export-program").disabled = true; $("repair-program").disabled = true; renderTable();
        }
        if (!state.job) $("job-status").textContent = `${ds.function_name} geladen · bereit für die Evolution.`;
      } catch (err) { error(err); }
    });
    entry.append(info, button); $("functions").append(entry);
  }
}
async function refresh() {
  const catalog = await api("/api/catalog");
  if (!catalog.operations) throw new Error("Die neuen Bitbreitenfunktionen benötigen einen Neustart des lokalen Webservers. Danach die Seite neu laden.");
  if (catalog.datasets.some(ds => !ds.function_id)) throw new Error("Die Funktionsübersicht benötigt einen Neustart des lokalen Webservers. Danach die Seite neu laden.");
  state.operations = catalog.operations;
  state.presets = catalog.presets;
  if (!$("preset").options.length) {
    for (const name of Object.keys(catalog.operations)) $("operation").add(new Option(name, name));
    editPorts({ inputs: [{ name: "a", bits: 2 }, { name: "b", bits: 2 }], outputs: [{ name: "c", bits: 3 }] }, { c: "a+b" });
    for (const name of Object.keys(catalog.presets)) $("preset").add(new Option(presetLabels[name] || name.toUpperCase(), name));
    for (const name of Object.keys(catalog.operations)) if (!catalog.presets[name.toLowerCase()]) $("preset").add(new Option(name, `op:${name}`));
    $("preset").add(new Option("Eigener Ausdruck", "custom"));
    $("preset").value = "xor";
    $("preset").addEventListener("change", () => {
      const name = $("preset").value, p = catalog.presets[name];
      $("mul-hint").hidden = name !== "mul";
      if (name.startsWith("op:")) { chooseOperation(name.slice(3)); return; }
      if (!p) return;
      if (catalog.operations[name.toUpperCase()]) {
        chooseOperation(name.toUpperCase()); return;
      }
      $("task-mode").value = "legacy"; updateDefinition();
      $("inputs").value = p.inputs; $("outputs").value = p.outputs;
      $("dataset-name").value = presetLabels[name] || name; $("expression").value = p.expression;
    });
    if (!catalog.tiny_available) {
      $("backend").value = "python";
      $("job-status").textContent = "TinyLanguage ist noch nicht eingerichtet. Python ist bereit.";
    }
  }
  $("background-status").textContent = `Hintergrundsuche · ${catalog.background.message} · ${catalog.background.attempts} Durchgänge`;
  renderFunctions(catalog);
  renderBlocks(catalog.blocks || []);
  const signature = JSON.stringify(catalog.programs.map(p => [p.id, p.frozen]));
  if (signature === state.librarySignature) return;
  state.librarySignature = signature;
  $("library").replaceChildren();
  if (!catalog.programs.length) $("library").append(el("p", "Deine Bibliothek wächst mit jedem Suchlauf.", "hint"));
  for (const program of catalog.programs) {
    const entry = el("div", undefined, "library-entry");
    const button = el("button", undefined, "library-open");
    button.append(el("strong", `${program.dataset_name} · ${program.circuit.inputs}:${program.circuit.outputs.length}`));
    button.append(el("small", `${program.fitness.gates} Gatter · Tiefe ${program.fitness.depth} · ${(program.fitness.accuracy * 100).toFixed(1)} %`));
    button.append(el("span", verification(program.fitness), `badge${program.fitness.verified_truth_table ? "" : " warn"}`));
    if (program.correction) button.append(el("small", `${program.correction.cases.length} ${program.correction.cases.length === 1 ? "Restfall" : "Restfälle"} durch NAND-Gatter korrigiert`));
    button.append(el("small", program.id));
    button.addEventListener("click", async () => {
      clearError();
      try {
        const data = await api(`/api/datasets/${program.dataset_id}`);
        state.dataset = data; state.datasetId = program.dataset_id;
        datasetSummary(data); restoreDefinition(data);
        $("export-dataset").disabled = false;
        showProgram(program);
      } catch (err) { error(err); }
    });
    const label = el("label", undefined, "check-label frozen-control");
    const frozen = el("input"); frozen.type = "checkbox"; frozen.checked = program.frozen;
    frozen.setAttribute("aria-label", `Frozen: ${program.dataset_name} ${program.circuit.inputs}:${program.circuit.outputs.length}`);
    label.append(frozen, document.createTextNode("Frozen · Hintergrundsuche stoppen"));
    frozen.addEventListener("change", async () => {
      clearError(); frozen.disabled = true;
      try {
        await api(`/api/programs/${program.id}/frozen`, { frozen: frozen.checked });
        await refresh();
      } catch (err) { frozen.checked = program.frozen; error(err); }
      finally { frozen.disabled = false; }
    });
    entry.append(button, label);
    $("library").append(entry);
  }
}
function verification(f) {
  return f.verified_truth_table ? "Vollständig geprüft" : f.exact_on_dataset ? "Passt zur Stichprobe" : "Annäherung";
}
function showProgram(result) {
  stopAnimation(); state.result = result;
  if (result.hierarchy) {
    inspectBlock(result.hierarchy);
    $("block-status").textContent = "Die geöffnete Schaltung enthält die unten gezeigten festen Unterbausteine.";
  } else {
    $("block-tree").hidden = true;
    $("block-status").textContent = "Die geöffnete NAND-Schaltung ist flach. Sie kann als neuer Baustein gespeichert werden.";
  }
  const c = result.circuit;
  state.positions = CircuitGraph.automatic(c); state.selectedRef = 0;
  state.wires = {}; state.selectedWire = null; state.wireNotice = "";
  state.layoutDirty = false; state.routing = null; state.drag = null;
  state.camera = null; state.cameraTouched = false;
  const layoutToken = ++state.layoutToken;
  $("layout-status").textContent = "Automatische Anordnung. Gespeichertes Layout wird geladen …";
  api("/api/layout/load", { circuit: c }).then(({ positions, wires = {} }) => {
    if (layoutToken !== state.layoutToken || state.layoutDirty || state.drag) return;
    if (CircuitGraph.valid(c, positions) && positions.every((p, ref) => CircuitGraph.canPlace(positions, ref, p))) {
      state.positions = positions; state.wires = wires; state.routing = null;
      if (!state.cameraTouched) state.camera = null;
      renderSimulation();
      $("layout-status").textContent = "Gespeichertes Layout geladen.";
    } else $("layout-status").textContent = "Automatische Anordnung. Das Layout kann auf diesem Rechner gespeichert werden.";
  }).catch(err => {
    if (layoutToken === state.layoutToken && !state.layoutDirty) $("layout-status").textContent = `Layout konnte nicht geladen werden: ${err.message}`;
  });
  state.bits = Array(c.inputs).fill(0);
  $("empty").hidden = true; $("program").hidden = false; $("export-program").disabled = false;
  $("save-block-program").disabled = false;
  $("block-name").value = result.hierarchy ? result.hierarchy.definitions[result.hierarchy.root].name : result.dataset_name || state.dataset?.name || "Mein Baustein";
  $("step").max = c.gates.length; $("step").value = c.gates.length;
  $("metrics").replaceChildren();
  const metrics = [[c.gates.length, "NAND-Gatter"], [depths(c).depth, "Gattertiefe"], [`${c.inputs}:${c.outputs.length}`, "Ein- / Ausgänge"]];
  if (result.fitness) metrics.push([`${(result.fitness.accuracy * 100).toFixed(1)} %`, "Korrekte Vektorbits"]);
  for (const [value, label] of metrics) {
    const cell = el("div", undefined, "metric"); cell.append(el("strong", value), el("span", label)); $("metrics").append(cell);
  }
  $("program-name").textContent = result.fitness ? `${verification(result.fitness)} · ${result.id || "Suchergebnis"}` : "Eigenes NAND-Programm · ⊼ steht zwischen den beiden Argumenten.";
  $("repair-program").disabled = !result.id || !result.fitness?.errors || Boolean(state.job);
  $("correction-details").hidden = !result.correction;
  $("correction-cases").replaceChildren();
  if (result.correction) {
    $("correction-summary").textContent = `${result.correction.cases.length} ${result.correction.cases.length === 1 ? "Restfall" : "Restfälle"} exakt korrigiert · ${result.correction.added_gates} zusätzliche NAND-Gatter`;
    for (const c of result.correction.cases) $("correction-cases").append(el("li", `(${c.inputs.join(",")}) → (${c.expected.join(",")}), zuvor (${c.actual.join(",")})`));
  }
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
    const port = compatible() && state.dataset.metadata?.interface?.inputs.find(p => p.offset <= i && i < p.offset + p.bits);
    const name = port ? `${port.name}[${i - port.offset}]` : String(i + 1);
    const button = el("button", `${name}: ${bit}`, bit ? "on" : "");
    button.setAttribute("aria-label", `Eingang ${name}: ${bit}`);
    button.setAttribute("aria-pressed", String(Boolean(bit)));
    button.addEventListener("click", () => toggleInput(i));
    $("bit-switches").append(button);
  });
  const ready = ref => ref < c.inputs + step;
  $("output-values").replaceChildren(el("small", "AUSGANG · LSB ZUERST"), document.createTextNode(c.outputs.map(o => ready(o) ? result.wires[o] : "·").join(" ")));
  $("step-label").textContent = `${step}/${c.gates.length}`;
  const graph = $("graph"), positions = state.positions, list = CircuitGraph.nodes(c);
  const focusedRef = document.activeElement?.closest?.("#graph [data-node]")?.getAttribute("data-node");
  const focusedWire = document.activeElement?.closest?.("#graph [data-wire]");
  const wireFocus = focusedWire && [focusedWire.getAttribute("data-wire"), focusedWire.getAttribute("data-segment")];
  graph.replaceChildren();
  if (!state.routing) state.routing = CircuitGraph.routes(c, positions, state.wires);
  if (!state.camera) state.camera = CircuitViewport.fit(graphBounds(), graphSize());
  renderCamera();
  for (const wire of state.routing) {
    const known = ready(wire.source), bit = result.wires[wire.source];
    const path = svg("path", { d: wire.path, fill: "none", stroke: !known ? "#d8dfd4" : bit ? "#3e8c54" : "#99a8a0",
      "stroke-width": wire.id === state.selectedWire ? 4 : known && bit ? 2.5 : 1.5, "stroke-linejoin": "round",
      class: `signal-wire${wire.blocked ? " blocked" : ""}${wire.id === state.selectedWire ? " selected" : ""}`,
      "data-source": wire.source, "data-target": wire.target, "data-port": wire.port });
    path.append(svg("title", {}, `Box ${wire.source} → Box ${wire.target}: ${known ? bit : "noch nicht ausgewertet"}`));
    graph.append(path);
  }
  // Wide hit areas keep thin wires usable at every zoom level. Boxes are painted last.
  for (const wire of state.routing) wire.points.slice(1).forEach((b, index) => {
    const a = wire.points[index];
    if (a.x === b.x && a.y === b.y) return;
    const hit = svg("path", { d: `M ${a.x} ${a.y} L ${b.x} ${b.y}`, fill: "none", stroke: "transparent",
      "stroke-width": 14, "vector-effect": "non-scaling-stroke", "data-wire": wire.id, "data-segment": index,
      class: `wire-hit ${a.x === b.x ? "vertical" : "horizontal"}`, tabindex: 0, role: "button",
      "aria-label": `Leitung Box ${wire.source} zu Box ${wire.target}, Eingang ${wire.port + 1}, Segment ${index + 1}. Ziehen oder Pfeiltasten; Entf setzt die Leitung zurück.` });
    hit.addEventListener("focus", () => { state.selectedWire = wire.id; updateWireStatus(); });
    graph.append(hit);
  });
  updateWireStatus();
  const valueAt = ref => ready(ref) ? result.wires[ref] : "·";
  list.forEach(node => {
    const { ref, kind, index, sources } = node, { x, y } = positions[ref];
    const signal = kind === "output" ? sources[0] : ref, known = ready(signal), bit = result.wires[signal];
    const heading = `Box ${ref} · ${kind === "input" ? `Eingang ${index + 1}` : kind === "gate" ? "NAND" : `Ausgang y${index}`}`;
    const formula = kind === "gate" ? `Box ${sources[0]} ⊼ Box ${sources[1]}` : kind === "output" ? `von Box ${sources[0]}` : "Klicken: 0 ↔ 1";
    const description = kind === "gate" ? `Box ${ref}: Box ${sources[0]} NAND mit Box ${sources[1]} verknüpft. Wert: ${valueAt(signal)}.` : `${heading}. Wert: ${valueAt(signal)}. ${kind === "input" ? "Zum Umschalten anklicken." : formula}`;
    const group = svg("g", { "data-node": ref, class: `graph-node ${kind}${ref === state.selectedRef ? " selected" : ""}`, tabindex: 0, role: "button", "aria-label": description });
    if (kind === "input") group.setAttribute("aria-pressed", String(Boolean(bit)));
    group.append(svg("title", {}, `${description} Zum Verschieben ziehen oder Pfeiltasten verwenden.`));
    group.append(svg("rect", { x, y: y - CircuitGraph.height / 2, width: CircuitGraph.width, height: CircuitGraph.height, rx: kind === "input" ? 24 : 9,
      fill: !known ? "#f3f5f0" : bit ? "#d6ed95" : "#fff", stroke: ref === state.selectedRef ? "#146653" : "#98b397", "stroke-width": ref === state.selectedRef ? 2 : 1 }));
    const text = (offset, content, className) => svg("text", { x: x + CircuitGraph.width / 2, y: y + offset, "text-anchor": "middle", class: className, fill: known ? "#183e31" : "#758575" }, content);
    group.append(text(-19, heading, "node-heading"), text(3, formula, "node-formula"), text(25, `Wert: ${valueAt(signal)}`, "node-value"));
    graph.append(group);
  });
  const selected = list[state.selectedRef];
  if (selected) {
    const signal = selected.kind === "output" ? selected.sources[0] : selected.ref;
    $("box-description").textContent = selected.kind === "gate"
      ? `Box ${selected.ref}: Box ${selected.sources[0]} NAND mit Box ${selected.sources[1]} verknüpft. Aktuell: ${valueAt(selected.sources[0])} ⊼ ${valueAt(selected.sources[1])} = ${valueAt(signal)}. NAND liefert nur bei zwei Einsen eine 0.`
      : selected.kind === "input" ? `Box ${selected.ref} ist Eingang ${selected.index + 1}. Wert: ${valueAt(signal)}. Mit einem Klick oder der Leertaste zwischen 0 und 1 umschalten.`
      : `Box ${selected.ref} ist Ausgang y${selected.index} und übernimmt den Wert von Box ${signal}: ${valueAt(signal)}.`;
  }
  if (focusedRef !== undefined) graph.querySelector(`[data-node="${focusedRef}"]`)?.focus({ preventScroll: true });
  else if (wireFocus) graph.querySelector(`[data-wire="${wireFocus[0]}"][data-segment="${wireFocus[1]}"]`)?.focus({ preventScroll: true });
}

function updateWireStatus() {
  const wire = state.routing?.find(w => w.id === state.selectedWire);
  $("reset-wire").disabled = !wire?.manual;
  const blocked = state.routing?.filter(w => w.blocked).length || 0;
  $("wire-status").textContent = (wire ? `Leitung Box ${wire.source} → Box ${wire.target}, Eingang ${wire.port + 1}${wire.manual ? " · manueller Weg" : " · automatischer Weg"}. ` : "") +
    (blocked ? `${blocked} manuelle Wege sind durch Boxen oder Anschlüsse blockiert (orange gestrichelt). Vorübergehend automatisch geführt; gespeicherte Stützpunkte bleiben erhalten.` : state.wireNotice || "Leitungssegmente quer zu ihrer Richtung ziehen. Anschlüsse bleiben fest; Wege durch Boxen werden abgelehnt.");
}

function moveWire(wire, index, original, point) {
  const points = CircuitGraph.moveSegment(original, index, point);
  if (!CircuitGraph.usablePath(wire, points, state.positions)) {
    state.wireNotice = "Dieser Weg ist ungültig oder führt durch eine Box. Der letzte gültige Leitungsweg bleibt erhalten.";
    updateWireStatus();
    return false;
  }
  state.wires[wire.id] = points; layoutChanged(); renderSimulation(); return true;
}

function toggleInput(ref) {
  stopAnimation(); state.bits[ref] ^= 1; renderSimulation(); renderTable();
}
function layoutChanged() {
  state.layoutDirty = true; state.routing = null; state.wireNotice = "";
  $("layout-status").textContent = "Layout geändert · noch nicht gespeichert.";
}
function moveBox(ref, x, y) {
  const point = { x: Math.max(20, Math.min(99000, x)), y: Math.max(64, Math.min(99000, y)) };
  if (!CircuitGraph.canPlace(state.positions, ref, point)) return false;
  state.positions[ref] = point; layoutChanged(); return true;
}
function graphSize() {
  const rect = $("graph").getBoundingClientRect();
  return { width: Math.max(1, rect.width), height: Math.max(1, rect.height) };
}
function graphBounds() {
  const points = state.positions.flatMap(p => [{ x: p.x, y: p.y - CircuitGraph.height / 2 },
    { x: p.x + CircuitGraph.width, y: p.y + CircuitGraph.height / 2 }]);
  for (const wire of state.routing || []) points.push(...wire.points);
  return { left: Math.min(...points.map(p => p.x)), right: Math.max(...points.map(p => p.x)),
    top: Math.min(...points.map(p => p.y)), bottom: Math.max(...points.map(p => p.y)) };
}
function renderCamera() {
  if (!state.camera) return;
  const { x, y, scale } = state.camera, size = graphSize();
  $("graph").setAttribute("viewBox", `${x - size.width / (2 * scale)} ${y - size.height / (2 * scale)} ${size.width / scale} ${size.height / scale}`);
  $("zoom-level").textContent = `${Number((scale * 100).toFixed(scale < 0.1 ? 1 : 0))} %`;
  $("zoom-out").disabled = scale <= CircuitViewport.minScale;
  $("zoom-in").disabled = scale >= CircuitViewport.maxScale;
}
function zoomGraph(scale, point) {
  if (!state.camera || state.drag) return;
  state.camera = CircuitViewport.zoom(state.camera, graphSize(), scale, point);
  state.cameraTouched = true; renderCamera();
}
function fitGraph() {
  if (!state.result || state.drag) return;
  state.camera = CircuitViewport.fit(graphBounds(), graphSize());
  state.cameraTouched = true; renderCamera();
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

const graphElement = $("graph");
graphElement.addEventListener("pointerdown", event => {
  const node = event.target.closest("[data-node]");
  const segment = event.target.closest("[data-wire]");
  if (!state.camera || state.drag || ![0, 1].includes(event.button)) return;
  if (segment && event.button === 0) {
    event.preventDefault(); stopAnimation();
    const wire = state.routing.find(w => w.id === segment.getAttribute("data-wire"));
    state.selectedWire = wire.id; state.wireNotice = ""; segment.focus({ preventScroll: true });
    const matrix = graphElement.getScreenCTM().inverse();
    state.drag = { kind: "wire", wire, index: Number(segment.getAttribute("data-segment")),
      points: wire.points.map(p => ({ ...p })), matrix, start: new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix),
      pointerId: event.pointerId, clientX: event.clientX, clientY: event.clientY, moved: false };
    graphElement.setPointerCapture(event.pointerId); renderSimulation(); return;
  }
  if (!node || event.button === 1) {
    event.preventDefault(); graphElement.focus({ preventScroll: true });
    state.drag = { kind: "pan", pointerId: event.pointerId, camera: { ...state.camera },
      clientX: event.clientX, clientY: event.clientY };
    graphElement.classList.add("panning"); graphElement.setPointerCapture(event.pointerId);
    return;
  }
  event.preventDefault(); stopAnimation();
  const ref = Number(node.getAttribute("data-node"));
  state.selectedWire = null;
  state.selectedRef = ref; node.focus({ preventScroll: true });
  const matrix = graphElement.getScreenCTM().inverse();
  const start = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix);
  state.drag = { kind: "box", ref, pointerId: event.pointerId, start, matrix, origin: { ...state.positions[ref] },
    clientX: event.clientX, clientY: event.clientY, moved: false };
  graphElement.setPointerCapture(event.pointerId);
  renderSimulation();
});
graphElement.addEventListener("pointermove", event => {
  const drag = state.drag;
  if (!drag || event.pointerId !== drag.pointerId) return;
  if (drag.kind === "pan") {
    state.camera = CircuitViewport.pan(drag.camera, event.clientX - drag.clientX, event.clientY - drag.clientY);
    state.cameraTouched = true; renderCamera(); return;
  }
  if (Math.hypot(event.clientX - drag.clientX, event.clientY - drag.clientY) < 5 && !drag.moved) return;
  drag.moved = true;
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(drag.matrix);
  if (drag.kind === "wire") {
    const a = drag.points[drag.index], b = drag.points[drag.index + 1];
    moveWire(drag.wire, drag.index, drag.points, a.x === b.x
      ? { x: a.x + point.x - drag.start.x, y: a.y }
      : { x: a.x, y: a.y + point.y - drag.start.y });
    return;
  }
  if (moveBox(drag.ref, drag.origin.x + point.x - drag.start.x, drag.origin.y + point.y - drag.start.y)) renderSimulation();
});
function finishBoxDrag(event) {
  const drag = state.drag;
  if (!drag || event.pointerId !== drag.pointerId) return;
  state.drag = null;
  graphElement.classList.remove("panning");
  if (graphElement.hasPointerCapture(event.pointerId)) graphElement.releasePointerCapture(event.pointerId);
  if (drag.kind === "pan") return;
  if (drag.kind === "wire") { renderSimulation(); return; }
  if (!drag.moved && event.type === "pointerup" && drag.ref < state.result.circuit.inputs) toggleInput(drag.ref);
  else renderSimulation();
}
graphElement.addEventListener("pointerup", finishBoxDrag);
graphElement.addEventListener("pointercancel", finishBoxDrag);
graphElement.addEventListener("lostpointercapture", finishBoxDrag);
graphElement.addEventListener("auxclick", event => { if (event.button === 1) event.preventDefault(); });
graphElement.addEventListener("wheel", event => {
  // Leave normal scrolling to the page; Ctrl+wheel also covers trackpad pinch.
  if (!event.ctrlKey || !state.camera) return;
  event.preventDefault();
  const rect = graphElement.getBoundingClientRect();
  const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1);
  zoomGraph(state.camera.scale * Math.exp(-Math.max(-300, Math.min(300, delta)) * 0.002),
    { x: event.clientX - rect.left, y: event.clientY - rect.top });
}, { passive: false });
new ResizeObserver(() => renderCamera()).observe(graphElement);
action("zoom-in", () => zoomGraph(state.camera.scale * 1.25));
action("zoom-out", () => zoomGraph(state.camera.scale / 1.25));
action("zoom-reset", () => zoomGraph(1));
action("zoom-fit", fitGraph);
graphElement.addEventListener("keydown", event => {
  if (event.ctrlKey || event.metaKey || event.altKey || !state.camera || state.drag) return;
  if (["+", "=", "-", "0", "f", "F"].includes(event.key)) {
    event.preventDefault();
    if (event.key.toLowerCase() === "f") fitGraph();
    else zoomGraph(event.key === "0" ? 1 : state.camera.scale * (event.key === "-" ? 0.8 : 1.25));
    return;
  }
  const node = event.target.closest("[data-node]");
  const segment = event.target.closest("[data-wire]");
  if (segment) {
    const wire = state.routing.find(w => w.id === segment.getAttribute("data-wire"));
    state.selectedWire = wire.id;
    if (["Delete", "Backspace"].includes(event.key)) { event.preventDefault(); resetWire(); }
    else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault(); stopAnimation();
      const index = Number(segment.getAttribute("data-segment")), a = wire.points[index], delta = event.shiftKey ? 40 : 10;
      moveWire(wire, index, wire.points, { x: a.x + (event.key === "ArrowRight" ? delta : event.key === "ArrowLeft" ? -delta : 0),
        y: a.y + (event.key === "ArrowDown" ? delta : event.key === "ArrowUp" ? -delta : 0) });
    }
    return;
  }
  if (!node) {
    if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      const delta = event.shiftKey ? 160 : 40;
      state.camera = CircuitViewport.pan(state.camera,
        event.key === "ArrowRight" ? -delta : event.key === "ArrowLeft" ? delta : 0,
        event.key === "ArrowDown" ? -delta : event.key === "ArrowUp" ? delta : 0);
      state.cameraTouched = true; renderCamera();
    }
    return;
  }
  const ref = Number(node.getAttribute("data-node"));
  if (["Enter", " "].includes(event.key)) {
    event.preventDefault(); state.selectedRef = ref;
    if (ref < state.result.circuit.inputs) toggleInput(ref); else renderSimulation();
  } else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
    event.preventDefault(); stopAnimation(); state.selectedRef = ref;
    const p = state.positions[ref], delta = event.shiftKey ? 40 : 10;
    if (moveBox(ref, p.x + (event.key === "ArrowRight" ? delta : event.key === "ArrowLeft" ? -delta : 0),
      p.y + (event.key === "ArrowDown" ? delta : event.key === "ArrowUp" ? -delta : 0))) renderSimulation();
  }
});
action("save-layout", async () => {
  const token = state.layoutToken, circuit = state.result.circuit;
  const positions = state.positions.map(p => ({ ...p }));
  const wires = JSON.parse(JSON.stringify(state.wires));
  $("save-layout").disabled = true;
  try {
    await api("/api/layout/save", { circuit, positions, wires });
    if (token !== state.layoutToken) return;
    state.layoutDirty = JSON.stringify(positions) !== JSON.stringify(state.positions) || JSON.stringify(wires) !== JSON.stringify(state.wires);
    $("layout-status").textContent = state.layoutDirty ? "Layout gespeichert. Weitere Änderungen sind noch nicht gespeichert." : "Layout gespeichert · wird beim Öffnen dieser Schaltung wiederhergestellt.";
  } finally { $("save-layout").disabled = false; }
});
action("auto-layout", () => {
  stopAnimation(); state.positions = CircuitGraph.automatic(state.result.circuit);
  state.wires = {}; state.selectedWire = null;
  state.camera = null; state.cameraTouched = false;
  layoutChanged(); renderSimulation();
});

function resetWire() {
  if (!state.selectedWire || !state.wires[state.selectedWire]) return;
  delete state.wires[state.selectedWire]; layoutChanged(); renderSimulation();
}
action("reset-wire", resetWire);

$("task-mode").addEventListener("change", async () => {
  clearError();
  try {
    if ($("task-mode").value === "formula") {
      if (state.formMode === "operation" || state.formMode === "named") await editAsFormula();
      else if (state.formMode !== "formula") newFormula();
      updateDefinition(); return;
    }
    if ($("task-mode").value === "named" && state.formMode === "formula") {
      const { spec } = readPorts();
      const v = await api("/api/formulas/expressions", { formula: $("formula-source").value, result_name: spec.outputs[0]?.name || "c" });
      spec.outputs = Object.keys(v.expression).map(name => spec.outputs.find(p => p.name === name) || { name, bits: 1 });
      editPorts(spec, v.expression);
    }
    else if ($("task-mode").value === "named" && state.formMode === "legacy") editLegacyPorts(int("inputs"), int("outputs"), $("expression").value);
    else if ($("task-mode").value === "named" && state.formMode === "operation") {
      const v = await api("/api/operations/variant", operationRequest()); editPorts(v.interface, v.expression);
    }
    updateDefinition();
  } catch (err) { $("task-mode").value = state.formMode; error(err); }
});
function newFormula() {
  state.autoName = false; $("dataset-name").value = "Eigene Summe"; $("preset").value = "custom";
  editPorts({ inputs: [{ name: "a", bits: 4 }, { name: "b", bits: 4 }], outputs: [{ name: "c", bits: 5 }] });
  $("formula-source").value = "a + b"; $("task-mode").value = "formula"; updateDefinition();
}
async function editAsFormula() {
  let spec, expressions;
  if (state.formMode === "operation") {
    const v = await api("/api/operations/variant", operationRequest()); spec = v.interface; expressions = v.expression;
  } else ({ spec, expressions } = readPorts());
  const converted = await api("/api/formulas/convert", { expression: expressions });
  editPorts(spec, expressions); $("formula-source").value = converted.formula;
  state.autoName = false; $("preset").value = "custom"; $("task-mode").value = "formula"; updateDefinition();
}
async function syncFormula() {
  const { spec } = readPorts();
  const parsed = await api("/api/formulas/parse", { formula: $("formula-source").value, result_name: spec.outputs[0]?.name || "c" });
  spec.outputs = Object.keys(parsed.expression).map(name => spec.outputs.find(p => p.name === name) || { name, bits: 1, overflow: "error" });
  editPorts(spec, parsed.expression); updateDefinition();
  $("formula-status").textContent = `Ergebnisse: ${spec.outputs.map(p => `${p.name}[${p.bits}]`).join(", ")}. Neue Ergebnisports beginnen mit 1 Bit; ihre Breiten sind frei einstellbar.`;
}
action("new-formula", () => { newFormula(); $("formula-source").focus(); });
action("edit-operation-formula", async () => { await editAsFormula(); $("formula-source").focus(); });
action("formula-sync", syncFormula);
action("formula-example", () => {
  newFormula(); $("dataset-name").value = "Summe und Übertrag";
  editPorts({ inputs: [{ name: "a", bits: 4 }, { name: "b", bits: 4 }],
    outputs: [{ name: "c", bits: 4 }, { name: "e", bits: 1 }] });
  $("formula-source").value = "c = mod(a+b,2^4)\ne = div(a+b,2^4)"; updateDefinition();
  $("formula-status").textContent = "a und b: je 4 Bits. c: untere 4 Bits der Summe. e: Übertrag (1 Bit).";
});
$("dataset-name").addEventListener("input", () => { state.autoName = false; });
$("operation").addEventListener("change", () => chooseOperation($("operation").value));
for (const id of ["a-bits", "b-bits", "result-bits", "signed", "overflow", "result-flag", "shift-mode", "shift"]) $(id).addEventListener("input", updateDefinition);
for (const [id, side] of [["add-input-port", "inputs"], ["add-output-port", "outputs"]]) action(id, () => {
  const container = $(side === "inputs" ? "input-ports" : "output-ports");
  container.append(portRow(side, { name: `${side === "inputs" ? "in" : "out"}${container.children.length}`, bits: 1 })); updateDefinition();
});
action("new-width-variant", async () => {
  const result = state.result;
  const ds = result.dataset_id ? await api(`/api/datasets/${result.dataset_id}`) : null;
  const family = ds && Object.entries(state.presets).find(([name, p]) => state.operations[name.toUpperCase()] &&
    p.inputs === ds.inputs && p.outputs === ds.outputs && p.expression === ds.metadata?.expression)?.[0];
  if (ds?.metadata?.operation || ds?.metadata?.interface && (ds.metadata.expression || ds.metadata.reference_circuit)) {
    restoreDefinition(ds);
  } else if (family) {
    chooseOperation(family.toUpperCase()); $("preset").value = family;
  } else if (typeof ds?.metadata?.expression === "string" && !ds.metadata.oracle_file) {
    editLegacyPorts(ds.inputs, ds.outputs, ds.metadata.expression);
    $("preset").value = "custom";
    $("task-mode").value = "named"; updateDefinition();
  } else {
    state.referenceCircuit = result.circuit;
    $("preset").value = "custom";
    editPorts({ inputs: Array.from({ length: result.circuit.inputs }, (_, i) => ({ name: `in${i}`, bits: 1 })),
      outputs: result.circuit.outputs.map((_, i) => ({ name: `out${i}`, bits: 1, overflow: "wrap" })) });
    $("task-mode").value = "circuit"; updateDefinition();
  }
  if ($("task-mode").value === "operation") { state.autoName = true; updateDefinition(); }
  else $("dataset-name").value = `${ds?.name || "NAND"} – Breitenvariante`.slice(0, 120);
  $("variant-description").append(document.createTextNode(" Breiten jetzt anpassen und neue Vektoren erzeugen."));
  $("task-mode").focus(); $("task-mode").scrollIntoView({ block: "center", behavior: "smooth" });
});
async function saveDefinition() {
  if ($("task-mode").value === "formula") await syncFormula();
  updateDefinition();
  const obj = { name: $("dataset-name").value, inputs: int("inputs"), outputs: int("outputs"),
    expression: $("expression").value, samples: int("samples"), seed: int("seed") };
  const mode = $("task-mode").value;
  if (mode === "operation") obj.operation = operationRequest();
  else if (mode === "block") {
    if (!state.referenceBlock) throw new Error("Zuerst einen gespeicherten Unterprogramm-Baustein öffnen.");
    obj.block = state.referenceBlock;
  }
  else if (mode === "named" || mode === "circuit" || mode === "formula") {
    const { spec, expressions } = readPorts(); obj.interface = spec; obj.expression = expressions;
    if (mode === "formula") obj.formula = $("formula-source").value;
    if (mode === "circuit") {
      if (!state.referenceCircuit) throw new Error("Zuerst eine Schaltung öffnen und «Neue Breitenvariante» wählen.");
      obj.reference_circuit = state.referenceCircuit;
    }
  }
  return setDataset(obj);
}
action("generate", saveDefinition);
action("save-formula", saveDefinition);
action("import-rows", () => setDataset({ name: $("dataset-name").value, inputs: int("inputs"), outputs: int("outputs"), rows: JSON.parse($("raw-rows").value) }));
$("import").addEventListener("change", async event => { clearError(); try {
  if (event.target.files[0]) { const obj = JSON.parse(await event.target.files[0].text()); await setDataset(obj.dataset || obj); }
} catch (err) { error(err); } });
action("evolve", async () => {
  if (!state.datasetId) throw new Error("Bitte zuerst Zuordnungsvektoren erzeugen.");
  const config = { gates: int("gates"), population: int("population"), generations: int("generations"), seed: int("seed"), backend: $("backend").value, repair_cases: $("auto-repair").checked ? 4 : 0 };
  $("evolve").disabled = true;
  let job_id;
  try {
    ({ job_id } = await api("/api/search", { dataset_id: state.datasetId, config }));
  } catch (err) { $("evolve").disabled = false; throw err; }
  state.job = job_id; $("cancel-search").disabled = false;
  $("repair-program").disabled = true;
  $("job-status").textContent = "Suche läuft …";
  async function poll() {
    try {
      const job = await api(`/api/jobs/${job_id}`);
      $("job-status").textContent = job.status === "cancelling" ? "Suche wird abgebrochen …" : `Suche läuft · ${job.elapsed_seconds} s`;
      if (job.status === "done") {
        state.job = null; $("evolve").disabled = false; $("cancel-search").disabled = true;
        showProgram(job.result); await refresh();
        const comparison = job.result.comparison;
        if (comparison) {
          const before = comparison.previous_fitness, after = comparison.candidate_fitness;
          $("job-status").textContent = `Retest: bisher ${before.errors}, neu ${after.errors} fehlerhafte Ausgangsbits · ${comparison.accepted ? "Bessere Version übernommen." : "Bisherige Version beibehalten."}`;
        } else $("job-status").textContent = `${verification(job.result.fitness)} · Programm gespeichert.`;
      } else if (job.status === "failed" || job.status === "cancelled") {
        state.job = null; $("evolve").disabled = false; $("cancel-search").disabled = true;
        $("job-status").textContent = job.status === "cancelled" ? "Suche abgebrochen. Bisherige Programme bleiben erhalten." : "Suche fehlgeschlagen.";
        if (job.status === "failed") error(new Error(job.error));
        $("repair-program").disabled = !state.result?.id || !state.result?.fitness?.errors;
      } else setTimeout(poll, 700);
    } catch (err) {
      if (state.job !== job_id) { error(err); return; }
      $("job-status").textContent = "Verbindung zur Suche unterbrochen. Erneuter Versuch …"; error(err);
      setTimeout(poll, 1500);
    }
  }
  setTimeout(poll, 250);
});
action("cancel-search", async () => {
  if (!state.job) return;
  $("cancel-search").disabled = true;
  $("job-status").textContent = "Suche wird abgebrochen …";
  try { await api(`/api/jobs/${state.job}/cancel`, {}); }
  catch (err) { $("cancel-search").disabled = !state.job; throw err; }
});
action("parse", async () => {
  const result = await api("/api/parse", { expression: $("nand-expression").value, inputs: int("nand-inputs") });
  showProgram(result);
});
action("refresh", refresh);
action("repair-program", async () => {
  $("repair-program").disabled = true;
  try {
    const result = await api("/api/repair", { program_id: state.result.id });
    showProgram(result); await refresh();
    $("job-status").textContent = `${verification(result.fitness)} · Beste Version nach Restfallkorrektur geladen.`;
  } finally { $("repair-program").disabled = !state.result?.id || !state.result?.fitness?.errors || Boolean(state.job); }
});
action("export-program", async () => {
  const result = state.result;
  const dataset = result.dataset_id ? await api(`/api/datasets/${result.dataset_id}`) : null;
  download(`${result.id || "nand-programm"}.json`, dataset ? { ...result, dataset } : result);
});

function inspectBlock(bundle) {
  const lines = [];
  function visit(key, path, depth) {
    const d = bundle.definitions[key];
    lines.push(`${"  ".repeat(depth)}${path}: ${d.name} v${d.version} · ${d.interface.inputs.map(p => `${p.name}[${p.bits}]`).join(", ")} → ${d.interface.outputs.map(p => `${p.name}[${p.bits}]`).join(", ")} · ${key.slice(0, 18)}`);
    for (const node of d.nodes || []) if (node.type === "instance") visit(node.definition, node.id, depth + 1);
  }
  visit(bundle.root, "Wurzel", 0);
  $("block-tree").textContent = lines.join("\n"); $("block-tree").hidden = false;
}
async function openBlock(bundle) {
  await setDataset({ block: bundle, samples: int("samples"), seed: int("seed") });
  const expanded = await api("/api/blocks/expand", { block: bundle });
  showProgram({ ...expanded, dataset_id: state.datasetId });
  inspectBlock(bundle);
  $("block-status").textContent = `${bundle.definitions[bundle.root].name} geöffnet. Hierarchie bleibt im JSON-Export erhalten; Schaltbild zeigt ihre NAND-Expansion.`;
}
function prepareBlock(bundle, count) {
  const root = bundle.definitions[bundle.root], inputs = [], outputs = [], nodes = [], mapping = {};
  if (count * root.interface.inputs.reduce((n,p) => n+p.bits, 0) > 32 || count * root.interface.outputs.reduce((n,p) => n+p.bits, 0) > 32) throw new Error("Diese Anzahl Instanzen überschreitet die 32-Bit-Grenze. Ports im eigenen JSON-Entwurf verbinden oder zusammenfassen.");
  for (let i = 0; i < count; i++) {
    const connections = {}, nodeId = `part${i + 1}`;
    root.interface.inputs.forEach((p, j) => {
      const name = count === 1 ? p.name : `in${i + 1}_${j}`;
      inputs.push({ name, bits: p.bits, signed: p.signed });
      connections[p.name] = Array.from({length:p.bits}, (_, bit) => ({input:name, bit}));
    });
    root.interface.outputs.forEach((p, j) => {
      const name = count === 1 ? p.name : `out${i + 1}_${j}`;
      outputs.push({ name, bits: p.bits, signed: p.signed, overflow:p.overflow });
      mapping[name] = Array.from({length:p.bits}, (_, bit) => ({node:nodeId, port:p.name, bit}));
    });
    nodes.push({ id:nodeId, type:"instance", definition:bundle.root, inputs:connections });
  }
  $("block-source").value = JSON.stringify({ definition:{ name:`${root.name} – Unterprogramm`, version:1,
    interface:{inputs, outputs}, nodes, outputs:mapping }, dependencies:[bundle.root] }, null, 2);
  $("block-editor").open = true; inspectBlock(bundle);
  $("block-status").textContent = `${count} Instanz${count === 1 ? "" : "en"} vorbereitet. Namen und Portverbindungen im JSON bearbeiten, dann prüfen und speichern.`;
}
function renderBlocks(blocks) {
  const signature = JSON.stringify(blocks);
  if (signature === state.blockSignature) return;
  state.blockSignature = signature; $("blocks").replaceChildren();
  if (!blocks.length) $("blocks").append(el("p", "Eine Schaltung als Baustein speichern oder ein Bausteinpaket importieren.", "hint"));
  for (const block of blocks) {
    const card = el("div", undefined, "library-entry function-entry");
    card.append(el("strong", `${block.name} · v${block.version}`), el("small", `${block.gates} NAND-Gatter · ${block.instances} direkte Instanzen · ${block.definitions} Definitionen`));
    card.append(el("small", `${block.interface.inputs.map(p => `${p.name}[${p.bits}]`).join(", ")} → ${block.interface.outputs.map(p => `${p.name}[${p.bits}]`).join(", ")}`));
    for (const [label, handler] of [
      ["Baustein öffnen", openBlock], ["Als Unterbaustein einsetzen", b => prepareBlock(b, 1)],
      ["Zweimal einsetzen", b => prepareBlock(b, 2)], ["Bausteinpaket exportieren", b => download(`${block.id}.json`, b)]]) {
      const button = el("button", label, "secondary");
      button.addEventListener("click", async () => { clearError(); try { await handler(await api(`/api/blocks/${block.id}`)); } catch (err) { error(err); } });
      card.append(button);
    }
    $("blocks").append(card);
  }
}
action("save-block", async () => {
  const saved = await api("/api/blocks", JSON.parse($("block-source").value));
  $("block-source").value = JSON.stringify(saved.block, null, 2); inspectBlock(saved.block); await refresh();
  $("block-status").textContent = `${saved.summary.name} v${saved.summary.version} mit ${saved.summary.definitions} Definitionen gespeichert. Kennung: ${saved.summary.id}`;
});
action("save-block-program", async () => {
  const result = state.result;
  if (!result) throw new Error("Zuerst eine NAND-Schaltung öffnen.");
  let request;
  if (result.id) request = {program_id:result.id, name:$("block-name").value};
  else if (result.hierarchy) {
    const root = result.hierarchy.definitions[result.hierarchy.root];
    const refs = root.interface.inputs.map(p => [p.name, Array.from({length:p.bits}, (_,bit) => ({input:p.name, bit}))]);
    request = {definition:{name:$("block-name").value, version:1, interface:root.interface,
      nodes:[{id:"body", type:"instance", definition:result.hierarchy.root, inputs:Object.fromEntries(refs)}],
      outputs:Object.fromEntries(root.interface.outputs.map(p => [p.name, Array.from({length:p.bits}, (_,bit) => ({node:"body", port:p.name, bit}))]))}, dependencies:[result.hierarchy.root]};
  } else {
    const c = result.circuit, ports = compatible() ? state.dataset?.metadata?.interface : null;
    request = {definition:{name:$("block-name").value, version:1, circuit:c, interface:ports || {
      inputs:Array.from({length:c.inputs}, (_,i) => ({name:`in${i}`, bits:1})), outputs:c.outputs.map((_,i) => ({name:`out${i}`, bits:1}))}}};
  }
  const saved = await api("/api/blocks", request); await refresh(); inspectBlock(saved.block);
  $("block-status").textContent = `${saved.summary.name} als feste Version gespeichert.`;
});
$("import-block").addEventListener("change", async event => { clearError(); try {
  if (!event.target.files[0]) return;
  const obj = JSON.parse(await event.target.files[0].text());
  const saved = await api("/api/blocks", obj.hierarchy || obj);
  $("block-source").value = JSON.stringify(saved.block, null, 2); inspectBlock(saved.block); await refresh();
  $("block-status").textContent = `${saved.summary.name} mit allen Unterbausteinen importiert.`;
} catch (err) { error(err); } });
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
setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 5000);

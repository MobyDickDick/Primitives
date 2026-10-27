"use strict";
const $ = id => document.getElementById(id);
const state = { dataset: null, datasetId: null, result: null, bits: [], timer: null, job: null, librarySignature: null,
  positions: [], selectedRef: 0, layoutToken: 0, layoutDirty: false, routing: null, drag: null,
  camera: null, cameraTouched: false, wires: {}, selectedWire: null, wireNotice: "", operations: {}, presets: {}, referenceCircuit: null, formMode: "legacy", autoName: false, functionSignature: null,
  referenceBlock: null, blockSignature: null, debug: null, vectorJob: null };
const svgNS = "http://www.w3.org/2000/svg";
const int = id => Number($(id).value);
const presetLabels = { mul: "MUL(2,2,4)" };

const pageRoutes = { functions: "funktionen", editor: "editor", evolution: "evolution", circuit: "schaltbild", blocks: "bausteine", help: "hilfe" };
function showPage(page, push = true) {
  if (!pageRoutes[page]) page = "functions";
  state.page = page;
  for (const key of Object.keys(pageRoutes)) $(`page-${key}`).hidden = key !== page;
  for (const link of document.querySelectorAll(".page-nav a")) {
    if (link.dataset.page === page) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
  if (push && location.hash !== `#${pageRoutes[page]}`) history.pushState(null, "", `#${pageRoutes[page]}`);
  window.scrollTo(0, 0);
  if (page === "circuit" && state.result) requestAnimationFrame(() => {
    if (!state.cameraTouched) state.camera = CircuitViewport.fit(graphBounds(), graphSize());
    renderCamera();
  });
}
function pageFromHash() {
  const hash = location.hash.slice(1);
  const page = hash.startsWith("hilfe-") ? "help" : Object.keys(pageRoutes).find(key => pageRoutes[key] === hash) || "functions";
  showPage(page, false);
  if (hash.startsWith("hilfe-")) requestAnimationFrame(() => document.getElementById(hash)?.scrollIntoView());
}
function updateContext() {
  const ds = state.dataset;
  const text = ds ? `Geladen: ${ds.name} · ${ds.inputs} → ${ds.outputs} Bits · ${ds.rows.length} Vektoren` : "Keine Funktion geladen. Öffne eine Funktion oder lege im Editor eine neue an.";
  $("active-function").textContent = text;
  $("search-task").textContent = text;
  $("activity-status").textContent = state.vectorJob ? "Vektorerzeugung läuft …" : state.job ? "Evolution läuft …" : "";
}
document.addEventListener("click", event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const page = Object.keys(pageRoutes).find(key => `#${pageRoutes[key]}` === link.getAttribute("href"));
  if (!page) return;
  event.preventDefault(); showPage(page);
  $(`heading-${page}`).focus({ preventScroll: true });
});
window.addEventListener("hashchange", pageFromHash);
window.addEventListener("popstate", pageFromHash);

function portRow(side, port, expression = "0") {
  const row = el("div", undefined, "port-editor"); row.dataset.side = side;
  function field(label, key, value, type = "text") {
    const wrap = el("label", label), input = el("input"); input.type = type; input.value = value;
    input.dataset.field = key;
    if (type === "number") { input.min = 1; input.max = 128; }
    wrap.append(input); row.append(wrap);
    input.addEventListener("input", updateDefinition);
  }
  field(side === "inputs" ? "Eingangsname" : "Ergebnisname", "name", port.name);
  field("Bits", "bits", port.bits, $("task-mode").value === "template" || typeof port.bits === "string" ? "text" : "number");
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
    const width = get("bits").value.trim();
    const port = { name: get("name").value, bits: /^\d+$/.test(width) ? Number(width) : width, signed: get("signed").checked };
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
  const mode = $("task-mode").value, formula = mode === "formula", template = mode === "template", program = mode === "program" || template, named = formula || program || mode === "named" || mode === "circuit";
  $("formula-editor").hidden = !formula;
  $("source-program-editor").hidden = !program;
  $("template-options").hidden = !template;
  $("editor-guide").hidden = formula || program;
  const options = $("named-options"); options.classList.toggle("formula-mode", formula || program);
  if (formula || program) {
    const home = $(program ? "source-program-ports" : "formula-ports");
    if (options.parentNode !== home) home.append(options);
  } else if (options.parentNode !== $("ports-home").parentNode) $("ports-home").after(options);
  $("operation-options").hidden = mode !== "operation"; $("named-options").hidden = !named;
  $("expression").closest("label").hidden = mode !== "legacy";
  $("expression-hint").hidden = mode !== "legacy"; $("mul-hint").hidden = true;
  $("inputs").readOnly = $("outputs").readOnly = mode !== "legacy";
  $("circuit-reference-hint").hidden = mode !== "circuit";
  for (const node of document.querySelectorAll(".port-expression, .remove-port, #add-input-port, #add-output-port")) node.hidden = mode === "circuit";
  if (formula || program) for (const node of document.querySelectorAll(".port-expression")) node.hidden = true;
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
    if (!template) {
      n = spec.inputs.reduce((v, p) => v + p.bits, 0); m = spec.outputs.reduce((v, p) => v + p.bits, 0);
    }
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
  $("variant-description").textContent = description + (template ? " Parameter und Breiten vor dem Speichern prüfen; beim Speichern erfolgt die Prüfung erneut." : mode === "legacy" ? "" : ` Diese Breitenkombination wird als eigene Funktion gespeichert. ${n <= 16 ? `Vollständige Tabelle: ${2 ** n} Eingaben möglich.` : `2^${n} Eingaben: maximal 65536 Vektoren als Stichprobe.`}`);
  state.formMode = mode;
}
function restoreDefinition(ds) {
  $("dataset-name").value = ds.name; $("inputs").value = ds.inputs; $("outputs").value = ds.outputs;
  $("dataset-description").value = ds.metadata?.description || "";
  const meta = ds.metadata || {};
  $("preset").value = meta.operation ? (state.presets[meta.operation.definition.toLowerCase()] ? meta.operation.definition.toLowerCase() : `op:${meta.operation.definition}`) : "custom";
  if (meta.hierarchy) {
    state.referenceBlock = meta.hierarchy; $("task-mode").value = "block"; updateDefinition();
  } else if (meta.operation && state.operations[meta.operation.definition]) chooseOperation(meta.operation.definition, meta.operation.parameters);
  else if (meta.interface) {
    state.referenceCircuit = meta.reference_circuit || null;
    $("task-mode").value = meta.program?.version === 2 ? "template" : meta.program ? "program" : meta.formula ? "formula" : meta.reference_circuit ? "circuit" : "named";
    editPorts(meta.program?.interface || meta.interface, typeof meta.expression === "object" ? meta.expression : { [meta.interface.outputs[0].name]: meta.expression || "0" });
    if (meta.program) {
      if (meta.program.version === 2) {
        $("template-parameters").value = JSON.stringify(meta.program.parameters, null, 2);
        $("template-conditions").value = (meta.program.conditions || []).join("\n");
      }
      $("source-program").value = meta.program.source;
      const example = Object.entries(sourceProgramExamples).find(([, source]) => source.trim() === meta.program.source.trim());
      if (example) $("source-program-example").value = example[0];
      $("samples").value = ds.rows.length; $("seed").value = meta.seed ?? 1;
      $("source-program-steps").value = meta.program.limits.steps;
      $("source-program-iterations").value = meta.program.limits.iterations;
      $("source-program-total").value = meta.program.limits.total_steps;
    }
    if (meta.formula) $("formula-source").value = meta.formula.source;
    updateDefinition();
  } else {
    $("task-mode").value = "legacy";
    if (typeof meta.expression === "string") $("expression").value = meta.expression;
    updateDefinition();
  }
}
function datasetSummary(ds) {
  updateContext();
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
  await acceptDataset(saved);
}
async function acceptDataset(saved) {
  state.dataset = saved.dataset; state.datasetId = saved.id;
  datasetSummary(saved.dataset); restoreDefinition(saved.dataset);
  $("export-dataset").disabled = false;
  renderTable();
  $("editor-save-status").textContent = `„${saved.dataset.name}“ gespeichert. Unter Evolution kannst du jetzt eine Schaltung suchen.`;
  await refresh();
}
async function deleteFunction(functionId, name, count) {
  clearError();
  if (state.job || state.vectorJob) throw new Error("Zum Löschen zuerst den laufenden Auftrag abwarten oder abbrechen.");
  if (!confirm(`Funktion „${name}“ wirklich löschen?\n\nAlle ${count} gespeicherten Vektorsätze und die ausschliesslich dafür gespeicherten Schaltungen werden dauerhaft gelöscht. Separat gespeicherte Bausteine bleiben erhalten.`)) return;
  const deleted = await api(`/api/functions/${functionId}/delete`, {});
  if (deleted.dataset_ids.includes(state.datasetId)) {
    state.dataset = null; state.datasetId = null;
    $("export-dataset").disabled = true;
    $("dataset-summary").textContent = "Funktion gelöscht. Neue Vektoren erzeugen oder eine Funktion öffnen.";
    $("table-info").textContent = "Keine Vektoren geladen.";
  }
  if (state.result && (deleted.program_ids.includes(state.result.id) || deleted.dataset_ids.includes(state.result.dataset_id))) {
    stopAnimation(); state.debug = null; state.result = null; ++state.layoutToken;
    $("block-debug").hidden = true;
    $("program").hidden = true; $("empty").hidden = false;
    for (const id of ["save-block-program", "export-program", "repair-program"]) $(id).disabled = true;
  }
  renderTable();
  $("job-status").textContent = `Funktion „${name}“ gelöscht.`;
  await refresh();
}
function renderFunctions(catalog) {
  const signature = JSON.stringify([catalog.datasets, catalog.programs.map(p => [p.id, p.dataset_id, p.task_id])]);
  if (signature === state.functionSignature) return;
  // Background refreshes must not discard an open metadata form or its draft.
  if ($("library-tree").querySelector(".function-edit[open]")) return;
  state.functionSignature = signature;
  const groups = new Map();
  for (const dataset of catalog.datasets) {
    const key = dataset.function_id || dataset.id;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(dataset);
  }
  $("functions").replaceChildren();
  if (!groups.size) $("functions").append(el("p", "Noch keine Funktion gespeichert. Im Editor eine Vorlage, Formel oder ein Programm wählen und speichern.", "hint"));
  for (const datasets of [...groups.values()].sort((a, b) => a[0].function_name.localeCompare(b[0].function_name))) {
    datasets.sort((a, b) => b.count - a.count || a.id.localeCompare(b.id));
    const first = datasets[0], entry = el("div", undefined, "library-entry function-entry");
    entry.dataset.kind = "function"; entry.dataset.id = first.function_id; entry.dataset.name = first.function_name;
    entry.dataset.search = `${first.function_name} ${first.description || ""} ${first.operation_label || ""}`.toLocaleLowerCase("de");
    const p = first.metadata?.operation?.parameters;
    entry.append(el("strong", first.function_name));
    entry.append(el("p", first.description || "Noch keine Beschreibung.", "function-description"));
    if (first.operation_label) entry.append(el("code", first.operation_label, "function-formula"));
    if (p) entry.append(el("small", `${p.signed ? "Zweierkomplement" : "unsigned"} · ${p.overflow === "wrap" ? "Abschneiden" : "Überlauffehler"}${p.flag ? " · Statusausgang" : ""}`));
    const reference = first.metadata?.formula?.source || first.metadata?.program?.source;
    if (reference) {
      const details = el("details"), summary = el("summary", "Rechenvorschrift anzeigen");
      details.append(summary, el("code", reference, "function-formula")); entry.append(details);
    }
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
        if (implementation) showProgram(implementation, false);
        else {
          state.result = null; $("program").hidden = true; $("empty").hidden = false;
          $("save-block-program").disabled = true;
          $("export-program").disabled = true; $("repair-program").disabled = true; renderTable();
        }
        if (!state.job) $("job-status").textContent = `${ds.function_name} geladen · bereit für die Evolution.`;
        showPage("editor");
      } catch (err) { error(err); }
    });
    const remove = el("button", "Funktion löschen", "danger function-delete");
    remove.setAttribute("aria-label", `Funktion ${first.function_name} löschen`);
    remove.addEventListener("click", async () => {
      remove.disabled = true;
      try { await deleteFunction(first.function_id, first.function_name, datasets.length); }
      catch (err) { error(err); }
      finally { remove.disabled = false; }
    });
    const edit = el("details", undefined, "function-edit"), form = el("form");
    edit.append(el("summary", "Name & Beschreibung"));
    const nameLabel = el("label", "Name"), nameInput = el("input");
    nameInput.value = first.function_name; nameInput.maxLength = 120; nameInput.required = true;
    nameLabel.append(nameInput);
    const descriptionLabel = el("label", "Beschreibung"), description = el("textarea");
    description.value = first.description || ""; description.maxLength = 4000; description.rows = 4;
    descriptionLabel.append(description);
    const save = el("button", "Angaben speichern", "secondary"), cancel = el("button", "Abbrechen", "text-button");
    save.type = "submit"; cancel.type = "button";
    cancel.addEventListener("click", () => { nameInput.value = first.function_name; description.value = first.description || ""; edit.open = false; });
    form.append(nameLabel, descriptionLabel, save, cancel); edit.append(form);
    form.addEventListener("submit", async event => {
      event.preventDefault(); clearError(); save.disabled = true;
      try {
        const updated = await api(`/api/functions/${first.function_id}/details`, { name: nameInput.value, description: description.value });
        if (updated.dataset_ids.includes(state.datasetId)) {
          const previous = state.dataset;
          state.dataset = { ...previous, name: updated.name, metadata: { ...previous.metadata, description: updated.description } };
          if ($("dataset-name").value === previous.name) $("dataset-name").value = updated.name;
          if ($("dataset-description").value === (previous.metadata?.description || "")) $("dataset-description").value = updated.description;
          datasetSummary(state.dataset); renderTable();
        }
        if (state.result && updated.dataset_ids.includes(state.result.dataset_id)) {
          state.result.dataset_name = updated.name;
          state.result.dataset_metadata = { ...state.result.dataset_metadata, description: updated.description };
          $("block-name").value = updated.name;
        }
        edit.open = false; await refresh();
      } catch (err) { error(err); }
      finally { save.disabled = false; }
    });
    const view = el("button", "Schaltung ansehen", "secondary");
    view.disabled = !program();
    select.addEventListener("change", () => { view.disabled = !program(); });
    view.addEventListener("click", async () => {
      try {
        const ds = selected(), data = await api(`/api/datasets/${ds.id}`);
        state.dataset = data; state.datasetId = ds.id; datasetSummary(data); restoreDefinition(data);
        $("export-dataset").disabled = false; showProgram(program());
      } catch (err) { error(err); }
    });
    entry.append(info, button, view, edit, remove); $("functions").append(entry);
  }
  state.functionEntries = [...$("functions").children].filter(entry => entry.classList.contains("function-entry"));
}
function filterFunctions() {
  const query = $("function-search").value.trim().toLocaleLowerCase("de");
  const root = $("library-tree");
  function filter(container, ancestorMatch = false) {
    let count = 0;
    for (const node of container.children) {
      if (node.classList.contains("library-folder")) {
        const match = ancestorMatch || Boolean(query && node.dataset.name.includes(query));
        const visible = filter(node.querySelector(":scope > .folder-children"), match);
        node.hidden = Boolean(query) && !match && !node.dataset.search.includes(query) && visible === 0;
        node.open = query ? !node.hidden : state.folderOpen?.[node.dataset.id] !== false;
        count += visible;
      } else if (node.classList.contains("library-leaf")) {
        node.hidden = !ancestorMatch && !node.dataset.search.includes(query);
        if (!node.hidden) count++;
      }
    }
    return count;
  }
  const count = filter(root), total = root.querySelectorAll(".library-leaf").length;
  $("function-count").textContent = `${count} von ${total} Einträgen · Templates und Funktionen`;
  $("function-no-match").hidden = !query || count > 0 || [...root.querySelectorAll(".library-folder")].some(folder => !folder.hidden);
}
$("function-search").addEventListener("input", filterFunctions);
async function refresh() {
  const catalog = await api("/api/catalog");
  updateContext();
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
  renderLibraryTree(catalog);
  renderBlocks(catalog.blocks || []);
  const signature = JSON.stringify(catalog.programs.map(p => [p.id, p.frozen, p.dataset_name, p.dataset_metadata?.description]));
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
function showProgram(result, navigate = true) {
  if (navigate) showPage("circuit");
  stopAnimation(); state.result = result; state.debug = null; $("block-debug").hidden = true;
  if (result.hierarchy) {
    inspectBlock(result.hierarchy);
    $("block-status").textContent = "Die geöffnete Schaltung enthält die unten gezeigten festen Unterbausteine.";
  } else {
    $("block-tree").hidden = true;
    $("block-status").textContent = "Die geöffnete NAND-Schaltung ist flach. Sie kann als neuer Baustein gespeichert werden.";
  }
  const c = result.circuit;
  $("circuit-source").value = JSON.stringify(c, null, 2);
  $("circuit-edit-status").textContent = result.manual_edit ? "Manueller Entwurf. Zum Aufbewahren JSON exportieren oder unter Bausteine speichern." : "Gatteranschlüsse bearbeiten, dann prüfen und anzeigen.";
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
  $("program-name").textContent = result.fitness ? `${verification(result.fitness)} · ${result.manual_edit ? "Manueller Entwurf" : result.id || "Suchergebnis"}` : result.manual_edit ? "Manueller Entwurf · Struktur geprüft, ohne Sollvektoren." : "Eigenes NAND-Programm · ⊼ steht zwischen den beiden Argumenten.";
  $("repair-program").disabled = !result.id || !result.fitness?.errors || Boolean(state.job);
  $("correction-details").hidden = !result.correction;
  $("correction-cases").replaceChildren();
  if (result.correction) {
    $("correction-summary").textContent = `${result.correction.cases.length} ${result.correction.cases.length === 1 ? "Restfall" : "Restfälle"} exakt korrigiert · ${result.correction.added_gates} zusätzliche NAND-Gatter`;
    for (const c of result.correction.cases) $("correction-cases").append(el("li", `(${c.inputs.join(",")}) → (${c.expected.join(",")}), zuvor (${c.actual.join(",")})`));
  }
  $("notation").textContent = result.expressions ? result.expressions.map((s, i) => `y${i} = ${s}`).join("  ;  ") : "Gatterliste im JSON-Export verfügbar.";
  renderSimulation(); renderTable(); renderHistory();
  if (result.hierarchy) BlockDebug.start(result).catch(error);
}
function simulationCircuit() { return state.debug?.view.circuit || state.result.circuit; }
function depths(c) {
  const d = Array(c.inputs).fill(0);
  for (const [a, b] of c.gates) d.push(1 + Math.max(d[a], d[b]));
  return { d, depth: Math.max(...c.outputs.map(o => d[o])) };
}
function renderSimulation() {
  if (!state.result) return;
  const c = simulationCircuit(), step = int("step");
  const result = evaluate(c, state.bits);
  $("bit-switches").replaceChildren();
  state.bits.forEach((bit, i) => {
    const ports = state.debug?.view.interface || (compatible() && state.dataset.metadata?.interface);
    const port = ports?.inputs?.find(p => p.offset <= i && i < p.offset + p.bits);
    const name = port ? `${port.name}[${i - port.offset}]` : String(i + 1);
    const button = el("button", `${name}: ${bit}`, bit ? "on" : "");
    button.setAttribute("aria-label", `Eingang ${name}: ${bit}`);
    button.setAttribute("aria-pressed", String(Boolean(bit)));
    button.addEventListener("click", () => toggleInput(i));
    $("bit-switches").append(button);
  });
  const ready = ref => ref < c.inputs + step;
  BlockDebug.render(result.wires, ready);
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
    const source = list[wire.source].signalRefs?.[wire.sourceBit || 0] ?? wire.source;
    const known = ready(source), bit = result.wires[source];
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
    const signal = node.signalRefs?.[0] ?? (kind === "output" ? sources[0] : ref), known = (node.signalRefs || [signal]).every(ready), bit = result.wires[signal];
    const heading = `Box ${ref} · ${kind === "input" ? `Eingang ${node.label || index + 1}` : kind === "gate" ? "NAND" : kind === "instance" ? `${node.id} · v${node.version}` : `Ausgang ${node.label || `y${index}`}`}`;
    const formula = kind === "gate" ? `Box ${sources[0]} ⊼ Box ${sources[1]}` : kind === "output" ? `von Box ${sources[0]}` : "Klicken: 0 ↔ 1";
    const description = kind === "instance" ? `${heading}: ${node.name}. Zum lokalen Handtest öffnen.` : kind === "gate" ? `Box ${ref}: Box ${sources[0]} NAND mit Box ${sources[1]} verknüpft. Wert: ${valueAt(signal)}.` : `${heading}. Wert: ${valueAt(signal)}. ${kind === "input" ? "Zum Umschalten anklicken." : formula}`;
    const group = svg("g", { "data-node": ref, class: `graph-node ${kind}${ref === state.selectedRef ? " selected" : ""}`, tabindex: 0, role: "button", "aria-label": description });
    if (kind === "input") group.setAttribute("aria-pressed", String(Boolean(bit)));
    group.append(svg("title", {}, `${description} Zum Verschieben ziehen oder Pfeiltasten verwenden.`));
    const height = CircuitGraph.boxHeight(positions[ref]);
    group.append(svg("rect", { x, y: y - height / 2, width: CircuitGraph.width, height, rx: kind === "input" ? 24 : 9,
      fill: !known ? "#f3f5f0" : bit ? "#d6ed95" : "#fff", stroke: ref === state.selectedRef ? "#146653" : "#98b397", "stroke-width": ref === state.selectedRef ? 2 : 1 }));
    const text = (offset, content, className) => svg("text", { x: x + CircuitGraph.width / 2, y: y + offset, "text-anchor": "middle", class: className, fill: known ? "#183e31" : "#758575" }, content);
    if (kind === "instance") {
      group.append(text(-height / 2 + 14, heading, "node-heading"));
      const name = text(height / 2 - 6, node.name.length > 28 ? `${node.name.slice(0, 27)}…` : node.name, "node-heading");
      name.append(svg("title", {}, node.name)); group.append(name);
      for (const side of ["inputs", "outputs"]) {
        const refs = side === "inputs" ? node.inputRefs : node.signalRefs;
        for (const p of node.interface[side]) for (let i = 0; i < p.bits; i++) {
          const slot = p.offset + i, offset = CircuitGraph.pinOffset(refs.length, slot);
          const label = `${p.name}[${i}]/${p.bits}=${valueAt(refs[slot])}`;
          const portText = svg("text", { x: side === "inputs" ? x + 5 : x + CircuitGraph.width - 5,
            y: y + offset + 3, "text-anchor": side === "inputs" ? "start" : "end", class: "node-port" },
            label.length > 17 ? `${p.name.slice(0, 6)}…[${i}]=${valueAt(refs[slot])}` : label);
          portText.append(svg("title", {}, `${label} · ${p.signed ? "Zweierkomplement" : "unsigned"}`)); group.append(portText);
        }
      }
    } else group.append(text(-19, heading, "node-heading"), text(3, formula, "node-formula"), text(25, `Wert: ${valueAt(signal)}`, "node-value"));
    graph.append(group);
  });
  const selected = list[state.selectedRef];
  if (selected) {
    const signal = selected.signalRefs?.[0] ?? (selected.kind === "output" ? selected.sources[0] : selected.ref);
    $("box-description").textContent = selected.kind === "instance" ? `${selected.id}: ${selected.name} v${selected.version}. Ports: ${["inputs", "outputs"].map(side => selected.interface[side].map(p => `${p.name}[${p.bits}]`).join(", ")).join(" → ")}. Anklicken oder Enter öffnet die interne Schaltung für einen getrennten lokalen Handtest.` : selected.kind === "gate"
      ? `Box ${selected.ref}: Box ${selected.sources[0]} NAND mit Box ${selected.sources[1]} verknüpft. Aktuell: ${(selected.inputRefs || selected.sources).map(valueAt).join(" ⊼ ")} = ${valueAt(signal)}. NAND liefert nur bei zwei Einsen eine 0.`
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
  const height = state.positions[ref].height;
  const point = { x: Math.max(20, Math.min(99000, x)), y: Math.max((height || CircuitGraph.height) / 2 + 20, Math.min(99000, y)), ...(height ? { height } : {}) };
  if (!CircuitGraph.canPlace(state.positions, ref, point)) return false;
  state.positions[ref] = point; layoutChanged(); return true;
}
function graphSize() {
  const rect = $("graph").getBoundingClientRect();
  return { width: Math.max(1, rect.width), height: Math.max(1, rect.height) };
}
function graphBounds() {
  const points = state.positions.flatMap(p => [{ x: p.x, y: p.y - CircuitGraph.boxHeight(p) / 2 },
    { x: p.x + CircuitGraph.width, y: p.y + CircuitGraph.boxHeight(p) / 2 }]);
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
  $("table-info").textContent = `${ds.name} · ${ds.rows.length} Vektoren${ds.rows.length > 128 ? " · die ersten 128 werden angezeigt" : ""} · ${ds.exhaustive ? "alle Eingaben" : "Stichprobe"}${state.result && !matches ? " · Programm und Datensatz haben verschiedene Bitbreiten" : ""}. ${state.debug?.path.length ? "Gesamtschaltung: Für Vektortests zuerst zur Wurzel zurückkehren." : "Zeile anklicken zum Testen."}`;
  for (const row of ds.rows.slice(0, 128)) {
    const tr = el("tr"), input = row.slice(0, ds.inputs), output = row.slice(ds.inputs);
    const actual = matches ? evaluate(state.result.circuit, input).outputs : null;
    const ok = actual && actual.every((v, i) => v === output[i]);
    tr.append(el("td", input.join(" ")), el("td", output.join(" ")), el("td", actual ? actual.join(" ") : "–"), el("td", actual ? ok ? "✓" : "✕" : "–", actual ? ok ? "ok" : "bad" : ""));
    if (state.result && !state.debug?.path.length && state.result.circuit.inputs === ds.inputs) tr.addEventListener("click", () => {
      stopAnimation(); state.bits = input; $("step").value = state.result.circuit.gates.length; renderSimulation();
    });
    $("vectors").append(tr);
  }
}
function renderHistory() {
  const target = $("history"), search = state.result.search;
  renderAncestry(search?.ancestry);
  target.replaceChildren();
  $("phase-summary").hidden = true;
  $("phase-summary").textContent = "";
  if (!search) { $("search-summary").textContent = state.result.synthesis ? "Konventionell aus festen Bit-Stufen nach NAND übersetzt; kein evolutionärer Suchlauf. Prüfstatus siehe oben." : "Für ein eingegebenes Programm gibt es keinen Suchverlauf."; return; }
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
  if (search.diversity) {
    const d = search.diversity;
    $("search-summary").textContent += ` · ${search.restarts_completed}/${search.restarts} Starts · ${search.islands} Inseln · Diversität der letzten Population: ${d.unique_genomes}/${d.size} unterschiedliche Genome (${Math.round(d.unique_fraction * 100)} %) · mittlere Gendifferenz ${(d.mean_hamming * 100).toFixed(1)} %`;
  }
  if (search.neutral && search.phases?.length === 2) {
    const phase = search.phases[1];
    $("phase-summary").hidden = false;
    $("phase-summary").textContent = `Phase 1: neutrale Evolution (${search.phases[0].result.errors} falsche Bits) · Phase 2: Vereinfachung ${phase.before.gates} → ${phase.result.gates} Gatter, Tiefe ${phase.before.depth} → ${phase.result.depth} (vor einer allfälligen Restfallkorrektur)`;
  }
}

function renderAncestry(ancestry) {
  $("ancestry-panel").hidden = !ancestry;
  $("ancestry-nodes").replaceChildren();
  $("ancestry-summary").textContent = "";
  if (!ancestry) return;
  const operators = { random: "Zufall", library: "Bibliothekskomposition", incumbent: "Bisherige Lösung" };
  const transformations = { compact: "Kompaktierung", simplification: "Vereinfachung", repair: "Restfallkorrektur", incumbent_selection: "Auswahl der bisherigen Lösung" };
  $("ancestry-summary").textContent = `Bester Suchkandidat #${ancestry.root} · ${ancestry.nodes.length} Kandidaten einschliesslich Vorfahren · ${Object.keys(ancestry.sources).length} konkret eingesetzte Quellen · Danach: ${ancestry.transformations.map(t => transformations[t.operation] || t.operation).join(" → ")}`;
  for (const node of ancestry.nodes.slice(-100).reverse()) {
    const row = document.createElement("tr");
    const origin = node.operator === "variation"
      ? `${node.parents.length > 1 ? "Rekombination" : "Kopie"} · Mutationsstellen: ${node.mutation_genes.length} · Genänderungen: ${node.changes.length}`
      : `${operators[node.operator] || node.operator}${node.origin.seeds?.length ? ": " + node.origin.seeds.map(s => s.source).join(", ") : ""}`;
    for (const value of [`#${node.id}`, node.parents.map(id => `#${id}`).join(", ") || "—", origin,
      `Start ${node.restart + 1} · Insel ${node.island + 1} · Gen ${node.generation}`]) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    $("ancestry-nodes").append(row);
  }
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
  if (!drag.moved && event.type === "pointerup") activateNode(drag.ref);
  else renderSimulation();
}
function activateNode(ref) {
  const node = CircuitGraph.nodes(simulationCircuit())[ref];
  if (node.kind === "input") toggleInput(ref);
  else if (node.kind === "instance") BlockDebug.enter(node).catch(error);
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
    activateNode(ref);
  } else if (["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
    event.preventDefault(); stopAnimation(); state.selectedRef = ref;
    const p = state.positions[ref], delta = event.shiftKey ? 40 : 10;
    if (moveBox(ref, p.x + (event.key === "ArrowRight" ? delta : event.key === "ArrowLeft" ? -delta : 0),
      p.y + (event.key === "ArrowDown" ? delta : event.key === "ArrowUp" ? -delta : 0))) renderSimulation();
  }
});
action("save-layout", async () => {
  const token = state.layoutToken, circuit = simulationCircuit();
  const positions = state.positions.map(p => ({ x: p.x, y: p.y }));
  const wires = JSON.parse(JSON.stringify(state.wires));
  $("save-layout").disabled = true;
  try {
    await api(state.debug ? "/api/blocks/layout/save" : "/api/layout/save",
      { ...(state.debug ? BlockDebug.request() : { circuit }), positions, wires });
    if (token !== state.layoutToken) return;
    state.layoutDirty = JSON.stringify(positions) !== JSON.stringify(state.positions.map(p => ({ x: p.x, y: p.y }))) || JSON.stringify(wires) !== JSON.stringify(state.wires);
    $("layout-status").textContent = state.layoutDirty ? "Layout gespeichert. Weitere Änderungen sind noch nicht gespeichert." : "Layout gespeichert · wird beim Öffnen dieser Schaltung wiederhergestellt.";
  } finally { $("save-layout").disabled = false; }
});
action("auto-layout", () => {
  stopAnimation(); state.positions = CircuitGraph.automatic(simulationCircuit());
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
    if ($("task-mode").value === "template") { newTemplate(); return; }
    if ($("task-mode").value === "program") {
      if (state.formMode !== "program") newSourceProgram();
      updateDefinition(); return;
    }
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
  showPage("editor"); $("dataset-description").value = "";
  state.autoName = false; $("dataset-name").value = "Eigene Summe"; $("preset").value = "custom";
  editPorts({ inputs: [{ name: "a", bits: 4 }, { name: "b", bits: 4 }], outputs: [{ name: "c", bits: 5 }] });
  $("formula-source").value = "a + b"; $("task-mode").value = "formula"; updateDefinition();
}
async function editAsFormula() {
  showPage("editor");
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
  showPage("editor");
  const result = state.result;
  const ds = result.dataset_id ? await api(`/api/datasets/${result.dataset_id}`) : null;
  const family = ds && Object.entries(state.presets).find(([name, p]) => state.operations[name.toUpperCase()] &&
    p.inputs === ds.inputs && p.outputs === ds.outputs && p.expression === ds.metadata?.expression)?.[0];
  if (ds?.metadata?.operation || ds?.metadata?.interface && (ds.metadata.expression || ds.metadata.reference_circuit || ds.metadata.program)) {
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
  if (state.vectorJob) throw new Error("Die Vektorerzeugung läuft bereits. Bitte abwarten oder abbrechen.");
  if ($("task-mode").value === "formula") await syncFormula();
  updateDefinition();
  const obj = { name: $("dataset-name").value, description: $("dataset-description").value, inputs: int("inputs"), outputs: int("outputs"),
    expression: $("expression").value, samples: int("samples"), seed: int("seed") };
  const mode = $("task-mode").value;
  if (mode === "operation") obj.operation = operationRequest();
  else if (mode === "block") {
    if (!state.referenceBlock) throw new Error("Zuerst einen gespeicherten Unterprogramm-Baustein öffnen.");
    obj.block = state.referenceBlock;
  }
  else if (mode === "named" || mode === "circuit" || mode === "formula" || mode === "program" || mode === "template") {
    const { spec, expressions } = readPorts(); obj.interface = spec; obj.expression = expressions;
    if (mode === "program" || mode === "template") {
      delete obj.expression;
      obj.program = readSourceProgram();
      if (mode === "template") Object.assign(obj, await specializeTemplate());
      return generateProgramVectors(obj);
    }
    if (mode === "formula") obj.formula = $("formula-source").value;
    if (mode === "circuit") {
      if (!state.referenceCircuit) throw new Error("Zuerst eine Schaltung öffnen und «Neue Breitenvariante» wählen.");
      obj.reference_circuit = state.referenceCircuit;
    }
  }
  return setDataset(obj);
}
const sourceProgramExamples = {
  for: "s = 0\nfor i in range(n):\n    s += i\nreturn s",
  while: "s = 0\ni = 0\nwhile i < n:\n    s += i\n    i += 1\nreturn s",
  if: "if n < 8:\n    if n == 0:\n        c = 1\n    else:\n        c = n * 2\nelse:\n    c = n - 1\nreturn c",
  bits: "# Vier Eingangsbits in umgekehrter Reihenfolge ausgeben\na = bits(n, 4)  # Index 0 ist das niederwertigste Bit\nreturn pack(a[::-1])",
  jump: 's = 0\ni = 0\nlabel("loop")\njump_if(i >= n, "done")\ns += i\ni += 1\ngoto("loop")\nlabel("done")\nreturn s',
  zero: 'jump_zero(n, "zero")\nreturn n\nlabel("zero")\nreturn 42'
};
const recursiveAdderSource = `# Addition zweier n-Bit-Zahlen, Ergebnis mit Übertrag
# w ist die Bitbreite; Basisfall: ein Bit.
def obereHaelfte<k>(a):
    return a // (2 ** k)

def untereHaelfte<k>(a):
    return a % (2 ** k)

def add<w>(a, b):
    assert w > 0 and (w & (w - 1)) == 0
    assert 0 <= a < 2 ** w and 0 <= b < 2 ** w
    if w == 1:
        return 2 * (a & b) + xor(a, b)
    k = w // 2
    a1 = obereHaelfte<k>(a)
    a2 = untereHaelfte<k>(a)
    b1 = obereHaelfte<k>(b)
    b2 = untereHaelfte<k>(b)
    c0 = add<w - k>(a1, b1)
    c1 = c0 + 1
    d0 = add<k>(a2, b2)
    rest = d0 % (2 ** k)
    carry = d0 // (2 ** k)
    if carry == 0:
        return c0 * (2 ** k) + rest
    else:
        return c1 * (2 ** k) + rest

return add<n>(a, b)`;
function readSourceProgram() {
  const program = { version: 1, source: $("source-program").value, limits: {
    steps: int("source-program-steps"), iterations: int("source-program-iterations"), total_steps: int("source-program-total") } };
  if ($("task-mode").value === "template") Object.assign(program, {
    version: 2, parameters: JSON.parse($("template-parameters").value), interface: readPorts().spec,
    conditions: $("template-conditions").value.split("\n").map(s => s.trim()).filter(Boolean)
  });
  return program;
}
async function specializeTemplate() {
  const result = await api("/api/templates/specialize", { program: readSourceProgram() });
  $("inputs").value = result.inputs; $("outputs").value = result.outputs;
  let call = result.program.source.split("\n").findLast(line => line.startsWith("return "))?.slice(7) || "";
  for (const [name, value] of Object.entries(result.program.parameters)) call = call.replace(new RegExp(`\\b${name}\\b`, "g"), String(value));
  $("template-status").textContent = `${call ? `Konkreter Aufruf: ${call} · ` : ""}${Object.entries(result.program.parameters).map(([k,v]) => `${k}=${v}`).join(", ")} · Bedingungen erfüllt · ${result.inputs} → ${result.outputs} Bits · ${result.inputs <= 16 ? `${2 ** result.inputs} Eingaben für eine vollständige Tabelle` : "Stichprobe (mehr als 65536 Eingaben)"}.`;
  return result;
}
function newTemplate() {
  showPage("editor"); state.autoName = false; $("preset").value = "custom";
  $("task-mode").value = "template";
  $("dataset-name").value = "Rekursiver Addierer";
  $("dataset-description").value = "Addiert zwei n-Bit-Zahlen durch rekursive Halbierung. n muss eine Zweierpotenz sein; das Ergebnis hat n+1 Bits.";
  $("template-parameters").value = '{"n": 4}';
  $("template-conditions").value = "n >= 1\nis_power_of_two(n)";
  $("inputs").value = 8; $("outputs").value = 5;
  editPorts({inputs: [{name: "a", bits: "n"}, {name: "b", bits: "n"}], outputs: [{name: "c", bits: "n+1"}]});
  $("source-program").value = recursiveAdderSource;
  $("source-program-steps").value = 10000; $("source-program-iterations").value = 10000;
  $("source-program-total").value = 1000000;
  $("template-status").textContent = "n=4 vorbereitet. Parameter und Breiten prüfen oder direkt speichern.";
  updateDefinition();
}
action("new-template", newTemplate);
action("specialize-template", specializeTemplate);
$("template-parameters").addEventListener("input", () => { $("template-status").textContent = "Parameter geändert. Breiten erneut prüfen oder speichern."; });
$("template-conditions").addEventListener("input", () => { $("template-status").textContent = "Bedingungen geändert. Konkretisierung erneut prüfen oder speichern."; });
function abstractTemplate() {
  const spec = readSourceProgram();
  return { schema: 1, kind: "template", name: $("dataset-name").value, description: $("dataset-description").value,
    parameters: Object.keys(spec.parameters), interface: spec.interface, source: spec.source, limits: spec.limits,
    conditions: spec.conditions };
}
function openTemplate(doc) {
  showPage("editor"); $("task-mode").value = "template"; state.autoName = false; $("preset").value = "custom";
  $("dataset-name").value = doc.name; $("dataset-description").value = doc.description;
  $("template-parameters").value = JSON.stringify(Object.fromEntries(doc.parameters.map(name => [name, 1])), null, 2);
  $("template-conditions").value = doc.conditions.join("\n");
  $("source-program").value = doc.source;
  $("source-program-steps").value = doc.limits.steps; $("source-program-iterations").value = doc.limits.iterations;
  $("source-program-total").value = doc.limits.total_steps;
  editPorts(doc.interface); updateDefinition();
  $("template-status").textContent = "Abstraktes Template geöffnet. Für die Konkretisierung Parameterwerte setzen, dann prüfen oder Vektoren erzeugen.";
}
function renderTemplates(templates) {
  const signature = JSON.stringify(templates);
  if (signature === state.templateSignature) return;
  state.templateSignature = signature; $("templates").replaceChildren();
  if (!templates.length) $("templates").append(el("p", "Noch keine abstrakten Templates gespeichert.", "hint"));
  for (const doc of templates) {
    const card = el("div", undefined, "library-entry function-entry template-entry");
    card.dataset.kind = "template"; card.dataset.id = doc.id; card.dataset.name = doc.name;
    card.dataset.search = `${doc.name} ${doc.description} ${doc.conditions.join(" ")}`.toLocaleLowerCase("de");
    card.append(el("strong", `${doc.name}<${doc.parameters.join(", ")}>`), el("small", doc.description),
      el("small", doc.conditions.length ? `Bedingungen: ${doc.conditions.join("; ")}` : "Keine zusätzlichen Parameterbedingungen."));
    const open = el("button", "Template öffnen & konkretisieren", "secondary");
    open.addEventListener("click", () => openTemplate(doc)); card.append(open);
    const exportButton = el("button", "Template exportieren", "secondary");
    exportButton.addEventListener("click", () => { const { id, ...document } = doc; download(`${doc.name}.template.json`, document); });
    card.append(exportButton);
    $("templates").append(card);
  }
  state.templateEntries = [...$("templates").children].filter(entry => entry.classList.contains("template-entry"));
}

function folderChoices(tree, selected, includeRoot = false, exclude = null) {
  const select = el("select");
  if (includeRoot) select.add(new Option("Bibliothek (oberste Ebene)", ""));
  const folders = new Map(tree.folders.map(folder => [folder.id, folder]));
  const path = folder => folder.parent ? `${path(folders.get(folder.parent))} / ${folder.name}` : folder.name;
  function below(folder) { return folder.id === exclude || Boolean(folder.parent && below(folders.get(folder.parent))); }
  for (const folder of [...folders.values()].filter(folder => !below(folder)).sort((a, b) => path(a).localeCompare(path(b), "de"))) {
    select.add(new Option(path(folder), folder.id));
  }
  select.value = selected || "";
  return select;
}
function folderEditor(tree, folder = null, parent = null) {
  const details = el("details", undefined, "library-edit folder-editor");
  details.append(el("summary", folder ? "Ordner bearbeiten" : parent ? "Unterordner anlegen" : "Ordner anlegen"));
  const form = el("form"), nameLabel = el("label", "Ordnername"), name = el("input");
  name.required = true; name.maxLength = 120; name.value = folder?.name || ""; nameLabel.append(name);
  const descriptionLabel = el("label", "Beschreibung"), description = el("textarea");
  description.maxLength = 4000; description.rows = 3; description.value = folder?.description || ""; descriptionLabel.append(description);
  const parentLabel = el("label", "Übergeordneter Ordner"), select = folderChoices(tree, folder ? folder.parent : parent, true, folder?.id);
  select.setAttribute("aria-label", "Übergeordneter Ordner");
  parentLabel.append(select);
  const save = el("button", folder ? "Ordner speichern" : "Ordner anlegen", "secondary"); save.type = "submit";
  const cancel = el("button", "Abbrechen", "text-button"); cancel.type = "button";
  cancel.addEventListener("click", () => { name.value = folder?.name || ""; description.value = folder?.description || ""; select.value = (folder ? folder.parent : parent) || ""; details.open = false; });
  form.append(nameLabel, descriptionLabel, parentLabel, save, cancel); details.append(form);
  form.addEventListener("submit", async event => {
    event.preventDefault(); clearError(); save.disabled = true;
    try {
      await api("/api/library/folders", { id: folder?.id, name: name.value, description: description.value, parent: select.value || null });
      if (select.value) state.folderOpen[select.value] = true;
      details.open = false; await refresh();
    } catch (err) { error(err); } finally { save.disabled = false; }
  });
  if (folder && !["functions", "templates"].includes(folder.id)) {
    const remove = el("button", "Leeren Ordner löschen", "text-button"); remove.type = "button";
    remove.disabled = tree.folders.some(f => f.parent === folder.id) || Object.values(tree.entries).includes(folder.id);
    remove.addEventListener("click", async () => {
      clearError();
      try { await api("/api/library/folders/delete", { id: folder.id }); details.open = false; await refresh(); }
      catch (err) { error(err); }
    });
    form.append(remove);
  }
  return details;
}
function entryFolderEditor(tree, entry) {
  entry.querySelector(".entry-folder-editor")?.remove();
  const details = el("details", undefined, "library-edit entry-folder-editor"); details.append(el("summary", "In Ordner verschieben"));
  const form = el("form"), label = el("label", "Zielordner"), key = `${entry.dataset.kind}:${entry.dataset.id}`;
  const select = folderChoices(tree, tree.entries[key]); label.append(select);
  select.setAttribute("aria-label", "Zielordner");
  const save = el("button", "Verschieben", "secondary"); save.type = "submit";
  form.append(label, save); details.append(form); entry.append(details);
  form.addEventListener("submit", async event => {
    event.preventDefault(); clearError(); save.disabled = true;
    try {
      await api("/api/library/move", { kind: entry.dataset.kind, id: entry.dataset.id, folder: select.value });
      state.folderOpen[select.value] = true; details.open = false; await refresh();
    } catch (err) { error(err); } finally { save.disabled = false; }
  });
}
function renderLibraryTree(catalog) {
  const root = $("library-tree");
  if (document.querySelector(".library-edit[open], .function-edit[open]")) return;
  const signature = JSON.stringify([catalog.tree, catalog.datasets, catalog.templates, catalog.programs.map(p => [p.id, p.dataset_id, p.task_id])]);
  if (signature === state.treeSignature) return;
  state.treeSignature = signature;
  state.folderOpen ||= {}; state.leafOpen ||= {};
  renderFunctions(catalog); renderTemplates(catalog.templates || []);
  root.replaceChildren();
  const tree = catalog.tree;
  if (!tree) { root.append(el("p", "Für den Verzeichnisbaum den lokalen Webserver neu starten.", "hint")); return; }
  $("folder-create").replaceChildren(folderEditor(tree));
  const entries = [...(state.functionEntries || []), ...(state.templateEntries || [])];
  function append(parent, container) {
    const folders = tree.folders.filter(f => f.parent === parent).sort((a, b) => a.name.localeCompare(b.name, "de"));
    for (const folder of folders) {
      const branch = el("details", undefined, "library-folder"); branch.dataset.id = folder.id;
      branch.dataset.name = folder.name.toLocaleLowerCase("de");
      branch.dataset.search = `${folder.name} ${folder.description}`.toLocaleLowerCase("de");
      branch.open = state.folderOpen[folder.id] !== false;
      const summary = el("summary"); summary.append(el("span", folder.name, "folder-name"));
      summary.addEventListener("click", () => { state.folderOpen[folder.id] = !branch.open; });
      branch.append(summary, el("p", folder.description || "Noch keine Beschreibung.", "folder-description"));
      const tools = el("div", undefined, "folder-tools"); tools.append(folderEditor(tree, folder), folderEditor(tree, null, folder.id)); branch.append(tools);
      const children = el("div", undefined, "folder-children"); append(folder.id, children);
      if (!children.children.length) children.append(el("p", "Leerer Ordner. Einträge lassen sich über „In Ordner verschieben“ hier ablegen.", "hint"));
      branch.append(children); container.append(branch);
    }
    for (const entry of entries.filter(entry => tree.entries[`${entry.dataset.kind}:${entry.dataset.id}`] === parent)
      .sort((a, b) => a.dataset.name.localeCompare(b.dataset.name, "de"))) {
      const key = `${entry.dataset.kind}:${entry.dataset.id}`, leaf = el("details", undefined, "library-leaf");
      leaf.dataset.search = entry.dataset.search; leaf.open = Boolean(state.leafOpen[key]);
      const summary = el("summary"); summary.append(el("span", entry.dataset.name), el("span", entry.dataset.kind === "template" ? "Template" : "Funktion", "badge"));
      summary.addEventListener("click", () => { state.leafOpen[key] = !leaf.open; });
      entryFolderEditor(tree, entry); leaf.append(summary, entry); container.append(leaf);
    }
  }
  append(null, root); filterFunctions();
}
action("save-template", async () => {
  const result = await api("/api/templates", abstractTemplate());
  $("template-status").textContent = `Abstraktes Template „${result.template.name}“ gespeichert. Dabei wurden keine konkrete Funktion und keine Vektoren erzeugt.`;
  await refresh();
});
action("export-template", () => download("abstraktes-template.json", abstractTemplate()));
action("synthesize-template", async () => {
  if (state.job || state.vectorJob) throw new Error("Zum Übersetzen zuerst den laufenden Auftrag abwarten oder abbrechen.");
  const button = $("synthesize-template"); button.disabled = true;
  $("template-status").textContent = "Feste Bit-Stufen nach NAND übersetzen und mit Referenzvektoren prüfen …";
  try {
    const result = await api("/api/templates/synthesize", { program: readSourceProgram(), name: $("dataset-name").value,
      description: $("dataset-description").value, samples: int("samples"), seed: int("seed") });
    await acceptDataset(result); showProgram(result.result);
    $("template-status").textContent = `NAND-Schaltung gespeichert: ${result.result.fitness.gates} Gatter. ${verification(result.result.fitness)}.`;
  } finally { button.disabled = false; }
});
$("import-template").addEventListener("change", async event => {
  clearError();
  try {
    if (!event.target.files[0]) return;
    const saved = await api("/api/templates", JSON.parse(await event.target.files[0].text()));
    openTemplate(saved.template); await refresh();
  } catch (err) { error(err); }
  finally { event.target.value = ""; }
});
function newSourceProgram() {
  showPage("editor"); $("dataset-description").value = "";
  state.autoName = false; $("preset").value = "custom";
  const example = $("source-program-example").value;
  $("dataset-name").value = example === "bits" ? "Bitreihenfolge umkehren" : example === "if" ? "Auswahl mit if/else" : example === "zero" ? "Auswahl mit Zero-Sprung" : example === "jump" ? "Summe mit Rücksprung" : `Summe mit ${example}`;
  editPorts({ inputs: [{ name: "n", bits: 4 }], outputs: [{ name: "c", bits: 8 }] });
  $("source-program").value = sourceProgramExamples[example];
  $("task-mode").value = "program"; updateDefinition();
}
function vectorControls(busy) {
  updateContext();
  for (const id of ["generate", "save-source-program", "save-formula"]) $(id).disabled = busy;
  $("evolve").disabled = busy || Boolean(state.job);
  $("cancel-vectors").disabled = !busy;
}
async function generateProgramVectors(obj) {
  if (state.job) throw new Error("Eine Suche läuft. Bitte zuerst abwarten oder abbrechen.");
  state.vectorJob = "starting"; vectorControls(true);
  $("vector-job-status").textContent = "Vektorerzeugung wird gestartet …";
  let job_id;
  try { ({ job_id } = await api("/api/datasets/generate", obj)); }
  catch (err) { state.vectorJob = null; vectorControls(false); throw err; }
  state.vectorJob = job_id;
  async function poll() {
    let job;
    try { job = await api(`/api/jobs/${job_id}`); }
    catch (err) {
      $("vector-job-status").textContent = "Verbindung zur Vektorerzeugung unterbrochen. Erneuter Versuch …";
      setTimeout(poll, 1500); return;
    }
    $("vector-job-status").textContent = job.status === "cancelling" ? "Vektorerzeugung wird abgebrochen …" : `Vektorerzeugung läuft · ${job.elapsed_seconds} s`;
    if (["done", "failed", "cancelled"].includes(job.status)) {
      state.vectorJob = null; vectorControls(false);
      if (job.status === "done") {
        $("vector-job-status").textContent = "Programm und Vektoren gespeichert.";
        try { await acceptDataset(job.result); } catch (err) { error(err); }
      } else {
        $("vector-job-status").textContent = job.status === "cancelled" ? "Vektorerzeugung abgebrochen; kein Datensatz gespeichert." : "Vektorerzeugung fehlgeschlagen; kein Datensatz gespeichert.";
        if (job.status === "failed") error(new Error(job.error));
      }
    } else setTimeout(poll, 200);
  }
  setTimeout(poll, 100);
}
action("new-source-program", () => { newSourceProgram(); $("source-program").focus(); });
action("load-source-program-example", newSourceProgram);
action("save-source-program", saveDefinition);

const sourceDebug = { id: null, source: "", running: false, busy: false, pending: null, snapshot: null, runToken: 0 };
function sourceDebugControls() {
  const active = sourceDebug.snapshot && ["paused", "stopped"].includes(sourceDebug.snapshot.status);
  $("source-debug-start").disabled = sourceDebug.busy || sourceDebug.running;
  $("source-debug-step").disabled = !active || sourceDebug.busy || sourceDebug.running;
  $("source-debug-continue").disabled = !active || sourceDebug.busy || sourceDebug.running;
  $("source-debug-reset").disabled = !sourceDebug.id || sourceDebug.busy || sourceDebug.running;
  $("source-debug-stop").disabled = !sourceDebug.running;
}
function renderSourceDebug(snapshot) {
  sourceDebug.snapshot = snapshot;
  const names = { paused: "Bereit", stopped: "Gestoppt", done: "Beendet", failed: "Fehler" };
  $("source-debug-status").textContent = `${sourceDebug.running && snapshot.status === "paused" ? "Läuft" : names[snapshot.status]} · PC ${snapshot.pc} · Zeile ${snapshot.line} · ${snapshot.operation} · ${snapshot.instructions} Programmanweisungen · ${snapshot.steps} Budgetschritte · ${snapshot.iterations} Iterationen${snapshot.error ? ` · ${snapshot.error}` : ""}`;
  $("source-debug-code").replaceChildren(...sourceDebug.source.split("\n").map((line, index) => {
    const row = el("span", `${index + 1 === snapshot.line ? "▶" : " "} ${String(index + 1).padStart(3)}  ${line}\n`);
    if (index + 1 === snapshot.line) row.className = "source-debug-current";
    return row;
  }));
  $("source-debug-variables").textContent = Object.entries(snapshot.variables).map(([name, value]) => `${name} = ${Array.isArray(value) ? JSON.stringify(value) : value}`).join("\n") || "–";
  $("source-debug-result").textContent = snapshot.result ? `return ${snapshot.result.join(", ")}\n${snapshot.outputs ? `Portwerte (kodiert): ${JSON.stringify(snapshot.outputs)}` : ""}` : "–";
  sourceDebugControls();
}
async function sourceDebugRequest(command) {
  sourceDebug.busy = true; sourceDebugControls();
  try {
    sourceDebug.pending = api(`/api/source-debug/${sourceDebug.id}/${command}`, {});
    const snapshot = await sourceDebug.pending;
    renderSourceDebug(snapshot);
    return snapshot;
  } finally { sourceDebug.pending = null; sourceDebug.busy = false; sourceDebugControls(); }
}
action("source-debug-start", async () => {
  sourceDebug.busy = true; sourceDebugControls();
  try {
    const source = $("source-program").value;
    const request = {
      interface: readPorts().spec, x: $("source-debug-input").value.trim(),
      program: { version: 1, source, limits: { steps: int("source-program-steps"),
        iterations: int("source-program-iterations"), total_steps: int("source-program-total") } }
    };
    if ($("task-mode").value === "template") {
      const specialized = await specializeTemplate();
      request.program = specialized.program; request.interface = specialized.interface;
    }
    const snapshot = await api("/api/source-debug/start", request);
    const previous = sourceDebug.id;
    sourceDebug.id = snapshot.id; sourceDebug.source = source;
    renderSourceDebug(snapshot);
    if (previous) api(`/api/source-debug/${previous}/close`, {}).catch(() => {});
  } finally { sourceDebug.busy = false; sourceDebugControls(); }
});
action("source-debug-step", () => sourceDebugRequest("step"));
action("source-debug-reset", () => sourceDebugRequest("reset"));
action("source-debug-continue", async () => {
  const token = ++sourceDebug.runToken;
  sourceDebug.running = true; sourceDebugControls();
  try {
    while (sourceDebug.running && token === sourceDebug.runToken) {
      const snapshot = await sourceDebugRequest("continue");
      if (["done", "failed"].includes(snapshot.status)) break;
      await new Promise(resolve => setTimeout(resolve, 30));
    }
  } finally {
    if (token === sourceDebug.runToken) sourceDebug.running = false;
    sourceDebugControls();
  }
});
action("source-debug-stop", async () => {
  sourceDebug.runToken += 1;
  sourceDebug.running = false;
  if (sourceDebug.pending) await sourceDebug.pending;
  await sourceDebugRequest("stop");
});
action("cancel-vectors", async () => {
  if (!state.vectorJob || state.vectorJob === "starting") return;
  const result = await api(`/api/jobs/${state.vectorJob}/cancel`, {});
  if (result.status === "cancelling") $("vector-job-status").textContent = "Vektorerzeugung wird abgebrochen …";
});
action("generate", saveDefinition);
action("save-formula", saveDefinition);
action("import-rows", () => setDataset({ name: $("dataset-name").value, description: $("dataset-description").value, inputs: int("inputs"), outputs: int("outputs"), rows: JSON.parse($("raw-rows").value) }));
$("import").addEventListener("change", async event => { clearError(); try {
  if (event.target.files[0]) { const obj = JSON.parse(await event.target.files[0].text()); await setDataset(obj.dataset || obj); }
} catch (err) { error(err); } });
action("evolve", async () => {
  if (!state.datasetId) throw new Error("Bitte zuerst Zuordnungsvektoren erzeugen.");
  const config = { gates: int("gates"), population: int("population"), generations: int("generations"), seed: int("seed"), backend: $("backend").value, repair_cases: $("auto-repair").checked ? 4 : 0,
    restarts: int("restarts"), islands: int("islands"), migration_interval: int("migration-interval"), neutral: $("neutral").checked };
  $("evolve").disabled = true;
  let job_id;
  try {
    ({ job_id } = await api("/api/search", { dataset_id: state.datasetId, config }));
  } catch (err) { $("evolve").disabled = false; throw err; }
  state.job = job_id; $("cancel-search").disabled = false;
  updateContext();
  $("repair-program").disabled = true;
  $("job-status").textContent = "Suche läuft …";
  async function poll() {
    try {
      const job = await api(`/api/jobs/${job_id}`);
      $("job-status").textContent = job.status === "cancelling" ? "Suche wird abgebrochen …" : `Suche läuft · ${job.elapsed_seconds} s`;
      if (job.status === "done") {
        state.job = null; $("evolve").disabled = false; $("cancel-search").disabled = true;
        showProgram(job.result, state.page === "evolution"); await refresh();
        const comparison = job.result.comparison;
        if (comparison) {
          const before = comparison.previous_fitness, after = comparison.candidate_fitness;
          $("job-status").textContent = `Retest: bisher ${before.errors}, neu ${after.errors} fehlerhafte Ausgangsbits · ${comparison.accepted ? "Bessere Version übernommen." : "Bisherige Version beibehalten."}`;
        } else $("job-status").textContent = `${verification(job.result.fitness)} · Programm gespeichert.`;
      } else if (job.status === "failed" || job.status === "cancelled") {
        state.job = null; $("evolve").disabled = false; $("cancel-search").disabled = true;
        updateContext();
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

async function applyCircuit(document) {
  const circuit = document.circuit || document;
  if (document.dataset) await setDataset(document.dataset);
  const datasetId = document.dataset ? state.datasetId : state.result?.dataset_id || state.datasetId;
  const result = await api("/api/circuits/check", { circuit, ...(datasetId ? { dataset_id: datasetId } : {}) });
  showProgram(result);
  $("circuit-edit-status").textContent = result.fitness ?
    `${verification(result.fitness)} · ${result.fitness.errors} falsche Ausgangsbits in ${result.fitness.total_bits} geprüften Bits. Entwurf als JSON exportieren oder als Baustein speichern.` :
    "Schaltungsstruktur geprüft; keine Sollvektoren geladen. Entwurf als JSON exportieren oder als Baustein speichern.";
}
action("apply-circuit", () => applyCircuit(JSON.parse($("circuit-source").value)));
action("reset-circuit-source", () => { $("circuit-source").value = JSON.stringify(state.result.circuit, null, 2); });
$("import-circuit").addEventListener("change", async event => {
  clearError();
  try { if (event.target.files[0]) await applyCircuit(JSON.parse(await event.target.files[0].text())); }
  catch (err) { error(err); }
  finally { event.target.value = ""; }
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
  $("block-status").textContent = `${bundle.definitions[bundle.root].name} geöffnet. Unterprogramm-Boxen anklicken, um ihre interne Schaltung lokal zu testen.`;
}
function prepareBlock(bundle, count) {
  const root = bundle.definitions[bundle.root], inputs = [], outputs = [], nodes = [], mapping = {};
  if (count * root.interface.inputs.reduce((n,p) => n+p.bits, 0) > 128 || count * root.interface.outputs.reduce((n,p) => n+p.bits, 0) > 128) throw new Error("Diese Anzahl Instanzen überschreitet die 128-Bit-Grenze. Ports im eigenen JSON-Entwurf verbinden oder zusammenfassen.");
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
    if (int("step") >= simulationCircuit().gates.length) stopAnimation();
  }, 450);
});
BlockDebug.init();
pageFromHash();
refresh().catch(error);
setInterval(() => { if (!document.hidden) refresh().catch(() => {}); }, 5000);

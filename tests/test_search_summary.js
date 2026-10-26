"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");
const code = source.slice(source.indexOf("function renderHistory()"), source.indexOf("const graphElement ="));

function summary(search) {
  const elements = new Map();
  const element = () => ({ textContent: "", children: [], append(child) { this.children.push(child); }, replaceChildren() { this.children = []; } });
  const context = {
    state: { result: { search } },
    document: { createElement: element },
    $: id => {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    svg: () => ({})
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  context.renderHistory();
  return { text: elements.get("search-summary").textContent, phase: elements.get("phase-summary"),
    ancestry: elements.get("ancestry-panel"), ancestryText: elements.get("ancestry-summary").textContent,
    rows: elements.get("ancestry-nodes").children };
}

const legacy = { backend: "tiny", evaluations: 1, generation: 0, elapsed_seconds: .01,
  library_candidates: 0, seed: 1, history: [{ generation: 0, errors: 0 }] };

test("older searches without phase metadata still display their history", () => {
  const result = summary(legacy);
  assert.match(result.text, /TinyLanguage · 1 Kandidaten/);
  assert.equal(result.phase.hidden, true);
  assert.equal(result.phase.textContent, "");
  assert.equal(result.ancestry.hidden, true);
});

test("ancestry shows actual candidate parents and later transformations", () => {
  const result = summary({ ...legacy, ancestry: { root: 7, sources: { "program:test": {} },
    nodes: [
      { id: 2, parents: [], operator: "library", restart: 0, island: 1, generation: 0,
        origin: { seeds: [{ source: "program:<b>test</b>" }] } },
      { id: 7, parents: [2, 2], operator: "variation", restart: 0, island: 0, generation: 1,
        mutation_genes: [0], crossover_genes: [1], changes: [[0, 1]] }
    ], transformations: [{ operation: "compact" }, { operation: "incumbent_selection" }, { operation: "repair" }] } });
  assert.equal(result.ancestry.hidden, false);
  assert.match(result.ancestryText, /Bester Suchkandidat #7 · 2 Kandidaten/);
  assert.match(result.ancestryText, /1 konkret eingesetzte Quellen/);
  assert.match(result.ancestryText, /Kompaktierung → Auswahl der bisherigen Lösung → Restfallkorrektur/);
  assert.equal(result.rows[0].children[1].textContent, "#2, #2");
  assert.match(result.rows[0].children[2].textContent, /Rekombination · Mutationsstellen: 1 · Genänderungen: 1/);
  assert.equal(result.rows[1].children[2].textContent, "Bibliothekskomposition: program:<b>test</b>");
  assert.equal(result.rows[1].children[3].textContent, "Start 1 · Insel 2 · Gen 0");
});

test("large ancestry is limited to the latest 100 rows", () => {
  const result = summary({ ...legacy, ancestry: { root: 250, sources: {}, transformations: [],
    nodes: Array.from({ length: 250 }, (_, index) => ({ id: index + 1, parents: [],
      operator: "random", origin: {}, restart: 0, island: 0, generation: 0 })) } });
  assert.equal(result.rows.length, 100);
  assert.equal(result.rows[0].children[0].textContent, "#250");
  assert.equal(result.rows[99].children[0].textContent, "#151");
  assert.match(result.ancestryText, /250 Kandidaten/);
});

test("neutral summary distinguishes evolution from simplification before repair", () => {
  const result = summary({ ...legacy, neutral: true, phases: [
    { name: "neutral_evolution", result: { errors: 2 } },
    { name: "simplification", before: { gates: 7, depth: 5 }, result: { gates: 3, depth: 2 } }
  ] });
  assert.equal(result.phase.hidden, false);
  const text = result.phase.textContent;
  assert.match(text, /Phase 1: neutrale Evolution \(2 falsche Bits\)/);
  assert.match(text, /Phase 2: Vereinfachung 7 → 3 Gatter, Tiefe 5 → 2/);
  assert.match(text, /vor einer allfälligen Restfallkorrektur/);
});

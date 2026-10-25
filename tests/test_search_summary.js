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
  const context = {
    state: { result: { search } },
    $: id => {
      if (!elements.has(id)) elements.set(id, { textContent: "", append() {}, replaceChildren() {} });
      return elements.get(id);
    },
    svg: () => ({})
  };
  vm.createContext(context);
  vm.runInContext(code, context);
  context.renderHistory();
  return { text: elements.get("search-summary").textContent, phase: elements.get("phase-summary") };
}

const legacy = { backend: "tiny", evaluations: 1, generation: 0, elapsed_seconds: .01,
  library_candidates: 0, seed: 1, history: [{ generation: 0, errors: 0 }] };

test("older searches without phase metadata still display their history", () => {
  const result = summary(legacy);
  assert.match(result.text, /TinyLanguage · 1 Kandidaten/);
  assert.equal(result.phase.hidden, true);
  assert.equal(result.phase.textContent, "");
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

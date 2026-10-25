"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");
const deletion = source.slice(source.indexOf("async function deleteFunction("), source.indexOf("function renderFunctions("));

function setup({ confirmed = true, failure = false } = {}) {
  const elements = new Map();
  const calls = [];
  const state = { datasetId: "removed-data", dataset: {}, result: { id: "removed-program", dataset_id: "removed-data" }, debug: {}, layoutToken: 4 };
  const context = {
    state,
    $: id => {
      if (!elements.has(id)) elements.set(id, {});
      return elements.get(id);
    },
    clearError: () => {},
    confirm: message => { calls.push(["confirm", message]); return confirmed; },
    api: async (url, body) => {
      calls.push(["api", url, body]);
      if (failure) throw new Error("Server nicht erreichbar");
      return { dataset_ids: ["removed-data"], program_ids: ["removed-program"] };
    },
    stopAnimation: () => calls.push(["stop"]),
    renderTable: () => calls.push(["table"]),
    refresh: async () => calls.push(["refresh"]),
  };
  vm.createContext(context);
  vm.runInContext(deletion, context);
  return { state, elements, calls, remove: () => context.deleteFunction("abc123", "Meine Funktion", 2) };
}

test("cancelling deletion leaves the function and active view intact", async () => {
  const ui = setup({ confirmed: false });
  await ui.remove();
  assert.equal(ui.calls.length, 1);
  assert.equal(ui.calls[0][0], "confirm");
  assert.match(ui.calls[0][1], /Meine Funktion/);
  assert.match(ui.calls[0][1], /Alle 2 gespeicherten Vektorsätze/);
  assert.equal(ui.state.datasetId, "removed-data");
  assert.equal(ui.state.result.id, "removed-program");
});

test("confirmed deletion clears removed vectors, circuit and pending layout view", async () => {
  const ui = setup();
  await ui.remove();
  assert.equal(ui.calls[1][1], "/api/functions/abc123/delete");
  assert.equal(ui.state.dataset, null);
  assert.equal(ui.state.datasetId, null);
  assert.equal(ui.state.result, null);
  assert.equal(ui.state.debug, null);
  assert.equal(ui.state.layoutToken, 5);
  assert.equal(ui.elements.get("program").hidden, true);
  assert.equal(ui.elements.get("empty").hidden, false);
  for (const id of ["export-dataset", "export-program", "save-block-program", "repair-program"]) {
    assert.equal(ui.elements.get(id).disabled, true);
  }
  assert.equal(ui.calls.at(-1)[0], "refresh");
});

test("deleting another function preserves the currently loaded view", async () => {
  const ui = setup();
  ui.state.datasetId = "other-data";
  const result = ui.state.result = { id: "other-program", dataset_id: "other-data" };
  await ui.remove();
  assert.equal(ui.state.datasetId, "other-data");
  assert.equal(ui.state.result, result);
  assert.equal(ui.state.layoutToken, 4);
  assert.ok(!ui.calls.some(c => c[0] === "stop"));
});

test("server failure preserves the active function", async () => {
  const ui = setup({ failure: true });
  await assert.rejects(ui.remove(), /Server nicht erreichbar/);
  assert.equal(ui.state.datasetId, "removed-data");
  assert.equal(ui.state.result.id, "removed-program");
  assert.ok(!ui.calls.some(c => c[0] === "refresh"));
});

test("active search and vector generation prevent deletion", async () => {
  for (const job of ["job", "vectorJob"]) {
    const ui = setup();
    ui.state[job] = "running";
    await assert.rejects(ui.remove(), /laufenden Auftrag/);
    assert.equal(ui.calls.length, 0);
  }
});

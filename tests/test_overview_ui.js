"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), vm = require("node:vm");
const source = fs.readFileSync(require("node:path").join(__dirname, "../web/app.js"), "utf8");
const code = source.slice(source.indexOf("function setBundled("), source.indexOf('$("bus-mode").addEventListener'));

function setup() {
  const state = { overview: { bundled: true, selected: "", direction: "sources", focus: false },
    camera: { x: 120, y: 240, scale: 0.5 }, routing: [{}], positions: [{ x: 40, y: 100 }],
    wires: { "0:1:0": [{ x: 236, y: 100 }, { x: 328, y: 100 }] }, layoutDirty: false };
  const context = { state, renderSimulation() {}, fitGraph() { state.camera = { x: 20, y: 30, scale: 2 }; } };
  vm.createContext(context); vm.runInContext(code, context);
  return context;
}

test("focus and signal changes restore the original camera and retain bus preference and layout", () => {
  const ui = setup(), s = ui.state, before = JSON.stringify({ positions: s.positions, wires: s.wires });
  const camera = { ...s.camera };
  ui.selectTrace("out:0"); ui.setTraceFocus(true);
  assert.equal(s.overview.focus, true); assert.equal(s.overview.bundled, true);
  ui.selectTrace("out:1");
  assert.equal(s.overview.focus, true); assert.equal(s.overview.selected, "out:1");
  s.camera = { x: -100, y: 70, scale: 4 };
  ui.selectTrace("");
  assert.equal(s.overview.focus, false); assert.equal(s.overview.selected, "");
  assert.equal(JSON.stringify(s.camera), JSON.stringify(camera));
  assert.equal(s.layoutDirty, false);
  assert.equal(JSON.stringify({ positions: s.positions, wires: s.wires }), before);
});

test("bundling never edits saved paths or camera and discards only derived routes", () => {
  const ui = setup(), s = ui.state, before = JSON.stringify({ positions: s.positions, wires: s.wires, camera: s.camera });
  s.selectedWire = "0:1:0";
  ui.setBundled(false); ui.setBundled(true);
  assert.equal(s.routing, null); assert.equal(s.selectedWire, null);
  assert.equal(s.overview.bundled, true); assert.equal(s.layoutDirty, false);
  assert.equal(JSON.stringify({ positions: s.positions, wires: s.wires, camera: s.camera }), before);
});

test("changing traced bits reuses geometry while leaving tracing restores the bus geometry", () => {
  const ui = setup(), s = ui.state;
  ui.selectTrace("sig:2"); assert.equal(s.routing, null);
  const routing = [{}]; s.routing = routing;
  ui.selectTrace("sig:3"); assert.equal(s.routing, routing);
  ui.selectTrace(""); assert.equal(s.routing, null);
});

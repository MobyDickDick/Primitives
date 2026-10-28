"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../web/playback.js");
const { plan } = globalThis.CircuitPlayback;

test("parallel stages respect dependencies even when gate storage interleaves depths", () => {
  const c = { inputs: 2, gates: [[0, 1], [2, 2], [0, 0], [3, 4]], outputs: [5] };
  const p = plan(c);
  assert.equal(p.stages.length, 3);
  assert.deepEqual(p.stages[0].refs, [2, 4]);
  assert.equal(p.ready(4, 1), true);
  assert.equal(p.ready(3, 1), false);
  assert.equal(p.ready(5, 2), false);
  assert.equal(p.ready(5, 3), true);
  const gates = plan(c, "gates");
  assert.equal(gates.stages.length, 4);
  assert.equal(gates.ready(4, 2), false);
});

test("FBox chapters include wiring-only boxes and expose whole buses together", () => {
  const c = { inputs: 2, gates: [[0, 1], [2, 2]], outputs: [0, 3], view_nodes: [
    { ref: 0, kind: "input", level: 0, signalRefs: [0] },
    { ref: 1, kind: "input", level: 0, signalRefs: [1] },
    { ref: 2, kind: "instance", name: "Reverse", level: 1, signalRefs: [0, 1] },
    { ref: 3, kind: "instance", name: "AND", level: 1, signalRefs: [3] },
    { ref: 4, kind: "output", level: 2, signalRefs: [3] }
  ] };
  const parallel = plan(c);
  assert.equal(parallel.stages.length, 1);
  assert.match(parallel.stages[0].label, /Reverse.*AND/);
  const boxes = plan(c, "blocks");
  assert.equal(boxes.stages.length, 2);
  assert.equal(boxes.ready(3, 1), false);
  assert.equal(boxes.ready(3, 2), true);
  assert.equal(plan(c, "gates").stages.length, 2);
});

test("empty gate networks immediately expose direct outputs", () => {
  const p = plan({ inputs: 1, gates: [], outputs: [0] });
  assert.equal(p.stages.length, 0);
  assert.equal(p.ready(0, 0), true);
});

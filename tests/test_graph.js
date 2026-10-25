"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../web/graph.js");
const graph = globalThis.CircuitGraph;
const xor = { inputs: 2, gates: [[0, 0], [1, 1], [3, 2], [4, 4]], outputs: [5] };

function assertClearWires(c, positions) {
  const routes = graph.routes(c, positions);
  const boxes = positions.map(p => ({ left: p.x, right: p.x + graph.width, top: p.y - graph.height / 2, bottom: p.y + graph.height / 2 }));
  for (const wire of routes) {
    assert.deepEqual(wire.points[0], wire.start);
    assert.deepEqual(wire.points.at(-1), wire.end);
    wire.points.slice(1).forEach((p, i) => {
      const a = wire.points[i];
      assert.ok(a.x === p.x || a.y === p.y, "wires must remain orthogonal");
      assert.ok(graph.clear(a, p, boxes), `wire ${wire.source} → ${wire.target} intersects a box`);
    });
  }
  return routes;
}

test("reversed NAND arguments use ports in visual top-to-bottom order", () => {
  const positions = graph.automatic(xor);
  positions.forEach((p, ref) => assert.ok(graph.canPlace(positions, ref, p), "automatic positions must also be valid saved positions"));
  const incoming = graph.connections(xor, positions).filter(e => e.target === 4);
  assert.equal(incoming[0].source, 2);
  assert.equal(incoming[1].source, 3);
  assert.ok(incoming[0].end.y < incoming[1].end.y);
  const routes = assertClearWires(xor, positions).filter(e => e.target === 4);
  const ys = routes.map(e => e.points.map(p => p.y));
  assert.ok(Math.max(...ys[0]) < Math.min(...ys[1]), "the two incoming wires must not cross");
});

test("dragged boxes and reversed connections route around every box", () => {
  const positions = graph.automatic(xor);
  positions[2] = { x: 960, y: 520 };
  positions[4] = { x: 340, y: 520 };
  assertClearWires(xor, positions);
});

test("direct outputs, duplicated inputs and multiple outputs remain connected", () => {
  for (const c of [{ inputs: 1, gates: [], outputs: [0] }, { inputs: 1, gates: [[0, 0]], outputs: [0, 1] }]) {
    const positions = graph.automatic(c);
    assert.ok(graph.valid(c, positions));
    assert.equal(assertClearWires(c, positions).length, c.gates.length * 2 + c.outputs.length);
  }
});

test("moving a box cannot overlap another box", () => {
  const positions = graph.automatic(xor);
  assert.equal(graph.canPlace(positions, 0, positions[1]), false);
  assert.equal(graph.canPlace(positions, 0, { x: 40, y: 600 }), true);
  assert.equal(graph.valid(xor, [{ x: NaN, y: 0 }]), false);
});

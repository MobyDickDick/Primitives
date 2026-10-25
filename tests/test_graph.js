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

test("straight wires gain draggable bends while both terminals stay fixed", () => {
  const c = { inputs: 1, gates: [], outputs: [0] }, positions = graph.automatic(c);
  const edge = graph.routes(c, positions)[0], original = JSON.stringify(c);
  assert.equal(edge.points.length, 2);
  const points = graph.moveSegment(edge.points, 0, { x: 0, y: edge.start.y + 60 });
  assert.ok(graph.usablePath(edge, points, positions));
  assert.deepEqual(points[0], edge.start); assert.deepEqual(points.at(-1), edge.end);
  const wires = { [edge.id]: points };
  for (let i = 0; i < 3; i++) {
    const routed = graph.routes(c, positions, JSON.parse(JSON.stringify(wires)))[0];
    assert.deepEqual(routed.points, points); assert.equal(routed.blocked, false);
  }
  assert.equal(JSON.stringify(c), original, "routing cannot change the logical circuit");
  // Dragging the new horizontal segment is independent of its screen zoom.
  const index = points.findIndex((p, i) => i && points[i - 1].y === p.y && p.y !== edge.start.y) - 1;
  for (const scale of [0.25, 1, 2]) {
    const shifted = graph.moveSegment(points, index, { x: 0, y: points[index].y + 20 / scale });
    assert.ok(graph.usablePath(edge, shifted, positions));
    assert.equal(shifted[index].y, points[index].y + 20 / scale);
  }
});

test("logical port IDs survive visual source swaps and duplicated NAND inputs", () => {
  const positions = graph.automatic(xor), before = graph.connections(xor, positions);
  [positions[2].y, positions[3].y] = [positions[3].y, positions[2].y];
  const after = graph.connections(xor, positions);
  assert.deepEqual(before.map(e => e.id).sort(), after.map(e => e.id).sort());
  assert.notEqual(before.find(e => e.id === '3:4:0').end.y, after.find(e => e.id === '3:4:0').end.y);
  const doubled = graph.routes(xor, positions).filter(e => e.target === 2);
  assert.deepEqual(doubled.map(e => e.id), ['0:2:0', '0:2:1']);
  assert.notDeepEqual(doubled[0].end, doubled[1].end);
  const points = graph.moveSegment(doubled[0].points, doubled[0].points.length - 2, { x: 0, y: doubled[0].start.y - 30 });
  assert.ok(graph.usablePath(doubled[0], points, positions));
  assert.notDeepEqual(points, doubled[0].points);
  const routed = graph.routes(xor, positions, { [doubled[0].id]: points });
  assert.deepEqual(routed.find(e => e.id === doubled[0].id).points, points);
  assert.equal(routed.find(e => e.id === doubled[1].id).manual, false);
});

test("box moves reconnect manual terminals and blocked paths recover without losing intent", () => {
  const c = { inputs: 1, gates: [], outputs: [0] }, positions = graph.automatic(c);
  const edge = graph.routes(c, positions)[0];
  const points = graph.moveSegment(edge.points, 0, { x: 0, y: edge.start.y + 60 });
  const wires = { [edge.id]: points }, saved = JSON.stringify(wires);
  positions[0].y -= 50;
  let routed = graph.routes(c, positions, wires)[0];
  assert.equal(routed.blocked, false);
  assert.deepEqual(routed.points[0], { x: positions[0].x + graph.width, y: positions[0].y });
  assert.deepEqual(routed.points.at(-1), edge.end);
  positions[0].x = 1000;
  routed = graph.routes(c, positions, wires)[0];
  assert.equal(routed.blocked, true); assert.equal(routed.manual, true);
  assert.ok(graph.usablePath(routed, routed.points, positions));
  positions[0] = graph.automatic(c)[0];
  assert.deepEqual(graph.routes(c, positions, wires)[0].points, points);
  assert.equal(JSON.stringify(wires), saved);
  assert.deepEqual(graph.routes(c, positions, {})[0].points, edge.points, "reset restores automatic routing");
});

test("manual routing rejects obstacles, diagonals, nonfinite coordinates and excess points", () => {
  const positions = graph.automatic(xor), edge = graph.routes(xor, positions)[0];
  const blocked = graph.moveSegment(edge.points, edge.points.length - 2, { x: 0, y: edge.start.y + 100 });
  const obstacle = { x: edge.start.x + 20, y: edge.start.y + 100 };
  assert.equal(graph.usablePath(edge, blocked, [...positions, obstacle]), false);
  for (const points of [[], [{ x: NaN, y: 0 }, edge.end], [edge.start, { x: -1, y: 20 }, edge.end],
    [edge.start, { x: edge.start.x + 1, y: edge.start.y + 1 }, edge.end], Array(129).fill(edge.start)]) {
    assert.equal(graph.validPoints(points), false);
  }
});

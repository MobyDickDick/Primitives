"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../web/graph.js");
require("../web/overview.js");
const graph = globalThis.CircuitGraph, overview = globalThis.CircuitOverview;
const spec = { inputs: [{ name: "a", offset: 0, bits: 4 }], outputs: [{ name: "c", offset: 0, bits: 4 }] };
const iface = { inputs: [{ name: "a", offset: 0, bits: 4 }], outputs: [{ name: "c", offset: 0, bits: 4 }] };
const c = { inputs: 4, gates: [], outputs: [0, 1, 2, 3], view_nodes: [
  ...Array.from({ length: 4 }, (_, ref) => ({ ref, kind: "input", index: ref, sources: [], signalRefs: [ref], level: 0 })),
  { ref: 4, kind: "instance", id: "reverse", sources: [0, 1, 2, 3], sourceBits: [0, 0, 0, 0], signalRefs: [3, 2, 1, 0], inputRefs: [0, 1, 2, 3], interface: iface, level: 1, height: 108 },
  { ref: 5, kind: "instance", id: "restore", sources: [4, 4, 4, 4], sourceBits: [3, 2, 1, 0], signalRefs: [0, 1, 2, 3], inputRefs: [0, 1, 2, 3], interface: iface, level: 2, height: 108 },
  ...Array.from({ length: 4 }, (_, index) => ({ ref: 6 + index, kind: "output", index, sources: [5], sourceBits: [index], signalRefs: [index], level: 3 })),
] };

test("named four-bit buses retain every permuted pin and expand to original wires", () => {
  const positions = graph.automatic(c), original = JSON.stringify({ c, positions });
  const bundled = overview.project(c, positions, spec, true);
  assert.equal(bundled.wires.length, 3);
  assert.ok(bundled.wires.every(w => w.bus && w.members.length === 4));
  assert.equal(bundled.hidden.size, 6);
  const middle = bundled.wires.find(w => w.source === 4 && w.target === 5);
  assert.deepEqual(middle.members.map(e => [e.sourceBit, e.port]), [[3, 0], [2, 1], [1, 2], [0, 3]]);
  assert.deepEqual(middle.mappings, ["c[3] → a[0]", "c[2] → a[1]", "c[1] → a[2]", "c[0] → a[3]"]);
  assert.match(middle.label, /4 Bit/);
  const expanded = overview.project(c, positions, spec, false);
  assert.equal(expanded.hidden.size, 0);
  assert.deepEqual(expanded.wires.map(w => w.id), graph.connections(c, positions).map(w => w.id));
  for (const wire of overview.route(bundled, positions)) {
    assert.deepEqual(wire.points[0], wire.start); assert.deepEqual(wire.points.at(-1), wire.end);
    const boxes = positions.map(p => ({ left: p.x, right: p.x + graph.width,
      top: p.y - graph.boxHeight(p) / 2, bottom: p.y + graph.boxHeight(p) / 2 })).filter((_, i) => !bundled.hidden.has(i));
    assert.ok(wire.points.slice(1).every((p, i) => graph.clear(wire.points[i], p, boxes)));
  }
  assert.equal(JSON.stringify({ c, positions }), original);
});

test("bus partitions preserve different source ports, partial ranges and repeated bits", () => {
  const mixed = structuredClone(c);
  mixed.view_nodes[5].sourceBits = [3, 3, 0, 2];
  mixed.view_nodes[4].interface.outputs = [{ name: "lo", offset: 0, bits: 2 }, { name: "hi", offset: 2, bits: 2 }];
  const view = overview.project(mixed, graph.automatic(mixed), spec, true);
  const incoming = view.wires.filter(w => w.target === 5);
  assert.equal(incoming.length, 2);
  assert.deepEqual(incoming.flatMap(w => w.members).map(e => [e.sourceBit, e.port]).sort((a, b) => a[1] - b[1]), [[3, 0], [3, 1], [0, 2], [2, 3]]);
  assert.ok(incoming.some(w => w.mappings.includes("hi[1] → a[0]") && w.mappings.includes("hi[1] → a[1]")));
  const single = incoming.find(w => !w.bus);
  const positions = graph.automatic(mixed);
  assert.equal(single.displayOnly, true);
  assert.equal(single.start.y, positions[4].y + graph.pinOffset(4, 0.5));
});

test("direct buses and saved bit paths survive repeated bundling without mutation", () => {
  const direct = { inputs: 4, gates: [], outputs: [3, 1, 1, 0] };
  const positions = graph.automatic(direct), original = JSON.stringify(positions);
  const edges = graph.routes(direct, positions);
  const wires = Object.fromEntries(edges.map(w => [w.id, w.points]));
  const saved = JSON.stringify(wires);
  for (let i = 0; i < 3; i++) {
    const view = overview.project(direct, positions, spec, true);
    assert.equal(view.wires.length, 1);
    assert.deepEqual(view.wires[0].mappings, ["a[3] → c[0]", "a[1] → c[1]", "a[1] → c[2]", "a[0] → c[3]"]);
    overview.route(view, positions, wires);
    assert.deepEqual(graph.routes(direct, positions, wires).map(w => w.points), edges.map(w => w.points));
  }
  assert.equal(JSON.stringify(positions), original); assert.equal(JSON.stringify(wires), saved);
});

test("output tracing and fan-out exclude unrelated siblings sharing earlier inputs", () => {
  const flat = { inputs: 3, gates: [[0, 1], [3, 2], [3, 3], [0, 2]], outputs: [4, 5, 6, 0] };
  const nodes = graph.nodes(flat), edges = graph.connections(flat, graph.automatic(flat));
  const source = overview.trace(flat, 4);
  assert.deepEqual([...source.signals].sort(), [0, 1, 2, 3, 4]);
  assert.deepEqual(nodes.filter(source.node).map(n => n.ref), [0, 1, 2, 3, 4, 7]);
  assert.deepEqual(edges.filter(w => source.edge(w, nodes)).map(w => [w.source, w.target]), [[0, 3], [1, 3], [3, 4], [2, 4], [4, 7]]);
  const both = overview.trace(flat, 3, "both");
  assert.deepEqual([...both.downstream].sort(), [3, 4, 5]);
  assert.equal(both.signals.has(6), false); assert.equal(both.signals.has(2), false);
  assert.ok(edges.filter(w => both.edge(w, nodes)).every(w => w.target !== 6 && w.target !== 10 && w.source !== 2));
});

test("hierarchical tracing follows the actual permuted signal, including wiring-only instances", () => {
  const nodes = graph.nodes(c), trace = overview.trace(c, 1);
  const edges = graph.connections(c, graph.automatic(c)).filter(w => trace.edge(w, nodes));
  assert.deepEqual(edges.map(w => [w.source, w.sourceBit, w.target, w.port]), [[1, 0, 4, 1], [4, 2, 5, 1], [5, 1, 7, 0]]);
  assert.equal(overview.trace(c, -1), null); assert.equal(overview.trace(c, 4), null);
});

test("choosing one direct output excludes other output aliases of the same signal", () => {
  const flat = { inputs: 1, gates: [[0, 0]], outputs: [0, 0, 1] };
  const nodes = graph.nodes(flat), trace = overview.trace(flat, 0, "sources", 1);
  const edges = graph.connections(flat, graph.automatic(flat));
  assert.deepEqual(nodes.filter(trace.node).map(n => n.ref), [0, 3]);
  assert.deepEqual(edges.filter(w => trace.edge(w, nodes)).map(w => [w.source, w.target]), [[0, 3]]);
});

test("512-gate flat net tracing agrees with an independent iterative dependency oracle", () => {
  const flat = { inputs: 8, gates: [], outputs: [] };
  for (let i = 0; i < 512; i++) flat.gates.push([i ? 7 + i : 0, (i * 17 + 3) % (8 + i)]);
  flat.outputs = [519, 257, 0];
  const before = JSON.stringify(flat);
  for (const root of flat.outputs) {
    const expected = new Set([root]);
    for (let r = 519; r >= 8; r--) if (expected.has(r)) flat.gates[r - 8].forEach(s => expected.add(s));
    assert.deepEqual(overview.trace(flat, root).signals, expected);
  }
  assert.equal(JSON.stringify(flat), before);
});

test("hidden internal NAND signals highlight their containing FBox and exact incoming pins", () => {
  const nested = { inputs: 3, gates: [[0, 1], [3, 2]], outputs: [4], view_nodes: [
    ...Array.from({ length: 3 }, (_, ref) => ({ ref, kind: "input", index: ref, sources: [], signalRefs: [ref], level: 0 })),
    { ref: 3, kind: "instance", sources: [0, 1, 2], sourceBits: [0, 0, 0], inputRefs: [0, 1, 2], signalRefs: [4], gateRefs: [3, 4], level: 1 },
    { ref: 4, kind: "output", sources: [3], sourceBits: [0], signalRefs: [4], level: 2 },
  ] };
  const nodes = graph.nodes(nested), edges = graph.connections(nested, graph.automatic(nested));
  const trace = overview.trace(nested, 3);
  assert.deepEqual(nodes.filter(trace.node).map(n => n.ref), [0, 1, 3]);
  assert.deepEqual(edges.filter(w => trace.edge(w, nodes)).map(w => [w.source, w.target]), [[0, 3], [1, 3]]);
  const both = overview.trace(nested, 3, "both");
  assert.ok(both.node(nodes[4]));
  assert.deepEqual(edges.filter(w => both.edge(w, nodes)).map(w => [w.source, w.target]), [[0, 3], [1, 3], [3, 4]]);
});

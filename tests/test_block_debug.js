"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../web/graph.js");
require("../web/block-debug.js");
const graph = globalThis.CircuitGraph, debug = globalThis.BlockDebug;

test("local numeric inputs preserve neighbouring ports and all 32 bits", () => {
  const port = { name: "word", bits: 32, offset: 1, signed: false };
  const bits = Array(34).fill(0); bits[0] = bits[33] = 1;
  const max = debug.withNumber(bits, port, 4294967295);
  assert.equal(debug.number(max, port), 4294967295);
  assert.equal(max[0], 1); assert.equal(max[33], 1);
  assert.deepEqual(bits.slice(1, 33), Array(32).fill(0));
  for (const value of [-1, 4294967296, 1.5, NaN]) assert.throws(() => debug.withNumber(bits, port, value));
  const signed = { ...port, signed: true };
  for (const value of [-2147483648, -1, 0, 2147483647]) {
    assert.equal(debug.number(debug.withNumber(bits, signed, value), signed), value);
  }
  assert.throws(() => debug.withNumber(bits, signed, 2147483648));
});

test("128-bit decimal input preserves every bit, signed bounds and neighbours", () => {
  const port = { name: "wide", bits: 128, offset: 1, signed: false };
  const bits = Array(130).fill(0); bits[0] = bits[129] = 1;
  const max = (1n << 128n) - 1n;
  for (const value of [0n, 1n, (1n << 100n) + 3n, max]) {
    const result = debug.withNumber(bits, port, String(value));
    assert.equal(BigInt(debug.number(result, port)), value);
    assert.equal(result[0], 1); assert.equal(result[129], 1);
    for (let i = 0; i < 128; i++) assert.equal(result[i + 1], Number(value >> BigInt(i) & 1n));
  }
  const signed = { ...port, signed: true };
  for (const value of [-(1n << 127n), -1n, 0n, (1n << 127n) - 1n]) {
    assert.equal(BigInt(debug.number(debug.withNumber(bits, signed, String(value)), signed)), value);
  }
  for (const value of ["", "1.5", "1e20", " ", "0x10", String(max + 1n), "-1", Number(max)]) {
    assert.throws(() => debug.withNumber(bits, port, value));
  }
  for (const value of [-(1n << 127n) - 1n, 1n << 127n]) assert.throws(() => debug.withNumber(bits, signed, value));
  assert.deepEqual(bits.slice(1, 129), Array(128).fill(0));
});

test("hierarchical wires retain ordered bit pins, including repeated sources", () => {
  const c = { inputs: 2, gates: [], outputs: [0, 1], view_nodes: [
    { ref: 0, kind: "input", sources: [], signalRefs: [0], level: 0 },
    { ref: 1, kind: "input", sources: [], signalRefs: [1], level: 0 },
    { ref: 2, kind: "instance", sources: [1, 0, 1], sourceBits: [0, 0, 0], signalRefs: [0, 1], height: 108, level: 1 },
    { ref: 3, kind: "instance", sources: [2, 2], sourceBits: [1, 0], signalRefs: [1, 0], height: 84, level: 2 },
    { ref: 4, kind: "output", sources: [3], sourceBits: [0], signalRefs: [1], level: 3 },
  ] };
  const positions = graph.automatic(c);
  assert.ok(graph.valid(c, positions));
  positions.forEach((p, i) => assert.ok(graph.canPlace(positions, i, p)));
  const edges = graph.connections(c, positions), first = edges.filter(e => e.target === 2);
  assert.deepEqual(first.map(e => e.port), [0, 1, 2]);
  assert.ok(first[0].end.y < first[1].end.y && first[1].end.y < first[2].end.y);
  const second = edges.filter(e => e.target === 3);
  assert.ok(second[0].start.y > second[1].start.y);
  assert.notEqual(second[0].id, second[1].id);
  const restored = debug.positions(c, JSON.parse(JSON.stringify(positions.map(({ x, y }) => ({ x, y })))));
  assert.deepEqual(restored, positions);
  for (const edge of graph.routes(c, positions)) assert.ok(graph.usablePath(edge, edge.points, positions));
  const before = JSON.stringify(c);
  graph.routes(c, positions, {});
  assert.equal(JSON.stringify(c), before);
});

"use strict";

// Geometry is independent of signal values, so toggling an input keeps the layout.
globalThis.CircuitGraph = (() => {
  const width = 196, height = 84, clearance = 12;
  const boxName = ref => `Box ${ref}`;
  const boxHeight = p => p?.height || height;
  const pinOffset = (count, slot) => (slot - (count - 1) / 2) * 16;

  function nodes(c) {
    if (c.view_nodes) return c.view_nodes;
    const result = Array.from({ length: c.inputs }, (_, ref) => ({ ref, kind: "input", index: ref, sources: [], level: 0 }));
    c.gates.forEach((sources, index) => result.push({ ref: result.length, kind: "gate", index, sources, level: 1 + Math.max(...sources.map(r => result[r].level)) }));
    const level = 1 + Math.max(...result.map(n => n.level));
    c.outputs.forEach((source, index) => result.push({ ref: result.length, kind: "output", index, sources: [source], level }));
    return result;
  }

  function automatic(c) {
    const list = nodes(c), layers = [], positions = [];
    list.forEach(n => (layers[n.level] ||= []).push(n.ref));
    const totalHeight = Math.max(300, ...layers.map(l => l.reduce((sum, ref) => sum + boxHeight(list[ref]) + 48, 48)));
    const place = () => layers.forEach((layer, level) => {
      const used = layer.reduce((sum, ref) => sum + boxHeight(list[ref]), 0);
      const gap = (totalHeight - used) / (layer.length + 1);
      let y = gap;
      layer.forEach(ref => {
        const h = boxHeight(list[ref]);
        positions[ref] = { x: 40 + level * 288, y: y + h / 2, ...(h !== height ? { height: h } : {}) };
        y += h + gap;
      });
    });
    place();
    // Barycentre sweeps reduce crossings between neighbouring layers.
    for (let pass = 0; pass < 4; pass++) {
      for (let level = 1; level < layers.length - 1; level++) {
        const average = ref => list[ref].sources.reduce((sum, r) => sum + positions[r].y, 0) / list[ref].sources.length;
        layers[level].sort((a, b) => average(a) - average(b) || a - b);
      }
      place();
    }
    return positions;
  }

  function valid(c, positions) {
    return Array.isArray(positions) && positions.length === nodes(c).length && positions.every(p =>
      p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 20 && p.y >= boxHeight(p) / 2 + 20 && p.x <= 99000 && p.y <= 99000);
  }

  function canPlace(positions, ref, point) {
    return positions.every((p, i) => i === ref || Math.abs(point.x - p.x) >= width + 44 || Math.abs(point.y - p.y) >= (boxHeight(point) + boxHeight(p)) / 2 + 36);
  }

  function connections(c, positions) {
    const list = nodes(c);
    return list.flatMap(node => {
      // NAND is commutative: the upper source always uses the upper port.
      const sources = node.sources.map((source, port) => ({ source, port }))
        .sort((a, b) => node.kind === "instance" ? a.port - b.port : positions[a.source].y - positions[b.source].y || a.source - b.source || a.port - b.port);
      return sources.map(({ source, port }, slot) => {
        const sourceBit = node.sourceBits?.[port] || 0;
        return { source, sourceBit, target: node.ref, port, id: `${source}:${node.ref}:${port}${c.view_nodes ? `:${sourceBit}` : ""}`,
          start: { x: positions[source].x + width, y: positions[source].y + (list[source].kind === "instance" ? pinOffset(list[source].signalRefs.length, sourceBit) : 0) },
          end: { x: positions[node.ref].x, y: positions[node.ref].y + (node.kind === "instance" ? pinOffset(sources.length, slot) : sources.length === 2 ? (slot ? 18 : -18) : 0) } };
      });
    });
  }

  function rectangles(positions) {
    return positions.map(p => ({ left: p.x - clearance, right: p.x + width + clearance,
      top: p.y - boxHeight(p) / 2 - clearance, bottom: p.y + boxHeight(p) / 2 + clearance }));
  }
  function clear(a, b, obstacles) {
    return !obstacles.some(r => a.x === b.x
      ? a.x > r.left && a.x < r.right && Math.max(a.y, b.y) > r.top && Math.min(a.y, b.y) < r.bottom
      : a.y > r.top && a.y < r.bottom && Math.max(a.x, b.x) > r.left && Math.min(a.x, b.x) < r.right);
  }
  const distance = (a, b) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);
  function crossings(a, b, paths) {
    let count = 0;
    for (const path of paths) for (let i = 1; i < path.length; i++) {
      const c = path[i - 1], d = path[i];
      const vertical = a.x === b.x;
      if (vertical === (c.x === d.x)) {
        if ((vertical && a.x === c.x) || (!vertical && a.y === c.y)) {
          const overlap = vertical
            ? Math.min(Math.max(a.y, b.y), Math.max(c.y, d.y)) - Math.max(Math.min(a.y, b.y), Math.min(c.y, d.y))
            : Math.min(Math.max(a.x, b.x), Math.max(c.x, d.x)) - Math.max(Math.min(a.x, b.x), Math.min(c.x, d.x));
          if (overlap > 0) count += 1 + overlap / 10;
        }
        continue;
      }
      const v1 = vertical ? a : c, v2 = vertical ? b : d, h1 = vertical ? c : a, h2 = vertical ? d : b;
      if (v1.x > Math.min(h1.x, h2.x) && v1.x < Math.max(h1.x, h2.x)
          && h1.y > Math.min(v1.y, v2.y) && h1.y < Math.max(v1.y, v2.y)) count++;
    }
    return count;
  }
  function simplify(path) {
    const result = [];
    for (const p of path) {
      if (result.length && distance(result.at(-1), p) === 0) continue;
      while (result.length > 1) {
        const a = result.at(-2), b = result.at(-1);
        if ((a.x === b.x && b.x === p.x) || (a.y === b.y && b.y === p.y)) result.pop();
        else break;
      }
      result.push(p);
    }
    return result;
  }

  class Heap {
    items = [];
    push(item) {
      let i = this.items.length;
      this.items.push(item);
      while (i > 0) {
        const parent = (i - 1) >> 1;
        if (this.items[parent].priority <= item.priority) break;
        this.items[i] = this.items[parent]; i = parent;
      }
      this.items[i] = item;
    }
    pop() {
      const top = this.items[0], last = this.items.pop();
      if (this.items.length) {
        let i = 0;
        while (i * 2 + 1 < this.items.length) {
          let child = i * 2 + 1;
          if (child + 1 < this.items.length && this.items[child + 1].priority < this.items[child].priority) child++;
          if (this.items[child].priority >= last.priority) break;
          this.items[i] = this.items[child]; i = child;
        }
        this.items[i] = last;
      }
      return top;
    }
  }

  function route(edge, obstacles, previous = []) {
    const start = { x: edge.start.x + 18, y: edge.start.y }, end = { x: edge.end.x - 18, y: edge.end.y };
    const candidates = [];
    const add = points => {
      if (points.slice(1).every((p, i) => clear(points[i], p, obstacles))) candidates.push(simplify(points));
    };
    const mid = (start.x + end.x) / 2;
    for (const x of [mid, mid - 16, mid + 16, start.x, end.x]) add([start, { x, y: start.y }, { x, y: end.y }, end]);
    for (const y of [start.y, end.y, Math.max(4, Math.min(...obstacles.map(r => r.top)) - 20), Math.max(...obstacles.map(r => r.bottom)) + 20]) {
      add([start, { x: start.x, y }, { x: end.x, y }, end]);
    }
    const cost = path => path.slice(1).reduce((sum, p, i) => sum + distance(path[i], p) + 90 * crossings(path[i], p, previous), 0) + path.length * 8;
    candidates.sort((a, b) => cost(a) - cost(b));
    if (candidates.length) return simplify([edge.start, ...candidates[0], edge.end]);

    // Compressed orthogonal grid: route around boxes even after free dragging.
    const xs = [...new Set([start.x, end.x, ...obstacles.flatMap(r => [r.left, r.right])])].sort((a, b) => a - b);
    const ys = [...new Set([start.y, end.y, ...obstacles.flatMap(r => [r.top, r.bottom])])].sort((a, b) => a - b);
    const key = (x, y) => y * xs.length + x;
    const point = id => ({ x: xs[id % xs.length], y: ys[Math.floor(id / xs.length)] });
    const first = key(xs.indexOf(start.x), ys.indexOf(start.y)), goal = key(xs.indexOf(end.x), ys.indexOf(end.y));
    const queue = new Heap(), costs = new Map([[first, 0]]), parents = new Map();
    queue.push({ id: first, cost: 0, priority: distance(start, end) });
    while (queue.items.length) {
      const current = queue.pop();
      if (current.cost !== costs.get(current.id)) continue;
      if (current.id === goal) {
        const path = [];
        for (let id = goal; id !== undefined; id = parents.get(id)) path.push(point(id));
        return simplify([edge.start, ...path.reverse(), edge.end]);
      }
      const x = current.id % xs.length, y = Math.floor(current.id / xs.length), a = point(current.id);
      for (const [nx, ny] of [[x - 1, y], [x + 1, y], [x, y - 1], [x, y + 1]]) {
        if (nx < 0 || nx >= xs.length || ny < 0 || ny >= ys.length) continue;
        const id = key(nx, ny), b = point(id);
        if (!clear(a, b, obstacles)) continue;
        const cost = current.cost + distance(a, b) + 90 * crossings(a, b, previous);
        if (cost >= (costs.get(id) ?? Infinity)) continue;
        costs.set(id, cost); parents.set(id, current.id);
        queue.push({ id, cost, priority: cost + distance(b, end) });
      }
    }
    throw new Error("Keine freie Zuleitung gefunden. Bitte die Boxen weiter auseinanderziehen.");
  }

  function validPoints(points) {
    return Array.isArray(points) && points.length >= 2 && points.length <= 128 && points.every((p, i) =>
      p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 0 && p.y >= 0 && p.x <= 100000 && p.y <= 100000 &&
      (!i || p.x === points[i - 1].x || p.y === points[i - 1].y));
  }

  function manualPath(edge, points) {
    if (!validPoints(points)) return null;
    if (!distance(edge.start, points[0]) && !distance(edge.end, points.at(-1))) return points;
    // Keep the interior in world coordinates; only reconnect the two terminal leads.
    const inside = points.slice(1, -1);
    if (!inside.length) return null;
    const start = { x: edge.start.x + 18, y: edge.start.y }, end = { x: edge.end.x - 18, y: edge.end.y };
    return simplify([edge.start, start, { x: start.x, y: inside[0].y }, ...inside,
      { x: end.x, y: inside.at(-1).y }, end, edge.end]);
  }

  function usablePath(edge, points, positions) {
    if (!validPoints(points) || distance(points[0], edge.start) || distance(points.at(-1), edge.end)) return false;
    // Leads must leave to the right and enter from the left, outside the clearance.
    if (points[1].y !== edge.start.y || points[1].x < edge.start.x + 18 ||
        points.at(-2).y !== edge.end.y || points.at(-2).x > edge.end.x - 18) return false;
    const boxes = positions.map(p => ({ left: p.x, right: p.x + width, top: p.y - boxHeight(p) / 2, bottom: p.y + boxHeight(p) / 2 }));
    return points.slice(1).every((p, i) => clear(points[i], p, boxes));
  }

  function moveSegment(points, index, point) {
    let a = points[index], b = points[index + 1];
    const vertical = a.x === b.x;
    const prefix = points.slice(0, index + 1), suffix = points.slice(index + 1);
    // A straight wire has no bends yet: create two while retaining terminal stubs.
    if (!vertical && index === 0) { a = { x: a.x + 18, y: a.y }; prefix.push(a); }
    if (!vertical && index === points.length - 2) { b = { x: b.x - 18, y: b.y }; suffix.unshift(b); }
    const first = vertical ? { x: point.x, y: a.y } : { x: a.x, y: point.y };
    const last = vertical ? { x: point.x, y: b.y } : { x: b.x, y: point.y };
    return simplify([...prefix, first, last, ...suffix]);
  }

  function routes(c, positions, wires = {}) {
    const obstacles = rectangles(positions), paths = [];
    const edges = connections(c, positions);
    const blocked = [];
    edges.forEach(edge => {
      const manual = wires[edge.id] && manualPath(edge, wires[edge.id]);
      const usable = manual && usablePath(edge, manual, positions);
      blocked.push(Boolean(wires[edge.id]) && !usable);
      paths.push(usable ? manual : route(edge, obstacles, paths.filter((_, i) => edges[i].source !== edge.source)));
    });
    return edges.map((edge, i) => ({ ...edge, manual: Boolean(wires[edge.id]), blocked: blocked[i], points: paths[i],
      path: paths[i].map((p, j) => `${j ? "L" : "M"} ${p.x} ${p.y}`).join(" ") }));
  }
  return { width, height, boxHeight, pinOffset, boxName, nodes, automatic, valid, canPlace, connections, routes, rectangles, clear,
    validPoints, manualPath, usablePath, moveSegment };
})();

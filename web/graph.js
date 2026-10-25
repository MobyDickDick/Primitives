"use strict";

// Geometry is independent of signal values, so toggling an input keeps the layout.
globalThis.CircuitGraph = (() => {
  const width = 196, height = 84, clearance = 12;
  const boxName = ref => `Box ${ref}`;

  function nodes(c) {
    const result = Array.from({ length: c.inputs }, (_, ref) => ({ ref, kind: "input", index: ref, sources: [], level: 0 }));
    c.gates.forEach((sources, index) => result.push({ ref: result.length, kind: "gate", index, sources, level: 1 + Math.max(...sources.map(r => result[r].level)) }));
    const level = 1 + Math.max(...result.map(n => n.level));
    c.outputs.forEach((source, index) => result.push({ ref: result.length, kind: "output", index, sources: [source], level }));
    return result;
  }

  function automatic(c) {
    const list = nodes(c), layers = [], positions = [];
    list.forEach(n => (layers[n.level] ||= []).push(n.ref));
    const totalHeight = Math.max(300, (Math.max(...layers.map(l => l.length)) + 1) * 132);
    const place = () => layers.forEach((layer, level) => layer.forEach((ref, i) => {
      positions[ref] = { x: 40 + level * 288, y: (i + 1) * totalHeight / (layer.length + 1) };
    }));
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
      p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 20 && p.y >= height / 2 + 20 && p.x <= 99000 && p.y <= 99000);
  }

  function canPlace(positions, ref, point) {
    return positions.every((p, i) => i === ref || Math.abs(point.x - p.x) >= width + 44 || Math.abs(point.y - p.y) >= height + 36);
  }

  function connections(c, positions) {
    return nodes(c).flatMap(node => {
      // NAND is commutative: the upper source always uses the upper port.
      const sources = [...node.sources].sort((a, b) => positions[a].y - positions[b].y || a - b);
      return sources.map((source, port) => ({ source, target: node.ref, port,
        start: { x: positions[source].x + width, y: positions[source].y },
        end: { x: positions[node.ref].x, y: positions[node.ref].y + (sources.length === 2 ? (port ? 18 : -18) : 0) } }));
    });
  }

  function rectangles(positions) {
    return positions.map(p => ({ left: p.x - clearance, right: p.x + width + clearance,
      top: p.y - height / 2 - clearance, bottom: p.y + height / 2 + clearance }));
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

  function routes(c, positions) {
    const obstacles = rectangles(positions), paths = [];
    const edges = connections(c, positions);
    edges.forEach(edge => paths.push(route(edge, obstacles,
      paths.filter((_, i) => edges[i].source !== edge.source))));
    return edges.map((edge, i) => ({ ...edge, points: paths[i], path: paths[i].map((p, j) => `${j ? "L" : "M"} ${p.x} ${p.y}`).join(" ") }));
  }
  return { width, height, boxName, nodes, automatic, valid, canPlace, connections, routes, rectangles, clear };
})();

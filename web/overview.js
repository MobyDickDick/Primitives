"use strict";

// Presentation only: stable box refs and bit-wire IDs always belong to the
// original graph. Bundling, tracing and filtering never rewrite its circuit.
globalThis.CircuitOverview = (() => {
  const portAt = (ports, slot) => ports?.find(p => p.offset <= slot && slot < p.offset + p.bits);
  const signal = (node, slot = 0) => node.signalRefs?.[slot] ?? (node.kind === "output" ? node.sources[0] : node.ref);
  const range = p => `${p.name}[0…${p.bits - 1}]`;

  function project(c, positions, spec, bundled) {
    const nodes = CircuitGraph.nodes(c), edges = CircuitGraph.connections(c, positions);
    const hidden = new Set(), groups = new Map(), boundary = new Map();
    if (bundled) for (const side of ["inputs", "outputs"]) for (const p of spec?.[side] || []) {
      if (p.bits < 2) continue;
      const members = nodes.filter(n => n.kind === (side === "inputs" ? "input" : "output") && n.index >= p.offset && n.index < p.offset + p.bits);
      if (members.length !== p.bits) continue;
      const first = members[0];
      groups.set(first.ref, { port: p, members, side });
      members.forEach((n, i) => { boundary.set(n.ref, first.ref); if (i) hidden.add(n.ref); });
    }
    function endpoint(ref, side, slot) {
      const n = nodes[ref], groupRef = boundary.get(ref);
      if (groupRef !== undefined) {
        const g = groups.get(groupRef);
        return { ref: groupRef, key: `${groupRef}:${g.port.name}`, label: g.port.name,
          bit: n.index - g.port.offset, point: { x: positions[groupRef].x + (side === "outputs" ? CircuitGraph.width : 0), y: positions[groupRef].y } };
      }
      const p = n.kind === "instance" ? portAt(n.interface?.[side], slot) : null;
      const count = side === "inputs" ? n.sources.length : n.signalRefs?.length || 1;
      const pin = p && bundled ? p.offset + (p.bits - 1) / 2 : slot;
      return { ref, key: `${ref}:${p?.name ?? slot}`, label: p?.name || n.label || `Box ${ref}`,
        bit: p ? slot - p.offset : slot,
        point: { x: positions[ref].x + (side === "outputs" ? CircuitGraph.width : 0),
          y: positions[ref].y + (n.kind === "instance" ? CircuitGraph.pinOffset(count, pin) : 0) } };
    }
    const bundles = new Map();
    for (const edge of edges) {
      const from = endpoint(edge.source, "outputs", edge.sourceBit), to = endpoint(edge.target, "inputs", edge.port);
      const key = bundled ? `${from.key}>${to.key}` : edge.id;
      if (!bundles.has(key)) bundles.set(key, { ...edge, id: key, source: from.ref, target: to.ref,
        start: from.point, end: to.point, members: [], mappings: [], from: from.label, to: to.label });
      const bus = bundles.get(key);
      bus.members.push(edge); bus.mappings.push(`${from.label}[${from.bit}] → ${to.label}[${to.bit}]`);
    }
    const wires = [...bundles.values()].map(bus => bus.members.length > 1
      ? { ...bus, bus: true, label: `${bus.from} → ${bus.to} · ${bus.members.length} Bit` }
      : { ...bus.members[0], members: bus.members, mappings: bus.mappings });
    // Single wires attached to a collapsed boundary still terminate at its box.
    if (bundled) for (const wire of wires) if (!wire.bus) {
      const edge = wire.members[0];
      const a = endpoint(edge.source, "outputs", edge.sourceBit), b = endpoint(edge.target, "inputs", edge.port);
      if (boundary.has(edge.source) || nodes[edge.source].kind === "instance") { wire.source = a.ref; wire.start = a.point; }
      if (boundary.has(edge.target) || nodes[edge.target].kind === "instance") { wire.target = b.ref; wire.end = b.point; }
      wire.displayOnly = wire.start.x !== edge.start.x || wire.start.y !== edge.start.y || wire.end.x !== edge.end.x || wire.end.y !== edge.end.y;
    }
    return { nodes, wires, hidden, groups };
  }

  function route(view, positions, manual = {}) {
    const obstacles = CircuitGraph.rectangles(positions).filter((_, i) => !view.hidden.has(i)), paths = [];
    return view.wires.map(edge => {
      const saved = !edge.bus && manual[edge.id] && CircuitGraph.manualPath(edge, manual[edge.id]);
      const usable = saved && CircuitGraph.usablePath(edge, saved, positions);
      const points = usable ? saved : CircuitGraph.route(edge, obstacles, paths);
      paths.push(points);
      return { ...edge, points, path: points.map((p, i) => `${i ? "L" : "M"} ${p.x} ${p.y}`).join(" "),
        manual: Boolean(!edge.bus && manual[edge.id]), blocked: Boolean(saved && !usable) };
    });
  }

  function trace(c, ref, direction = "sources", outputIndex = null) {
    const count = c.inputs + c.gates.length;
    if (!Number.isInteger(ref) || ref < 0 || ref >= count) return null;
    const upstream = new Set(), downstream = new Set(), ancestors = new Map();
    const parents = r => r < c.inputs ? [] : c.gates[r - c.inputs];
    const visit = (r, set, next) => { if (set.has(r)) return; set.add(r); for (const p of next(r)) visit(p, set, next); };
    visit(ref, upstream, parents);
    const children = Array.from({ length: count }, () => []);
    c.gates.forEach((inputs, i) => inputs.forEach(r => children[r].push(c.inputs + i)));
    visit(ref, downstream, r => children[r]);
    const signals = direction === "both" ? new Set([...upstream, ...downstream]) : upstream;
    const isAncestor = (a, b) => {
      if (!ancestors.has(b)) { const set = new Set(); visit(b, set, parents); ancestors.set(b, set); }
      return ancestors.get(b).has(a);
    };
    const nodeSignals = n => [...(n.signalRefs || [signal(n)]), ...(n.gateRefs || [])];
    const node = n => {
      const refs = nodeSignals(n);
      if (n.kind === "output") return outputIndex === null
        ? refs.some(r => r === ref || direction === "both" && downstream.has(r))
        : n.index === outputIndex && refs.some(r => signals.has(r));
      return refs.some(r => signals.has(r));
    };
    const edge = (wire, nodes) => {
      const a = signal(nodes[wire.source], wire.sourceBit), target = nodes[wire.target];
      if (!node(target)) return false;
      const outputs = nodeSignals(target);
      // For fan-out only include edges on a path from the selected signal.
      return outputs.some(b => (upstream.has(a) && upstream.has(b) && isAncestor(a, b)) ||
        (direction === "both" && downstream.has(a) && downstream.has(b) && isAncestor(a, b)));
    };
    return { signals, upstream, downstream, node, edge };
  }
  return { project, route, trace, signal, range };
})();

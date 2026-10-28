"use strict";

// A schedule separates presentation steps from the topological NAND storage order.
globalThis.CircuitPlayback = (() => {
  function plan(c, mode = "layers") {
    const levels = Array(c.inputs).fill(0);
    c.gates.forEach(([a, b]) => levels.push(1 + Math.max(levels[a], levels[b])));
    const hierarchy = mode !== "gates" && c.view_nodes;
    const nodes = hierarchy ? c.view_nodes.filter(n => n.kind === "instance" || n.kind === "gate") : [];
    const groups = [];
    if (hierarchy) {
      for (const node of nodes) {
        const index = mode === "blocks" ? groups.length : node.level - 1;
        (groups[index] ||= []).push(node);
      }
    } else if (mode === "gates") {
      c.gates.forEach((_, i) => groups.push([{ ref: c.inputs + i, signalRefs: [c.inputs + i] }]));
    } else {
      c.gates.forEach((_, i) => (groups[levels[c.inputs + i] - 1] ||= []).push({ ref: c.inputs + i, signalRefs: [c.inputs + i] }));
    }
    const stages = groups.filter(Boolean).map((group, i) => ({
      refs: group.map(n => n.ref),
      label: hierarchy ? group.map(n => n.name || n.id || `NAND ${n.ref}`).join(" · ") :
        mode === "gates" ? `NAND ${i + 1}` : `Logikstufe ${i + 1} · ${group.length} NAND${group.length === 1 ? "" : "s"}`,
      signals: group.flatMap(n => n.signalRefs)
    }));
    const signalStep = Array(c.inputs + c.gates.length).fill(Infinity);
    for (let i = 0; i < c.inputs; i++) signalStep[i] = 0;
    stages.forEach((stage, i) => stage.signals.forEach(ref => {
      // A wiring-only FBox can forward a signal already known at its input.
      signalStep[ref] = Math.min(signalStep[ref], i + 1);
    }));
    return { stages, ready: (ref, step) => step >= stages.length || signalStep[ref] <= step };
  }
  return { plan };
})();

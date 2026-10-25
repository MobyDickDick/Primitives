"use strict";

// A local test owns its input vector; parent frames never read those hand values.
globalThis.BlockDebug = (() => {
  const frameKeys = ["bits", "positions", "wires", "selectedRef", "selectedWire", "wireNotice",
    "layoutDirty", "routing", "camera", "cameraTouched"];
  function number(bits, port) {
    let value = bits.slice(port.offset, port.offset + port.bits).reduce((sum, bit, i) => sum + bit * 2 ** i, 0);
    if (port.signed && value >= 2 ** (port.bits - 1)) value -= 2 ** port.bits;
    return value;
  }
  function withNumber(bits, port, value) {
    const min = port.signed ? -(2 ** (port.bits - 1)) : 0;
    const max = 2 ** (port.bits - (port.signed ? 1 : 0)) - 1;
    if (!Number.isSafeInteger(value) || value < min || value > max) throw new Error(`${port.name}: ganze Zahl von ${min} bis ${max} erforderlich.`);
    const result = bits.slice(), unsigned = value < 0 ? value + 2 ** port.bits : value;
    for (let i = 0; i < port.bits; i++) result[port.offset + i] = Math.floor(unsigned / 2 ** i) % 2;
    return result;
  }
  const positions = (c, points) => points?.map((p, i) => ({ x: p.x, y: p.y,
    ...(c.view_nodes?.[i]?.height && c.view_nodes[i].height !== CircuitGraph.height ? { height: c.view_nodes[i].height } : {}) }));
  function capture() {
    return { ...Object.fromEntries(frameKeys.map(k => [k, state[k]])), step: int("step"),
      path: state.debug.path, view: state.debug.view, initialBits: state.debug.initialBits };
  }
  function request() { return { block: state.debug.bundle, path: state.debug.path }; }
  async function activate(view, path, bits) {
    stopAnimation();
    const debug = state.debug, cached = debug.cache.get(JSON.stringify(path));
    debug.view = view; debug.path = path; debug.initialBits = bits.slice();
    state.bits = bits.slice(); state.selectedRef = 0; state.selectedWire = null; state.wireNotice = "";
    state.positions = cached?.positions || CircuitGraph.automatic(view.circuit);
    state.wires = cached?.wires || {}; state.camera = cached?.camera || null;
    state.cameraTouched = cached?.cameraTouched || false;
    state.layoutDirty = cached?.layoutDirty || false; state.routing = null; state.drag = null;
    $("step").max = view.circuit.gates.length; $("step").value = view.circuit.gates.length;
    const token = ++state.layoutToken;
    buildPanel(); renderSimulation(); renderTable();
    $("layout-status").textContent = state.layoutDirty ? "Layout geändert · noch nicht gespeichert." : "Instanzlayout wird geladen …";
    if (cached) { $("layout-status").textContent = state.layoutDirty ? "Layout geändert · noch nicht gespeichert." : "Instanzansicht wiederhergestellt."; return; }
    const saved = await api("/api/blocks/layout/load", request());
    if (state.debug !== debug || token !== state.layoutToken || state.layoutDirty || state.drag) return;
    const points = positions(view.circuit, saved.positions);
    if (CircuitGraph.valid(view.circuit, points) && points.every((p, i) => CircuitGraph.canPlace(points, i, p))) {
      state.positions = points; state.wires = saved.wires; state.routing = null;
      if (!state.cameraTouched) state.camera = null;
      renderSimulation();
      $("layout-status").textContent = "Gespeichertes Instanzlayout geladen.";
    } else $("layout-status").textContent = "Automatische Anordnung · Layout pro Instanz speicherbar.";
  }
  async function start(result) {
    const token = state.layoutToken;
    const view = await api("/api/blocks/view", { block: result.hierarchy });
    if (state.result !== result || state.layoutToken !== token) return;
    state.debug = { bundle: result.hierarchy, path: [], view, stack: [], cache: new Map() };
    await activate(view, [], state.bits);
  }
  async function enter(node) {
    const debug = state.debug, token = state.layoutToken;
    const path = [...debug.path, node.id];
    const view = await api("/api/blocks/view", { block: debug.bundle, path });
    if (state.debug !== debug || token !== state.layoutToken) return;
    const values = evaluate(debug.view.circuit, state.bits).wires;
    const bits = node.inputRefs.map(r => values[r]);
    debug.stack.push(capture());
    debug.cache.set(JSON.stringify(debug.path), capture());
    await activate(view, path, bits);
  }
  function back() {
    stopAnimation();
    const debug = state.debug, frame = debug.stack.pop();
    if (!frame) return;
    debug.cache.set(JSON.stringify(debug.path), capture());
    for (const k of frameKeys) state[k] = frame[k];
    Object.assign(debug, { path: frame.path, view: frame.view, initialBits: frame.initialBits });
    state.drag = null; ++state.layoutToken;
    $("step").max = frame.view.circuit.gates.length; $("step").value = frame.step;
    buildPanel(); renderSimulation(); renderTable();
    $("layout-status").textContent = state.layoutDirty ? "Layout geändert · noch nicht gespeichert." : "Übergeordnete Ansicht wiederhergestellt.";
  }
  function buildPanel() {
    $("block-debug").hidden = false;
    $("debug-back").disabled = !state.debug.stack.length;
    $("debug-inputs").replaceChildren();
    for (const p of state.debug.view.interface.inputs) {
      const label = el("label", `${p.name} · ${p.bits} Bit${p.signed ? " · Zweierkomplement" : " · unsigned"}`);
      const input = el("input"); input.type = "number"; input.step = "1";
      input.min = p.signed ? -(2 ** (p.bits - 1)) : 0;
      input.max = 2 ** (p.bits - (p.signed ? 1 : 0)) - 1;
      input.dataset.port = p.name;
      input.addEventListener("input", () => {
        try {
          if (input.value === "") throw new Error("Bitte eine ganze Zahl eingeben.");
          const bits = withNumber(state.bits, p, Number(input.value));
          input.setCustomValidity(""); stopAnimation(); state.bits = bits; renderSimulation(); renderTable();
          $("debug-input-status").textContent = "";
        } catch (err) { input.setCustomValidity(err.message); $("debug-input-status").textContent = err.message; }
      });
      label.append(input); $("debug-inputs").append(label);
    }
  }
  function render(values, ready) {
    const debug = state.debug;
    if (!debug) { $("block-debug").hidden = true; return; }
    const view = debug.view;
    $("debug-path").textContent = `${["Wurzel", ...debug.path].join(" / ")} · ${view.name} v${view.version}`;
    $("debug-mode").textContent = debug.path.length
      ? "Lokaler Handtest: Eingänge wurden von den Quellen übernommen. Änderungen gelten nur hier. Zurück zeigt wieder die tatsächlichen Signale der übergeordneten Schaltung."
      : "Verdrahtete NAND-Implementierung. Unterprogramm-Box anklicken oder mit Enter öffnen. Eingänge hier bestimmen das Gesamtschema.";
    for (const p of view.interface.inputs) {
      const input = Array.from($("debug-inputs").querySelectorAll("input")).find(i => i.dataset.port === p.name);
      if (document.activeElement !== input) { input.value = number(state.bits, p); input.setCustomValidity(""); }
    }
    const outputs = view.circuit.outputs.map(r => values[r]);
    $("debug-outputs").replaceChildren(...view.interface.outputs.map(p => {
      const known = view.circuit.outputs.slice(p.offset, p.offset + p.bits).every(ready);
      return el("div", `${p.name}[${p.bits}] = ${known ? number(outputs, p) : "·"} · Bits (LSB): ${view.circuit.outputs.slice(p.offset, p.offset + p.bits).map(r => ready(r) ? values[r] : "·").join(" ")}`);
    }));
  }
  function init() {
    action("debug-back", back);
    action("debug-reset", () => {
      stopAnimation(); state.bits = state.debug.initialBits.slice(); $("step").value = 0;
      $("debug-input-status").textContent = ""; renderSimulation(); renderTable();
    });
    action("debug-next", () => { stopAnimation(); $("step").value = Math.min(int("step") + 1, simulationCircuit().gates.length); renderSimulation(); });
    action("debug-finish", () => { stopAnimation(); $("step").value = simulationCircuit().gates.length; renderSimulation(); });
  }
  return { number, withNumber, positions, start, enter, back, request, render, init };
})();

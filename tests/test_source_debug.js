"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const source = fs.readFileSync(require("node:path").join(__dirname, "../web/app.js"), "utf8");
const code = source.slice(source.indexOf("const sourceDebug ="), source.indexOf('action("cancel-vectors"'));

function setup() {
  const elements = new Map(), actions = {}, calls = [];
  const snapshot = { id: "one", status: "paused", pc: 0, line: 1, operation: "assign",
    instructions: 0, steps: 0, iterations: 0, variables: { n: "5" }, result: null };
  const context = {
    $: id => {
      if (!elements.has(id)) elements.set(id, { value: id === "source-program" ? "s = 0\nreturn s" : "5",
        replaceChildren(...children) { this.children = children; } });
      return elements.get(id);
    },
    el: (tag, textContent) => ({ tag, textContent }),
    int: () => 5, readPorts: () => ({ spec: {} }),
    action: (name, fn) => { actions[name.replace("source-debug-", "")] = fn; },
    api: async (path, body) => { calls.push({ path, body }); return { ...snapshot }; },
    setTimeout: fn => setTimeout(fn, 0)
  };
  vm.createContext(context); vm.runInContext(code, context);
  return { context, elements, actions, calls, snapshot };
}

test("start captures the source and reset restores the same input through its session", async () => {
  const ui = setup();
  await ui.actions.start();
  assert.equal(ui.calls[0].path, "/api/source-debug/start");
  assert.equal(ui.calls[0].body.program.source, "s = 0\nreturn s");
  assert.equal(ui.elements.get("source-debug-step").disabled, false);
  ui.elements.get("source-program").value = "return 99";
  await ui.actions.reset();
  assert.equal(ui.calls[1].path, "/api/source-debug/one/reset");
  assert.match(ui.elements.get("source-debug-code").children[0].textContent, /s = 0/);
});

test("continue displays completed result and disables further steps", async () => {
  const ui = setup(); await ui.actions.start();
  Object.assign(ui.snapshot, { status: "done", result: ["10"], outputs: { c: 10 } });
  await ui.actions.continue();
  assert.match(ui.elements.get("source-debug-result").textContent, /return 10/);
  assert.equal(ui.elements.get("source-debug-step").disabled, true);
  assert.equal(ui.elements.get("source-debug-stop").disabled, true);
  assert.equal(ui.elements.get("source-debug-reset").disabled, false);
});

test("stop waits for the current batch and prevents another continue request", async () => {
  const ui = setup(); await ui.actions.start();
  let finish;
  ui.context.api = async path => {
    ui.calls.push({ path });
    if (path.endsWith("/continue")) return new Promise(resolve => { finish = resolve; });
    return { ...ui.snapshot, status: "stopped" };
  };
  const run = ui.actions.continue();
  assert.equal(ui.elements.get("source-debug-start").disabled, true);
  const stop = ui.actions.stop();
  finish({ ...ui.snapshot });
  await Promise.all([run, stop]);
  assert.equal(ui.calls.filter(c => c.path.endsWith("/continue")).length, 1);
  assert.match(ui.elements.get("source-debug-status").textContent, /Gestoppt/);
  assert.equal(ui.elements.get("source-debug-continue").disabled, false);
});

test("network failure releases controls and source is rendered as literal text", async () => {
  const ui = setup();
  ui.context.$("source-program").value = '# <img onerror="bad">\nreturn n';
  await ui.actions.start();
  assert.match(ui.elements.get("source-debug-code").children[0].textContent, /<img/);
  ui.context.api = async () => { throw new Error("offline"); };
  await assert.rejects(ui.actions.continue(), /offline/);
  assert.equal(ui.elements.get("source-debug-start").disabled, false);
  assert.equal(ui.elements.get("source-debug-stop").disabled, true);
});

"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const source = fs.readFileSync(path.join(__dirname, "../web/app.js"), "utf8");
const filtering = source.slice(source.indexOf("function filterFunctions("), source.indexOf('$("function-search").addEventListener'));

function node(kind, name, children = [], description = "") {
  return { classList: { contains: value => value === `library-${kind}` },
    dataset: { id: name, name, search: `${name} ${description}` }, children, hidden: false, open: true,
    querySelector: () => ({ children }),
    querySelectorAll: selector => {
      const descendants = children.flatMap(child => [child, ...child.querySelectorAll("*")]);
      return selector === "*" ? descendants : descendants.filter(child => child.classList.contains(selector.slice(1)));
    } };
}

function setup() {
  const add = node("leaf", "addition"), div = node("leaf", "division");
  const templates = node("folder", "templates", [add, div], "addition und division");
  const root = node("root", "root", [node("folder", "beispiele", [templates])]);
  const elements = { "library-tree": root, "function-search": { value: "" }, "function-count": {}, "function-no-match": {} };
  const context = { $: id => elements[id], state: { folderOpen: { templates: false } } };
  vm.createContext(context); vm.runInContext(filtering, context);
  return { add, div, templates, elements, filter: query => { elements["function-search"].value = query; context.filterFunctions(); } };
}

test("matching a folder description preserves paths without matching unrelated entries", () => {
  const ui = setup(); ui.filter("division");
  assert.equal(ui.add.hidden, true);
  assert.equal(ui.div.hidden, false);
  assert.equal(ui.templates.open, true);
  assert.equal(ui.elements["function-count"].textContent, "1 von 2 Einträgen · Templates und Funktionen");
});

test("matching a folder name includes its subtree and clearing restores collapsed folders", () => {
  const ui = setup(); ui.filter("beispiele");
  assert.equal(ui.add.hidden, false); assert.equal(ui.div.hidden, false);
  assert.equal(ui.templates.open, true);
  ui.filter(""); assert.equal(ui.templates.open, false);
});

test("a missing search term hides empty branches and shows the no-match message", () => {
  const ui = setup(); ui.filter("unbekannt");
  assert.equal(ui.templates.hidden, true);
  assert.equal(ui.elements["function-no-match"].hidden, false);
});

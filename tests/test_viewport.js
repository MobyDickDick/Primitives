"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
require("../web/viewport.js");
const viewport = globalThis.CircuitViewport;
const size = { width: 720, height: 420 };
function near(a, b) { assert.ok(Math.abs(a - b) < 1e-7, `${a} != ${b}`); }

test("zoom preserves the world point under the pointer, including at both limits", () => {
  const camera = { x: 1400, y: 800, scale: 0.4 }, point = { x: 127, y: 319 };
  const anchor = viewport.worldAt(camera, size, point);
  for (const scale of [0.8, 1, 4, 100, 0.00001]) {
    const zoomed = viewport.zoom(camera, size, scale, point);
    const actual = viewport.worldAt(zoomed, size, point);
    near(actual.x, anchor.x); near(actual.y, anchor.y);
    assert.ok(zoomed.scale >= viewport.minScale && zoomed.scale <= viewport.maxScale);
  }
});

test("100 percent keeps the view centre and pan follows the pointer at different scales", () => {
  for (const scale of [0.1, 0.5, 1, 4]) {
    const camera = { x: -200, y: 700, scale };
    assert.deepEqual(viewport.zoom(camera, size, 1), { x: -200, y: 700, scale: 1 });
    const before = viewport.worldAt(camera, size, { x: 70, y: 90 });
    const after = viewport.worldAt(viewport.pan(camera, 80, -40), size, { x: 150, y: 50 });
    near(before.x, after.x); near(before.y, after.y);
  }
});

test("fit contains wide, tall and small circuits with padding at desktop and mobile sizes", () => {
  for (const viewSize of [size, { width: 280, height: 280 }]) {
    for (const bounds of [
      { left: -50, right: 100000, top: 0, bottom: 400 },
      { left: 20, right: 216, top: -100, bottom: 6000 },
      { left: 40, right: 520, top: 100, bottom: 300 }
    ]) {
      const camera = viewport.fit(bounds, viewSize);
      const topLeft = viewport.worldAt(camera, viewSize, { x: 24, y: 24 });
      const bottomRight = viewport.worldAt(camera, viewSize, { x: viewSize.width - 24, y: viewSize.height - 24 });
      assert.ok(topLeft.x <= bounds.left + 1e-7 && topLeft.y <= bounds.top + 1e-7);
      assert.ok(bottomRight.x >= bounds.right - 1e-7 && bottomRight.y >= bounds.bottom - 1e-7);
      assert.ok(camera.scale <= 1, "initial fit should not enlarge small circuits");
    }
  }
});

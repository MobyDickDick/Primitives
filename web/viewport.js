"use strict";

// The camera uses world coordinates; scale is CSS pixels per world unit.
globalThis.CircuitViewport = (() => {
  const minScale = 0.001, maxScale = 4;
  const clamp = scale => Math.max(minScale, Math.min(maxScale, scale));
  function worldAt(camera, size, point) {
    return { x: camera.x + (point.x - size.width / 2) / camera.scale,
      y: camera.y + (point.y - size.height / 2) / camera.scale };
  }
  function zoom(camera, size, scale, point = { x: size.width / 2, y: size.height / 2 }) {
    const anchor = worldAt(camera, size, point), next = clamp(scale);
    return { x: anchor.x - (point.x - size.width / 2) / next,
      y: anchor.y - (point.y - size.height / 2) / next, scale: next };
  }
  function pan(camera, dx, dy) {
    return { ...camera, x: camera.x - dx / camera.scale, y: camera.y - dy / camera.scale };
  }
  function fit(bounds, size, padding = 24) {
    return { x: (bounds.left + bounds.right) / 2, y: (bounds.top + bounds.bottom) / 2,
      scale: clamp(Math.min(Math.max(1, size.width - 2 * padding) / Math.max(1, bounds.right - bounds.left),
        Math.max(1, size.height - 2 * padding) / Math.max(1, bounds.bottom - bounds.top), 1)) };
  }
  return { minScale, maxScale, worldAt, zoom, pan, fit };
})();

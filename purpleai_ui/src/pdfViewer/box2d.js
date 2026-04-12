import { getViewerConfig } from './viewerConfig.js';

/**
 * Normalize corners to 0–1000 integers.
 * Accepts 0–1 floats (some model outputs).
 */
export function normalizeRawBox(raw) {
  if (!Array.isArray(raw) || raw.length !== 4) return null;
  let nums = raw.map(Number);
  if (nums.some((n) => Number.isNaN(n))) return null;
  if (nums.every((n) => n >= 0 && n <= 1)) {
    nums = nums.map((n) => n * 1000);
  }
  return nums;
}

function packBox(y0, x0, y1, x1) {
  const { box2dMaxSpan } = getViewerConfig();
  if ([y0, x0, y1, x1].some((v) => v < 0 || v > 1000)) return null;
  if (x1 <= x0 || y1 <= y0) return null;
  if (x1 - x0 > box2dMaxSpan || y1 - y0 > box2dMaxSpan) return null;
  const w = x1 - x0;
  const h = y1 - y0;
  const aspect = w / h;
  return { y0, x0, y1, x1, aspect };
}

export function parseBox2d(raw) {
  const nums = normalizeRawBox(raw);
  if (!nums) return null;
  const [a, b, c, d] = nums;

  const optA = packBox(a, b, c, d);
  const optB = packBox(b, a, d, c);

  if (optA && !optB) return [optA.y0, optA.x0, optA.y1, optA.x1];
  if (optB && !optA) return [optB.y0, optB.x0, optB.y1, optB.x1];
  if (!optA && !optB) return null;

  function aspectScore(o) {
    const r = o.aspect;
    if (r >= 0.35 && r <= 10) return 3;
    if (r >= 0.18 && r <= 16) return 2;
    if (r >= 0.06 && r <= 40) return 1;
    return 0;
  }
  const sA = aspectScore(optA);
  const sB = aspectScore(optB);
  if (sB > sA) return [optB.y0, optB.x0, optB.y1, optB.x1];
  if (sA > sB) return [optA.y0, optA.x0, optA.y1, optA.x1];
  return [optA.y0, optA.x0, optA.y1, optA.x1];
}

/** If aspect heuristics reject the box, still map valid 0–1000 corners (y0,x0,y1,x1). */
export function parseBox2dRelaxed(raw) {
  const nums = normalizeRawBox(raw);
  if (!nums) return null;
  const [a, b, c, d] = nums;
  const y0 = Math.min(a, c);
  const y1 = Math.max(a, c);
  const x0 = Math.min(b, d);
  const x1 = Math.max(b, d);
  if (x1 <= x0 || y1 <= y0) return null;
  if (y0 < 0 || x0 < 0 || y1 > 1000 || x1 > 1000) return null;
  return [y0, x0, y1, x1];
}

/** Pixel box from model box_2d (viewport pixels). */
export function box2dToPixelStyle(box, pageW, pageH) {
  const { highlightPadPx } = getViewerConfig();
  const padX = highlightPadPx.x;
  const padY = highlightPadPx.y;
  const parsed = parseBox2d(box) || parseBox2dRelaxed(box);
  if (!parsed || pageW <= 0 || pageH <= 0) return null;
  const [y0, x0, y1, x1] = parsed;
  const left = (x0 / 1000) * pageW;
  const top = (y0 / 1000) * pageH;
  const width = ((x1 - x0) / 1000) * pageW;
  const height = ((y1 - y0) / 1000) * pageH;
  return {
    left: `${Math.max(0, left - padX)}px`,
    top: `${Math.max(0, top - padY)}px`,
    width: `${Math.max(4, width + padX * 2)}px`,
    height: `${Math.max(4, height + padY * 2)}px`,
  };
}

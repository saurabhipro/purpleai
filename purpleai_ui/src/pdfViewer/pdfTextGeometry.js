import { getViewerConfig } from './viewerConfig.js';

export function itemPdfRect(item) {
  const m = item.transform;
  const x = m[4];
  const y = m[5];
  const w = item.width || 0;
  const h = Math.abs(m[3]) || item.height || 10;
  return { x, y, w, h };
}

/** PDF user space → viewport CSS box (top-left origin, matches canvas). */
export function pdfRectToViewportStyle(rect, viewport) {
  const { highlightPadPx } = getViewerConfig();
  const padX = highlightPadPx.x;
  const padY = highlightPadPx.y;
  const { x, y, w, h } = rect;
  const pts = [
    viewport.convertToViewportPoint(x, y),
    viewport.convertToViewportPoint(x + w, y),
    viewport.convertToViewportPoint(x, y + h),
    viewport.convertToViewportPoint(x + w, y + h),
  ];
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const left = Math.min(...xs);
  const top = Math.min(...ys);
  const right = Math.max(...xs);
  const bottom = Math.max(...ys);
  return {
    left: `${Math.max(0, left - padX)}px`,
    top: `${Math.max(0, top - padY)}px`,
    width: `${Math.max(4, right - left + padX * 2)}px`,
    height: `${Math.max(4, bottom - top + padY * 2)}px`,
  };
}

export function parseCssPx(style) {
  if (!style) return null;
  return {
    left: parseFloat(style.left) || 0,
    top: parseFloat(style.top) || 0,
    width: parseFloat(style.width) || 0,
    height: parseFloat(style.height) || 0,
  };
}

export function iouPixels(a, b) {
  if (!a || !b || a.width <= 0 || a.height <= 0 || b.width <= 0 || b.height <= 0) return 0;
  const x0 = Math.max(a.left, b.left);
  const y0 = Math.max(a.top, b.top);
  const x1 = Math.min(a.left + a.width, b.left + b.width);
  const y1 = Math.min(a.top + a.height, b.top + b.height);
  const iw = Math.max(0, x1 - x0);
  const ih = Math.max(0, y1 - y0);
  const inter = iw * ih;
  const u = a.width * a.height + b.width * b.height - inter;
  return u <= 0 ? 0 : inter / u;
}

/** Same baseline in PDF user space (handles split glyphs like "684.9" + "0"). */
export function sameTextLine(r1, r2) {
  const h = Math.min(Math.abs(r1.h), Math.abs(r2.h)) || 8;
  return Math.abs(r1.y - r2.y) < Math.max(2.5, 0.35 * h);
}

export function itemsOnSameLine(seedRect, items, rectsMap) {
  return items
    .map((it) => ({ it, r: rectsMap.get(it) }))
    .filter(({ r }) => r && sameTextLine(seedRect, r))
    .sort((a, b) => a.r.x - b.r.x)
    .map(({ it }) => it);
}

export function unionPdfRects(items, rectsMap) {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const it of items) {
    const r = rectsMap.get(it);
    if (!r) continue;
    minX = Math.min(minX, r.x);
    minY = Math.min(minY, r.y);
    maxX = Math.max(maxX, r.x + r.w);
    maxY = Math.max(maxY, r.y + r.h);
  }
  if (!Number.isFinite(minX)) return null;
  return { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
}

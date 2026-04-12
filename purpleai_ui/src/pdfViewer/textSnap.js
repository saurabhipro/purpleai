import { getViewerConfig } from './viewerConfig.js';
import { box2dToPixelStyle } from './box2d.js';
import {
  itemPdfRect,
  pdfRectToViewportStyle,
  parseCssPx,
  iouPixels,
  sameTextLine,
  itemsOnSameLine,
  unionPdfRects,
} from './pdfTextGeometry.js';
import { searchVariantsForSnap } from './searchVariants.js';

export function normToken(s) {
  return String(s).replace(/[\s₹$€,]/g, '');
}

export function normTokenFold(s) {
  return normToken(s).toLowerCase();
}

function minAlphabeticSubMatchLen(compactLen) {
  const { alphabeticSubMinRatio, alphabeticSubMinFloor } = getViewerConfig().snap;
  return Math.max(alphabeticSubMinFloor, Math.floor(alphabeticSubMinRatio * Math.max(compactLen, 1)));
}

function expandExtMatchesTargets(ext, targets) {
  return targets.some((t) => t === ext || (t.startsWith(ext) && ext.length < t.length));
}

function expandRunEqualsTarget(ext, targets) {
  return targets.some((t) => t === ext);
}

export function expandRunOnLine(lineItems, seedIt, targetCompacts) {
  const targets = (Array.isArray(targetCompacts) ? targetCompacts : [targetCompacts]).filter(Boolean);
  if (!targets.length || lineItems.length === 0) return lineItems;
  const idx = lineItems.indexOf(seedIt);
  if (idx < 0) return [seedIt];
  let left = idx;
  let right = idx;
  const joinRange = (l, r) =>
    lineItems
      .slice(l, r + 1)
      .map((it) => normToken(it.str))
      .join('');

  while (right < lineItems.length - 1) {
    const ext = joinRange(left, right + 1);
    if (expandRunEqualsTarget(ext, targets)) {
      right += 1;
      break;
    }
    if (expandExtMatchesTargets(ext, targets)) {
      right += 1;
      continue;
    }
    break;
  }

  while (left > 0) {
    const ext = joinRange(left - 1, right);
    if (
      expandRunEqualsTarget(ext, targets) ||
      targets.some((t) => t.startsWith(ext) && ext.length <= t.length)
    ) {
      left -= 1;
      continue;
    }
    break;
  }

  return lineItems.slice(left, right + 1);
}

function itemMatchesVariant(norm, vv) {
  if (!norm || !vv) return false;
  if (norm === vv) return true;
  if (norm.length < 2) return false;
  if (norm.includes(vv)) return true;
  if (!vv.includes(norm)) return false;
  if (/^\d+[.,]?\d*$/.test(norm)) {
    return norm.length >= 2 && vv.length <= norm.length + 3;
  }
  return norm.length >= minAlphabeticSubMatchLen(vv.length);
}

function clusterLinesPdfSpace(items, rectsMap) {
  const arr = items
    .map((it) => ({ it, r: rectsMap.get(it) }))
    .filter((x) => x.r);
  arr.sort((a, b) => b.r.y - a.r.y || a.r.x - b.r.x);
  const lines = [];
  let cur = [];
  let refR = null;
  for (const { it, r } of arr) {
    if (!cur.length) {
      cur.push(it);
      refR = r;
    } else if (sameTextLine(refR, r)) {
      cur.push(it);
    } else {
      lines.push(cur);
      cur = [it];
      refR = r;
    }
  }
  if (cur.length) lines.push(cur);
  return lines;
}

function collectLinePrefixMatches(items, rectsMap, viewport, targetCompacts) {
  const { minTargetLengthPrefix, maxItemsPerLineScan } = getViewerConfig().snap;
  const targets = [...new Set(targetCompacts)].filter((t) => t.length >= minTargetLengthPrefix);
  if (!targets.length) return [];
  targets.sort((a, b) => b.length - a.length);
  const out = [];
  const lines = clusterLinesPdfSpace(items, rectsMap);
  for (const lineItems of lines) {
    const sorted = [...lineItems].sort((a, b) => rectsMap.get(a).x - rectsMap.get(b).x);
    const n = sorted.length;
    for (let i = 0; i < n; i += 1) {
      let acc = '';
      for (let j = i; j < Math.min(n, i + maxItemsPerLineScan); j += 1) {
        acc += normToken(sorted[j].str);
        if (targets.includes(acc)) {
          const run = sorted.slice(i, j + 1);
          const ur = unionPdfRects(run, rectsMap);
          if (ur) {
            const css = pdfRectToViewportStyle(ur, viewport);
            const px = parseCssPx(css);
            out.push({ css, px, runLen: acc.length, overlap: 0, runText: acc });
          }
        }
        const prefixOk = targets.some((t) => t.startsWith(acc));
        if (acc.length > 0 && !prefixOk) break;
      }
    }
  }
  return out;
}

function collectSubstringLineMatches(items, rectsMap, viewport, targetCompacts) {
  const { minAlphaSubstringTarget } = getViewerConfig().snap;
  const foldedTargets = [
    ...new Set(
      targetCompacts
        .map((t) => normTokenFold(t))
        .filter((t) => t.length >= minAlphaSubstringTarget && /[a-z]/.test(t)),
    ),
  ].sort((a, b) => b.length - a.length);
  if (!foldedTargets.length) return [];
  const out = [];
  const lines = clusterLinesPdfSpace(items, rectsMap);
  for (const lineItems of lines) {
    const sorted = [...lineItems].sort((a, b) => rectsMap.get(a).x - rectsMap.get(b).x);
    if (!sorted.length) continue;
    const spans = [];
    let pos = 0;
    for (const it of sorted) {
      const piece = normTokenFold(it.str);
      const start = pos;
      pos += piece.length;
      spans.push({ it, start, end: pos });
    }
    const joined = sorted.map((it) => normTokenFold(it.str)).join('');
    for (const t of foldedTargets) {
      let from = 0;
      while (from <= joined.length) {
        const idx = joined.indexOf(t, from);
        if (idx < 0) break;
        const end = idx + t.length;
        const run = sorted.filter((it, i) => {
          const { start, end: e } = spans[i];
          return start < end && e > idx;
        });
        if (run.length) {
          const ur = unionPdfRects(run, rectsMap);
          if (ur) {
            const css = pdfRectToViewportStyle(ur, viewport);
            const px = parseCssPx(css);
            out.push({ css, px, runLen: t.length, overlap: 0, runText: t });
          }
        }
        from = idx + 1;
      }
    }
  }
  return out;
}

export function pickBestLineHit(candidates, modelPx) {
  const { iouTrustMin } = getViewerConfig().snap;
  if (!candidates.length) return null;
  const scored = candidates.map((c) => ({
    ...c,
    overlap: modelPx ? iouPixels(c.px, modelPx) : c.overlap,
    centerY: c.px.top + c.px.height / 2,
  }));
  if (modelPx) {
    scored.sort((a, b) => b.overlap - a.overlap);
    const best = scored[0];
    if (best.overlap >= iouTrustMin) return best.css;
  }
  scored.sort((a, b) => {
    if (b.runLen !== a.runLen) return b.runLen - a.runLen;
    return a.centerY - b.centerY;
  });
  return scored[0].css;
}

export function runMatchesTargets(runText, targets) {
  const { minTextMatchShort } = getViewerConfig().snap;
  if (!runText) return false;
  const rf = normTokenFold(runText);
  const tFold = targets.map((t) => normTokenFold(t));
  if (tFold.some((t) => t === rf)) return true;
  return tFold.some((t) => {
    const short = Math.min(rf.length, t.length);
    if (short < minTextMatchShort) return false;
    return rf.startsWith(t) || t.startsWith(rf);
  });
}

/**
 * Snap highlight to pdf.js text items (browser equivalent of Odoo PyMuPDF snap).
 */
export async function snapHighlightToText(page, viewport, rawValue, modelBox2d) {
  const { iouTrustMin } = getViewerConfig().snap;
  const variants = searchVariantsForSnap(rawValue);
  if (!variants.length) return null;
  if (variants.every((v) => String(v).replace(/\s/g, '').length < 2)) return null;

  const targetCompacts = [...new Set(variants.map((v) => normToken(v)).filter(Boolean))].sort(
    (a, b) => b.length - a.length,
  );

  let textContent;
  try {
    textContent = await page.getTextContent();
  } catch {
    return null;
  }

  const items = textContent.items.filter((it) => it.str != null && it.str !== '');
  const rectsMap = new Map(items.map((it) => [it, itemPdfRect(it)]));

  const matchedItems = [];
  const seen = new Set();
  for (const it of items) {
    const norm = normTokenFold(it.str);
    if (!norm) continue;
    for (const v of variants) {
      const vv = normTokenFold(v);
      if (vv.length < 2) continue;
      if (itemMatchesVariant(norm, vv)) {
        if (!seen.has(it)) {
          seen.add(it);
          matchedItems.push(it);
        }
        break;
      }
    }
  }

  const W = viewport.width;
  const H = viewport.height;
  let modelPx = null;
  if (modelBox2d) {
    const st = box2dToPixelStyle(modelBox2d, W, H);
    modelPx = parseCssPx(st);
  }

  const lineHits = [
    ...collectLinePrefixMatches(items, rectsMap, viewport, targetCompacts),
    ...collectSubstringLineMatches(items, rectsMap, viewport, targetCompacts),
  ];

  if (!matchedItems.length) {
    return pickBestLineHit(lineHits, modelPx);
  }

  const scored = matchedItems.map((it) => {
    const line = itemsOnSameLine(rectsMap.get(it), items, rectsMap);
    const run = expandRunOnLine(line, it, targetCompacts);
    const runText = run.map((x) => normToken(x.str)).join('');
    const ur = unionPdfRects(run, rectsMap);
    const css = ur ? pdfRectToViewportStyle(ur, viewport) : pdfRectToViewportStyle(itemPdfRect(it), viewport);
    const px = parseCssPx(css);
    const overlap = modelPx ? iouPixels(px, modelPx) : 0;
    return {
      css,
      px,
      overlap,
      it,
      runText,
      runLen: normTokenFold(runText).length,
    };
  });

  const merged = [...scored, ...lineHits.map((h) => ({ ...h, runLen: h.runLen || normTokenFold(h.runText).length }))];
  merged.forEach((c) => {
    c.overlap = modelPx ? iouPixels(c.px, modelPx) : 0;
  });

  if (modelPx) {
    merged.sort((a, b) => b.overlap - a.overlap);
    const best = merged[0];
    if (best.overlap >= iouTrustMin && runMatchesTargets(best.runText, targetCompacts)) return best.css;
    return null;
  }

  const good = merged.filter((c) => runMatchesTargets(c.runText, targetCompacts));
  const pool = good.length ? good : merged;
  pool.sort((a, b) => {
    if (b.runLen !== a.runLen) return b.runLen - a.runLen;
    return a.px.top - b.px.top;
  });
  return pool[0].css;
}

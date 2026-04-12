/**
 * Central knobs for the PDF evidence viewer (highlight snap, layout).
 * Import and spread overrides where you mount the viewer if needed.
 */
export const defaultViewerConfig = {
  /** Reject model boxes larger than this span in 0–1000 space (matches Odoo). */
  box2dMaxSpan: 700,
  highlightPadPx: { x: 2, y: 1 },
  snap: {
    /** Min IoU(text box, model box) to prefer text snap over falling back to box_2d. */
    iouTrustMin: 0.03,
    minTargetLengthPrefix: 4,
    minAlphaSubstringTarget: 10,
    maxItemsPerLineScan: 28,
    minTextMatchShort: 4,
    alphabeticSubMinRatio: 0.36,
    alphabeticSubMinFloor: 6,
  },
  layout: {
    defaultMaxWidth: 600,
    scrollHorizontalPad: 32,
    minMaxWidth: 200,
    /** Viewer zoom around fitted width (1 = fit panel). */
    defaultZoom: 1,
    zoomMin: 0.5,
    zoomMax: 2.5,
    zoomStep: 0.15,
  },
};

let activeConfig = { ...defaultViewerConfig };

/**
 * Replace viewer config (shallow merge per section).
 * @param {Partial<typeof defaultViewerConfig>} patch
 */
export function setViewerConfig(patch) {
  const prev = activeConfig;
  activeConfig = {
    ...prev,
    ...patch,
    snap: { ...prev.snap, ...(patch.snap || {}) },
    layout: { ...prev.layout, ...(patch.layout || {}) },
  };
}

export function getViewerConfig() {
  return activeConfig;
}

export function resetViewerConfig() {
  activeConfig = { ...defaultViewerConfig };
}

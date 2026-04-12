export { PdfViewerWithHighlights } from './PdfViewerWithHighlights.jsx';
export { PdfPage } from './PdfPage.jsx';
export {
  defaultViewerConfig,
  setViewerConfig,
  getViewerConfig,
  resetViewerConfig,
} from './viewerConfig.js';
export { snapHighlightToText, normToken, normTokenFold, runMatchesTargets } from './textSnap.js';
export { box2dToPixelStyle, parseBox2d, parseBox2dRelaxed, normalizeRawBox } from './box2d.js';
export { searchVariantsForSnap } from './searchVariants.js';
export { pdfjsLib, base64ToUint8Array } from './pdfDocument.js';

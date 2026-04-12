import { useEffect, useRef, useState, useCallback } from 'react';
import { pdfjsLib, base64ToUint8Array } from './pdfDocument.js';
import { getViewerConfig } from './viewerConfig.js';
import { PdfPage } from './PdfPage.jsx';

export function PdfViewerWithHighlights({ pdfBase64, highlight }) {
  const scrollRef = useRef(null);
  const layoutCfg = getViewerConfig().layout;
  const {
    defaultMaxWidth,
    scrollHorizontalPad,
    minMaxWidth,
    defaultZoom,
    zoomMin,
    zoomMax,
    zoomStep,
  } = layoutCfg;
  const [maxWidth, setMaxWidth] = useState(defaultMaxWidth);
  const [zoom, setZoom] = useState(defaultZoom);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [error, setError] = useState('');

  const clampZoom = useCallback(
    (z) => Math.min(zoomMax, Math.max(zoomMin, z)),
    [zoomMin, zoomMax],
  );

  const measure = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    const w = el.clientWidth;
    setMaxWidth(Math.max(minMaxWidth, w - scrollHorizontalPad));
  }, [minMaxWidth, scrollHorizontalPad]);

  useEffect(() => {
    measure();
    const el = scrollRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(() => measure());
    ro.observe(el);
    return () => ro.disconnect();
  }, [measure]);

  useEffect(() => {
    let cancelled = false;
    setPdfDoc(null);
    setNumPages(0);
    setError('');
    if (!pdfBase64) return undefined;
    (async () => {
      try {
        const data = base64ToUint8Array(pdfBase64);
        const loading = pdfjsLib.getDocument({ data, verbosity: 0 });
        const doc = await loading.promise;
        if (cancelled) return;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
      } catch (e) {
        if (!cancelled) {
          console.error(e);
          setError((e && e.message) || 'Failed to load PDF');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfBase64]);

  const scaledMaxWidth = Math.round(Math.max(minMaxWidth, maxWidth * zoom));

  if (error) {
    return <div className="gt-pdf-error">{error}</div>;
  }

  if (!pdfBase64) {
    return <div className="no-pdf">No PDF available</div>;
  }

  return (
    <div className="gt-pdf-scroll-wrap">
      <div className="gt-pdf-toolbar" role="toolbar" aria-label="Document zoom and page">
        <span className="gt-pdf-toolbar-group">
          <button
            type="button"
            className="gt-pdf-tool-btn"
            aria-label="Zoom out"
            onClick={() => setZoom((z) => clampZoom(z - zoomStep))}
          >
            −
          </button>
          <span className="gt-pdf-zoom-label">{Math.round(zoom * 100)}%</span>
          <button
            type="button"
            className="gt-pdf-tool-btn"
            aria-label="Zoom in"
            onClick={() => setZoom((z) => clampZoom(z + zoomStep))}
          >
            +
          </button>
          <button
            type="button"
            className="gt-pdf-tool-btn gt-pdf-tool-btn--text"
            aria-label="Reset zoom to fit width"
            onClick={() => setZoom(defaultZoom)}
          >
            Fit width
          </button>
        </span>
        {numPages > 0 ? (
          <span className="gt-pdf-toolbar-meta">
            {highlight?.pageNumber
              ? `Page ${highlight.pageNumber} of ${numPages}`
              : `${numPages} page${numPages === 1 ? '' : 's'}`}
          </span>
        ) : null}
      </div>
      <div className="gt-pdf-scroll" ref={scrollRef}>
        {pdfDoc &&
          numPages > 0 &&
          Array.from({ length: numPages }, (_, i) => i + 1).map((pn) => (
            <PdfPage
              key={pn}
              pdfDoc={pdfDoc}
              pageNumber={pn}
              maxWidth={scaledMaxWidth}
              highlight={highlight}
            />
          ))}
        {!pdfDoc && pdfBase64 && (
          <div className="viewer-loading">Loading PDF…</div>
        )}
      </div>
    </div>
  );
}

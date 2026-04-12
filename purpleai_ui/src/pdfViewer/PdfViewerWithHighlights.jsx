import { useEffect, useRef, useState, useCallback } from 'react';
import { pdfjsLib, base64ToUint8Array } from './pdfDocument.js';
import { getViewerConfig } from './viewerConfig.js';
import { PdfPage } from './PdfPage.jsx';

export function PdfViewerWithHighlights({ pdfBase64, highlight }) {
  const scrollRef = useRef(null);
  const { defaultMaxWidth, scrollHorizontalPad, minMaxWidth } = getViewerConfig().layout;
  const [maxWidth, setMaxWidth] = useState(defaultMaxWidth);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [error, setError] = useState('');

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

  useEffect(() => {
    if (!highlight || !highlight.pageNumber || !scrollRef.current) return;
    const shell = scrollRef.current.querySelector(
      `.gt-pdf-page-shell[data-page="${highlight.pageNumber}"]`,
    );
    if (shell) {
      shell.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlight]);

  if (error) {
    return <div className="gt-pdf-error">{error}</div>;
  }

  if (!pdfBase64) {
    return <div className="no-pdf">No PDF available</div>;
  }

  return (
    <div className="gt-pdf-scroll-wrap">
      <div className="gt-pdf-scroll" ref={scrollRef}>
        {pdfDoc &&
          numPages > 0 &&
          Array.from({ length: numPages }, (_, i) => i + 1).map((pn) => (
            <PdfPage key={pn} pdfDoc={pdfDoc} pageNumber={pn} maxWidth={maxWidth} highlight={highlight} />
          ))}
        {!pdfDoc && pdfBase64 && (
          <div className="viewer-loading">Loading PDF…</div>
        )}
      </div>
    </div>
  );
}

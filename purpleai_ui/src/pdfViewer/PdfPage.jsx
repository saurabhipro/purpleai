import { useEffect, useRef, useState } from 'react';
import { box2dToPixelStyle } from './box2d.js';
import { snapHighlightToText } from './textSnap.js';

export function PdfPage({ pdfDoc, pageNumber, maxWidth, highlight }) {
  const canvasRef = useRef(null);
  const [pagePx, setPagePx] = useState({ w: 0, h: 0 });
  const [overlayStyle, setOverlayStyle] = useState(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!pdfDoc || !maxWidth) return;
      const page = await pdfDoc.getPage(pageNumber);
      const baseVp = page.getViewport({ scale: 1 });
      const scale = maxWidth / baseVp.width;
      const viewport = page.getViewport({ scale });
      const W = viewport.width;
      const H = viewport.height;
      if (cancelled) return;
      setPagePx({ w: W, h: H });

      const canvas = canvasRef.current;
      if (canvas) {
        const ctx = canvas.getContext('2d');
        if (ctx) {
          canvas.width = W;
          canvas.height = H;
          await page.render({ canvasContext: ctx, viewport }).promise;
        }
      }

      if (cancelled) return;

      if (!highlight || highlight.pageNumber !== pageNumber) {
        setOverlayStyle(null);
        return;
      }

      let style = null;
      const snapVal = highlight.snapValue;
      if (snapVal != null && String(snapVal).trim() !== '') {
        try {
          style = await snapHighlightToText(page, viewport, snapVal, highlight.box2d);
        } catch {
          style = null;
        }
      }
      if (!style && highlight.box2d) {
        style = box2dToPixelStyle(highlight.box2d, W, H);
      }
      if (cancelled || !highlight || highlight.pageNumber !== pageNumber) {
        if (!cancelled) setOverlayStyle(null);
        return;
      }
      if (!cancelled) setOverlayStyle(style);
    })();
    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pageNumber, maxWidth, highlight]);

  const hl = highlight && highlight.pageNumber === pageNumber ? highlight : null;
  const label = hl?.label || '';
  const showOverlay = Boolean(overlayStyle && hl);

  return (
    <div className="gt-pdf-page-shell" data-page={pageNumber}>
      <div
        className="gt-pdf-page-inner"
        style={{
          position: 'relative',
          display: 'inline-block',
          lineHeight: 0,
          verticalAlign: 'top',
          width: pagePx.w > 0 ? pagePx.w : maxWidth,
          height: pagePx.h > 0 ? pagePx.h : undefined,
          minHeight: pagePx.h > 0 ? undefined : 120,
          margin: '0 auto 16px',
          boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
        }}
      >
        <canvas
          ref={canvasRef}
          className="gt-pdf-page-canvas"
          style={
            pagePx.w > 0
              ? {
                  display: 'block',
                  width: pagePx.w,
                  height: pagePx.h,
                  margin: 0,
                  padding: 0,
                }
              : { display: 'block', width: maxWidth, height: 'auto', margin: 0 }
          }
        />
        {showOverlay && hl && (
          <div
            key={hl.fieldKey || hl.label || 'hl'}
            className={`gt-pdf-highlight-box ${hl.variant === 'selected' ? 'is-selected' : 'is-hover'}`}
            style={{
              position: 'absolute',
              ...overlayStyle,
              pointerEvents: 'none',
              zIndex: 2,
              boxSizing: 'border-box',
            }}
            title={label}
          >
            {label ? (
              <span className="gt-pdf-highlight-tag">{label.replace(/_/g, ' ')}</span>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}

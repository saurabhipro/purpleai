import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import * as api from './aiCoreClient';
import gtLogo from './assets/gt_logo.jpeg';
import { Upload, FileText, Settings, LogOut, Loader2, Search, RefreshCw, X } from 'lucide-react';
import { PdfViewerWithHighlights } from './pdfViewer';
import './index.css';

function normalizeExtractedFields(extracted) {
  if (!extracted || typeof extracted !== 'object') return [];
  return Object.entries(extracted)
    .filter(([k]) => k !== 'validations')
    .map(([key, item]) => {
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        const pg = item.page_number != null ? Number(item.page_number) : 1;
        const box = item.box_2d;
        return {
          key,
          value: item.value,
          page_number: Number.isFinite(pg) && pg > 0 ? pg : 1,
          box_2d: Array.isArray(box) && box.length === 4 ? box.map(Number) : null,
        };
      }
      return { key, value: item, page_number: 1, box_2d: null };
    });
}

// --- Sub-Component: Document Viewer ---
function DocumentViewer({ docId, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hoverField, setHoverField] = useState(null);
  const [pinnedField, setPinnedField] = useState(null);

  useEffect(() => {
    setHoverField(null);
    setPinnedField(null);
  }, [docId]);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch(`/purple_invoices/v1/viewer_data/${docId}`, {
          headers: { ...api.authHeaders() },
          credentials: 'include',
        });
        const json = await res.json();
        setData(json);
      } catch (e) {
        console.error("Viewer load failed", e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [docId]);

  const fields = useMemo(() => normalizeExtractedFields(data?.extracted_json), [data?.extracted_json]);

  const activeHighlight = useMemo(() => {
    const h = hoverField || pinnedField;
    if (!h) return null;
    return {
      fieldKey: h.key,
      pageNumber: h.page_number,
      box2d: h.box_2d,
      snapValue: h.value,
      label: h.key,
      variant: hoverField ? 'hover' : 'selected',
    };
  }, [hoverField, pinnedField]);

  if (loading) return <div className="viewer-loading"><Loader2 className="spinning" /></div>;

  return (
    <div className="gt-viewer-overlay">
      <div className="gt-viewer-container animate-fade-in">
        <header className="gt-viewer-header">
          <h3>{data?.filename || 'Document Viewer'}</h3>
          <button className="gt-icon-btn" onClick={onClose}><X size={20} /></button>
        </header>
        <div className="gt-viewer-body">
          <div className="gt-viewer-left">
            <p className="gt-viewer-hint">
              Hover or click a field to highlight it on the PDF. The viewer snaps to real text when possible
              (same idea as Odoo), then falls back to AI coordinates.
            </p>
            {data?.pdf_base64 ? (
              <PdfViewerWithHighlights pdfBase64={data.pdf_base64} highlight={activeHighlight} />
            ) : (
              <div className="no-pdf">No PDF available</div>
            )}
          </div>
          <div className="gt-viewer-right">
            <h4>Extracted Data</h4>
            <div className="gt-data-grid">
              {fields.map((f) => (
                <div
                  key={f.key}
                  role="button"
                  tabIndex={0}
                  className={`gt-data-item ${f.box_2d || (f.value != null && String(f.value).trim() !== '') ? 'gt-data-item--interactive' : ''} ${pinnedField?.key === f.key ? 'gt-data-item--pinned' : ''}`}
                  onMouseEnter={() => setHoverField(f)}
                  onMouseLeave={() => setHoverField(null)}
                  onClick={() =>
                    setPinnedField((p) => (p && p.key === f.key ? null : f))
                  }
                  onKeyDown={(ev) => {
                    if (ev.key === 'Enter' || ev.key === ' ') {
                      ev.preventDefault();
                      setPinnedField((p) => (p && p.key === f.key ? null : f));
                    }
                  }}
                >
                  <label>{f.key}</label>
                  <div className="gt-data-val">
                    {f.value != null && f.value !== '' ? String(f.value) : '—'}
                    <span className="gt-pg-badge">Pg {f.page_number}</span>
                  </div>
                </div>
              ))}
            </div>
            {data?.status === 'processing' && (
              <div className="gt-processing-loader">
                <Loader2 className="spinning" size={16} />
                <span>AI is still analyzing...</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


// --- Main Dashboard ---
export function Dashboard() {
  const [token, setToken] = useState(() => api.devKey());
  const [authRequired, setAuthRequired] = useState(false);
  const [activeEnv, setActiveEnv] = useState('purpleai_invoices');
  const [pingMsg, setPingMsg] = useState('Offline');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [records, setRecords] = useState([]);
  const [viewingId, setViewingId] = useState(null);
  const [invoiceClients, setInvoiceClients] = useState(null);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [clientsApiMissing, setClientsApiMissing] = useState(false);

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!invoiceClients || invoiceClients.length === 0) {
      setSelectedClientId('');
      return;
    }
    if (invoiceClients.length === 1) {
      setSelectedClientId(String(invoiceClients[0].id));
      return;
    }
    setSelectedClientId((prev) => {
      if (prev && invoiceClients.some((c) => String(c.id) === prev)) return prev;
      return '';
    });
  }, [invoiceClients]);

  const loadRecords = useCallback(async () => {
    try {
      const res = await fetch('/purple_invoices/v1/results', {
        headers: { ...api.authHeaders() },
        credentials: 'include',
      });
      let data = {};
      try {
        data = await res.json();
      } catch {
        data = {};
      }
      if (res.status === 401) {
        setAuthRequired(true);
        setRecords([]);
        setPingMsg('Offline');
        setError(
          data.hint ||
            (data.reason === 'missing_header'
              ? 'No API key was sent. Enter the key below or set VITE_AI_CORE_DEV_KEY in .env.'
              : data.reason === 'mismatch'
                ? 'Key does not match Odoo. Open Odoo → Settings → AI Core → React UI Dev API Key, set it to the same value (e.g. 123), click Save, then try again.'
                : 'Unauthorized.'),
        );
        return;
      }
      if (data.ok) {
        setRecords(data.results);
        setAuthRequired(false);
        setError('');
        try {
          const cr = await fetch('/purple_invoices/v1/clients', {
            headers: { ...api.authHeaders() },
            credentials: 'include',
          });
          if (cr.status === 404) {
            setInvoiceClients([]);
            setClientsApiMissing(true);
          } else {
            setClientsApiMissing(false);
            const cj = await cr.json().catch(() => ({}));
            if (cj.ok) setInvoiceClients(cj.clients || []);
            else setInvoiceClients([]);
          }
        } catch {
          setInvoiceClients([]);
          setClientsApiMissing(false);
        }
      } else if ((data.error || '').toLowerCase().includes('unauthorized')) {
        setAuthRequired(true);
        setRecords([]);
        setError(data.hint || data.error || '');
        return;
      }

      const p = await api.ping();
      setPingMsg(p.ok ? 'Online' : 'Warning');
    } catch (e) {
      const msg = (e && e.message) || '';
      if (msg.includes('401') || msg.toLowerCase().includes('unauthorized')) {
        setAuthRequired(true);
      }
    }
  }, []);

  useEffect(() => {
    if (authRequired) return undefined;
    void loadRecords();
    const timer = setInterval(() => void loadRecords(), 10000);
    return () => clearInterval(timer);
  }, [loadRecords, authRequired]);

  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setBusy(true);
    const formData = new FormData();
    formData.append('file', file);

    if (invoiceClients && invoiceClients.length > 0) {
      const cid =
        selectedClientId ||
        (invoiceClients.length === 1 ? String(invoiceClients[0].id) : '');
      if (!cid) {
        setError('Select a client in the dropdown before uploading.');
        setBusy(false);
        e.target.value = '';
        return;
      }
      formData.append('client_id', cid);
    }

    try {
      const res = await fetch('/purple_invoices/v1/upload', {
        method: 'POST',
        headers: { ...api.authHeaders() },
        credentials: 'include',
        body: formData,
      });
      const result = await res.json().catch(() => ({}));
      if (res.status === 401) {
        setAuthRequired(true);
        throw new Error(
          result.hint || result.error || 'Unauthorized — match Odoo React UI Dev API Key.',
        );
      }
      if (!res.ok || !result.ok) {
        throw new Error(result.hint || result.error || `Upload failed (${res.status})`);
      }
      loadRecords();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const logout = () => {
    api.setToken('');
    setToken('');
    setAuthRequired(true);
  };

  const handleAuth = (e) => {
    e.preventDefault();
    const t = e.target.token.value;
    api.setToken(t);
    setToken(t);
    setAuthRequired(false);
    setError('');
    void loadRecords();
  };

  if (authRequired) {
    return (
      <div className="auth-overlay">
        <div className="auth-card glass-morphism animate-fade-in">
          <img src={gtLogo} alt="Logo" className="auth-logo" />
          <h1>Welcome</h1>
          <p>Access the Purple AI ecosystem</p>
          <p className="auth-subtle">
            Use the same value as Odoo: <strong>Settings → General Settings → AI Core → React UI Dev API Key</strong>.
            Save Odoo after editing. Leave that field empty in Odoo to disable this check.
          </p>
          <form onSubmit={handleAuth}>
            <input
              name="token"
              type="password"
              placeholder="Same value as Odoo “React UI Dev API Key” (e.g. 123)"
              required
              autoFocus
            />
            <button type="submit" className="primary">Connect</button>
          </form>
          {error && <p className="error-text">{error}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className="gt-dashboard">
      {viewingId && <DocumentViewer docId={viewingId} onClose={() => setViewingId(null)} />}

      <header className="gt-header">
        <div className="gt-header-left">
          <img src={gtLogo} alt="GT Logo" className="gt-logo" />
          <span className="gt-brand-name">Purple AI</span>
        </div>
        <div className="gt-header-center">
           <div className={`status-pill ${pingMsg === 'Online' ? 'online' : 'offline'}`}>
              <div className="dot"></div>
              {activeEnv.replace('_', ' ').toUpperCase()} - {pingMsg}
           </div>
        </div>
        <div className="gt-header-right">
          <button className="gt-icon-btn" onClick={loadRecords} title="Refresh">
            <RefreshCw size={18} className={busy ? 'spinning' : ''} />
          </button>
          <button className="gt-logout-btn" onClick={logout}>
            <LogOut size={16} />
            <span>Logout</span>
          </button>
        </div>
      </header>

      <div className="gt-layout">
        <aside className="gt-sidebar">
          <button 
            className={`gt-nav-item ${activeEnv === 'purpleai_invoices' ? 'active' : ''}`}
            onClick={() => setActiveEnv('purpleai_invoices')}
          >
            <FileText size={18} />
            <span>Invoices</span>
          </button>
          <button 
            className={`gt-nav-item ${activeEnv === 'leaseai' ? 'active' : ''}`}
            onClick={() => setActiveEnv('leaseai')}
          >
            <Search size={18} />
            <span>Lease Extraction</span>
          </button>
          <button 
            className={`gt-nav-item ${activeEnv === 'memoai' ? 'active' : ''}`}
            onClick={() => setActiveEnv('memoai')}
          >
            <Settings size={18} />
            <span>Settings</span>
          </button>
        </aside>

        <main className="gt-main">
          <div className="gt-container">
            {clientsApiMissing && (
              <div className="gt-banner-error" role="alert">
                <strong>Client list API not found (404).</strong> Update and restart Odoo with the latest{' '}
                <code>purpleai_invoices</code> module (route <code>/purple_invoices/v1/clients</code>), then refresh
                this page.
              </div>
            )}
            {invoiceClients && invoiceClients.length === 0 && !clientsApiMissing && (
              <div className="gt-banner-warn" role="alert">
                <strong>No invoice clients in Odoo.</strong> Uploads will fail until you create one:
                Purple Invoices → Client Master — add a client and an Extraction Template, then refresh.
              </div>
            )}
            {invoiceClients && invoiceClients.length > 0 && (
              <div className="gt-client-row">
                <label htmlFor="gt-client-select">Client for upload</label>
                <select
                  id="gt-client-select"
                  className="gt-client-select"
                  value={selectedClientId}
                  onChange={(ev) => setSelectedClientId(ev.target.value)}
                  disabled={busy}
                >
                  {invoiceClients.length > 1 && <option value="">— Select client —</option>}
                  {invoiceClients.map((c) => (
                    <option key={c.id} value={String(c.id)}>
                      {c.name}
                      {c.extraction_master_id ? '' : ' (no template)'}
                    </option>
                  ))}
                </select>
              </div>
            )}
            {error && (
              <div className="gt-banner-error" role="alert">
                {error}
              </div>
            )}
            <div className="gt-upload-section">
              <div className="gt-dropzone" onClick={handleUploadClick}>
                <Upload size={40} className="gt-muted-icon" />
                <h2>{busy ? 'Uploading...' : 'Drop documents here'}</h2>
                <p>PDF, JPEG, or PNG files up to 10MB</p>
                <button className="gt-btn-primary" disabled={busy}>
                  {busy ? <Loader2 className="spinning" /> : 'Browse Files'}
                </button>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: 'none' }} 
                  onChange={handleFileChange}
                />
              </div>
            </div>

            <div className="gt-table-section">
              <div className="gt-table-header">
                <h3>Recent Processing</h3>
              </div>
              <table className="gt-table">
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Date</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((rec) => (
                    <tr key={rec.id}>
                      <td>
                        <div className="gt-file-info">
                          <FileText size={16} className="gt-purple-icon" />
                          <span>{rec.name}</span>
                        </div>
                      </td>
                      <td>{rec.date}</td>
                      <td>
                        <span className={`gt-badge ${rec.status.toLowerCase()}`}>
                          {rec.status === 'processing' ? 'Scanning...' : 'Done'}
                        </span>
                      </td>
                      <td>
                        <button className="gt-btn-link" onClick={() => setViewingId(rec.id)}>
                          Details
                        </button>
                      </td>
                    </tr>
                  ))}
                  {records.length === 0 && (
                    <tr>
                      <td colSpan="4" className="gt-no-data">No documents processed yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

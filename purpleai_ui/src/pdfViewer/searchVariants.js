/** ISO YYYY-MM-DD → common invoice date strings (PDFs rarely use ISO). */
function addIsoDateVariants(s, add) {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(String(s).trim());
  if (!m) return;
  const y = m[1];
  const mo = m[2].padStart(2, '0');
  const d = m[3].padStart(2, '0');
  const moN = String(parseInt(m[2], 10));
  const dN = String(parseInt(m[3], 10));
  add(`${d}/${mo}/${y}`);
  add(`${d}-${mo}-${y}`);
  add(`${d}.${mo}.${y}`);
  add(`${dN}/${moN}/${y}`);
  add(`${d}/${mo}/${y.slice(2)}`);
  add(`${d}-${mo}-${y.slice(2)}`);
  add(`${y}/${mo}/${d}`);
  add(`${d} ${mo} ${y}`);
  add(`${d}-${m[2]}-${m[3]}`);
}

/** Same variants as Odoo `document_processing_service._search_string_variants`, plus dates / ids. */
export function searchVariantsForSnap(value) {
  if (value === null || value === undefined) return [];
  const s = String(value).trim();
  if (!s || ['---', 'null', 'none', 'n/a', 'undefined'].includes(s.toLowerCase())) return [];
  const seen = new Set();
  const out = [];
  const add = (x) => {
    const t = String(x).trim();
    if (t && !seen.has(t)) {
      seen.add(t);
      out.push(t);
    }
  };
  add(s);
  addIsoDateVariants(s, add);
  if (/[a-z]/i.test(s)) {
    add(s.toLowerCase());
  }
  const compact = s.replace(/[\s₹$€]/g, '').replace(/,/g, '');
  if (compact && compact !== s.replace(/\s/g, '')) add(compact);
  if (compact && /[a-z]/i.test(compact)) {
    add(compact.toLowerCase());
  }
  const idCompact = s.replace(/[\s/_.]/g, '').replace(/-+/g, '');
  if (idCompact && idCompact.length >= 4 && idCompact !== compact) add(idCompact);
  const num = s.replace(/,/g, '').match(/-?[\d]+(?:[.,][\d]+)?/);
  if (num) {
    const raw = num[0].replace(',', '.');
    add(raw);
    const f = parseFloat(raw);
    if (!Number.isNaN(f)) {
      if (Math.abs(f - Math.round(f)) < 1e-9) add(String(Math.round(f)));
      add(f.toFixed(2));
      add(f.toFixed(1));
      const intPart = String(Math.trunc(Math.abs(f)));
      if (intPart.length >= 3) {
        const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        add(withCommas);
        add(`${withCommas}.00`);
        add(`${withCommas}.0`);
      }
    }
  }
  return out;
}

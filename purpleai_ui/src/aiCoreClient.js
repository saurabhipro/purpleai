const LS_KEY = 'purple_ai_token'

/** Prefer token saved from the dashboard login, then .env (Vite injects at build time). */
export function devKey() {
  if (typeof localStorage !== 'undefined') {
    const fromLs = localStorage.getItem(LS_KEY)
    if (fromLs != null && fromLs !== '') return fromLs.trim()
  }
  return String(import.meta.env.VITE_AI_CORE_DEV_KEY || '').trim()
}

export function setToken(token) {
  if (typeof localStorage === 'undefined') return
  const t = String(token || '').trim()
  if (t) localStorage.setItem(LS_KEY, t)
  else localStorage.removeItem(LS_KEY)
}

/** Headers for Purple Invoices API (must match Odoo AI Core “React UI Dev API Key” when set). */
export function authHeaders() {
  const k = devKey()
  return k ? { 'X-AI-Core-Dev-Key': k } : {}
}

async function apiFetch(path, init = {}) {
  const headers = new Headers(init.headers)
  if (!(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  const k = devKey()
  if (k) headers.set('X-AI-Core-Dev-Key', k)
  const res = await fetch(path, { ...init, headers, credentials: 'include' })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    const msg = data.error || res.statusText
    throw new Error(msg)
  }
  return data
}

export function ping() {
  return apiFetch('/ai_core/v1/ping')
}

export function fetchSettingsSummary() {
  return apiFetch('/ai_core/v1/settings')
}

export function chat(prompt) {
  return apiFetch('/ai_core/v1/chat', {
    method: 'POST',
    body: JSON.stringify({ prompt }),
  })
}

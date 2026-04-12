import { useCallback, useEffect, useState } from 'react'
import * as api from './aiCoreClient'
import './AiCorePanel.css'

export function AiCorePanel() {
  const [pingMsg, setPingMsg] = useState('')
  const [settings, setSettings] = useState(null)
  const [settingsErr, setSettingsErr] = useState('')
  const [prompt, setPrompt] = useState('Say hello in one short sentence.')
  const [reply, setReply] = useState('')
  const [busy, setBusy] = useState(false)
  const [chatErr, setChatErr] = useState('')

  const loadMeta = useCallback(async () => {
    setSettingsErr('')
    try {
      const p = await api.ping()
      setPingMsg(p?.ok ? 'Connected to Odoo (AI Core ping).' : 'Unexpected ping response.')
    } catch (e) {
      setPingMsg(`Ping failed: ${e instanceof Error ? e.message : String(e)}`)
    }
    try {
      const s = await api.fetchSettingsSummary()
      setSettings(s)
    } catch (e) {
      setSettings(null)
      setSettingsErr(e instanceof Error ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void loadMeta()
  }, [loadMeta])

  const runChat = async () => {
    setBusy(true)
    setChatErr('')
    setReply('')
    try {
      const data = await api.chat(prompt)
      if (!data.ok) throw new Error(data.error || 'Chat failed')
      const text = data.result?.text || JSON.stringify(data.result)
      const extra =
        data.result?.total_tokens != null
          ? `\n\n(tokens: ${data.result.total_tokens}, cost est.: ${data.result.cost ?? 'n/a'})`
          : ''
      setReply(text + extra)
    } catch (e) {
      setChatErr(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ai-core">
      <header className="ai-core__header">
        <h1>Purple AI</h1>
        <p className="ai-core__muted">
          Proxied to Odoo via Vite. Set <code>VITE_ODOO_URL</code> and optional{' '}
          <code>VITE_AI_CORE_DEV_KEY</code> in <code>.env</code> (see{' '}
          <code>.env.example</code>).
        </p>
      </header>

      <section className="ai-core__card">
        <h2>Connection</h2>
        <p>{pingMsg}</p>
        <button type="button" className="ai-core__btn ai-core__btn--secondary" onClick={() => void loadMeta()}>
          Refresh
        </button>
        {settingsErr ? (
          <p className="ai-core__error">{settingsErr}</p>
        ) : settings?.settings ? (
          <pre className="ai-core__pre">{JSON.stringify(settings.settings, null, 2)}</pre>
        ) : (
          <p className="ai-core__muted">No settings loaded.</p>
        )}
      </section>

      <section className="ai-core__card">
        <h2>Chat (AI Core provider)</h2>
        <textarea
          className="ai-core__textarea"
          rows={6}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />
        <div className="ai-core__row">
          <button type="button" className="ai-core__btn" onClick={() => void runChat()} disabled={busy}>
            {busy ? 'Running…' : 'Send to AI Core'}
          </button>
        </div>
        {chatErr ? <p className="ai-core__error">{chatErr}</p> : null}
        {reply ? <pre className="ai-core__pre ai-core__pre--reply">{reply}</pre> : null}
      </section>
    </div>
  )
}

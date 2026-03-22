/**
 * BillingDashboard.jsx
 * Place in: frontend/src/pages/BillingDashboard.jsx
 *
 * Install: npm install axios recharts
 *
 * Shows LIVE AWS billing data fetched using credentials in backend/.env
 * Displays account identity, real costs, threshold bars, daily chart,
 * threshold editor, and manual alert trigger.
 */

import React, { useState, useEffect, useCallback } from 'react'
import axios from 'axios'
import {
  AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'

const API = 'http://localhost:8000'

// ── Design tokens ──────────────────────────────────────────────
const C = {
  bg:         '#0a0c10',
  surface:    '#111318',
  surface2:   '#16191f',
  border:     '#1e2330',
  borderHov:  '#2a3040',
  accent:     '#FF9900',
  accentDim:  'rgba(255,153,0,0.1)',
  success:    '#00C853',
  error:      '#FF3D3D',
  warn:       '#FFB800',
  cyan:       '#00BCD4',
  cyanDim:    'rgba(0,188,212,0.08)',
  text:       '#E8EAF0',
  muted:      '#5a6070',
  dim:        '#3a4050',
}
const F = {
  display: "'Syne', sans-serif",
  mono:    "'JetBrains Mono', monospace",
  body:    "'DM Sans', sans-serif",
}

// ── Tiny utils ─────────────────────────────────────────────────
const fmt4  = (n) => Number(n || 0).toFixed(4)
const fmt6  = (n) => Number(n || 0).toFixed(6)
const pct   = (cost, limit) => limit ? Math.min((cost / limit) * 100, 100).toFixed(1) : 0
const color = (breached, pctVal) => breached ? C.error : pctVal > 75 ? C.warn : C.success

function Spinner({ size = 20, c = C.accent }) {
  return <div style={{
    width: size, height: size, borderRadius: '50%',
    border: `2px solid ${C.border}`, borderTop: `2px solid ${c}`,
    animation: 'spin 0.7s linear infinite', flexShrink: 0
  }} />
}

// ── Account Identity Bar ───────────────────────────────────────
function AccountBar({ account }) {
  if (!account) return null
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderLeft: `3px solid ${C.cyan}`,
      borderRadius: 8, padding: '12px 20px',
      display: 'flex', alignItems: 'center', gap: 32,
      flexWrap: 'wrap'
    }}>
      <Field label="Account ID"  value={account.account_id} mono />
      <Field label="Access Key"  value={account.key_masked}  mono accent />
      <Field label="Region"      value={account.region}      mono />
      <Field label="ARN"         value={account.arn}         mono small />
    </div>
  )
}

function Field({ label, value, mono, accent: isAccent, small }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ fontSize: 10, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {label}
      </span>
      <span style={{
        fontSize: small ? 11 : 13,
        fontFamily: mono ? F.mono : F.body,
        color: isAccent ? C.accent : C.text,
        fontWeight: isAccent ? 600 : 400,
      }}>
        {value || '—'}
      </span>
    </div>
  )
}

// ── Total Cost Card ────────────────────────────────────────────
function TotalCard({ summary }) {
  const { total, currency, total_limit, total_percent, total_breached, period } = summary
  const p   = pct(total, total_limit)
  const clr = total_breached ? C.error : p > 75 ? C.warn : C.cyan

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderLeft: `3px solid ${clr}`,
      borderRadius: 10, padding: '24px 28px',
    }}>
      <div style={{ fontSize: 11, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
        Total Bill — {period}
      </div>
      <div style={{ fontFamily: F.display, fontSize: 46, fontWeight: 800, color: clr, lineHeight: 1, marginBottom: 8 }}>
        ${fmt4(total)}
        <span style={{ fontSize: 15, color: C.muted, marginLeft: 8, fontFamily: F.body }}>{currency}</span>
      </div>

      {total_breached && (
        <div style={{
          display: 'inline-block',
          background: 'rgba(255,61,61,0.12)', border: '1px solid rgba(255,61,61,0.3)',
          borderRadius: 6, padding: '4px 12px', fontSize: 12, color: C.error,
          fontWeight: 700, marginBottom: 12
        }}>
          ⚠️ Over budget limit
        </div>
      )}

      {total_limit && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 12, color: C.muted }}>Budget used</span>
            <span style={{ fontSize: 12, fontFamily: F.mono, color: clr, fontWeight: 600 }}>
              {total_percent}% of ${total_limit.toFixed(2)}
            </span>
          </div>
          <div style={{ background: C.surface2, borderRadius: 6, height: 12, overflow: 'hidden', border: `1px solid ${C.border}` }}>
            <div style={{
              width: `${Math.min(total_percent, 100)}%`, height: '100%',
              background: clr, borderRadius: 6,
              transition: 'width 0.8s ease',
              boxShadow: total_breached ? `0 0 10px ${clr}` : 'none'
            }} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Daily Spend Chart ──────────────────────────────────────────
function DailyChart({ daily }) {
  if (!daily || daily.length === 0) return null
  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 10, padding: '20px 24px',
    }}>
      <div style={{ fontSize: 11, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 14 }}>
        Daily Spend — Last 7 Days
      </div>
      <ResponsiveContainer width="100%" height={150}>
        <AreaChart data={daily} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
          <defs>
            <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%"  stopColor={C.accent} stopOpacity={0.25} />
              <stop offset="95%" stopColor={C.accent} stopOpacity={0}    />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={C.border} vertical={false} />
          <XAxis dataKey="date" tick={{ fill: C.muted, fontSize: 10, fontFamily: F.mono }}
            tickFormatter={d => d.slice(5)} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: C.muted, fontSize: 10, fontFamily: F.mono }}
            tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} />
          <Tooltip
            contentStyle={{ background: C.surface2, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 12 }}
            labelStyle={{ color: C.muted, fontFamily: F.mono }}
            formatter={v => [`$${Number(v).toFixed(6)}`, 'Cost']}
          />
          <Area type="monotone" dataKey="cost" stroke={C.accent} strokeWidth={2}
            fill="url(#areaGrad)" dot={{ fill: C.accent, strokeWidth: 0, r: 3 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

// ── Service Row ────────────────────────────────────────────────
function ServiceRow({ svc }) {
  const p   = pct(svc.cost, svc.threshold)
  const clr = color(svc.breached, p)

  return (
    <div style={{
      background: svc.breached ? 'rgba(255,61,61,0.04)' : C.surface,
      border: `1px solid ${svc.breached ? 'rgba(255,61,61,0.25)' : C.border}`,
      borderLeft: `3px solid ${clr}`,
      borderRadius: 8, padding: '14px 18px',
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <span style={{ fontSize: 12, color: C.text, fontFamily: F.mono, fontWeight: 500, flex: 1 }}>
          {svc.service}
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 14, fontWeight: 700, color: svc.breached ? C.error : C.text, fontFamily: F.mono }}>
            ${fmt6(svc.cost)}
          </span>
          {svc.breached && (
            <span style={{
              background: 'rgba(255,61,61,0.15)', border: '1px solid rgba(255,61,61,0.3)',
              borderRadius: 4, padding: '2px 7px', fontSize: 10, color: C.error, fontWeight: 700
            }}>OVER</span>
          )}
        </div>
      </div>

      {svc.threshold ? (
        <div>
          <div style={{ background: C.surface2, borderRadius: 4, height: 8, overflow: 'hidden', border: `1px solid ${C.border}` }}>
            <div style={{
              width: `${Math.min(p, 100)}%`, height: '100%',
              background: clr, borderRadius: 4, transition: 'width 0.5s ease',
              boxShadow: svc.breached ? `0 0 6px ${clr}` : 'none'
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
            <span style={{ fontSize: 10, color: clr, fontFamily: F.mono }}>{p}% of limit</span>
            <span style={{ fontSize: 10, color: C.muted, fontFamily: F.mono }}>limit: ${svc.threshold.toFixed(2)}</span>
          </div>
        </div>
      ) : (
        <div style={{ fontSize: 10, color: C.dim }}>No limit set</div>
      )}
    </div>
  )
}

// ── Threshold Editor ───────────────────────────────────────────
function ThresholdEditor({ thresholds, allServices, onSave, saving }) {
  const [vals, setVals]           = useState({ ...thresholds })
  const [newSvc, setNewSvc]       = useState('')
  const [newLimit, setNewLimit]   = useState('')
  const [showAdd, setShowAdd]     = useState(false)

  useEffect(() => setVals({ ...thresholds }), [thresholds])

  const set    = (k, v) => setVals(prev => ({ ...prev, [k]: parseFloat(v) || 0 }))
  const remove = (k)    => setVals(prev => { const n = { ...prev }; delete n[k]; return n })

  const addSvc = () => {
    if (!newSvc.trim() || !newLimit) return
    setVals(prev => ({ ...prev, [newSvc.trim()]: parseFloat(newLimit) }))
    setNewSvc(''); setNewLimit(''); setShowAdd(false)
  }

  const inp = {
    background: C.surface2, border: `1px solid ${C.borderHov}`,
    borderRadius: 6, padding: '8px 12px',
    color: C.text, fontSize: 12, fontFamily: F.mono,
    outline: 'none',
  }

  // Ordered: TOTAL first, then rest alphabetically
  const ordered = [
    ['TOTAL', vals['TOTAL']],
    ...Object.entries(vals).filter(([k]) => k !== 'TOTAL').sort(([a], [b]) => a.localeCompare(b))
  ].filter(([, v]) => v !== undefined)

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderLeft: `3px solid ${C.cyan}`,
      borderRadius: 10, padding: '20px 24px',
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontFamily: F.display, fontSize: 16, fontWeight: 700, color: C.text }}>
            Cost Thresholds
          </div>
          <div style={{ fontSize: 12, color: C.muted, marginTop: 2 }}>
            Alert email fires when any limit is crossed
          </div>
        </div>
        <button onClick={() => onSave(vals)} disabled={saving} style={{
          display: 'flex', alignItems: 'center', gap: 8,
          padding: '9px 18px', background: saving ? C.dim : C.accent,
          border: 'none', borderRadius: 6, color: '#0a0c10',
          fontWeight: 700, fontSize: 13, fontFamily: F.body,
          cursor: saving ? 'not-allowed' : 'pointer',
        }}>
          {saving ? <><Spinner size={13} c="#0a0c10" /> Saving…</> : '💾 Save'}
        </button>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 340, overflowY: 'auto' }}>
        {ordered.map(([key, val]) => (
          <div key={key} style={{
            display: 'flex', alignItems: 'center', gap: 10,
            background: C.surface2, borderRadius: 6, padding: '9px 12px',
            border: `1px solid ${key === 'TOTAL' ? 'rgba(255,153,0,0.2)' : C.border}`,
          }}>
            <span style={{
              flex: 1, fontSize: 12, fontFamily: F.mono, color: C.text,
              fontWeight: key === 'TOTAL' ? 700 : 400,
              color: key === 'TOTAL' ? C.accent : C.text,
            }}>
              {key === 'TOTAL' ? '🎯 TOTAL BILL' : key}
            </span>
            <span style={{ fontSize: 12, color: C.muted }}>$</span>
            <input
              type="number" min="0" step="1"
              value={val ?? ''}
              onChange={e => set(key, e.target.value)}
              style={{ ...inp, width: 80, textAlign: 'right' }}
            />
            {key !== 'TOTAL' && (
              <button onClick={() => remove(key)} style={{
                background: 'rgba(255,61,61,0.08)', border: '1px solid rgba(255,61,61,0.2)',
                borderRadius: 4, padding: '4px 8px', color: C.error,
                fontSize: 12, cursor: 'pointer',
              }}>✕</button>
            )}
          </div>
        ))}
      </div>

      {!showAdd ? (
        <button onClick={() => setShowAdd(true)} style={{
          background: 'transparent', border: `1px dashed ${C.borderHov}`,
          borderRadius: 6, padding: '8px', color: C.muted,
          fontSize: 12, cursor: 'pointer', width: '100%',
        }}>
          + Add service limit
        </button>
      ) : (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <input
            placeholder="e.g. Amazon EC2"
            value={newSvc}
            onChange={e => setNewSvc(e.target.value)}
            style={{ ...inp, flex: 1 }}
          />
          <span style={{ fontSize: 12, color: C.muted }}>$</span>
          <input
            type="number" min="0" placeholder="Limit"
            value={newLimit}
            onChange={e => setNewLimit(e.target.value)}
            style={{ ...inp, width: 70 }}
          />
          <button onClick={addSvc} style={{
            padding: '8px 14px', background: C.accentDim,
            border: `1px solid rgba(255,153,0,0.3)`,
            borderRadius: 6, color: C.accent,
            fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>Add</button>
          <button onClick={() => setShowAdd(false)} style={{
            background: 'transparent', border: 'none', color: C.muted, cursor: 'pointer', fontSize: 18
          }}>✕</button>
        </div>
      )}
    </div>
  )
}

// ── SMTP Config Hint ───────────────────────────────────────────
function SMTPHint() {
  const [open, setOpen] = useState(false)
  return (
    <div>
      <button onClick={() => setOpen(p => !p)} style={{
        background: 'transparent', border: 'none',
        color: C.cyan, fontSize: 12, cursor: 'pointer',
        textDecoration: 'underline', fontFamily: F.body
      }}>
        {open ? '▲ Hide' : '▼'} Email alert setup (SMTP)
      </button>
      {open && (
        <div style={{
          background: C.surface2, border: `1px solid ${C.border}`,
          borderLeft: `3px solid ${C.cyan}`,
          borderRadius: 8, padding: '14px 18px', marginTop: 8,
          fontSize: 12, color: C.muted, lineHeight: 2, fontFamily: F.mono
        }}>
          Add to backend/.env:<br />
          <span style={{ color: C.text }}>SMTP_HOST</span>=smtp.gmail.com<br />
          <span style={{ color: C.text }}>SMTP_PORT</span>=587<br />
          <span style={{ color: C.text }}>SMTP_USER</span>=you@gmail.com<br />
          <span style={{ color: C.text }}>SMTP_PASSWORD</span>=xxxx xxxx xxxx xxxx
          <span style={{ color: C.dim }}> ← Gmail App Password</span><br />
          <span style={{ color: C.text }}>SMTP_FROM</span>=you@gmail.com<br />
          <span style={{ color: C.text }}>ALERT_EMAIL</span>=alerts@yourapp.com<br /><br />
          <span style={{ color: C.accent }}>Gmail App Password: </span>
          Google Account → Security → 2-Step Verification → App Passwords
        </div>
      )}
    </div>
  )
}

// ── Breach Banner ──────────────────────────────────────────────
function BreachBanner({ services, totalBreached, total, totalLimit }) {
  const svcBreaches = services.filter(s => s.breached)
  const allBreaches = [...(totalBreached ? [{ service: 'Total AWS Bill', current: total, threshold: totalLimit }] : []), ...svcBreaches]
  if (allBreaches.length === 0) return null

  return (
    <div style={{
      background: 'rgba(255,61,61,0.06)', border: '1px solid rgba(255,61,61,0.3)',
      borderRadius: 8, padding: '14px 18px', display: 'flex', flexDirection: 'column', gap: 6
    }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: C.error, fontFamily: F.display }}>
        🚨 {allBreaches.length} Threshold{allBreaches.length > 1 ? 's' : ''} Exceeded
      </div>
      {allBreaches.map(b => (
        <div key={b.service} style={{ fontSize: 12, color: C.text }}>
          • <strong style={{ fontFamily: F.mono }}>{b.service}</strong>:
          ${fmt6(b.cost || b.current)} / limit ${(b.threshold || 0).toFixed(2)}
        </div>
      ))}
    </div>
  )
}

// ── Main Dashboard ─────────────────────────────────────────────
export default function BillingDashboard() {
  const [summary,    setSummary]    = useState(null)
  const [loading,    setLoading]    = useState(true)
  const [checking,   setChecking]   = useState(false)
  const [saving,     setSaving]     = useState(false)
  const [error,      setError]      = useState(null)
  const [toast,      setToast]      = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [autoRefresh, setAutoRefresh] = useState(false)

  const showToast = (msg, type = 'ok') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 5000)
  }

  const fetchSummary = useCallback(async () => {
    setError(null)
    try {
      const { data } = await axios.get(`${API}/billing/summary`)
      setSummary(data.summary)
      setLastUpdate(new Date().toLocaleTimeString())
    } catch (e) {
      const detail = e.response?.data?.detail || e.message
      setError(detail)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchSummary() }, [fetchSummary])

  // Auto-refresh every 5 minutes
  useEffect(() => {
    if (!autoRefresh) return
    const id = setInterval(fetchSummary, 5 * 60 * 1000)
    return () => clearInterval(id)
  }, [autoRefresh, fetchSummary])

  const runCheck = async () => {
    setChecking(true)
    try {
      const { data } = await axios.post(`${API}/billing/check`)
      await fetchSummary()
      if (data.email_sent) {
        showToast(`✅ ${data.breaches.length} breach(es) found — alert email sent!`)
      } else if (data.breaches.length > 0) {
        showToast('⚠️ Breaches found but SMTP not configured — check .env', 'warn')
      } else {
        showToast('✅ All costs within limits — no alert needed')
      }
    } catch (e) {
      showToast('❌ ' + (e.response?.data?.detail || e.message), 'error')
    } finally {
      setChecking(false)
    }
  }

  const saveThresholds = async (vals) => {
    setSaving(true)
    try {
      await axios.post(`${API}/billing/thresholds`, { thresholds: vals })
      showToast('✅ Thresholds saved')
      await fetchSummary()
    } catch (e) {
      showToast('❌ Failed to save', 'error')
    } finally {
      setSaving(false)
    }
  }

  const toastColor = toast?.type === 'error' ? C.error : toast?.type === 'warn' ? C.warn : C.success

  return (
    <div style={{ minHeight: '100vh', background: C.bg, fontFamily: F.body, color: C.text, padding: '32px 40px' }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500;600&family=DM+Sans:wght@300;400;500;600&display=swap');
        * { box-sizing: border-box; }
        @keyframes spin { to { transform: rotate(360deg); } }
        @keyframes fadeSlide { from { opacity:0; transform:translateY(-8px); } to { opacity:1; transform:none; } }
        input:focus { border-color: rgba(255,153,0,0.4) !important; }
        input[type=number]::-webkit-inner-spin-button { opacity: 0.4; }
        ::-webkit-scrollbar { width: 4px; } ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 2px; }
      `}</style>

      {/* Toast */}
      {toast && (
        <div style={{
          position: 'fixed', top: 20, right: 24, zIndex: 9999,
          background: C.surface, border: `1px solid ${toastColor}`,
          borderRadius: 8, padding: '12px 20px', fontSize: 13, color: C.text,
          boxShadow: `0 4px 20px rgba(0,0,0,0.5)`,
          animation: 'fadeSlide 0.3s ease', maxWidth: 380
        }}>
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 24, flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ fontFamily: F.display, fontSize: 26, fontWeight: 800, color: C.text, marginBottom: 4 }}>
            AWS Billing Dashboard
          </h1>
          <div style={{ fontSize: 13, color: C.muted }}>
            Live data from your AWS account
            {lastUpdate && <span style={{ marginLeft: 10, color: C.dim }}>· Updated {lastUpdate}</span>}
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: C.muted, cursor: 'pointer' }}>
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            Auto-refresh (5 min)
          </label>
          <button onClick={fetchSummary} style={{
            padding: '9px 16px', background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 6, color: C.muted, fontSize: 13, cursor: 'pointer',
          }}>↻ Refresh</button>
          <button onClick={runCheck} disabled={checking} style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 20px', background: C.accent,
            border: 'none', borderRadius: 6,
            color: '#0a0c10', fontWeight: 700, fontSize: 13,
            cursor: checking ? 'not-allowed' : 'pointer',
            opacity: checking ? 0.6 : 1,
          }}>
            {checking ? <><Spinner size={14} c="#0a0c10" /> Checking…</> : '▶ Run Check & Alert'}
          </button>
        </div>
      </div>

      {/* Error state */}
      {error && (
        <div style={{
          background: 'rgba(255,61,61,0.08)', border: '1px solid rgba(255,61,61,0.3)',
          borderRadius: 8, padding: '16px 20px', marginBottom: 20,
          fontSize: 13, color: C.error, lineHeight: 1.7
        }}>
          <strong>❌ Failed to load billing data</strong><br />
          {error}<br />
          <span style={{ color: C.muted, fontSize: 12 }}>
            Make sure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set in backend/.env
            and Cost Explorer is enabled in your AWS account.
          </span>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14, padding: '80px 0' }}>
          <Spinner size={28} />
          <span style={{ color: C.muted, fontSize: 14 }}>Fetching live billing from AWS…</span>
        </div>
      )}

      {/* Dashboard content */}
      {!loading && summary && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>

          {/* Account identity */}
          <AccountBar account={summary.account} />

          {/* Breach banner */}
          <BreachBanner
            services={summary.services || []}
            totalBreached={summary.total_breached}
            total={summary.total}
            totalLimit={summary.total_limit}
          />

          {/* Total + Daily chart */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.5fr', gap: 16 }}>
            <TotalCard summary={summary} />
            <DailyChart daily={summary.daily} />
          </div>

          {/* Services + Threshold editor side by side */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, alignItems: 'start' }}>

            {/* Services list */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ fontSize: 11, color: C.muted, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Cost by Service ({summary.services?.length || 0} active)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 540, overflowY: 'auto', paddingRight: 4 }}>
                {(summary.services || []).map(svc => (
                  <ServiceRow key={svc.service} svc={svc} />
                ))}
                {(!summary.services || summary.services.length === 0) && (
                  <div style={{
                    color: C.dim, fontSize: 13, padding: '24px',
                    textAlign: 'center', border: `1px dashed ${C.border}`, borderRadius: 8
                  }}>
                    No service costs found for this period.<br />
                    <span style={{ fontSize: 11, color: C.dim }}>Account may be in free tier.</span>
                  </div>
                )}
              </div>
            </div>

            {/* Threshold editor + SMTP hint */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              <ThresholdEditor
                thresholds={summary.thresholds || {}}
                allServices={summary.services || []}
                onSave={saveThresholds}
                saving={saving}
              />
              <SMTPHint />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
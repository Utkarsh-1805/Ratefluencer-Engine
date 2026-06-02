/* ============ Screens: Brief Composer · AI Working · Screener ============ */
import { useState, useEffect } from 'react'
import { api, ScoreTile, bandColor, compact, FLAG_LABELS } from '../lib.jsx'

/* derive the "detected" chips from the brief text (replaces window.RATE.DETECTED) */
function detect(text) {
  const t = (text || '').toLowerCase()
  const cat = ['skincare', 'fitness', 'fashion', 'finance', 'food', 'tech'].find((c) =>
    t.includes(c) || (c === 'skincare' && /(skin|serum|spf|beauty)/.test(t))) || 'skincare'
  const goal = /sales|sell|buy/.test(t) ? 'Sales' : /aware/.test(t) ? 'Awareness'
    : /convert|sign.?up|lead/.test(t) ? 'Conversions' : /engage/.test(t) ? 'Engagement' : 'Sales'
  const gender = /\b(women|female|her|ladies)\b/.test(t) ? 'Women' : /\b(men|male|guys)\b/.test(t) ? 'Men' : 'All'
  const geo = /india/.test(t) ? 'India' : /usa|america/.test(t) ? 'USA' : /uk/.test(t) ? 'UK' : 'India'
  const age = t.match(/(\d{2})\s*[-–to]+\s*(\d{2})/)
  const budget = t.match(/(\d{5,})/)
  const tone = /science|clinical|derma/.test(t) ? 'Science-backed' : /luxur|premium/.test(t) ? 'Luxury'
    : /clean|minimal|natural/.test(t) ? 'Clean' : /fun|playful|bold/.test(t) ? 'Playful' : 'Authentic'
  return [
    { k: 'Category', v: cat[0].toUpperCase() + cat.slice(1) },
    { k: 'Audience', v: `${gender} · ${age ? age[1] + '–' + age[2] : '22–35'}` },
    { k: 'Geo', v: geo },
    { k: 'Goal', v: goal },
    { k: 'Tone', v: tone },
    { k: 'Budget', v: budget ? '₹' + Number(budget[1]).toLocaleString('en-IN') : '₹3,00,000' },
  ]
}

/* ---------------- Screen 1: Brief Composer ---------------- */
export function BriefComposer({ brief, setBrief, onGenerate, onScreen }) {
  const detected = detect(brief)
  const hasContent = brief.trim().length > 12

  return (
    <div className="screen app-shell" style={{ paddingTop: 56, paddingBottom: 80 }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <div className="eyebrow" style={{ marginBottom: 18 }}>Ratefluencer Copilot · AI media-buyer</div>
        <h1 className="r-hero-title" style={{ fontSize: 52, lineHeight: 1.04, letterSpacing: "-0.035em" }}>
          Find creators by<br /><span style={{ background: "linear-gradient(120deg,#fff,#818CF8)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>impact, not hype.</span>
        </h1>
        <p className="muted" style={{ fontSize: 17, marginTop: 18, maxWidth: 620, lineHeight: 1.6 }}>
          Describe your campaign in plain English. We parse it, screen every creator for fraud, and rank a shortlist by <span style={{ color: "var(--text)" }}>predicted business impact</span> — not follower count.
        </p>

        <div style={{ marginTop: 34, position: "relative" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 11 }}>
            <span className="kicker">Campaign brief</span>
            <span className="dim" style={{ fontSize: 12 }}>{brief.length} chars</span>
          </div>
          <textarea className="brief-area" value={brief} onChange={(e) => setBrief(e.target.value)} placeholder="Describe your brand, audience, budget, goal, and tone…" />
        </div>

        <div style={{ marginTop: 22, opacity: hasContent ? 1 : 0.35, transition: "opacity .3s" }}>
          <div className="kicker" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ color: "var(--accent-2)" }}>✦</span> Detected from your brief
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            {detected.map((d, i) => (
              <div key={d.k} className="chip chip-detected" style={{ animationDelay: hasContent ? `${i * 60}ms` : "0ms" }}>
                <span className="chip-k">{d.k}</span>
                <span style={{ fontWeight: 600 }}>{d.v}</span>
              </div>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 14, marginTop: 36, flexWrap: "wrap" }}>
          <button className="btn btn-primary btn-lg" disabled={!hasContent} onClick={onGenerate}>
            <span>✦</span> Generate AI Recommendations
          </button>
          <button className="btn btn-lg" onClick={onScreen}>
            <span>🔍</span> Screen a real Instagram account
          </button>
        </div>

        <div style={{ display: "flex", gap: 26, marginTop: 44, flexWrap: "wrap" }}>
          {[
            ["Fraud-adjusted", "Bot audiences, pods & spikes removed before ranking"],
            ["ROI-ranked", "Scored on predicted conversions per rupee, not reach"],
            ["Explainable", "Every score backed by positive & negative drivers"],
          ].map(([t, d]) => (
            <div key={t} style={{ flex: "1 1 200px", minWidth: 180 }}>
              <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 14.5, marginBottom: 5 }}>{t}</div>
              <div className="dim" style={{ fontSize: 13, lineHeight: 1.5 }}>{d}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

/* normalize an API creator dict into the shape the design screens expect */
function normalize(c) {
  return {
    ...c,
    handle: (c.handle || '').replace(/^@/, ''),            // design prepends @
    display_name: c.display_name || c.handle || '',
    drivers: c.drivers || [],
    authenticity_detail: c.authenticity_detail || { bot_follower_pct: 0, comment_spam_ratio: 0, spike_anomaly_score: 0, flags: [] },
    audience_fit: c.audience_fit || { age_match: 0, gender_match: 0, geo_match: 0 },
    flag_reason: c.flag_reason || null,
    region: c.region || 'India',
    content_category: c.content_category || '',
  }
}

/* ---------------- Screen 2: AI Working (calls the real API) ---------------- */
const WORK_STEPS = [
  { k: "Parsing brief", d: "Extracting category, audience, geo, budget & tone", ico: "✎" },
  { k: "Pulling candidates", d: "Matching skincare creators in India", ico: "⤓" },
  { k: "Running fraud check", d: "Bot %, engagement pods, spikes, comment spam", ico: "🛡" },
  { k: "Predicting impact", d: "Fraud-adjusted reach → conversions per ₹", ico: "📈" },
  { k: "Ranking creators", d: "Weighting impact, authenticity, match & ROI", ico: "≡" },
  { k: "Composing recommendation", d: "Budget allocation + rationale", ico: "✦" },
]

export function AIWorking({ brief, onDone, onError }) {
  const [active, setActive] = useState(0)

  useEffect(() => {
    let alive = true
    const timer = setInterval(() => setActive((a) => Math.min(a + 1, WORK_STEPS.length - 1)), 600)
    api('/analyze', { brief })
      .then((r) => {
        if (!alive) return
        clearInterval(timer); setActive(WORK_STEPS.length)
        const creators = (r.ranked || []).map(normalize)
        setTimeout(() => onDone({ creators, recommendation: r.recommendation }), 600)
      })
      .catch((e) => { console.error(e); clearInterval(timer); if (alive) onError(e) })
    return () => { alive = false; clearInterval(timer) }
  }, [])

  const pct = Math.round((Math.min(active, WORK_STEPS.length) / WORK_STEPS.length) * 100)

  return (
    <div className="screen app-shell" style={{ paddingTop: 90, paddingBottom: 80 }}>
      <div style={{ maxWidth: 620, margin: "0 auto" }}>
        <div className="eyebrow" style={{ marginBottom: 14 }}>Working</div>
        <h1 style={{ fontSize: 32, letterSpacing: "-0.03em" }}>Analysing your campaign</h1>
        <p className="muted" style={{ marginTop: 10, fontSize: 15 }}>Screening creators and predicting business impact in real time.</p>

        <div style={{ margin: "26px 0 30px" }}>
          <div className="sbar-track" style={{ height: 6 }}>
            <div className="sbar-fill" style={{ width: pct + "%", background: "linear-gradient(90deg,#818CF8,#6366F1)" }}></div>
          </div>
          <div className="mono dim" style={{ fontSize: 12, marginTop: 8, textAlign: "right" }}>{pct}%</div>
        </div>

        <div className="card" style={{ padding: 12 }}>
          {WORK_STEPS.map((s, i) => {
            const state = i < active ? "done" : i === active ? "active" : "idle"
            return (
              <div key={s.k} className={`pstep ${state}`}>
                <div className="pstep-ico">
                  {state === "done" ? "✓" : state === "active" ? <span className="spinner"></span> : <span style={{ opacity: .6 }}>{s.ico}</span>}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5 }}>{s.k}</div>
                  <div className="dim" style={{ fontSize: 12.5 }}>{s.d}</div>
                </div>
                {state === "done" && <span className="pill pill-good" style={{ padding: "3px 9px" }}>done</span>}
                {state === "active" && <span className="pill pill-accent" style={{ padding: "3px 9px" }}>running</span>}
              </div>
            )
          })}
        </div>
        <p className="dim" style={{ fontSize: 12, marginTop: 14 }}>First run warms the models (~40s) — then it's instant.</p>
      </div>
    </div>
  )
}

/* ---------------- Screen 5b: Real-Account Screener (live /screen API) ---------------- */
export function Screener({ onBack }) {
  const [f, setF] = useState({ handle: "famous.face", followers: "512000", following: "820", likes: "9200", comments: "180", category: "skincare" })
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function run() {
    setLoading(true)
    try {
      const r = await api('/screen', {
        handle: f.handle, followers: +f.followers || 1, following: +f.following || 0,
        avg_likes: +f.likes || 0, avg_comments: +f.comments || 0, category: f.category,
      })
      const auth = r.authenticity_score
      const verdict = auth >= 60 ? "Looks authentic for its size — engagement is in line with expectations."
        : auth >= 40 ? "Mixed signals — engagement is softer than expected for this audience size."
        : "Likely inflated audience — engagement is far below what this follower count should produce."
      setResult({ eng: r.engagement_rate, expected: r.expected_rate, auth, flags: r.flags || [], verdict, followers: r.followers })
    } catch (e) {
      setResult({ error: String(e) })
    } finally { setLoading(false) }
  }

  return (
    <div className="screen app-shell" style={{ paddingTop: 40, paddingBottom: 80 }}>
      <div style={{ maxWidth: 880, margin: "0 auto" }}>
        <button className="btn btn-ghost" onClick={onBack} style={{ marginBottom: 22, padding: "8px 14px" }}>← Back to brief</button>
        <div className="eyebrow" style={{ marginBottom: 12 }}>Account screener</div>
        <h1 style={{ fontSize: 34, letterSpacing: "-0.03em" }}>Screen a real Instagram account</h1>
        <p className="muted" style={{ marginTop: 10, fontSize: 15, maxWidth: 560 }}>Enter public stats. We score authenticity from engagement-vs-size signals.</p>

        <div className="r-grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 28, marginTop: 30, alignItems: "start" }}>
          <div className="card" style={{ padding: 24 }}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div style={{ gridColumn: "1 / -1" }}>
                <label className="field-label">Handle</label>
                <input className="field" value={f.handle} onChange={set("handle")} />
              </div>
              <div><label className="field-label">Followers</label><input className="field mono" value={f.followers} onChange={set("followers")} /></div>
              <div><label className="field-label">Following</label><input className="field mono" value={f.following} onChange={set("following")} /></div>
              <div><label className="field-label">Avg likes</label><input className="field mono" value={f.likes} onChange={set("likes")} /></div>
              <div><label className="field-label">Avg comments</label><input className="field mono" value={f.comments} onChange={set("comments")} /></div>
              <div style={{ gridColumn: "1 / -1" }}><label className="field-label">Category</label><input className="field" value={f.category} onChange={set("category")} /></div>
            </div>
            <button className="btn btn-primary" style={{ marginTop: 20, width: "100%", justifyContent: "center" }} onClick={run} disabled={loading}>
              {loading ? <><span className="spinner"></span>&nbsp;Screening…</> : "Run authenticity screen"}
            </button>
            <p className="dim" style={{ fontSize: 11.5, marginTop: 14, lineHeight: 1.5 }}>Authenticity screen from public engagement-vs-size signals — not an accusation.</p>
          </div>

          <div>
            {!result ? (
              <div className="card" style={{ padding: 40, textAlign: "center", color: "var(--text-3)", height: "100%", display: "grid", placeItems: "center", minHeight: 300 }}>
                <div>
                  <div style={{ fontSize: 30, marginBottom: 10, opacity: .5 }}>🔍</div>
                  Run a screen to see the authenticity verdict.
                </div>
              </div>
            ) : result.error ? (
              <div className="card" style={{ padding: 24, color: "var(--bad)" }}>Could not screen: {result.error}</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 16 }} className="screen">
                <ScoreTile label="Authenticity score" value={result.auth} big />
                <div className="card" style={{ padding: 20 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14 }}>
                    <div>
                      <div className="dim" style={{ fontSize: 11.5 }}>Actual engagement</div>
                      <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: bandColor(result.auth) }}>{result.eng.toFixed(2)}%</div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      <div className="dim" style={{ fontSize: 11.5 }}>Expected for {compact(result.followers)}</div>
                      <div className="mono" style={{ fontSize: 22, fontWeight: 600, color: "var(--text-2)" }}>~{result.expected.toFixed(1)}%</div>
                    </div>
                  </div>
                  <div style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--text)" }}>{result.verdict}</div>
                  {result.flags.length > 0 && (
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 14 }}>
                      {result.flags.map((fl) => (
                        <span key={fl} className="pill pill-bad" style={{ padding: "5px 10px" }}>⚑ {FLAG_LABELS[fl] || fl}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ============ Ratefluencer Copilot — app router (exact design, live data) ============ */
import { useState, useEffect } from 'react'
import { BRIEF_DEFAULT } from './lib.jsx'
import { BriefComposer, AIWorking, Screener } from './screens/Screens1.jsx'
import { Shortlist, CreatorDetail, Recommendation } from './screens/Screens2.jsx'

const STEPS = [
  { key: "brief", label: "Brief" },
  { key: "shortlist", label: "Shortlist" },
  { key: "detail", label: "Detail" },
  { key: "recommend", label: "Recommendation" },
]

export default function App() {
  const [route, setRoute] = useState("brief")  // brief | working | shortlist | detail | recommend | screener
  const [brief, setBrief] = useState(BRIEF_DEFAULT)
  const [weights, setWeights] = useState({ impact: 60, authenticity: 70, match: 55, roi: 65 })
  const [creators, setCreators] = useState([])
  const [recommendation, setRecommendation] = useState(null)
  const [openId, setOpenId] = useState(null)

  useEffect(() => { window.scrollTo({ top: 0 }) }, [route])

  const open = (id) => { setOpenId(id); setRoute("detail") }
  const current = creators.find((c) => c.influencer_id === openId)

  function toggleStatus(id) {
    setCreators((prev) => prev.map((c) => {
      if (c.influencer_id !== id) return c
      if (c.status === "recommended") return { ...c, status: "excluded" }
      if (c.status === "excluded") return { ...c, status: "recommended" }
      if (c.status === "flagged") return { ...c, status: "recommended" }
      return c
    }))
  }

  const crumbIndex = { brief: 0, working: 0, shortlist: 1, detail: 2, recommend: 3 }[route] ?? 0

  return (
    <div>
      <div className="topbar">
        <div className="topbar-inner">
          <div className="brand" style={{ cursor: "pointer" }} onClick={() => setRoute("brief")}>
            <div className="brand-mark">R</div>
            <span>Ratefluencer <span className="brand-sub">Copilot</span></span>
          </div>
          {route !== "screener" && (
            <div className="crumbs">
              {STEPS.map((s, i) => (
                <div key={s.key} className="crumbs-step" style={i <= crumbIndex ? { color: "var(--text)" } : null}>
                  <span className={`crumbs-dot ${i <= crumbIndex ? "on" : ""}`}></span>
                  {s.label}
                  {i < STEPS.length - 1 && <span style={{ margin: "0 4px", opacity: .4 }}>→</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {route === "brief" && (
        <BriefComposer brief={brief} setBrief={setBrief} onGenerate={() => setRoute("working")} onScreen={() => setRoute("screener")} />
      )}
      {route === "working" && (
        <AIWorking brief={brief}
          onDone={(res) => { setCreators(res.creators); setRecommendation(res.recommendation); setRoute("shortlist") }}
          onError={() => setRoute("brief")} />
      )}
      {route === "shortlist" && (
        <Shortlist creators={creators} weights={weights} setWeights={setWeights} onOpen={open} onRecommend={() => setRoute("recommend")} />
      )}
      {route === "detail" && current && (
        <CreatorDetail c={current} onBack={() => setRoute("shortlist")} onToggle={toggleStatus} onRecommend={() => setRoute("recommend")} />
      )}
      {route === "recommend" && (
        <Recommendation creators={creators} weights={weights} recommendation={recommendation} onBack={() => setRoute("shortlist")} onOpen={open} />
      )}
      {route === "screener" && <Screener onBack={() => setRoute("brief")} />}
    </div>
  )
}

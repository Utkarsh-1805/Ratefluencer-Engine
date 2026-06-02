/* ============ Screens: Ranked Shortlist · Creator Detail · Recommendation ============ */
import { useMemo, useState } from 'react'
import {
  composite, roiScore, bandColor, fmtFollowers, fmtINR, fmtBigINR, compact,
  Avatar, StatusPill, ScoreBar, ScoreChip, ScoreTile, MiniBar, Stat, FLAG_LABELS,
} from '../lib.jsx'

const WEIGHT_DEFS = [
  { key: "impact", name: "True-Impact", hint: "Fraud-adjusted real reach" },
  { key: "authenticity", name: "Authenticity", hint: "Audience quality vs bots" },
  { key: "match", name: "Brand Match", hint: "Fit to brief tone & audience" },
  { key: "roi", name: "ROI / Cost", hint: "Predicted return per rupee" },
]

/* ---------------- Screen 3: Ranked Shortlist ---------------- */
const DEMO_BUDGET = 300000   // ₹3,00,000 — the brief's budget, for the counterfactual cost

export function Shortlist({ creators, weights, setWeights, onOpen, onRecommend }) {
  // The counterfactual: 'impact' = fraud-adjusted True-Impact ranking (flagged sunk to bottom);
  // 'followers' = naive reach ranking (flagged NOT sunk — so the fraud account rises to #1).
  const [rankMode, setRankMode] = useState("impact")

  const ranked = useMemo(() => {
    const scored = creators.map((c) => ({ ...c, _score: composite(c, weights) }))
    if (rankMode === "followers") {
      // rank purely by follower count — fraud is no longer guard-railed to the bottom
      return [...scored].sort((a, b) => b.followers - a.followers)
    }
    const live = scored.filter((c) => c.status !== "flagged" && c.status !== "excluded").sort((a, b) => b._score - a._score)
    const sunk = scored.filter((c) => c.status === "flagged" || c.status === "excluded").sort((a, b) => b._score - a._score)
    return [...live, ...sunk]
  }, [creators, weights, rankMode])

  const featured = ranked[0]
  const rest = ranked.slice(1)
  const recommended = ranked.filter((c) => c.status === "recommended")
  const flagged = ranked.filter((c) => c.status === "flagged")

  const reach = recommended.reduce((s, c) => s + c.followers * (0.35 + c.impact / 400), 0)
  const conversions = Math.round(recommended.reduce((s, c) => s + c.followers * (c.impact / 100) * (c.predicted_roi / 100) * 0.9, 0))
  const avgRoi = recommended.reduce((s, c) => s + c.predicted_roi, 0) / (recommended.length || 1)

  const famous = creators.find((c) => c.handle === "famous.face")

  // Counterfactual cost: if budget were split ∝ followers across the top 5,
  // how much would land on the flagged (bot) #1 account?
  const top5 = ranked.slice(0, 5)
  const sumFollowers = top5.reduce((s, c) => s + c.followers, 0) || 1
  const wastedOnFraud = famous ? (famous.followers / sumFollowers) * DEMO_BUDGET : 0
  const wastedPct = famous ? (famous.followers / sumFollowers) * 100 : 0
  const famousRank = famous ? ranked.findIndex((c) => c.handle === "famous.face") + 1 : 0

  return (
    <div className="screen app-shell" style={{ paddingTop: 34, paddingBottom: 80 }}>
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 16, marginBottom: 22 }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 10 }}>Ranked shortlist</div>
          <h1 style={{ fontSize: 34, letterSpacing: "-0.03em" }}>
            {rankMode === "followers" ? "Creators ranked by follower count" : "Creators ranked by predicted impact"}
          </h1>
          <p className="muted" style={{ marginTop: 8, fontSize: 14.5 }}>Skincare · Women 22–35 · India · ₹3,00,000 · drive online sales</p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 12 }}>
          <div className="seg" role="tablist" aria-label="Ranking mode">
            <button className={`seg-btn ${rankMode === "impact" ? "on" : ""}`} onClick={() => setRankMode("impact")}>True-Impact</button>
            <button className={`seg-btn ${rankMode === "followers" ? "on danger" : ""}`} onClick={() => setRankMode("followers")}>Follower count</button>
          </div>
          <button className="btn btn-primary" onClick={onRecommend}>View recommendation →</button>
        </div>
      </div>

      <div className="r-grid-4" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 18 }}>
        <Stat label="Projected reach" value={compact(reach)} sub="fraud-adjusted" icon="◎" />
        <Stat label="Conversions" value={conversions.toLocaleString("en-IN")} sub="predicted online sales" icon="↗" />
        <Stat label="Projected ROI" value={avgRoi.toFixed(1) + "×"} sub="blended, recommended set" icon="₹" accent="#34D399" />
        <Stat label="Shortlist" value={`${recommended.length} · ${flagged.length}`} sub={`${recommended.length} recommended · ${flagged.length} flagged`} icon="≡" />
      </div>

      {famous && famous.status === "flagged" && rankMode === "impact" && (
        <div className="reveal-banner" style={{ marginBottom: 22 }} onClick={() => onOpen(famous.influencer_id)}>
          <span style={{ fontSize: 20 }}>⚡</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 14.5, color: "var(--bad)" }}>A {fmtFollowers(famous.followers)} {famous.verified ? "verified " : ""}account ranked dead last — see why.</div>
            <div className="muted" style={{ fontSize: 12.5 }}>True-Impact {famous.impact}/100 · ~{Math.round(famous.authenticity_detail.bot_follower_pct)}% bot audience. Reach is not impact.</div>
          </div>
          <span className="btn btn-ghost" style={{ borderColor: "rgba(248,113,113,0.4)", color: "var(--bad)", padding: "8px 14px" }}>Open report →</span>
        </div>
      )}

      {famous && rankMode === "followers" && (
        <div className="reveal-banner" style={{ marginBottom: 22 }} onClick={() => onOpen(famous.influencer_id)}>
          <span style={{ fontSize: 20 }}>⚠️</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 600, fontSize: 14.5, color: "var(--bad)" }}>
              Ranking by reach alone — fraud ignored. @{famous.handle} ({fmtFollowers(famous.followers)}{famous.verified ? ", verified" : ""}) is now #{famousRank}.
            </div>
            <div className="muted" style={{ fontSize: 12.5 }}>
              ~{Math.round(famous.authenticity_detail.bot_follower_pct)}% bot audience · True-Impact {famous.impact}/100. Allocating budget by followers would send <b style={{ color: "var(--bad)" }}>{fmtBigINR(wastedOnFraud)}</b> (~{Math.round(wastedPct)}% of spend) to a fake audience.
            </div>
          </div>
          <span className="btn btn-ghost" style={{ borderColor: "rgba(248,113,113,0.4)", color: "var(--bad)", padding: "8px 14px" }}>See the fraud →</span>
        </div>
      )}

      <div className="r-shortlist" style={{ display: "grid", gridTemplateColumns: "1fr 268px", gap: 22, alignItems: "start" }}>
        <div>
          {featured && <FeaturedCard c={featured} onOpen={onOpen} />}
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 18 }}>
            {rest.map((c, i) => (
              <CreatorRow key={c.influencer_id} c={c} rank={i + 2} onOpen={onOpen} />
            ))}
          </div>
        </div>

        <div className="card r-sidebar" style={{ padding: 20, position: "sticky", top: 78 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 15 }}>Ranking weights</span>
            <button className="linkish" style={{ background: "none", border: "none", fontSize: 12, padding: 0, cursor: "pointer" }}
              onClick={() => setWeights({ impact: 50, authenticity: 50, match: 50, roi: 50 })}>Reset</button>
          </div>
          <p className="dim" style={{ fontSize: 12, marginBottom: 18, lineHeight: 1.45 }}>Drag to re-rank the shortlist live.</p>
          {WEIGHT_DEFS.map((w) => (
            <div key={w.key} className="slider-row">
              <div className="slider-head">
                <span className="slider-name">{w.name}</span>
                <span className="slider-val">{weights[w.key]}%</span>
              </div>
              <input type="range" min="0" max="100" value={weights[w.key]} onChange={(e) => setWeights({ ...weights, [w.key]: +e.target.value })} />
              <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>{w.hint}</div>
            </div>
          ))}
          <div className="divider" style={{ margin: "6px 0 14px" }}></div>
          <div className="dim" style={{ fontSize: 11.5, lineHeight: 1.5 }}>Flagged creators stay sunk to the bottom regardless of weights.</div>
        </div>
      </div>
    </div>
  )
}

function FeaturedCard({ c, onOpen }) {
  const danger = c.status === "flagged"   // the #1 pick is fraud (followers-ranking counterfactual)
  return (
    <div className="card" style={{ position: "relative", overflow: "hidden", borderColor: danger ? "rgba(248,113,113,0.5)" : "rgba(99,102,241,0.45)", cursor: "pointer", padding: 0 }} onClick={() => onOpen(c.influencer_id)}>
      <div className="hero-glow" style={{ animation: "glowPulse 4s ease-in-out infinite", background: danger ? "radial-gradient(120% 120% at 18% 0%, rgba(248,113,113,0.28), transparent 55%)" : undefined }}></div>
      <div style={{ position: "relative", padding: 26 }}>
        <div className="r-card-head" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
          <div className="r-id" style={{ display: "flex", gap: 16, alignItems: "center" }}>
            <Avatar name={c.display_name} size={62} verified={c.verified} radius={18} />
            <div style={{ minWidth: 0 }}>
              <div className="r-id-line" style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span className="r-handle" style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 22, letterSpacing: "-0.02em" }}>@{c.handle}</span>
                <span className={danger ? "pill pill-bad" : "pill pill-accent"}>#1 · {Math.round(c._score)}</span>
              </div>
              <div className="muted" style={{ fontSize: 13.5, marginTop: 3 }}>
                <span className="mono">{fmtFollowers(c.followers)}</span> followers · {c.content_category} · {c.region}
              </div>
            </div>
          </div>
          <StatusPill status={c.status} />
        </div>

        <div className="r-featured" style={{ display: "grid", gridTemplateColumns: "1.6fr 1fr", gap: 28, alignItems: "center" }}>
          <div className="r-featured-scores" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px 26px" }}>
            <ScoreBar label="True-Impact" value={c.impact} />
            <ScoreBar label="Authenticity" value={c.authenticity} />
            <ScoreBar label="Brand Match" value={c.match} />
            <ScoreBar label="Predicted ROI" value={Math.round(roiScore(c.predicted_roi))} suffix={``} />
          </div>
          <div className="r-composite" style={{ textAlign: "center", borderLeft: "1px solid var(--border)", paddingLeft: 24 }}>
            <div className="kicker" style={{ marginBottom: 6 }}>Composite</div>
            <div className="mono" style={{ fontSize: 58, fontWeight: 600, letterSpacing: "-0.04em", lineHeight: 1, color: bandColor(c.impact) }}>{Math.round(c._score)}</div>
            <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>{c.predicted_roi.toFixed(1)}× projected ROI</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function CreatorRow({ c, rank, onOpen }) {
  const flagged = c.status === "flagged" || c.status === "excluded"
  return (
    <div className={`crow ${flagged ? "flagged" : ""}`} onClick={() => onOpen(c.influencer_id)}>
      <div className="crow-rank">{rank}</div>
      <div className="crow-name" style={{ display: "flex", alignItems: "center", gap: 13 }}>
        <Avatar name={c.display_name} size={40} verified={c.verified} />
        <div style={{ minWidth: 0 }}>
          <div className="crow-handle" style={{ fontWeight: 600, fontSize: 14.5, whiteSpace: "nowrap" }}>@{c.handle}</div>
          <div className="dim" style={{ fontSize: 12 }}><span className="mono">{fmtFollowers(c.followers)}</span> followers</div>
        </div>
      </div>
      {flagged ? (
        <div className="crow-flag" style={{ display: "flex", alignItems: "center", gap: 9, color: "var(--bad)", fontSize: 13 }}>
          <span style={{ fontSize: 14 }}>⚑</span>
          <span style={{ opacity: .92 }}>{c.flag_reason || "Excluded from shortlist"}</span>
        </div>
      ) : (
        <div className="crow-chips">
          <ScoreChip label="Impact" value={c.impact} />
          <ScoreChip label="Auth" value={c.authenticity} />
          <ScoreChip label="Match" value={c.match} />
          <ScoreChip label="ROI" value={c.predicted_roi} roi />
        </div>
      )}
      <div className="crow-tail" style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <StatusPill status={c.status} />
        <span className="dim" style={{ fontSize: 16 }}>›</span>
      </div>
    </div>
  )
}

/* ---------------- Screen 4: Creator Detail ---------------- */
export function CreatorDetail({ c, onBack, onToggle, onRecommend }) {
  const ad = c.authenticity_detail
  const flagged = c.status === "flagged"
  const pos = c.drivers.filter((d) => d.effect === "+")
  const neg = c.drivers.filter((d) => d.effect === "-")

  return (
    <div className="screen app-shell" style={{ paddingTop: 30, paddingBottom: 80 }}>
      <button className="btn btn-ghost" onClick={onBack} style={{ marginBottom: 20, padding: "8px 14px" }}>← Back to shortlist</button>

      <div className="card" style={{ padding: 24, marginBottom: 18, position: "relative", overflow: "hidden", borderColor: flagged ? "rgba(248,113,113,0.4)" : "var(--border)" }}>
        {flagged && <div className="hero-glow" style={{ background: "radial-gradient(120% 120% at 18% 0%, rgba(248,113,113,0.22), transparent 55%)" }}></div>}
        <div className="r-card-head" style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 16 }}>
          <div className="r-id" style={{ display: "flex", gap: 17, alignItems: "center" }}>
            <Avatar name={c.display_name} size={64} verified={c.verified} radius={18} />
            <div style={{ minWidth: 0 }}>
              <div className="r-id-line" style={{ display: "flex", alignItems: "center", gap: 11 }}>
                <span className="r-handle" style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 24, letterSpacing: "-0.02em" }}>@{c.handle}</span>
                {c.verified && <span className="pill pill-accent" style={{ padding: "3px 9px" }}>✓ Verified</span>}
              </div>
              <div className="muted" style={{ fontSize: 13.5, marginTop: 4 }}>
                <span className="mono">{fmtFollowers(c.followers)}</span> followers · Instagram · {c.content_category} · {c.region}
              </div>
            </div>
          </div>
          <StatusPill status={c.status} />
        </div>
      </div>

      <div className="r-grid-4" style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 18 }}>
        <ScoreTile label="True-Impact" value={c.impact} />
        <ScoreTile label="Authenticity" value={c.authenticity} />
        <ScoreTile label="Brand Match" value={c.match} />
        <ScoreTile label="Predicted ROI" value={Math.round(roiScore(c.predicted_roi))} />
      </div>

      <div className="r-grid-2" style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18, alignItems: "start" }}>
        <div className="card" style={{ padding: 22, borderColor: flagged ? "rgba(248,113,113,0.4)" : "rgba(52,211,153,0.3)" }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <span style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 16, display: "flex", alignItems: "center", gap: 9 }}>🛡 Fraud screening</span>
            {flagged
              ? <span className="pill pill-bad">{ad.flags.length} flags</span>
              : <span className="pill pill-good">✓ Clean</span>}
          </div>
          {flagged ? (
            <>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 14 }}>
                {ad.flags.map((fl) => (
                  <span key={fl} className="pill pill-bad" style={{ padding: "5px 11px" }}>⚑ {FLAG_LABELS[fl] || fl}</span>
                ))}
              </div>
              <div style={{ padding: "11px 14px", borderRadius: 11, background: "var(--bad-ghost)", color: "var(--bad)", fontSize: 13, marginBottom: 18 }}>
                {c.flag_reason}
              </div>
            </>
          ) : (
            <div style={{ padding: "11px 14px", borderRadius: 11, background: "var(--good-ghost)", color: "var(--good)", fontSize: 13.5, marginBottom: 18 }}>
              ✓ No fraud flags detected — audience and engagement look organic.
            </div>
          )}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MiniBar label="Bot follower %" value={Math.round(ad.bot_follower_pct)} invert />
            <MiniBar label="Comment spam ratio" value={Math.round(ad.comment_spam_ratio * 100)} invert />
            <MiniBar label="Spike anomaly score" value={Math.round(ad.spike_anomaly_score * 100)} invert />
          </div>
        </div>

        <div className="card" style={{ padding: 22 }}>
          <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 16, marginBottom: 16 }}>Score drivers</div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div>
              <div style={{ color: "var(--good)", fontSize: 12.5, fontWeight: 600, marginBottom: 11, display: "flex", alignItems: "center", gap: 6 }}>▲ Positive</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {pos.map((d, i) => (
                  <div key={i} style={{ borderLeft: "2px solid var(--good)", paddingLeft: 11 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{d.feature}</div>
                    <div className="mono dim" style={{ fontSize: 11.5 }}>{d.value}</div>
                  </div>
                ))}
                {pos.length === 0 && <div className="dim" style={{ fontSize: 12.5 }}>None</div>}
              </div>
            </div>
            <div>
              <div style={{ color: "var(--bad)", fontSize: 12.5, fontWeight: 600, marginBottom: 11, display: "flex", alignItems: "center", gap: 6 }}>▼ Negative</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {neg.map((d, i) => (
                  <div key={i} style={{ borderLeft: "2px solid var(--bad)", paddingLeft: 11 }}>
                    <div style={{ fontSize: 13, fontWeight: 500 }}>{d.feature}</div>
                    <div className="mono dim" style={{ fontSize: 11.5 }}>{d.value}</div>
                  </div>
                ))}
                {neg.length === 0 && <div className="dim" style={{ fontSize: 12.5 }}>None</div>}
              </div>
            </div>
          </div>
        </div>

        <div className="card" style={{ padding: 22 }}>
          <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 16, marginBottom: 16 }}>Audience fit</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <MiniBar label="Age match (22–35)" value={c.audience_fit.age_match} />
            <MiniBar label="Gender match (women)" value={c.audience_fit.gender_match} />
            <MiniBar label="Geo match (India)" value={c.audience_fit.geo_match} />
          </div>
        </div>

        <div className="card" style={{ padding: 22, display: "flex", flexDirection: "column", justifyContent: "center", gap: 13 }}>
          <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 16, marginBottom: 2 }}>Actions</div>
          <button className="btn btn-primary" onClick={onRecommend} style={{ justifyContent: "center" }}>View recommendation</button>
          <button className="btn" onClick={() => onToggle(c.influencer_id)} style={{ justifyContent: "center" }}>
            {c.status === "excluded" ? "Include in shortlist" : c.status === "flagged" ? "Override & include" : "Exclude from shortlist"}
          </button>
          <button className="btn btn-ghost" onClick={onBack} style={{ justifyContent: "center" }}>Back to shortlist</button>
        </div>
      </div>
    </div>
  )
}

/* ---------------- Screen 5: Recommendation / Export ---------------- */
export function Recommendation({ creators, weights, recommendation, onBack, onOpen }) {
  const ranked = useMemo(() => {
    return creators
      .filter((c) => c.status === "recommended")
      .map((c) => ({ ...c, _score: composite(c, weights) }))
      .sort((a, b) => b._score - a._score)
  }, [creators, weights])

  const flagged = creators.filter((c) => c.status === "flagged")
  const top = ranked.slice(0, 5)
  // total budget from the API recommendation's allocation if present, else ₹3L
  const total = (recommendation?.budget_split || []).reduce((s, b) => s + (b.allocated || 0), 0) || 300000

  const sumScore = top.reduce((s, c) => s + c._score, 0) || 1
  const alloc = top.map((c) => ({ ...c, _budget: (c._score / sumScore) * total }))

  const blendedRoi = alloc.reduce((s, c) => s + c.predicted_roi * (c._budget / total), 0)
  const reach = alloc.reduce((s, c) => s + c.followers * (0.35 + c.impact / 400), 0)
  const conversions = Math.round(alloc.reduce((s, c) => s + c.followers * (c.impact / 100) * (c.predicted_roi / 100) * 0.9, 0))

  // prefer the API's rationale per recommended handle, else a generic line
  const recRationale = {}
  ;(recommendation?.budget_split || []).forEach((b) => {
    recRationale[(b.handle || '').replace(/^@/, '')] = b.rationale
  })
  const lineFor = (c) => recRationale[c.handle] || `On-brief ${c.content_category} creator · Impact ${c.impact}, Auth ${c.authenticity}.`

  function exportTxt() {
    const lines = []
    lines.push("RATEFLUENCER COPILOT — CAMPAIGN RECOMMENDATION")
    lines.push("=".repeat(52)); lines.push("")
    lines.push("Brief: DTC skincare · women 22–35 · India · drive online sales")
    lines.push(`Total budget: ${fmtINR(total)}`); lines.push("")
    lines.push(`Projected ROI: ${blendedRoi.toFixed(1)}x   Reach: ${compact(reach)}   Conversions: ${conversions.toLocaleString("en-IN")}`)
    lines.push(""); lines.push("RATIONALE"); lines.push("-".repeat(52))
    lines.push(recommendation?.summary || "Ranked by fraud-adjusted predicted business impact, not follower count.")
    lines.push(""); lines.push("RECOMMENDED CREATORS & BUDGET ALLOCATION"); lines.push("-".repeat(52))
    alloc.forEach((c, i) => {
      lines.push(`${i + 1}. @${c.handle}  (${fmtFollowers(c.followers)} followers)`)
      lines.push(`   Composite ${Math.round(c._score)} · Impact ${c.impact} · Auth ${c.authenticity} · Match ${c.match} · ROI ${c.predicted_roi.toFixed(1)}x`)
      lines.push(`   Budget: ${fmtINR(c._budget)}  —  ${lineFor(c)}`); lines.push("")
    })
    if (flagged.length) {
      lines.push("EXCLUDED (FRAUD-FLAGGED)"); lines.push("-".repeat(52))
      flagged.forEach((c) => lines.push(`x @${c.handle} (${fmtFollowers(c.followers)}${c.verified ? ", verified" : ""}) — ${c.flag_reason}`))
      lines.push("")
    }
    lines.push("Generated by Ratefluencer Copilot · predicted impact over follower count.")
    const blob = new Blob([lines.join("\n")], { type: "text/plain" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url; a.download = "ratefluencer-recommendation.txt"
    document.body.appendChild(a); a.click(); a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="screen app-shell" style={{ paddingTop: 30, paddingBottom: 80 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 22, flexWrap: "wrap", gap: 14 }}>
        <button className="btn btn-ghost" onClick={onBack} style={{ padding: "8px 14px" }}>← Back to shortlist</button>
        <button className="btn btn-primary" onClick={exportTxt}>⤓ Download recommendation</button>
      </div>

      <div className="card" style={{ padding: 0, position: "relative", overflow: "hidden", marginBottom: 18, borderColor: "rgba(99,102,241,0.4)" }}>
        <div className="hero-glow"></div>
        <div className="r-roihero" style={{ position: "relative", padding: 30, display: "grid", gridTemplateColumns: "auto 1fr", gap: 36, alignItems: "center" }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Projected campaign ROI</div>
            <div className="mono" style={{ fontSize: 76, fontWeight: 600, lineHeight: 1, letterSpacing: "-0.04em", color: "#34D399" }}>{blendedRoi.toFixed(1)}×</div>
          </div>
          <div className="r-grid-3" style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
            <div className="card" style={{ padding: 16, background: "var(--surface-2)" }}>
              <div className="dim" style={{ fontSize: 12 }}>Total budget</div>
              <div className="mono" style={{ fontSize: 24, fontWeight: 600, marginTop: 6 }}>{fmtBigINR(total)}</div>
            </div>
            <div className="card" style={{ padding: 16, background: "var(--surface-2)" }}>
              <div className="dim" style={{ fontSize: 12 }}>Projected reach</div>
              <div className="mono" style={{ fontSize: 24, fontWeight: 600, marginTop: 6 }}>{compact(reach)}</div>
            </div>
            <div className="card" style={{ padding: 16, background: "var(--surface-2)" }}>
              <div className="dim" style={{ fontSize: 12 }}>Conversions</div>
              <div className="mono" style={{ fontSize: 24, fontWeight: 600, marginTop: 6 }}>{conversions.toLocaleString("en-IN")}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 22, marginBottom: 18 }}>
        <div className="kicker" style={{ marginBottom: 10, display: "flex", alignItems: "center", gap: 8 }}><span style={{ color: "var(--accent-2)" }}>✦</span> AI rationale</div>
        <p style={{ fontSize: 16, lineHeight: 1.6, margin: 0, maxWidth: 880 }}>
          {recommendation?.summary ||
            "We ranked every candidate by fraud-adjusted predicted business impact, not follower count. The budget concentrates on micro and nano creators with authentic, on-tone audiences."}
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 18 }}>
        <div className="card" style={{ padding: 22 }}>
          <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 17, marginBottom: 18 }}>Recommended creators & budget allocation</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {alloc.map((c, i) => {
              const pct = (c._budget / total) * 100
              return (
                <div key={c.influencer_id} className="r-alloc" style={{ display: "grid", gridTemplateColumns: "26px 200px 1fr 120px", gap: 18, alignItems: "center", cursor: "pointer" }} onClick={() => onOpen(c.influencer_id)}>
                  <div className="mono dim" style={{ fontWeight: 600 }}>{i + 1}</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <Avatar name={c.display_name} size={38} verified={c.verified} />
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 14 }}>@{c.handle}</div>
                      <div className="dim" style={{ fontSize: 11.5 }}><span className="mono">{fmtFollowers(c.followers)}</span> · ROI {c.predicted_roi.toFixed(1)}×</div>
                    </div>
                  </div>
                  <div className="r-alloc-bar">
                    <div className="sbar-track" style={{ height: 8 }}>
                      <div className="sbar-fill" style={{ width: pct + "%", background: "linear-gradient(90deg,#818CF8,#6366F1)" }}></div>
                    </div>
                    <div className="dim" style={{ fontSize: 11.5, marginTop: 6, lineHeight: 1.4 }}>{lineFor(c)}</div>
                  </div>
                  <div className="r-alloc-amt" style={{ textAlign: "right" }}>
                    <div className="mono" style={{ fontWeight: 600, fontSize: 16 }}>{fmtINR(c._budget)}</div>
                    <div className="dim" style={{ fontSize: 11 }}>{pct.toFixed(0)}% of budget</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {flagged.length > 0 && (
          <div className="card" style={{ padding: 22, borderColor: "rgba(248,113,113,0.35)", background: "rgba(248,113,113,0.04)" }}>
            <div style={{ fontFamily: "var(--font-head)", fontWeight: 600, fontSize: 16, marginBottom: 14, color: "var(--bad)", display: "flex", alignItems: "center", gap: 9 }}>⚑ Excluded — fraud-flagged</div>
            {flagged.map((c) => (
              <div key={c.influencer_id} style={{ display: "flex", alignItems: "center", gap: 14, cursor: "pointer" }} onClick={() => onOpen(c.influencer_id)}>
                <Avatar name={c.display_name} size={42} verified={c.verified} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14.5 }}>@{c.handle} <span className="dim" style={{ fontWeight: 400 }}>· <span className="mono">{fmtFollowers(c.followers)}</span> followers{c.verified ? " · verified" : ""}</span></div>
                  <div style={{ fontSize: 13, color: "var(--bad)", marginTop: 2 }}>{c.flag_reason}</div>
                </div>
                <span className="pill pill-bad">True-Impact {c.impact}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

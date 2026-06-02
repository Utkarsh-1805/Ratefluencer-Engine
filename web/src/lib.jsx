/* ============ Ratefluencer Copilot — shared UI primitives (ES module) ============ */

/* ---- helpers ---- */
export function band(score) { return score >= 60 ? "good" : score >= 50 ? "watch" : "bad"; }
export function bandColor(score) {
  const c = { good: "#34D399", watch: "#FBBF24", bad: "#F87171" };
  return c[band(score)];
}
export function fmtFollowers(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + "K";
  return String(n);
}
export function fmtINR(n) {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}
export function fmtBigINR(n) {
  if (n >= 100000) return "₹" + (n / 100000).toFixed(2).replace(/\.00$/, "") + "L";
  return fmtINR(n);
}
export function compact(n) {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(0) + "K";
  return String(n);
}
/* avatar color from handle */
export function avatarColor(handle) {
  let h = 0;
  for (let i = 0; i < handle.length; i++) h = (h * 31 + handle.charCodeAt(i)) % 360;
  return `linear-gradient(140deg, hsl(${h} 52% 56%), hsl(${(h + 38) % 360} 56% 42%))`;
}
export function initials(name) {
  const p = name.replace(/[@.]/g, " ").trim().split(/\s+/);
  return ((p[0]?.[0] || "") + (p[1]?.[0] || "")).toUpperCase();
}

/* roi → 0-100 score for ranking (₹roi capped at 6) */
export function roiScore(roi) { return Math.max(0, Math.min(100, (roi / 6) * 100)); }

/* composite from weights */
export function composite(c, w) {
  const sum = w.impact + w.authenticity + w.match + w.roi || 1;
  return (
    (w.impact * c.impact + w.authenticity * c.authenticity + w.match * c.match + w.roi * roiScore(c.predicted_roi)) / sum
  );
}

/* flag labels + default brief */
export const FLAG_LABELS = {
  bot_followers: "Bot followers",
  engagement_pod: "Engagement pod",
  spike_anomaly: "Follower spike anomaly",
  comment_spam: "Comment spam",
};
export const BRIEF_DEFAULT =
  "DTC skincare brand targeting women aged 22–35 in India. Budget ₹3,00,000. " +
  "Goal: drive online sales. Clean, science-backed tone. Promoting a new SPF serum.";

/* POST helper to the FastAPI bridge (via Vite proxy at /api) */
export async function api(path, body) {
  const res = await fetch('/api' + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  if (!res.ok) throw new Error('API ' + res.status);
  return res.json();
}

/* ---- components ---- */
export function Avatar({ name, size = 44, verified = false, radius }) {
  return (
    <div className="avatar" style={{ width: size, height: size, background: avatarColor(name), fontSize: size * 0.36, borderRadius: radius || Math.round(size * 0.29) }}>
      {initials(name)}
      {verified && <span className="verified" style={{ color: "#fff" }}>✓</span>}
    </div>
  );
}

export function StatusPill({ status }) {
  if (status === "recommended") return <span className="pill pill-good"><span className="pill-dot"></span>Recommended</span>;
  if (status === "flagged") return <span className="pill pill-bad"><span className="pill-dot"></span>Flagged</span>;
  if (status === "excluded") return <span className="pill pill-watch"><span className="pill-dot"></span>Excluded</span>;
  return null;
}

export function ScoreBar({ label, value, suffix = "" }) {
  const col = bandColor(value);
  return (
    <div className="sbar-wrap">
      <div className="sbar-top">
        <span className="sbar-label">{label}</span>
        <span className="sbar-val" style={{ color: col }}>{value}{suffix}</span>
      </div>
      <div className="sbar-track">
        <div className="sbar-fill" style={{ width: Math.max(3, value) + "%", background: col }}></div>
      </div>
    </div>
  );
}

export function ScoreChip({ label, value, roi = false }) {
  const num = roi ? Math.round(roiScore(value)) : value;
  const col = bandColor(num);
  return (
    <div className="schip">
      <span className="schip-k">{label}</span>
      <span className="schip-v" style={{ color: col }}>{roi ? value.toFixed(1) + "×" : value}</span>
    </div>
  );
}

export function ScoreTile({ label, value, suffix = "", big }) {
  const col = bandColor(value);
  return (
    <div className="card" style={{ padding: "16px 18px", borderColor: `${col}33`, background: `linear-gradient(180deg, ${col}0d, transparent)` }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 12, color: "var(--text-2)", fontWeight: 500 }}>{label}</span>
        <span className="pill" style={{ background: `${col}1f`, color: col, padding: "3px 9px", fontSize: 11 }}>{band(value) === "good" ? "Strong" : band(value) === "watch" ? "Watch" : "Poor"}</span>
      </div>
      <div className="mono" style={{ fontSize: big ? 38 : 30, fontWeight: 600, color: col, marginTop: 8, letterSpacing: "-0.02em" }}>
        {value}{suffix}
      </div>
      <div className="sbar-track" style={{ marginTop: 12 }}>
        <div className="sbar-fill" style={{ width: Math.max(3, value) + "%", background: col }}></div>
      </div>
    </div>
  );
}

export function MiniBar({ label, value, max = 100, invert = false, suffix = "%" }) {
  const pct = Math.max(2, Math.min(100, (value / max) * 100));
  const col = invert ? bandColor(100 - pct) : bandColor(pct);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontSize: 12, color: "var(--text-2)" }}>{label}</span>
        <span className="mono" style={{ fontSize: 12.5, color: col, fontWeight: 600 }}>{value}{suffix}</span>
      </div>
      <div className="sbar-track" style={{ height: 6 }}>
        <div className="sbar-fill" style={{ width: pct + "%", background: col }}></div>
      </div>
    </div>
  );
}

export function Stat({ label, value, sub, icon, accent }) {
  return (
    <div className="card stat">
      <div className="stat-k">{icon && <span style={{ color: accent || "var(--accent-2)" }}>{icon}</span>}{label}</div>
      <div className="stat-v" style={accent ? { color: accent } : null}>{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

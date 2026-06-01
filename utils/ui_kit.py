"""
utils/ui_kit.py — Reusable HTML/CSS building blocks for the redesigned UI.
All renderers return HTML strings (no Streamlit calls) so they can be
composed inside st.markdown(..., unsafe_allow_html=True).

Design system tokens live in app.py (DESIGN_CSS). Fonts are untouched.
"""
from utils.components import fmt_followers


# ----------------------------------------------------------------------------- helpers
def initials(name: str) -> str:
    parts = [p for p in name.replace("@", "").replace(".", " ").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[1][0]).upper()


def score_color(v) -> str:
    if v >= 75:
        return "var(--good)"
    if v >= 50:
        return "var(--warn)"
    return "var(--bad)"


def score_tone(v) -> str:
    if v >= 75:
        return "good"
    if v >= 50:
        return "warn"
    return "bad"


def roi_color(v) -> str:
    return "var(--good)" if v > 0 else "var(--bad)"


def status_meta(status: str):
    return {
        "recommended": ("good", "Recommended"),
        "flagged":     ("bad",  "Flagged · Excluded"),
        "excluded":    ("muted", "Excluded"),
    }.get(status, ("muted", status.title()))


# ----------------------------------------------------------------------------- atoms
def pill(text: str, tone: str = "muted") -> str:
    return f'<span class="rf-pill rf-pill--{tone}">{text}</span>'


def chip(label: str, value, tone: str = None) -> str:
    tone = tone or score_tone(value if isinstance(value, (int, float)) else 0)
    return (
        f'<span class="rf-chip rf-chip--{tone}">'
        f'<span class="rf-chip-l">{label}</span>'
        f'<span class="rf-chip-v">{value}</span></span>'
    )


def stat_tile(label: str, value: str, accent: str = "var(--text)") -> str:
    return (
        f'<div class="rf-stat">'
        f'<div class="rf-stat-l">{label}</div>'
        f'<div class="rf-stat-v" style="color:{accent}">{value}</div>'
        f'</div>'
    )


def metric_bar(label: str, value, suffix: str = "") -> str:
    pct = max(0, min(100, value if isinstance(value, (int, float)) else 0))
    col = score_color(value)
    return (
        f'<div class="rf-mbar">'
        f'<div class="rf-mbar-head"><span class="rf-mbar-l">{label}</span>'
        f'<span class="rf-mbar-v" style="color:{col}">{value}{suffix}</span></div>'
        f'<div class="rf-mbar-track"><div class="rf-mbar-fill" '
        f'style="width:{pct}%;background:{col}"></div></div></div>'
    )


# ----------------------------------------------------------------------------- featured #1 card
def featured_card_html(rank: int, s: dict) -> str:
    roi = s["predicted_roi"]
    rcol = roi_color(roi)
    composite = s.get("composite", s["impact"])
    return f"""
<div class="rf-feature">
  <div class="rf-feature-aura"></div>
  <div class="rf-feature-row">
    <span class="rf-trophy">★ #1 RECOMMENDED CREATOR</span>
    <span class="rf-pill rf-pill--good">Recommended</span>
  </div>
  <div class="rf-feature-head">
    <div class="rf-avatar rf-avatar--lg">{initials(s.get("display_name", s["handle"]))}</div>
    <div class="rf-feature-id">
      <div class="rf-handle">{s["handle"]}</div>
      <div class="rf-sub">{s.get("display_name","")} &nbsp;·&nbsp; {fmt_followers(s["followers"])} followers
      &nbsp;·&nbsp; {s["platform"]} &nbsp;·&nbsp; {s["content_category"]}</div>
    </div>
    <div class="rf-composite">
      <div class="rf-composite-v">{composite}</div>
      <div class="rf-composite-l">COMPOSITE</div>
    </div>
  </div>
  <div class="rf-feature-grid">
    {metric_bar("True-Impact", s["impact"])}
    {metric_bar("Authenticity", s["authenticity"])}
    {metric_bar("Brand Match", s["match"])}
    <div class="rf-mbar rf-mbar--roi">
      <div class="rf-mbar-head"><span class="rf-mbar-l">Predicted ROI</span></div>
      <div class="rf-roi-big" style="color:{rcol}">{roi:.1f}x</div>
    </div>
  </div>
</div>
"""


# ----------------------------------------------------------------------------- ranked row card
def ranked_card_html(rank: int, s: dict) -> str:
    status = s["status"]
    flagged = status == "flagged"
    roi = s["predicted_roi"]
    rcol = roi_color(roi)
    tone, label = status_meta(status)
    flag_line = ""
    if flagged and s.get("flag_reason"):
        flag_line = f'<div class="rf-flag-reason">⚠ {s["flag_reason"]}</div>'
    return f"""
<div class="rf-card {'rf-card--flagged' if flagged else ''}">
  <div class="rf-card-main">
    <div class="rf-rank">{rank}</div>
    <div class="rf-avatar">{initials(s.get("display_name", s["handle"]))}</div>
    <div class="rf-card-id">
      <div class="rf-handle-sm">{s["handle"]}</div>
      <div class="rf-sub-sm">{fmt_followers(s["followers"])} &nbsp;·&nbsp; {s["content_category"]}</div>
    </div>
    <div class="rf-card-metrics">
      {chip("Impact", s["impact"])}
      {chip("Auth", s["authenticity"])}
      {chip("Match", s["match"])}
      <span class="rf-chip rf-chip--{'good' if roi>0 else 'bad'}">
        <span class="rf-chip-l">ROI</span><span class="rf-chip-v">{roi:.1f}x</span></span>
      {pill(label, tone)}
    </div>
  </div>
  {flag_line}
</div>
"""


def section(title: str, sub: str = "") -> str:
    sub_html = f'<div class="rf-sec-sub">{sub}</div>' if sub else ""
    return f'<div class="rf-sec"><div class="rf-sec-title">{title}</div>{sub_html}</div>'


def page_header(title: str, subtitle: str, eyebrow: str = "") -> str:
    eye = f'<div class="rf-eyebrow">{eyebrow}</div>' if eyebrow else ""
    return (
        f'<div class="rf-page-head">{eye}'
        f'<div class="rf-page-title">{title}</div>'
        f'<div class="rf-page-sub">{subtitle}</div></div>'
    )
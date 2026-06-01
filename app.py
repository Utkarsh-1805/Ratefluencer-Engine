import streamlit as st
from ui.brief_composer import render_brief_composer
from ui.agent_working import render_agent_working
from ui.ranked_shortlist import render_ranked_shortlist
from ui.creator_detail import render_creator_detail
from ui.recommendation import render_recommendation
from utils.session import init_session
import base64
from pathlib import Path

font_path = Path("assets/TT Hoves Pro Trial DemiBold.ttf")

with open(font_path, "rb") as f:
    tt_hoves = base64.b64encode(f.read()).decode()
    
with open("assets/WorkSans-Regular.ttf", "rb") as f:
    work_sans_regular = base64.b64encode(f.read()).decode()

with open("assets/WorkSans-Medium.ttf", "rb") as f:
    work_sans_medium = base64.b64encode(f.read()).decode()

with open("assets/WorkSans-SemiBold.ttf", "rb") as f:
    work_sans_semibold = base64.b64encode(f.read()).decode()

st.set_page_config(
    page_title="Ratefluencer Copilot",
    page_icon="assets/favicon.svg",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
  }
  
  :root {
    --font-heading: 'TTHoves', sans-serif;
    --font-body: 'WorkSans', sans-serif;
  }

  .score-chip {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.88rem;
    color: #fff;
    letter-spacing: 0.02em;
  }
  .chip-green { background: #059669; }
  .chip-amber { background: #D97706; }
  .chip-red   { background: #DC2626; }

  .status-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 12px;
    border-radius: 999px;
    font-weight: 600;
    font-size: 0.78rem;
  }
  .pill-recommended { background: #D1FAE5; color: #065F46; }
  .pill-flagged     { background: #FEE2E2; color: #991B1B; }
  .pill-excluded    { background: #F3F4F6; color: #6B7280; }

  .label {
    font-size: 0.72rem;
    color: #6B7280;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .row-green  { background: #ECFDF5; border-left: 4px solid #059669; padding: 10px 12px; border-radius: 6px; margin: 4px 0; }
  .row-red    { background: #FEF2F2; border-left: 4px solid #DC2626; padding: 10px 12px; border-radius: 6px; margin: 4px 0; }
  .row-normal { background: #F9FAFB; border-left: 4px solid #E5E7EB; padding: 10px 12px; border-radius: 6px; margin: 4px 0; }

  .page-title {
    font-size: 1.9rem;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.02em;
  }
  .page-subtitle {
    font-size: 0.95rem;
    color: #ffffff;
    margin-top: 2px;
  }
  .section-heading {
    font-size: 1.05rem;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 8px;
  }
  
  
  /* =========================
   CUSTOM FONTS
========================= */

@font-face {
    font-family: 'TTHoves';
    src: url('assets/fonts/TT Hoves Pro Trial DemiBold.ttf');
    font-weight: 600;
}

@font-face {
    font-family: 'WorkSans';
    src: url('assets/fonts/WorkSans-Regular.ttf');
    font-weight: 400;
}

/* =========================
   HEADINGS
========================= */

h1,
h2,
h3,
h4,
h5,
h6,
.page-title,
.page-subtitle,
.section-heading {
    var(--font-heading);
}

/* =========================
   BODY CONTENT
========================= */

body,
p,
span,
div,
label,
li,
input,
textarea,
button,
select,
.stMarkdown,
.stText,
.stCaption,
.stAlert,
.stMetric,
.stDataFrame {
    font-family: var(--font-body);
}

h1,h2,h3,h4,h5,h6{
   font-family: var(--font-body);
}
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<style>

@font-face {{
    font-family: 'TTHoves';
    src: url(data:font/ttf;base64,{tt_hoves}) format('truetype');
    font-weight: 600;
}}

@font-face {{
    font-family: 'WorkSans';
    src: url(data:font/ttf;base64,{work_sans_regular}) format('truetype');
    font-weight: 400;
}}

@font-face {{
    font-family: 'WorkSans';
    src: url(data:font/ttf;base64,{work_sans_medium}) format('truetype');
    font-weight: 500;
}}

@font-face {{
    font-family: 'WorkSans';
    src: url(data:font/ttf;base64,{work_sans_semibold}) format('truetype');
    font-weight: 600;
}}

.page-title,
.page-subtitle,
.section-heading,
h1,h2,h3,h4,h5,h6 {{
    font-family: 'TTHoves' !important;
}}

body,
p,
span,
div,
label,
li,
input,
textarea,
button,
select {{
    font-family: 'WorkSans' !important;
}}

</style>
""", unsafe_allow_html=True)

# =============================================================================
#  DESIGN SYSTEM  (loaded AFTER the font blocks so fonts are never overridden)
# =============================================================================
st.markdown("""
<style>
:root{
  --bg:#0A0B0D; --surface:#131519; --surface-2:#16191F; --surface-3:#1B1F26;
  --border:#262A31; --border-soft:#1F232A;
  --text:#F4F5F7; --text-2:#9CA3AF; --text-3:#6B7280;
  --accent:#6366F1; --accent-2:#818CF8; --accent-soft:rgba(99,102,241,.14);
  --good:#34D399; --good-bg:rgba(52,211,153,.12);
  --warn:#FBBF24; --warn-bg:rgba(251,191,36,.12);
  --bad:#F87171;  --bad-bg:rgba(248,113,113,.12);
  --muted:#6B7280; --muted-bg:rgba(107,114,128,.14);
}

/* ---- canvas ---- */
.stApp{ background:var(--bg); }
.block-container{ max-width:1080px; padding-top:2.4rem; padding-bottom:4rem; }
[data-testid="stHeader"]{ background:transparent; }
hr, [data-testid="stMarkdownContainer"] hr{ display:none; }

/* ---- page header ---- */
.rf-page-head{ margin-bottom:1.6rem; }
.rf-eyebrow{ font-size:.72rem; letter-spacing:.16em; text-transform:uppercase;
  color:var(--accent-2); font-weight:600; margin-bottom:.55rem; }
.rf-page-title{ font-family:'TTHoves'!important; font-size:2.15rem; line-height:1.1;
  color:var(--text); letter-spacing:-.02em; }
.rf-page-sub{ font-size:.98rem; color:var(--text-2); margin-top:.5rem; max-width:640px; }

/* ---- section heading ---- */
.rf-sec{ margin:1.9rem 0 .9rem; }
.rf-sec-title{ font-family:'TTHoves'!important; font-size:1.06rem; color:var(--text);
  letter-spacing:-.01em; }
.rf-sec-sub{ font-size:.85rem; color:var(--text-3); margin-top:.2rem; }

/* ---- pills & chips ---- */
.rf-pill{ display:inline-flex; align-items:center; gap:.3rem; padding:.22rem .65rem;
  border-radius:999px; font-size:.74rem; font-weight:600; letter-spacing:.01em;
  white-space:nowrap; }
.rf-pill--good{ background:var(--good-bg); color:var(--good); }
.rf-pill--bad{ background:var(--bad-bg); color:var(--bad); }
.rf-pill--warn{ background:var(--warn-bg); color:var(--warn); }
.rf-pill--muted{ background:var(--muted-bg); color:var(--text-2); }

.rf-chip{ display:inline-flex; align-items:center; gap:.4rem; padding:.28rem .6rem;
  border-radius:8px; font-size:.78rem; background:var(--surface-3);
  border:1px solid var(--border-soft); }
.rf-chip-l{ color:var(--text-3); font-size:.72rem; }
.rf-chip-v{ font-weight:700; }
.rf-chip--good .rf-chip-v{ color:var(--good); }
.rf-chip--warn .rf-chip-v{ color:var(--warn); }
.rf-chip--bad  .rf-chip-v{ color:var(--bad); }

/* ---- avatars ---- */
.rf-avatar{ width:42px; height:42px; border-radius:12px; flex:0 0 auto;
  display:flex; align-items:center; justify-content:center; font-weight:700;
  font-size:.95rem; color:#fff;
  background:linear-gradient(135deg,#4F46E5,#7C3AED); letter-spacing:.02em; }
.rf-avatar--lg{ width:62px; height:62px; border-radius:16px; font-size:1.35rem;
  box-shadow:0 0 0 4px rgba(99,102,241,.12); }

/* ---- stat tiles row ---- */
.rf-stats{ display:grid; grid-template-columns:repeat(4,1fr); gap:.8rem; margin-top:.4rem; }
.rf-stat{ background:var(--surface); border:1px solid var(--border-soft);
  border-radius:14px; padding:1rem 1.1rem; }
.rf-stat-l{ font-size:.74rem; letter-spacing:.05em; text-transform:uppercase;
  color:var(--text-3); }
.rf-stat-v{ font-family:'TTHoves'!important; font-size:1.7rem; margin-top:.3rem;
  letter-spacing:-.01em; }

/* ---- mini metric bars ---- */
.rf-mbar-head{ display:flex; justify-content:space-between; align-items:baseline;
  margin-bottom:.4rem; }
.rf-mbar-l{ font-size:.78rem; color:var(--text-2); }
.rf-mbar-v{ font-family:'TTHoves'!important; font-size:1.05rem; }
.rf-mbar-track{ height:6px; border-radius:999px; background:var(--surface-3); overflow:hidden; }
.rf-mbar-fill{ height:100%; border-radius:999px; }
.rf-roi-big{ font-family:'TTHoves'!important; font-size:1.55rem; line-height:1; }

/* ---- featured card ---- */
.rf-feature{ position:relative; overflow:hidden; border-radius:20px;
  background:linear-gradient(160deg,#171A21 0%,#121419 100%);
  border:1px solid rgba(99,102,241,.32); padding:1.5rem 1.6rem 1.65rem;
  box-shadow:0 18px 48px -20px rgba(99,102,241,.45); }
.rf-feature-aura{ position:absolute; top:-120px; right:-90px; width:320px; height:320px;
  background:radial-gradient(circle,rgba(99,102,241,.35),transparent 70%);
  filter:blur(8px); pointer-events:none; }
.rf-feature-row{ display:flex; justify-content:space-between; align-items:center;
  position:relative; z-index:1; }
.rf-trophy{ font-size:.74rem; font-weight:700; letter-spacing:.12em;
  color:var(--accent-2); }
.rf-feature-head{ display:flex; align-items:center; gap:1rem; margin:1.1rem 0 1.3rem;
  position:relative; z-index:1; }
.rf-feature-id{ flex:1 1 auto; }
.rf-handle{ font-family:'TTHoves'!important; font-size:1.6rem; color:var(--text);
  letter-spacing:-.01em; }
.rf-sub{ font-size:.85rem; color:var(--text-2); margin-top:.25rem; }
.rf-composite{ text-align:center; padding-left:1rem;
  border-left:1px solid var(--border); flex:0 0 auto; }
.rf-composite-v{ font-family:'TTHoves'!important; font-size:2.7rem; line-height:1;
  color:var(--accent-2); }
.rf-composite-l{ font-size:.66rem; letter-spacing:.14em; color:var(--text-3); margin-top:.25rem; }
.rf-feature-grid{ display:grid; grid-template-columns:repeat(4,1fr); gap:1.2rem;
  position:relative; z-index:1; }

/* ---- ranked cards ---- */
.rf-card{ background:var(--surface); border:1px solid var(--border-soft);
  border-radius:14px; padding:.85rem 1.05rem; transition:border-color .15s, background .15s; }
.rf-card:hover{ border-color:var(--border); background:var(--surface-2); }
.rf-card--flagged{ border-color:rgba(248,113,113,.32);
  background:linear-gradient(180deg,rgba(248,113,113,.05),var(--surface)); }
.rf-card-main{ display:flex; align-items:center; gap:.85rem; }
.rf-rank{ font-family:'TTHoves'!important; font-size:1.05rem; color:var(--text-3);
  width:22px; text-align:center; flex:0 0 auto; }
.rf-card-id{ flex:0 0 auto; min-width:150px; }
.rf-handle-sm{ font-weight:600; color:var(--text); font-size:.96rem; }
.rf-sub-sm{ font-size:.76rem; color:var(--text-3); margin-top:.1rem; }
.rf-card-metrics{ display:flex; gap:.45rem; flex-wrap:wrap; margin-left:auto;
  align-items:center; justify-content:flex-end; }
.rf-flag-reason{ margin-top:.65rem; padding-left:calc(22px + .85rem + 42px + .85rem);
  font-size:.8rem; color:var(--bad); }

/* ---- generic panel ---- */
.rf-panel{ background:var(--surface); border:1px solid var(--border-soft);
  border-radius:16px; padding:1.25rem 1.4rem; }
.rf-panel--accent{ border-color:rgba(99,102,241,.3);
  background:linear-gradient(160deg,rgba(99,102,241,.08),var(--surface)); }
.rf-panel--bad{ border-color:rgba(248,113,113,.32);
  background:linear-gradient(160deg,rgba(248,113,113,.07),var(--surface)); }

/* ---- driver rows ---- */
.rf-driver{ display:flex; align-items:center; gap:.7rem; padding:.6rem .8rem;
  border-radius:10px; margin-bottom:.5rem; font-size:.88rem; }
.rf-driver--pos{ background:var(--good-bg); border:1px solid rgba(52,211,153,.22); }
.rf-driver--neg{ background:var(--bad-bg); border:1px solid rgba(248,113,113,.22); }
.rf-driver-dot{ width:8px; height:8px; border-radius:50%; flex:0 0 auto; }
.rf-driver--pos .rf-driver-dot{ background:var(--good); }
.rf-driver--neg .rf-driver-dot{ background:var(--bad); }
.rf-driver-feat{ color:var(--text); flex:1 1 auto; }
.rf-driver-val{ color:var(--text-2); font-size:.8rem; font-weight:600; }

/* ---- fraud flags ---- */
.rf-fraud{ display:flex; flex-wrap:wrap; gap:.5rem; margin-top:.3rem; }
.rf-fraud-tag{ display:inline-flex; align-items:center; gap:.35rem; padding:.35rem .7rem;
  border-radius:8px; background:var(--bad-bg); color:var(--bad);
  border:1px solid rgba(248,113,113,.28); font-size:.8rem; font-weight:600; }
.rf-clean{ display:inline-flex; align-items:center; gap:.4rem; padding:.4rem .8rem;
  border-radius:8px; background:var(--good-bg); color:var(--good);
  border:1px solid rgba(52,211,153,.28); font-size:.85rem; font-weight:600; }

/* ---- big ROI hero (recommendation) ---- */
.rf-roi-hero{ display:flex; align-items:center; gap:1.5rem; }
.rf-roi-hero-v{ font-family:'TTHoves'!important; font-size:4.2rem; line-height:.95;
  color:var(--good); letter-spacing:-.03em; }
.rf-roi-hero-l{ font-size:.78rem; letter-spacing:.12em; text-transform:uppercase;
  color:var(--text-3); }

/* ---- detected insight chips (brief) ---- */
.rf-insights{ display:flex; flex-wrap:wrap; gap:.5rem; }
.rf-insight{ display:inline-flex; align-items:center; gap:.45rem; padding:.4rem .75rem;
  border-radius:10px; background:var(--surface-3); border:1px solid var(--border-soft);
  font-size:.82rem; color:var(--text); }
.rf-insight b{ color:var(--accent-2); font-weight:600; }
.rf-insight-k{ color:var(--text-3); font-size:.74rem; text-transform:uppercase;
  letter-spacing:.04em; }

/* ---- budget alloc rows ---- */
.rf-alloc{ background:var(--surface); border:1px solid var(--border-soft);
  border-radius:12px; padding:.9rem 1.1rem; margin-bottom:.6rem; }
.rf-alloc-top{ display:flex; justify-content:space-between; align-items:center; }
.rf-alloc-h{ font-weight:600; color:var(--text); }
.rf-alloc-amt{ font-family:'TTHoves'!important; color:var(--accent-2); font-size:1.05rem; }
.rf-alloc-r{ font-size:.78rem; color:var(--text-3); margin-top:.15rem; }
.rf-alloc-track{ height:5px; border-radius:999px; background:var(--surface-3);
  margin-top:.6rem; overflow:hidden; }
.rf-alloc-fill{ height:100%; background:linear-gradient(90deg,var(--accent),var(--accent-2)); }

/* ---- Streamlit widget polish ---- */
.stButton > button{ border-radius:10px; font-weight:600; border:1px solid var(--border);
  background:var(--surface-2); color:var(--text); transition:all .15s; }
.stButton > button:hover{ border-color:var(--accent); color:var(--text); }
.stButton > button[kind="primary"]{ background:linear-gradient(135deg,#6366F1,#7C3AED);
  border:none; color:#fff; box-shadow:0 8px 24px -8px rgba(99,102,241,.6); }
.stButton > button[kind="primary"]:hover{ filter:brightness(1.08); }
.stTextArea textarea, .stTextInput input, .stNumberInput input{
  background:var(--surface)!important; border:1px solid var(--border)!important;
  border-radius:12px!important; color:var(--text)!important; }
.stTextArea textarea:focus{ border-color:var(--accent)!important;
  box-shadow:0 0 0 3px var(--accent-soft)!important; }
div[data-baseweb="select"] > div{ background:var(--surface)!important;
  border:1px solid var(--border)!important; border-radius:12px!important; }
[data-testid="stExpander"]{ border:1px solid var(--border-soft)!important;
  border-radius:14px!important; background:var(--surface)!important; }
[data-testid="stSidebar"]{ background:var(--surface); border-right:1px solid var(--border-soft); }
[data-testid="stMetricValue"]{ font-family:'TTHoves'!important; }
</style>
""", unsafe_allow_html=True)

init_session()

stage = st.session_state.ui["stage"]

if stage == "compose":
    render_brief_composer()
elif stage == "working":
    render_agent_working()
elif stage == "results":
    render_ranked_shortlist()
elif stage == "detail":
    render_creator_detail()
elif stage == "export":
    render_recommendation()
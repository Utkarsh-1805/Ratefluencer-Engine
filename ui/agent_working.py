import time
import streamlit as st
from utils.session import go_to
from utils.dummy_scores import load_dummy_data
from utils.ui_kit import page_header

STEPS = [
    ("Parsing brief",            "Extracting category, audience, and objective weights"),
    ("Pulling candidates",       "Retrieving creators matching brief parameters"),
    ("Running fraud check",      "Analysing follower curves, engagement ratios, comment signals"),
    ("Predicting impact",        "Scoring True-Impact and expected ROI for each candidate"),
    ("Ranking creators",         "Applying weighted composite across impact, authenticity, fit, cost"),
    ("Composing recommendation", "Generating budget split and narrative"),
]


def _step(title, sub, state):
    if state == "done":
        icon = '<span style="color:var(--good);font-weight:700">✓</span>'
        tcol, scol = "var(--text)", "var(--text-3)"
    elif state == "active":
        icon = '<span style="color:var(--accent-2);font-weight:700">◌</span>'
        tcol, scol = "var(--text)", "var(--text-2)"
    else:
        icon = '<span style="color:var(--text-3)">○</span>'
        tcol, scol = "var(--text-3)", "var(--text-3)"
    return (
        f'<div style="display:flex;gap:.8rem;align-items:flex-start;padding:.7rem .2rem;'
        f'border-bottom:1px solid var(--border-soft)"><div style="width:18px;font-size:1rem">{icon}</div>'
        f'<div><div style="color:{tcol};font-weight:600;font-size:.95rem">{title}</div>'
        f'<div style="color:{scol};font-size:.82rem;margin-top:.1rem">{sub}</div></div></div>'
    )


def render_agent_working():
    st.markdown(
        page_header("Analysing your brief",
                    "Running fraud checks and predicting business impact across all candidates.",
                    eyebrow="AI Working"),
        unsafe_allow_html=True,
    )

    container = st.empty()
    n = len(STEPS)
    for i in range(n + 1):
        rows = []
        for j, (title, sub) in enumerate(STEPS):
            state = "done" if j < i else ("active" if j == i else "pending")
            rows.append(_step(title, sub, state))
        container.markdown(
            '<div class="rf-panel">' + "".join(rows) + '</div>', unsafe_allow_html=True)
        if i < n:
            time.sleep(0.5)

    load_dummy_data()
    time.sleep(0.3)
    go_to("results")
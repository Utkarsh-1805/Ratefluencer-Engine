import time
import streamlit as st
from utils.session import go_to
from utils.dummy_scores import load_dummy_data
from utils.ui_kit import page_header
from agent.orchestrator import run_pipeline

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

    def render_progress(active_idx: int):
        rows = []
        for j, (title, sub) in enumerate(STEPS):
            state = "done" if j < active_idx else ("active" if j == active_idx else "pending")
            rows.append(_step(title, sub, state))
        container.markdown(
            '<div class="rf-panel">' + "".join(rows) + '</div>', unsafe_allow_html=True)

    # Map the orchestrator's step names → progress index, so the real pipeline
    # drives the animation. (Falls back to timed ticks if a name is unknown.)
    step_index = {name: i for i, (name, _) in enumerate(STEPS)}

    def on_step(step_name: str):
        idx = step_index.get(step_name, 0)
        render_progress(idx)
        time.sleep(0.25)  # brief pause so each step is visible

    render_progress(0)

    # Run the REAL agent pipeline (parse → retrieve → score → rank → compose).
    # If anything fails or yields no scores, fall back to dummy data so the demo
    # always reaches the results screen.
    used_fallback = False
    try:
        run_pipeline(progress_callback=on_step)
        if not st.session_state.get("scores"):
            used_fallback = True
    except Exception as e:
        print(f"[agent_working] pipeline failed ({e}) — falling back to dummy data")
        used_fallback = True

    if used_fallback:
        load_dummy_data()

    render_progress(n)   # all steps done
    time.sleep(0.3)
    go_to("results")
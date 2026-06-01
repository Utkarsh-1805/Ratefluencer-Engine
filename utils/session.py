"""
utils/session.py — Single session object for the entire app.
All screens read from and write to st.session_state.
"""
import streamlit as st

DEMO_BRIEF = (
    "DTC skincare brand targeting women aged 22–35 in India. "
    "Budget ₹3,00,000. Goal: drive online sales. "
    "Brand tone is clean, science-backed, and trustworthy. "
    "Looking for creators who can authentically promote a new SPF serum."
)

def init_session():
    defaults = {
        "brief": {
            "raw": DEMO_BRIEF,
            "category": "skincare",
            "audience": {"age_min": 22, "age_max": 35, "gender": "female", "geo": "India"},
            "budget": 300000,
            "goal": "sales",
            "tone": "clean, science-backed",
            "weights": {"impact": 0.4, "authenticity": 0.35, "match": 0.15, "cost": 0.10},
        },
        "candidates": [],       # list of influencer_ids
        "scores": {},           # { influencer_id: {impact, authenticity, match, roi, drivers} }
        "ranked": [],           # ordered influencer_ids after weighting
        "recommendation": {},   # {summary, budget_split, projected_roi}
        "selected_creator": None,
        "ui": {"stage": "compose"},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def go_to(stage: str):
    st.session_state.ui["stage"] = stage
    st.rerun()

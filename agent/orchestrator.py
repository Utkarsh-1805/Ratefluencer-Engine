"""
agent/orchestrator.py
─────────────────────
The main agent pipeline. Called by agent_working.py.

Flow:
  parse_brief() → get_candidates() → score each → rank → compose

This replaces load_dummy_data() once Person A's models are ready.
Toggle USE_REAL_MODELS = True when score_creator() is available.
"""

import streamlit as st
from agent.brief_parser import parse_brief
from agent.retriever    import get_candidates
from agent.ranker       import rank_candidates, apply_fraud_guardrail
from agent.composer     import compose_recommendation

# ── Toggle this to True when Person A's score_creator() is ready ──────────────
USE_REAL_MODELS = False


def _get_score_fn():
    """
    Returns the scoring function.
    - If USE_REAL_MODELS: import Person A's real function
    - Else: return a dummy that reads from dummy_scores.py
    """
    if USE_REAL_MODELS:
        # Person A: make sure models/score_creator.py exposes this function
        from models.score_creator import score_creator
        return score_creator
    else:
        from utils.dummy_scores import DUMMY_SCORES
        def dummy_score_creator(influencer_id: str, brief_id: str = None) -> dict:
            return dict(DUMMY_SCORES.get(influencer_id, {}))
        return dummy_score_creator


def run_pipeline(progress_callback=None) -> None:
    """
    Full agent pipeline. Writes results into st.session_state.

    Args:
        progress_callback: optional fn(step_name: str) called after each step
                           (used by agent_working.py to tick progress UI)
    """
    def tick(name):
        if progress_callback:
            progress_callback(name)

    brief_state = st.session_state.brief
    weights     = brief_state.get("weights", {"impact": 0.4, "authenticity": 0.35, "match": 0.15, "cost": 0.10})

    # ── Step 1: Parse brief ───────────────────────────────────────────────────
    tick("Parsing brief")
    parsed = parse_brief(
        brief_text=brief_state["raw"],
        budget=brief_state["budget"],
        goal_hint=brief_state["goal"],
    )
    # Merge parsed fields back into session
    brief_state["category"] = parsed.get("category", brief_state["category"])
    brief_state["goal"]     = parsed.get("goal",     brief_state["goal"])
    brief_state["tone"]     = parsed.get("tone",     "authentic")
    if "objective_weights" in parsed:
        brief_state["weights"] = parsed["objective_weights"]
        weights = parsed["objective_weights"]
    st.session_state.brief = brief_state

    # ── Step 2: Retrieve candidates ───────────────────────────────────────────
    tick("Pulling candidates")
    candidate_ids = get_candidates(parsed)
    if not candidate_ids:
        # Last resort: use dummy IDs
        from utils.dummy_scores import DUMMY_RANKED
        candidate_ids = DUMMY_RANKED
    st.session_state.candidates = candidate_ids

    # ── Step 3: Score each candidate ─────────────────────────────────────────
    tick("Running fraud check")
    score_fn = _get_score_fn()
    scores   = {}
    for iid in candidate_ids:
        try:
            s = score_fn(iid, brief_id=None)
            if s:
                scores[iid] = s
        except Exception as e:
            print(f"[orchestrator] score_creator({iid}) failed: {e}")

    tick("Predicting impact")   # scoring is done above; tick for UI pacing

    # ── Step 4: Rank ──────────────────────────────────────────────────────────
    tick("Ranking creators")
    ranked = rank_candidates(scores, weights)
    st.session_state.scores = scores
    st.session_state.ranked = ranked

    # ── Step 5: Compose recommendation ───────────────────────────────────────
    tick("Composing recommendation")
    rec = compose_recommendation(brief_state, ranked, scores)
    st.session_state.recommendation = rec

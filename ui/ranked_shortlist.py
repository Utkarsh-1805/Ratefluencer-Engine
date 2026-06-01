import streamlit as st
from utils.session import go_to
from utils.components import fmt_inr
from utils.ranking import rerank
from utils.ui_kit import (
    featured_card_html, ranked_card_html, stat_tile, page_header, section,
)


def render_weights_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="rf-sec" style="margin-top:.4rem">'
            '<div class="rf-sec-title">Objective Weights</div>'
            '<div class="rf-sec-sub">Re-rank instantly · auto-normalised</div></div>',
            unsafe_allow_html=True,
        )

        w_impact = st.slider("True-Impact",  0, 100, int(st.session_state.brief["weights"]["impact"] * 100), 5)
        w_auth   = st.slider("Authenticity", 0, 100, int(st.session_state.brief["weights"]["authenticity"] * 100), 5)
        w_match  = st.slider("Brand Match",  0, 100, int(st.session_state.brief["weights"]["match"] * 100), 5)
        w_cost   = st.slider("ROI / Cost",   0, 100, int(st.session_state.brief["weights"]["cost"] * 100), 5)

        total = max(w_impact + w_auth + w_match + w_cost, 1)
        weights = {
            "impact":       w_impact / total,
            "authenticity": w_auth / total,
            "match":        w_match / total,
            "cost":         w_cost / total,
        }

        if weights != st.session_state.brief["weights"]:
            st.session_state.brief["weights"] = weights
            st.session_state.ranked = rerank(
                st.session_state.scores, weights, st.session_state.ranked,
            )
            st.rerun()

        st.caption(f"Impact {w_impact} · Auth {w_auth} · Match {w_match} · ROI {w_cost}")

        if st.button("Reset to defaults", use_container_width=True):
            defaults = {"impact": 0.40, "authenticity": 0.35, "match": 0.15, "cost": 0.10}
            st.session_state.brief["weights"] = defaults
            st.session_state.ranked = rerank(st.session_state.scores, defaults, st.session_state.ranked)
            st.rerun()


def render_ranked_shortlist():
    render_weights_sidebar()

    rec    = st.session_state.recommendation
    scores = st.session_state.scores
    ranked = st.session_state.ranked

    recommended = sum(1 for iid in ranked if scores[iid]["status"] == "recommended")
    flagged     = sum(1 for iid in ranked if scores[iid]["status"] == "flagged")

    st.markdown(
        page_header(
            "Ranked Shortlist",
            "Creators ranked by predicted business impact — not follower count. "
            "Every score is fraud-adjusted.",
            eyebrow="AI Recommendations",
        ),
        unsafe_allow_html=True,
    )

    # ---- summary stat row ----
    st.markdown(
        '<div class="rf-stats">'
        + stat_tile("Projected Reach", f"{rec['projected_reach']:,}")
        + stat_tile("Conversions", f"{rec['projected_conversions']:,}")
        + stat_tile("Projected ROI", f"{rec['projected_roi']:.1f}x", "var(--good)")
        + stat_tile("Recommended", f"{recommended} · {flagged} flagged",
                    "var(--accent-2)")
        + '</div>',
        unsafe_allow_html=True,
    )

    # ---- featured #1 ----
    top_iid = ranked[0]
    st.markdown('<div style="height:1.7rem"></div>', unsafe_allow_html=True)
    st.markdown(featured_card_html(1, scores[top_iid]), unsafe_allow_html=True)
    st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
    if st.button("View full AI analysis  →", key=f"detail_{top_iid}",
                 type="primary", use_container_width=True):
        st.session_state.selected_creator = top_iid
        go_to("detail")

    # ---- remaining ranked creators ----
    st.markdown(section("Other creators", "Ordered by weighted composite score"),
                unsafe_allow_html=True)

    for rank_idx, iid in enumerate(ranked[1:], start=2):
        s = scores[iid]
        col_card, col_btn = st.columns([6, 1], vertical_alignment="center")
        with col_card:
            st.markdown(ranked_card_html(rank_idx, s), unsafe_allow_html=True)
        with col_btn:
            if st.button("Details", key=f"detail_{iid}", use_container_width=True):
                st.session_state.selected_creator = iid
                go_to("detail")

    # ---- footer actions ----
    st.markdown('<div style="height:1.4rem"></div>', unsafe_allow_html=True)
    col_back, col_rec = st.columns([1, 1])
    with col_back:
        if st.button("← New brief", use_container_width=True):
            go_to("compose")
    with col_rec:
        if st.button("View full recommendation  →", type="primary", use_container_width=True):
            go_to("export")
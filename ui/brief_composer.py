import streamlit as st
from utils.session import go_to
from utils.ui_kit import page_header, section
from agent.brief_parser import parse_brief, apply_parsed_brief


def _insight(key: str, value: str) -> str:
    return (
        f'<div class="rf-insight"><span class="rf-insight-k">{key}</span>'
        f'<b>{value}</b></div>'
    )


def render_brief_composer():
    st.markdown(
        page_header(
            "Find creators by impact, not hype.",
            "Describe your campaign in plain language. The AI parses your brief, "
            "screens for fraud, and ranks creators by predicted business impact.",
            eyebrow="Ratefluencer Copilot",
        ),
        unsafe_allow_html=True,
    )

    # ---- HERO: campaign brief ----
    st.markdown(section("Campaign brief"), unsafe_allow_html=True)
    brief_text = st.text_area(
        label="brief",
        label_visibility="collapsed",
        value=st.session_state.brief["raw"],
        height=170,
        placeholder="e.g. DTC skincare brand targeting women 22–35 in India, "
                    "budget ₹3,00,000, goal: drive online sales, clean science-backed tone…",
    )
    st.session_state.brief["raw"] = brief_text

    # ---- detected insights as chips ----
    parsed = None
    if brief_text.strip():
        parsed = parse_brief(brief_text, st.session_state.brief["budget"], st.session_state.brief["goal"])
        ta = parsed["target_audience"]
        st.markdown('<div style="height:.4rem"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="rf-insights">'
            + _insight("Category", parsed["category"].title())
            + _insight("Audience", f"{ta['gender'].title()} · {ta['age_min']}–{ta['age_max']}")
            + _insight("Geo", ta["geo"])
            + _insight("Goal", parsed["goal"].title())
            + _insight("Tone", parsed["tone"].title())
            + _insight("Budget", f"₹{parsed['budget']:,}")
            + '</div>',
            unsafe_allow_html=True,
        )

    # ---- advanced settings (collapsed) ----
    st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
    with st.expander("Advanced settings — override detected parameters", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            categories = ["skincare", "fitness", "finance", "fashion", "food", "tech"]
            category = st.selectbox("Category", categories,
                index=categories.index(st.session_state.brief.get("category", "skincare")))
            goals = ["sales", "awareness", "engagement", "conversions"]
            goal = st.selectbox("Goal", goals,
                index=goals.index(st.session_state.brief.get("goal", "sales")))
        with c2:
            budget = st.number_input("Budget (INR)", min_value=10_000, max_value=10_000_000,
                value=st.session_state.brief.get("budget", 300_000), step=10_000)
            gender = st.selectbox("Target gender", ["female", "male", "all"])
        with c3:
            geo = st.selectbox("Target geography", ["India", "Global", "USA", "UK", "SEA"])
            age = st.slider("Target age", 18, 65, (
                st.session_state.brief["audience"]["age_min"],
                st.session_state.brief["audience"]["age_max"]))

        st.session_state.brief["category"] = category
        st.session_state.brief["goal"]     = goal
        st.session_state.brief["budget"]   = budget
        st.session_state.brief["audience"]["gender"]  = gender
        st.session_state.brief["audience"]["geo"]     = geo
        st.session_state.brief["audience"]["age_min"] = age[0]
        st.session_state.brief["audience"]["age_max"] = age[1]

    # ---- primary CTA ----
    st.markdown('<div style="height:1.1rem"></div>', unsafe_allow_html=True)
    if st.button("✦  Generate AI Recommendations", type="primary", use_container_width=True):
        p = parse_brief(brief_text, st.session_state.brief["budget"], st.session_state.brief["goal"])
        apply_parsed_brief(p)
        go_to("working")
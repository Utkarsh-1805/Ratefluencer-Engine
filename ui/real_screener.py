"""
ui/real_screener.py — "Screen a real account" page.

Runs the REAL authenticity engine on public Instagram numbers the user types in.
The honest "it works on real data" demo: authenticity needs only follower +
engagement data (which is public), unlike ROI which has no public ground truth.
"""
import streamlit as st
from utils.session import go_to
from utils.ui_kit import page_header, section, stat_tile
from utils.components import fmt_followers


def render_real_screener():
    st.markdown(
        page_header(
            "Screen a Real Account",
            "Paste a real creator's public numbers — our fraud engine scores audience "
            "authenticity from engagement-vs-size signals alone.",
            eyebrow="Real-Data Authenticity Screen",
        ),
        unsafe_allow_html=True,
    )

    # ---- input form ----
    with st.form("screen_form"):
        c1, c2 = st.columns(2)
        with c1:
            handle    = st.text_input("Handle", "@example.creator")
            followers = st.number_input("Followers", min_value=1, value=500000, step=1000)
            following = st.number_input("Following", min_value=0, value=4000, step=100)
        with c2:
            avg_likes    = st.number_input("Avg likes (last ~10 posts)", min_value=0, value=2000, step=50)
            avg_comments = st.number_input("Avg comments (last ~10 posts)", min_value=0, value=30, step=5)
            category     = st.text_input("Category (optional)", "skincare")
        submitted = st.form_submit_button("Run authenticity screen  →", type="primary",
                                          use_container_width=True)

    if submitted:
        try:
            from models.screen_real import screen_account
            with st.spinner("Calibrating engine on the creator population + screening…"):
                r = screen_account(handle, int(followers), int(following),
                                   float(avg_likes), float(avg_comments), category)
        except Exception as e:
            st.error(f"Could not screen this account: {e}")
            return

        score = r["authenticity_score"]
        color = {"green": "var(--good)", "amber": "var(--warn)", "red": "var(--bad)"}[r["band"]]
        verdict = {"green": "Clean — audience signals look authentic",
                   "amber": "Watch — some authenticity risk",
                   "red":   "Screened out — engagement far below norm for this size"}[r["band"]]

        st.markdown('<div style="height:1rem"></div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="rf-stats">'
            + stat_tile("Authenticity", str(score), color)
            + stat_tile("Engagement rate", f'{r["engagement_rate"]:.2f}%')
            + stat_tile("Expected for size", f'{r["expected_rate"]:.2f}%')
            + stat_tile("Followers", fmt_followers(r["followers"]))
            + '</div>',
            unsafe_allow_html=True,
        )

        panel_cls = "rf-panel--bad" if r["band"] == "red" else "rf-panel"
        st.markdown(
            f'<div class="rf-panel {panel_cls}" style="margin-top:1rem">'
            f'<div style="font-weight:600;color:{color}">{verdict}</div>'
            f'<div style="margin-top:.5rem;color:var(--text-2);font-size:.9rem">'
            f'This account engages at <b>{r["engagement_rate"]:.2f}%</b>, vs <b>{r["expected_rate"]:.2f}%</b> '
            f'typical for {fmt_followers(r["followers"])} followers. '
            f'{"That gap is a known bought-follower signal." if r["band"]=="red" else "That is within a healthy range."}'
            f'</div>',
            unsafe_allow_html=True,
        )
        if r["flags"]:
            tags = "".join(
                f'<span class="rf-fraud-tag">⚠ {f.replace("_"," ").title()}</span>'
                for f in r["flags"]
            )
            st.markdown(f'<div class="rf-fraud" style="margin-top:.8rem">{tags}</div>',
                        unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.caption(
            "Uses public engagement-vs-size signals only (spike/comment-spam need "
            "private data). This is an authenticity screen, not an accusation."
        )

    st.markdown('<div style="height:1.2rem"></div>', unsafe_allow_html=True)
    if st.button("← Back to brief", use_container_width=True):
        go_to("compose")

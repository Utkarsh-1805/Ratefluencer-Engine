import streamlit as st
from utils.session import go_to
from utils.components import fmt_followers
from utils.ui_kit import (
    page_header, section, stat_tile, metric_bar, status_meta, initials, roi_color,
)


def _driver_row(d: dict) -> str:
    pos = d["effect"] == "+"
    cls = "rf-driver--pos" if pos else "rf-driver--neg"
    return (
        f'<div class="rf-driver {cls}"><span class="rf-driver-dot"></span>'
        f'<span class="rf-driver-feat">{d["feature"]}</span>'
        f'<span class="rf-driver-val">{d["value"]}</span></div>'
    )


def render_creator_detail():
    iid = st.session_state.selected_creator
    if not iid:
        go_to("results")
        return

    s = st.session_state.scores[iid]
    tone, status_label = status_meta(s["status"])
    roi = s["predicted_roi"]

    # ---- header ----
    st.markdown(
        page_header(s["handle"], "AI analysis report · fraud screening + impact prediction",
                    eyebrow="Creator Intelligence"),
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:1rem;margin:-.6rem 0 .4rem">'
        f'<div class="rf-avatar rf-avatar--lg">{initials(s.get("display_name", s["handle"]))}</div>'
        f'<div><div style="font-size:.9rem;color:var(--text-2)">'
        f'{s.get("display_name","")} · {fmt_followers(s["followers"])} followers · '
        f'{s["platform"]} · {s["content_category"]}</div>'
        f'<div style="margin-top:.4rem"><span class="rf-pill rf-pill--{tone}">{status_label}</span></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    # ---- top score tiles ----
    st.markdown('<div style="height:.8rem"></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="rf-stats">'
        + stat_tile("True-Impact", str(s["impact"]),
                    "var(--good)" if s["impact"] >= 75 else "var(--warn)" if s["impact"] >= 50 else "var(--bad)")
        + stat_tile("Authenticity", str(s["authenticity"]),
                    "var(--good)" if s["authenticity"] >= 75 else "var(--warn)" if s["authenticity"] >= 50 else "var(--bad)")
        + stat_tile("Brand Match", str(s["match"]),
                    "var(--good)" if s["match"] >= 75 else "var(--warn)" if s["match"] >= 50 else "var(--bad)")
        + stat_tile("Predicted ROI", f"{roi:.1f}x", roi_color(roi))
        + '</div>',
        unsafe_allow_html=True,
    )

    # ---- fraud screening (highly visible) ----
    auth = s.get("authenticity_detail", {})
    flags = auth.get("flags", [])
    bot_pct = auth.get("bot_follower_pct", 0)
    st.markdown(section("Fraud screening"), unsafe_allow_html=True)

    if flags:
        flag_names = {
            "bot_followers": "Bot followers", "engagement_pod": "Engagement pod",
            "spike_anomaly": "Follower spike anomaly", "comment_spam": "Comment spam",
        }
        tags = "".join(
            f'<span class="rf-fraud-tag">⚠ {flag_names.get(f, f.replace("_"," ").title())}</span>'
            for f in flags
        )
        body = f'<div class="rf-fraud">{tags}</div>'
        if s.get("flag_reason"):
            body += (f'<div style="margin-top:.9rem;color:var(--bad);font-weight:600">'
                     f'{s["flag_reason"]}</div>')
        st.markdown(f'<div class="rf-panel rf-panel--bad">{body}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="rf-panel"><span class="rf-clean">✓ No fraud flags detected — '
            'audience signals are clean</span></div>',
            unsafe_allow_html=True,
        )

    # fraud detail bars
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
        st.markdown(metric_bar("Bot follower share", round(bot_pct, 1), "%"), unsafe_allow_html=True)
        st.markdown('<div style="height:.5rem"></div>', unsafe_allow_html=True)
        st.markdown(metric_bar("Comment spam ratio", round(auth.get("comment_spam_ratio", 0) * 100)),
                    unsafe_allow_html=True)
    with c2:
        st.markdown('<div style="height:.7rem"></div>', unsafe_allow_html=True)
        st.markdown(metric_bar("Spike anomaly score", round(auth.get("spike_anomaly_score", 0) * 100)),
                    unsafe_allow_html=True)
        pod = auth.get("engagement_pod_flag", False)
        st.markdown(
            f'<div style="margin-top:.6rem"><span class="rf-pill rf-pill--{"bad" if pod else "good"}">'
            f'Engagement pod: {"Detected" if pod else "None"}</span></div>',
            unsafe_allow_html=True,
        )

    # ---- SHAP drivers: positive vs negative ----
    st.markdown(section("Score drivers", "Why the model scored this creator the way it did"),
                unsafe_allow_html=True)
    drivers = s.get("drivers", [])
    pos = [d for d in drivers if d["effect"] == "+"]
    neg = [d for d in drivers if d["effect"] == "-"]

    dc1, dc2 = st.columns(2)
    with dc1:
        st.markdown('<div style="font-size:.85rem;color:var(--good);font-weight:600;'
                    'margin-bottom:.6rem">▲ Positive drivers</div>', unsafe_allow_html=True)
        st.markdown("".join(_driver_row(d) for d in pos) or
                    '<div style="color:var(--text-3);font-size:.85rem">None</div>',
                    unsafe_allow_html=True)
    with dc2:
        st.markdown('<div style="font-size:.85rem;color:var(--bad);font-weight:600;'
                    'margin-bottom:.6rem">▼ Negative drivers</div>', unsafe_allow_html=True)
        st.markdown("".join(_driver_row(d) for d in neg) or
                    '<div style="color:var(--text-3);font-size:.85rem">None</div>',
                    unsafe_allow_html=True)

    # ---- audience fit ----
    st.markdown(section("Audience fit vs. target"), unsafe_allow_html=True)
    fit = s.get("audience_fit", {})
    f1, f2, f3 = st.columns(3)
    f1.markdown(metric_bar("Age match", fit.get("age_match", 0), "%"), unsafe_allow_html=True)
    f2.markdown(metric_bar("Gender match", fit.get("gender_match", 0), "%"), unsafe_allow_html=True)
    f3.markdown(metric_bar("Geo match", fit.get("geo_match", 0), "%"), unsafe_allow_html=True)

    # ---- actions ----
    st.markdown('<div style="height:1.4rem"></div>', unsafe_allow_html=True)
    col_back, col_toggle, col_rec = st.columns(3)
    with col_back:
        if st.button("← Back to shortlist", use_container_width=True):
            go_to("results")
    with col_toggle:
        if s["status"] == "excluded":
            if st.button("Include in recommendation", use_container_width=True):
                st.session_state.scores[iid]["status"] = "recommended"
                go_to("results")
        else:
            if st.button("Exclude from recommendation", use_container_width=True):
                st.session_state.scores[iid]["status"] = "excluded"
                go_to("results")
    with col_rec:
        if st.button("View recommendation  →", type="primary", use_container_width=True):
            go_to("export")
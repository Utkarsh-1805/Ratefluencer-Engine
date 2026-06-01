import streamlit as st
from utils.session import go_to
from utils.components import fmt_inr
from utils.ui_kit import page_header, section, stat_tile, initials


def _build_recommendation(rec: dict, brief: dict, scores: dict, ranked: list) -> dict:
    recommended = [iid for iid in ranked if scores[iid]["status"] == "recommended"]
    flagged     = [iid for iid in ranked if scores[iid]["status"] == "flagged"]

    top_handles  = [scores[iid]["handle"] for iid in recommended[:3]]
    flag_handles = [scores[iid]["handle"] for iid in flagged]

    audience = brief["audience"]
    category = brief["category"].title()
    geo, gender = audience["geo"], audience["gender"]
    age, goal = f"{audience['age_min']}–{audience['age_max']}", brief["goal"]

    flag_str = (
        f" We have excluded {', '.join(flag_handles)} due to inauthentic audience "
        f"signals and projected negative ROI." if flag_handles else ""
    )
    summary = (
        f"For your {category} campaign targeting {gender} audiences aged {age} in {geo}, "
        f"we recommend a {len(recommended)}-creator stack anchored by "
        f"{top_handles[0] if top_handles else 'top creators'}. These creators deliver higher "
        f"fraud-adjusted reach and stronger audience alignment relative to their follower "
        f"counts, with a projected positive ROI on a {goal} goal.{flag_str}"
    )

    total_budget, n = brief["budget"], len(recommended)
    if n == 0:
        budget_split = []
    else:
        ratios = [scores[iid]["impact"] + scores[iid]["authenticity"] for iid in recommended]
        total_ratio = sum(ratios) or 1
        budget_split = [
            {
                "handle":    scores[iid]["handle"],
                "allocated": round(total_budget * (ratios[i] / total_ratio) / 1000) * 1000,
                "rationale": f"Impact {scores[iid]['impact']} · Authenticity {scores[iid]['authenticity']}",
                "impact":    scores[iid]["impact"],
            }
            for i, iid in enumerate(recommended)
        ]

    return {
        "summary": summary,
        "projected_reach": rec.get("projected_reach", 0),
        "projected_conversions": rec.get("projected_conversions", 0),
        "projected_roi": rec.get("projected_roi", 0.0),
        "budget_split": budget_split,
        "flag_handles": flag_handles,
    }


def render_recommendation():
    brief  = st.session_state.brief
    scores = st.session_state.scores
    ranked = st.session_state.ranked
    rec    = _build_recommendation(st.session_state.recommendation, brief, scores, ranked)

    st.markdown(
        page_header(
            "Campaign Recommendation",
            f"{brief['category'].title()} · {brief['audience']['geo']} · {brief['goal'].title()} goal",
            eyebrow="Executive Summary",
        ),
        unsafe_allow_html=True,
    )

    # ---- ROI hero + outcomes ----
    st.markdown(
        f'<div class="rf-panel rf-panel--accent"><div class="rf-roi-hero">'
        f'<div><div class="rf-roi-hero-v">{rec["projected_roi"]:.1f}x</div>'
        f'<div class="rf-roi-hero-l">Projected Return on Investment</div></div>'
        f'<div style="flex:1"></div>'
        f'<div class="rf-stats" style="grid-template-columns:repeat(3,1fr);min-width:480px">'
        + stat_tile("Total Budget", fmt_inr(brief["budget"]))
        + stat_tile("Projected Reach", f"{rec['projected_reach']:,}")
        + stat_tile("Conversions", f"{rec['projected_conversions']:,}")
        + '</div></div></div>',
        unsafe_allow_html=True,
    )

    # ---- AI rationale ----
    st.markdown(section("AI rationale"), unsafe_allow_html=True)
    st.markdown(
        f'<div class="rf-panel" style="font-size:.96rem;line-height:1.6;color:var(--text)">'
        f'{rec["summary"]}</div>',
        unsafe_allow_html=True,
    )

    # ---- recommended creators + budget allocation ----
    st.markdown(section("Recommended creators & budget allocation"), unsafe_allow_html=True)
    for item in rec["budget_split"]:
        pct = item["allocated"] / max(brief["budget"], 1) * 100
        st.markdown(
            f'<div class="rf-alloc"><div class="rf-alloc-top">'
            f'<div style="display:flex;align-items:center;gap:.7rem">'
            f'<div class="rf-avatar" style="width:34px;height:34px;font-size:.8rem;border-radius:10px">'
            f'{initials(item["handle"])}</div>'
            f'<div><div class="rf-alloc-h">{item["handle"]}</div>'
            f'<div class="rf-alloc-r">{item["rationale"]}</div></div></div>'
            f'<div class="rf-alloc-amt">{fmt_inr(item["allocated"])}</div></div>'
            f'<div class="rf-alloc-track"><div class="rf-alloc-fill" style="width:{pct}%"></div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if rec["flag_handles"]:
        st.markdown(
            f'<div class="rf-panel rf-panel--bad" style="margin-top:.4rem">'
            f'<span class="rf-fraud-tag">⚠ Excluded</span> &nbsp;'
            f'<span style="color:var(--text);font-size:.9rem">'
            f'{", ".join(rec["flag_handles"])} — inauthentic audience · projected negative ROI</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ---- export ----
    st.markdown(section("Export"), unsafe_allow_html=True)
    export_lines = [
        "RATEFLUENCER COPILOT — CAMPAIGN RECOMMENDATION",
        "=" * 50,
        f"Brief: {brief['raw']}",
        "",
        "PROJECTED OUTCOMES",
        f"  Reach:       {rec['projected_reach']:,}",
        f"  Conversions: {rec['projected_conversions']:,}",
        f"  ROI:         {rec['projected_roi']:.1f}x",
        "",
        "BUDGET ALLOCATION",
    ] + [
        f"  {item['handle']}: {fmt_inr(item['allocated'])} — {item['rationale']}"
        for item in rec["budget_split"]
    ] + ["", "SUMMARY", rec["summary"], "",
         "Generated by Ratefluencer Copilot · Ratefluencer AI Hackathon 2026"]
    export_text = "\n".join(export_lines)

    col_dl, col_back = st.columns([1, 1])
    with col_dl:
        st.download_button("⤓  Download recommendation", data=export_text,
            file_name="ratefluencer_recommendation.txt", mime="text/plain",
            use_container_width=True, type="primary")
    with col_back:
        if st.button("← Back to shortlist", use_container_width=True):
            go_to("results")

    with st.expander("Copy as text"):
        st.text_area("export", export_text, height=180, label_visibility="collapsed")
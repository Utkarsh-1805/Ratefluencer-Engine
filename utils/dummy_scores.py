"""
utils/dummy_scores.py
Hardcoded demo scores so Person B can build + test the UI
without waiting for Person A's models.

Replace score_creator() calls with Person A's real function at hour 20.
The influencer_id keys here must match what Person A seeds in SQLite.
"""

DUMMY_CREATORS = [
    {
        "influencer_id": "inf_001",
        "handle": "@minimal.skin",
        "display_name": "Minimal Skin",
        "platform": "instagram",
        "followers": 14000,
        "content_category": "skincare",
        "region": "India",
        "verified": False,
    },
    {
        "influencer_id": "inf_002",
        "handle": "@glow.daily",
        "display_name": "Glow Daily",
        "platform": "instagram",
        "followers": 88000,
        "content_category": "skincare",
        "region": "India",
        "verified": False,
    },
    {
        "influencer_id": "inf_003",
        "handle": "@skin.science.india",
        "display_name": "Skin Science India",
        "platform": "instagram",
        "followers": 45000,
        "content_category": "skincare",
        "region": "India",
        "verified": False,
    },
    {
        "influencer_id": "inf_004",
        "handle": "@beautywithpriya",
        "display_name": "Beauty with Priya",
        "platform": "instagram",
        "followers": 210000,
        "content_category": "skincare",
        "region": "India",
        "verified": True,
    },
    {
        "influencer_id": "inf_005",  # THE FRAUD ACCOUNT — the reveal
        "handle": "@famous.face",
        "display_name": "Famous Face",
        "platform": "instagram",
        "followers": 512000,
        "content_category": "skincare",
        "region": "India",
        "verified": True,
    },
]

DUMMY_SCORES = {
    "inf_001": {
        "impact": 91, "authenticity": 96, "match": 93,
        "predicted_roi": 3.4, "success_prob": 0.82,
        "composite": 93,
        "status": "recommended",
        "flag_reason": None,
        "drivers": [
            {"feature": "Real engagement rate", "effect": "+", "value": "7.2%"},
            {"feature": "Brand fit (skincare + SPF)", "effect": "+", "value": "0.91 similarity"},
            {"feature": "Audience age 22–35 match", "effect": "+", "value": "81% overlap"},
            {"feature": "Fraud-adjusted reach", "effect": "-", "value": "13.4K (low volume)"},
        ],
        "authenticity_detail": {
            "bot_follower_pct": 3.1,
            "engagement_pod_flag": False,
            "spike_anomaly_score": 0.08,
            "comment_spam_ratio": 0.04,
            "flags": [],
        },
        "audience_fit": {
            "age_match": 81, "gender_match": 88, "geo_match": 94,
        },
    },
    "inf_002": {
        "impact": 84, "authenticity": 90, "match": 78,
        "predicted_roi": 2.8, "success_prob": 0.74,
        "composite": 84,
        "status": "recommended",
        "flag_reason": None,
        "drivers": [
            {"feature": "Consistent posting schedule", "effect": "+", "value": "4.2 posts/week"},
            {"feature": "High save rate", "effect": "+", "value": "3.8%"},
            {"feature": "Brand fit similarity", "effect": "+", "value": "0.78"},
            {"feature": "Slight audience age skew", "effect": "-", "value": "28% under 22"},
        ],
        "authenticity_detail": {
            "bot_follower_pct": 7.2,
            "engagement_pod_flag": False,
            "spike_anomaly_score": 0.14,
            "comment_spam_ratio": 0.07,
            "flags": [],
        },
        "audience_fit": {"age_match": 72, "gender_match": 85, "geo_match": 91},
    },
    "inf_003": {
        "impact": 76, "authenticity": 88, "match": 85,
        "predicted_roi": 2.1, "success_prob": 0.68,
        "composite": 79,
        "status": "recommended",
        "flag_reason": None,
        "drivers": [
            {"feature": "Strong skincare niche alignment", "effect": "+", "value": "0.85"},
            {"feature": "Good comment quality", "effect": "+", "value": "avg 18 words"},
            {"feature": "Lower share rate", "effect": "-", "value": "1.1%"},
        ],
        "authenticity_detail": {
            "bot_follower_pct": 9.4,
            "engagement_pod_flag": False,
            "spike_anomaly_score": 0.11,
            "comment_spam_ratio": 0.09,
            "flags": [],
        },
        "audience_fit": {"age_match": 77, "gender_match": 82, "geo_match": 88},
    },
    "inf_004": {
        "impact": 61, "authenticity": 72, "match": 70,
        "predicted_roi": 1.4, "success_prob": 0.52,
        "composite": 65,
        "status": "recommended",
        "flag_reason": None,
        "drivers": [
            {"feature": "Large real reach", "effect": "+", "value": "151K adjusted"},
            {"feature": "Moderate engagement rate", "effect": "-", "value": "1.8%"},
            {"feature": "Some bot signals", "effect": "-", "value": "19% inauthentic"},
        ],
        "authenticity_detail": {
            "bot_follower_pct": 19.3,
            "engagement_pod_flag": False,
            "spike_anomaly_score": 0.28,
            "comment_spam_ratio": 0.16,
            "flags": ["bot_followers"],
        },
        "audience_fit": {"age_match": 65, "gender_match": 78, "geo_match": 82},
    },
    "inf_005": {  # THE FRAUD ACCOUNT
        "impact": 29, "authenticity": 41, "match": 70,
        "predicted_roi": -0.3, "success_prob": 0.18,
        "composite": 38,
        "status": "flagged",
        "flag_reason": "38% inauthentic audience → projected negative ROI",
        "drivers": [
            {"feature": "Bot follower share", "effect": "-", "value": "38% fake"},
            {"feature": "Engagement pod detected", "effect": "-", "value": "coordinated likes"},
            {"feature": "Follower spike anomaly", "effect": "-", "value": "z-score 3.8"},
            {"feature": "Raw follower count", "effect": "+", "value": "512K (misleading)"},
        ],
        "authenticity_detail": {
            "bot_follower_pct": 38.1,
            "engagement_pod_flag": True,
            "spike_anomaly_score": 0.91,
            "comment_spam_ratio": 0.44,
            "flags": ["bot_followers", "engagement_pod", "spike_anomaly", "comment_spam"],
        },
        "audience_fit": {"age_match": 58, "gender_match": 71, "geo_match": 76},
    },
}

# Pre-ranked order (composite score descending, flagged suppressed to bottom)
DUMMY_RANKED = ["inf_001", "inf_002", "inf_003", "inf_004", "inf_005"]

DUMMY_RECOMMENDATION = {
    "summary": (
        "For your DTC skincare SPF serum targeting women 22–35 in India, "
        "we recommend a 3-creator micro-influencer stack anchored by @minimal.skin. "
        "Despite lower follower counts, these creators deliver higher fraud-adjusted reach, "
        "stronger audience alignment, and projected positive ROI. "
        "We have excluded @famous.face due to 38% inauthentic followers and projected negative ROI."
    ),
    "projected_reach": 120000,
    "projected_conversions": 1440,
    "projected_roi": 2.9,
    "budget_split": [
        {"handle": "@minimal.skin",      "allocated": 120000, "rationale": "Highest impact + authenticity"},
        {"handle": "@glow.daily",        "allocated": 100000, "rationale": "Strong reach + engagement"},
        {"handle": "@skin.science.india","allocated": 80000,  "rationale": "Niche skincare alignment"},
    ],
}


def load_dummy_data():
    """Populate session state with dummy data. Call this from agent_working."""
    import streamlit as st
    st.session_state.candidates = [c["influencer_id"] for c in DUMMY_CREATORS]
    st.session_state.scores = {
        iid: {**DUMMY_SCORES[iid], **next(c for c in DUMMY_CREATORS if c["influencer_id"] == iid)}
        for iid in DUMMY_SCORES
    }
    st.session_state.ranked = DUMMY_RANKED
    st.session_state.recommendation = DUMMY_RECOMMENDATION

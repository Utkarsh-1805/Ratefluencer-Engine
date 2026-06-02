"""
agent/composer.py
─────────────────
Composes the final campaign recommendation narrative using Claude.
Falls back to a template if the API is unavailable.
"""

import os
import re
# NOTE: `anthropic` is imported lazily inside compose_recommendation() so the app
# runs fully offline (template fallback) when the package/key isn't present.


def _template_fallback(brief: dict, ranked: list, scores: dict) -> dict:
    """Rule-based recommendation — always works offline."""
    recommended = [iid for iid in ranked if scores[iid].get("status") == "recommended"][:3]
    flagged     = [iid for iid in ranked if scores[iid].get("status") == "flagged"]

    rec_handles  = ", ".join(scores[iid]["handle"] for iid in recommended)
    flag_handles = ", ".join(scores[iid]["handle"] for iid in flagged)

    budget = brief.get("budget", 300000)
    category = brief.get("category", "your category")
    goal = brief.get("goal", "your goal")

    # Budget split: roughly 40 / 33 / 27 across top 3
    splits = [0.40, 0.33, 0.27]
    budget_split = [
        {
            "handle": scores[iid]["handle"],
            "allocated": int(budget * pct),
            "rationale": _one_line_rationale(scores[iid]),
        }
        for iid, pct in zip(recommended, splits)
    ]

    # Projected outcomes
    total_auth_reach = sum(
        scores[iid]["followers"] * (1 - scores[iid].get("authenticity_detail", {}).get("bot_follower_pct", 0) / 100)
        for iid in recommended
    )
    projected_reach       = int(total_auth_reach)
    projected_conversions = int(projected_reach * 0.012)  # 1.2% conversion assumption
    avg_roi               = sum(scores[iid]["predicted_roi"] for iid in recommended) / max(len(recommended), 1)

    flag_note = (
        f" We have excluded {flag_handles} due to inauthentic audience signals and projected negative ROI."
        if flagged else ""
    )

    summary = (
        f"For your {category} campaign targeting {brief.get('audience', {}).get('geo', 'India')} "
        f"with a {goal} goal, we recommend a {len(recommended)}-creator stack: {rec_handles}. "
        f"These creators deliver fraud-adjusted reach, strong audience alignment, and positive projected ROI."
        f"{flag_note}"
    )

    return {
        "summary":               summary,
        "projected_reach":       projected_reach,
        "projected_conversions": projected_conversions,
        "projected_roi":         round(avg_roi, 1),
        "budget_split":          budget_split,
    }


def _one_line_rationale(score: dict) -> str:
    drivers = score.get("drivers", [])
    if drivers:
        top = drivers[0]
        return f"{top['feature']} ({top['value']})"
    return f"Impact {score['impact']} · Authenticity {score['authenticity']}"


def _build_prompt(brief: dict, ranked: list, scores: dict) -> str:
    """Tight LLM context shared by all providers."""
    creator_lines = "\n".join(
        f"- {scores[iid]['handle']} ({scores[iid]['followers']:,} followers): "
        f"Impact {scores[iid]['impact']}, Authenticity {scores[iid]['authenticity']}, "
        f"ROI {scores[iid]['predicted_roi']:.1f}×, Status: {scores[iid]['status']}"
        for iid in ranked[:6]
    )
    return f"""Write a 3-sentence campaign recommendation for a brand marketer.

Brief: {brief.get('raw', brief.get('category', ''))}
Goal: {brief.get('goal')} | Budget: ₹{brief.get('budget', 0):,}
Target: {brief.get('target_audience', brief.get('audience', {}))}

Creator scores:
{creator_lines}

Rules:
- Be specific: name the recommended handles and why
- Call out flagged creators by name with the fraud reason
- End with projected impact
- Plain English, confident, no jargon
- 3 sentences max"""


def _gemini_summary(prompt: str, api_key: str) -> str | None:
    """Generate the summary with Gemini. Returns None on any failure."""
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        # gemini-2.5-flash is the model with free-tier quota (2.0-flash is 0/0).
        resp = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt,
        )
        return (resp.text or "").strip() or None
    except Exception as e:
        print(f"[composer] Gemini failed ({e})")
        return None


def _claude_summary(prompt: str, api_key: str) -> str | None:
    """Generate the summary with Claude. Returns None on any failure."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-20250514", max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip() or None
    except Exception as e:
        print(f"[composer] Claude failed ({e})")
        return None


def compose_recommendation(brief: dict, ranked: list, scores: dict) -> dict:
    """
    Compose the final recommendation narrative with an LLM, falling back cleanly.

    Provider order: Gemini (GEMINI_API_KEY) → Claude (ANTHROPIC_API_KEY) →
    deterministic offline template. The structured numeric fields always come
    from the template; the LLM only rewrites the `summary` prose.

    Keys are read from environment variables ONLY — never hard-coded.
    """
    # Structured fields (reach/conversions/roi/budget) always from the template.
    template = _template_fallback(brief, ranked, scores)

    gemini_key = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("GOOGLE_API_KEY", "")
    claude_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not gemini_key and not claude_key:
        print("[composer] No LLM key — using template fallback")
        return template

    prompt = _build_prompt(brief, ranked, scores)

    if gemini_key:
        summary = _gemini_summary(prompt, gemini_key)
        if summary:
            template["summary"] = summary
            template["composed_by"] = "gemini"
            return template

    if claude_key:
        summary = _claude_summary(prompt, claude_key)
        if summary:
            template["summary"] = summary
            template["composed_by"] = "claude"
            return template

    print("[composer] all LLM providers failed — using template")
    return template


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    from utils.dummy_scores import DUMMY_SCORES, DUMMY_RANKED
    from utils.session import init_session

    brief = {
        "raw": "DTC skincare brand targeting women 22–35 in India. Budget ₹3L. Goal: sales.",
        "category": "skincare",
        "audience": {"geo": "India", "age_min": 22, "age_max": 35, "gender": "female"},
        "budget": 300000,
        "goal": "sales",
    }

    scores = {k: dict(v) for k, v in DUMMY_SCORES.items()}
    result = compose_recommendation(brief, DUMMY_RANKED, scores)
    print(json.dumps(result, indent=2))

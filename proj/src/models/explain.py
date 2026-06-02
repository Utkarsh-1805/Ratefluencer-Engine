"""Explainability (task-010) — SHAP drivers + plain-English rationale.

Turns a True-Impact prediction into:
  * ``drivers`` — top positive/negative feature attributions (SHAP TreeExplainer
    on the LightGBM regressor), mapped to friendly labels,
  * ``rationale`` — one factual sentence assembled from the drivers + authenticity
    flags. An LLM phrases it when a key is configured (cached); otherwise a
    deterministic **template** assembles it. The rationale never invents a number.

Rules honored:
  * >= 3 named drivers per shortlisted creator.
  * Friendly labels in the UI, not raw column names.
  * Deterministic SHAP for seeded creators (precompute for the demo set).
  * Tie/near-zero SHAP -> fall back to largest-magnitude features.
  * Negative driver (e.g. fraud) is always surfaced, never hidden.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

import config
from src.data.features import compute_creator_features, compute_fit_features
from src.models.true_impact import TrueImpactModel
from src.store import repo
from src.store.schema import BrandBrief

# Raw feature name -> friendly label shown to humans.
FRIENDLY = {
    "engagement_rate": "engagement rate",
    "fraud_adjusted_reach": "fraud-adjusted reach",
    "real_engagement_rate": "real engagement",
    "save_rate": "save rate",
    "share_rate": "share rate",
    "comment_rate": "comment rate",
    "comment_quality": "comment quality",
    "audience_quality": "audience quality",
    "posting_consistency": "posting consistency",
    "growth_rate_30d": "30-day growth",
    "growth_rate_90d": "90-day growth",
    "follower_following_ratio": "follower/following ratio",
    "like_comment_ratio": "like/comment ratio",
    "spike_anomaly_score": "follower-spike anomaly",
    "comment_spam_ratio": "comment-spam ratio",
    "audience_demo_match": "audience-demographic match",
    "brand_fit_similarity": "brand fit",
}

FLAG_PHRASES = {
    "bot_followers": "inauthentic (bot) followers",
    "engagement_pod": "coordinated engagement (pod)",
    "spike_anomaly": "suspicious follower spikes",
    "comment_spam": "spammy comments",
}


class Explainer:
    """Wraps a SHAP TreeExplainer over the True-Impact regressor."""

    def __init__(self, model: TrueImpactModel):
        import shap

        self.model = model
        self.columns = list(model.columns)
        self._explainer = shap.TreeExplainer(model.regressor)

    def shap_values(self, X: np.ndarray) -> np.ndarray:
        vals = self._explainer.shap_values(X)
        return np.asarray(vals)  # (n, n_features) for LightGBM regression

    def drivers_for(self, vec: dict, top_n: int = 3) -> list[dict]:
        """Return top +/- drivers for one feature dict (>= max(top_n,3) total)."""
        X = np.array([[vec.get(c, 0.0) for c in self.columns]], dtype=float)
        shap_row = self.shap_values(X)[0]

        contribs = [
            {
                "feature": col,
                "label": FRIENDLY.get(col, col),
                "effect": "+" if s >= 0 else "-",
                "value": round(float(vec.get(col, 0.0)), 4),
                "shap": round(float(s), 4),
            }
            for col, s in zip(self.columns, shap_row)
        ]
        # Largest magnitude first (handles ties / near-zero gracefully).
        contribs.sort(key=lambda d: (-abs(d["shap"]), d["feature"]))

        pos = [c for c in contribs if c["effect"] == "+"]
        neg = [c for c in contribs if c["effect"] == "-"]

        # Always surface the strongest negative driver alongside the top positives.
        selected = pos[: max(top_n - 1, 2)]
        if neg:
            selected.append(neg[0])
        for c in contribs:  # top up by magnitude if still short
            if len(selected) >= max(top_n, 3):
                break
            if c not in selected:
                selected.append(c)
        return selected[: max(top_n, 3)]


# --------------------------------------------------------------------------- #
# Rationale
# --------------------------------------------------------------------------- #
def template_rationale(drivers: list[dict], flags: list[str], score: int) -> str:
    """Deterministic one-sentence rationale from drivers + flags (no LLM, no invented numbers)."""
    pos = [d for d in drivers if d["effect"] == "+"][:2]
    neg = [d for d in drivers if d["effect"] == "-"][:1]

    if flags:
        flag_txt = " and ".join(FLAG_PHRASES.get(f, f) for f in flags[:2])
        lead = f"Flagged for {flag_txt}"
        if neg:
            lead += f", which drags down {neg[0]['label']}"
        return lead + "."

    parts = []
    if pos:
        parts.append("strong " + " and ".join(p["label"] for p in pos))
    if neg:
        parts.append("held back by " + neg[0]["label"])
    body = "; ".join(parts) if parts else "balanced signals across drivers"
    verdict = ("High-impact pick" if score >= config.GREEN_THRESHOLD
               else ("Solid option" if score >= config.FLAG_THRESHOLD else "Weak fit"))
    return f"{verdict}: {body}."


def llm_rationale(drivers: list[dict], flags: list[str], score: int) -> Optional[str]:
    """Phrase the rationale via an LLM if a key is configured; else None.

    Any failure (no key, network, bad response) returns None so the caller falls
    back to the deterministic template. The LLM only PHRASES the given
    drivers/flags — it is told not to introduce new facts or numbers.
    """
    import os

    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        return None
    try:  # pragma: no cover - exercised only when a key is present
        facts = {
            "score": score,
            "positive": [d["label"] for d in drivers if d["effect"] == "+"][:3],
            "negative": [d["label"] for d in drivers if d["effect"] == "-"][:2],
            "flags": [FLAG_PHRASES.get(f, f) for f in flags],
        }
        prompt = (
            "Write ONE factual sentence (max 22 words) explaining an influencer's "
            "True-Impact score using ONLY these facts. Do not invent numbers.\n"
            f"{facts}"
        )
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic

            client = anthropic.Anthropic()
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=80,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        from openai import OpenAI

        client = OpenAI()
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}],
        )
        return r.choices[0].message.content.strip()
    except Exception:
        return None


def explain(
    influencer_id: str,
    brief: BrandBrief,
    model: Optional[TrueImpactModel] = None,
    explainer: Optional[Explainer] = None,
    score: Optional[int] = None,
    use_llm: bool = True,
) -> dict:
    """Full explanation for one creator x brief: drivers + rationale."""
    model = model or TrueImpactModel.load()
    explainer = explainer or Explainer(model)

    vec = compute_creator_features(influencer_id)
    vec.update(compute_fit_features(influencer_id, brief))
    drivers = explainer.drivers_for(vec, top_n=3)

    auth = repo.get_authenticity(influencer_id)
    flags = auth.flags if auth else []

    if score is None:
        from src.models.true_impact import predict_true_impact

        score = predict_true_impact(influencer_id, brief, model)["true_impact_score"]

    rationale = (llm_rationale(drivers, flags, score) if use_llm else None) \
        or template_rationale(drivers, flags, score)

    return {"drivers": drivers, "rationale": rationale}

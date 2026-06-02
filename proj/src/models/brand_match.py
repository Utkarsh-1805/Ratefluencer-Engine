"""Brand Match score (task-011) — the third score, alongside Authenticity and True-Impact.

True-Impact answers "will this creator drive ROI?"; Brand Match answers "is this
creator *on-brand* for *this* brief?" — semantic fit + audience fit + category fit,
blended to a 0-100 score with sub-scores and rationale tags for the UI.

Reuses the shared building blocks (no new index, no new model):
  * ``src.data.embeddings`` — the MiniLM helper (offline deterministic fallback),
  * ``src.store.vector.VectorStore`` — the FAISS index (for top-k retrieval),
  * ``src.data.features.compute_fit_features`` — already computes the cosine
    similarity (``brand_fit_similarity``) and audience overlap (``audience_demo_match``)
    used by the True-Impact model, so Brand Match stays consistent with it.

Output (per creator x brief)::

    { brand_match_score: 0-100, semantic_similarity: 0-1, audience_alignment: 0-1,
      category_match: 0-1, rationale_tags: [...], confidence: high|low }

Stored in ``scores.brand_match_score``. Deterministic for seeded creators.

Edge cases honored (spec):
  * empty/short brief -> fall back to category + audience, flag low confidence,
  * missing creator embedding -> computed on the fly by ``compute_fit_features``,
  * banned terms / off-brand -> hard penalty + an explicit tag.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

import config
from src.data import embeddings as emb
from src.data.features import compute_fit_features, _brief_text
from src.store import repo
from src.store.schema import BrandBrief

MODEL_VERSION = "brandmatch-v1"

# Blend weights (semantic + audience + category). Category/audience are reliable
# even with the offline embedding fallback, so the on-brand > off-brand ordering
# holds whether or not sentence-transformers is installed; semantic adds lift
# when the real MiniLM model is present.
SEM_W, AUD_W, CAT_W = 0.40, 0.35, 0.25

# Partial credit when the creator's category is adjacent to the brief's.
RELATED_CATEGORIES: dict[str, dict[str, float]] = {
    "skincare": {"beauty": 0.85, "fashion": 0.45, "fitness": 0.30},
    "beauty":   {"skincare": 0.85, "fashion": 0.55},
    "fashion":  {"beauty": 0.55, "skincare": 0.45},
    "fitness":  {"food": 0.40, "skincare": 0.30, "travel": 0.25},
    "food":     {"fitness": 0.40, "travel": 0.35},
    "tech":     {"finance": 0.45},
    "finance":  {"tech": 0.45},
    "travel":   {"food": 0.35, "fashion": 0.30},
}


def _category_match(creator_category: Optional[str], brief_category: Optional[str]) -> float:
    """1.0 exact, partial for adjacent categories, 0.5 neutral if the brief is unspecified."""
    if not brief_category:
        return 0.5
    if not creator_category:
        return 0.0
    if creator_category == brief_category:
        return 1.0
    return float(RELATED_CATEGORIES.get(brief_category, {}).get(creator_category, 0.0))


def _banned_hit(inf, posts, brief: BrandBrief) -> bool:
    """True if any banned term appears in the creator's bio/category/captions."""
    if not brief.banned_terms:
        return False
    hay = " ".join(
        [inf.bio or "", inf.content_category or ""] + [(p.caption or "") for p in posts]
    ).lower()
    return any(bt.lower() in hay for bt in brief.banned_terms if bt)


def _rationale_tags(inf, audience, brief: BrandBrief) -> list[str]:
    """Deterministic, human-readable themes explaining the fit (<=5)."""
    tags: list[str] = []
    if inf.content_category:
        tags.append(inf.content_category)
    # interests shared between the brief target and the creator's audience
    if brief.target_interests and audience and audience.top_interests:
        tags.extend(i for i in brief.target_interests if i in audience.top_interests)
    # audience age descriptor
    if audience and audience.age_distribution:
        young = (audience.age_distribution.get("13-17", 0.0) or 0.0) + (
            audience.age_distribution.get("18-24", 0.0) or 0.0
        )
        if young >= 0.45:
            tags.append("Gen-Z audience")
        elif (audience.age_distribution.get("25-34", 0.0) or 0.0) >= 0.40:
            tags.append("millennial audience")
    # gender skew
    if audience and audience.gender_split:
        if (audience.gender_split.get("female", 0.0) or 0.0) >= 0.65:
            tags.append("women-led audience")
        elif (audience.gender_split.get("male", 0.0) or 0.0) >= 0.65:
            tags.append("men-led audience")
    if brief.tone:
        tags.append(brief.tone)
    # de-dup, preserve order, cap at 5
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out[:5]


def _brief_is_thin(brief: BrandBrief) -> bool:
    """Too little signal to match confidently -> fall back to category/audience."""
    signal = sum(
        bool(x)
        for x in (
            brief.category,
            brief.target_interests,
            brief.target_gender,
            brief.target_geo,
            (brief.raw_text or "").strip() if (brief.raw_text and len(brief.raw_text) >= 12) else "",
        )
    )
    return signal <= 1


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def brand_match(influencer_id: str, brief: BrandBrief) -> dict:
    """Score how well one creator fits one brief. Returns score + sub-scores + tags."""
    inf = repo.get_influencer(influencer_id)
    if inf is None:
        raise ValueError(f"unknown influencer {influencer_id}")
    audience = repo.get_audience_profile(influencer_id)

    fit = compute_fit_features(influencer_id, brief)  # cosine + audience overlap, on the fly
    semantic_similarity = float(fit["brand_fit_similarity"])   # [0,1]
    audience_alignment = float(fit["audience_demo_match"])      # [0,1]
    category_match = _category_match(inf.content_category, brief.category)

    raw = SEM_W * semantic_similarity + AUD_W * audience_alignment + CAT_W * category_match
    score = 100.0 * raw

    tags = _rationale_tags(inf, audience, brief)

    # banned terms -> hard penalty + explicit tag (off-brand).
    if _banned_hit(inf, repo.get_posts(influencer_id), brief):
        score *= 0.25
        tags = ["⚠ off-brand (banned term)"] + tags

    low_conf = _brief_is_thin(brief)
    return {
        "brand_match_score": int(np.clip(round(score), 0, 100)),
        "semantic_similarity": round(semantic_similarity, 4),
        "audience_alignment": round(audience_alignment, 4),
        "category_match": round(category_match, 4),
        "rationale_tags": tags,
        "confidence": "low" if low_conf else "high",
    }


def get_candidates(
    brief: BrandBrief,
    k: int = 20,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Retrieval API for the agent (task-011 contract `get_candidates`).

    Returns the top-k most semantically similar creators to the brief from the
    shared FAISS vector store (built in feature-engineering), each as a
    ``{influencer_id, score, metadata}`` dict. ``filters`` accepts category /
    region / min_followers / max_followers. The agent then scores survivors in
    full via ``brand_match`` + ``predict_true_impact``. Empty store -> ``[]``.
    """
    from src.store.vector import VectorStore

    vs = VectorStore()           # auto-loads any persisted index on construction
    if len(vs) == 0:
        return []
    brief_vec = emb.embed_text(_brief_text(brief))
    return vs.query(brief_vec, top_k=k, filters=filters)


def top_matches(brief: BrandBrief, top_k: int = 20, filters: Optional[dict] = None) -> list[dict]:
    """Alias for :func:`get_candidates` (kept for readability at call sites)."""
    return get_candidates(brief, k=top_k, filters=filters)


def brand_match_all(brief: BrandBrief, persist: bool = False) -> dict[str, dict]:
    """Score every creator against the brief. Returns id -> result."""
    results = {c.influencer_id: brand_match(c.influencer_id, brief) for c in repo.list_candidates()}
    if persist:
        persist_brand_match(brief.brief_id, results)
    return results


def persist_brand_match(brief_id: str, results: dict[str, dict]) -> int:
    """Write brand_match_score into EXISTING scores rows for this brief only.

    Mirrors the growth-score persistence: touches only the one column so it never
    clobbers other fields the ranking step has written. Returns rows updated.
    """
    conn = repo.get_connection()
    updated = 0
    for iid, res in results.items():
        cur = conn.execute(
            "UPDATE scores SET brand_match_score=? WHERE brief_id=? AND influencer_id=?",
            (int(res["brand_match_score"]), brief_id, iid),
        )
        updated += cur.rowcount
    conn.commit()
    return updated


if __name__ == "__main__":
    print(f"brand_match module ready (embedding fallback={emb.using_fallback()}). "
          "Call brand_match(influencer_id, brief).")

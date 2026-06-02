"""Feature engineering (task-006).

Pure, deterministic transforms that turn raw profile/post/audience/metrics rows
into the engineered feature vectors the models consume. Two kinds of vector:

  * **brief-independent** (per creator): engagement, fraud-adjusted reach, real
    engagement, intent rates, comment quality, audience quality, posting
    consistency, growth, plus authenticity ratios. Computed once on ingest.
  * **fit features** (per creator x brief): ``audience_demo_match`` and
    ``brand_fit_similarity`` (cosine of brief vs creator embedding). Recomputed
    per brief.

Rules honored (specs/feature-engineering):
  * NO target leakage — never reads roi / success / is_fraud.
  * ``authenticity_factor`` comes from ``authenticity_results`` if present, else
    is estimated from ratios (both orderings supported).
  * Missing data -> neutral defaults / low-confidence flag, never NaN/inf.
  * Deterministic: same raw input -> identical vector.

Embeddings are produced via ``src.data.embeddings`` (shared with brand-matching)
and persisted into the vector store + ``influencers.embedding_ref``.
"""
from __future__ import annotations

import statistics
from typing import Any, Optional

import numpy as np

import config
from src.data import embeddings as emb
from src.store import repo
from src.store.schema import BrandBrief, Features, Influencer

FEATURE_VERSION = "fe-v1"

# Canonical ordered list of brief-independent features (the model input schema).
IMPACT_FEATURES = [
    "engagement_rate",
    "fraud_adjusted_reach",
    "real_engagement_rate",
    "save_rate",
    "share_rate",
    "comment_rate",
    "comment_quality",
    "audience_quality",
    "posting_consistency",
    "growth_rate_30d",
    "growth_rate_90d",
    "follower_following_ratio",
    "like_comment_ratio",
    "spike_anomaly_score",
    "comment_spam_ratio",
]
# Fit features appended for the per-brief vector (used by Impact + Match).
FIT_FEATURES = ["audience_demo_match", "brand_fit_similarity"]

_GENERIC_COMMENTS = {"nice", "great post", "first", "follow back", "check my page", "❤️", "🔥🔥🔥", ""}


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    return float(a / b) if b else default


def _clip01(x: float) -> float:
    return float(np.clip(x, 0.0, 1.0))


# --------------------------------------------------------------------------- #
# Brief-independent features
# --------------------------------------------------------------------------- #
def compute_creator_features(influencer_id: str) -> dict[str, float]:
    """Compute the brief-independent feature vector for one creator."""
    inf = repo.get_influencer(influencer_id)
    if inf is None:
        raise ValueError(f"unknown influencer {influencer_id}")
    posts = repo.get_posts(influencer_id)
    metrics = repo.get_metrics(influencer_id)
    audience = repo.get_audience_profile(influencer_id)
    auth = repo.get_authenticity(influencer_id)  # may be None (built later)

    followers = max(inf.followers or 0, 1)

    # --- authenticity_factor: from results if present, else estimate -------- #
    if auth is not None and auth.bot_follower_pct is not None:
        bot_pct = _clip01(auth.bot_follower_pct)
        spam_ratio = _clip01(auth.comment_spam_ratio or 0.0)
        spike_score = float(auth.spike_anomaly_score or 0.0)
    else:
        bot_pct = _estimate_bot_pct(inf, posts, metrics)
        spam_ratio = _estimate_spam_ratio(posts)
        spike_score = _spike_anomaly(metrics)
    authenticity_factor = _clip01(1.0 - bot_pct)

    # --- engagement aggregates over recent posts --------------------------- #
    if posts:
        likes = np.array([p.likes or 0 for p in posts], dtype=float)
        comments = np.array([p.comments or 0 for p in posts], dtype=float)
        shares = np.array([p.shares or 0 for p in posts], dtype=float)
        saves = np.array([p.saves or 0 for p in posts], dtype=float)
        total_eng = likes + comments + shares + saves
        engagement_rate = _clip01(float(np.mean(total_eng)) / followers)
        save_rate = _clip01(float(np.mean(saves)) / followers)
        share_rate = _clip01(float(np.mean(shares)) / followers)
        comment_rate = _clip01(float(np.mean(comments)) / followers)
        like_comment_ratio = _safe_div(float(np.sum(likes)), float(np.sum(comments)), default=0.0)
        comment_quality = _comment_quality(posts)
        low_confidence = len(posts) < 3
    else:
        engagement_rate = save_rate = share_rate = comment_rate = 0.0
        like_comment_ratio = 0.0
        comment_quality = 0.5  # neutral
        low_confidence = True

    real_engagement_rate = _clip01(engagement_rate * authenticity_factor)
    fraud_adjusted_reach = float(followers * authenticity_factor)

    # --- audience quality -------------------------------------------------- #
    if audience is not None and audience.audience_quality is not None:
        audience_quality = _clip01(audience.audience_quality)
    else:
        audience_quality = authenticity_factor  # fall back to authenticity

    # --- posting consistency (inverse std of inter-post gaps) -------------- #
    posting_consistency = _posting_consistency(posts)

    # --- growth from metrics series ---------------------------------------- #
    growth_30d, growth_90d = _growth_rates(metrics)

    follower_following_ratio = _safe_div(followers, max(inf.following or 0, 1), default=float(followers))

    vec = {
        "engagement_rate": round(engagement_rate, 6),
        "fraud_adjusted_reach": round(fraud_adjusted_reach, 2),
        "real_engagement_rate": round(real_engagement_rate, 6),
        "save_rate": round(save_rate, 6),
        "share_rate": round(share_rate, 6),
        "comment_rate": round(comment_rate, 6),
        "comment_quality": round(comment_quality, 6),
        "audience_quality": round(audience_quality, 6),
        "posting_consistency": round(posting_consistency, 6),
        "growth_rate_30d": round(growth_30d, 6),
        "growth_rate_90d": round(growth_90d, 6),
        "follower_following_ratio": round(follower_following_ratio, 4),
        "like_comment_ratio": round(like_comment_ratio, 4),
        "spike_anomaly_score": round(spike_score, 4),
        "comment_spam_ratio": round(spam_ratio, 6),
        "_low_confidence": float(low_confidence),
    }
    _assert_finite(vec)
    return vec


# --------------------------------------------------------------------------- #
# Per-brief fit features
# --------------------------------------------------------------------------- #
def compute_fit_features(influencer_id: str, brief: BrandBrief, creator_vec: Optional[np.ndarray] = None) -> dict[str, float]:
    """Compute audience_demo_match + brand_fit_similarity for one creator x brief."""
    inf = repo.get_influencer(influencer_id)
    audience = repo.get_audience_profile(influencer_id)

    # brand_fit_similarity: cosine of brief embedding vs creator embedding.
    if creator_vec is None:
        creator_vec = emb.embed_text(_creator_text(inf, repo.get_posts(influencer_id)))
    brief_vec = emb.embed_text(_brief_text(brief))
    brand_fit_similarity = _clip01((emb.cosine(creator_vec, brief_vec) + 1.0) / 2.0)  # map [-1,1]->[0,1]

    audience_demo_match = _audience_demo_match(audience, brief)

    vec = {
        "audience_demo_match": round(audience_demo_match, 6),
        "brand_fit_similarity": round(brand_fit_similarity, 6),
    }
    _assert_finite(vec)
    return vec


# --------------------------------------------------------------------------- #
# Helpers — estimators used when authenticity_results is absent
# --------------------------------------------------------------------------- #
def _estimate_bot_pct(inf: Influencer, posts, metrics) -> float:
    """Rough bot-share estimate from profile/engagement ratios (pre-authenticity)."""
    followers = max(inf.followers or 0, 1)
    if posts:
        avg_eng = float(np.mean([(p.likes or 0) + (p.comments or 0) for p in posts]))
        eng_rate = avg_eng / followers
    else:
        eng_rate = 0.02
    # Very low engagement for the follower count -> more likely inflated.
    # Expected organic engagement shrinks with size; compare against a loose floor.
    expected = 0.06 if followers < 100_000 else 0.02
    deficit = _clip01((expected - eng_rate) / expected) if expected else 0.0
    spike = _spike_anomaly(metrics)
    est = 0.05 + 0.6 * deficit + 0.1 * _clip01(spike / 4.0)
    return _clip01(est)


def _estimate_spam_ratio(posts) -> float:
    return _clip01(1.0 - _comment_quality(posts)) if posts else 0.05


def _comment_quality(posts) -> float:
    """Proxy: fraction of non-generic captions + length signal. [0,1], higher=better."""
    if not posts:
        return 0.5
    caps = [(p.caption or "").strip().lower() for p in posts]
    non_generic = sum(1 for c in caps if c not in _GENERIC_COMMENTS and len(c) > 12)
    return _clip01(non_generic / len(caps))


def _spike_anomaly(metrics) -> float:
    """Max z-score of weekly follower deltas (0 if too short)."""
    if not metrics or len(metrics) < 4:
        return 0.0
    followers = np.array([m.followers or 0 for m in metrics], dtype=float)
    deltas = np.diff(followers)
    if len(deltas) < 2:
        return 0.0
    mu, sd = float(np.mean(deltas)), float(np.std(deltas))
    if sd == 0:
        return 0.0
    return float(np.max((deltas - mu) / sd))


def _posting_consistency(posts) -> float:
    """1 / (1 + std of inter-post gaps in days). Higher = more regular."""
    if not posts or len(posts) < 2:
        return 0.5
    times = sorted([p.posted_at for p in posts if p.posted_at is not None])
    if len(times) < 2:
        return 0.5
    gaps = [(times[i + 1] - times[i]).total_seconds() / 86400.0 for i in range(len(times) - 1)]
    if not gaps:
        return 0.5
    sd = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
    return _clip01(1.0 / (1.0 + sd))


def _growth_rates(metrics) -> tuple[float, float]:
    """(30d, 90d) follower growth fractions from the metrics series."""
    if not metrics or len(metrics) < 2:
        return 0.0, 0.0
    ms = sorted(metrics, key=lambda m: m.date)
    followers = [m.followers or 0 for m in ms]
    dates = [m.date for m in ms]
    end_f = followers[-1]
    end_d = dates[-1]

    def growth_over(days: int) -> float:
        # find the earliest snapshot within `days` of the end
        ref_f = followers[0]
        for f, d in zip(followers, dates):
            if (end_d - d).days <= days:
                ref_f = f
                break
        return _safe_div(end_f - ref_f, max(ref_f, 1), default=0.0)

    return round(growth_over(30), 6), round(growth_over(90), 6)


def _audience_demo_match(audience, brief: BrandBrief) -> float:
    """Overlap of creator audience vs brief target (age band + gender + geo). [0,1]."""
    if audience is None:
        return 0.5  # neutral default, never error
    score = 0.0
    weight = 0.0

    # Age overlap
    if brief.target_age_min is not None and brief.target_age_max is not None and audience.age_distribution:
        bands = {
            "13-17": (13, 17), "18-24": (18, 24), "25-34": (25, 34),
            "35-44": (35, 44), "45+": (45, 99),
        }
        covered = 0.0
        for band, (lo, hi) in bands.items():
            frac = audience.age_distribution.get(band, 0.0) or 0.0
            # overlap if the band intersects the target range
            if hi >= brief.target_age_min and lo <= brief.target_age_max:
                covered += frac
        score += covered
        weight += 1.0

    # Gender overlap
    if brief.target_gender and audience.gender_split:
        g = brief.target_gender.lower()
        if g in ("female", "male"):
            score += audience.gender_split.get(g, 0.0) or 0.0
            weight += 1.0

    # Geo overlap
    if brief.target_geo and audience.geo_distribution:
        geo_score = sum((audience.geo_distribution.get(str(g), 0.0) or 0.0) for g in brief.target_geo)
        score += _clip01(geo_score)
        weight += 1.0

    return _clip01(score / weight) if weight else 0.5


def _creator_text(inf: Influencer, posts) -> str:
    """Embedding source = bio + recent captions + category."""
    caps = " ".join((p.caption or "") for p in posts[:8])
    return f"{inf.bio or ''} {caps} {inf.content_category or ''}".strip()


def _brief_text(brief: BrandBrief) -> str:
    parts = [brief.category or "", brief.tone or "", brief.raw_text or ""]
    if brief.target_interests:
        parts.append(" ".join(str(i) for i in brief.target_interests))
    return " ".join(p for p in parts if p).strip()


def _assert_finite(vec: dict[str, float]) -> None:
    for k, v in vec.items():
        if not np.isfinite(v):
            raise ValueError(f"non-finite feature {k}={v}")


# --------------------------------------------------------------------------- #
# Batch build + persistence
# --------------------------------------------------------------------------- #
def build_all_creator_features(persist: bool = True, embed: bool = True) -> dict[str, dict]:
    """Compute brief-independent features for every creator; optionally persist + embed."""
    creators = repo.list_candidates()
    out: dict[str, dict] = {}

    # Embeddings (batched) -> vector store + influencers.embedding_ref
    if embed:
        from src.store.vector import VectorStore

        vs = VectorStore()
        ids = [c.influencer_id for c in creators]
        texts = [_creator_text(c, repo.get_posts(c.influencer_id)) for c in creators]
        vecs = emb.embed_texts(texts)
        metas = [
            {"category": c.content_category, "region": c.region, "followers": c.followers}
            for c in creators
        ]
        vs.upsert_many(ids, vecs, metas)
        vs.persist()
        for c in creators:
            c.embedding_ref = f"vec_{c.influencer_id}"
            repo.upsert_influencer(c)

    for c in creators:
        vec = compute_creator_features(c.influencer_id)
        out[c.influencer_id] = vec
        if persist:
            repo.upsert_features(
                Features(influencer_id=c.influencer_id, brief_id=None, feature_vector=vec, feature_version=FEATURE_VERSION)
            )
    return out


def features_to_matrix(feature_dicts: dict[str, dict], columns: Optional[list[str]] = None):
    """Stack feature dicts into (ids, X, columns) for model training. Drops private keys."""
    columns = columns or IMPACT_FEATURES
    ids = sorted(feature_dicts.keys())
    X = np.array([[feature_dicts[i].get(col, 0.0) for col in columns] for i in ids], dtype=float)
    return ids, X, columns


if __name__ == "__main__":
    feats = build_all_creator_features(persist=True, embed=True)
    print(f"Built features for {len(feats)} creators "
          f"(embeddings: {'FALLBACK' if emb.using_fallback() else 'all-MiniLM-L6-v2'})")

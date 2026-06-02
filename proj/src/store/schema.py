"""Data model — the contract every other feature reads/writes against.

Two things live here and nowhere else:
  1. Pydantic models for all 10 entities (the single source of truth for shapes).
  2. The SQLite DDL + per-table JSON-column registry used by the repository.

Field names/types follow docs/05_backend_schema.md exactly. Schema is written to
map cleanly onto Postgres + pgvector later (no SQLite-only tricks).
"""
from __future__ import annotations

from datetime import date as Date
from datetime import datetime as DateTime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# config sits at the proj/ root; import the small constants we validate against.
try:
    from config import DEFAULT_CURRENCY, DEFAULT_OBJECTIVE_WEIGHTS, GOALS, STATUSES
except ImportError:  # pragma: no cover - fallback if imported before root on path
    DEFAULT_CURRENCY = "INR"
    DEFAULT_OBJECTIVE_WEIGHTS = {"impact": 0.45, "authenticity": 0.30, "match": 0.20, "cost": 0.05}
    GOALS = ("awareness", "engagement", "conversions", "sales")
    STATUSES = ("recommended", "flagged", "excluded")


# --------------------------------------------------------------------------- #
# Entity models
# --------------------------------------------------------------------------- #
class Influencer(BaseModel):
    influencer_id: str
    handle: Optional[str] = None
    platform: Optional[str] = None
    display_name: Optional[str] = None
    bio: Optional[str] = None
    content_category: Optional[str] = None
    followers: int = 0
    following: int = 0
    post_count: int = 0
    account_created: Optional[Date] = None
    region: Optional[str] = None
    verified: bool = False
    embedding_ref: Optional[str] = None
    ingested_at: Optional[DateTime] = None


class PostSample(BaseModel):
    post_id: str
    influencer_id: str
    posted_at: Optional[DateTime] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    views: int = 0
    caption: Optional[str] = None
    media_type: Optional[str] = None


class MetricsSnapshot(BaseModel):
    snapshot_id: str
    influencer_id: str
    date: Date
    followers: int = 0
    avg_engagement: float = 0.0


class AudienceProfile(BaseModel):
    influencer_id: str
    age_distribution: dict[str, Any] = Field(default_factory=dict)
    gender_split: dict[str, Any] = Field(default_factory=dict)
    geo_distribution: dict[str, Any] = Field(default_factory=dict)
    top_interests: list[Any] = Field(default_factory=list)
    audience_quality: Optional[float] = None


class AuthenticityResult(BaseModel):
    influencer_id: str
    authenticity_score: int = 0
    bot_follower_pct: float = 0.0
    engagement_pod_flag: bool = False
    spike_anomaly_score: float = 0.0
    comment_spam_ratio: float = 0.0
    flags: list[str] = Field(default_factory=list)
    model_version: Optional[str] = None
    computed_at: Optional[DateTime] = None


class Features(BaseModel):
    influencer_id: str
    brief_id: Optional[str] = None  # null/'' => brief-independent feature row
    feature_vector: dict[str, Any] = Field(default_factory=dict)
    feature_version: Optional[str] = None


class BrandBrief(BaseModel):
    brief_id: str
    raw_text: str = ""
    brand_name: Optional[str] = None
    category: Optional[str] = None
    target_age_min: Optional[int] = None
    target_age_max: Optional[int] = None
    target_gender: Optional[str] = None
    target_geo: list[Any] = Field(default_factory=list)
    target_interests: list[Any] = Field(default_factory=list)
    budget: Optional[float] = None
    currency: str = DEFAULT_CURRENCY
    goal: Optional[str] = None
    tone: Optional[str] = None
    objective_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_OBJECTIVE_WEIGHTS))
    banned_terms: list[Any] = Field(default_factory=list)  # off-brand terms -> hard penalty in brand-match
    created_at: Optional[DateTime] = None

    @field_validator("goal")
    @classmethod
    def _check_goal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in GOALS:
            raise ValueError(f"goal must be one of {GOALS}, got {v!r}")
        return v


class Scores(BaseModel):
    score_id: str
    brief_id: str
    influencer_id: str
    true_impact_score: Optional[int] = None
    predicted_roi: Optional[float] = None
    success_prob: Optional[float] = None
    brand_match_score: Optional[int] = None
    authenticity_score: Optional[int] = None
    growth_potential_score: Optional[int] = None
    composite_rank_score: Optional[float] = None
    drivers: list[Any] = Field(default_factory=list)
    computed_at: Optional[DateTime] = None


class Recommendation(BaseModel):
    recommendation_id: str
    brief_id: str
    summary: Optional[str] = None
    total_estimated_reach: Optional[int] = None
    projected_conversions: Optional[int] = None
    projected_roi: Optional[float] = None
    recommended_budget_split: dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[DateTime] = None


class RecommendationItem(BaseModel):
    item_id: str
    recommendation_id: str
    influencer_id: str
    rank: int
    allocated_budget: float = 0.0
    rationale: Optional[str] = None
    status: str = "recommended"
    flag_reason: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got {v!r}")
        return v


# --------------------------------------------------------------------------- #
# JSON column registry (columns stored as TEXT-encoded JSON in SQLite)
# --------------------------------------------------------------------------- #
JSON_COLUMNS: dict[str, set[str]] = {
    "influencers": set(),
    "post_samples": set(),
    "metrics_snapshot": set(),
    "audience_profile": {"age_distribution", "gender_split", "geo_distribution", "top_interests"},
    "authenticity_results": {"flags"},
    "features": {"feature_vector"},
    "brand_brief": {"target_geo", "target_interests", "objective_weights", "banned_terms"},
    "scores": {"drivers"},
    "recommendations": {"recommended_budget_split"},
    "recommendation_items": set(),
}


# --------------------------------------------------------------------------- #
# DDL — one CREATE TABLE per entity (executed in dependency order)
# --------------------------------------------------------------------------- #
DDL: dict[str, str] = {
    "influencers": """
        CREATE TABLE IF NOT EXISTS influencers (
            influencer_id   TEXT PRIMARY KEY,
            handle          TEXT,
            platform        TEXT,
            display_name    TEXT,
            bio             TEXT,
            content_category TEXT,
            followers       INTEGER,
            following       INTEGER,
            post_count      INTEGER,
            account_created TEXT,
            region          TEXT,
            verified        INTEGER,
            embedding_ref   TEXT,
            ingested_at     TEXT
        )
    """,
    "post_samples": """
        CREATE TABLE IF NOT EXISTS post_samples (
            post_id       TEXT PRIMARY KEY,
            influencer_id TEXT,
            posted_at     TEXT,
            likes         INTEGER,
            comments      INTEGER,
            shares        INTEGER,
            saves         INTEGER,
            views         INTEGER,
            caption       TEXT,
            media_type    TEXT,
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
    "metrics_snapshot": """
        CREATE TABLE IF NOT EXISTS metrics_snapshot (
            snapshot_id    TEXT PRIMARY KEY,
            influencer_id  TEXT,
            date           TEXT,
            followers      INTEGER,
            avg_engagement REAL,
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
    "audience_profile": """
        CREATE TABLE IF NOT EXISTS audience_profile (
            influencer_id    TEXT PRIMARY KEY,
            age_distribution TEXT,
            gender_split     TEXT,
            geo_distribution TEXT,
            top_interests    TEXT,
            audience_quality REAL,
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
    "authenticity_results": """
        CREATE TABLE IF NOT EXISTS authenticity_results (
            influencer_id      TEXT PRIMARY KEY,
            authenticity_score INTEGER,
            bot_follower_pct   REAL,
            engagement_pod_flag INTEGER,
            spike_anomaly_score REAL,
            comment_spam_ratio REAL,
            flags              TEXT,
            model_version      TEXT,
            computed_at        TEXT,
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
    "features": """
        CREATE TABLE IF NOT EXISTS features (
            influencer_id  TEXT NOT NULL,
            brief_id       TEXT NOT NULL DEFAULT '',
            feature_vector TEXT,
            feature_version TEXT,
            PRIMARY KEY (influencer_id, brief_id),
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
    "brand_brief": """
        CREATE TABLE IF NOT EXISTS brand_brief (
            brief_id          TEXT PRIMARY KEY,
            raw_text          TEXT,
            brand_name        TEXT,
            category          TEXT,
            target_age_min    INTEGER,
            target_age_max    INTEGER,
            target_gender     TEXT,
            target_geo        TEXT,
            target_interests  TEXT,
            budget            REAL,
            currency          TEXT,
            goal              TEXT,
            tone              TEXT,
            objective_weights TEXT,
            banned_terms      TEXT,
            created_at        TEXT
        )
    """,
    "scores": """
        CREATE TABLE IF NOT EXISTS scores (
            score_id              TEXT PRIMARY KEY,
            brief_id              TEXT NOT NULL,
            influencer_id         TEXT NOT NULL,
            true_impact_score     INTEGER,
            predicted_roi         REAL,
            success_prob          REAL,
            brand_match_score     INTEGER,
            authenticity_score    INTEGER,
            growth_potential_score INTEGER,
            composite_rank_score  REAL,
            drivers               TEXT,
            computed_at           TEXT,
            UNIQUE (brief_id, influencer_id),
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id),
            FOREIGN KEY (brief_id) REFERENCES brand_brief (brief_id)
        )
    """,
    "recommendations": """
        CREATE TABLE IF NOT EXISTS recommendations (
            recommendation_id      TEXT PRIMARY KEY,
            brief_id               TEXT,
            summary                TEXT,
            total_estimated_reach  INTEGER,
            projected_conversions  INTEGER,
            projected_roi          REAL,
            recommended_budget_split TEXT,
            created_at             TEXT,
            FOREIGN KEY (brief_id) REFERENCES brand_brief (brief_id)
        )
    """,
    "recommendation_items": """
        CREATE TABLE IF NOT EXISTS recommendation_items (
            item_id           TEXT PRIMARY KEY,
            recommendation_id TEXT,
            influencer_id     TEXT,
            rank              INTEGER,
            allocated_budget  REAL,
            rationale         TEXT,
            status            TEXT,
            flag_reason       TEXT,
            FOREIGN KEY (recommendation_id) REFERENCES recommendations (recommendation_id),
            FOREIGN KEY (influencer_id) REFERENCES influencers (influencer_id)
        )
    """,
}

# Indexes on the foreign-key columns we look up by influencer_id. Without these,
# every get_posts()/get_metrics() is a full-table scan -> feature-building becomes
# O(n^2) and a large population (15k+ creators) hangs for hours. With them it is
# a fast index seek. Created in init_db() right after the tables (idempotent).
INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS idx_posts_influencer ON post_samples (influencer_id)",
    "CREATE INDEX IF NOT EXISTS idx_metrics_influencer ON metrics_snapshot (influencer_id)",
    "CREATE INDEX IF NOT EXISTS idx_features_influencer ON features (influencer_id)",
    "CREATE INDEX IF NOT EXISTS idx_scores_brief ON scores (brief_id)",
    "CREATE INDEX IF NOT EXISTS idx_recitems_rec ON recommendation_items (recommendation_id)",
)

# Convenience: model class <-> table name (used by the repository).
MODEL_TABLE: dict[type[BaseModel], str] = {
    Influencer: "influencers",
    PostSample: "post_samples",
    MetricsSnapshot: "metrics_snapshot",
    AudienceProfile: "audience_profile",
    AuthenticityResult: "authenticity_results",
    Features: "features",
    BrandBrief: "brand_brief",
    Scores: "scores",
    Recommendation: "recommendations",
    RecommendationItem: "recommendation_items",
}

__all__ = [
    "Influencer", "PostSample", "MetricsSnapshot", "AudienceProfile",
    "AuthenticityResult", "Features", "BrandBrief", "Scores",
    "Recommendation", "RecommendationItem",
    "DDL", "INDEXES", "JSON_COLUMNS", "MODEL_TABLE",
]

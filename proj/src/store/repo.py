"""SQLite repository — the only place that talks SQL.

Every other module reads/writes its data through these functions and never
touches the database directly. Models go in as pydantic objects and come back
as pydantic objects; JSON / date / bool fields are (de)serialized automatically.

Design notes
------------
* A single lazily-opened connection is reused (works for scripts + Streamlit).
* Writes are upserts keyed on the natural PK, so re-ingest never duplicates.
* Empty queries return [] / None, never raise.
* `set_db_path()` lets tests point at a throwaway database.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date as Date
from datetime import datetime as DateTime
from pathlib import Path
from typing import Any, Optional

import config
from src.store.schema import (
    DDL,
    INDEXES,
    JSON_COLUMNS,
    AudienceProfile,
    AuthenticityResult,
    BrandBrief,
    Features,
    Influencer,
    MetricsSnapshot,
    PostSample,
    Recommendation,
    RecommendationItem,
    Scores,
)

# --------------------------------------------------------------------------- #
# Connection management
# --------------------------------------------------------------------------- #
_CONN: Optional[sqlite3.Connection] = None
_DB_PATH_OVERRIDE: Optional[Path] = None


def set_db_path(path: str | Path) -> None:
    """Point the repository at a specific database file (closes any open one)."""
    global _DB_PATH_OVERRIDE, _CONN
    if _CONN is not None:
        _CONN.close()
        _CONN = None
    _DB_PATH_OVERRIDE = Path(path)


def get_connection() -> sqlite3.Connection:
    """Return the shared connection, opening it (and the data dir) on first use."""
    global _CONN
    if _CONN is None:
        config.ensure_dirs()
        path = _DB_PATH_OVERRIDE or config.DB_PATH
        _CONN = sqlite3.connect(str(path), check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
        _CONN.execute("PRAGMA journal_mode=WAL")
    return _CONN


def close_connection() -> None:
    global _CONN
    if _CONN is not None:
        _CONN.close()
        _CONN = None


def init_db() -> None:
    """Create all tables if they do not exist (idempotent)."""
    conn = get_connection()
    for table in DDL:  # dict preserves insertion (dependency) order
        conn.execute(DDL[table])
    for idx in INDEXES:  # FK lookup indexes -> avoids O(n^2) feature builds at scale
        conn.execute(idx)
    conn.commit()


# --------------------------------------------------------------------------- #
# (De)serialization helpers
# --------------------------------------------------------------------------- #
def _dump(model: Any, json_cols: set[str]) -> dict[str, Any]:
    """pydantic model -> dict of SQLite-storable primitives."""
    out: dict[str, Any] = {}
    for key, val in model.model_dump().items():
        if val is None:
            out[key] = None
        elif key in json_cols:
            out[key] = json.dumps(val, default=str)
        elif isinstance(val, bool):
            out[key] = int(val)
        elif isinstance(val, (Date, DateTime)):
            out[key] = val.isoformat()
        else:
            out[key] = val
    return out


def _load(row: sqlite3.Row, cls: type, json_cols: set[str]) -> Any:
    """SQLite row -> pydantic model (pydantic parses ISO dates / bool ints)."""
    data = dict(row)
    for col in json_cols:
        if data.get(col) is not None:
            data[col] = json.loads(data[col])
    return cls(**data)


def _upsert(table: str, row: dict[str, Any], conflict_cols: list[str]) -> None:
    conn = get_connection()
    cols = list(row.keys())
    placeholders = ",".join("?" for _ in cols)
    update_cols = [c for c in cols if c not in conflict_cols]
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    if update_cols:
        sets = ",".join(f"{c}=excluded.{c}" for c in update_cols)
        sql += f" ON CONFLICT({','.join(conflict_cols)}) DO UPDATE SET {sets}"
    else:
        sql += f" ON CONFLICT({','.join(conflict_cols)}) DO NOTHING"
    conn.execute(sql, [row[c] for c in cols])
    conn.commit()


def _bulk_upsert(table: str, rows: list[dict[str, Any]], conflict_cols: list[str]) -> None:
    if not rows:
        return
    conn = get_connection()
    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    update_cols = [c for c in cols if c not in conflict_cols]
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
    if update_cols:
        sets = ",".join(f"{c}=excluded.{c}" for c in update_cols)
        sql += f" ON CONFLICT({','.join(conflict_cols)}) DO UPDATE SET {sets}"
    else:
        sql += f" ON CONFLICT({','.join(conflict_cols)}) DO NOTHING"
    conn.executemany(sql, [[r[c] for c in cols] for r in rows])
    conn.commit()


# --------------------------------------------------------------------------- #
# influencers
# --------------------------------------------------------------------------- #
def upsert_influencer(inf: Influencer) -> None:
    _upsert("influencers", _dump(inf, JSON_COLUMNS["influencers"]), ["influencer_id"])


def bulk_upsert_influencers(items: list[Influencer]) -> None:
    _bulk_upsert("influencers", [_dump(i, JSON_COLUMNS["influencers"]) for i in items], ["influencer_id"])


def get_influencer(influencer_id: str) -> Optional[Influencer]:
    row = get_connection().execute(
        "SELECT * FROM influencers WHERE influencer_id=?", (influencer_id,)
    ).fetchone()
    return _load(row, Influencer, JSON_COLUMNS["influencers"]) if row else None


def list_candidates(
    category: Optional[str] = None,
    region: Optional[str] = None,
    min_followers: Optional[int] = None,
    max_followers: Optional[int] = None,
    limit: Optional[int] = None,
) -> list[Influencer]:
    """Metadata-filtered candidate list. No filters => all influencers."""
    clauses: list[str] = []
    params: list[Any] = []
    if category is not None:
        clauses.append("content_category=?")
        params.append(category)
    if region is not None:
        clauses.append("region=?")
        params.append(region)
    if min_followers is not None:
        clauses.append("followers>=?")
        params.append(min_followers)
    if max_followers is not None:
        clauses.append("followers<=?")
        params.append(max_followers)
    sql = "SELECT * FROM influencers"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY influencer_id"  # deterministic
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = get_connection().execute(sql, params).fetchall()
    return [_load(r, Influencer, JSON_COLUMNS["influencers"]) for r in rows]


# --------------------------------------------------------------------------- #
# post_samples
# --------------------------------------------------------------------------- #
def insert_post_sample(post: PostSample) -> None:
    _upsert("post_samples", _dump(post, JSON_COLUMNS["post_samples"]), ["post_id"])


def bulk_insert_posts(posts: list[PostSample]) -> None:
    _bulk_upsert("post_samples", [_dump(p, JSON_COLUMNS["post_samples"]) for p in posts], ["post_id"])


def get_posts(influencer_id: str) -> list[PostSample]:
    rows = get_connection().execute(
        "SELECT * FROM post_samples WHERE influencer_id=? ORDER BY post_id", (influencer_id,)
    ).fetchall()
    return [_load(r, PostSample, JSON_COLUMNS["post_samples"]) for r in rows]


# --------------------------------------------------------------------------- #
# metrics_snapshot
# --------------------------------------------------------------------------- #
def insert_metrics_snapshot(snap: MetricsSnapshot) -> None:
    _upsert("metrics_snapshot", _dump(snap, JSON_COLUMNS["metrics_snapshot"]), ["snapshot_id"])


def bulk_insert_snapshots(snaps: list[MetricsSnapshot]) -> None:
    _bulk_upsert(
        "metrics_snapshot",
        [_dump(s, JSON_COLUMNS["metrics_snapshot"]) for s in snaps],
        ["snapshot_id"],
    )


def get_metrics(influencer_id: str) -> list[MetricsSnapshot]:
    rows = get_connection().execute(
        "SELECT * FROM metrics_snapshot WHERE influencer_id=? ORDER BY date", (influencer_id,)
    ).fetchall()
    return [_load(r, MetricsSnapshot, JSON_COLUMNS["metrics_snapshot"]) for r in rows]


# --------------------------------------------------------------------------- #
# audience_profile
# --------------------------------------------------------------------------- #
def upsert_audience_profile(ap: AudienceProfile) -> None:
    _upsert("audience_profile", _dump(ap, JSON_COLUMNS["audience_profile"]), ["influencer_id"])


def get_audience_profile(influencer_id: str) -> Optional[AudienceProfile]:
    row = get_connection().execute(
        "SELECT * FROM audience_profile WHERE influencer_id=?", (influencer_id,)
    ).fetchone()
    return _load(row, AudienceProfile, JSON_COLUMNS["audience_profile"]) if row else None


# --------------------------------------------------------------------------- #
# authenticity_results
# --------------------------------------------------------------------------- #
def upsert_authenticity(res: AuthenticityResult) -> None:
    _upsert("authenticity_results", _dump(res, JSON_COLUMNS["authenticity_results"]), ["influencer_id"])


def get_authenticity(influencer_id: str) -> Optional[AuthenticityResult]:
    row = get_connection().execute(
        "SELECT * FROM authenticity_results WHERE influencer_id=?", (influencer_id,)
    ).fetchone()
    return _load(row, AuthenticityResult, JSON_COLUMNS["authenticity_results"]) if row else None


# --------------------------------------------------------------------------- #
# features  (brief_id None <=> '' for the brief-independent row)
# --------------------------------------------------------------------------- #
def upsert_features(feat: Features) -> None:
    row = _dump(feat, JSON_COLUMNS["features"])
    if row.get("brief_id") is None:
        row["brief_id"] = ""
    _upsert("features", row, ["influencer_id", "brief_id"])


def get_features(influencer_id: str, brief_id: Optional[str] = None) -> Optional[Features]:
    key = brief_id or ""
    row = get_connection().execute(
        "SELECT * FROM features WHERE influencer_id=? AND brief_id=?", (influencer_id, key)
    ).fetchone()
    if not row:
        return None
    feat = _load(row, Features, JSON_COLUMNS["features"])
    if feat.brief_id == "":
        feat.brief_id = None
    return feat


# --------------------------------------------------------------------------- #
# brand_brief
# --------------------------------------------------------------------------- #
def upsert_brief(brief: BrandBrief) -> None:
    _upsert("brand_brief", _dump(brief, JSON_COLUMNS["brand_brief"]), ["brief_id"])


def get_brief(brief_id: str) -> Optional[BrandBrief]:
    row = get_connection().execute(
        "SELECT * FROM brand_brief WHERE brief_id=?", (brief_id,)
    ).fetchone()
    return _load(row, BrandBrief, JSON_COLUMNS["brand_brief"]) if row else None


# --------------------------------------------------------------------------- #
# scores  (one row per brief x influencer)
# --------------------------------------------------------------------------- #
def upsert_scores(score: Scores) -> None:
    _upsert("scores", _dump(score, JSON_COLUMNS["scores"]), ["brief_id", "influencer_id"])


def get_scores(brief_id: str, influencer_id: str) -> Optional[Scores]:
    row = get_connection().execute(
        "SELECT * FROM scores WHERE brief_id=? AND influencer_id=?", (brief_id, influencer_id)
    ).fetchone()
    return _load(row, Scores, JSON_COLUMNS["scores"]) if row else None


def list_scores(brief_id: str) -> list[Scores]:
    rows = get_connection().execute(
        "SELECT * FROM scores WHERE brief_id=? ORDER BY influencer_id", (brief_id,)
    ).fetchall()
    return [_load(r, Scores, JSON_COLUMNS["scores"]) for r in rows]


# --------------------------------------------------------------------------- #
# recommendations + items
# --------------------------------------------------------------------------- #
def save_recommendation(rec: Recommendation, items: list[RecommendationItem]) -> None:
    """Upsert the recommendation and replace its line items atomically."""
    _upsert("recommendations", _dump(rec, JSON_COLUMNS["recommendations"]), ["recommendation_id"])
    conn = get_connection()
    conn.execute("DELETE FROM recommendation_items WHERE recommendation_id=?", (rec.recommendation_id,))
    conn.commit()
    _bulk_upsert(
        "recommendation_items",
        [_dump(it, JSON_COLUMNS["recommendation_items"]) for it in items],
        ["item_id"],
    )


def get_recommendation(
    recommendation_id: str,
) -> Optional[tuple[Recommendation, list[RecommendationItem]]]:
    row = get_connection().execute(
        "SELECT * FROM recommendations WHERE recommendation_id=?", (recommendation_id,)
    ).fetchone()
    if not row:
        return None
    rec = _load(row, Recommendation, JSON_COLUMNS["recommendations"])
    item_rows = get_connection().execute(
        "SELECT * FROM recommendation_items WHERE recommendation_id=? ORDER BY rank",
        (recommendation_id,),
    ).fetchall()
    items = [_load(r, RecommendationItem, JSON_COLUMNS["recommendation_items"]) for r in item_rows]
    return rec, items


# --------------------------------------------------------------------------- #
# misc helpers
# --------------------------------------------------------------------------- #
def count(table: str) -> int:
    """Row count for any table (handy for smoke tests / sanity checks)."""
    return get_connection().execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

"""
agent/retriever.py
──────────────────
Retrieves candidate influencer IDs relevant to a parsed brief.

Uses sentence-transformers + FAISS for semantic search.
Falls back to metadata filter only (no FAISS) if the index isn't built yet.
Person A builds the FAISS index as part of the data pipeline.
"""

import os
import json
import numpy as np

# ── Constants ─────────────────────────────────────────────────────────────────
FAISS_INDEX_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "faiss.index")
FAISS_META_PATH  = os.path.join(os.path.dirname(__file__), "..", "data", "faiss_meta.json")
EMBED_MODEL      = "all-MiniLM-L6-v2"
TOP_K            = 20   # candidates before re-ranking


def _embed_brief(parsed_brief: dict) -> np.ndarray:
    """
    Build a single embedding string from the parsed brief and embed it.
    """
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)

    ta = parsed_brief.get("target_audience", {})
    query = (
        f"{parsed_brief.get('category', '')} "
        f"{ta.get('geo', '')} "
        f"{ta.get('gender', '')} "
        f"age {ta.get('age_min', 18)}-{ta.get('age_max', 45)} "
        f"{parsed_brief.get('tone', '')} "
        f"{parsed_brief.get('goal', '')}"
    )
    embedding = model.encode([query], normalize_embeddings=True)
    return embedding.astype("float32")


def _faiss_search(embedding: np.ndarray, top_k: int = TOP_K) -> list[str]:
    """Search the FAISS index. Returns influencer_ids."""
    import faiss

    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(FAISS_META_PATH):
        return []

    index = faiss.read_index(FAISS_INDEX_PATH)
    with open(FAISS_META_PATH) as f:
        meta = json.load(f)   # list of {influencer_id, category, region, followers}

    distances, indices = index.search(embedding, top_k)
    results = []
    for idx in indices[0]:
        if 0 <= idx < len(meta):
            results.append(meta[idx]["influencer_id"])
    return results


def _metadata_fallback(parsed_brief: dict, db_path: str | None = None) -> list[str]:
    """
    Simple SQLite filter when FAISS index isn't ready.
    Returns up to TOP_K influencer_ids matching category + region.
    """
    import sqlite3

    db = db_path or os.path.join(os.path.dirname(__file__), "..", "data", "ratefluencer.db")
    if not os.path.exists(db):
        # No DB either — return dummy IDs for UI testing
        from utils.dummy_scores import DUMMY_RANKED
        return DUMMY_RANKED

    category = parsed_brief.get("category", "")
    geo      = parsed_brief.get("target_audience", {}).get("geo", "")

    conn = sqlite3.connect(db)
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT influencer_id FROM influencers
        WHERE content_category = ? OR region = ?
        LIMIT ?
        """,
        (category, geo, TOP_K),
    )
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def get_candidates(parsed_brief: dict, db_path: str | None = None) -> list[str]:
    """
    Main retrieval function called by the agent.

    Args:
        parsed_brief: Output of parse_brief()
        db_path: Optional override for SQLite path

    Returns:
        List of influencer_ids (up to TOP_K), ordered by semantic relevance.
    """
    # Try FAISS first
    try:
        embedding = _embed_brief(parsed_brief)
        ids = _faiss_search(embedding)
        if ids:
            print(f"[retriever] FAISS returned {len(ids)} candidates")
            return ids
    except Exception as e:
        print(f"[retriever] FAISS search failed ({e}) — falling back to metadata filter")

    # Fallback to metadata filter
    ids = _metadata_fallback(parsed_brief, db_path)
    print(f"[retriever] Metadata fallback returned {len(ids)} candidates")
    return ids


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    demo_brief = {
        "category": "skincare",
        "target_audience": {"age_min": 22, "age_max": 35, "gender": "female", "geo": "India"},
        "goal": "sales",
        "tone": "clean, science-backed",
    }
    candidates = get_candidates(demo_brief)
    print("Candidates:", candidates)

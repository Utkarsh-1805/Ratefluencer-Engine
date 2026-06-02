"""Vector store — the `influencer_profiles` collection (FAISS backend).

A thin wrapper everything else uses for embedding storage + retrieval. It keeps
three things in lock-step and persists them under ``data/vector/``:

  * a FAISS inner-product index over L2-normalized 384-dim vectors
    (inner product of normalized vectors == cosine similarity),
  * the row-order list of ``influencer_id`` (FAISS only knows integer rows),
  * a metadata dict ``{influencer_id: {category, region, followers}}`` for
    filtering, since FAISS itself does not filter.

Design choices
--------------
* **Upsert by influencer_id** — re-embedding a creator replaces the old vector,
  never duplicates (mirrors the SQL repository).
* **Deterministic ordering** — ties in similarity break by ``influencer_id`` so
  seeded demo queries return identical results every run.
* **Filtered query** — category/region/follower filters are applied to the
  metadata, then similarity is ranked within the allowed set, so top-k is always
  filled from valid candidates (not silently truncated by a pre-filter).

The embedding vectors themselves are produced in feature-engineering /
brand-matching; this module is storage + retrieval only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

import numpy as np

import config

# FAISS is optional at import time so the rest of the store works without it;
# we only require it when the vector store is actually used.
try:
    import faiss  # type: ignore

    _HAS_FAISS = True
except ImportError:  # pragma: no cover
    faiss = None  # type: ignore
    _HAS_FAISS = False


def _normalize(mat: np.ndarray) -> np.ndarray:
    """L2-normalize rows so inner product == cosine similarity. Zero-safe."""
    mat = np.ascontiguousarray(mat, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


class VectorStore:
    """Persistent FAISS-backed store for the ``influencer_profiles`` collection."""

    def __init__(self, dim: int = config.EMBED_DIM, persist_dir: Optional[Path] = None):
        if not _HAS_FAISS:
            raise ImportError(
                "faiss is not installed. Install with `py -m pip install faiss-cpu` "
                "(pre-installed on Kaggle)."
            )
        self.dim = dim
        self.dir = Path(persist_dir or config.VECTOR_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)

        self._index_path = self.dir / f"{config.VECTOR_COLLECTION}.faiss"
        self._meta_path = self.dir / f"{config.VECTOR_COLLECTION}.meta.json"

        # In-memory mirrors (source of truth for ids/metadata; FAISS holds vectors).
        self._ids: list[str] = []
        self._pos: dict[str, int] = {}  # influencer_id -> row index
        self._meta: dict[str, dict[str, Any]] = {}
        self._vectors: np.ndarray = np.zeros((0, dim), dtype=np.float32)  # normalized

        self._index = faiss.IndexFlatIP(dim)
        self._load()

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def _rebuild_index(self) -> None:
        self._index = faiss.IndexFlatIP(self.dim)
        if len(self._ids):
            self._index.add(self._vectors)

    def _load(self) -> None:
        if self._meta_path.exists():
            payload = json.loads(self._meta_path.read_text(encoding="utf-8"))
            self._ids = payload["ids"]
            self._meta = payload["meta"]
            self._pos = {iid: i for i, iid in enumerate(self._ids)}
            vecs = self.dir / f"{config.VECTOR_COLLECTION}.vectors.npy"
            if vecs.exists() and self._ids:
                self._vectors = np.load(vecs)
            else:
                self._vectors = np.zeros((0, self.dim), dtype=np.float32)
            self._rebuild_index()

    def persist(self) -> None:
        """Write index + metadata to disk so it survives a restart."""
        np.save(self.dir / f"{config.VECTOR_COLLECTION}.vectors.npy", self._vectors)
        faiss.write_index(self._index, str(self._index_path))
        self._meta_path.write_text(
            json.dumps({"ids": self._ids, "meta": self._meta}), encoding="utf-8"
        )

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def upsert(self, influencer_id: str, vector: np.ndarray | list[float], metadata: dict[str, Any]) -> None:
        """Insert or replace one creator's vector + metadata (no duplicates)."""
        self.upsert_many([influencer_id], np.asarray([vector], dtype=np.float32), [metadata])

    def upsert_many(
        self,
        influencer_ids: list[str],
        vectors: np.ndarray,
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Batch upsert. ``vectors`` shape = (n, dim)."""
        vectors = np.asarray(vectors, dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[1] != self.dim:
            raise ValueError(f"vectors must be (n, {self.dim}); got {vectors.shape}")
        if not (len(influencer_ids) == vectors.shape[0] == len(metadatas)):
            raise ValueError("influencer_ids, vectors, metadatas must be the same length")

        normed = _normalize(vectors)
        # Grow the in-memory matrix lazily; rebuild FAISS once at the end.
        rows = list(self._vectors) if len(self._ids) else []
        for iid, vec, meta in zip(influencer_ids, normed, metadatas):
            self._meta[iid] = dict(meta)
            if iid in self._pos:  # replace existing row in place
                rows[self._pos[iid]] = vec
            else:
                self._pos[iid] = len(self._ids)
                self._ids.append(iid)
                rows.append(vec)
        self._vectors = np.ascontiguousarray(np.vstack(rows), dtype=np.float32)
        self._rebuild_index()

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def query(
        self,
        vector: np.ndarray | list[float],
        top_k: int = 10,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """Cosine top-k, optionally restricted by metadata filters.

        ``filters`` keys: ``category``, ``region`` (exact match),
        ``min_followers``, ``max_followers`` (range). Returns a list of
        ``{influencer_id, score, metadata}`` sorted by score desc, ties by id.
        Empty / no-match => ``[]`` (never raises).
        """
        if len(self._ids) == 0:
            return []

        allowed = self._apply_filters(filters)
        if not allowed:
            return []

        q = _normalize(np.asarray([vector], dtype=np.float32))[0]
        sims = self._vectors @ q  # cosine for every stored creator

        # Restrict to the allowed rows, then rank deterministically.
        candidates = [(self._ids[i], float(sims[i])) for i in allowed]
        # Sort by score desc, then influencer_id asc for stable tie-breaking.
        candidates.sort(key=lambda t: (-t[1], t[0]))
        out = candidates[: max(0, top_k)]
        return [
            {"influencer_id": iid, "score": score, "metadata": self._meta.get(iid, {})}
            for iid, score in out
        ]

    def _apply_filters(self, filters: Optional[dict[str, Any]]) -> list[int]:
        """Return the list of row indices that satisfy the metadata filters."""
        if not filters:
            return list(range(len(self._ids)))
        category = filters.get("category")
        region = filters.get("region")
        min_f = filters.get("min_followers")
        max_f = filters.get("max_followers")
        rows: list[int] = []
        for i, iid in enumerate(self._ids):
            m = self._meta.get(iid, {})
            if category is not None and m.get("category") != category:
                continue
            if region is not None and m.get("region") != region:
                continue
            if min_f is not None and (m.get("followers") or 0) < min_f:
                continue
            if max_f is not None and (m.get("followers") or 0) > max_f:
                continue
            rows.append(i)
        return rows

    # ------------------------------------------------------------------ #
    # Introspection
    # ------------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self._ids)

    def get_metadata(self, influencer_id: str) -> Optional[dict[str, Any]]:
        return self._meta.get(influencer_id)

    def get_vector(self, influencer_id: str) -> Optional[np.ndarray]:
        """Return the stored (normalized) embedding for a creator, or None.

        Lets callers reuse the embedding computed at ingest instead of re-running
        the (CPU-expensive) encoder at serve time.
        """
        pos = self._pos.get(influencer_id)
        if pos is None or pos >= len(self._vectors):
            return None
        return self._vectors[pos]

    def reset(self) -> None:
        """Wipe in-memory + on-disk state (handy for tests / re-seeding)."""
        self._ids, self._pos, self._meta = [], {}, {}
        self._vectors = np.zeros((0, self.dim), dtype=np.float32)
        self._index = faiss.IndexFlatIP(self.dim)
        for p in (self._index_path, self._meta_path, self.dir / f"{config.VECTOR_COLLECTION}.vectors.npy"):
            if p.exists():
                p.unlink()

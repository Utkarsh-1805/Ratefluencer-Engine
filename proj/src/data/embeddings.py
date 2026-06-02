"""Embedding helper — shared by feature-engineering and brand-matching.

Wraps sentence-transformers ``all-MiniLM-L6-v2`` (384-dim) with:
  * lazy, cached model loading (downloaded once, then offline),
  * a deterministic **offline fallback** encoder so the pipeline + tests run
    even when the model can't be downloaded (no network on the box).

The fallback is a seeded hashing encoder: same text -> same 384-dim vector,
different texts -> different vectors. It is NOT semantically meaningful, so the
real model is strongly preferred for the demo; the fallback only guarantees the
pipeline never hard-fails offline (an explicit project requirement).

Call ``embed_texts([...])`` -> np.ndarray (n, 384).
"""
from __future__ import annotations

import hashlib
from typing import Optional

import numpy as np

import config

_MODEL = None
_USING_FALLBACK = False


def _load_model():
    global _MODEL, _USING_FALLBACK
    if _MODEL is not None or _USING_FALLBACK:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer

        _MODEL = SentenceTransformer(config.EMBED_MODEL)
    except Exception:
        # No network / package missing -> deterministic fallback.
        _USING_FALLBACK = True
        _MODEL = None
    return _MODEL


def using_fallback() -> bool:
    """True if embeddings are coming from the deterministic offline fallback."""
    _load_model()
    return _USING_FALLBACK


def _fallback_embed(texts: list[str]) -> np.ndarray:
    """Deterministic hashing encoder -> unit vectors in R^384."""
    out = np.zeros((len(texts), config.EMBED_DIM), dtype=np.float32)
    for i, t in enumerate(texts):
        # Seed a per-text RNG from a stable hash of the text.
        h = hashlib.sha256((t or "").encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "little")
        rng = np.random.default_rng(seed)
        v = rng.standard_normal(config.EMBED_DIM).astype(np.float32)
        n = np.linalg.norm(v)
        out[i] = v / n if n else v
    return out


def embed_texts(texts: list[str], normalize: bool = True) -> np.ndarray:
    """Embed a list of strings to a (n, 384) float32 array."""
    if not texts:
        return np.zeros((0, config.EMBED_DIM), dtype=np.float32)
    model = _load_model()
    if model is None:  # fallback
        vecs = _fallback_embed(texts)
    else:
        vecs = np.asarray(
            model.encode(texts, normalize_embeddings=False, show_progress_bar=False),
            dtype=np.float32,
        )
    if normalize:
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vecs = vecs / norms
    return vecs


_EMBED_CACHE: dict[tuple[str, bool], np.ndarray] = {}
_EMBED_CACHE_MAX = 4096


def embed_text(text: str, normalize: bool = True) -> np.ndarray:
    """Embed a single string -> (384,) float32 vector.

    Memoized: the same text returns the cached vector instead of re-running the
    (CPU-expensive) MiniLM forward pass. This matters a lot when scoring many
    creators against ONE brief — the brief text and each creator's text are
    embedded once, not once per model call. Deterministic, so caching is safe.
    """
    key = (text or "", normalize)
    cached = _EMBED_CACHE.get(key)
    if cached is not None:
        return cached
    vec = embed_texts([text], normalize=normalize)[0]
    if len(_EMBED_CACHE) < _EMBED_CACHE_MAX:
        _EMBED_CACHE[key] = vec
    return vec


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (safe for zero vectors)."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

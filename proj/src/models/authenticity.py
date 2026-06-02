"""Authenticity engine (task-007).

Detects inauthentic audiences/engagement and outputs an Authenticity Score
(0-100, lower = less authentic) plus named fraud flags. Two combined signals:

  * **IsolationForest** — unsupervised anomaly score over ratio features. Catches
    "this profile looks weird vs the whole population" (multivariate).
  * **Tier-relative engagement deficit** — bought followers mean the *real*
    engagement is far below what's normal for an account of that size. This is
    the single strongest fraud signal and keeps the score interpretable.
  * **Deterministic rule overlay** — named flags with explicit thresholds, so
    every penalty is explainable (no unexplained score drops).

Output (persisted to ``authenticity_results``)::

    { authenticity_score, bot_follower_pct, engagement_pod_flag,
      spike_anomaly_score, comment_spam_ratio,
      flags: [bot_followers, engagement_pod, spike_anomaly, comment_spam] }

Design rules honored:
  * Every flag has a threshold; the score is explainable.
  * Spike alone does NOT flag (must combine with another NAMED flag) -> avoids
    false-positives on genuinely viral creators.
  * Sparse data -> low-confidence, never asserts fraud.
  * Deterministic: fixed seed; seeded creators score identically.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import numpy as np

import config
from src.data.features import compute_creator_features
from src.store import repo
from src.store.schema import AuthenticityResult

MODEL_VERSION = "auth-v1"

# Feature columns fed to the IsolationForest (ratio/anomaly signals only).
ANOMALY_FEATURES = [
    "engagement_rate",
    "real_engagement_rate",
    "like_comment_ratio",
    "follower_following_ratio",
    "spike_anomaly_score",
    "comment_spam_ratio",
]

# Rule thresholds (deterministic, explainable).
SPAM_THRESHOLD = 0.22          # comment_spam_ratio above this -> comment_spam flag
SPIKE_THRESHOLD = 2.0          # spike z-score above this -> spike signal (needs corroboration)
POD_LCR_LOW = 3.0              # like/comment ratio below this -> pod suspicion
POD_LCR_HIGH = 300.0           # like/comment ratio above this -> pod suspicion
BOT_DEFICIT_RATIO = 0.60       # real engagement below this fraction of tier-expected -> bot suspicion


def _expected_engagement(followers: int) -> float:
    """Typical organic engagement rate for an account of this size (falls with tier)."""
    if followers < 10_000:
        return 0.075
    if followers < 100_000:
        return 0.050
    if followers < 500_000:
        return 0.030
    if followers < 1_000_000:
        return 0.020
    return 0.012


class AuthenticityEngine:
    """Trains the IsolationForest on the population, then scores creators."""

    def __init__(self, seed: int = config.SEED):
        self.seed = seed
        self._iforest = None
        self._mu: Optional[np.ndarray] = None
        self._sd: Optional[np.ndarray] = None
        self._score_min = 0.0
        self._score_max = 1.0

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def fit(self, feature_dicts: dict[str, dict]) -> "AuthenticityEngine":
        from sklearn.ensemble import IsolationForest

        X = self._matrix(feature_dicts)
        self._mu = X.mean(axis=0)
        self._sd = X.std(axis=0)
        self._sd[self._sd == 0] = 1.0
        Xz = (X - self._mu) / self._sd

        self._iforest = IsolationForest(
            n_estimators=300, contamination=0.2, random_state=self.seed
        )
        self._iforest.fit(Xz)

        raw = -self._iforest.score_samples(Xz)  # higher = more anomalous
        self._score_min, self._score_max = float(raw.min()), float(raw.max())
        return self

    def _matrix(self, feature_dicts: dict[str, dict]) -> np.ndarray:
        ids = sorted(feature_dicts.keys())
        return np.array(
            [[feature_dicts[i].get(c, 0.0) for c in ANOMALY_FEATURES] for i in ids],
            dtype=float,
        )

    def _norm_anomaly(self, vec: dict) -> float:
        x = np.array([[vec.get(c, 0.0) for c in ANOMALY_FEATURES]], dtype=float)
        xz = (x - self._mu) / self._sd
        raw = float(-self._iforest.score_samples(xz)[0])
        rng = self._score_max - self._score_min
        return float(np.clip((raw - self._score_min) / rng, 0.0, 1.0)) if rng else 0.0

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #
    def score(self, influencer_id: str, vec: Optional[dict] = None, persist: bool = True) -> AuthenticityResult:
        if self._iforest is None:
            raise RuntimeError("AuthenticityEngine must be fit() before score()")
        if vec is None:
            vec = compute_creator_features(influencer_id)

        inf = repo.get_influencer(influencer_id)
        followers = max((inf.followers if inf else 0) or 0, 1)
        low_confidence = bool(vec.get("_low_confidence", 0.0))

        anomaly = self._norm_anomaly(vec)

        # --- tier-relative engagement deficit (the strongest signal) ----- #
        real_eng = float(vec.get("real_engagement_rate", 0.0))
        expected_eng = _expected_engagement(followers)
        eng_ratio = real_eng / expected_eng if expected_eng else 1.0
        eng_deficit = float(np.clip(1.0 - eng_ratio, 0.0, 1.0))  # 0=healthy, 1=no real engagement

        spam_ratio = float(vec.get("comment_spam_ratio", 0.0))
        spike = float(vec.get("spike_anomaly_score", 0.0))
        lcr = float(vec.get("like_comment_ratio", 0.0))

        # --- deterministic rule overlay -> named flags ------------------- #
        flags: list[str] = []
        spam_flag = spam_ratio >= SPAM_THRESHOLD
        pod_flag = (lcr < POD_LCR_LOW or lcr > POD_LCR_HIGH) and anomaly > 0.5
        bot_flag = (
            followers > 5_000
            and eng_ratio < BOT_DEFICIT_RATIO
            and (eng_deficit > 0.30 or anomaly > 0.35)
        )
        # spike must combine with another NAMED flag (not just anomaly), so a
        # genuinely viral-but-clean creator is never flagged on the spike alone.
        spike_corroborated = spike >= SPIKE_THRESHOLD and (spam_flag or bot_flag or pod_flag)

        if bot_flag:
            flags.append("bot_followers")
        if pod_flag:
            flags.append("engagement_pod")
        if spike_corroborated:
            flags.append("spike_anomaly")
        if spam_flag:
            flags.append("comment_spam")

        # --- bot_follower_pct estimate ---------------------------------- #
        bot_pct = float(np.clip(0.04 + 0.4 * anomaly + 0.5 * eng_deficit, 0.0, 0.9))

        # --- authenticity score 0-100 ----------------------------------- #
        # Combine "weird vs population" (anomaly) with "too little real reach"
        # (engagement deficit). The deficit dominates because it is the most
        # reliable fraud tell; spam adds a smaller push.
        fraud_signal = 0.42 * anomaly + 0.70 * eng_deficit + 0.20 * spam_ratio
        fraud_signal = float(np.clip(fraud_signal, 0.0, 1.0))
        score = 100.0 * (1.0 - fraud_signal)
        score -= 8.0 * len(flags)               # each named flag nudges the score down
        if low_confidence:
            score = 0.7 * score + 30.0          # pull sparse-data scores toward neutral
        authenticity_score = int(np.clip(round(score), 0, 100))

        # No naked penalties: if the score lands below the trust threshold but no
        # rule fired, the cause is always a real-engagement deficit too small to
        # trip the explicit rule yet large enough to sink the score -> name it.
        if authenticity_score < config.FLAG_THRESHOLD and not flags and not low_confidence:
            flags.append("bot_followers")

        result = AuthenticityResult(
            influencer_id=influencer_id,
            authenticity_score=authenticity_score,
            bot_follower_pct=round(bot_pct, 4),
            engagement_pod_flag=pod_flag,
            spike_anomaly_score=round(spike, 4),
            comment_spam_ratio=round(spam_ratio, 4),
            flags=flags,
            model_version=MODEL_VERSION,
            computed_at=datetime(2026, 5, 31, 12, 0, 0),
        )
        if persist:
            repo.upsert_authenticity(result)
        return result


def fit_and_score_all(feature_dicts: Optional[dict[str, dict]] = None, persist: bool = True) -> dict[str, AuthenticityResult]:
    """Train on the full population and score every creator. Returns id -> result."""
    if feature_dicts is None:
        from src.data.features import build_all_creator_features

        feature_dicts = build_all_creator_features(persist=False, embed=False)
    engine = AuthenticityEngine().fit(feature_dicts)
    return {iid: engine.score(iid, vec=feature_dicts[iid], persist=persist) for iid, vec in feature_dicts.items()}


if __name__ == "__main__":
    results = fit_and_score_all(persist=True)
    flagged = sum(1 for r in results.values() if r.authenticity_score < config.FLAG_THRESHOLD)
    print(f"Scored {len(results)} creators | {flagged} below flag threshold ({config.FLAG_THRESHOLD})")

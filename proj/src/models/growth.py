"""Growth Potential model (task-019, optional P1).

Predicts a creator's near-term growth as a Growth Potential Score (0-100) so the
shortlist can surface *rising* creators worth signing cheap. This is a secondary,
forward-looking lever — it is **not** part of the True-Impact spine and never
feeds back into it, so enabling/disabling it cannot move the core ranking.

Why a momentum model (not a trained forecaster)
-----------------------------------------------
The synthetic labels are ``roi``/``success``/``is_fraud`` — there is **no
future-follower label** to train a supervised forecaster against. Inventing one
would be dishonest and add risk for an optional feature. The spec explicitly
permits "a simple slope/momentum model", so we estimate growth directly from the
``metrics_snapshot`` time series. It is fully deterministic and interpretable.

The signal blends four documented effects::

    raw = (recent_slope + acceleration) x tier_headroom x authenticity_discount

  * recent_slope    — least-squares slope of the (smoothed) recent follower
    series, projected over the 30-day horizon as a fraction of the base.
  * acceleration    — is 30-day growth outpacing the 90-day trend? (rising vs
    plateauing).
  * tier_headroom   — big accounts saturate; a nano has far more room to grow
    than a mega. Decays with log-followers.
  * authenticity_discount — bought followers / spike anomalies are NOT organic
    growth, so inflated "growth" is discounted. This is what keeps the famous
    fraud account from scoring as a great growth pick.

Output (per creator)::

    { growth_potential_score: 0-100, trend: rising|steady|declining,
      horizon_days: 30, confidence: high|low }

Edge cases honored (spec):
  * short / sparse history -> low confidence, score pulled toward neutral-low
    (never over-claims),
  * already-huge creators -> naturally low (headroom term),
  * volatile series -> smoothed before the slope is taken,
  * deterministic: seeded creators score identically every run.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

import config
from src.data.features import compute_creator_features
from src.store import repo

MODEL_VERSION = "growth-v1"

# --- tunables (deterministic thresholds) ----------------------------------- #
MIN_SNAPSHOTS = 4          # fewer than this -> low confidence
RECENT_POINTS = 5          # snapshots used for the recent-slope window (~35d)
SNAPSHOT_STEP_DAYS = 7     # weekly cadence of the synthetic series
SAT_FLOOR_FOLLOWERS = 1_000        # full headroom at/below this
SAT_CAP_FOLLOWERS = 5_000_000      # ~no headroom at/above this
RISING_RATE = 0.04         # projected horizon growth >= this -> "rising"
DECLINING_RATE = -0.02     # <= this -> "declining"
LOW_CONF_CAP = 50          # low-confidence scores can't exceed this (no over-claim)


def _moving_avg(x: np.ndarray, w: int = 3) -> np.ndarray:
    """Light smoothing to tame volatile series before taking a slope.

    Edges are replicated (not zero-padded) so the most-recent value — exactly
    where the slope is measured — is not dragged toward zero.
    """
    if len(x) < w:
        return x.astype(float)
    pad = w // 2
    xp = np.pad(x.astype(float), pad, mode="edge")
    return np.convolve(xp, np.ones(w) / w, mode="valid")


def _headroom(followers: int) -> float:
    """Tier saturation factor in [0.1, 1.0]; shrinks as followers grow (log scale)."""
    f = max(int(followers), 1)
    lo, hi = np.log10(SAT_FLOOR_FOLLOWERS), np.log10(SAT_CAP_FOLLOWERS)
    frac = (np.log10(f) - lo) / (hi - lo)
    return float(np.clip(1.0 - frac, 0.1, 1.0))


class GrowthModel:
    """Momentum/slope forecaster over the follower time series, calibrated 0-100."""

    def __init__(self, seed: int = config.SEED, horizon_days: int = config.GROWTH_HORIZON_DAYS):
        self.seed = seed
        self.horizon_days = horizon_days
        # raw-signal -> score calibration (robust percentiles of the population).
        self._raw_lo = 0.0
        self._raw_hi = 1.0
        self._fitted = False

    # ------------------------------------------------------------------ #
    # Core signal
    # ------------------------------------------------------------------ #
    def _authenticity_factor(self, influencer_id: str, vec: dict) -> float:
        """Share of followers that are genuine. Prefer the authenticity result;
        fall back to the real/observed engagement ratio in the feature vector."""
        auth = repo.get_authenticity(influencer_id)
        if auth is not None and auth.bot_follower_pct is not None:
            return float(np.clip(1.0 - auth.bot_follower_pct, 0.05, 1.0))
        er = float(vec.get("engagement_rate", 0.0))
        rer = float(vec.get("real_engagement_rate", 0.0))
        return float(np.clip(rer / er, 0.05, 1.0)) if er > 0 else 0.8

    def _proj_slope(self, series: np.ndarray) -> float:
        """Project the recent linear slope of a series over the horizon, as a
        fraction of the recent mean. Works for any trajectory — follower counts
        OR per-snapshot average engagement — so the same logic gives us both
        follower growth and engagement growth."""
        n = len(series)
        if n < 2:
            return 0.0
        seg = series[-min(RECENT_POINTS, n):]
        x = np.arange(len(seg), dtype=float)
        slope = float(np.polyfit(x, seg, 1)[0])  # units per weekly step
        base = max(float(np.mean(seg)), 1e-9)
        steps = self.horizon_days / SNAPSHOT_STEP_DAYS
        return slope * steps / base

    def _raw_signal(self, influencer_id: str, vec: Optional[dict] = None):
        """Return (raw_signal, trend, low_confidence, parts) for one creator.

        ``parts`` carries the three forward-looking sub-signals the spec asks a
        growth engine to predict, each a projected horizon fraction:
          * follower_growth   — slope of the (smoothed) follower series,
          * engagement_growth — slope of the per-snapshot average-engagement series,
          * audience_expansion — net new *real* followers (follower growth net of
            the bot share), i.e. is the genuine audience actually expanding.
        """
        if vec is None:
            vec = compute_creator_features(influencer_id)
        inf = repo.get_influencer(influencer_id)
        followers = max((inf.followers if inf else 0) or 0, 1)
        metrics = sorted(repo.get_metrics(influencer_id), key=lambda m: m.date)

        low_conf = len(metrics) < MIN_SNAPSHOTS
        f = np.array([m.followers or 0 for m in metrics], dtype=float)
        e = np.array([m.avg_engagement or 0.0 for m in metrics], dtype=float)
        fs = _moving_avg(f, w=3) if len(f) >= 3 else f
        es = _moving_avg(e, w=3) if len(e) >= 3 else e

        # --- the three required sub-signals -------------------------------- #
        follower_growth = self._proj_slope(fs)
        engagement_growth = self._proj_slope(es)
        authenticity_factor = self._authenticity_factor(influencer_id, vec)
        # audience expansion = growth that is actually *real* audience, not bots.
        audience_expansion = follower_growth * authenticity_factor

        # acceleration: is the 30d pace beating a third of the 90d trend?
        g30 = float(vec.get("growth_rate_30d", 0.0))
        g90 = float(vec.get("growth_rate_90d", 0.0))
        accel = g30 - g90 / 3.0

        # Blend the three sub-signals (+ acceleration) into one momentum number.
        blended = (
            0.40 * follower_growth
            + 0.25 * engagement_growth
            + 0.20 * audience_expansion
            + 0.15 * accel
        )

        headroom = _headroom(followers)
        spike = float(vec.get("spike_anomaly_score", 0.0))
        spike_discount = float(np.clip(1.0 - 0.5 * np.clip(spike / 4.0, 0.0, 1.0), 0.3, 1.0))
        raw = blended * headroom * (authenticity_factor * spike_discount)

        if follower_growth >= RISING_RATE:
            trend = "rising"
        elif follower_growth <= DECLINING_RATE:
            trend = "declining"
        else:
            trend = "steady"

        parts = {
            "follower_growth": round(follower_growth, 4),
            "engagement_growth": round(engagement_growth, 4),
            "audience_expansion": round(audience_expansion, 4),
        }
        return float(raw), trend, bool(low_conf), parts

    # ------------------------------------------------------------------ #
    # Fit (calibration) + score
    # ------------------------------------------------------------------ #
    def fit(self, ids: Optional[list[str]] = None) -> "GrowthModel":
        """Calibrate the raw-signal -> 0-100 mapping on the population (5th-95th pct)."""
        if ids is None:
            ids = [c.influencer_id for c in repo.list_candidates()]
        raws = [self._raw_signal(iid)[0] for iid in ids]
        if raws:
            self._raw_lo = float(np.percentile(raws, 5))
            self._raw_hi = float(np.percentile(raws, 95))
            if self._raw_hi <= self._raw_lo:
                self._raw_hi = self._raw_lo + 1e-6
        self._fitted = True
        return self

    def score(self, influencer_id: str, vec: Optional[dict] = None) -> dict:
        """Return the growth result dict for one creator (score + sub-signals)."""
        raw, trend, low_conf, parts = self._raw_signal(influencer_id, vec)
        frac = float(np.clip((raw - self._raw_lo) / (self._raw_hi - self._raw_lo), 0.0, 1.0))
        score = 100.0 * frac
        if low_conf:
            # don't over-claim on thin history: pull toward neutral-low and cap.
            score = min(0.6 * score + 0.4 * 30.0, float(LOW_CONF_CAP))
        return {
            "growth_potential_score": int(np.clip(round(score), 0, 100)),
            "trend": trend,
            "horizon_days": self.horizon_days,
            "confidence": "low" if low_conf else "high",
            # the three forward-looking predictions the spec asks for:
            "follower_growth": parts["follower_growth"],
            "engagement_growth": parts["engagement_growth"],
            "audience_expansion": parts["audience_expansion"],
        }

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: Optional[Path] = None) -> Path:
        config.ensure_dirs()
        path = Path(path or config.MODELS_DIR / "growth.pkl")
        with open(path, "wb") as f:
            pickle.dump(self, f)
        return path

    @staticmethod
    def load(path: Optional[Path] = None) -> "GrowthModel":
        path = Path(path or config.MODELS_DIR / "growth.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def predict_growth(influencer_id: str, model: Optional[GrowthModel] = None) -> dict:
    """Agent/ranking tool entry point: returns the growth result for one creator.

    Loads the saved calibrated model; if none exists yet, calibrates on the
    current population on the fly (cheap — no ML training, just percentiles).
    """
    if model is None:
        try:
            model = GrowthModel.load()
        except (FileNotFoundError, OSError):
            model = GrowthModel().fit()
    return model.score(influencer_id)


def fit_and_score_all(persist_brief_id: Optional[str] = None, save_model: bool = False) -> dict[str, dict]:
    """Calibrate on the full population and score every creator. Returns id -> result.

    If ``persist_brief_id`` is given, the growth score is written into the matching
    existing ``scores`` rows (only that column is touched — see ``persist_growth``).
    """
    ids = [c.influencer_id for c in repo.list_candidates()]
    model = GrowthModel().fit(ids)
    if save_model:
        model.save()
    results = {iid: model.score(iid) for iid in ids}
    if persist_brief_id is not None:
        persist_growth(persist_brief_id, results)
    return results


def persist_growth(brief_id: str, results: dict[str, dict]) -> int:
    """Write growth_potential_score into EXISTING scores rows for this brief only.

    Growth is brief-independent, but it lives in the brief-keyed ``scores`` table
    (filled in by ranking). To avoid clobbering other score fields, this updates
    only the one column on rows the ranking step has already created. Returns the
    number of rows updated.
    """
    conn = repo.get_connection()
    updated = 0
    for iid, res in results.items():
        cur = conn.execute(
            "UPDATE scores SET growth_potential_score=? WHERE brief_id=? AND influencer_id=?",
            (int(res["growth_potential_score"]), brief_id, iid),
        )
        updated += cur.rowcount
    conn.commit()
    return updated


if __name__ == "__main__":
    if not config.ENABLE_GROWTH:
        print("Growth scoring is disabled (config.ENABLE_GROWTH=False). "
              "Set RATEFLUENCER_ENABLE_GROWTH=1 to enable in the pipeline.")
    results = fit_and_score_all(save_model=True)
    rising = sum(1 for r in results.values() if r["trend"] == "rising")
    print(f"Scored {len(results)} creators | {rising} rising | model saved to "
          f"{config.MODELS_DIR / 'growth.pkl'}")

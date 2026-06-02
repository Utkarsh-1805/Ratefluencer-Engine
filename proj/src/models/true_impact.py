"""True-Impact model (task-008) — the spine.

Predicts a creator's business impact for a brief:
  * **predicted_roi**     — LightGBM regressor on the fraud-adjusted feature vector
  * **success_prob**      — LightGBM classifier (calibrated) for P(roi > threshold)
  * **true_impact_score** — calibrated 0-100 blend of the two

Training data = the synthetic labeled set (task-003/004). The model consumes the
*fraud-adjusted* features from feature-engineering (so authenticity is baked in:
high followers + low authenticity => low fraud_adjusted_reach => low impact).

Determinism: fixed seeds everywhere; seeded creators score identically. Models
persist to ``MODELS_DIR`` for fast load (``@st.cache_resource`` in the app).
The agent tool entry point is ``predict_true_impact(influencer_id, brief)``.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np

import config
from src.data.features import IMPACT_FEATURES, FIT_FEATURES, compute_creator_features, compute_fit_features
from src.store import repo
from src.store.schema import BrandBrief

MODEL_VERSION = "impact-v1"
# Model input = brief-independent impact features + per-brief fit features.
MODEL_FEATURES = IMPACT_FEATURES + FIT_FEATURES


class TrueImpactModel:
    """LightGBM regressor (ROI) + calibrated classifier (success), blended to 0-100."""

    def __init__(self, seed: int = config.SEED):
        self.seed = seed
        self.regressor = None
        self.classifier = None          # calibrated classifier
        self.columns = list(MODEL_FEATURES)
        # ROI -> score mapping calibrated on training ROI distribution.
        self._roi_lo = 0.0
        self._roi_hi = 1.0

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    def fit(self, X: np.ndarray, roi: np.ndarray, success: np.ndarray) -> "TrueImpactModel":
        import lightgbm as lgb
        from sklearn.calibration import CalibratedClassifierCV

        reg_params = dict(
            n_estimators=300, learning_rate=0.05, num_leaves=31,
            subsample=0.8, colsample_bytree=0.8, random_state=self.seed,
            min_child_samples=20, verbose=-1,
        )
        self.regressor = lgb.LGBMRegressor(**reg_params)
        self.regressor.fit(X, roi)

        clf_params = dict(reg_params)
        base = lgb.LGBMClassifier(**clf_params)
        # Calibrate probabilities (isotonic) so success_prob is meaningful.
        n_pos = int(success.sum())
        n_neg = int(len(success) - n_pos)
        cv = min(3, max(2, min(n_pos, n_neg)))
        if min(n_pos, n_neg) >= cv:
            self.classifier = CalibratedClassifierCV(base, method="isotonic", cv=cv)
            self.classifier.fit(X, success)
        else:  # degenerate label balance -> fall back to uncalibrated
            base.fit(X, success)
            self.classifier = base

        # Calibrate ROI->score range on the training ROI (robust percentiles).
        self._roi_lo = float(np.percentile(roi, 5))
        self._roi_hi = float(np.percentile(roi, 95))
        if self._roi_hi <= self._roi_lo:
            self._roi_hi = self._roi_lo + 1.0
        return self

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #
    def _row(self, vec: dict) -> np.ndarray:
        return np.array([[vec.get(c, 0.0) for c in self.columns]], dtype=float)

    def predict_roi(self, X: np.ndarray) -> np.ndarray:
        return self.regressor.predict(X)

    def predict_success(self, X: np.ndarray) -> np.ndarray:
        if hasattr(self.classifier, "predict_proba"):
            return self.classifier.predict_proba(X)[:, 1]
        return self.classifier.predict(X).astype(float)

    def _roi_norm(self, roi_pred: float) -> float:
        """Map predicted ROI to a 0..1 score fraction.

        Default "absolute" mode interpolates fixed business-meaningful ROI anchors
        (config.ROI_SCORE_ANCHORS), so a given ROI always earns the same score
        regardless of the surrounding population — a genuinely profitable creator
        reads green by design, not by luck. "percentile" mode keeps the legacy
        population-relative normalization.
        """
        if getattr(config, "IMPACT_CALIBRATION", "absolute") == "percentile":
            return float(np.clip((roi_pred - self._roi_lo) / (self._roi_hi - self._roi_lo), 0.0, 1.0))
        xs = [a for a, _ in config.ROI_SCORE_ANCHORS]
        ys = [b for _, b in config.ROI_SCORE_ANCHORS]
        return float(np.clip(np.interp(roi_pred, xs, ys), 0.0, 1.0))

    def impact_score(self, roi_pred: float, success_prob: float) -> int:
        """Blend predicted ROI (calibrated) + success prob into 0-100."""
        roi_norm = self._roi_norm(roi_pred)
        blended = 0.6 * roi_norm + 0.4 * float(np.clip(success_prob, 0.0, 1.0))
        return int(np.clip(round(blended * 100), 0, 100))

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #
    def save(self, path: Optional[Path] = None) -> Path:
        config.ensure_dirs()
        path = Path(path or config.MODELS_DIR / "true_impact.pkl")
        with open(path, "wb") as f:
            pickle.dump(self, f)
        return path

    @staticmethod
    def load(path: Optional[Path] = None) -> "TrueImpactModel":
        path = Path(path or config.MODELS_DIR / "true_impact.pkl")
        with open(path, "rb") as f:
            return pickle.load(f)


# --------------------------------------------------------------------------- #
# Training entry point helpers
# --------------------------------------------------------------------------- #
def build_training_matrix(labels: list[dict], brief: BrandBrief, feature_dicts: dict[str, dict]):
    """Assemble (ids, X, roi, success) for training from labels + features + brief.

    Each creator's row = brief-independent features + fit features vs the training
    brief. Returns numpy arrays aligned by sorted id order.
    """
    ids = sorted(feature_dicts.keys())
    rows, roi, success, kept = [], [], [], []
    label_by_id = {l["influencer_id"]: l for l in labels}
    for iid in ids:
        if iid not in label_by_id:
            continue
        vec = dict(feature_dicts[iid])
        vec.update(compute_fit_features(iid, brief, None))
        rows.append([vec.get(c, 0.0) for c in MODEL_FEATURES])
        roi.append(label_by_id[iid]["roi"])
        success.append(label_by_id[iid]["success"])
        kept.append(iid)
    return kept, np.array(rows, dtype=float), np.array(roi, dtype=float), np.array(success, dtype=float)


def predict_true_impact(influencer_id: str, brief: BrandBrief, model: Optional[TrueImpactModel] = None) -> dict:
    """Agent tool entry point: returns score/ROI/prob (drivers added by explainability)."""
    model = model or TrueImpactModel.load()
    vec = compute_creator_features(influencer_id)
    vec.update(compute_fit_features(influencer_id, brief))
    X = model._row(vec)
    roi_pred = float(model.predict_roi(X)[0])
    success_prob = float(model.predict_success(X)[0])
    return {
        "true_impact_score": model.impact_score(roi_pred, success_prob),
        "predicted_roi": round(roi_pred, 4),
        "success_prob": round(success_prob, 4),
    }

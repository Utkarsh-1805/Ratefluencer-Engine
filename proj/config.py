"""Global configuration: seeds, paths, thresholds, and shared constants.

Single source of truth for everything deterministic and path-related. Every
module imports from here so the pipeline runs identically on a laptop and on
Kaggle (paths are overridable via environment variables).

Kaggle note
-----------
Set these env vars in a Kaggle notebook cell *before* importing anything else
to redirect storage into the writable working dir:

    import os
    os.environ["RATEFLUENCER_DATA_DIR"]   = "/kaggle/working/data"
    os.environ["RATEFLUENCER_MODELS_DIR"] = "/kaggle/working/models"
"""
from __future__ import annotations

import os
import random
from pathlib import Path

# --------------------------------------------------------------------------- #
# Reproducibility
# --------------------------------------------------------------------------- #
SEED: int = 42


def seed_everything(seed: int = SEED) -> None:
    """Seed every RNG we rely on. Call once at the start of any entry point."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        # numpy not installed yet (e.g. running only the store smoke test)
        pass


# --------------------------------------------------------------------------- #
# Paths  (all overridable via env vars for Kaggle / CI)
# --------------------------------------------------------------------------- #
BASE_DIR: Path = Path(__file__).resolve().parent  # the proj/ folder

DATA_DIR: Path = Path(os.environ.get("RATEFLUENCER_DATA_DIR", BASE_DIR / "data"))
REAL_DIR: Path = DATA_DIR / "real"
SYNTHETIC_DIR: Path = DATA_DIR / "synthetic"
SEED_DIR: Path = DATA_DIR / "seed"
VECTOR_DIR: Path = DATA_DIR / "vector"

MODELS_DIR: Path = Path(os.environ.get("RATEFLUENCER_MODELS_DIR", BASE_DIR / "models_store"))

DB_PATH: Path = Path(os.environ.get("RATEFLUENCER_DB", DATA_DIR / "ratefluencer.db"))


def ensure_dirs() -> None:
    """Create every storage directory if it does not exist (idempotent)."""
    for d in (DATA_DIR, REAL_DIR, SYNTHETIC_DIR, SEED_DIR, VECTOR_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Thresholds & weights
# --------------------------------------------------------------------------- #
# Authenticity score (0-100) strictly below this => creator is "flagged" and
# suppressed in ranking (see ranking-recommendation spec).
FLAG_THRESHOLD: int = 50

# Score band cutoffs for the red->amber->green gradient used on cards.
#   >= GREEN_THRESHOLD : green  (a clear "recommend")
#   >= FLAG_THRESHOLD  : amber  (viable but watch)
#   <  FLAG_THRESHOLD  : red    (avoid / flagged)
# 60 = "clearly profitable" cutoff: a creator predicted to return well above
# break-even with clean signals is a recommend. (Display-only; never changes a
# model score.)
GREEN_THRESHOLD: int = 60

# ROI above this multiple => success label = 1 (synthetic-data-generator).
ROI_SUCCESS_THRESHOLD: float = 1.0

# --- True-Impact score calibration ----------------------------------------- #
# How predicted ROI maps to the 0-100 impact score.
#   "absolute"   -> fixed, business-meaningful ROI anchors (below). A creator's
#                   score reflects whether its ROI is objectively good, not its
#                   rank within whatever population happened to be generated.
#                   Defensible to judges ("4x ROI is good, full stop") and stable
#                   across dataset sizes.
#   "percentile" -> legacy: normalize ROI to the training set's 5th-95th pct
#                   (population-relative; drifts as the population changes).
IMPACT_CALIBRATION: str = os.environ.get("RATEFLUENCER_IMPACT_CALIBRATION", "absolute")
# Piecewise-linear anchors: (predicted_ROI multiple -> score fraction 0..1).
# 1.0x = break-even (floor of "viable"); ~6.6x = industry-benchmark "excellent".
ROI_SCORE_ANCHORS: tuple[tuple[float, float], ...] = (
    (0.0, 0.00),   # loses money
    (1.0, 0.25),   # break-even -> bottom of amber
    (3.0, 0.55),   # solid, profitable -> green begins (>=0.50)
    (6.6, 0.85),   # industry-benchmark return -> strong green
    (12.0, 1.00),  # exceptional
)

# --- Growth Potential (task-019, optional P1) ------------------------------ #
# Off by default: growth is a secondary, forward-looking lever and is NOT part
# of the True-Impact spine. Enable in the pipeline via RATEFLUENCER_ENABLE_GROWTH=1.
ENABLE_GROWTH: bool = os.environ.get("RATEFLUENCER_ENABLE_GROWTH", "0") == "1"
GROWTH_HORIZON_DAYS: int = 30          # forecast horizon for the growth score
GROWTH_RANK_WEIGHT: float = 0.05       # optional small weight if ranking opts in

# Default objective weights when the brief/agent does not supply them.
DEFAULT_OBJECTIVE_WEIGHTS: dict[str, float] = {
    "impact": 0.45,
    "authenticity": 0.30,
    "match": 0.20,
    "cost": 0.05,
}

DEFAULT_CURRENCY: str = "INR"

# --------------------------------------------------------------------------- #
# Embeddings / vector store
# --------------------------------------------------------------------------- #
EMBED_MODEL: str = "all-MiniLM-L6-v2"
EMBED_DIM: int = 384
VECTOR_COLLECTION: str = "influencer_profiles"

# --------------------------------------------------------------------------- #
# Controlled vocabularies (must match the specs exactly)
# --------------------------------------------------------------------------- #
GOALS: tuple[str, ...] = ("awareness", "engagement", "conversions", "sales")
STATUSES: tuple[str, ...] = ("recommended", "flagged", "excluded")
PLATFORMS: tuple[str, ...] = ("instagram", "youtube", "tiktok")

"""Synthetic data generator (task-003 core).

No public dataset has campaign-outcome labels (conversions / ROI live in brands'
CRMs), so we synthesize a labeled creator population from documented, defensible
relationships. This module produces, for ~2,000 creators:

  * an ``influencers`` row (handle, tier, category, followers, ...),
  * ``post_samples`` (recent posts with engagement),
  * a ``metrics_snapshot`` time series (for spike detection + growth),
  * an ``audience_profile`` (age/gender/geo/interests + quality),
  * ground-truth labels: ``roi``, ``success``, ``is_fraud``, ``bot_pct``.

Generation model (per specs/synthetic-data-generator/spec.md)::

    base_engagement = tier_base_rate * category_effect * authenticity_multiplier + noise
    real_reach      = followers * authenticity_factor
    conversions    ~ f(real_reach, brand_fit, engagement_quality) + noise
    roi             = (conversions * AOV * margin) / cost
    success         = roi > threshold

Fraud is injected during generation (engagement + labels depend on it). The
*calibration to published benchmarks*, ``assumptions.md``, and separability
tuning are finished in task-004; this task establishes the deterministic
pipeline and plausible distributions.

Determinism: everything derives from ``config.SEED``. Same seed => identical
dataset, identical labels, byte-for-byte.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np

import config
from src.store import repo
from src.store.schema import (
    AudienceProfile,
    Influencer,
    MetricsSnapshot,
    PostSample,
)

# --------------------------------------------------------------------------- #
# Population definition
# --------------------------------------------------------------------------- #
# Follower tiers with (min, max) follower bounds and a base engagement rate.
# Engagement rate falls as follower count rises (documented relationship).
@dataclass(frozen=True)
class Tier:
    name: str
    f_min: int
    f_max: int
    base_engagement: float  # fraction of followers engaging on an average post
    weight: float           # share of the population in this tier


TIERS: tuple[Tier, ...] = (
    Tier("nano",   1_000,    10_000,   0.085, 0.34),
    Tier("micro",  10_000,   100_000,  0.060, 0.34),
    Tier("mid",    100_000,  500_000,  0.035, 0.18),
    Tier("macro",  500_000,  1_000_000, 0.022, 0.10),
    Tier("mega",   1_000_000, 5_000_000, 0.013, 0.04),
)

# Content categories with a mild multiplicative effect on engagement and a
# representative average order value (AOV, in INR) used in the ROI label.
@dataclass(frozen=True)
class Category:
    name: str
    engagement_effect: float
    aov: float  # average order value (INR)
    margin: float  # gross margin fraction


CATEGORIES: tuple[Category, ...] = (
    Category("skincare",  1.15, 1200, 0.55),
    Category("fitness",   1.05, 1800, 0.50),
    Category("fashion",   1.00, 2500, 0.45),
    Category("food",      1.10, 600,  0.40),
    Category("tech",      0.85, 8000, 0.30),
    Category("finance",   0.70, 5000, 0.60),
    Category("travel",    0.95, 12000, 0.35),
    Category("beauty",    1.12, 1500, 0.55),
)

REGIONS: tuple[tuple[str, float], ...] = (("IN", 0.6), ("US", 0.2), ("UK", 0.1), ("AE", 0.1))

# --------------------------------------------------------------------------- #
# Calibration benchmarks (task-004)
# --------------------------------------------------------------------------- #
# Published reference points the generator is calibrated to. These are asserted
# (within tolerance) by scripts/calibration_report.py and documented for judges
# in data/synthetic/assumptions.md.
#
# * Engagement-rate-by-tier: typical Instagram organic engagement, which falls
#   as follower count rises (Influencer Marketing Hub / HypeAuditor ranges).
# * Industry ROI: the widely-cited "$6.6 earned per $1 spent" influencer-
#   marketing benchmark — the target *mean ROI for clean, well-matched creators*.
# * Verified status mildly correlates with conversion (small uplift, not large).
BENCHMARKS = {
    "engagement_by_tier": {  # acceptable mean engagement-rate band per tier (clean)
        "nano":  (0.04, 0.10),
        "micro": (0.03, 0.07),
        "mid":   (0.015, 0.045),
        "macro": (0.010, 0.030),
        "mega":  (0.005, 0.020),
    },
    "industry_roi_mean": 6.6,        # clean-creator mean ROI target
    "industry_roi_tolerance": 1.5,   # acceptable absolute deviation around it
    "verified_conversion_uplift": 0.12,  # mild but ROBUST: large enough to stay
                                          # measurable above ROI variance in the thin
                                          # verification-eligible (>100K) segment.
}

# Conversion model coefficients (documented; calibrated so clean-creator mean ROI
# lands on the ~6.6x industry benchmark).
CONVERSION_COEFFICIENT = 0.062      # base conversions per unit (reach x quality x fit)
CONVERSION_NOISE_SD = 0.15

_CAPTION_BITS = [
    "loving this {c} find", "my honest {c} review", "new {c} routine",
    "{c} tips that actually work", "obsessed with this {c} drop",
    "before & after — {c}", "answering your {c} questions", "{c} haul",
]
_SPAM_COMMENTS = ["🔥🔥🔥", "nice", "follow back", "great post", "❤️", "first", "check my page"]


@dataclass
class GenConfig:
    """Knobs for a generation run (all defaulted to the spec targets)."""
    n_creators: int = 2_000
    fraud_fraction: float = 0.20
    posts_per_creator: int = 12
    snapshot_days: int = 90           # length of the metrics time series
    snapshot_step: int = 7            # one snapshot per week
    campaign_cost_per_1k: float = 500.0  # INR cost per 1k real reach (proxy)
    seed: int = config.SEED


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _pick(rng: np.random.Generator, items, weights) -> int:
    return int(rng.choice(len(items), p=np.asarray(weights) / np.sum(weights)))


def _tier_for_followers(followers: int) -> Tier:
    for t in TIERS:
        if t.f_min <= followers <= t.f_max:
            return t
    return TIERS[-1]


# --------------------------------------------------------------------------- #
# Per-creator generation
# --------------------------------------------------------------------------- #
def _make_creator(idx: int, rng: np.random.Generator, gc: GenConfig, force_fraud: Optional[bool] = None):
    """Build one creator + children + labels. Returns a bundle of rows + label dict."""
    influencer_id = f"inf_{idx:04d}"

    tier = TIERS[_pick(rng, TIERS, [t.weight for t in TIERS])]
    category = CATEGORIES[int(rng.integers(len(CATEGORIES)))]
    region = REGIONS[_pick(rng, REGIONS, [w for _, w in REGIONS])][0]

    followers = int(rng.integers(tier.f_min, tier.f_max + 1))
    is_fraud = bool(rng.random() < gc.fraud_fraction) if force_fraud is None else force_fraud

    # --- authenticity ---------------------------------------------------- #
    if is_fraud:
        bot_pct = float(np.clip(rng.normal(0.50, 0.12), 0.25, 0.85))
        followers = int(followers * rng.uniform(1.3, 2.2))  # inflated
        engagement_mult = rng.uniform(0.14, 0.40)           # depressed real engagement
        spam_ratio = float(np.clip(rng.normal(0.37, 0.1), 0.12, 0.8))
    else:
        bot_pct = float(np.clip(rng.normal(0.06, 0.03), 0.0, 0.20))
        engagement_mult = rng.uniform(0.9, 1.15)
        spam_ratio = float(np.clip(rng.normal(0.05, 0.03), 0.0, 0.20))

    authenticity_factor = 1.0 - bot_pct

    # --- engagement ------------------------------------------------------ #
    # base_engagement = tier_base * category_effect * authenticity_mult + noise
    eng_rate = (
        tier.base_engagement
        * category.engagement_effect
        * engagement_mult
        * float(rng.normal(1.0, 0.10))
    )
    eng_rate = float(np.clip(eng_rate, 0.002, 0.30))  # never impossible

    following = int(np.clip(rng.normal(800, 400) * (3 if is_fraud else 1), 50, 50_000))
    post_count = int(rng.integers(40, 1200))
    account_age_days = int(rng.integers(120, 2200))
    account_created = date(2026, 5, 31) - timedelta(days=account_age_days)
    verified = bool(followers > 100_000 and rng.random() < 0.5)

    # --- posts ----------------------------------------------------------- #
    posts: list[PostSample] = []
    base_date = datetime(2026, 5, 31, 12, 0, 0)
    for p in range(gc.posts_per_creator):
        avg_eng = followers * eng_rate
        likes = int(max(0, rng.normal(avg_eng * 0.88, avg_eng * 0.15)))
        comments = int(max(0, rng.normal(avg_eng * 0.07, avg_eng * 0.03)))
        shares = int(max(0, rng.normal(avg_eng * 0.03, avg_eng * 0.02)))
        saves = int(max(0, rng.normal(avg_eng * 0.05, avg_eng * 0.03)))
        views = int(followers * rng.uniform(0.6, 1.4))
        caption = rng.choice(_CAPTION_BITS).format(c=category.name)
        media = rng.choice(["image", "reel", "carousel"])
        posts.append(
            PostSample(
                post_id=f"{influencer_id}_p{p:02d}",
                influencer_id=influencer_id,
                posted_at=base_date - timedelta(days=p * 4),
                likes=likes, comments=comments, shares=shares, saves=saves, views=views,
                caption=caption, media_type=str(media),
            )
        )

    # --- metrics snapshots (time series) --------------------------------- #
    snapshots: list[MetricsSnapshot] = []
    # growth trend: fraud accounts get a sharp spike; clean accounts drift.
    growth = rng.uniform(-0.05, 0.25)  # net 90d growth fraction
    n_steps = gc.snapshot_days // gc.snapshot_step
    start_followers = int(followers / (1.0 + max(growth, 0.0) + 0.001))
    spike_step = int(rng.integers(1, n_steps - 1)) if is_fraud else -1
    # Engagement drifts over the window in step with audience health: clean
    # accounts that are genuinely growing tend to see engagement climb modestly,
    # while fraud accounts (bought followers) see engagement DECAY as bots dilute
    # the real audience. This gives the growth engine a real engagement trend to
    # read (otherwise avg_engagement is flat and engagement-growth is always ~0).
    # The drift is MEAN-PRESERVING (centered on the window midpoint), so it changes
    # the slope the growth model reads WITHOUT shifting the average engagement level
    # that the calibration benchmarks depend on.
    eng_trend = (-rng.uniform(0.10, 0.30)) if is_fraud else (0.5 * growth + rng.uniform(-0.03, 0.08))
    for s in range(n_steps):
        frac = s / max(n_steps - 1, 1)
        f = int(start_followers + (followers - start_followers) * frac)
        if s == spike_step:
            f = int(f * rng.uniform(1.4, 2.0))  # injected follower spike
        snap_date = date(2026, 5, 31) - timedelta(days=(n_steps - 1 - s) * gc.snapshot_step)
        eng_t = eng_rate * (1.0 + eng_trend * (frac - 0.5))  # centered drift: slope w/o level shift
        snapshots.append(
            MetricsSnapshot(
                snapshot_id=f"{influencer_id}_s{s:02d}",
                influencer_id=influencer_id,
                date=snap_date,
                followers=max(f, 1),
                avg_engagement=float(np.clip(eng_t * rng.normal(1.0, 0.05), 0.001, 0.3)),
            )
        )

    # --- audience profile ------------------------------------------------ #
    # Skincare/beauty skew female + younger; finance/tech skew male + older.
    if category.name in ("skincare", "beauty", "fashion"):
        gender = {"female": round(float(np.clip(rng.normal(0.78, 0.08), 0.4, 0.95)), 3)}
    elif category.name in ("finance", "tech"):
        gender = {"female": round(float(np.clip(rng.normal(0.35, 0.08), 0.1, 0.6)), 3)}
    else:
        gender = {"female": round(float(np.clip(rng.normal(0.55, 0.1), 0.2, 0.85)), 3)}
    gender["male"] = round(1.0 - gender["female"], 3)

    young = float(np.clip(rng.normal(0.45, 0.1), 0.1, 0.8))
    age_dist = {
        "13-17": round(young * 0.15, 3),
        "18-24": round(young * 0.55, 3),
        "25-34": round((1 - young) * 0.6, 3),
        "35-44": round((1 - young) * 0.3, 3),
        "45+": round((1 - young) * 0.1, 3),
    }
    geo = {region: 0.7, "other": 0.3}
    audience_quality = round(float(np.clip(authenticity_factor * rng.normal(0.95, 0.05), 0.05, 1.0)), 3)
    audience = AudienceProfile(
        influencer_id=influencer_id,
        age_distribution=age_dist,
        gender_split=gender,
        geo_distribution=geo,
        top_interests=[category.name, "lifestyle"],
        audience_quality=audience_quality,
    )

    # --- outcome labels -------------------------------------------------- #
    real_reach = followers * authenticity_factor
    # engagement_quality blends real engagement + low spam + audience quality.
    engagement_quality = eng_rate * (1.0 - spam_ratio) * audience_quality
    brand_fit = float(rng.uniform(0.4, 1.0))  # generic latent fit (brief-specific fit comes later)
    conversions = (
        real_reach
        * engagement_quality
        * brand_fit
        * CONVERSION_COEFFICIENT
        * float(rng.normal(1.0, CONVERSION_NOISE_SD))
    )
    conversions = max(conversions, 0.0)
    if verified:
        conversions *= 1.0 + BENCHMARKS["verified_conversion_uplift"]  # mild verified -> conversion

    cost = max(real_reach / 1000.0 * gc.campaign_cost_per_1k, 1.0)
    revenue = conversions * category.aov * category.margin
    roi = revenue / cost
    success = int(roi > config.ROI_SUCCESS_THRESHOLD)

    influencer = Influencer(
        influencer_id=influencer_id,
        handle=f"@{category.name}.{tier.name}.{idx:04d}",
        platform="instagram",
        display_name=f"{category.name.title()} {tier.name.title()} {idx}",
        bio=f"{category.name} creator | {region} | {tier.name} tier",
        content_category=category.name,
        followers=followers,
        following=following,
        post_count=post_count,
        account_created=account_created,
        region=region,
        verified=verified,
        embedding_ref=None,  # set in feature-engineering (task-006)
        ingested_at=datetime(2026, 5, 31, 12, 0, 0),
    )

    label = {
        "influencer_id": influencer_id,
        "tier": tier.name,
        "category": category.name,
        "is_fraud": int(is_fraud),
        "bot_pct": round(bot_pct, 4),
        "engagement_rate": round(eng_rate, 5),
        "roi": round(float(roi), 4),
        "success": success,
        "conversions": round(float(conversions), 2),
    }
    return influencer, posts, snapshots, audience, label


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def generate(gc: Optional[GenConfig] = None, persist: bool = True) -> list[dict]:
    """Generate the full creator population and (optionally) write it via the repo.

    Returns the list of ground-truth label dicts (also written to a Parquet file
    under ``data/synthetic/`` when ``persist`` is True).
    """
    gc = gc or GenConfig()
    config.seed_everything(gc.seed)
    rng = np.random.default_rng(gc.seed)

    influencers: list[Influencer] = []
    all_posts: list[PostSample] = []
    all_snaps: list[MetricsSnapshot] = []
    audiences: list[AudienceProfile] = []
    labels: list[dict] = []

    for idx in range(1, gc.n_creators + 1):
        inf, posts, snaps, aud, label = _make_creator(idx, rng, gc)
        influencers.append(inf)
        all_posts.extend(posts)
        all_snaps.extend(snaps)
        audiences.append(aud)
        labels.append(label)

    if persist:
        repo.init_db()
        repo.bulk_upsert_influencers(influencers)
        repo.bulk_insert_posts(all_posts)
        repo.bulk_insert_snapshots(all_snaps)
        for aud in audiences:
            repo.upsert_audience_profile(aud)
        _write_labels(labels)

    return labels


def _write_labels(labels: list[dict]) -> None:
    """Persist ground-truth labels to Parquet (falls back to CSV if no pyarrow)."""
    import pandas as pd

    config.ensure_dirs()
    df = pd.DataFrame(labels)
    try:
        df.to_parquet(config.SYNTHETIC_DIR / "labels.parquet", index=False)
    except Exception:
        df.to_csv(config.SYNTHETIC_DIR / "labels.csv", index=False)


def train_test_split_ids(labels: list[dict], test_frac: float = 0.2, seed: int = config.SEED):
    """Deterministic held-out split of influencer_ids (stratified by fraud label)."""
    rng = np.random.default_rng(seed)
    ids = np.array([l["influencer_id"] for l in labels])
    fraud = np.array([l["is_fraud"] for l in labels])
    test_mask = np.zeros(len(ids), dtype=bool)
    for cls in (0, 1):
        cls_idx = np.where(fraud == cls)[0]
        cls_idx_sorted = cls_idx[np.argsort(ids[cls_idx])]  # deterministic order
        n_test = int(round(len(cls_idx_sorted) * test_frac))
        chosen = rng.choice(cls_idx_sorted, size=n_test, replace=False)
        test_mask[chosen] = True
    return sorted(ids[~test_mask].tolist()), sorted(ids[test_mask].tolist())


if __name__ == "__main__":
    labels = generate()
    n_fraud = sum(l["is_fraud"] for l in labels)
    n_success = sum(l["success"] for l in labels)
    print(f"Generated {len(labels)} creators | fraud={n_fraud} ({n_fraud/len(labels):.0%}) "
          f"| success={n_success} ({n_success/len(labels):.0%})")

"""Plant the two reveal seed cases (task-005).

The entire demo hinges on one contradiction:

  * a famous **fraud account** (~512K followers, ~38% bots) that LOOKS huge but
    has tiny real reach -> low / negative ROI -> flagged RED,
  * an unknown **micro gem** (~14K followers, strong skincare fit, real
    engagement) that ranks #1 GREEN.

These two creators are hand-crafted with FIXED attributes (no randomness in the
headline numbers) so they pass through features -> authenticity -> impact
unchanged and the reveal lands identically every run. They use reserved IDs
(``inf_9001`` / ``inf_9002``) that never collide with the generated population
(``inf_0001``..``inf_2000``).

    py scripts/seed_demo.py            # plant into the working DB
    py scripts/seed_demo.py --help     # options

Idempotent: re-running upserts the same rows, never duplicates.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

import config  # noqa: E402
from src.store import repo  # noqa: E402
from src.store.schema import (  # noqa: E402
    AudienceProfile,
    Influencer,
    MetricsSnapshot,
    PostSample,
)

# Reserved, stable IDs for the two demo creators.
GEM_ID = "inf_9001"      # the micro gem (recommended, #1)
FRAUD_ID = "inf_9002"    # the famous fraud account (flagged)

# --------------------------------------------------------------------------- #
# Fixed headline attributes (the numbers that appear on stage)
# --------------------------------------------------------------------------- #
GEM = {
    "influencer_id": GEM_ID,
    "handle": "@minimal.skin",
    "display_name": "Minimal Skin",
    "bio": "Clean, science-backed skincare for sensitive skin. Honest reviews, no fluff. India.",
    "content_category": "skincare",
    "followers": 14_000,
    "following": 280,
    "post_count": 240,
    "region": "IN",
    "verified": False,
    "bot_pct": 0.04,
    "engagement_rate": 0.092,    # strong, real
    "spam_ratio": 0.03,
    "is_fraud": 0,
}
FRAUD = {
    "influencer_id": FRAUD_ID,
    "handle": "@famous.face",
    "display_name": "Famous Face",
    "bio": "Lifestyle | brand collabs | DM for promo 💄✨ skincare beauty fashion",
    "content_category": "skincare",
    "followers": 512_000,
    "following": 4_800,
    "post_count": 980,
    "region": "IN",
    "verified": True,
    "bot_pct": 0.38,             # ~38% inauthentic audience (the reveal stat)
    "engagement_rate": 0.011,    # looks low for the follower count -> suspicious
    "spam_ratio": 0.34,
    "is_fraud": 1,
}

_GEM_CAPTIONS = [
    "my honest barrier-repair routine for sensitive skin",
    "the only 3 actives you actually need",
    "answering your skincare questions — niacinamide vs azelaic",
    "before & after: 8 weeks on a simple routine",
    "drugstore skincare that actually works in India",
]
_FRAUD_CAPTIONS = [
    "obsessed with this 💄✨ #ad", "link in bio!! 🔥🔥", "use my code",
    "collab 💕 dm for promo", "new drop 😍😍😍",
]


def _build(creator: dict, captions: list[str], rng: np.random.Generator):
    """Build the full row bundle for one seed creator from fixed attributes."""
    iid = creator["influencer_id"]
    followers = creator["followers"]
    eng = creator["engagement_rate"]
    base_date = datetime(2026, 5, 31, 12, 0, 0)

    inf = Influencer(
        influencer_id=iid,
        handle=creator["handle"],
        platform="instagram",
        display_name=creator["display_name"],
        bio=creator["bio"],
        content_category=creator["content_category"],
        followers=followers,
        following=creator["following"],
        post_count=creator["post_count"],
        account_created=date(2026, 5, 31) - timedelta(days=900),
        region=creator["region"],
        verified=creator["verified"],
        embedding_ref=None,
        ingested_at=base_date,
    )

    # Posts: engagement consistent with the fixed engagement_rate.
    posts: list[PostSample] = []
    for p in range(12):
        avg = followers * eng
        likes = int(avg * 0.88)
        comments = int(avg * 0.07)
        shares = int(avg * 0.03)
        saves = int(avg * (0.08 if creator["is_fraud"] == 0 else 0.02))
        views = int(followers * (1.1 if creator["is_fraud"] == 0 else 0.7))
        posts.append(
            PostSample(
                post_id=f"{iid}_p{p:02d}",
                influencer_id=iid,
                posted_at=base_date - timedelta(days=p * 4),
                likes=likes, comments=comments, shares=shares, saves=saves, views=views,
                caption=captions[p % len(captions)],
                media_type="reel" if p % 2 else "carousel",
            )
        )

    # Snapshots: fraud account gets a sharp follower spike; gem grows smoothly.
    snaps: list[MetricsSnapshot] = []
    n_steps = 13
    if creator["is_fraud"]:
        start = int(followers * 0.45)
        spike_step = 6
    else:
        start = int(followers * 0.82)
        spike_step = -1
    # Engagement trend: the gem's real engagement climbs over the window (healthy,
    # growing audience); the fraud's decays as bought followers dilute it. Mirrors
    # the generator (mean-preserving, centered on the midpoint) so the growth engine
    # reads a real engagement-growth signal without shifting the headline level.
    eng_trend = -0.22 if creator["is_fraud"] else 0.18
    for s in range(n_steps):
        frac = s / (n_steps - 1)
        f = int(start + (followers - start) * frac)
        if s == spike_step:
            f = int(f * 1.8)
        snaps.append(
            MetricsSnapshot(
                snapshot_id=f"{iid}_s{s:02d}",
                influencer_id=iid,
                date=date(2026, 5, 31) - timedelta(days=(n_steps - 1 - s) * 7),
                followers=max(f, 1),
                avg_engagement=round(eng * (1.0 + eng_trend * (frac - 0.5)), 4),
            )
        )

    # Audience: gem skews exactly to the demo brief (women 22-35 IN, high quality).
    if creator["is_fraud"] == 0:
        gender = {"female": 0.82, "male": 0.18}
        age = {"13-17": 0.04, "18-24": 0.30, "25-34": 0.48, "35-44": 0.14, "45+": 0.04}
        geo = {"IN": 0.86, "other": 0.14}
    else:
        gender = {"female": 0.61, "male": 0.39}
        age = {"13-17": 0.18, "18-24": 0.42, "25-34": 0.24, "35-44": 0.10, "45+": 0.06}
        geo = {"IN": 0.44, "other": 0.56}
    audience = AudienceProfile(
        influencer_id=iid,
        age_distribution=age,
        gender_split=gender,
        geo_distribution=geo,
        top_interests=["skincare", "beauty", "wellness"],
        audience_quality=round(1.0 - creator["bot_pct"], 3),
    )

    return inf, posts, snaps, audience


def build_seed_bundles():
    """Return (rows, labels) for both seed creators without writing to the DB."""
    rng = np.random.default_rng(config.SEED)
    bundles = []
    labels = []
    for creator, caps in ((GEM, _GEM_CAPTIONS), (FRAUD, _FRAUD_CAPTIONS)):
        bundles.append(_build(creator, caps, rng))
        labels.append(
            {
                "influencer_id": creator["influencer_id"],
                "tier": "micro" if creator["is_fraud"] == 0 else "macro",
                "category": creator["content_category"],
                "is_fraud": creator["is_fraud"],
                "bot_pct": creator["bot_pct"],
                "engagement_rate": creator["engagement_rate"],
                "seed_case": True,
            }
        )
    return bundles, labels


def seed(persist: bool = True) -> list[dict]:
    """Plant both seed creators into the DB and write a provenance JSON to data/seed/."""
    bundles, labels = build_seed_bundles()
    if persist:
        repo.init_db()
        for inf, posts, snaps, audience in bundles:
            repo.upsert_influencer(inf)
            repo.bulk_insert_posts(posts)
            repo.bulk_insert_snapshots(snaps)
            repo.upsert_audience_profile(audience)
        config.ensure_dirs()
        (config.SEED_DIR / "seed_cases.json").write_text(
            json.dumps({"gem": GEM, "fraud": FRAUD}, indent=2), encoding="utf-8"
        )
    return labels


if __name__ == "__main__":
    seed()
    print(f"Planted seed cases: gem={GEM_ID} ({GEM['followers']:,} followers), "
          f"fraud={FRAUD_ID} ({FRAUD['followers']:,} followers, {FRAUD['bot_pct']:.0%} bots)")
    print(f"Provenance written to {config.SEED_DIR / 'seed_cases.json'}")

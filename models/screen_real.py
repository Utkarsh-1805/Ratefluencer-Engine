"""
models/screen_real.py — authenticity screening on REAL Instagram accounts
═════════════════════════════════════════════════════════════════════════
Runs the SAME authenticity engine the product uses, on real, public account
numbers you provide in data/real_accounts.csv. This is the honest "it works on
real data" demo: authenticity only needs follower/engagement data, which IS
public — unlike ROI, which has no public ground truth.

IMPORTANT — present results responsibly:
  • Output is an AUTHENTICITY / engagement-quality SCORE, not an accusation.
  • Only the engagement-deficit + ratio signals are used (spike/comment-spam need
    private data, so those flags stay off). Say so in the demo.
  • Don't publicly label a named person "fraud". Frame it as "screening score:
    engagement far below what an account this size normally shows — a known
    bought-follower signal."

    py models/screen_real.py                      # uses data/real_accounts.csv
    py models/screen_real.py path/to/other.csv

Real accounts are stored under reserved ids (real_*) that never appear in normal
brief retrieval, so this does not pollute the main shortlist.
"""
from __future__ import annotations

import csv
import sys
from datetime import date, datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")   # avoid cp1252 crashes on Windows
except (AttributeError, ValueError):
    pass

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

from models.score_creator import ML_AVAILABLE, _PROJ  # noqa: E402

if not ML_AVAILABLE:
    print(f"ML layer not found at {_PROJ}.")
    raise SystemExit(2)

DEFAULT_CSV = _ENGINE_ROOT / "data" / "real_accounts.csv"


def _read_csv(path: Path) -> list[dict]:
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for raw in f:
            if raw.strip().startswith("#") or not raw.strip():
                continue
            # rewind-style: collect non-comment lines, then DictReader them
            rows.append(raw)
    if not rows:
        return []
    reader = csv.DictReader(rows)
    return list(reader)


def _vec_from_public(row: dict) -> dict:
    """Build the authenticity feature vector from PUBLIC numbers only.

    engagement_rate      = (avg_likes + avg_comments) / followers
    real_engagement_rate = same (we have no separate 'real' signal for real data;
                           the tier-deficit comparison does the work)
    like_comment_ratio   = avg_likes / avg_comments
    follower_following_ratio = followers / following
    spike_anomaly_score / comment_spam_ratio = 0.0 (need private data → omitted)
    """
    followers = max(int(float(row["followers"])), 1)
    following = max(int(float(row.get("following", 0) or 0)), 1)
    likes = float(row.get("avg_likes", 0) or 0)
    comments = float(row.get("avg_comments", 0) or 0)
    eng = (likes + comments) / followers
    return {
        "engagement_rate": eng,
        "real_engagement_rate": eng,
        "like_comment_ratio": (likes / comments) if comments > 0 else 0.0,
        "follower_following_ratio": followers / following,
        "spike_anomaly_score": 0.0,
        "comment_spam_ratio": 0.0,
        "_low_confidence": 0.0,
    }


def _band(score: int) -> str:
    return "GREEN (clean)" if score >= 60 else ("AMBER (watch)" if score >= 50 else "RED (screened out)")


# ── Reusable API (used by the CLI above AND the Streamlit screener page) ──────
_ENGINE_CACHE = {"engine": None}


def _get_engine():
    """Fit (once) and cache the authenticity engine on the population."""
    if _ENGINE_CACHE["engine"] is None:
        from src.data.features import build_all_creator_features
        from src.models.authenticity import AuthenticityEngine
        pop_feats = build_all_creator_features(persist=False, embed=False)
        _ENGINE_CACHE["engine"] = AuthenticityEngine().fit(pop_feats)
    return _ENGINE_CACHE["engine"]


def screen_account(handle: str, followers: int, following: int,
                   avg_likes: float, avg_comments: float,
                   category: str = "", verified: bool = False) -> dict:
    """Screen ONE real account from public numbers. Returns a UI-friendly dict:
       {handle, followers, engagement_rate, expected_rate, authenticity_score,
        band, flags}. Raises ValueError on bad input."""
    from datetime import date, datetime
    from src.store import repo
    from src.store.schema import Influencer
    from src.models.authenticity import _expected_engagement

    followers = max(int(followers), 1)
    row = {"handle": handle, "followers": followers, "following": following,
           "avg_likes": avg_likes, "avg_comments": avg_comments}
    vec = _vec_from_public(row)
    rid = "real_" + (handle or "acct").lstrip("@").replace(".", "_")

    repo.upsert_influencer(Influencer(
        influencer_id=rid, handle=handle or "@account", platform="instagram",
        display_name=handle or "@account", bio="", content_category=category or "",
        followers=followers, following=int(following or 0), post_count=0,
        account_created=date(2020, 1, 1), region="", verified=bool(verified),
        embedding_ref=None, ingested_at=datetime(2026, 1, 1, 12, 0, 0),
    ))
    res = _get_engine().score(rid, vec=vec, persist=False)
    score = int(res.authenticity_score)
    return {
        "handle": handle,
        "followers": followers,
        "engagement_rate": round(vec["engagement_rate"] * 100, 2),     # %
        "expected_rate": round(_expected_engagement(followers) * 100, 2),  # %
        "authenticity_score": score,
        "band": "green" if score >= 60 else ("amber" if score >= 50 else "red"),
        "flags": list(res.flags or []),
    }


def main(csv_path: str | None = None) -> int:
    import config
    from src.store import repo
    from src.store.schema import Influencer
    from src.data.features import build_all_creator_features
    from src.models.authenticity import AuthenticityEngine, _expected_engagement

    path = Path(csv_path) if csv_path else DEFAULT_CSV
    if not path.exists():
        print(f"No CSV at {path}. Fill in data/real_accounts.csv first.")
        return 2

    accounts = _read_csv(path)
    if not accounts:
        print("No account rows found in the CSV (only comments?). Add real rows.")
        return 2

    # Fit the engine on the existing synthetic population (so the IsolationForest +
    # tier baselines are calibrated), exactly as the product does.
    print(f"Fitting authenticity engine on the population ({_PROJ.name}) ...")
    pop_feats = build_all_creator_features(persist=False, embed=False)
    engine = AuthenticityEngine().fit(pop_feats)

    print(f"\nScreening {len(accounts)} real account(s) — public engagement signals only:\n")
    print(f"  {'handle':<28}{'followers':>10}  {'eng%':>6}  {'tier-exp%':>9}  {'auth':>4}  band")
    print("  " + "-" * 78)

    for row in accounts:
        handle = (row.get("handle") or "?").strip()
        try:
            rid = "real_" + handle.lstrip("@").replace(".", "_")
            vec = _vec_from_public(row)
            followers = max(int(float(row["followers"])), 1)

            # Upsert a minimal Influencer so engine.score() can read followers.
            repo.upsert_influencer(Influencer(
                influencer_id=rid, handle=handle, platform="instagram",
                display_name=handle, bio="", content_category=row.get("category", "") or "",
                followers=followers, following=int(float(row.get("following", 0) or 0)),
                post_count=int(float(row.get("posts", 0) or 0)),
                account_created=date(2020, 1, 1),
                region="", verified=str(row.get("verified", "")).strip().lower() == "true",
                embedding_ref=None, ingested_at=datetime(2026, 1, 1, 12, 0, 0),
            ))

            res = engine.score(rid, vec=vec, persist=False)
            exp = _expected_engagement(followers)
            print(f"  {handle:<28}{followers:>10,}  {vec['engagement_rate']*100:>5.2f}  "
                  f"{exp*100:>8.2f}  {res.authenticity_score:>4}  {_band(res.authenticity_score)}")
            if res.flags:
                print(f"  {'':<28}        -> signals: {', '.join(res.flags)}")
        except Exception as e:
            # One malformed row shouldn't kill the whole run — skip it with a note.
            print(f"  {handle:<28}  [skipped — bad row: {e}. Check it has all 8 columns.]")

    print("\nNote: scores use PUBLIC engagement-vs-size signals only (spike/comment-"
          "spam need private data). Present as an authenticity SCREEN, not an accusation.")
    repo.close_connection()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))

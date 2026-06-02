"""
models/prepare_demo.py  —  one-command demo data setup
══════════════════════════════════════════════════════
Builds a consistent, demo-ready state in the ML layer so the live UI has real
data to score:

  1. generate a synthetic creator population (default 2,000 — fast),
  2. plant the two reveal seed creators (@minimal.skin gem, @famous.face fraud),
  3. compute features + build the FAISS vector index (real MiniLM embeddings),
  4. fit the Authenticity engine and write authenticity_results for every creator,
  5. rebuild features so they are fraud-adjusted.

It does NOT retrain True-Impact — it reuses the trained model already in
models_store/true_impact.pkl (the 30K Kaggle model). Run this once before the
first live demo, or after wiping the DB.

    py models/prepare_demo.py            # 2,000 creators (fast, recommended for demo)
    py models/prepare_demo.py 5000       # bigger pool if you want more candidates

Idempotent: safe to re-run (upserts, never duplicates).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the engine root is importable whether run as `py models/prepare_demo.py`
# (cwd=root) or as a module — so `import models.score_creator` always resolves.
_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

# Reuse the bridge's path setup so `src.*` imports resolve to the ML repo.
from models.score_creator import ML_AVAILABLE, _PROJ  # noqa: E402

if not ML_AVAILABLE:
    print(f"ML layer not found at {_PROJ}. Set RATEFLUENCER_PROJ or fix the layout.")
    raise SystemExit(2)


def main(n_creators: int = 2000) -> int:
    import config
    from src.data.generate_synthetic import GenConfig, generate
    from src.data.features import build_all_creator_features
    from src.models.authenticity import AuthenticityEngine
    from src.store import repo
    from scripts.seed_demo import seed, GEM_ID, FRAUD_ID

    config.seed_everything()
    print(f"Preparing demo data in: {_PROJ}")
    print(f"  DB:     {config.DB_PATH}")
    print(f"  Vector: {config.VECTOR_DIR}")
    print(f"  Model:  {config.MODELS_DIR / 'true_impact.pkl'}")

    # 1) population + 2) seed creators
    print(f"\n[1/4] Generating {n_creators} creators + planting seed cases ...")
    generate(GenConfig(n_creators=n_creators), persist=True)
    seed(persist=True)

    # 3) features + FAISS vector index (embed=True → real MiniLM if installed)
    print("[2/4] Building features + FAISS vector index (this embeds every creator) ...")
    feats = build_all_creator_features(persist=True, embed=True)

    # 4) authenticity for every creator
    print("[3/4] Fitting authenticity engine + scoring all creators ...")
    engine = AuthenticityEngine().fit(feats)
    for iid, vec in feats.items():
        engine.score(iid, vec=vec, persist=True)

    # 5) rebuild features now that authenticity_results exist (fraud-adjusted)
    print("[4/4] Rebuilding fraud-adjusted features ...")
    build_all_creator_features(persist=True, embed=False)

    # 6) fit + SAVE the growth model so the live app loads it instantly instead
    #    of refitting over the whole population (~45s) on first use.
    print("[5/5] Fitting + saving growth model (so the app starts fast) ...")
    from src.models.growth import GrowthModel
    GrowthModel().fit().save()

    n = repo.count("influencers")
    n_auth = repo.count("authenticity_results")
    print(f"\nDone. influencers={n}, authenticity_results={n_auth}")
    print(f"Seed creators: gem={GEM_ID}, fraud={FRAUD_ID}")

    # quick sanity: score the two seed creators through the bridge
    from models.score_creator import score_creator
    for iid in (GEM_ID, FRAUD_ID):
        s = score_creator(iid)
        if s:
            print(f"  {iid} {s['handle']:<16} impact={s['impact']} "
                  f"auth={s['authenticity']} match={s['match']} roi={s['predicted_roi']:.1f}x "
                  f"flags={s['authenticity_detail']['flags']}")
    repo.close_connection()
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    raise SystemExit(main(n_creators=n))

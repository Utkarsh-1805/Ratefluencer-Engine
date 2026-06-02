"""
models/test_integration.py — headless end-to-end integration test
═════════════════════════════════════════════════════════════════
Exercises the FULL agent pipeline (parse → retrieve → score → rank → compose)
against the REAL ML models, WITHOUT Streamlit. This is what can be verified
automatically; the visual UI itself must be eyeballed in the browser.

    py models/test_integration.py

Exit 0 only if:
  • the ML bridge loads and scores the two reveal seed creators,
  • every score dict has the exact keys the UI reads,
  • the reveal holds: gem (@minimal.skin) out-ranks fraud (@famous.face),
    and the fraud account is flagged,
  • retrieval returns candidates,
  • the ranker + composer run and produce a recommendation.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(_ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(_ENGINE_ROOT))

# Required keys in every score dict the UI consumes.
REQUIRED_KEYS = {
    "impact", "authenticity", "match", "predicted_roi", "success_prob",
    "handle", "display_name", "followers", "platform", "content_category",
    "verified", "drivers", "authenticity_detail", "audience_fit", "status",
}
GEM_ID, FRAUD_ID = "inf_9001", "inf_9002"

_passed = _failed = 0


def check(label, ok, detail=""):
    global _passed, _failed
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    _passed += ok
    _failed += not ok


def main() -> int:
    from models.score_creator import ML_AVAILABLE, score_creator, get_candidates_real
    print("\n== integration test ==\n")
    check("ML layer available", ML_AVAILABLE)
    if not ML_AVAILABLE:
        print("\nML layer missing — run models/prepare_demo.py first.")
        return 1

    # ── 1. Bridge scores the two reveal creators ──────────────────────────────
    parsed = {
        "category": "skincare",
        "target_audience": {"age_min": 22, "age_max": 35, "gender": "female", "geo": "India"},
        "goal": "sales", "tone": "authentic",
        "raw": "DTC skincare for women 22-35 in India, goal sales", "budget": 300000,
    }
    gem = score_creator(GEM_ID, parsed_brief=parsed)
    fraud = score_creator(FRAUD_ID, parsed_brief=parsed)

    check("gem scored (non-empty)", bool(gem), gem.get("handle", ""))
    check("fraud scored (non-empty)", bool(fraud), fraud.get("handle", ""))
    if not (gem and fraud):
        print("\nSeed creators not in DB — run models/prepare_demo.py first.")
        return 1

    # ── 2. Shape contract ─────────────────────────────────────────────────────
    miss_gem = REQUIRED_KEYS - set(gem)
    check("gem dict has all UI keys", not miss_gem, f"missing={miss_gem}")
    check("drivers is a non-empty list of {feature,effect,value}",
          isinstance(gem["drivers"], list) and len(gem["drivers"]) >= 3
          and all({"feature", "effect", "value"} <= set(d) for d in gem["drivers"]))
    check("authenticity_detail has fraud fields",
          {"bot_follower_pct", "flags", "spike_anomaly_score", "comment_spam_ratio"}
          <= set(gem["authenticity_detail"]))
    check("audience_fit has age/gender/geo",
          {"age_match", "gender_match", "geo_match"} <= set(gem["audience_fit"]))

    print(f"\n  GEM   {gem['handle']:<16} impact={gem['impact']} auth={gem['authenticity']} "
          f"match={gem['match']} roi={gem['predicted_roi']:.1f}x flags={gem['authenticity_detail']['flags']}")
    print(f"  FRAUD {fraud['handle']:<16} impact={fraud['impact']} auth={fraud['authenticity']} "
          f"match={fraud['match']} roi={fraud['predicted_roi']:.1f}x flags={fraud['authenticity_detail']['flags']}\n")

    # ── 3. The reveal holds ───────────────────────────────────────────────────
    check("gem out-ranks fraud on True-Impact", gem["impact"] > fraud["impact"],
          f"{gem['impact']} vs {fraud['impact']}")
    check("fraud has authenticity flags", len(fraud["authenticity_detail"]["flags"]) > 0)
    check("fraud authenticity lower than gem", fraud["authenticity"] < gem["authenticity"])

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    cands = get_candidates_real(parsed, top_k=20)
    check("retrieval returns candidates", len(cands) > 0, f"n={len(cands)}")

    # ── 5. Ranker + composer (the rest of the agent) ──────────────────────────
    from agent.ranker import rank_candidates
    from agent.composer import compose_recommendation

    # Score a small candidate set (seed creators + a few retrieved).
    ids = list(dict.fromkeys([GEM_ID, FRAUD_ID] + cands))[:8]
    scores = {}
    for iid in ids:
        s = score_creator(iid, parsed_brief=parsed)
        if s:
            scores[iid] = s
    weights = {"impact": 0.40, "authenticity": 0.35, "match": 0.15, "cost": 0.10}
    ranked = rank_candidates(scores, weights)
    check("ranker produced an order", len(ranked) == len(scores), f"n={len(ranked)}")
    check("flagged creators sink below recommended",
          all(scores[ranked[i]]["status"] != "flagged" or scores[ranked[j]]["status"] == "flagged"
              for i in range(len(ranked)) for j in range(i, len(ranked))))
    # gem should be at/near the top; fraud should not be #1
    check("gem is ranked #1", ranked and ranked[0] == GEM_ID, f"top={ranked[0] if ranked else None}")
    check("fraud is not ranked #1", not ranked or ranked[0] != FRAUD_ID)

    brief_for_composer = {**parsed, "audience": parsed["target_audience"]}
    rec = compose_recommendation(brief_for_composer, ranked, scores)
    check("composer returns a recommendation",
          isinstance(rec, dict) and "summary" in rec and "budget_split" in rec)
    check("recommendation has projected ROI", "projected_roi" in rec)

    print(f"\n  Recommendation summary:\n    {rec.get('summary', '')[:200]}...")
    print(f"\n== {_passed} passed, {_failed} failed ==\n")
    return 0 if _failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

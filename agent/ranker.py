"""
agent/ranker.py
───────────────
Ranks candidates by weighted composite score.
Fraud guardrail: creators with authenticity < threshold are flagged
and pushed to the bottom of the list (not excluded — judges see them).
"""

AUTHENTICITY_FLAG_THRESHOLD = 60   # below this → flagged
AUTHENTICITY_SUPPRESS_THRESHOLD = 50  # below this → pushed to end of ranked list


def compute_composite(scores: dict, weights: dict) -> float:
    """
    Compute weighted composite score for one creator.

    Args:
        scores: {impact, authenticity, match, predicted_roi}
        weights: {impact, authenticity, match, cost}

    Returns:
        float composite score
    """
    # Normalise ROI into a 0-100 cost/value score (cap at 5× ROI = 100)
    roi = scores.get("predicted_roi", 0)
    roi_score = max(0, min(100, roi * 20))   # 5× ROI → 100

    composite = (
        weights.get("impact",        0.40) * scores.get("impact",        0) +
        weights.get("authenticity",  0.35) * scores.get("authenticity",  0) +
        weights.get("match",         0.15) * scores.get("match",         0) +
        weights.get("cost",          0.10) * roi_score
    )
    return round(composite, 2)


def apply_fraud_guardrail(influencer_id: str, scores: dict) -> dict:
    """
    Apply fraud guardrail — mutates and returns updated scores dict.
    Sets status to 'flagged' and adds flag_reason if authenticity is low.
    """
    auth = scores.get("authenticity", 100)
    if auth < AUTHENTICITY_FLAG_THRESHOLD:
        scores["status"] = "flagged"
        bot_pct = scores.get("authenticity_detail", {}).get("bot_follower_pct", 0)
        scores["flag_reason"] = (
            f"{bot_pct:.0f}% inauthentic audience → projected "
            f"{'negative' if scores.get('predicted_roi', 0) < 0 else 'poor'} ROI"
        )
    else:
        if scores.get("status") != "excluded":
            scores["status"] = "recommended"
        scores["flag_reason"] = None
    return scores


def rank_candidates(
    scores: dict,          # { influencer_id: score_dict }
    weights: dict,         # objective weights from brief
) -> list[str]:
    """
    Main ranking function.

    1. Apply fraud guardrail to each creator
    2. Compute composite score
    3. Sort: recommended first (by composite desc), flagged last

    Args:
        scores: dict of influencer_id → score dict (mutated in place)
        weights: objective weights {impact, authenticity, match, cost}

    Returns:
        Ordered list of influencer_ids
    """
    composite_scores = {}

    for iid, s in scores.items():
        # Apply fraud guardrail
        scores[iid] = apply_fraud_guardrail(iid, s)
        # Compute composite
        composite = compute_composite(s, weights)
        scores[iid]["composite"] = composite
        composite_scores[iid] = composite

    # Separate recommended vs flagged/excluded
    recommended = [
        iid for iid, s in scores.items()
        if s.get("status") == "recommended"
    ]
    flagged = [
        iid for iid, s in scores.items()
        if s.get("status") in ("flagged", "excluded")
    ]

    # Sort each group by composite desc
    recommended.sort(key=lambda x: composite_scores[x], reverse=True)
    flagged.sort(key=lambda x: composite_scores[x], reverse=True)

    ranked = recommended + flagged
    return ranked

if __name__ == "__main__":
    from utils.dummy_scores import DUMMY_SCORES

    weights = {"impact": 0.40, "authenticity": 0.35, "match": 0.15, "cost": 0.10}
    scores  = {k: dict(v) for k, v in DUMMY_SCORES.items()}  # copy
    ranked  = rank_candidates(scores, weights)

    print("Ranked order:")
    for i, iid in enumerate(ranked, 1):
        s = scores[iid]
        print(f"  {i}. {iid} | composite={s['composite']} | status={s['status']}")

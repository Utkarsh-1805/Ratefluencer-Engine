"""utils/ranking.py — Re-rank creators from cached scores using objective weights.
No model recompute needed — pure weighted composite from existing scores.
"""

def rerank(scores: dict, weights: dict, ranked: list) -> list:
    """
    Re-rank influencer_ids by weighted composite score.
    Flagged accounts are always pushed to the bottom.

    Args:
        scores:  session scores dict  { influencer_id: { impact, authenticity, match, predicted_roi, status, ... } }
        weights: { "impact": float, "authenticity": float, "match": float, "cost": float }
        ranked:  current ordered list of influencer_ids

    Returns:
        New ordered list of influencer_ids.
    """
    w_impact  = weights.get("impact", 0.4)
    w_auth    = weights.get("authenticity", 0.35)
    w_match   = weights.get("match", 0.15)
    w_cost    = weights.get("cost", 0.10)

    def composite(iid):
        s = scores[iid]
        # Normalise ROI to 0-100 scale (clamp between -1× and 5×)
        roi_norm = max(0, min(100, (s["predicted_roi"] + 1) / 6 * 100))
        score = (
            w_impact * s["impact"] +
            w_auth   * s["authenticity"] +
            w_match  * s["match"] +
            w_cost   * roi_norm
        )
        return score

    flagged     = [iid for iid in ranked if scores[iid]["status"] == "flagged"]
    not_flagged = [iid for iid in ranked if scores[iid]["status"] != "flagged"]

    not_flagged_sorted = sorted(not_flagged, key=composite, reverse=True)
    flagged_sorted     = sorted(flagged,     key=composite, reverse=True)

    return not_flagged_sorted + flagged_sorted

# Ratefluencer Copilot 🎯
> The AI media-buyer that ranks **business impact, not follower count.**

**Ratefluencer AI Hackathon 2026 · Track 1 — AI Influencer Intelligence Engine**

A marketer types a plain-English brief; the product returns a **fraud-adjusted,
ROI-ranked, explainable shortlist of creators** plus an exportable campaign
recommendation — powered by five real ML models, not vanity metrics.

---

## Quick Start

```powershell
# 1. Enter the engine repo
cd Ratefluencer-Engine-main

# 2. Install dependencies
py -m pip install -r requirements.txt

# 3. Build the demo data (generates creators, plants the reveal cases, builds the
#    FAISS index + authenticity scores). Reuses the trained model — does NOT retrain.
py models/prepare_demo.py

# 4. Run the app
py -m streamlit run app.py
```

The demo runs **fully offline** from seeded data. No API key needed.
*(Optional: drop a `GEMINI_API_KEY` in a `.env` file for LLM-written campaign
summaries — see `.env.example`. Without it, a built-in template is used.)*

> **First analysis takes ~40s** (one-time model + embedding warm-up), then it's
> instant. See [TEST_GUIDE.md](TEST_GUIDE.md) for exactly what to type and expect.

---

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full diagram. In brief — four
layers, deterministic ML in the middle, LLM only at the edges:

```
Layer 4 · UI        Streamlit: brief → ranked shortlist (the reveal) → cards → export
        ▲
Layer 3 · Agent     parse brief → retrieve → score → rank → compose recommendation
        ▲
Layer 2 · Models    Authenticity · True-Impact (ROI+success) · Brand-Match · Growth · SHAP
        ▲
Layer 1 · Data      synthetic generator (labeled) → features → FAISS vector index
```

This repo (**Engine**) holds the agent + UI; the sibling repo
**`ratefluencer-copilot/proj`** holds the Data+ML layer. They connect through one
bridge — [`models/score_creator.py`](models/score_creator.py). See
[INTEGRATION.md](INTEGRATION.md).

---

## The five scores (every creator, every brief)

| Score | What it answers | Model |
|---|---|---|
| **True-Impact** (0–100) | Will this creator drive ROI? | LightGBM regressor + calibrated classifier |
| **Authenticity** (0–100) | Is the audience real? | IsolationForest + tier-relative engagement deficit + rules |
| **Brand-Match** (0–100) | Do they fit *this* brief? | MiniLM embeddings + audience/category fit |
| **Growth** (0–100) | Are they rising? | Momentum model over follower/engagement trend |
| **Drivers + rationale** | *Why* this score? | SHAP TreeExplainer + one-line rationale |

Fraud is **baked into impact**: `fraud_adjusted_reach = followers × (1 − bot%)` is
a model input, so a big account with a fake audience scores low *by prediction*,
not by a hard rule.

---

## Verified results (held-out, seed=42)

Trained on **30,000 synthetic creators**, evaluated on **6,000 held-out**:

| Metric | Value | Meaning |
|---|---|---|
| **Precision@50** | **1.000 vs 0.320** baseline | every top-50 creator is a genuine success — vs 32% when ranking by followers |
| ROI Spearman | **0.792** | ranking order strongly matches true ROI |
| Success ROC-AUC | **0.963** | cleanly separates winners from losers |
| Fraud F1 | **0.893** | catches fraud (recall 0.974) without false alarms |
| Clean-creator mean ROI | **~6.6×** | matches the published industry benchmark |

**The headline:** ranking by True-Impact ≈ **3× the shortlist quality** of
follower-count ranking, validated on 6,000 unseen creators.

---

## The Reveal

Seeded so it lands every run — **the demo's money moment** (skincare brief):

- **@famous.face** — 512K followers, ✔verified → flagged **RED**, ranked **last**,
  True-Impact **~6/100** (~54% bot audience: bot_followers, spike, comment-spam).
- **@minimal.skin** — 14K followers, unknown → **clean GREEN**, True-Impact ~62,
  ROI ~4.2×.

> "The 512K verified influencer is flagged and dead-last; unknown micro-creators
> with real engagement dominate the top. Follower count is inverted."

**Bonus — real-data proof:** `py models/screen_real.py` runs the authenticity
engine on **real public Instagram numbers** (it needs only follower/engagement
data). It correctly flags big-but-fake accounts — same likes, 40K vs 800K
followers → one passes, one flagged. (Present as an authenticity *screen*, not a
public accusation.)

---

## Data Provenance (stated openly)

- **Synthetic generator** → training labels, because **no public dataset has
  campaign-outcome (ROI) labels** — conversions live in brands' private CRMs.
  Calibrated to documented benchmarks (engagement-by-tier, ~6.6× industry ROI,
  verified-conversion uplift). Fraud injected into ~20% of profiles.
- **Real public profiles** → used for the live authenticity screen (where public
  data genuinely supports the model).
- One-liner: *"Real profiles for realism, a benchmark-calibrated synthetic
  generator for outcome labels — because no one publishes conversion data."*

---

## Project Structure

```
Ratefluencer-Engine-main/
├── app.py                  # Streamlit entry point + global styles
├── ui/                     # screens: brief → working → shortlist → detail → recommend
├── agent/                  # orchestrator, brief_parser, retriever, ranker, composer
├── models/                 # ML BRIDGE → score_creator.py, prepare_demo.py, screen_real.py
├── utils/                  # session, env loader, ui_kit, ranking
└── data/                   # SQLite + FAISS (built by prepare_demo) + real_accounts.csv

ratefluencer-copilot/proj/  # (sibling) Data+ML layer: src/{store,data,models}, models_store/
```

---

## Hackathon Rubric

| Category | Points | How we earn them |
|---|---|---|
| AI/ML Innovation | 20 | Fraud-adjusted True-Impact + anomaly detection + SHAP + embeddings |
| Scoring Accuracy | 20 | Precision@50 1.000 vs 0.32, validated on 6,000 held-out creators |
| Viral Prediction | 15 | ROI + success probability + growth potential |
| Agent Design | 15 | Brief → retrieve → score → rank → recommend |
| Product Design | 10 | Decision-first UI + the reveal |
| Business Impact | 10 | Quantified wasted-spend savings (fraud → negative ROI) |
| Technical Complexity | 5 | 5-model stack + vector search + synthetic data engine |
| Demo | 5 | Rehearsed reveal + real-account screen + backup video |
| **Total** | **100** | |

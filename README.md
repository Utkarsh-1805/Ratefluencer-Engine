# Ratefluencer Copilot 🎯
> The AI media-buyer that ranks business impact, not follower count.

**Ratefluencer AI Hackathon 2026 · Track 1 — AI Influencer Intelligence Engine**

---

## Quick Start

```bash
# 1. Clone and enter the repo
git clone <repo-url> && cd ratefluencer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the app
streamlit run app.py
```

The demo runs **fully offline** from seeded data. No API key needed for the UI demo.

---

## Project Structure

```
ratefluencer/
├── app.py                  # Streamlit entry point + global styles
├── requirements.txt
├── ui/
│   ├── brief_composer.py   # Screen A: Brief input
│   ├── agent_working.py    # Screen B: Progress animation
│   ├── ranked_shortlist.py # Screen C: THE REVEAL (hero screen)
│   ├── creator_detail.py   # Screen D: SHAP + authenticity breakdown
│   └── recommendation.py  # Screen E: Budget split + export
├── utils/
│   ├── session.py          # Session state model
│   ├── dummy_scores.py     # Hardcoded demo scores (replace with real models)
│   └── components.py       # ScoreChip, StatusPill, helpers
├── models/                 # Person A: ML models go here
├── agent/                  # Person A→B handoff: score_creator() lives here
└── data/                   # Person A: SQLite + Parquet files go here
```

---

## Data Provenance

- **Demo dataset**: Synthetic creator profiles generated with documented assumptions
- **Fraud injection**: ~20% of profiles seeded with purchased-follower patterns, engagement pods, and spike anomalies
- **Training labels**: Derived from `roi = (conversions × AOV × margin) / cost`
- **Real public profiles**: Used for demo realism (Kaggle influencer datasets)

All assumptions are documented and stated openly.

---

## The Reveal

The demo is seeded so the reveal is guaranteed:
- **@famous.face** (512K followers) → 🚨 Flagged: 38% inauthentic audience → projected **negative ROI**
- **@minimal.skin** (14K followers) → ✅ Rank #1: True-Impact 91, Authenticity 96

---

## Hackathon Rubric

| Category | Points | How we earn them |
|---|---|---|
| AI/ML Innovation | 20 | Fraud-adjusted True-Impact + anomaly detection + embeddings |
| Scoring Accuracy | 20 | SHAP-explained drivers + calibrated ranking |
| Viral Prediction | 15 | ROI prediction + success probability |
| Agent Design | 15 | Brief → retrieve → score → rank → recommend |
| Product Design | 10 | Decision-first UI + the reveal |
| Business Impact | 10 | Quantified wasted-spend savings |
| Technical Complexity | 5 | Multi-model + vector search + agent |
| Demo | 5 | Rehearsed reveal + backup video |
| **Total** | **100** | |

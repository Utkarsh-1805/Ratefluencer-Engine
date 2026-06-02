<div align="center">

# 🎯 Ratefluencer Copilot

### The AI media-buyer that ranks **business impact — not follower count.**

*Ratefluencer AI Hackathon 2026 · Track 1 — AI Influencer Intelligence Engine*

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LightGBM](https://img.shields.io/badge/LightGBM-gradient_boosting-02569B)
![scikit-learn](https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS-vector_search-0467DF)
![SHAP](https://img.shields.io/badge/SHAP-explainability-8A2BE2)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)
![Offline](https://img.shields.io/badge/runs-100%25_offline-34D399)

**Type a campaign brief in plain English → get a fraud-adjusted, ROI-ranked,
explainable shortlist of creators + an exportable plan.**

</div>

---

## 🚀 The 10-second pitch

> Brands burn **billions** picking influencers by follower count. Follower count
> **does not predict campaign success.** Ratefluencer Copilot predicts the thing
> that actually matters — **business impact (ROI)** — sees through fake audiences,
> and explains every decision.

And it proves it on stage:

```
  #1   @minimal.skin     14K followers   🟢 True-Impact 62   ✅ recommended
        ⋮  (real micro-creators with genuine engagement rank at the top)
  #22  @famous.face     512K ✔verified   🔴 True-Impact  6   🚩 FLAGGED — last
                                          ~54% bot audience → projected poor ROI
```

**A 512K verified influencer ranked dead last. An unknown 14K creator wins.**
Follower count, inverted — with proof. *That's the reveal.*

---

## 📊 Verified results (held-out test set, seed = 42)

> Trained on **30,000** synthetic creators · evaluated on **6,000 held-out** creators.

| Metric | Result | What it means |
|:--|:--:|:--|
| 🎯 **Precision@50** | **1.000** vs `0.320` | every one of the top-50 picks is a genuine success — vs **32%** when ranking by followers |
| 📈 **ROI Spearman** | **0.792** | predicted ranking order strongly matches true ROI |
| ✅ **Success ROC-AUC** | **0.963** | cleanly separates campaign winners from losers |
| 🛡️ **Fraud F1** | **0.893** | catches **97%** of fraud (recall 0.974) without false alarms |
| 💰 **Clean-creator ROI** | **~6.6×** | matches the published industry benchmark |

> ### 💡 Headline: ranking by True-Impact delivers **~3× the shortlist quality** of follower-count ranking — validated on 6,000 unseen creators.

---

## 🧠 Five models behind every score

| Score | Answers | Powered by |
|:--|:--|:--|
| 🎯 **True-Impact** `0–100` | *Will they drive ROI?* | LightGBM regressor + isotonic-calibrated classifier |
| 🛡️ **Authenticity** `0–100` | *Is the audience real?* | IsolationForest + tier-relative engagement deficit + rules |
| 🤝 **Brand-Match** `0–100` | *Do they fit THIS brief?* | MiniLM embeddings + audience/category fit |
| 🌱 **Growth** `0–100` | *Are they rising?* | Momentum model over follower + engagement trend |
| 🔍 **Drivers + rationale** | *Why this score?* | SHAP TreeExplainer + one-line explanation |

> **Fraud is baked into impact, not bolted on.**
> `fraud_adjusted_reach = followers × (1 − bot%)` is a *model input* — so a big
> account with a fake audience scores low **by prediction**, not by a hard rule.
> The reveal is a forecast, not a filter.

---

## ⚡ Quick start

```powershell
# 1 · install dependencies
py -m pip install -r requirements.txt

# 2 · build the demo data (creators + reveal cases + FAISS index + fraud scores).
#     Reuses the trained model — does NOT retrain.
py models/prepare_demo.py

# 3 · launch
py -m streamlit run app.py
```

✅ Runs **100% offline** from seeded data — no API key required.
🔑 *Optional:* add `GEMINI_API_KEY` to a `.env` file (see `.env.example`) for
LLM-written campaign summaries; without it, a built-in template is used.
⏱️ *First analysis ≈ 40s* (one-time model + embedding warm-up), instant after.

---

## 🏗️ Architecture

**Deterministic ML in the middle, LLM only at the edges.** Every score is
reproducible (global seed = 42).

```
┌──────────────────────────────────────────────────────────────────────┐
│  Layer 4 · UI         Streamlit — brief → ranked shortlist (REVEAL)   │
│                                    → creator detail → export plan      │
│       ▲                                                                │
│  Layer 3 · Agent      parse brief → retrieve → score → rank → compose │
│       ▲                                          │                     │
│       │                                          └──► LLM (Gemini /    │
│       │                                               offline template)│
│  ═══ models/score_creator.py  ── THE BRIDGE ══════════════════════════│
│       ▼                                                                │
│  Layer 2 · Models     Authenticity · True-Impact · Brand-Match ·      │
│                        Growth · SHAP            (sibling ML repo)      │
│       ▲                                                                │
│  Layer 1 · Data       synthetic generator → 17 features → FAISS index │
└──────────────────────────────────────────────────────────────────────┘
```

**The agent pipeline:**

```
  Brief ─►Parse─►Retrieve─►Score (5 models/creator)─►Rank─►Compose─► Shortlist + Plan
                              │                          │
            Authenticity ─────┤            weighted composite + fraud
            True-Impact ──────┤            guardrail (flagged → bottom)
            Brand-Match ──────┤
            Growth ───────────┤
            SHAP drivers ─────┘
```

This repo (**Engine** — agent + UI) connects to the sibling **Data + ML** repo
(`ratefluencer-copilot/proj`) through a single bridge: `models/score_creator.py`.

---

## 🔬 Real-data proof (not just synthetic)

```powershell
py models/screen_real.py    # screens real Instagram accounts from public numbers
```

The authenticity engine needs only **public** data (followers + engagement), so
it runs on **real accounts**. It's *tier-aware* — the clever part:

| Account | Followers | Avg likes | Engagement | Verdict |
|:--|:--:|:--:|:--:|:--:|
| @small.creator | 40K | 2,000 | 5.4% | 🟢 **clean** |
| @big.account | 800K | 2,000 | 0.27% | 🔴 **flagged — bots** |

**Identical likes, opposite verdict** — because the model judges engagement
*relative to audience size*. *(Presented as an authenticity screen, not a public
accusation.)*

---

## 🧪 Why synthetic data? (stated openly — it's a strength)

> **No public dataset has campaign outcomes.** Conversions and ROI live inside
> brands' private CRMs. So we **generate** a labeled creator population calibrated
> to documented benchmarks (engagement-by-tier, ~6.6× industry ROI,
> verified-conversion uplift), with fraud injected into ~20% of profiles. We then
> validate fraud detection on *real* public accounts, where the data supports it.

***"Real profiles for realism, a benchmark-calibrated synthetic generator for
outcome labels — because no one publishes conversion data."***

---

## 📁 Project structure

```
Ratefluencer-Engine-main/
├── app.py                # Streamlit entry point + design system
├── ui/                   # 5 screens: brief → working → shortlist → detail → export
│                         #   + real_screener.py (real-account fraud screen)
├── agent/                # orchestrator · brief_parser · retriever · ranker · composer
├── models/               # ⭐ ML BRIDGE: score_creator · prepare_demo · screen_real
├── utils/                # session · env loader · ui_kit · ranking
└── data/                 # built by prepare_demo (gitignored) + real_accounts.csv

ratefluencer-copilot/proj/   # sibling Data+ML repo: src/{store,data,models}, models_store/
```

> ℹ️ Running this app needs the sibling **`ratefluencer-copilot/proj`** repo
> beside it (the ML layer the bridge imports). Without it, the UI falls back to
> demo data.

---

## 🏆 How it maps to the judging rubric

| Category | Pts | How we earn them |
|:--|:--:|:--|
| **AI / ML Innovation** | 20 | Fraud-adjusted True-Impact + anomaly detection + SHAP + embeddings |
| **Scoring Accuracy** | 20 | Precision@50 **1.000 vs 0.32**, validated on 6,000 held-out creators |
| **Viral Prediction** | 15 | ROI + success probability + growth-potential model |
| **Agent Design** | 15 | Brief → retrieve → score → rank → recommend |
| **Product Design** | 10 | Decision-first UI + the reveal |
| **Business Impact** | 10 | Quantified wasted-spend savings (fraud → poor ROI) |
| **Technical Complexity** | 5 | 5-model stack + vector search + synthetic-data engine |
| **Demo** | 5 | Rehearsed reveal + live real-account screen |

<div align="center">

---

**Built for Ratefluencer AI Hackathon 2026** · *Predict influence before it happens.*

</div>

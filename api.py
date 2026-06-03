"""
api.py — FastAPI bridge + production web server.

In DEV it serves the agent pipeline over HTTP and the Vite dev server proxies
`/api/*` here. In PROD the same process also serves the built React app
(`web/dist`) from the same origin, so the whole product is one container.

Run (dev):   py -m uvicorn api:app --reload --port 8000
Run (prod):  uvicorn api:app --host 0.0.0.0 --port 7860      # serves web/dist + /api/*

Endpoints (all under /api):
    GET  /api/health                          -> {ok, ml_available}
    POST /api/analyze  {brief, budget?, goal?} -> ranked shortlist + recommendation
    POST /api/screen   {handle, followers, ...} -> real-account authenticity screen

The models load once on first request (~40s warm-up), then responses are fast.
"""
from __future__ import annotations

import os
from pathlib import Path

# Load .env (GEMINI_API_KEY etc.) before anything reads the environment.
from utils.env import load_env
load_env()

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.brief_parser import parse_brief
from agent.retriever import get_candidates
from agent.ranker import rank_candidates, compute_composite
from agent.composer import compose_recommendation

app = FastAPI(title="Ratefluencer Copilot API")

# Allow any origin to call the API (harmless for a same-origin prod build; handy
# if you ever split the frontend onto a different host).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_BRIEF = (
    "DTC skincare brand targeting women aged 22-35 in India. Budget 300000. "
    "Goal: drive online sales. Clean, science-backed tone. New SPF serum."
)


# ── request models ───────────────────────────────────────────────────────────
class AnalyzeReq(BaseModel):
    brief: str = DEFAULT_BRIEF
    budget: int = 300000
    goal: str = "sales"
    weights: dict | None = None


class ScreenReq(BaseModel):
    handle: str = "@account"
    followers: int = 500000
    following: int = 4000
    avg_likes: float = 2000
    avg_comments: float = 30
    category: str = "skincare"
    verified: bool = False


# ── API (everything under /api so it never collides with the static app) ───────
api = APIRouter(prefix="/api")


@api.get("/health")
def health():
    try:
        from models.score_creator import ML_AVAILABLE
        return {"ok": True, "ml_available": bool(ML_AVAILABLE)}
    except Exception as e:
        return {"ok": True, "ml_available": False, "error": str(e)}


@api.post("/analyze")
def analyze(req: AnalyzeReq):
    """Full pipeline: parse -> retrieve -> score -> rank -> compose."""
    parsed = parse_brief(req.brief, budget=req.budget, goal_hint=req.goal)
    weights = req.weights or parsed.get(
        "objective_weights",
        {"impact": 0.40, "authenticity": 0.35, "match": 0.15, "cost": 0.10},
    )

    from models.score_creator import score_creator
    candidate_ids = get_candidates(parsed)
    scores: dict[str, dict] = {}
    for iid in candidate_ids:
        try:
            s = score_creator(iid, parsed_brief=parsed)
            if s:
                scores[iid] = s
        except Exception as e:
            print(f"[api] score {iid} failed: {e}")

    ranked = rank_candidates(scores, weights)
    for iid in scores:
        scores[iid].setdefault("composite", compute_composite(scores[iid], weights))

    brief_for_composer = {
        "raw": req.brief, "category": parsed.get("category"),
        "goal": parsed.get("goal"), "budget": parsed.get("budget", req.budget),
        "audience": parsed.get("target_audience", {}),
        "target_audience": parsed.get("target_audience", {}),
    }
    rec = compose_recommendation(brief_for_composer, ranked, scores)

    n_rec = sum(1 for i in ranked if scores[i].get("status") == "recommended")
    n_flag = sum(1 for i in ranked if scores[i].get("status") == "flagged")

    return {
        "parsed": parsed,
        "weights": weights,
        "ranked": [scores[iid] for iid in ranked],
        "counts": {"recommended": n_rec, "flagged": n_flag, "total": len(ranked)},
        "recommendation": rec,
    }


@api.post("/screen")
def screen(req: ScreenReq):
    """Authenticity screen for one real account (public numbers only)."""
    from models.screen_real import screen_account
    return screen_account(
        req.handle, req.followers, req.following,
        req.avg_likes, req.avg_comments, req.category, req.verified,
    )


app.include_router(api)


# ── serve the built React app (production) ─────────────────────────────────────
# In a Docker/prod build, web/dist exists and is served from "/". In local dev it
# usually doesn't (you run the Vite dev server instead), so we expose a tiny JSON
# root so `/` still responds.
_DIST = Path(__file__).resolve().parent / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="web")
else:
    @app.get("/")
    def _root():
        return {
            "service": "Ratefluencer Copilot API",
            "note": "web/dist not built — run `cd web && npm run build`, or use the Vite dev server.",
            "endpoints": ["/api/health", "POST /api/analyze", "POST /api/screen"],
        }

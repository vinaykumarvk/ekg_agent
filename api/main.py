# api/main.py
from __future__ import annotations

import json
import os
import pickle
import logging
from functools import lru_cache
from typing import Any, Dict, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from api.schemas import AskRequest, AskResponse
from api.settings import settings
from agents.ekg_agent import EKGAgent

# -----------------------------------------------------------------------------
# App & Logging
# -----------------------------------------------------------------------------
log = logging.getLogger("uvicorn.error")  # Cloud Run/uvicorn-friendly logger
app = FastAPI(title="KG Vector Response API", version="2.0.0")

# (Optional) CORS for browser callers. Adjust allow_origins for stricter policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------------------------------
# Lazy singletons
# -----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Create OpenAI client once, using env/Secret Manager-provided key."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)

@lru_cache(maxsize=1)
def load_graph_artifacts() -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """
    Load graph artifacts on first use. Keep this FAST and resilient.
    Provide whichever of (G, by_id, name_index) you actually have.
    """
    G = None
    by_id: Dict[str, Any] = {}
    name_index: Dict[str, Any] = {}

    # Example autodiscovery (override with your own loading logic)
    base_dir = os.path.dirname(os.path.dirname(__file__))  # repo root-ish
    data_dir = os.getenv("KG_DATA_DIR", os.path.join(base_dir, "..", "data", "kg"))
    try:
        g_pkl = os.path.join(data_dir, "G.pkl")
        by_id_json = os.path.join(data_dir, "by_id.json")
        name_index_json = os.path.join(data_dir, "name_index.json")

        if os.path.exists(g_pkl):
            with open(g_pkl, "rb") as f:
                G = pickle.load(f)
        if os.path.exists(by_id_json):
            with open(by_id_json, "r", encoding="utf-8") as f:
                by_id = json.load(f)
        if os.path.exists(name_index_json):
            with open(name_index_json, "r", encoding="utf-8") as f:
                name_index = json.load(f)

        # If you use a single KG_PATH file instead:
        # if settings.KG_PATH and os.path.exists(settings.KG_PATH):
        #     ... load from settings.KG_PATH ...
    except Exception as e:
        # Do not crash the server on load; we’ll report via /health and at call time.
        log.warning("KG artifact load failed: %s", e)

    return G, by_id, name_index

def get_agent(vectorstore_id: str, params: Dict[str, Any] | None = None) -> EKGAgent:
    client = get_client()
    G, by_id, name_index = load_graph_artifacts()
    return EKGAgent(
        client=client,
        vs_id=vectorstore_id,
        G=G,
        by_id=by_id,
        name_index=name_index,
        preset_params=params or {},
    )

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    G, by_id, name_index = load_graph_artifacts()
    ok = True
    err = None
    try:
        _ = get_client()
    except Exception as e:
        ok = False
        err = f"OpenAI client init failed: {e}"

    return {
        "status": "healthy" if ok else "degraded",
        "service_loaded": True,
        "available_modes": ["concise", "balanced", "deep"],
        "data_dir": os.getenv("KG_DATA_DIR", "/app/data"),
        "graph_loaded": bool(G) or (len(by_id) > 0 or len(name_index) > 0),
        "error": err,
    }

# -----------------------------------------------------------------------------
# Normalize any core/agent output to AskResponse
# -----------------------------------------------------------------------------
def _normalize_answer(res: Dict[str, Any]) -> AskResponse:
    """
    Your core may return:
      - {"markdown": "...", "sources": ..., "meta": ...}
      - {"answer": "...", "curated_chunks": ..., "model_used": ..., "export_path": ...}
      - or nested under "data": {...}
    We normalize to AskResponse.
    """
    # Try top-level first
    markdown = res.get("markdown") or res.get("answer") or ""
    sources = res.get("sources") or res.get("curated_chunks")
    meta = res.get("meta") or {
        "export_path": res.get("export_path"),
        "model": res.get("model_used"),
        "mode": res.get("mode"),
    }

    # If nothing found, try "data"
    if not markdown and isinstance(res.get("data"), dict):
        d = res["data"]
        markdown = d.get("markdown") or d.get("answer") or ""
        sources = sources or d.get("sources")
        if not meta:
            meta = d.get("meta")

    if markdown is None:
        markdown = ""

    return AskResponse(markdown=markdown, sources=sources, meta=meta)

# -----------------------------------------------------------------------------
# Main endpoint
# -----------------------------------------------------------------------------
@app.post("/v1/answer", response_model=AskResponse)
def answer(req: AskRequest) -> AskResponse:
    try:
        agent = get_agent(req.vectorstore_id, req.params)
        raw = agent.answer(req.question)  # dict from orchestrator/core

        # Normalize shapes into AskResponse
        return _normalize_answer(raw)
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.exception("Answer handler failed")
        raise HTTPException(status_code=500, detail=str(e))

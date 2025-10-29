# api/main.py
from __future__ import annotations

import json
import os
import pickle
import logging
import uuid
import asyncio
import time
from functools import lru_cache
from typing import Any, Dict, Tuple
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from api.schemas import AskRequest, AskResponse
from api.settings import settings
from agents.ekg_agent import EKGAgent

# -----------------------------------------------------------------------------
# App & Logging
# -----------------------------------------------------------------------------
# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
    ]
)

log = logging.getLogger("ekg_agent")  # Application-specific logger
app = FastAPI(title="KG Vector Response API", version="2.0.0")

# Request timeout configuration (5 minutes for deep mode)
REQUEST_TIMEOUT = 1800  # 30 minutes

# Request metrics
_request_count = 0
_response_times = []

# (Optional) CORS for browser callers. Adjust allow_origins for stricter policy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    global _request_count, _response_times
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Log request
    log.info(f"Request {request_id}: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate metrics
    process_time = time.time() - start_time
    _request_count += 1
    _response_times.append(process_time)
    
    # Keep only last 100 response times for metrics
    if len(_response_times) > 100:
        _response_times.pop(0)
    
    # Log response
    log.info(f"Request {request_id} completed: {response.status_code} in {process_time:.2f}s")
    
    return response

# -----------------------------------------------------------------------------
# Lazy singletons
# -----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    """Create OpenAI client once, using env/Secret Manager-provided key."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)

# Multi-domain KG cache: domain_id -> (G, by_id, name_index)
_KG_CACHE: Dict[str, Tuple[Any, Dict[str, Any], Dict[str, Any]]] = {}

def load_graph_artifacts(domain_id: str) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """
    Load graph artifacts for a specific domain.
    Results are cached per domain for performance.
    
    Args:
        domain_id: Domain identifier (e.g., 'wealth_management')
        
    Returns:
        Tuple of (G, by_id, name_index) for the domain
    """
    from ekg_core import load_kg_from_json
    from api.domains import get_domain
    
    # Check cache first
    if domain_id in _KG_CACHE:
        log.debug(f"Using cached KG for domain: {domain_id}")
        return _KG_CACHE[domain_id]
    
    G = None
    by_id: Dict[str, Any] = {}
    name_index: Dict[str, Any] = {}
    
    try:
        # Get domain configuration
        domain_config = get_domain(domain_id)
        kg_path = domain_config.kg_path
        
        # Resolve relative paths from project root
        if not os.path.isabs(kg_path):
            base_dir = os.path.dirname(os.path.dirname(__file__))
            kg_path = os.path.join(base_dir, kg_path)
        
        if os.path.exists(kg_path):
            log.info(f"Loading KG for domain '{domain_id}' from {kg_path}")
            G, by_id, name_index = load_kg_from_json(kg_path)
            log.info(f"✓ Loaded KG for '{domain_id}': {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(name_index)} aliases")
            
            # Cache the result
            _KG_CACHE[domain_id] = (G, by_id, name_index)
        else:
            log.warning(f"KG file not found for domain '{domain_id}': {kg_path}")
            
    except ValueError as e:
        log.error(f"Invalid domain: {e}")
    except Exception as e:
        log.error(f"KG load failed for domain '{domain_id}': {e}", exc_info=True)
    
    return G, by_id, name_index

def get_agent(domain_id: str, vectorstore_id: str, params: Dict[str, Any] | None = None) -> EKGAgent:
    """
    Create an agent for a specific domain and vector store.
    
    Args:
        domain_id: Domain identifier
        vectorstore_id: Vector store ID
        params: Optional parameters for the agent
        
    Returns:
        Configured EKGAgent instance
    """
    client = get_client()
    G, by_id, name_index = load_graph_artifacts(domain_id)
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
@app.get("/domains")
def list_available_domains():
    """List all available domains/subjects with their status"""
    from api.domains import list_domains
    
    domains_info = []
    for domain_config in list_domains():
        try:
            G, by_id, name_index = load_graph_artifacts(domain_config.domain_id)
            domains_info.append({
                "domain_id": domain_config.domain_id,
                "name": domain_config.name,
                "description": domain_config.description,
                "kg_loaded": G is not None,
                "kg_nodes": G.number_of_nodes() if G else 0,
                "kg_edges": G.number_of_edges() if G else 0,
                "default_vectorstore_id": domain_config.default_vectorstore_id,
            })
        except Exception as e:
            log.error(f"Error loading domain '{domain_config.domain_id}': {e}")
            domains_info.append({
                "domain_id": domain_config.domain_id,
                "name": domain_config.name,
                "description": domain_config.description,
                "kg_loaded": False,
                "kg_nodes": 0,
                "kg_edges": 0,
                "default_vectorstore_id": domain_config.default_vectorstore_id,
                "error": str(e),
            })
    
    return {"domains": domains_info}

@app.get("/health")
def health():
    """Health check with multi-domain status"""
    from api.domains import list_domains
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0",
        "service_loaded": True,
        "available_modes": ["concise", "balanced", "deep"],
        "domains": {},
        "errors": []
    }
    
    # Check OpenAI client
    try:
        client = get_client()
        health_status["openai_status"] = "connected"
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["openai_status"] = "error"
        health_status["errors"].append(f"OpenAI client failed: {str(e)}")
        log.error(f"OpenAI client health check failed: {e}")
    
    # Check each domain
    for domain_config in list_domains():
        try:
            G, by_id, name_index = load_graph_artifacts(domain_config.domain_id)
            health_status["domains"][domain_config.domain_id] = {
                "loaded": G is not None,
                "nodes": G.number_of_nodes() if G else 0,
                "edges": G.number_of_edges() if G else 0,
                "aliases": len(name_index) if name_index else 0,
                "status": "healthy" if G else "error"
            }
        except Exception as e:
            health_status["domains"][domain_config.domain_id] = {
                "loaded": False,
                "nodes": 0,
                "edges": 0,
                "aliases": 0,
                "status": "error",
                "error": str(e)
            }
            health_status["errors"].append(f"Domain {domain_config.domain_id} failed: {str(e)}")
            log.error(f"Domain {domain_config.domain_id} health check failed: {e}")
    
    # Check cache status
    try:
        from ekg_core.core import _Q_CACHE, _HITS_CACHE
        health_status["cache_status"] = {
            "query_cache_size": _Q_CACHE.size(),
            "hits_cache_size": _HITS_CACHE.size()
        }
    except Exception as e:
        health_status["cache_status"] = {"error": str(e)}
        log.warning(f"Cache status check failed: {e}")
    
    # Determine overall status
    if health_status["status"] == "healthy" and any(
        domain.get("status") == "error" for domain in health_status["domains"].values()
    ):
        health_status["status"] = "degraded"
    
    return health_status

@app.get("/metrics")
def metrics():
    """Application metrics endpoint"""
    global _request_count, _response_times
    
    avg_response_time = sum(_response_times) / len(_response_times) if _response_times else 0
    max_response_time = max(_response_times) if _response_times else 0
    min_response_time = min(_response_times) if _response_times else 0
    
    return {
        "total_requests": _request_count,
        "response_times": {
            "average": round(avg_response_time, 2),
            "max": round(max_response_time, 2),
            "min": round(min_response_time, 2),
            "count": len(_response_times)
        },
        "cache_status": {
            "query_cache_size": _Q_CACHE.size() if '_Q_CACHE' in globals() else 0,
            "hits_cache_size": _HITS_CACHE.size() if '_HITS_CACHE' in globals() else 0
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# -----------------------------------------------------------------------------
# Normalize any core/agent output to AskResponse
# -----------------------------------------------------------------------------
def _normalize_answer(res: Dict[str, Any], response_id: str) -> AskResponse:
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
        "mode": res.get("mode") or res.get("_mode"),
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

    return AskResponse(response_id=response_id, markdown=markdown, sources=sources, meta=meta)

# -----------------------------------------------------------------------------
# Main endpoint
# -----------------------------------------------------------------------------
@app.post("/v1/answer", response_model=AskResponse)
def answer(req: AskRequest) -> AskResponse:
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        log.info(f"Processing request {request_id} for domain {req.domain}")
        
        from api.domains import get_domain
        
        # Get domain configuration
        try:
            domain_config = get_domain(req.domain)
        except ValueError as e:
            log.warning(f"Invalid domain {req.domain}: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid domain: {str(e)}")
        
        # Use request vectorstore_id or domain default
        vectorstore_id = req.vectorstore_id or domain_config.default_vectorstore_id
        if not vectorstore_id:
            log.error(f"No vector store for domain {req.domain}")
            raise HTTPException(
                status_code=400,
                detail=f"No vector store specified for domain '{req.domain}'. "
                       f"Please provide vectorstore_id in request or configure default for domain."
            )
        
        # Generate unique response ID (use provided one or create new)
        response_id = req.response_id or req.conversation_id or str(uuid.uuid4())
        
        # Create agent for this domain + vector store
        # Merge user params with preset parameters
        from ekg_core.core import get_preset
        mode = req.params.get("_mode", "balanced") if req.params else "balanced"
        preset_params = get_preset(mode)
        if req.params:
            preset_params.update(req.params)  # User params override preset
        
        log.info(f"Creating agent for domain {req.domain}, mode {mode}")
        agent = get_agent(req.domain, vectorstore_id, preset_params)
        
        # Enhance question with conversational context if response_id provided
        enhanced_question = req.question
        if req.response_id or req.conversation_id:
            # Add conversational context to the question
            enhanced_question = f"Previous context ID: {response_id}\n\nQuestion: {req.question}"
        
        # Execute with timeout
        log.info(f"Executing agent.answer for request {request_id}")
        try:
            raw = agent.answer(enhanced_question)  # dict from orchestrator/core
        except Exception as e:
            log.error(f"Agent execution failed for request {request_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to generate answer")
        
        # Add domain info to metadata
        if "meta" not in raw or raw["meta"] is None:
            raw["meta"] = {}
        raw["meta"]["domain"] = req.domain
        raw["meta"]["vectorstore_id"] = vectorstore_id
        raw["meta"]["response_id"] = response_id
        raw["meta"]["is_conversational"] = bool(req.response_id or req.conversation_id)
        raw["meta"]["mode"] = mode  # Add mode information
        if req.response_id:
            raw["meta"]["previous_response_id"] = req.response_id
        if req.conversation_id:
            raw["meta"]["conversation_id"] = req.conversation_id

        # Add timing information
        processing_time = time.time() - start_time
        raw["meta"]["processing_time_seconds"] = round(processing_time, 2)
        raw["meta"]["request_id"] = request_id
        
        log.info(f"Request {request_id} completed in {processing_time:.2f}s")
        
        # Normalize shapes into AskResponse
        return _normalize_answer(raw, response_id)
        
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.error(f"Unexpected error in request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

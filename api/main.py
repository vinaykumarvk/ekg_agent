# api/main.py
from __future__ import annotations

import json
import os
import pickle
import logging
import uuid
import time
import asyncio
from functools import lru_cache
from typing import Any, Dict, Tuple, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI

from api.schemas import AskRequest, AskResponse, TaskInfo, TaskListResponse, TaskStatusResponse
from api.settings import settings
from agents.ekg_agent import EKGAgent
from ekg_core.v2_workflow import parse_llm_json, extract_output_text
from api.task_store import get_task_store, TaskStore

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
REQUEST_TIMEOUT = 300  # 5 minutes

# Request metrics
_request_count = 0
_response_times = []

# Thread pool for background task execution
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="ekg_task_")

# CORS configuration - configurable via CORS_ORIGINS env var
# For production, set CORS_ORIGINS to specific domains (comma-separated) instead of "*"
cors_origins_str = getattr(settings, 'CORS_ORIGINS', '*')
cors_origins = ["*"] if cors_origins_str == "*" else [origin.strip() for origin in cors_origins_str.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
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
    Load graph artifacts for a specific domain from GCS.
    
    IMPORTANT: Only GCS paths (gs://bucket/path) are supported.
    All KG files must be stored in Google Cloud Storage.
    
    Args:
        domain_id: Domain identifier (e.g., 'wealth_management')
        
    Returns:
        Tuple of (G, by_id, name_index) for the domain
        
    Raises:
        ValueError: If kg_path is not a valid GCS path
        ImportError: If google-cloud-storage is not installed
    """
    from ekg_core import load_kg_from_json
    from api.domains import get_domain
    from google.cloud import storage
    import tempfile
    
    # Check cache first
    if domain_id in _KG_CACHE:
        log.debug(f"Using cached KG for domain: {domain_id}")
        return _KG_CACHE[domain_id]
    
    # Get domain configuration
    domain_config = get_domain(domain_id)
    kg_path = domain_config.kg_path
    
    # Validate GCS path - NO LOCAL FALLBACK
    if not kg_path.startswith("gs://"):
        raise ValueError(
            f"Invalid KG path for domain '{domain_id}': '{kg_path}'. "
            f"Only GCS paths (gs://bucket/path) are supported. "
            f"Set {domain_id.upper()}_KG_PATH environment variable to a valid GCS path."
        )
    
    log.info(f"Loading KG for domain '{domain_id}' from GCS: {kg_path}")
    
    # Parse GCS path: gs://bucket-name/path/to/file.json
    path_parts = kg_path[5:].split("/", 1)  # Remove "gs://" prefix
    if len(path_parts) != 2:
        raise ValueError(f"Invalid GCS path format: {kg_path}. Expected: gs://bucket-name/path/to/file.json")
    
    bucket_name = path_parts[0]
    blob_name = path_parts[1]
    
    # Initialize GCS client (uses default credentials or service account)
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Download to temporary file
    with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as tmp_file:
        blob.download_to_filename(tmp_file.name)
        tmp_path = tmp_file.name
    
    log.info(f"Downloaded KG from GCS to temporary file: {tmp_path}")
    
    try:
        G, by_id, name_index = load_kg_from_json(tmp_path)
    finally:
        # Always clean up temporary file
        os.unlink(tmp_path)
    
    log.info(f"✓ Loaded KG for '{domain_id}' from GCS: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(name_index)} aliases")
    
    # Cache the result
    _KG_CACHE[domain_id] = (G, by_id, name_index)
    
    return G, by_id, name_index

def get_agent(domain_id: str, vectorstore_id: str, kg_vectorstore_id: str = None, params: Dict[str, Any] | None = None) -> EKGAgent:
    """
    Create an agent for a specific domain and vector store.
    
    Args:
        domain_id: Domain identifier
        vectorstore_id: Document vector store ID
        kg_vectorstore_id: KG vector store ID (for V2 semantic discovery)
        params: Optional parameters for the agent
        
    Returns:
        Configured EKGAgent instance (V2 workflow)
    """
    import os
    client = get_client()
    G, by_id, name_index = load_graph_artifacts(domain_id)
    
    # Get KG vector store ID from param, env var, or settings
    kg_vs_id = kg_vectorstore_id or os.getenv("KG_VECTOR_STORE_ID")
    
    log.info(f"Creating V2 agent: doc_vs={vectorstore_id}, kg_vs={kg_vs_id}")
    
    return EKGAgent(
        client=client,
        vs_id=vectorstore_id,
        kg_vs_id=kg_vs_id,  # V2: Pass KG vector store ID
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


def _build_status_meta(task_id: str, status: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Helper to standardize background task metadata."""
    meta = {
        "background_task_id": task_id,
        "background_status": status or "unknown",
        "background_status_endpoint": f"/v1/answer/status/{task_id}",
    }
    if model:
        meta["model"] = model
    return meta


# -----------------------------------------------------------------------------
# Background Task Processing
# -----------------------------------------------------------------------------
def _process_task_in_background(task_id: str, question: str, domain: str, mode: str, 
                                 vectorstore_id: str, kg_vectorstore_id: str):
    """
    Process a task in background thread.
    Updates task status in SQLite store.
    """
    task_store = get_task_store()
    
    try:
        # Update status to processing
        task_store.update_status(task_id, TaskStore.STATUS_PROCESSING)
        log.info(f"Background task {task_id} started processing")
        
        # Get preset params
        from ekg_core.core import get_preset
        preset_params = get_preset(mode)
        preset_params["_response_id"] = task_id
        preset_params["_domain"] = domain
        
        # Create agent and execute
        agent = get_agent(domain, vectorstore_id, kg_vectorstore_id, preset_params)
        raw = agent.answer(question)
        
        # Build result
        result = {
            "response_id": task_id,
            "markdown": raw.get("markdown") or raw.get("answer") or "",
            "sources": raw.get("sources") or raw.get("curated_chunks"),
            "meta": raw.get("meta", {})
        }
        result["meta"]["domain"] = domain
        result["meta"]["mode"] = mode
        result["meta"]["task_id"] = task_id
        
        # Update status to completed with result
        task_store.update_status(task_id, TaskStore.STATUS_COMPLETED, result=result)
        log.info(f"Background task {task_id} completed successfully")
        
    except Exception as e:
        log.error(f"Background task {task_id} failed: {e}", exc_info=True)
        task_store.update_status(task_id, TaskStore.STATUS_FAILED, error=str(e))


@app.get("/v1/tasks", response_model=TaskListResponse)
def list_tasks(status: Optional[str] = None, limit: int = 50, offset: int = 0):
    """
    List all tasks, optionally filtered by status.
    
    Args:
        status: Filter by status (queued, processing, completed, failed)
        limit: Max tasks to return (default 50)
        offset: Pagination offset
    """
    task_store = get_task_store()
    
    tasks = task_store.list_tasks(status=status, limit=limit, offset=offset)
    stats = task_store.get_stats()
    
    return TaskListResponse(
        tasks=[TaskInfo(**task) for task in tasks],
        total=stats.get("total", 0),
        stats=stats
    )


@app.get("/v1/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """
    Get detailed status of a specific task.
    Returns full result if completed.
    """
    task_store = get_task_store()
    task = task_store.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Build response
    response = TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        question=task["question"],
        domain=task["domain"],
        mode=task["mode"],
        created_at=task["created_at"],
        error=task.get("error")
    )
    
    # Include result if completed
    if task["status"] == TaskStore.STATUS_COMPLETED and task.get("result"):
        result = task["result"]
        response.result = AskResponse(
            response_id=result.get("response_id", task_id),
            markdown=result.get("markdown"),
            json_data=result.get("json_data"),
            sources=result.get("sources"),
            meta=result.get("meta")
        )
    
    return response


@app.delete("/v1/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task."""
    task_store = get_task_store()
    
    if not task_store.delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return {"message": f"Task {task_id} deleted", "task_id": task_id}


@app.get("/v1/answer/status/{task_id}", response_model=AskResponse)
def get_answer_status(task_id: str) -> AskResponse:
    """
    Poll the status of a task.
    First checks our SQLite task store, then falls back to OpenAI for deep mode tasks.
    """
    # First, check our task store
    task_store = get_task_store()
    task = task_store.get_task(task_id)
    
    if task:
        status = task["status"]
        meta = _build_status_meta(task_id, status)
        meta["domain"] = task["domain"]
        meta["mode"] = task["mode"]
        
        if status == TaskStore.STATUS_COMPLETED and task.get("result"):
            result = task["result"]
            return AskResponse(
                response_id=task_id,
                markdown=result.get("markdown", ""),
                json_data=result.get("json_data"),
                sources=result.get("sources"),
                meta={**meta, **result.get("meta", {})}
            )
        elif status == TaskStore.STATUS_FAILED:
            return AskResponse(
                response_id=task_id,
                markdown=f"Task failed: {task.get('error', 'Unknown error')}",
                meta=meta
            )
        else:
            return AskResponse(
                response_id=task_id,
                markdown=f"Task is {status}. Question: {task['question'][:100]}...",
                meta=meta
            )
    
    # Fallback: Check OpenAI for deep mode background tasks
    try:
        client = get_client()
        resp = client.responses.retrieve(task_id)
    except Exception as e:
        log.error(f"Failed to retrieve status for task {task_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    status = getattr(resp, "status", "unknown")
    meta = _build_status_meta(task_id, status, getattr(resp, "model", None))

    if status != "completed":
        return AskResponse(
            response_id=task_id,
            markdown=f"Task {task_id} is {status or 'in_progress'}.",
            meta=meta,
        )

    output_text = extract_output_text(resp)
    parsed = parse_llm_json(output_text) if output_text else {}
    markdown = parsed.get("answer") if isinstance(parsed, dict) and parsed else output_text

    return AskResponse(
        response_id=task_id,
        markdown=markdown or "",
        json_data=parsed or None,
        meta=meta,
    )

# -----------------------------------------------------------------------------
# Main endpoint
# -----------------------------------------------------------------------------
@app.post("/v1/answer", response_model=AskResponse)
def answer(req: AskRequest, background_tasks: BackgroundTasks) -> AskResponse:
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        log.info(f"Processing request {request_id} for domain {req.domain}" + 
                 (" (async)" if req.async_mode else ""))
        
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
        
        # Get mode from params
        from ekg_core.core import get_preset
        mode = req.params.get("_mode", "balanced") if req.params else "balanced"
        
        # V2 Workflow: Get KG vector store ID for semantic discovery
        kg_vectorstore_id = os.getenv("KG_VECTOR_STORE_ID")
        
        # =======================================================================
        # ASYNC MODE: Queue task and return immediately
        # =======================================================================
        if req.async_mode:
            task_store = get_task_store()
            task_id = task_store.create_task(
                question=req.question,
                domain=req.domain,
                mode=mode
            )
            
            # Submit to thread pool for background processing
            _executor.submit(
                _process_task_in_background,
                task_id,
                req.question,
                req.domain,
                mode,
                vectorstore_id,
                kg_vectorstore_id
            )
            
            log.info(f"Task {task_id} queued for background processing")
            
            return AskResponse(
                response_id=task_id,
                markdown=f"Task queued successfully. Check status at /v1/tasks/{task_id}",
                meta={
                    "task_id": task_id,
                    "status": "queued",
                    "async_mode": True,
                    "status_endpoint": f"/v1/tasks/{task_id}",
                    "domain": req.domain,
                    "mode": mode,
                    "question": req.question[:100] + "..." if len(req.question) > 100 else req.question
                }
            )
        
        # =======================================================================
        # SYNC MODE: Process immediately and return result
        # =======================================================================
        # Generate unique response ID (use provided one or create new)
        response_id = req.response_id or req.conversation_id or str(uuid.uuid4())
        
        # Create agent for this domain + vector store
        # Merge user params with preset parameters
        preset_params = get_preset(mode)
        if req.params:
            preset_params.update(req.params)  # User params override preset
        # Pass along context for downstream metadata
        preset_params["_response_id"] = response_id
        preset_params["_domain"] = req.domain
        
        log.info(f"Creating V2 agent for domain {req.domain}, mode {mode}")
        log.info(f"  doc_vector_store={vectorstore_id}")
        log.info(f"  kg_vector_store={kg_vectorstore_id}")
        
        agent = get_agent(req.domain, vectorstore_id, kg_vectorstore_id, preset_params)
        
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

        # Handle background task metadata for deep mode
        background_task_id = raw["meta"].get("background_task_id")
        response_id_to_use = background_task_id or response_id
        if background_task_id:
            raw["meta"]["client_response_id"] = response_id
            raw["meta"]["background_status_endpoint"] = f"/v1/answer/status/{background_task_id}"

        # Add timing information
        processing_time = time.time() - start_time
        raw["meta"]["processing_time_seconds"] = round(processing_time, 2)
        raw["meta"]["request_id"] = request_id
        
        log.info(f"Request {request_id} completed in {processing_time:.2f}s")
        
        # Normalize shapes into AskResponse
        return _normalize_answer(raw, response_id_to_use)
        
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.error(f"Unexpected error in request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

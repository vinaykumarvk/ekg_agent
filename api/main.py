# api/main.py
from __future__ import annotations

import json
import os
import pickle
import logging
import uuid
import asyncio
import time
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Tuple, List
from datetime import datetime

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Form,
    UploadFile,
    File,
    status,
    RequestValidationError,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from openai import OpenAI

from api.schemas import (
    AskRequest,
    AskResponse,
    VectorStoreUploadResponse,
    GoogleDriveIngestRequest,
    StructuredAnswerRequest,
    StructuredAnswerResponse,
    WebSearchRequest,
    WebSearchResponse,
)
from api.settings import settings
from api.security import (
    verify_password,
    generate_session_identifier,
    generate_csrf_token,
)
from api.vector_store import (
    ingest_file,
    persist_upload,
    REGISTRY,
    MAX_FILE_SIZE_BYTES,
)
from api.google_drive import drive_client, extract_folder_id
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

# Add validation error handler for better error messages
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors and return detailed error messages"""
    errors = []
    for error in exc.errors():
        field = " -> ".join(str(loc) for loc in error.get("loc", []))
        msg = error.get("msg", "Validation error")
        error_type = error.get("type", "unknown")
        errors.append({
            "field": field,
            "message": msg,
            "type": error_type
        })
    
    log.warning(f"Validation error on {request.url.path}: {errors}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors,
            "body": exc.body if hasattr(exc, 'body') else None
        }
    )

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path(settings.CACHE_DIR) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET_KEY,
    session_cookie=settings.SESSION_COOKIE_NAME,
    https_only=settings.SESSION_COOKIE_SECURE,
    same_site=settings.SESSION_COOKIE_SAMESITE,
)

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


def humanize_bytes(value: int) -> str:
    units = ["bytes", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} bytes"


templates.env.globals.update(
    max_file_size=MAX_FILE_SIZE_BYTES,
    app_name="EKG Vector Store Admin",
    is_authenticated=is_authenticated,
)
templates.env.filters["human_bytes"] = humanize_bytes

SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "geolocation=()",
    "Content-Security-Policy": "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:",
}


def apply_security_headers(response):
    for key, value in SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


def ensure_session(request: Request) -> None:
    if "session_id" not in request.session:
        request.session["session_id"] = generate_session_identifier()


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted_token: str | None) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_authenticated"))


def render_template(name: str, request: Request, context: dict[str, Any]):
    response = templates.TemplateResponse(name, context)
    return apply_security_headers(response)

# Request timeout configuration (30 minutes for deep mode)
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
# Admin web experience
# -----------------------------------------------------------------------------


@app.get("/admin/login", response_class=HTMLResponse)
async def login_get(request: Request):
    ensure_session(request)
    if is_authenticated(request):
        response = RedirectResponse(url="/admin/ekg", status_code=status.HTTP_303_SEE_OTHER)
        return apply_security_headers(response)

    context = {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "max_file_size": MAX_FILE_SIZE_BYTES,
        "error": None,
    }
    return render_template("login.html", request, context)


@app.post("/admin/login", response_class=HTMLResponse)
async def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
):
    ensure_session(request)
    validate_csrf(request, csrf_token)

    if (
        secrets.compare_digest(username.strip(), settings.ADMIN_USERNAME)
        and verify_password(password, settings.ADMIN_PASSWORD_HASH)
    ):
        request.session["is_authenticated"] = True
        request.session["authenticated_at"] = datetime.utcnow().isoformat()
        request.session["csrf_token"] = generate_csrf_token()
        response = RedirectResponse(url="/admin/ekg", status_code=status.HTTP_303_SEE_OTHER)
        return apply_security_headers(response)

    context = {
        "request": request,
        "csrf_token": get_csrf_token(request),
        "error": "Invalid credentials",
        "max_file_size": MAX_FILE_SIZE_BYTES,
    }
    response = render_template("login.html", request, context)
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return response


@app.post("/admin/logout")
async def logout_post(request: Request, csrf_token: str = Form(...)):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    validate_csrf(request, csrf_token)
    request.session.clear()
    response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
    return apply_security_headers(response)


@app.get("/admin/ekg", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    ensure_session(request)
    if not is_authenticated(request):
        response = RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
        return apply_security_headers(response)

    records = await REGISTRY.list_records()
    context = {
        "request": request,
        "records": records,
        "csrf_token": get_csrf_token(request),
        "max_file_size": MAX_FILE_SIZE_BYTES,
    }
    return render_template("admin_dashboard.html", request, context)


@app.post("/admin/vector-store/upload", response_model=VectorStoreUploadResponse)
async def upload_vector_store_file(
    request: Request,
    vector_store_name: str = Form(...),
    csrf_token: str = Form(...),
    file: UploadFile = File(...),
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    validate_csrf(request, csrf_token)

    try:
        client = get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    temp_path, _, sanitized_name = await persist_upload(file, UPLOAD_DIR)
    try:
        stored, vector_store_id = await ingest_file(
            client=client,
            vector_store_name=vector_store_name,
            file_path=temp_path,
            original_filename=sanitized_name,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    return VectorStoreUploadResponse(
        vector_store_id=vector_store_id,
        file_id=stored.file_id,
        filename=stored.filename,
        size_bytes=stored.size_bytes,
    )


@app.get("/admin/google-drive/files")
async def google_drive_files(request: Request, folder_link: str):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")
    folder_id = extract_folder_id(folder_link)
    files = await drive_client.list_folder(folder_id)

    allowed_files = [
        file
        for file in files
        if file.mime_type in settings.GOOGLE_ALLOWED_MIME_TYPES
        and file.size <= MAX_FILE_SIZE_BYTES
        and file.size > 0
    ]
    return {
        "folderId": folder_id,
        "files": [
            {
                "id": file.id,
                "name": file.name,
                "mimeType": file.mime_type,
                "size": file.size,
                "modifiedTime": file.modified_time,
            }
            for file in allowed_files
        ]
    }


@app.post("/admin/google-drive/ingest", response_model=List[VectorStoreUploadResponse])
async def google_drive_ingest(
    request: Request,
    payload: GoogleDriveIngestRequest,
):
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="Not authenticated")

    header_token = request.headers.get("X-CSRF-Token")
    validate_csrf(request, header_token)

    if not payload.file_ids:
        raise HTTPException(status_code=400, detail="No files selected")

    try:
        client = get_client()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    responses: List[VectorStoreUploadResponse] = []

    for file_id in payload.file_ids:
        temp_path = UPLOAD_DIR / f"drive_{file_id}_{uuid.uuid4().hex}"
        downloaded_path, _, filename = await drive_client.download_file(file_id, temp_path)
        try:
            stored, vector_store_id = await ingest_file(
                client=client,
                vector_store_name=payload.vector_store_name,
                file_path=downloaded_path,
                original_filename=filename,
            )
            responses.append(
                VectorStoreUploadResponse(
                    vector_store_id=vector_store_id,
                    file_id=stored.file_id,
                    filename=stored.filename,
                    size_bytes=stored.size_bytes,
                )
            )
        finally:
            downloaded_path.unlink(missing_ok=True)

    return responses


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
def _normalize_answer(res: Dict[str, Any], response_id: str, output_format: str = "markdown") -> AskResponse:
    """
    Your core may return:
      - {"markdown": "...", "sources": ..., "meta": ...}
      - {"answer": "...", "curated_chunks": ..., "model_used": ..., "export_path": ...}
      - {"json_data": {...}, "answer": "..."} for structured responses
      - or nested under "data": {...}
    We normalize to AskResponse.
    """
    # Try top-level first
    markdown = res.get("markdown") or res.get("answer") or ""
    json_data = res.get("json_data")
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
        json_data = json_data or d.get("json_data")
        sources = sources or d.get("sources")
        if not meta:
            meta = d.get("meta")

    if markdown is None:
        markdown = ""

    # Return appropriate format
    if output_format == "json" and json_data:
        return AskResponse(
            response_id=response_id,
            markdown=None,
            json_data=json_data,
            sources=sources,
            meta=meta
        )
    else:
        return AskResponse(
            response_id=response_id,
            markdown=markdown,
            json_data=json_data if output_format == "json" else None,
            sources=sources,
            meta=meta
        )

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
        
        # Handle regular string question (backward compatible - no structured input here)
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
        return _normalize_answer(raw, response_id, output_format=req.output_format)
        
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.error(f"Unexpected error in request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------
# Structured Answer Endpoint (New)
# -----------------------------------------------------------------------------
@app.post("/v1/answer-structured", response_model=StructuredAnswerResponse)
def answer_structured(req: StructuredAnswerRequest) -> StructuredAnswerResponse:
    """
    New endpoint specifically for structured input with custom system prompts.
    This endpoint is designed for complex workflows like internal capabilities analysis.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        log.info(f"Processing structured request {request_id} for domain {req.domain}")
        
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
        
        # Generate unique response ID
        response_id = str(uuid.uuid4())
        
        # Create agent for this domain + vector store
        # Merge user params with preset parameters
        from ekg_core.core import get_preset
        mode = req.params.get("_mode", "balanced") if req.params else "balanced"
        preset_params = get_preset(mode)
        if req.params:
            preset_params.update(req.params)  # User params override preset
        
        log.info(f"Creating agent for domain {req.domain}, mode {mode}")
        agent = get_agent(req.domain, vectorstore_id, preset_params)
        
        # Convert StructuredQuestionPayload to dict for agent
        question_payload_dict = {
            "system_prompt": req.question_payload.system_prompt,
            "requirement": req.question_payload.requirement,
            "bank_profile": req.question_payload.bank_profile or {},
            "market_subrequirements": req.question_payload.market_subrequirements or []
        }
        
        # Handle structured input
        log.info(f"Processing structured input for request {request_id}")
        try:
            raw = agent.answer_structured(question_payload_dict)
        except Exception as e:
            log.error(f"Structured answer execution failed for request {request_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate structured answer: {str(e)}")
        
        # Add domain info to metadata
        if "meta" not in raw or raw["meta"] is None:
            raw["meta"] = {}
        raw["meta"]["domain"] = req.domain
        raw["meta"]["vectorstore_id"] = vectorstore_id
        raw["meta"]["response_id"] = response_id
        raw["meta"]["mode"] = mode
        
        # Add timing information
        processing_time = time.time() - start_time
        raw["meta"]["processing_time_seconds"] = round(processing_time, 2)
        raw["meta"]["request_id"] = request_id
        
        log.info(f"Structured request {request_id} completed in {processing_time:.2f}s")
        
        # Extract JSON data and answer
        json_data = raw.get("json_data")
        answer_text = raw.get("answer", "")
        sources = raw.get("curated_chunks") or raw.get("sources")
        
        return StructuredAnswerResponse(
            response_id=response_id,
            json_data=json_data,
            answer=answer_text if not json_data else None,  # Only include answer if JSON parsing failed
            sources=sources,
            meta=raw.get("meta")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.error(f"Unexpected error in structured request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# -----------------------------------------------------------------------------
# Web Search / Market Requirements Endpoint
# -----------------------------------------------------------------------------
@app.post("/req_desc_web_search", response_model=WebSearchResponse)
def req_desc_web_search(req: WebSearchRequest) -> WebSearchResponse:
    """
    Endpoint for decomposing requirements into market subrequirements.
    Uses web search to research market-standard expectations.
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    try:
        log.info(f"Processing web search request {request_id} for requirement: {req.requirement[:100]}...")
        
        # Generate unique response ID
        response_id = str(uuid.uuid4())
        
        # Get OpenAI client
        client = get_client()
        
        # Build WEB_SEARCH_SYSTEM_PROMPT
        profile = req.profile or {}
        WEB_SEARCH_SYSTEM_PROMPT = f"""
You are a Wealth Management Product Analyst researching market-standard expectations for a given requirement.

INPUT

You receive:

requirement: {req.requirement}

profile: {json.dumps(profile, indent=2, ensure_ascii=False) if profile else "{}"}

TASK

Holistic framing

First, step back and interpret the requirement in its broader business context
(customer segment, products, channels, regulatory environment, and the profile).

Decomposition

Decompose the requirement into a set of upto 10 non-overlapping subrequirements that,
together, fully cover the requirement from a modern wealth-platform perspective.

Market enrichment

Use web search to infer what modern wealth management platforms typically provide
for each of these subrequirements for similar banks.

Focus on capabilities and sub-features, not vendor names or specific products.

OUTPUT (JSON ONLY, NO PROSE, NO MARKDOWN)

Return a single JSON object with this shape:

{{
"market_subrequirements": [
  {{
    "id": "M1",
    "title": "Short name of the subrequirement",
    "description": "1–3 sentence description of what the platform should do",
    "priority": "must_have" | "nice_to_have"
  }},
  ...
]
}}

RULES

Return between 3 and 10 subrequirements.

Provide description of each subrequirment in <= 100 words. 

Make subrequirements non-overlapping and reasonably granular.

Keep them vendor-agnostic (generic capability statements).

Do NOT include any text outside the JSON object.
"""
        
        # Build user message
        user_msg = json.dumps({
            "requirement": req.requirement,
        }, indent=2, ensure_ascii=False)
        
        # Build the API payload
        api_payload = {
            "model": req.model,
            "input": [
                {"role": "system", "content": WEB_SEARCH_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            "tools": [{
                "type": "file_search",
            }]
        }
        
        # Log the exact payload being sent
        log.info(f"API Payload for request {request_id}:")
        log.info(f"  Model: {api_payload['model']}")
        log.info(f"  System message length: {len(api_payload['input'][0]['content'])} chars")
        log.info(f"  User message: {api_payload['input'][1]['content'][:200]}...")
        log.info(f"  Tools: {api_payload['tools']}")
        
        # Call LLM with web search (file_search tool)
        log.info(f"Calling LLM with model {req.model} and file_search tool for request {request_id}")
        try:
            resp = client.responses.create(**api_payload)
            answer = getattr(resp, "output_text", None) or getattr(resp, "output_texts", [""])[0]
        except Exception as e:
            log.error(f"LLM call failed for request {request_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")
        
        # Parse JSON from answer
        json_data = None
        answer_text = answer
        
        try:
            # Try to extract JSON from markdown code blocks
            if "```json" in answer:
                json_start = answer.find("```json") + 7
                json_end = answer.find("```", json_start)
                json_str = answer[json_start:json_end].strip()
                json_data = json.loads(json_str)
            elif "```" in answer:
                json_start = answer.find("```") + 3
                json_end = answer.find("```", json_start)
                json_str = answer[json_start:json_end].strip()
                json_data = json.loads(json_str)
            else:
                # Try parsing the entire answer as JSON
                json_data = json.loads(answer.strip())
        except (json.JSONDecodeError, ValueError) as e:
            log.warning(f"JSON parsing failed for request {request_id}: {e}")
            # Keep answer_text for debugging
            pass
        
        # Add timing information
        processing_time = time.time() - start_time
        
        meta = {
            "response_id": response_id,
            "model": req.model,
            "processing_time_seconds": round(processing_time, 2),
            "request_id": request_id
        }
        
        log.info(f"Web search request {request_id} completed in {processing_time:.2f}s")
        
        return WebSearchResponse(
            response_id=response_id,
            json_data=json_data,
            answer=answer_text if not json_data else None,
            sources=None,  # Web search doesn't return sources in the same way
            meta=meta
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Surface a clean 500 with message; full stacks remain in logs
        log.error(f"Unexpected error in web search request {request_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

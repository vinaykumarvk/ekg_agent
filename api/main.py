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
from pathlib import Path
from typing import Any, Dict, Tuple, List, Optional
from datetime import datetime

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Form,
    UploadFile,
    File,
    status,
)
from fastapi.exceptions import RequestValidationError
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


def ensure_session(request: Request) -> None:
    if "session_id" not in request.session:
        request.session["session_id"] = generate_session_identifier()


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = generate_csrf_token()
        request.session["csrf_token"] = token
    return token


def validate_csrf(request: Request, submitted_token: Optional[str]) -> None:
    expected = request.session.get("csrf_token")
    if not expected or not submitted_token or not secrets.compare_digest(expected, submitted_token):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("is_authenticated"))


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


def render_template(name: str, request: Request, context: dict[str, Any]):
    response = templates.TemplateResponse(name, context)
    return apply_security_headers(response)

# Request timeout configuration (20 minutes)
REQUEST_TIMEOUT = 1200  # 20 minutes

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
def get_client() -> OpenAI:
    """Create OpenAI client using env/Secret Manager-provided key."""
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _download_from_gcs(gcs_path: str, local_path: str) -> bool:
    """
    Download a file from Google Cloud Storage.
    
    Args:
        gcs_path: GCS path in format gs://bucket/path/to/file
        local_path: Local path to save the file
        
    Returns:
        True if download successful, False otherwise
    """
    try:
        from google.cloud import storage
        
        # Parse gs://bucket/path format
        if not gcs_path.startswith("gs://"):
            log.error(f"Invalid GCS path format: {gcs_path}")
            return False
        
        path_parts = gcs_path[5:].split("/", 1)
        if len(path_parts) != 2:
            log.error(f"Invalid GCS path format: {gcs_path}")
            return False
        
        bucket_name, blob_path = path_parts
        
        log.info(f"Downloading KG from GCS: {gcs_path}")
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Ensure local directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        blob.download_to_filename(local_path)
        log.info(f"✓ Downloaded KG from GCS to {local_path}")
        return True
        
    except ImportError:
        log.warning("google-cloud-storage not installed, cannot download from GCS")
        return False
    except Exception as e:
        log.error(f"Failed to download from GCS: {e}")
        return False


def load_graph_artifacts(domain_id: str) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """
    Load graph artifacts for a specific domain.
    Supports both local files and Google Cloud Storage (gs:// paths).
    Always loads fresh - no caching.
    
    Args:
        domain_id: Domain identifier (e.g., 'wealth_management')
        
    Returns:
        Tuple of (G, by_id, name_index) for the domain
        
    Raises:
        ValueError: If domain_id is invalid
        FileNotFoundError: If KG file is not found
        RuntimeError: If GCS download fails
    """
    from ekg_core import load_kg_from_json
    from api.domains import get_domain
    
    # Get domain configuration
    domain_config = get_domain(domain_id)
    # Use dynamic getter to read env vars at runtime
    kg_path = domain_config.get_kg_path()
    
    if not kg_path:
        raise ValueError(f"KG path not configured for domain '{domain_id}'. Set {domain_id.upper()}_KG_PATH environment variable.")
    
    # Handle GCS paths (gs://bucket/path)
    if kg_path.startswith("gs://"):
        # Cache downloaded files to avoid re-downloading on every request
        # File cache: keep downloaded file, but still load graph fresh each time
        import tempfile
        import hashlib
        cache_dir = Path(tempfile.gettempdir()) / "ekg_kg_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Create stable cache key from GCS path
        cache_key = hashlib.md5(kg_path.encode()).hexdigest()
        local_path = cache_dir / f"{domain_id}_kg_{cache_key}.json"
        
        # Re-download if file doesn't exist or is older than 1 hour
        # This balances freshness with performance
        CACHE_MAX_AGE = 3600  # 1 hour in seconds
        should_download = True
        
        if local_path.exists():
            file_age = time.time() - local_path.stat().st_mtime
            if file_age < CACHE_MAX_AGE:
                should_download = False
                log.debug(f"Using cached KG file for {domain_id} (age: {file_age:.0f}s)")
        
        if should_download:
            log.info(f"Downloading KG from GCS for {domain_id}: {kg_path}")
            # Download from GCS - fail explicitly if it doesn't work
            if not _download_from_gcs(kg_path, str(local_path)):
                raise RuntimeError(f"Failed to download KG for domain '{domain_id}' from GCS: {kg_path}")
        
        if not local_path.exists():
            raise FileNotFoundError(f"KG file not found after download: {local_path}")
        
        kg_path = str(local_path)
    else:
        # Resolve relative paths from project root
        if not os.path.isabs(kg_path):
            base_dir = os.path.dirname(os.path.dirname(__file__))
            kg_path = os.path.join(base_dir, kg_path)
    
    if not os.path.exists(kg_path):
        raise FileNotFoundError(f"KG file not found for domain '{domain_id}': {kg_path}")
    
    log.info(f"Loading KG for domain '{domain_id}' from {kg_path}")
    G, by_id, name_index = load_kg_from_json(kg_path)
    log.info(f"✓ Loaded KG for '{domain_id}': {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, {len(name_index)} aliases")
    
    return G, by_id, name_index

def get_agent(domain_id: str, vectorstore_id: str, params: Dict[str, Any] | None = None) -> EKGAgent:
    """
    Create an agent for a specific domain and vector store.
    
    Args:
        domain_id: Domain identifier
        vectorstore_id: Vector store ID (for documents)
        params: Optional parameters for the agent
        
    Returns:
        Configured EKGAgent instance
    """
    client = get_client()
    G, by_id, name_index = load_graph_artifacts(domain_id)
    
    # Get domain config to access kg_vectorstore_id
    from api.domains import get_domain
    domain_config = get_domain(domain_id)
    
    return EKGAgent(
        client=client,
        vs_id=vectorstore_id,
        G=G,
        by_id=by_id,
        name_index=name_index,
        preset_params=params or {},
        kg_vector_store_id=domain_config.kg_vectorstore_id  # Use domain's KG vector store ID
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
                "kg_vectorstore_id": domain_config.kg_vectorstore_id,
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
                "kg_vectorstore_id": domain_config.kg_vectorstore_id,
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
    
    # Cache status - caching disabled for fresh answers
    health_status["cache_status"] = {
        "query_cache_size": 0,
        "hits_cache_size": 0,
        "note": "Caching disabled - all answers are generated fresh"
    }
    
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
            "query_cache_size": 0,
            "hits_cache_size": 0,
            "note": "Caching disabled - all answers are generated fresh"
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
            
            # Check for OpenAI API errors
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                raise HTTPException(
                    status_code=429,
                    detail="OpenAI API quota exceeded. Please check your billing and plan limits. "
                           "See https://platform.openai.com/docs/guides/error-codes/api-errors for details."
                )
            elif "401" in error_str or "unauthorized" in error_str or "invalid_api_key" in error_str:
                raise HTTPException(
                    status_code=500,
                    detail="OpenAI API authentication failed. Please check your API key configuration."
                )
            elif "503" in error_str or "service unavailable" in error_str:
                raise HTTPException(
                    status_code=503,
                    detail="OpenAI API service is temporarily unavailable. Please try again later."
                )
            else:
                # Generic error - log full details but return user-friendly message
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



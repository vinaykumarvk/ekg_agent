# syntax=docker/dockerfile:1

# ---- Base image ----
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies for production
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ---- Dependency layer (better build caching) ----
# Copy only files needed to resolve/install deps
COPY pyproject.toml ./
# If you also keep a requirements.txt, include it as well (not mandatory with pyproject)
# COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
 && pip install --upgrade hatchling \
 && pip wheel --no-deps --wheel-dir /wheels .

# ---- App layer ----
# Now copy the full source
COPY . /app

# Install your package (editable not needed inside container)
# Use wheels for speed; fallback to normal if needed
RUN pip install --no-deps /wheels/*.whl || pip install . \
 && pip install pydantic-settings

# Security: run as non-root
RUN useradd -m appuser
USER appuser

# Cloud Run expects the server to listen on $PORT
ENV PORT=8080
# Production environment variables
ENV CACHE_DIR=/tmp/ekg_cache
ENV LOG_LEVEL=INFO
ENV MAX_CACHE_SIZE=1000
ENV CACHE_TTL=3600

# Expose for local docker runs (Cloud Run ignores EXPOSE)
EXPOSE 8080

# Healthcheck (optional; Cloud Run has its own, but helpful locally)
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.getenv(\"PORT\",\"8080\")}/health', timeout=2).read()" || exit 1

# Start FastAPI via production script
CMD ["python", "start_production.py"]


# syntax=docker/dockerfile:1

# ---- Base image ----
FROM python:3.11-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Optional: install system deps only if you need them (uncomment as required)
# RUN apt-get update && apt-get install -y --no-install-recommends \
#     build-essential gcc curl \
#  && rm -rf /var/lib/apt/lists/*

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
RUN pip install --no-deps /wheels/*.whl || pip install .

# Security: run as non-root
RUN useradd -m appuser
USER appuser

# Cloud Run expects the server to listen on $PORT
ENV PORT=8080
# Optional defaults (overridable at deploy time)
# ENV MODEL_DEFAULT=gpt-4o
# ENV KG_PATH=/app/data/kg/master_knowledge_graph.json

# Expose for local docker runs (Cloud Run ignores EXPOSE)
EXPOSE 8080

# Healthcheck (optional; Cloud Run has its own, but helpful locally)
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python - <<'PY' || exit 1
import urllib.request, os
url=f"http://127.0.0.1:{os.getenv('PORT','8080')}/health"
urllib.request.urlopen(url, timeout=2).read()
PY

# Start FastAPI via Uvicorn
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]


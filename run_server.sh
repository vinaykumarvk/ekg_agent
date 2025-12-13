#!/bin/bash

# EKG Agent - Quick Start Script
# Usage: ./run_server.sh
#
# REQUIRED Environment Variables:
#   - OPENAI_API_KEY
#   - DOC_VECTOR_STORE_ID
#   - WEALTH_MANAGEMENT_KG_PATH (gs://...)
#   - APF_KG_PATH (gs://...)
#
# Optional:
#   - GOOGLE_APPLICATION_CREDENTIALS (for local GCS access)

set -e

echo "🚀 Starting EKG Agent API Server"
echo "================================"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# Load .env file if exists
if [ -f ".env" ]; then
    echo "📝 Loading .env file..."
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check required environment variables
MISSING_VARS=""

if [ -z "$OPENAI_API_KEY" ]; then
    MISSING_VARS="$MISSING_VARS OPENAI_API_KEY"
fi

if [ -z "$DOC_VECTOR_STORE_ID" ]; then
    MISSING_VARS="$MISSING_VARS DOC_VECTOR_STORE_ID"
fi

if [ -z "$WEALTH_MANAGEMENT_KG_PATH" ]; then
    MISSING_VARS="$MISSING_VARS WEALTH_MANAGEMENT_KG_PATH"
fi

if [ -z "$APF_KG_PATH" ]; then
    MISSING_VARS="$MISSING_VARS APF_KG_PATH"
fi

if [ -n "$MISSING_VARS" ]; then
    echo "❌ Missing required environment variables:$MISSING_VARS"
    echo ""
    echo "Create a .env file with:"
    echo "  OPENAI_API_KEY=sk-your-key"
    echo "  DOC_VECTOR_STORE_ID=vs_your_vectorstore_id"
    echo "  WEALTH_MANAGEMENT_KG_PATH=gs://your-bucket/kg/wealth_product_kg.json (or local file path for dev)"
    echo "  APF_KG_PATH=gs://your-bucket/kg/apf_kg.json (or local file path for dev)"
    echo ""
    echo "For local GCS access, also set:"
    echo "  GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json"
    exit 1
fi

echo ""
echo "✓ Environment configured"
echo "  - DOC_VECTOR_STORE_ID: $DOC_VECTOR_STORE_ID"
echo "  - WEALTH_MANAGEMENT_KG_PATH: $WEALTH_MANAGEMENT_KG_PATH"
echo "  - APF_KG_PATH: $APF_KG_PATH"
echo ""
echo "✓ Starting server on http://localhost:8000"
echo ""
echo "📚 API Documentation: http://localhost:8000/docs"
echo "🏥 Health Check:      http://localhost:8000/health"
echo ""
echo "Press CTRL+C to stop"
echo "================================"
echo ""

# Activate venv and run server
source .venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload


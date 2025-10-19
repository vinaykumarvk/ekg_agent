#!/bin/bash

# EKG Agent - Quick Start Script
# Usage: ./run_server.sh

set -e

echo "🚀 Starting EKG Agent API Server"
echo "================================"

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

# Check if OPENAI_API_KEY is set
if [ -z "$OPENAI_API_KEY" ]; then
    if [ -f ".env" ]; then
        echo "📝 Loading .env file..."
        export $(cat .env | grep -v '^#' | xargs)
    else
        echo "⚠️  OPENAI_API_KEY not set!"
        echo "   Create .env file with: OPENAI_API_KEY=your_key_here"
        echo "   Or export it: export OPENAI_API_KEY=your_key"
        echo ""
        echo "   Using dummy key for testing (endpoints will fail with real OpenAI calls)"
        export OPENAI_API_KEY=dummy
    fi
fi

# Check if KG exists
if [ ! -f "data/kg/master_knowledge_graph.json" ]; then
    echo "⚠️  Knowledge graph not found at data/kg/master_knowledge_graph.json"
    echo "   Some features may not work."
fi

echo ""
echo "✓ Environment configured"
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



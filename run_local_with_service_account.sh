#!/bin/bash
# Script to run local Docker container with GCS access using Service Account Key

set -e

echo "🐳 Starting EKG Agent with GCS access (Service Account)..."

# Check if service account key path is provided
if [ -z "$1" ]; then
    echo "❌ Service account key file path required"
    echo ""
    echo "Usage: $0 <path-to-service-account-key.json>"
    echo ""
    echo "Example:"
    echo "  $0 ~/.gcp/ekg-agent-key.json"
    echo "  $0 ./gcp-credentials.json"
    echo ""
    exit 1
fi

SERVICE_ACCOUNT_KEY="$1"

# Check if file exists
if [ ! -f "$SERVICE_ACCOUNT_KEY" ]; then
    echo "❌ Service account key file not found: $SERVICE_ACCOUNT_KEY"
    exit 1
fi

# Get absolute path
SERVICE_ACCOUNT_KEY=$(cd "$(dirname "$SERVICE_ACCOUNT_KEY")" && pwd)/$(basename "$SERVICE_ACCOUNT_KEY")

echo "✅ Using service account key: $SERVICE_ACCOUNT_KEY"

# Stop and remove existing container
docker stop ekg-agent 2>/dev/null || true
docker rm ekg-agent 2>/dev/null || true

# Get GCS bucket path (default or from env)
WEALTH_KG_PATH="${WEALTH_MANAGEMENT_KG_PATH:-gs://wealth-report/kg/master_knowledge_graph.json}"
APF_KG_PATH="${APF_KG_PATH:-gs://wealth-report/kg/master_knowledge_graph.json}"

echo "📦 Starting container with:"
echo "   WEALTH_MANAGEMENT_KG_PATH=$WEALTH_KG_PATH"
echo "   APF_KG_PATH=$APF_KG_PATH"
echo "   Service Account Key: $SERVICE_ACCOUNT_KEY"
echo ""

# Run container with GCS access using service account key
docker run -d \
  --name ekg-agent \
  -p 8081:8080 \
  --env-file .env \
  -e LOG_LEVEL=DEBUG \
  -e WEALTH_MANAGEMENT_KG_PATH="$WEALTH_KG_PATH" \
  -e APF_KG_PATH="$APF_KG_PATH" \
  -v "$SERVICE_ACCOUNT_KEY:/root/gcp-key.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/gcp-key.json \
  ekg-agent:latest

echo ""
echo "✅ Container started!"
echo ""
echo "Waiting for startup..."
sleep 5

echo ""
echo "📊 Health check:"
curl -s http://127.0.0.1:8081/health | python3 -m json.tool | head -20

echo ""
echo "📝 View logs: docker logs -f ekg-agent"
echo "🌐 API URL: http://127.0.0.1:8081"


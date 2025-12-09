#!/bin/bash
# Script to run local Docker container with GCS access

set -e

echo "🐳 Starting EKG Agent with GCS access..."

# Check if gcloud is authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ No active gcloud authentication found"
    echo ""
    echo "Please run: gcloud auth application-default login"
    echo "Then run this script again."
    exit 1
fi

# Check if ADC exists
if [ ! -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
    echo "⚠️  Application Default Credentials not found"
    echo "Running: gcloud auth application-default login"
    gcloud auth application-default login
fi

# Stop and remove existing container
docker stop ekg-agent 2>/dev/null || true
docker rm ekg-agent 2>/dev/null || true

# Get GCS bucket path (default or from env)
WEALTH_KG_PATH="${WEALTH_MANAGEMENT_KG_PATH:-gs://wealth-report/kg/master_knowledge_graph.json}"
APF_KG_PATH="${APF_KG_PATH:-gs://wealth-report/kg/master_knowledge_graph.json}"

echo "📦 Starting container with:"
echo "   WEALTH_MANAGEMENT_KG_PATH=$WEALTH_KG_PATH"
echo "   APF_KG_PATH=$APF_KG_PATH"
echo ""

# Run container with GCS access
docker run -d \
  --name ekg-agent \
  -p 8081:8080 \
  --env-file .env \
  -e LOG_LEVEL=DEBUG \
  -e WEALTH_MANAGEMENT_KG_PATH="$WEALTH_KG_PATH" \
  -e APF_KG_PATH="$APF_KG_PATH" \
  -v "$HOME/.config/gcloud:/root/.config/gcloud:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/root/.config/gcloud/application_default_credentials.json \
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


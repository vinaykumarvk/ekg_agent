#!/bin/bash
# Production Log Extraction Script for EKG Agent
# Usage: ./extract_production_logs.sh

SERVICE_NAME="ekg-agent"
REGION="europe-west6"
OUTPUT_DIR="production_logs_$(date +%Y%m%d_%H%M%S)"

echo "=========================================="
echo "EKG Agent - Production Log Extraction"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    echo "Install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "⚠️  Warning: Not authenticated with gcloud"
    echo "Run: gcloud auth login"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

echo "📁 Output directory: $OUTPUT_DIR"
echo ""

# Extract recent errors
echo "1️⃣  Extracting recent errors (last 100)..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=ERROR" \
  --limit 100 \
  --format json > errors.json 2>&1
if [ $? -eq 0 ]; then
    ERROR_COUNT=$(cat errors.json | python3 -c "import json, sys; print(len([l for l in json.load(sys.stdin) if l]))" 2>/dev/null || echo "0")
    echo "   ✅ Extracted $ERROR_COUNT error logs"
else
    echo "   ⚠️  Failed to extract errors (check gcloud authentication)"
fi

# Extract recent logs
echo "2️⃣  Extracting recent logs (last 200)..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --limit 200 \
  --format json > all_logs.json 2>&1
if [ $? -eq 0 ]; then
    LOG_COUNT=$(cat all_logs.json | python3 -c "import json, sys; print(len([l for l in json.load(sys.stdin) if l]))" 2>/dev/null || echo "0")
    echo "   ✅ Extracted $LOG_COUNT log entries"
else
    echo "   ⚠️  Failed to extract logs"
fi

# Extract failed answer errors
echo "3️⃣  Extracting 'Failed to generate answer' errors..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND jsonPayload.detail=~\"Failed to generate answer\"" \
  --limit 50 \
  --format json > failed_answers.json 2>&1
if [ $? -eq 0 ]; then
    FAILED_COUNT=$(cat failed_answers.json | python3 -c "import json, sys; print(len([l for l in json.load(sys.stdin) if l]))" 2>/dev/null || echo "0")
    echo "   ✅ Extracted $FAILED_COUNT failed answer logs"
else
    echo "   ⚠️  Failed to extract failed answers"
fi

# Extract OpenAI API errors
echo "4️⃣  Extracting OpenAI API errors..."
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND (jsonPayload.message=~\"OpenAI\" OR jsonPayload.message=~\"429\" OR jsonPayload.message=~\"quota\")" \
  --limit 50 \
  --format json > openai_errors.json 2>&1
if [ $? -eq 0 ]; then
    OPENAI_COUNT=$(cat openai_errors.json | python3 -c "import json, sys; print(len([l for l in json.load(sys.stdin) if l]))" 2>/dev/null || echo "0")
    echo "   ✅ Extracted $OPENAI_COUNT OpenAI error logs"
else
    echo "   ⚠️  Failed to extract OpenAI errors"
fi

# Extract service configuration
echo "5️⃣  Extracting service configuration..."
gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format yaml > service_config.yaml 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Extracted service configuration"
else
    echo "   ⚠️  Failed to extract service config (check service name and region)"
fi

# Extract environment variables (redacted)
echo "6️⃣  Extracting environment variables..."
gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(spec.template.spec.containers[0].env)" > env_vars.txt 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ Extracted environment variables"
    # Redact sensitive values
    sed -i.bak 's/=.*/=***REDACTED***/g' env_vars.txt 2>/dev/null || \
    sed -i '' 's/=.*/=***REDACTED***/g' env_vars.txt 2>/dev/null
    rm -f env_vars.txt.bak 2>/dev/null
else
    echo "   ⚠️  Failed to extract environment variables"
fi

# Create error summary
echo "7️⃣  Creating error summary..."
if [ -f errors.json ] && [ -s errors.json ]; then
    python3 << 'PYTHON_SCRIPT' > error_summary.txt 2>&1
import json
import sys
from collections import Counter

try:
    with open('errors.json', 'r') as f:
        logs = json.load(f)
    
    if not logs:
        print("No errors found in logs")
        sys.exit(0)
    
    print("=" * 60)
    print("ERROR SUMMARY")
    print("=" * 60)
    print(f"\nTotal Errors: {len(logs)}\n")
    
    # Extract error messages
    error_messages = []
    for log in logs:
        payload = log.get('jsonPayload', {})
        text = log.get('textPayload', '')
        message = payload.get('message', '') or payload.get('detail', '') or text
        if message:
            error_messages.append(message)
    
    # Count error types
    error_types = Counter()
    for msg in error_messages:
        if '429' in msg or 'quota' in msg.lower():
            error_types['Quota/Rate Limit'] += 1
        elif '401' in msg or 'unauthorized' in msg.lower():
            error_types['Authentication'] += 1
        elif 'failed to generate' in msg.lower():
            error_types['Answer Generation Failed'] += 1
        elif 'openai' in msg.lower():
            error_types['OpenAI API Error'] += 1
        elif 'attributeerror' in msg.lower():
            error_types['AttributeError'] += 1
        elif 'keyerror' in msg.lower():
            error_types['KeyError'] += 1
        else:
            error_types['Other'] += 1
    
    print("Error Types:")
    for err_type, count in error_types.most_common():
        print(f"  - {err_type}: {count}")
    
    print("\n" + "=" * 60)
    print("SAMPLE ERROR MESSAGES (First 5)")
    print("=" * 60)
    for i, msg in enumerate(error_messages[:5], 1):
        print(f"\n{i}. {msg[:200]}...")
        
except Exception as e:
    print(f"Error creating summary: {e}")
PYTHON_SCRIPT
    echo "   ✅ Created error summary"
else
    echo "   ⚠️  No errors found to summarize"
fi

echo ""
echo "=========================================="
echo "✅ Extraction Complete!"
echo "=========================================="
echo ""
echo "📁 Files created in: $OUTPUT_DIR"
echo ""
ls -lh | grep -E "\.(json|txt|yaml)$" | awk '{print "   " $9 " (" $5 ")"}'
echo ""
echo "📋 Next Steps:"
echo "   1. Review error_summary.txt for error patterns"
echo "   2. Check errors.json for detailed error logs"
echo "   3. Verify service_config.yaml for configuration"
echo "   4. Share relevant files for analysis"
echo ""
echo "💡 To view logs in real-time:"
echo "   gcloud logging tail \"resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME\""
echo ""


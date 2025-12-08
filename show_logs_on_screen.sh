#!/bin/bash
# Script to display production logs on screen for easy copying

SERVICE_NAME="ekg-agent"

echo "=========================================="
echo "EKG Agent - Production Logs Viewer"
echo "=========================================="
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed"
    exit 1
fi

# Menu
echo "Select what to display:"
echo "1. Recent ERROR logs (formatted table)"
echo "2. Recent WARNING and ERROR logs (formatted table)"
echo "3. All recent logs (formatted table)"
echo "4. Error messages only (text)"
echo "5. Failed answer errors (JSON)"
echo "6. All logs as JSON (pretty printed)"
echo "7. Stream live logs"
echo ""
read -p "Enter choice (1-7): " choice

case $choice in
    1)
        echo ""
        echo "=========================================="
        echo "RECENT ERROR LOGS"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=ERROR" \
          --limit 50 --format="table(timestamp,severity,jsonPayload.message,jsonPayload.detail)" 2>&1 | head -100
        ;;
    2)
        echo ""
        echo "=========================================="
        echo "RECENT WARNING AND ERROR LOGS"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=WARNING" \
          --limit 50 --format="table(timestamp,severity,jsonPayload.message,jsonPayload.detail)" 2>&1 | head -100
        ;;
    3)
        echo ""
        echo "=========================================="
        echo "ALL RECENT LOGS"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
          --limit 50 --format="table(timestamp,severity,jsonPayload.message)" 2>&1 | head -100
        ;;
    4)
        echo ""
        echo "=========================================="
        echo "ERROR MESSAGES ONLY"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=ERROR" \
          --limit 50 --format="value(jsonPayload.message,jsonPayload.detail,textPayload)" 2>&1 | head -100
        ;;
    5)
        echo ""
        echo "=========================================="
        echo "FAILED ANSWER ERRORS (JSON)"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND jsonPayload.detail=~\"Failed to generate answer\"" \
          --limit 20 --format json 2>&1 | python3 -m json.tool | head -300
        ;;
    6)
        echo ""
        echo "=========================================="
        echo "ALL LOGS AS JSON (PRETTY PRINTED)"
        echo "=========================================="
        echo ""
        gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND severity>=WARNING" \
          --limit 20 --format json 2>&1 | python3 -m json.tool | head -300
        ;;
    7)
        echo ""
        echo "=========================================="
        echo "STREAMING LIVE LOGS (Press Ctrl+C to stop)"
        echo "=========================================="
        echo ""
        gcloud logging tail "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
          --format="table(timestamp,severity,jsonPayload.message)"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "Done! Copy the output above."
echo "=========================================="


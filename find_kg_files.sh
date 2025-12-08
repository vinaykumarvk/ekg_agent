#!/bin/bash
# Script to find KG files in GCS buckets

echo "=========================================="
echo "Searching for KG Files in GCS Buckets"
echo "=========================================="
echo ""

# Search wealth-report bucket
echo "1️⃣  Searching gs://wealth-report/..."
echo ""
echo "Root level files:"
gsutil ls gs://wealth-report/ 2>&1 | head -20
echo ""

echo "JSON files in root:"
gsutil ls gs://wealth-report/*.json 2>&1 | head -10
echo ""

echo "Recursive search for JSON files:"
gsutil ls -r gs://wealth-report/ 2>&1 | grep -i "\.json$" | head -20
echo ""

echo "Files with 'kg', 'wealth', or 'apf' in name:"
gsutil ls -r gs://wealth-report/ 2>&1 | grep -iE "(kg|wealth|apf)" | head -20
echo ""

# Search staging bucket
echo "2️⃣  Searching gs://staging.wealth-report.appspot.com/..."
echo ""
gsutil ls -r gs://staging.wealth-report.appspot.com/ 2>&1 | grep -i "\.json$" | head -20
echo ""

# Check other likely buckets
echo "3️⃣  Checking other buckets..."
echo ""
echo "gs://wealth-report.appspot.com/:"
gsutil ls gs://wealth-report.appspot.com/ 2>&1 | head -10
echo ""

echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "If KG files are found, note the full path (gs://bucket/path/file.json)"
echo "Then set environment variables:"
echo ""
echo "gcloud run services update ekg-service \\"
echo "  --region=europe-west6 \\"
echo "  --update-env-vars \\"
echo "  WEALTH_MANAGEMENT_KG_PATH=gs://bucket/path/wealth_product_kg.json,\\"
echo "  APF_KG_PATH=gs://bucket/path/apf_kg.json"


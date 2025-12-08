#!/bin/bash
# Script to check production environment variables

REGION="europe-west6"

echo "=========================================="
echo "Checking Cloud Run Service Configuration"
echo "=========================================="
echo ""

# Step 1: List all services
echo "1️⃣  Listing all Cloud Run services in $REGION..."
echo ""
gcloud run services list --region=$REGION --format="table(metadata.name,status.url)"
echo ""

# Step 2: Ask for service name
read -p "Enter the service name (from list above): " SERVICE_NAME

if [ -z "$SERVICE_NAME" ]; then
    echo "❌ Service name is required"
    exit 1
fi

echo ""
echo "2️⃣  Checking environment variables for: $SERVICE_NAME"
echo ""

# Step 3: Get all environment variables
echo "All Environment Variables:"
echo "-------------------------"
gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(spec.template.spec.containers[0].env)" 2>&1 | while IFS= read -r line; do
    echo "$line"
done

echo ""
echo "3️⃣  Checking for KG_PATH variables specifically:"
echo ""

# Step 4: Check for KG_PATH
KG_PATHS=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(spec.template.spec.containers[0].env)" 2>&1 | grep -i "KG_PATH" || echo "NONE FOUND")

if [ "$KG_PATHS" = "NONE FOUND" ]; then
    echo "❌ KG_PATH environment variables are NOT SET!"
    echo ""
    echo "This is likely why KG files are not loading!"
    echo ""
    echo "Required environment variables:"
    echo "  - WEALTH_MANAGEMENT_KG_PATH=gs://your-bucket/kg/wealth_product_kg.json"
    echo "  - APF_KG_PATH=gs://your-bucket/kg/apf_kg.json"
else
    echo "✅ Found KG_PATH variables:"
    echo "$KG_PATHS"
fi

echo ""
echo "4️⃣  Checking secrets:"
echo ""

# Step 5: Check secrets
SECRETS=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(spec.template.spec.containers[0].env)" 2>&1 | grep -i "secret" || echo "NONE FOUND")

if [ "$SECRETS" != "NONE FOUND" ]; then
    echo "Found secrets configuration:"
    echo "$SECRETS"
else
    echo "No secrets found in env vars (they might be in --set-secrets)"
fi

echo ""
echo "=========================================="
echo "Summary:"
echo "=========================================="
echo "Service: $SERVICE_NAME"
echo "Region: $REGION"
echo ""

if [ "$KG_PATHS" = "NONE FOUND" ]; then
    echo "❌ ACTION REQUIRED: Set KG_PATH environment variables!"
    echo ""
    echo "To fix, update the service:"
    echo "gcloud run services update $SERVICE_NAME \\"
    echo "  --region=$REGION \\"
    echo "  --update-env-vars WEALTH_MANAGEMENT_KG_PATH=gs://your-bucket/kg/wealth_product_kg.json,APF_KG_PATH=gs://your-bucket/kg/apf_kg.json"
else
    echo "✅ KG_PATH variables are set"
fi


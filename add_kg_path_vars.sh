#!/bin/bash
# Script to add KG_PATH environment variables to Cloud Run

SERVICE_NAME="ekg-service"
REGION="europe-west6"

echo "=========================================="
echo "Add KG_PATH Environment Variables"
echo "=========================================="
echo ""

# Get current environment variables
echo "1️⃣  Getting current environment variables..."
CURRENT_ENV=$(gcloud run services describe $SERVICE_NAME \
  --region=$REGION \
  --format="value(spec.template.spec.containers[0].env)" 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ Failed to get current environment variables"
    echo "$CURRENT_ENV"
    exit 1
fi

echo "Current variables:"
echo "$CURRENT_ENV" | tr ';' '\n' | grep -E "name|value" | head -20
echo ""

# Check if KG_PATH variables already exist
if echo "$CURRENT_ENV" | grep -q "WEALTH_MANAGEMENT_KG_PATH"; then
    echo "⚠️  WEALTH_MANAGEMENT_KG_PATH already exists"
    read -p "Update it? (y/n): " update_wealth
else
    update_wealth="y"
fi

if echo "$CURRENT_ENV" | grep -q "APF_KG_PATH"; then
    echo "⚠️  APF_KG_PATH already exists"
    read -p "Update it? (y/n): " update_apf
else
    update_apf="y"
fi

echo ""

# Build the update command
echo "2️⃣  Setting KG_PATH environment variables..."
echo ""

# Use --update-env-vars to ADD variables without removing existing ones
gcloud run services update $SERVICE_NAME \
  --region=$REGION \
  --update-env-vars \
  WEALTH_MANAGEMENT_KG_PATH=gs://wealth-report/kg/master_knowledge_graph.json,\
  APF_KG_PATH=gs://wealth-report/kg/master_knowledge_graph.json

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Environment variables updated!"
    echo ""
    echo "3️⃣  Verifying..."
    echo ""
    
    # Verify
    gcloud run services describe $SERVICE_NAME \
      --region=$REGION \
      --format="value(spec.template.spec.containers[0].env)" | grep KG_PATH
    
    echo ""
    echo "=========================================="
    echo "✅ Setup Complete!"
    echo "=========================================="
    echo ""
    echo "⏳ Service will restart automatically..."
    echo "Wait 1-2 minutes, then test:"
    echo ""
    echo "curl https://ekg-service-47249889063.europe-west6.run.app/domains | python3 -m json.tool"
    echo ""
    echo "You should see:"
    echo "  - kg_loaded: true"
    echo "  - kg_nodes: > 1000"
    echo "  - kg_edges: > 1000"
else
    echo ""
    echo "❌ Failed to update environment variables"
    echo ""
    echo "Try adding manually via Cloud Console UI:"
    echo "1. Go to Cloud Run → ekg-service → Edit & Deploy New Revision"
    echo "2. Variables & Secrets tab"
    echo "3. Add WEALTH_MANAGEMENT_KG_PATH=gs://wealth-report/kg/master_knowledge_graph.json"
    echo "4. Add APF_KG_PATH=gs://wealth-report/kg/master_knowledge_graph.json"
    echo "5. Click Deploy"
    exit 1
fi


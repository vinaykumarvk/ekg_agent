#!/bin/bash
# Script to upload KG files to GCS

BUCKET="wealth-report"
REGION="europe-west6"

echo "=========================================="
echo "Upload KG Files to GCS"
echo "=========================================="
echo ""

# Check if local files exist
echo "1️⃣  Checking for local KG files..."
echo ""

WEALTH_KG_LOCAL="data/kg/wealth_product_kg.json"
APF_KG_LOCAL="data/kg/apf_kg.json"

if [ -f "$WEALTH_KG_LOCAL" ]; then
    echo "✅ Found: $WEALTH_KG_LOCAL"
    WEALTH_EXISTS=true
else
    echo "❌ Not found: $WEALTH_KG_LOCAL"
    WEALTH_EXISTS=false
fi

if [ -f "$APF_KG_LOCAL" ]; then
    echo "✅ Found: $APF_KG_LOCAL"
    APF_EXISTS=true
else
    echo "❌ Not found: $APF_KG_LOCAL"
    APF_EXISTS=false
fi

echo ""

if [ "$WEALTH_EXISTS" = false ] && [ "$APF_EXISTS" = false ]; then
    echo "❌ No local KG files found!"
    echo ""
    echo "Please provide the paths to your KG files:"
    read -p "Enter path to wealth_product_kg.json: " WEALTH_PATH
    read -p "Enter path to apf_kg.json: " APF_PATH
    
    if [ -f "$WEALTH_PATH" ]; then
        WEALTH_KG_LOCAL="$WEALTH_PATH"
        WEALTH_EXISTS=true
    fi
    if [ -f "$APF_PATH" ]; then
        APF_KG_LOCAL="$APF_PATH"
        APF_EXISTS=true
    fi
fi

echo ""

# Create kg/ folder in bucket if it doesn't exist
echo "2️⃣  Creating kg/ folder in bucket (if needed)..."
gsutil ls gs://$BUCKET/kg/ >/dev/null 2>&1 || gsutil mkdir gs://$BUCKET/kg/
echo ""

# Upload files
echo "3️⃣  Uploading KG files..."
echo ""

if [ "$WEALTH_EXISTS" = true ]; then
    echo "Uploading wealth_product_kg.json..."
    gsutil cp "$WEALTH_KG_LOCAL" gs://$BUCKET/kg/wealth_product_kg.json
    if [ $? -eq 0 ]; then
        echo "✅ Uploaded: gs://$BUCKET/kg/wealth_product_kg.json"
        WEALTH_GCS="gs://$BUCKET/kg/wealth_product_kg.json"
    else
        echo "❌ Upload failed!"
        exit 1
    fi
else
    read -p "Enter GCS path for wealth_product_kg.json (gs://bucket/path): " WEALTH_GCS
fi

echo ""

if [ "$APF_EXISTS" = true ]; then
    echo "Uploading apf_kg.json..."
    gsutil cp "$APF_KG_LOCAL" gs://$BUCKET/kg/apf_kg.json
    if [ $? -eq 0 ]; then
        echo "✅ Uploaded: gs://$BUCKET/kg/apf_kg.json"
        APF_GCS="gs://$BUCKET/kg/apf_kg.json"
    else
        echo "❌ Upload failed!"
        exit 1
    fi
else
    read -p "Enter GCS path for apf_kg.json (gs://bucket/path): " APF_GCS
fi

echo ""
echo "=========================================="
echo "4️⃣  Setting Cloud Run Environment Variables"
echo "=========================================="
echo ""

read -p "Set environment variables in Cloud Run? (y/n): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo ""
    echo "Setting environment variables..."
    
    gcloud run services update ekg-service \
      --region=$REGION \
      --update-env-vars \
      WEALTH_MANAGEMENT_KG_PATH=$WEALTH_GCS,\
      APF_KG_PATH=$APF_GCS
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Environment variables set!"
        echo ""
        echo "Verifying..."
        gcloud run services describe ekg-service \
          --region=$REGION \
          --format="value(spec.template.spec.containers[0].env)" | grep KG_PATH
        
        echo ""
        echo "⏳ Service will restart automatically..."
        echo "Wait 1-2 minutes, then test:"
        echo "curl https://ekg-service-47249889063.europe-west6.run.app/domains | python3 -m json.tool"
    else
        echo "❌ Failed to set environment variables"
        exit 1
    fi
else
    echo ""
    echo "Manual setup required:"
    echo "gcloud run services update ekg-service \\"
    echo "  --region=$REGION \\"
    echo "  --update-env-vars \\"
    echo "  WEALTH_MANAGEMENT_KG_PATH=$WEALTH_GCS,\\"
    echo "  APF_KG_PATH=$APF_GCS"
fi


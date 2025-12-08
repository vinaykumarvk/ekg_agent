#!/bin/bash
# Script to set KG_PATH environment variables in Cloud Run

SERVICE_NAME="ekg-service"
REGION="europe-west6"

echo "=========================================="
echo "Setting KG_PATH Environment Variables"
echo "=========================================="
echo ""

# Check which bucket has KG files
echo "Checking buckets for KG files..."
echo ""

# Check wealth-report bucket
echo "1️⃣  Checking gs://wealth-report/kg/..."
WEALTH_KG=$(gsutil ls gs://wealth-report/kg/*.json 2>&1 | grep -i "wealth\|kg" | head -1)
if [ -n "$WEALTH_KG" ] && [ ! "$WEALTH_KG" = *"does not exist"* ]; then
    echo "   ✅ Found: $WEALTH_KG"
else
    echo "   ❌ Not found in gs://wealth-report/kg/"
fi

# Check for apf_kg.json
APF_KG=$(gsutil ls gs://wealth-report/kg/*.json 2>&1 | grep -i "apf\|kg" | head -1)
if [ -n "$APF_KG" ] && [ ! "$APF_KG" = *"does not exist"* ]; then
    echo "   ✅ Found: $APF_KG"
else
    echo "   ❌ Not found in gs://wealth-report/kg/"
fi

echo ""

# If not found, check staging
if [ -z "$WEALTH_KG" ] || [ -z "$APF_KG" ]; then
    echo "2️⃣  Checking gs://staging.wealth-report.appspot.com/kg/..."
    WEALTH_KG_STAGING=$(gsutil ls gs://staging.wealth-report.appspot.com/kg/*.json 2>&1 | grep -i "wealth\|kg" | head -1)
    APF_KG_STAGING=$(gsutil ls gs://staging.wealth-report.appspot.com/kg/*.json 2>&1 | grep -i "apf\|kg" | head -1)
    
    if [ -n "$WEALTH_KG_STAGING" ]; then
        WEALTH_KG="$WEALTH_KG_STAGING"
        echo "   ✅ Found: $WEALTH_KG"
    fi
    if [ -n "$APF_KG_STAGING" ]; then
        APF_KG="$APF_KG_STAGING"
        echo "   ✅ Found: $APF_KG"
    fi
fi

echo ""

# Determine bucket and paths
if [ -n "$WEALTH_KG" ] && [ -n "$APF_KG" ]; then
    echo "✅ Found KG files!"
    echo ""
    echo "Wealth Management KG: $WEALTH_KG"
    echo "APF KG: $APF_KG"
    echo ""
    
    read -p "Do you want to set these paths? (y/n): " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
        echo ""
        echo "Setting environment variables..."
        
        gcloud run services update $SERVICE_NAME \
          --region=$REGION \
          --update-env-vars \
          WEALTH_MANAGEMENT_KG_PATH=$WEALTH_KG,\
          APF_KG_PATH=$APF_KG
        
        echo ""
        echo "✅ Environment variables set!"
        echo ""
        echo "Verifying..."
        gcloud run services describe $SERVICE_NAME \
          --region=$REGION \
          --format="value(spec.template.spec.containers[0].env)" | grep KG_PATH
        
        echo ""
        echo "⏳ Service will restart automatically..."
        echo "Wait 1-2 minutes, then test:"
        echo "curl https://ekg-service-47249889063.europe-west6.run.app/domains | python3 -m json.tool"
    else
        echo "Cancelled."
    fi
else
    echo "❌ Could not find KG files automatically."
    echo ""
    echo "Please manually specify the paths:"
    echo ""
    read -p "Enter WEALTH_MANAGEMENT_KG_PATH (gs://bucket/path): " WEALTH_PATH
    read -p "Enter APF_KG_PATH (gs://bucket/path): " APF_PATH
    
    if [ -n "$WEALTH_PATH" ] && [ -n "$APF_PATH" ]; then
        echo ""
        echo "Setting environment variables..."
        gcloud run services update $SERVICE_NAME \
          --region=$REGION \
          --update-env-vars \
          WEALTH_MANAGEMENT_KG_PATH=$WEALTH_PATH,\
          APF_KG_PATH=$APF_PATH
        
        echo "✅ Done!"
    else
        echo "❌ Paths not provided. Exiting."
    fi
fi


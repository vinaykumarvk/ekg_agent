#!/bin/bash
# Script to setup master_knowledge_graph.json for production

BUCKET="wealth-report"
REGION="europe-west6"
SERVICE_NAME="ekg-service"

echo "=========================================="
echo "Setup Master Knowledge Graph for Production"
echo "=========================================="
echo ""

# Step 1: Check if file exists locally
echo "1️⃣  Checking for master_knowledge_graph.json..."
echo ""

MASTER_KG_LOCAL=""
POSSIBLE_PATHS=(
    "master_knowledge_graph.json"
    "data/kg/master_knowledge_graph.json"
    "$HOME/Downloads/master_knowledge_graph.json"
    "$HOME/Desktop/master_knowledge_graph.json"
)

for path in "${POSSIBLE_PATHS[@]}"; do
    if [ -f "$path" ]; then
        MASTER_KG_LOCAL="$path"
        echo "✅ Found: $path"
        echo "   Size: $(du -h "$path" | cut -f1)"
        break
    fi
done

if [ -z "$MASTER_KG_LOCAL" ]; then
    echo "❌ File not found in common locations"
    echo ""
    echo "Please download master_knowledge_graph.json from Google Drive:"
    echo "  Path: /content/drive/MyDrive/Wealth EKG/Product EKG/master_knowledge_graph.json"
    echo ""
    echo "Options:"
    echo "  1. Download from Google Drive web interface"
    echo "  2. Use Google Drive API"
    echo "  3. Mount Google Drive in Colab and download"
    echo ""
    read -p "Enter full path to master_knowledge_graph.json: " MASTER_KG_LOCAL
    
    if [ ! -f "$MASTER_KG_LOCAL" ]; then
        echo "❌ File not found at: $MASTER_KG_LOCAL"
        exit 1
    fi
fi

echo ""
echo "File: $MASTER_KG_LOCAL"
echo "Size: $(du -h "$MASTER_KG_LOCAL" | cut -f1)"
echo ""

# Step 2: Upload to GCS
echo "2️⃣  Uploading to GCS..."
echo ""

# Create kg/ folder if needed
gsutil mkdir gs://$BUCKET/kg/ 2>/dev/null || echo "Folder exists or created"

# Upload file
echo "Uploading master_knowledge_graph.json..."
gsutil cp "$MASTER_KG_LOCAL" gs://$BUCKET/kg/master_knowledge_graph.json

if [ $? -eq 0 ]; then
    echo "✅ Uploaded: gs://$BUCKET/kg/master_knowledge_graph.json"
    MASTER_KG_GCS="gs://$BUCKET/kg/master_knowledge_graph.json"
else
    echo "❌ Upload failed!"
    exit 1
fi

echo ""

# Step 3: Update domain configuration
echo "3️⃣  Updating domain configuration..."
echo ""
echo "Current setup uses separate files for each domain."
echo "You have a single master_knowledge_graph.json file."
echo ""
echo "Options:"
echo "  A) Use master_knowledge_graph.json for BOTH domains (recommended)"
echo "  B) Keep separate files (if master file contains both domains)"
echo ""
read -p "Choose option (A/B): " OPTION

if [ "$OPTION" = "A" ] || [ "$OPTION" = "a" ]; then
    WEALTH_KG_PATH="$MASTER_KG_GCS"
    APF_KG_PATH="$MASTER_KG_GCS"
    echo ""
    echo "✅ Will use master_knowledge_graph.json for both domains"
elif [ "$OPTION" = "B" ] || [ "$OPTION" = "b" ]; then
    echo ""
    read -p "Enter GCS path for wealth_management domain: " WEALTH_KG_PATH
    read -p "Enter GCS path for apf domain: " APF_KG_PATH
else
    echo "Invalid option. Using master file for both domains."
    WEALTH_KG_PATH="$MASTER_KG_GCS"
    APF_KG_PATH="$MASTER_KG_GCS"
fi

echo ""

# Step 4: Set Cloud Run environment variables
echo "4️⃣  Setting Cloud Run environment variables..."
echo ""

read -p "Update Cloud Run service? (y/n): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo ""
    echo "Setting environment variables..."
    
    gcloud run services update $SERVICE_NAME \
      --region=$REGION \
      --update-env-vars \
      WEALTH_MANAGEMENT_KG_PATH=$WEALTH_KG_PATH,\
      APF_KG_PATH=$APF_KG_PATH
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅ Environment variables set!"
        echo ""
        echo "Verifying..."
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
        echo "  - kg_nodes: > 0 (should be much higher than before)"
        echo "  - kg_edges: > 0 (should be much higher than before)"
    else
        echo "❌ Failed to set environment variables"
        exit 1
    fi
else
    echo ""
    echo "Manual setup required:"
    echo ""
    echo "gcloud run services update $SERVICE_NAME \\"
    echo "  --region=$REGION \\"
    echo "  --update-env-vars \\"
    echo "  WEALTH_MANAGEMENT_KG_PATH=$WEALTH_KG_PATH,\\"
    echo "  APF_KG_PATH=$APF_KG_PATH"
fi


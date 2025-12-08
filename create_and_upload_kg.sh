#!/bin/bash
# Script to create kg/ folder and upload master_knowledge_graph.json

BUCKET="wealth-report"
REGION="europe-west6"
SERVICE_NAME="ekg-service"

echo "=========================================="
echo "Create KG Folder and Upload Master File"
echo "=========================================="
echo ""

# Step 1: Create kg/ folder
echo "1️⃣  Creating kg/ folder in gs://$BUCKET/..."
gsutil mkdir gs://$BUCKET/kg/

if [ $? -eq 0 ]; then
    echo "✅ Folder created: gs://$BUCKET/kg/"
else
    echo "⚠️  Folder may already exist or error occurred"
fi

echo ""

# Step 2: Verify folder exists
echo "2️⃣  Verifying folder exists..."
gsutil ls gs://$BUCKET/ | grep "kg/"
if [ $? -eq 0 ]; then
    echo "✅ Folder verified"
else
    echo "❌ Folder not found!"
    exit 1
fi

echo ""

# Step 3: Find master_knowledge_graph.json
echo "3️⃣  Looking for master_knowledge_graph.json..."
echo ""

MASTER_KG_LOCAL=""
POSSIBLE_PATHS=(
    "master_knowledge_graph.json"
    "data/kg/master_knowledge_graph.json"
    "$HOME/Downloads/master_knowledge_graph.json"
    "$HOME/Desktop/master_knowledge_graph.json"
    "./master_knowledge_graph.json"
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
    read -p "Enter full path to master_knowledge_graph.json: " MASTER_KG_LOCAL
    
    if [ ! -f "$MASTER_KG_LOCAL" ]; then
        echo "❌ File not found at: $MASTER_KG_LOCAL"
        echo ""
        echo "Please download the file first, then run this script again."
        exit 1
    fi
fi

echo ""

# Step 4: Upload file
echo "4️⃣  Uploading master_knowledge_graph.json..."
echo ""

gsutil cp "$MASTER_KG_LOCAL" gs://$BUCKET/kg/master_knowledge_graph.json

if [ $? -eq 0 ]; then
    echo "✅ Uploaded successfully!"
    echo ""
    echo "Verifying upload..."
    gsutil ls -lh gs://$BUCKET/kg/master_knowledge_graph.json
    MASTER_KG_GCS="gs://$BUCKET/kg/master_knowledge_graph.json"
else
    echo "❌ Upload failed!"
    exit 1
fi

echo ""

# Step 5: Set Cloud Run environment variables
echo "5️⃣  Setting Cloud Run environment variables..."
echo ""

read -p "Set environment variables in Cloud Run? (y/n): " confirm
if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    echo ""
    echo "Setting environment variables..."
    
    gcloud run services update $SERVICE_NAME \
      --region=$REGION \
      --update-env-vars \
      WEALTH_MANAGEMENT_KG_PATH=$MASTER_KG_GCS,\
      APF_KG_PATH=$MASTER_KG_GCS
    
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
        echo "  - kg_nodes: > 1000 (much higher than before)"
        echo "  - kg_edges: > 1000 (much higher than before)"
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
    echo "  WEALTH_MANAGEMENT_KG_PATH=$MASTER_KG_GCS,\\"
    echo "  APF_KG_PATH=$MASTER_KG_GCS"
fi


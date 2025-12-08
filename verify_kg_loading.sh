#!/bin/bash
# Script to verify KG file loading and graph creation

SERVICE_URL="https://ekg-service-47249889063.europe-west6.run.app"
SERVICE_NAME="ekg-service"
REGION="europe-west6"

echo "=========================================="
echo "KG Loading Verification"
echo "=========================================="
echo ""

# Method 1: Check /domains endpoint
echo "1️⃣  Checking /domains endpoint..."
echo ""

DOMAINS_RESPONSE=$(curl -s "$SERVICE_URL/domains" 2>&1)

if [ $? -eq 0 ]; then
    echo "$DOMAINS_RESPONSE" | python3 -m json.tool 2>/dev/null > /tmp/domains_response.json
    
    if [ $? -eq 0 ]; then
        echo "✅ Successfully retrieved domain information"
        echo ""
        
        # Extract KG loading status
        echo "KG Loading Status:"
        echo "-----------------"
        
        python3 << 'PYTHON'
import json
with open('/tmp/domains_response.json', 'r') as f:
    data = json.load(f)

for domain in data:
    domain_id = domain.get('domain_id', 'unknown')
    kg_loaded = domain.get('kg_loaded', False)
    kg_nodes = domain.get('kg_nodes', 0)
    kg_edges = domain.get('kg_edges', 0)
    
    status = "✅ LOADED" if kg_loaded else "❌ NOT LOADED"
    print(f"\nDomain: {domain_id}")
    print(f"  Status: {status}")
    print(f"  Nodes: {kg_nodes}")
    print(f"  Edges: {kg_edges}")
    
    if kg_loaded and kg_nodes > 0:
        print(f"  ✅ Graph created successfully!")
    elif kg_loaded and kg_nodes == 0:
        print(f"  ⚠️  KG loaded but empty (0 nodes)")
    else:
        print(f"  ❌ KG file not loaded")
PYTHON
        
    else
        echo "❌ Failed to parse JSON response"
        echo "Raw response:"
        echo "$DOMAINS_RESPONSE" | head -20
    fi
else
    echo "❌ Failed to connect to service"
    echo "$DOMAINS_RESPONSE"
fi

echo ""
echo ""

# Method 2: Check logs for KG loading messages
echo "2️⃣  Checking logs for KG loading messages..."
echo ""

if command -v gcloud &> /dev/null; then
    echo "Recent KG loading logs:"
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND (jsonPayload.message=~\"Loading KG\" OR jsonPayload.message=~\"Loaded KG\")" \
      --limit 10 \
      --format="table(timestamp,jsonPayload.message)" 2>&1 | head -15
    
    echo ""
    echo "Recent KG retrieval logs (from diagnostic logging):"
    gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME AND jsonPayload.message=~\"KG retrieval\"" \
      --limit 5 \
      --format="table(timestamp,jsonPayload.message)" 2>&1 | head -10
else
    echo "⚠️  gcloud CLI not available - skipping log check"
fi

echo ""
echo ""

# Method 3: Check if GCS file exists
echo "3️⃣  Checking if KG file exists in GCS..."
echo ""

if command -v gsutil &> /dev/null; then
    echo "Checking gs://wealth-report/kg/master_knowledge_graph.json..."
    gsutil ls -lh gs://wealth-report/kg/master_knowledge_graph.json 2>&1
    
    if [ $? -eq 0 ]; then
        echo "✅ File exists in GCS"
    else
        echo "❌ File not found in GCS!"
        echo ""
        echo "Check if file was uploaded:"
        gsutil ls gs://wealth-report/kg/ 2>&1
    fi
else
    echo "⚠️  gsutil not available - skipping GCS check"
fi

echo ""
echo ""

# Method 4: Check environment variables
echo "4️⃣  Checking Cloud Run environment variables..."
echo ""

if command -v gcloud &> /dev/null; then
    echo "KG_PATH variables:"
    gcloud run services describe $SERVICE_NAME \
      --region=$REGION \
      --format="value(spec.template.spec.containers[0].env)" 2>&1 | grep -i "KG_PATH" || echo "❌ KG_PATH variables not found!"
else
    echo "⚠️  gcloud CLI not available - skipping env var check"
fi

echo ""
echo ""

# Method 5: Test with a query
echo "5️⃣  Testing with a sample query..."
echo ""

TEST_RESPONSE=$(curl -s -X POST "$SERVICE_URL/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is OTP?",
    "domain": "wealth_management",
    "params": {"_mode": "concise"}
  }' 2>&1)

if echo "$TEST_RESPONSE" | python3 -c "import json, sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "✅ Query successful"
    
    # Check for KG-related content in response
    if echo "$TEST_RESPONSE" | grep -qi "kg\|knowledge\|graph"; then
        echo "✅ Response contains KG-related content"
    fi
    
    # Check meta information
    echo ""
    echo "Response metadata:"
    echo "$TEST_RESPONSE" | python3 -c "import json, sys; d=json.load(sys.stdin); print(f\"  Domain: {d.get('meta', {}).get('domain', 'N/A')}\"); print(f\"  Mode: {d.get('meta', {}).get('mode', 'N/A')}\"); print(f\"  Processing time: {d.get('meta', {}).get('processing_time_seconds', 'N/A')}s\")" 2>/dev/null
    
else
    echo "❌ Query failed or invalid response"
    echo "Response:"
    echo "$TEST_RESPONSE" | head -10
fi

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo ""
echo "✅ Check /domains endpoint for kg_loaded status"
echo "✅ Check logs for 'Loading KG' or 'Loaded KG' messages"
echo "✅ Check logs for 'KG retrieval' diagnostic messages"
echo "✅ Verify GCS file exists and is accessible"
echo "✅ Verify environment variables are set"
echo "✅ Test with a query to see if KG is being used"
echo ""


#!/bin/bash
# cURL examples for testing EKG Agent API

BASE_URL="http://localhost:8000"

echo "🧪 EKG AGENT API - cURL TESTING EXAMPLES"
echo "=========================================="

# Test 1: Health check
echo -e "\n1. Testing health endpoint..."
curl -s "$BASE_URL/health" | jq '.' || echo "Health check failed"

# Test 2: List domains
echo -e "\n2. Testing domains endpoint..."
curl -s "$BASE_URL/domains" | jq '.' || echo "Domains check failed"

# Test 3: Basic query
echo -e "\n3. Testing basic query..."
RESPONSE=$(curl -s -X POST "$BASE_URL/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is OTP verification?",
    "domain": "wealth_management"
  }')

echo "$RESPONSE" | jq '.' || echo "Basic query failed"

# Extract response_id for conversational test
RESPONSE_ID=$(echo "$RESPONSE" | jq -r '.response_id' 2>/dev/null)

if [ "$RESPONSE_ID" != "null" ] && [ "$RESPONSE_ID" != "" ]; then
    echo -e "\n4. Testing conversational follow-up..."
    curl -s -X POST "$BASE_URL/v1/answer" \
      -H "Content-Type: application/json" \
      -d "{
        \"question\": \"How long is the OTP valid?\",
        \"domain\": \"wealth_management\",
        \"response_id\": \"$RESPONSE_ID\"
      }" | jq '.' || echo "Conversational test failed"
else
    echo -e "\n4. Skipping conversational test (no response_id)"
fi

# Test 5: APF domain
echo -e "\n5. Testing APF domain..."
curl -s -X POST "$BASE_URL/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the APF approval process?",
    "domain": "apf"
  }' | jq '.' || echo "APF domain test failed"

# Test 6: Conversation ID
echo -e "\n6. Testing conversation_id..."
curl -s -X POST "$BASE_URL/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the redemption process?",
    "domain": "wealth_management",
    "conversation_id": "test-conversation-123"
  }' | jq '.' || echo "Conversation ID test failed"

# Test 7: Error handling
echo -e "\n7. Testing error handling..."
echo "   Testing invalid domain..."
curl -s -X POST "$BASE_URL/v1/answer" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Test question",
    "domain": "invalid_domain"
  }' | jq '.' || echo "Error handling test failed"

echo -e "\n✅ cURL testing completed!"

# 🧪 Third-Party API Testing Guide

**EKG Agent API Testing from External Systems**

---

## 🚀 Quick Start

### 1. Start the Server
```bash
# Set your OpenAI API key
export OPENAI_API_KEY=sk-proj-your-actual-key-here

# Start the server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Test Basic Connectivity
```bash
# Health check
curl http://localhost:8000/health

# List domains
curl http://localhost:8000/domains
```

---

## 📋 API Endpoints Reference

### Base URL
```
http://localhost:8000
```

### Available Endpoints
- `GET /health` - Health check with domain status
- `GET /domains` - List all available domains
- `POST /v1/answer` - Query with conversational support

---

## 🔧 Testing Methods

### Method 1: cURL Commands

#### Basic Query
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is OTP verification?",
    "domain": "wealth_management"
  }'
```

#### Conversational Follow-up
```bash
# First, get a response_id from the above query, then:
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How long is the OTP valid?",
    "domain": "wealth_management",
    "response_id": "YOUR_RESPONSE_ID_HERE"
  }'
```

#### APF Domain Query
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the APF approval process?",
    "domain": "apf"
  }'
```

### Method 2: Python Scripts

#### Basic Python Test
```python
import requests
import json

# Test basic functionality
def test_ekg_api():
    base_url = "http://localhost:8000"
    
    # 1. Health check
    print("1. Testing health endpoint...")
    health_response = requests.get(f"{base_url}/health")
    print(f"Health Status: {health_response.status_code}")
    print(f"Health Data: {health_response.json()}")
    
    # 2. List domains
    print("\n2. Testing domains endpoint...")
    domains_response = requests.get(f"{base_url}/domains")
    print(f"Domains Status: {domains_response.status_code}")
    domains = domains_response.json()
    print(f"Available Domains: {[d['domain_id'] for d in domains['domains']]}")
    
    # 3. Test query
    print("\n3. Testing answer endpoint...")
    query_payload = {
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    }
    
    answer_response = requests.post(
        f"{base_url}/v1/answer",
        json=query_payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Answer Status: {answer_response.status_code}")
    if answer_response.status_code == 200:
        answer_data = answer_response.json()
        print(f"Response ID: {answer_data.get('response_id')}")
        print(f"Answer Preview: {answer_data.get('markdown', '')[:100]}...")
        print(f"Is Conversational: {answer_data.get('meta', {}).get('is_conversational', False)}")
    else:
        print(f"Error: {answer_response.text}")

if __name__ == "__main__":
    test_ekg_api()
```

#### Conversational Python Test
```python
import requests
import json

def test_conversational_flow():
    base_url = "http://localhost:8000"
    
    print("Testing Conversational Flow...")
    
    # Step 1: Initial question
    print("\n1. Initial question...")
    response1 = requests.post(f"{base_url}/v1/answer", json={
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    })
    
    if response1.status_code == 200:
        data1 = response1.json()
        response_id = data1.get('response_id')
        print(f"✓ Initial response ID: {response_id}")
        
        # Step 2: Follow-up using response_id
        print("\n2. Follow-up with response_id...")
        response2 = requests.post(f"{base_url}/v1/answer", json={
            "question": "How long is the OTP valid?",
            "domain": "wealth_management",
            "response_id": response_id
        })
        
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"✓ Follow-up response ID: {data2.get('response_id')}")
            print(f"✓ Is Conversational: {data2.get('meta', {}).get('is_conversational', False)}")
            print(f"✓ Previous Response ID: {data2.get('meta', {}).get('previous_response_id')}")
        else:
            print(f"✗ Follow-up failed: {response2.text}")
    else:
        print(f"✗ Initial question failed: {response1.text}")

if __name__ == "__main__":
    test_conversational_flow()
```

### Method 3: JavaScript/Node.js

#### Node.js Test Script
```javascript
const axios = require('axios');

async function testEkgApi() {
    const baseUrl = 'http://localhost:8000';
    
    try {
        // 1. Health check
        console.log('1. Testing health endpoint...');
        const healthResponse = await axios.get(`${baseUrl}/health`);
        console.log(`Health Status: ${healthResponse.status}`);
        console.log(`Health Data:`, healthResponse.data);
        
        // 2. List domains
        console.log('\n2. Testing domains endpoint...');
        const domainsResponse = await axios.get(`${baseUrl}/domains`);
        console.log(`Domains Status: ${domainsResponse.status}`);
        const domains = domainsResponse.data.domains.map(d => d.domain_id);
        console.log(`Available Domains: ${domains}`);
        
        // 3. Test query
        console.log('\n3. Testing answer endpoint...');
        const answerResponse = await axios.post(`${baseUrl}/v1/answer`, {
            question: "What is OTP verification?",
            domain: "wealth_management"
        });
        
        console.log(`Answer Status: ${answerResponse.status}`);
        const answerData = answerResponse.data;
        console.log(`Response ID: ${answerData.response_id}`);
        console.log(`Answer Preview: ${answerData.markdown.substring(0, 100)}...`);
        console.log(`Is Conversational: ${answerData.meta.is_conversational}`);
        
    } catch (error) {
        console.error('Error:', error.response?.data || error.message);
    }
}

testEkgApi();
```

### Method 4: Postman Collection

#### Postman Setup
1. **Create New Collection**: "EKG Agent API Tests"
2. **Set Base URL**: `http://localhost:8000`
3. **Add Environment Variables**:
   - `base_url`: `http://localhost:8000`
   - `response_id`: (will be set dynamically)

#### Postman Requests

**Request 1: Health Check**
```
GET {{base_url}}/health
```

**Request 2: List Domains**
```
GET {{base_url}}/domains
```

**Request 3: Basic Query**
```
POST {{base_url}}/v1/answer
Content-Type: application/json

{
    "question": "What is OTP verification?",
    "domain": "wealth_management"
}
```

**Request 4: Conversational Follow-up**
```
POST {{base_url}}/v1/answer
Content-Type: application/json

{
    "question": "How long is the OTP valid?",
    "domain": "wealth_management",
    "response_id": "{{response_id}}"
}
```

**Request 5: APF Domain Query**
```
POST {{base_url}}/v1/answer
Content-Type: application/json

{
    "question": "What is the APF approval process?",
    "domain": "apf"
}
```

### Method 5: HTTPie

#### Install HTTPie
```bash
pip install httpie
```

#### Test Commands
```bash
# Health check
http GET localhost:8000/health

# List domains
http GET localhost:8000/domains

# Basic query
http POST localhost:8000/v1/answer \
  question="What is OTP verification?" \
  domain="wealth_management"

# Conversational follow-up
http POST localhost:8000/v1/answer \
  question="How long is the OTP valid?" \
  domain="wealth_management" \
  response_id="YOUR_RESPONSE_ID_HERE"
```

---

## 🔍 Testing Scenarios

### Scenario 1: Basic Functionality
```bash
# Test all endpoints
curl http://localhost:8000/health
curl http://localhost:8000/domains
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What is OTP?", "domain": "wealth_management"}'
```

### Scenario 2: Multi-Domain Testing
```bash
# Test wealth_management domain
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What is redemption?", "domain": "wealth_management"}'

# Test APF domain
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What is project approval?", "domain": "apf"}'
```

### Scenario 3: Conversational Flow
```bash
# Step 1: Initial question
RESPONSE=$(curl -s -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What is OTP verification?", "domain": "wealth_management"}')

# Extract response_id
RESPONSE_ID=$(echo $RESPONSE | jq -r '.response_id')
echo "Response ID: $RESPONSE_ID"

# Step 2: Follow-up
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"How long is the OTP valid?\", \"domain\": \"wealth_management\", \"response_id\": \"$RESPONSE_ID\"}"
```

### Scenario 4: Error Handling
```bash
# Test invalid domain
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "Test question", "domain": "invalid_domain"}'

# Test malformed request
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "Test question"}'
```

---

## 📊 Response Validation

### Expected Response Structure
```json
{
  "response_id": "uuid-string",
  "markdown": "Answer content...",
  "sources": [...],
  "meta": {
    "domain": "wealth_management",
    "vectorstore_id": "vs_...",
    "is_conversational": false,
    "model": "gpt-4o",
    "mode": "balanced"
  }
}
```

### Validation Checklist
- [ ] `response_id` is present and valid UUID
- [ ] `markdown` contains answer content
- [ ] `meta.domain` matches request domain
- [ ] `meta.is_conversational` is boolean
- [ ] `meta.model` is present
- [ ] `meta.mode` is one of: concise, balanced, deep

---

## 🚨 Troubleshooting

### Common Issues

**1. Connection Refused**
```bash
# Check if server is running
curl http://localhost:8000/health
# If fails, start server:
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**2. 401 Unauthorized**
```bash
# Check OpenAI API key
export OPENAI_API_KEY=sk-proj-your-actual-key-here
```

**3. 500 Internal Server Error**
```bash
# Check server logs
# Usually indicates missing dependencies or configuration
```

**4. 400 Bad Request**
```bash
# Check request format
# Ensure Content-Type: application/json
# Validate required fields: question, domain
```

### Debug Commands
```bash
# Check server status
curl -v http://localhost:8000/health

# Test with verbose output
curl -v -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "Test", "domain": "wealth_management"}'

# Check response headers
curl -I http://localhost:8000/health
```

---

## 📱 Mobile/App Testing

### React Native Example
```javascript
import axios from 'axios';

const testEkgApi = async () => {
    try {
        const response = await axios.post('http://localhost:8000/v1/answer', {
            question: "What is OTP verification?",
            domain: "wealth_management"
        });
        
        console.log('Response:', response.data);
        return response.data;
    } catch (error) {
        console.error('Error:', error);
    }
};
```

### Flutter Example
```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Future<Map<String, dynamic>> testEkgApi() async {
  final response = await http.post(
    Uri.parse('http://localhost:8000/v1/answer'),
    headers: {'Content-Type': 'application/json'},
    body: json.encode({
      'question': 'What is OTP verification?',
      'domain': 'wealth_management'
    }),
  );
  
  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to load data');
  }
}
```

---

## 🔧 Production Testing

### Load Testing with Apache Bench
```bash
# Install Apache Bench
# Ubuntu: sudo apt-get install apache2-utils
# macOS: brew install httpd

# Test health endpoint
ab -n 100 -c 10 http://localhost:8000/health

# Test answer endpoint
ab -n 50 -c 5 -p test_payload.json -T application/json http://localhost:8000/v1/answer
```

### Test Payload File (test_payload.json)
```json
{
  "question": "What is OTP verification?",
  "domain": "wealth_management"
}
```

---

## 📋 Testing Checklist

### Pre-Testing Setup
- [ ] Server is running on correct port
- [ ] OpenAI API key is configured
- [ ] Knowledge graphs are loaded
- [ ] Network connectivity is working

### Basic Functionality
- [ ] Health endpoint responds
- [ ] Domains endpoint lists available domains
- [ ] Answer endpoint returns valid responses
- [ ] Response includes required fields

### Conversational Features
- [ ] response_id is included in responses
- [ ] Follow-up queries work with response_id
- [ ] conversation_id works for threading
- [ ] Metadata includes conversational flags

### Error Handling
- [ ] Invalid domains return 400
- [ ] Malformed requests return 400
- [ ] Server errors return 500
- [ ] Network timeouts are handled

### Performance
- [ ] Response times are acceptable
- [ ] Concurrent requests work
- [ ] Memory usage is stable
- [ ] No memory leaks

---

## 🎯 Ready for Integration

Your EKG Agent API is ready for third-party integration with:
- ✅ RESTful API endpoints
- ✅ JSON request/response format
- ✅ Conversational support
- ✅ Multi-domain capability
- ✅ Comprehensive error handling
- ✅ Production-ready performance

**Start testing and integrating!** 🚀

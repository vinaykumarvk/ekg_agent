#!/usr/bin/env python3
"""
Test script to demonstrate the new response ID functionality
"""
import json
import requests
import time

def test_response_id():
    """Test that response IDs are included in API responses"""
    
    print("="*60)
    print("TESTING RESPONSE ID FUNCTIONALITY")
    print("="*60)
    
    # Start server (in background)
    print("Starting server...")
    import subprocess
    import os
    
    # Set dummy API key for testing
    os.environ["OPENAI_API_KEY"] = "dummy-key-for-testing"
    
    # Start server in background
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", "api.main:app", 
        "--host", "0.0.0.0", "--port", "8000"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test 1: Check if server is running
        print("\n1. Testing server health...")
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✓ Server is running")
            else:
                print(f"✗ Server health check failed: {response.status_code}")
                return
        except requests.exceptions.RequestException as e:
            print(f"✗ Cannot connect to server: {e}")
            return
        
        # Test 2: Check domains endpoint
        print("\n2. Testing domains endpoint...")
        try:
            response = requests.get("http://localhost:8000/domains", timeout=5)
            if response.status_code == 200:
                domains = response.json()
                print(f"✓ Found {len(domains['domains'])} domains")
            else:
                print(f"✗ Domains endpoint failed: {response.status_code}")
        except Exception as e:
            print(f"✗ Domains test failed: {e}")
        
        # Test 3: Test answer endpoint with response ID
        print("\n3. Testing answer endpoint with response ID...")
        try:
            payload = {
                "question": "What is OTP verification?",
                "domain": "wealth_management"
            }
            
            response = requests.post(
                "http://localhost:8000/v1/answer",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if response_id is present
                if "response_id" in data:
                    print("✓ Response ID included in response")
                    print(f"  Response ID: {data['response_id']}")
                else:
                    print("✗ Response ID missing from response")
                
                # Check other fields
                if "markdown" in data:
                    print("✓ Markdown content present")
                    print(f"  Content length: {len(data['markdown'])} chars")
                
                if "meta" in data:
                    print("✓ Metadata present")
                    print(f"  Meta keys: {list(data['meta'].keys())}")
                
                # Show full response structure
                print("\n📋 Full Response Structure:")
                print(json.dumps({
                    "response_id": data.get("response_id"),
                    "markdown_preview": data.get("markdown", "")[:100] + "...",
                    "sources_count": len(data.get("sources", [])),
                    "meta": data.get("meta", {})
                }, indent=2))
                
            else:
                print(f"✗ Answer endpoint failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Answer test failed: {e}")
        
        # Test 4: Test multiple requests to verify unique IDs
        print("\n4. Testing unique response IDs...")
        try:
            response_ids = []
            for i in range(3):
                payload = {
                    "question": f"Test question {i+1}",
                    "domain": "wealth_management"
                }
                
                response = requests.post(
                    "http://localhost:8000/v1/answer",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=30
                )
                
                if response.status_code == 200:
                    data = response.json()
                    response_ids.append(data.get("response_id"))
                    print(f"  Request {i+1}: {data.get('response_id')}")
            
            # Check if all IDs are unique
            unique_ids = set(response_ids)
            if len(unique_ids) == len(response_ids):
                print("✓ All response IDs are unique")
            else:
                print("✗ Duplicate response IDs found")
                
        except Exception as e:
            print(f"✗ Unique ID test failed: {e}")
    
    finally:
        # Clean up server
        print("\n5. Cleaning up...")
        server_process.terminate()
        server_process.wait()
        print("✓ Server stopped")

if __name__ == "__main__":
    test_response_id()

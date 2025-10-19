#!/usr/bin/env python3
"""
Test script to verify KG file accessibility in deployed container
"""
import requests
import json
import os

def test_kg_access():
    """Test KG file accessibility through the deployed API"""
    base_url = os.getenv("BASE_URL", "https://ekg-service-47249889063.europe-west6.run.app")
    
    print("🔍 Testing KG file accessibility in deployed container...")
    
    # Test 1: Health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        response.raise_for_status()
        health_data = response.json()
        print("✅ Health endpoint accessible")
        print(f"   Status: {health_data.get('status')}")
        
        # Check domains status
        domains_status = health_data.get('domains', {})
        print(f"   Domains: {list(domains_status.keys())}")
        for domain_id, status in domains_status.items():
            print(f"   {domain_id}: loaded={status.get('loaded')}, nodes={status.get('nodes')}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check failed: {e}")
        return False
    
    # Test 2: KG status endpoint
    print("\n2. Testing KG status endpoint...")
    try:
        response = requests.get(f"{base_url}/kg-status", timeout=10)
        response.raise_for_status()
        kg_status_data = response.json()
        print("✅ KG status endpoint accessible")
        
        # Check data directory
        print(f"   Data directory exists: {kg_status_data.get('data_directory_exists')}")
        print(f"   KG directory exists: {kg_status_data.get('kg_directory_exists')}")
        
        # Check KG files
        kg_files = kg_status_data.get('kg_files', {})
        print(f"   KG files found: {len(kg_files)}")
        for domain_id, file_status in kg_files.items():
            print(f"   {domain_id}: exists={file_status.get('exists')}, valid_json={file_status.get('valid_json')}")
            
        # Check for errors
        errors = kg_status_data.get('errors', [])
        if errors:
            print("   ⚠️  Errors found:")
            for error in errors:
                print(f"     - {error}")
                
    except requests.exceptions.RequestException as e:
        print(f"❌ KG status check failed: {e}")
        return False
    
    # Test 3: Simple API call
    print("\n3. Testing simple API call...")
    try:
        test_payload = {
            "question": "What is OTP?",
            "domain": "wealth_management",
            "params": {"_mode": "concise"}
        }
        
        response = requests.post(f"{base_url}/v1/answer", json=test_payload, timeout=300)  # 5 minutes
        response.raise_for_status()
        answer_data = response.json()
        
        print("✅ API call successful")
        print(f"   Response ID: {answer_data.get('response_id')}")
        print(f"   Mode: {answer_data.get('meta', {}).get('mode')}")
        print(f"   Processing time: {answer_data.get('meta', {}).get('processing_time_seconds')}s")
        
        # Check if response contains actual content
        markdown = answer_data.get('markdown', '')
        if len(markdown) > 50:
            print("✅ Response contains substantial content")
        else:
            print("⚠️  Response seems short, might indicate KG access issues")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ API call failed: {e}")
        return False
    
    print("\n🎉 All KG access tests passed!")
    return True

if __name__ == "__main__":
    success = test_kg_access()
    if not success:
        print("\n💥 Some KG access tests failed!")
        exit(1)
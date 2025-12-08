#!/usr/bin/env python3
"""
Test script to verify the refactored code works with mode='concise'
"""
import requests
import json
import sys
import os

# Default to localhost, but allow override
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")

def test_concise_mode():
    """Test the /v1/answer endpoint with mode='concise'"""
    print("=" * 80)
    print("🧪 Testing EKG Agent API with mode='concise'")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}\n")
    
    # First, check health
    print("1. Checking health endpoint...")
    try:
        health_response = requests.get(f"{BASE_URL}/health", timeout=10)
        health_response.raise_for_status()
        health_data = health_response.json()
        print(f"   ✅ Health check passed")
        print(f"   Status: {health_data.get('status')}")
        
        # Check available domains
        domains = health_data.get('domains', {})
        if not domains:
            print("   ⚠️  No domains loaded!")
            return False
        
        # Use first available domain
        domain_id = list(domains.keys())[0]
        print(f"   Using domain: {domain_id}")
        print()
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Health check failed: {e}")
        print(f"   Make sure the server is running: uvicorn api.main:app --host 0.0.0.0 --port 8000")
        return False
    
    # Test question
    test_question = "What is CRR and PRR logic for order placement?"
    
    # Prepare request payload
    payload = {
        "question": test_question,
        "domain": domain_id,
        "params": {
            "_mode": "concise"
        }
    }
    
    print("2. Testing /v1/answer endpoint with mode='concise'...")
    print(f"   Question: {test_question}")
    print(f"   Domain: {domain_id}")
    print(f"   Mode: concise")
    print()
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/answer",
            json=payload,
            timeout=120  # Longer timeout for LLM calls
        )
        
        print(f"   Status Code: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Request failed!")
            print(f"   Response: {response.text}")
            return False
        
        result = response.json()
        
        print(f"   ✅ Request successful!")
        print()
        print("3. Response Details:")
        print(f"   Response ID: {result.get('response_id', 'N/A')}")
        print(f"   Mode: {result.get('meta', {}).get('mode', 'N/A')}")
        print()
        
        # Check if markdown response exists
        if result.get('markdown'):
            markdown = result['markdown']
            print("4. Answer Preview (first 500 chars):")
            print("-" * 80)
            print(markdown[:500])
            if len(markdown) > 500:
                print("...")
            print("-" * 80)
            print(f"   Total answer length: {len(markdown)} characters")
        else:
            print("   ⚠️  No markdown response found")
        
        # Check sources
        sources = result.get('sources')
        if sources:
            print(f"\n5. Sources: {len(sources) if isinstance(sources, list) else 'N/A'}")
        
        # Check meta information
        meta = result.get('meta', {})
        if meta:
            print(f"\n6. Metadata:")
            print(f"   Model: {meta.get('model_used', 'N/A')}")
            print(f"   Mode: {meta.get('mode', 'N/A')}")
            print(f"   Domain: {meta.get('domain', 'N/A')}")
            if 'prompt_chars' in meta:
                print(f"   Prompt chars: {meta.get('prompt_chars', 'N/A')}")
        
        print()
        print("=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)
        return True
        
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out (may take longer than 120s)")
        return False
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Request failed: {e}")
        return False
    except json.JSONDecodeError as e:
        print(f"   ❌ Failed to parse JSON response: {e}")
        print(f"   Response text: {response.text[:500]}")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_concise_mode()
    sys.exit(0 if success else 1)



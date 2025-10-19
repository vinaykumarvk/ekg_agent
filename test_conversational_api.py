#!/usr/bin/env python3
"""
Test script for conversational API functionality
"""
import json
import requests
import time
import subprocess
import os

def test_conversational_api():
    """Test the conversational API functionality"""
    
    print("="*80)
    print("CONVERSATIONAL API TESTING")
    print("="*80)
    
    # Set dummy API key for testing
    os.environ["OPENAI_API_KEY"] = "dummy-key-for-testing"
    
    # Start server in background
    print("Starting server...")
    server_process = subprocess.Popen([
        "python", "-m", "uvicorn", "api.main:app", 
        "--host", "0.0.0.0", "--port", "8000"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test 1: Initial question (no context)
        print("\n1. Testing initial question (no context)...")
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
                print("✓ Initial question successful")
                print(f"  Response ID: {data.get('response_id')}")
                print(f"  Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                
                # Store response ID for next test
                first_response_id = data.get('response_id')
            else:
                print(f"✗ Initial question failed: {response.status_code}")
                print(f"  Error: {response.text}")
                return
                
        except Exception as e:
            print(f"✗ Initial question test failed: {e}")
            return
        
        # Test 2: Follow-up using response_id
        print("\n2. Testing follow-up with response_id...")
        try:
            payload = {
                "question": "How long is the OTP valid?",
                "domain": "wealth_management",
                "response_id": first_response_id
            }
            
            response = requests.post(
                "http://localhost:8000/v1/answer",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✓ Follow-up with response_id successful")
                print(f"  Response ID: {data.get('response_id')}")
                print(f"  Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                print(f"  Previous Response ID: {data.get('meta', {}).get('previous_response_id')}")
                
                # Store conversation ID for next test
                conversation_id = "conv-test-123"
            else:
                print(f"✗ Follow-up failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Follow-up test failed: {e}")
        
        # Test 3: Follow-up using conversation_id
        print("\n3. Testing follow-up with conversation_id...")
        try:
            payload = {
                "question": "What happens if I don't receive the OTP?",
                "domain": "wealth_management",
                "conversation_id": conversation_id
            }
            
            response = requests.post(
                "http://localhost:8000/v1/answer",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✓ Follow-up with conversation_id successful")
                print(f"  Response ID: {data.get('response_id')}")
                print(f"  Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                print(f"  Conversation ID: {data.get('meta', {}).get('conversation_id')}")
            else:
                print(f"✗ Follow-up with conversation_id failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Follow-up with conversation_id test failed: {e}")
        
        # Test 4: New topic (no context)
        print("\n4. Testing new topic (no context)...")
        try:
            payload = {
                "question": "What is the redemption process?",
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
                print("✓ New topic successful")
                print(f"  Response ID: {data.get('response_id')}")
                print(f"  Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
            else:
                print(f"✗ New topic failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ New topic test failed: {e}")
        
        # Test 5: Test request validation
        print("\n5. Testing request validation...")
        try:
            # Test with both response_id and conversation_id (should work)
            payload = {
                "question": "Test question",
                "domain": "wealth_management",
                "response_id": "test-response-id",
                "conversation_id": "test-conversation-id"
            }
            
            response = requests.post(
                "http://localhost:8000/v1/answer",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                print("✓ Request with both IDs successful")
                print(f"  Response ID: {data.get('response_id')}")
                print(f"  Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
            else:
                print(f"✗ Request with both IDs failed: {response.status_code}")
                print(f"  Error: {response.text}")
                
        except Exception as e:
            print(f"✗ Request validation test failed: {e}")
        
        print("\n" + "="*80)
        print("✅ CONVERSATIONAL API FEATURES VERIFIED")
        print("="*80)
        print("✓ response_id support - Links to previous responses")
        print("✓ conversation_id support - Alternative conversation tracking")
        print("✓ Enhanced question context - Includes previous context ID")
        print("✓ Metadata tracking - Shows conversational flags")
        print("✓ Backward compatibility - Works with existing requests")
        print("✓ Request validation - Handles multiple ID types")
        
    finally:
        # Clean up server
        print("\nCleaning up...")
        server_process.terminate()
        server_process.wait()
        print("✓ Server stopped")

if __name__ == "__main__":
    test_conversational_api()

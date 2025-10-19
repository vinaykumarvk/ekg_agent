#!/usr/bin/env python3
"""
Demo script showing the new response ID structure
"""
import json
import uuid
from api.schemas import AskResponse
from api.main import _normalize_answer

def demo_response_structure():
    """Demonstrate the new response structure with response IDs"""
    
    print("="*70)
    print("EKG AGENT - RESPONSE ID DEMONSTRATION")
    print("="*70)
    
    # Simulate different types of responses from the agent
    test_cases = [
        {
            "name": "Hybrid Answer (KG + Vector)",
            "data": {
                "answer": "OTP verification is a two-factor authentication process that requires users to enter a one-time password sent to their registered mobile number. This ensures secure access to financial transactions and account management features.",
                "curated_chunks": [
                    {"text": "OTP is sent to registered mobile number", "filename": "security_guide.pdf"},
                    {"text": "Two-factor authentication process", "filename": "auth_manual.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "balanced",
                "export_path": "./outputs/otp-verification--20241019-1430.md"
            }
        },
        {
            "name": "Vector-Only Answer",
            "data": {
                "answer": "The redemption process allows investors to withdraw their mutual fund investments by submitting a redemption request through the online portal or mobile app.",
                "curated_chunks": [
                    {"text": "Redemption process steps", "filename": "redemption_guide.pdf"},
                    {"text": "Online portal submission", "filename": "user_manual.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "concise"
            }
        },
        {
            "name": "KG-Only Answer",
            "data": {
                "answer": "APF approval workflow involves multiple stages including initial review, compliance check, and final authorization by designated approvers.",
                "model_used": "gpt-4o",
                "mode": "deep"
            }
        }
    ]
    
    print("\n📋 RESPONSE STRUCTURE EXAMPLES")
    print("="*70)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 50)
        
        # Generate response ID
        response_id = str(uuid.uuid4())
        
        # Create response using the new structure
        response = _normalize_answer(test_case['data'], response_id)
        
        # Display the response structure
        print(f"Response ID: {response.response_id}")
        print(f"Markdown: {response.markdown[:100]}...")
        print(f"Sources: {len(response.sources) if response.sources else 0} items")
        print(f"Meta: {response.meta}")
        
        # Show JSON structure
        print("\n📄 JSON Response Structure:")
        json_response = {
            "response_id": response.response_id,
            "markdown": response.markdown,
            "sources": response.sources,
            "meta": response.meta
        }
        print(json.dumps(json_response, indent=2, default=str))
    
    print("\n" + "="*70)
    print("✅ RESPONSE ID FEATURES")
    print("="*70)
    print("✓ Unique UUID for each response")
    print("✓ Included in both response body and metadata")
    print("✓ Can be used for tracking and follow-up queries")
    print("✓ Backward compatible (existing clients will get response_id)")
    print("✓ Suitable for conversation threading")
    
    print("\n🔗 USAGE FOR FOLLOW-UP QUERIES")
    print("="*70)
    print("You can now include the response_id in subsequent requests:")
    print("""
    # Initial query
    POST /v1/answer
    {
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    }
    
    # Response includes response_id
    {
        "response_id": "123e4567-e89b-12d3-a456-426614174000",
        "markdown": "OTP verification is...",
        "sources": [...],
        "meta": {...}
    }
    
    # Follow-up query (if you implement conversation threading)
    POST /v1/answer
    {
        "question": "How long is the OTP valid?",
        "domain": "wealth_management",
        "conversation_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    """)

if __name__ == "__main__":
    demo_response_structure()

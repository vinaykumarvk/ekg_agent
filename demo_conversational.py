#!/usr/bin/env python3
"""
Demo script showing conversational response functionality
"""
import json
import uuid
from api.schemas import AskRequest, AskResponse
from api.main import _normalize_answer

def demo_conversational_flow():
    """Demonstrate conversational response flow"""
    
    print("="*80)
    print("EKG AGENT - CONVERSATIONAL RESPONSE DEMONSTRATION")
    print("="*80)
    
    # Simulate a conversation flow
    conversation_flow = [
        {
            "step": 1,
            "description": "Initial Question",
            "request": {
                "question": "What is OTP verification?",
                "domain": "wealth_management"
            }
        },
        {
            "step": 2,
            "description": "Follow-up Question (using response_id)",
            "request": {
                "question": "How long is the OTP valid?",
                "domain": "wealth_management",
                "response_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        },
        {
            "step": 3,
            "description": "Another Follow-up (using conversation_id)",
            "request": {
                "question": "What happens if I don't receive the OTP?",
                "domain": "wealth_management",
                "conversation_id": "conv-abc123-def456"
            }
        },
        {
            "step": 4,
            "description": "New Topic (no context)",
            "request": {
                "question": "What is the redemption process?",
                "domain": "wealth_management"
            }
        }
    ]
    
    print("\n📋 CONVERSATION FLOW SIMULATION")
    print("="*80)
    
    for step_info in conversation_flow:
        print(f"\n{step_info['step']}. {step_info['description']}")
        print("-" * 60)
        
        # Create request object
        request = AskRequest(**step_info['request'])
        
        # Simulate response generation
        response_id = request.response_id or request.conversation_id or str(uuid.uuid4())
        
        # Simulate agent response based on context
        if step_info['step'] == 1:
            # Initial response
            agent_data = {
                "answer": "OTP verification is a two-factor authentication process that requires users to enter a one-time password sent to their registered mobile number.",
                "curated_chunks": [
                    {"text": "OTP is sent to registered mobile number", "filename": "security_guide.pdf"},
                    {"text": "Two-factor authentication process", "filename": "auth_manual.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "balanced"
            }
        elif step_info['step'] == 2:
            # Follow-up with context
            agent_data = {
                "answer": "The OTP is typically valid for 5-10 minutes. After this period, you'll need to request a new OTP for security purposes.",
                "curated_chunks": [
                    {"text": "OTP validity period is 5-10 minutes", "filename": "otp_policy.pdf"},
                    {"text": "Security timeout requirements", "filename": "security_guide.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "balanced"
            }
        elif step_info['step'] == 3:
            # Another follow-up
            agent_data = {
                "answer": "If you don't receive the OTP, you can request a new one after the timeout period. Check your mobile number registration and network connectivity.",
                "curated_chunks": [
                    {"text": "OTP resend process", "filename": "troubleshooting.pdf"},
                    {"text": "Mobile number verification", "filename": "user_guide.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "balanced"
            }
        else:
            # New topic
            agent_data = {
                "answer": "The redemption process allows investors to withdraw their mutual fund investments by submitting a redemption request through the online portal.",
                "curated_chunks": [
                    {"text": "Redemption process steps", "filename": "redemption_guide.pdf"},
                    {"text": "Online portal submission", "filename": "user_manual.pdf"}
                ],
                "model_used": "gpt-4o",
                "mode": "balanced"
            }
        
        # Create response
        response = _normalize_answer(agent_data, response_id)
        
        # Display request details
        print("📤 REQUEST:")
        request_dict = {
            "question": request.question,
            "domain": request.domain,
            "response_id": request.response_id,
            "conversation_id": request.conversation_id
        }
        print(json.dumps({k: v for k, v in request_dict.items() if v is not None}, indent=2))
        
        # Display response details
        print("\n📥 RESPONSE:")
        response_dict = {
            "response_id": response.response_id,
            "markdown": response.markdown[:100] + "...",
            "meta": response.meta
        }
        print(json.dumps(response_dict, indent=2, default=str))
        
        # Show conversational context
        if request.response_id or request.conversation_id:
            print("\n🔄 CONVERSATIONAL CONTEXT:")
            print(f"  Previous Response ID: {request.response_id}")
            print(f"  Conversation ID: {request.conversation_id}")
            print(f"  Is Conversational: {response.meta.get('is_conversational', False)}")
    
    print("\n" + "="*80)
    print("✅ CONVERSATIONAL FEATURES")
    print("="*80)
    print("✓ response_id - Links to previous response")
    print("✓ conversation_id - Alternative conversation tracking")
    print("✓ Enhanced question context - Includes previous context ID")
    print("✓ Metadata tracking - Shows conversational flags")
    print("✓ Backward compatible - Works with existing requests")
    
    print("\n🔗 USAGE EXAMPLES")
    print("="*80)
    print("""
    # 1. Initial question (no context)
    POST /v1/answer
    {
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    }
    
    # 2. Follow-up using response_id
    POST /v1/answer
    {
        "question": "How long is the OTP valid?",
        "domain": "wealth_management",
        "response_id": "123e4567-e89b-12d3-a456-426614174000"
    }
    
    # 3. Follow-up using conversation_id
    POST /v1/answer
    {
        "question": "What if I don't receive it?",
        "domain": "wealth_management",
        "conversation_id": "conv-abc123-def456"
    }
    
    # 4. New conversation (no context)
    POST /v1/answer
    {
        "question": "What is redemption?",
        "domain": "wealth_management"
    }
    """)
    
    print("\n📊 RESPONSE METADATA FIELDS")
    print("="*80)
    print("✓ response_id - Unique identifier for this response")
    print("✓ is_conversational - Boolean flag indicating conversational context")
    print("✓ previous_response_id - ID of the previous response (if provided)")
    print("✓ conversation_id - Conversation identifier (if provided)")
    print("✓ domain - Domain used for the query")
    print("✓ vectorstore_id - Vector store used")
    print("✓ model - AI model used")
    print("✓ mode - Answer mode (concise/balanced/deep)")

if __name__ == "__main__":
    demo_conversational_flow()

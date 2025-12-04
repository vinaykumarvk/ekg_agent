"""
Debug script to test structured input and show correct request format
"""
import requests
import json

BASE_URL = "https://ekg-service-47249889063.europe-west6.run.app"

# Example question_payload structure
question_payload = {
    "system_prompt": "You are an Internal Capabilities Analyst...",
    "requirement": "The platform should support comprehensive credit operations...",
    "bank_profile": {
        "bank_name": "Example Bank",
        "region": "APAC"
    },
    "market_subrequirements": [
        {
            "id": "M1",
            "title": "Drawdown Processing",
            "description": "The platform should enable users to request...",
            "priority": "must_have"
        }
    ]
}

def test_structured_input():
    """Test structured input with correct format"""
    
    # CORRECT REQUEST FORMAT
    payload = {
        "question_payload": question_payload,  # Note: wrapped in "question_payload" key
        "domain": "wealth_management",
        "vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8",  # Optional - will use domain default if not provided
        "params": {
            "_mode": "balanced",
            "model": "gpt-4o"  # Note: "gpt-5" doesn't exist, use "gpt-4o" or "gpt-4o-mini"
        },
        "output_format": "json"  # Optional - auto-set to "json" when question_payload is used
    }
    
    print("=" * 80)
    print("Testing Structured Input API")
    print("=" * 80)
    print(f"\nRequest URL: {BASE_URL}/v1/answer")
    print(f"\nRequest Payload Structure:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:500] + "...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/answer",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 422:
            print("\n" + "=" * 80)
            print("VALIDATION ERROR - Details:")
            print("=" * 80)
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(response.text)
        elif response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 80)
            print("SUCCESS!")
            print("=" * 80)
            print(f"Response ID: {result.get('response_id')}")
            if result.get('json_data'):
                print(f"JSON Data: {json.dumps(result['json_data'], indent=2)[:500]}...")
        else:
            print(f"\nError Response: {response.text}")
            
    except Exception as e:
        print(f"\nException: {str(e)}")
        import traceback
        traceback.print_exc()


def show_correct_format():
    """Show the correct request format"""
    print("\n" + "=" * 80)
    print("CORRECT REQUEST FORMAT")
    print("=" * 80)
    print("""
The API expects a JSON body with this structure:

{
  "question_payload": {
    "system_prompt": "...",
    "requirement": "...",
    "bank_profile": {...},
    "market_subrequirements": [...]
  },
  "domain": "wealth_management",
  "vectorstore_id": "optional-vector-store-id",
  "params": {
    "_mode": "balanced",
    "model": "gpt-4o"  # Use "gpt-4o", "gpt-4o-mini", etc. (not "gpt-5")
  },
  "output_format": "json"  # Optional - auto-set when question_payload is used
}

IMPORTANT:
1. question_payload must be a dict (not a string or list)
2. question_payload must contain at least: system_prompt, requirement
3. model should be a valid OpenAI model name (gpt-4o, gpt-4o-mini, etc.)
4. The entire request body should be JSON
""")


if __name__ == "__main__":
    show_correct_format()
    test_structured_input()


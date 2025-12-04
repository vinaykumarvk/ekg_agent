"""
Test script for the new /v1/answer-structured endpoint
"""
import requests
import json

BASE_URL = "https://ekg-service-47249889063.europe-west6.run.app"

# Example structured payload
FILE_SEARCH_SYSTEM_PROMPT = """
You are an Internal Capabilities Analyst.

INPUT
- You receive:
  - `requirement`: a single functional/business requirement.
  - `profile`: JSON describing the bank.
  - `market_subrequirements`: array from the Web Search agent (ids like M1, M2, ...).

- You can access internal documentation via the file_search tool (PRDs, solution docs, implementation notes, etc.).

TASK
- For EACH market subrequirement:
  1) Use file_search with a focused query based on:
     - the subrequirement's title, description, and priority
     - the overall requirement
     - the bank_profile where relevant.
  2) From the retrieved documents, infer what the platform supports today that is relevant
     to this subrequirement.
  3) Summarise the capabilities clearly and concisely.

OUTPUT (JSON ONLY, NO PROSE, NO MARKDOWN)

Return a single JSON object with this shape:

{
  "internal_capabilities": [
    {
      "market_id": "M1",
      "coverage_hint": "full" | "partial" | "unknown",
      "capabilities": [
        {
          "id": "I1",
          "title": "Short name of the existing capability",
          "description": "2–4 sentences describing what is supported today relative to this subrequirement",
          "status": "live" | "configurable" | "roadmap" | "not_supported",
          "modules": ["Module / subsystem names if identifiable"],
          "evidence": [
            {
              "source_id": "doc-or-section-identifier-if-available",
              "note": "Very short snippet or pointer, max 1–2 sentences"
            }
          ]
        }
      ]
    },
    ...
  ]
}

RULES
- Iterate over ALL provided market_subrequirements, even if some have weaker support.
- Base your answer only on internal documentation retrieved via file_search.
- If you find no relevant evidence for a market subrequirement:
  - Still include an entry for that market_id.
  - Set "coverage_hint": "unknown" and "capabilities": [].
- Do NOT include any text outside the JSON object.
- Do NOT invent capabilities that are not grounded in retrieved documents.
"""

def test_new_endpoint():
    """Test the new /v1/answer-structured endpoint"""
    
    payload = {
        "question_payload": {
            "system_prompt": FILE_SEARCH_SYSTEM_PROMPT,
            "requirement": "The platform should support comprehensive credit and lending operations including drawdowns, disbursements, repayments, and compliance tracking.",
            "bank_profile": {
                "bank_name": "Example Bank",
                "region": "APAC",
                "regulatory_framework": "Basel III",
                "core_system": "Custom Platform"
            },
            "market_subrequirements": [
                {
                    "id": "M1",
                    "title": "Drawdown Processing",
                    "description": "The platform should enable users to request, process, and track drawdowns from available credit or investment lines, with automation for approvals, limits, and compliance checks.",
                    "priority": "must_have"
                },
                {
                    "id": "M2",
                    "title": "Disbursement Management",
                    "description": "The system should facilitate disbursement of funds to clients or third-parties, including support for multiple payment methods, automated scheduling, and settlement tracking.",
                    "priority": "must_have"
                }
            ]
        },
        "domain": "wealth_management",
        "vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8",
        "params": {
            "_mode": "balanced",
            "model": "gpt-4o"
        }
    }
    
    print("=" * 80)
    print("Testing NEW /v1/answer-structured Endpoint")
    print("=" * 80)
    print(f"\nRequest URL: {BASE_URL}/v1/answer-structured")
    print(f"\nRequest Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False)[:800] + "...")
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/answer-structured",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 80)
            print("SUCCESS!")
            print("=" * 80)
            print(f"Response ID: {result.get('response_id')}")
            
            if result.get('json_data'):
                print("\n" + "-" * 80)
                print("JSON Response:")
                print("-" * 80)
                print(json.dumps(result['json_data'], indent=2, ensure_ascii=False)[:1000] + "...")
            elif result.get('answer'):
                print("\n" + "-" * 80)
                print("Answer Text (JSON parsing may have failed):")
                print("-" * 80)
                print(result['answer'][:500])
            
            if result.get('meta'):
                print("\n" + "-" * 80)
                print("Metadata:")
                print("-" * 80)
                print(json.dumps(result['meta'], indent=2))
        else:
            print("\n" + "=" * 80)
            print("ERROR")
            print("=" * 80)
            print(f"Status Code: {response.status_code}")
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2, ensure_ascii=False))
            except:
                print(response.text)
                
    except Exception as e:
        print(f"\nException: {str(e)}")
        import traceback
        traceback.print_exc()


def show_endpoint_info():
    """Show information about the new endpoint"""
    print("\n" + "=" * 80)
    print("NEW ENDPOINT: /v1/answer-structured")
    print("=" * 80)
    print("""
This is a dedicated endpoint for structured input with custom system prompts.

Endpoint: POST /v1/answer-structured

Request Body:
{
  "question_payload": {
    "system_prompt": "Your custom system prompt...",
    "requirement": "Requirement description",
    "bank_profile": {
      "bank_name": "...",
      "region": "..."
    },
    "market_subrequirements": [
      {
        "id": "M1",
        "title": "...",
        "description": "...",
        "priority": "must_have"
      }
    ]
  },
  "domain": "wealth_management",
  "vectorstore_id": "optional",
  "params": {
    "_mode": "balanced",
    "model": "gpt-4o"
  }
}

Response:
{
  "response_id": "uuid",
  "json_data": {...},  // Parsed JSON if available
  "answer": "...",      // Raw answer if JSON parsing failed
  "sources": [...],
  "meta": {...}
}

Benefits:
- Clean separation from simple question endpoint
- No validation conflicts
- Dedicated schema for structured input
- Better error messages
""")


if __name__ == "__main__":
    show_endpoint_info()
    test_new_endpoint()


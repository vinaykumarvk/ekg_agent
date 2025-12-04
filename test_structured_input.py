"""
Test script for structured input functionality
"""
import requests
import json

# Base URL
BASE_URL = "http://localhost:8000"

# System prompt
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

# Example data
requirement = "The platform should support comprehensive credit and lending operations including drawdowns, disbursements, repayments, and compliance tracking."

profile = {
    "bank_name": "Example Bank",
    "region": "APAC",
    "regulatory_framework": "Basel III",
    "core_system": "Custom Platform"
}

market_subrequirements = [
    {
        'id': 'M1',
        'title': 'Drawdown Processing',
        'description': 'The platform should enable users to request, process, and track drawdowns from available credit or investment lines, with automation for approvals, limits, and compliance checks.',
        'priority': 'must_have'
    },
    {
        'id': 'M2',
        'title': 'Disbursement Management',
        'description': 'The system should facilitate disbursement of funds to clients or third-parties, including support for multiple payment methods, automated scheduling, and settlement tracking.',
        'priority': 'must_have'
    },
    {
        'id': 'M3',
        'title': 'Purpose Verification',
        'description': 'Mandatory verification and documentation of the intended use or purpose for funds requested or disbursed, including workflows for evidentiary uploads and compliance review.',
        'priority': 'must_have'
    },
    {
        'id': 'M4',
        'title': 'General Ledger (GL) Integration',
        'description': 'Automatic posting of all relevant transactions to an integrated GL, with real-time account mapping, reconciliation support, and detailed audit trails for regulatory compliance.',
        'priority': 'must_have'
    },
    {
        'id': 'M5',
        'title': 'Dynamic Repayment Allocation',
        'description': 'Configurable rules for allocation of repayments across principal, interest, and fees, supporting partial, overpayments, and priority sequencing as per client agreements.',
        'priority': 'must_have'
    },
    {
        'id': 'M6',
        'title': 'Arrears and Delinquency Management',
        'description': 'Automated monitoring, identification, and reporting of overdue payments, including workflows for communication, dunning, and regulatory notification.',
        'priority': 'must_have'
    },
    {
        'id': 'M7',
        'title': 'Penalty and Fee Assessment',
        'description': 'Automated calculation, application, and reversal of penalties and fees based on configurable business rules, grace periods, and client profiles.',
        'priority': 'must_have'
    }
]

def test_structured_input():
    """Test the structured input endpoint"""
    
    # Build the question payload
    question_payload = {
        "system_prompt": FILE_SEARCH_SYSTEM_PROMPT,
        "requirement": requirement,
        "bank_profile": profile,
        "market_subrequirements": market_subrequirements,
    }
    
    # Build the request
    request_data = {
        "question_payload": question_payload,
        "domain": "wealth_management",  # Adjust as needed
        "output_format": "json"
    }
    
    print("=" * 80)
    print("Testing Structured Input Endpoint")
    print("=" * 80)
    print(f"\nRequest URL: {BASE_URL}/v1/answer")
    print(f"Domain: {request_data['domain']}")
    print(f"Output Format: {request_data['output_format']}")
    print(f"\nRequirement: {requirement[:100]}...")
    print(f"Market Subrequirements: {len(market_subrequirements)} items")
    print(f"Bank Profile: {profile['bank_name']}")
    
    try:
        # Make the request
        response = requests.post(
            f"{BASE_URL}/v1/answer",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minutes timeout
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n" + "=" * 80)
            print("SUCCESS - Response Received")
            print("=" * 80)
            
            print(f"\nResponse ID: {result.get('response_id')}")
            print(f"\nJSON Data Present: {result.get('json_data') is not None}")
            print(f"Markdown Present: {result.get('markdown') is not None}")
            
            if result.get('json_data'):
                print("\n" + "-" * 80)
                print("JSON Response:")
                print("-" * 80)
                print(json.dumps(result['json_data'], indent=2, ensure_ascii=False))
            elif result.get('markdown'):
                print("\n" + "-" * 80)
                print("Markdown Response (first 500 chars):")
                print("-" * 80)
                print(result['markdown'][:500])
            
            if result.get('meta'):
                print("\n" + "-" * 80)
                print("Metadata:")
                print("-" * 80)
                print(json.dumps(result['meta'], indent=2))
            
            if result.get('sources'):
                print(f"\nSources: {len(result['sources'])} items")
        else:
            print("\n" + "=" * 80)
            print("ERROR - Request Failed")
            print("=" * 80)
            print(f"Status Code: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print("\n" + "=" * 80)
        print("ERROR - Request Exception")
        print("=" * 80)
        print(f"Error: {str(e)}")
        print("\nMake sure the server is running:")
        print("  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload")
    except Exception as e:
        print("\n" + "=" * 80)
        print("ERROR - Unexpected Exception")
        print("=" * 80)
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()


def test_backward_compatibility():
    """Test that regular string questions still work"""
    
    print("\n" + "=" * 80)
    print("Testing Backward Compatibility (String Question)")
    print("=" * 80)
    
    request_data = {
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/v1/answer",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        
        print(f"\nResponse Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✓ Backward compatibility test PASSED")
            print(f"Response ID: {result.get('response_id')}")
            print(f"Markdown length: {len(result.get('markdown', ''))}")
        else:
            print(f"✗ Backward compatibility test FAILED: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"✗ Backward compatibility test FAILED: {str(e)}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("EKG Agent - Structured Input Test")
    print("=" * 80)
    
    # Test backward compatibility first
    test_backward_compatibility()
    
    # Test structured input
    test_structured_input()
    
    print("\n" + "=" * 80)
    print("Test Complete")
    print("=" * 80)


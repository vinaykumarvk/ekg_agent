"""
Test script for the /req_desc_web_search endpoint
"""
import requests
import json

BASE_URL = "https://ekg-service-47249889063.europe-west6.run.app"

def test_web_search_endpoint():
    """Test the /req_desc_web_search endpoint"""
    
    payload = {
        "requirement": "The platform should support comprehensive credit and lending operations including drawdowns, disbursements, repayments, and compliance tracking.",
        "profile": {
            "bank_name": "Example Bank",
            "region": "APAC",
            "regulatory_framework": "Basel III",
            "core_system": "Custom Platform",
            "customer_segment": "Retail and Corporate"
        },
        "model": "gpt-4o"
    }
    
    print("=" * 80)
    print("Testing /req_desc_web_search Endpoint")
    print("=" * 80)
    print(f"\nRequest URL: {BASE_URL}/req_desc_web_search")
    print(f"\nRequirement: {payload['requirement'][:100]}...")
    print(f"Model: {payload['model']}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/req_desc_web_search",
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
                print("Market Subrequirements (JSON):")
                print("-" * 80)
                market_subreqs = result['json_data'].get('market_subrequirements', [])
                print(f"Found {len(market_subreqs)} subrequirements:")
                for subreq in market_subreqs:
                    print(f"\n  {subreq.get('id')}: {subreq.get('title')}")
                    print(f"    Priority: {subreq.get('priority')}")
                    print(f"    Description: {subreq.get('description', '')[:150]}...")
                
                print("\n" + "-" * 80)
                print("Full JSON Response:")
                print("-" * 80)
                print(json.dumps(result['json_data'], indent=2, ensure_ascii=False))
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
            
            if result.get('sources'):
                print(f"\nSources: {len(result['sources'])} documents retrieved")
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
    """Show information about the endpoint"""
    print("\n" + "=" * 80)
    print("ENDPOINT: /req_desc_web_search")
    print("=" * 80)
    print("""
This endpoint decomposes requirements into market subrequirements using web search.

Endpoint: POST /req_desc_web_search

Request Body:
{
  "requirement": "Requirement description to decompose",
  "profile": {
    "bank_name": "...",
    "region": "...",
    "regulatory_framework": "...",
    "customer_segment": "..."
  },
  "model": "gpt-4o"
}

Response:
{
  "response_id": "uuid",
  "json_data": {
    "market_subrequirements": [
      {
        "id": "M1",
        "title": "Subrequirement title",
        "description": "Description",
        "priority": "must_have" | "nice_to_have"
      }
    ]
  },
  "answer": "...",  // Raw answer if JSON parsing failed
  "sources": [...],
  "meta": {...}
}

Features:
- Decomposes requirements into 3-10 non-overlapping subrequirements
- Uses web search (file_search tool) to research market standards
- Returns structured JSON with priorities
- Vendor-agnostic capability statements
- No vectorstore_id needed - uses web search directly
""")


if __name__ == "__main__":
    show_endpoint_info()
    test_web_search_endpoint()


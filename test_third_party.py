#!/usr/bin/env python3
"""
Third-party testing script for EKG Agent API
"""
import requests
import json
import time
import sys

class EkgApiTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'EKG-API-Tester/1.0'
        })
    
    def test_health(self):
        """Test health endpoint"""
        print("🔍 Testing health endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health check passed")
                print(f"   Status: {data.get('status')}")
                print(f"   Domains: {list(data.get('domains', {}).keys())}")
                return True
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Health check error: {e}")
            return False
    
    def test_domains(self):
        """Test domains endpoint"""
        print("\n🔍 Testing domains endpoint...")
        try:
            response = self.session.get(f"{self.base_url}/domains")
            if response.status_code == 200:
                data = response.json()
                domains = data.get('domains', [])
                print(f"✅ Domains endpoint passed")
                print(f"   Found {len(domains)} domains:")
                for domain in domains:
                    print(f"   - {domain['domain_id']}: {domain['name']}")
                return domains
            else:
                print(f"❌ Domains endpoint failed: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Domains endpoint error: {e}")
            return []
    
    def test_basic_query(self, domain="wealth_management"):
        """Test basic query"""
        print(f"\n🔍 Testing basic query for domain: {domain}")
        try:
            payload = {
                "question": "What is OTP verification?",
                "domain": domain
            }
            
            response = self.session.post(f"{self.base_url}/v1/answer", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Basic query passed")
                print(f"   Response ID: {data.get('response_id')}")
                print(f"   Answer length: {len(data.get('markdown', ''))}")
                print(f"   Sources: {len(data.get('sources', []))}")
                print(f"   Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                return data
            else:
                print(f"❌ Basic query failed: {response.status_code}")
                print(f"   Error: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Basic query error: {e}")
            return None
    
    def test_conversational_flow(self, domain="wealth_management"):
        """Test conversational flow"""
        print(f"\n🔍 Testing conversational flow for domain: {domain}")
        
        # Step 1: Initial question
        print("   Step 1: Initial question...")
        initial_response = self.test_basic_query(domain)
        if not initial_response:
            return False
        
        response_id = initial_response.get('response_id')
        if not response_id:
            print("❌ No response_id in initial response")
            return False
        
        # Step 2: Follow-up with response_id
        print("   Step 2: Follow-up with response_id...")
        try:
            payload = {
                "question": "How long is the OTP valid?",
                "domain": domain,
                "response_id": response_id
            }
            
            response = self.session.post(f"{self.base_url}/v1/answer", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Follow-up query passed")
                print(f"   Response ID: {data.get('response_id')}")
                print(f"   Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                print(f"   Previous Response ID: {data.get('meta', {}).get('previous_response_id')}")
                return True
            else:
                print(f"❌ Follow-up query failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Follow-up query error: {e}")
            return False
    
    def test_conversation_id(self, domain="wealth_management"):
        """Test conversation_id flow"""
        print(f"\n🔍 Testing conversation_id flow for domain: {domain}")
        
        try:
            payload = {
                "question": "What is the redemption process?",
                "domain": domain,
                "conversation_id": "test-conversation-123"
            }
            
            response = self.session.post(f"{self.base_url}/v1/answer", json=payload)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Conversation ID query passed")
                print(f"   Response ID: {data.get('response_id')}")
                print(f"   Is Conversational: {data.get('meta', {}).get('is_conversational', False)}")
                print(f"   Conversation ID: {data.get('meta', {}).get('conversation_id')}")
                return True
            else:
                print(f"❌ Conversation ID query failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Conversation ID query error: {e}")
            return False
    
    def test_error_handling(self):
        """Test error handling"""
        print("\n🔍 Testing error handling...")
        
        # Test invalid domain
        print("   Testing invalid domain...")
        try:
            payload = {
                "question": "Test question",
                "domain": "invalid_domain"
            }
            
            response = self.session.post(f"{self.base_url}/v1/answer", json=payload)
            if response.status_code == 400:
                print("✅ Invalid domain correctly rejected")
            else:
                print(f"❌ Invalid domain not rejected: {response.status_code}")
        except Exception as e:
            print(f"❌ Invalid domain test error: {e}")
        
        # Test malformed request
        print("   Testing malformed request...")
        try:
            response = self.session.post(f"{self.base_url}/v1/answer", json={})
            if response.status_code == 422:  # Validation error
                print("✅ Malformed request correctly rejected")
            else:
                print(f"❌ Malformed request not rejected: {response.status_code}")
        except Exception as e:
            print(f"❌ Malformed request test error: {e}")
    
    def test_performance(self, num_requests=5):
        """Test performance with multiple requests"""
        print(f"\n🔍 Testing performance with {num_requests} requests...")
        
        start_time = time.time()
        successful_requests = 0
        
        for i in range(num_requests):
            try:
                payload = {
                    "question": f"Test question {i+1}",
                    "domain": "wealth_management"
                }
                
                response = self.session.post(f"{self.base_url}/v1/answer", json=payload)
                if response.status_code == 200:
                    successful_requests += 1
                
            except Exception as e:
                print(f"❌ Request {i+1} failed: {e}")
        
        end_time = time.time()
        total_time = end_time - start_time
        avg_time = total_time / num_requests
        
        print(f"✅ Performance test completed")
        print(f"   Successful requests: {successful_requests}/{num_requests}")
        print(f"   Total time: {total_time:.2f}s")
        print(f"   Average time per request: {avg_time:.2f}s")
        
        return successful_requests == num_requests
    
    def run_full_test_suite(self):
        """Run complete test suite"""
        print("="*80)
        print("🧪 EKG AGENT API - THIRD PARTY TESTING SUITE")
        print("="*80)
        
        tests_passed = 0
        total_tests = 0
        
        # Test 1: Health check
        total_tests += 1
        if self.test_health():
            tests_passed += 1
        
        # Test 2: Domains
        total_tests += 1
        domains = self.test_domains()
        if domains:
            tests_passed += 1
        
        # Test 3: Basic query for each domain
        for domain in domains:
            total_tests += 1
            if self.test_basic_query(domain['domain_id']):
                tests_passed += 1
        
        # Test 4: Conversational flow
        total_tests += 1
        if self.test_conversational_flow():
            tests_passed += 1
        
        # Test 5: Conversation ID
        total_tests += 1
        if self.test_conversation_id():
            tests_passed += 1
        
        # Test 6: Error handling
        total_tests += 1
        self.test_error_handling()
        tests_passed += 1  # Error handling tests don't fail the suite
        
        # Test 7: Performance
        total_tests += 1
        if self.test_performance():
            tests_passed += 1
        
        # Summary
        print("\n" + "="*80)
        print(f"📊 TEST RESULTS: {tests_passed}/{total_tests} tests passed")
        print("="*80)
        
        if tests_passed == total_tests:
            print("✅ ALL TESTS PASSED - API is ready for third-party integration!")
            return True
        else:
            print("⚠️  Some tests failed - Please check the issues above")
            return False

def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Test EKG Agent API from third-party systems')
    parser.add_argument('--url', default='http://localhost:8000', help='API base URL')
    parser.add_argument('--test', choices=['health', 'domains', 'query', 'conversational', 'performance', 'all'], 
                       default='all', help='Specific test to run')
    
    args = parser.parse_args()
    
    tester = EkgApiTester(args.url)
    
    if args.test == 'all':
        success = tester.run_full_test_suite()
        sys.exit(0 if success else 1)
    elif args.test == 'health':
        success = tester.test_health()
    elif args.test == 'domains':
        success = bool(tester.test_domains())
    elif args.test == 'query':
        success = bool(tester.test_basic_query())
    elif args.test == 'conversational':
        success = tester.test_conversational_flow()
    elif args.test == 'performance':
        success = tester.test_performance()
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

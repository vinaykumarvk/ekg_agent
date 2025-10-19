#!/usr/bin/env node
/**
 * JavaScript/Node.js testing example for EKG Agent API
 */

const axios = require('axios');

class EkgApiClient {
    constructor(baseUrl = 'http://localhost:8000') {
        this.baseUrl = baseUrl;
        this.client = axios.create({
            baseURL: baseUrl,
            timeout: 30000,
            headers: {
                'Content-Type': 'application/json',
                'User-Agent': 'EKG-API-Client/1.0'
            }
        });
    }

    async testHealth() {
        console.log('🔍 Testing health endpoint...');
        try {
            const response = await this.client.get('/health');
            console.log('✅ Health check passed');
            console.log(`   Status: ${response.data.status}`);
            console.log(`   Domains: ${Object.keys(response.data.domains || {})}`);
            return true;
        } catch (error) {
            console.log('❌ Health check failed:', error.message);
            return false;
        }
    }

    async testDomains() {
        console.log('\n🔍 Testing domains endpoint...');
        try {
            const response = await this.client.get('/domains');
            console.log('✅ Domains endpoint passed');
            console.log(`   Found ${response.data.domains.length} domains:`);
            response.data.domains.forEach(domain => {
                console.log(`   - ${domain.domain_id}: ${domain.name}`);
            });
            return response.data.domains;
        } catch (error) {
            console.log('❌ Domains endpoint failed:', error.message);
            return [];
        }
    }

    async testBasicQuery(domain = 'wealth_management') {
        console.log(`\n🔍 Testing basic query for domain: ${domain}`);
        try {
            const response = await this.client.post('/v1/answer', {
                question: 'What is OTP verification?',
                domain: domain
            });
            
            console.log('✅ Basic query passed');
            console.log(`   Response ID: ${response.data.response_id}`);
            console.log(`   Answer length: ${response.data.markdown.length}`);
            console.log(`   Sources: ${response.data.sources?.length || 0}`);
            console.log(`   Is Conversational: ${response.data.meta?.is_conversational || false}`);
            return response.data;
        } catch (error) {
            console.log('❌ Basic query failed:', error.response?.data || error.message);
            return null;
        }
    }

    async testConversationalFlow(domain = 'wealth_management') {
        console.log(`\n🔍 Testing conversational flow for domain: ${domain}`);
        
        // Step 1: Initial question
        console.log('   Step 1: Initial question...');
        const initialResponse = await this.testBasicQuery(domain);
        if (!initialResponse) return false;

        // Step 2: Follow-up with response_id
        console.log('   Step 2: Follow-up with response_id...');
        try {
            const response = await this.client.post('/v1/answer', {
                question: 'How long is the OTP valid?',
                domain: domain,
                response_id: initialResponse.response_id
            });
            
            console.log('✅ Follow-up query passed');
            console.log(`   Response ID: ${response.data.response_id}`);
            console.log(`   Is Conversational: ${response.data.meta?.is_conversational || false}`);
            console.log(`   Previous Response ID: ${response.data.meta?.previous_response_id}`);
            return true;
        } catch (error) {
            console.log('❌ Follow-up query failed:', error.response?.data || error.message);
            return false;
        }
    }

    async testConversationId(domain = 'wealth_management') {
        console.log(`\n🔍 Testing conversation_id flow for domain: ${domain}`);
        try {
            const response = await this.client.post('/v1/answer', {
                question: 'What is the redemption process?',
                domain: domain,
                conversation_id: 'test-conversation-123'
            });
            
            console.log('✅ Conversation ID query passed');
            console.log(`   Response ID: ${response.data.response_id}`);
            console.log(`   Is Conversational: ${response.data.meta?.is_conversational || false}`);
            console.log(`   Conversation ID: ${response.data.meta?.conversation_id}`);
            return true;
        } catch (error) {
            console.log('❌ Conversation ID query failed:', error.response?.data || error.message);
            return false;
        }
    }

    async testPerformance(numRequests = 5) {
        console.log(`\n🔍 Testing performance with ${numRequests} requests...`);
        
        const startTime = Date.now();
        let successfulRequests = 0;
        
        for (let i = 0; i < numRequests; i++) {
            try {
                const response = await this.client.post('/v1/answer', {
                    question: `Test question ${i + 1}`,
                    domain: 'wealth_management'
                });
                if (response.status === 200) {
                    successfulRequests++;
                }
            } catch (error) {
                console.log(`❌ Request ${i + 1} failed: ${error.message}`);
            }
        }
        
        const endTime = Date.now();
        const totalTime = (endTime - startTime) / 1000;
        const avgTime = totalTime / numRequests;
        
        console.log('✅ Performance test completed');
        console.log(`   Successful requests: ${successfulRequests}/${numRequests}`);
        console.log(`   Total time: ${totalTime.toFixed(2)}s`);
        console.log(`   Average time per request: ${avgTime.toFixed(2)}s`);
        
        return successfulRequests === numRequests;
    }

    async runFullTestSuite() {
        console.log('='.repeat(80));
        console.log('🧪 EKG AGENT API - JAVASCRIPT TESTING SUITE');
        console.log('='.repeat(80));
        
        let testsPassed = 0;
        let totalTests = 0;
        
        // Test 1: Health check
        totalTests++;
        if (await this.testHealth()) testsPassed++;
        
        // Test 2: Domains
        totalTests++;
        const domains = await this.testDomains();
        if (domains.length > 0) testsPassed++;
        
        // Test 3: Basic query for each domain
        for (const domain of domains) {
            totalTests++;
            if (await this.testBasicQuery(domain.domain_id)) testsPassed++;
        }
        
        // Test 4: Conversational flow
        totalTests++;
        if (await this.testConversationalFlow()) testsPassed++;
        
        // Test 5: Conversation ID
        totalTests++;
        if (await this.testConversationId()) testsPassed++;
        
        // Test 6: Performance
        totalTests++;
        if (await this.testPerformance()) testsPassed++;
        
        // Summary
        console.log('\n' + '='.repeat(80));
        console.log(`📊 TEST RESULTS: ${testsPassed}/${totalTests} tests passed`);
        console.log('='.repeat(80));
        
        if (testsPassed === totalTests) {
            console.log('✅ ALL TESTS PASSED - API is ready for third-party integration!');
            return true;
        } else {
            console.log('⚠️  Some tests failed - Please check the issues above');
            return false;
        }
    }
}

// Usage examples
async function main() {
    const client = new EkgApiClient();
    
    // Run full test suite
    await client.runFullTestSuite();
    
    // Example: Single query
    console.log('\n📝 Example: Single query');
    const result = await client.testBasicQuery('wealth_management');
    if (result) {
        console.log('Query successful!');
        console.log(`Response ID: ${result.response_id}`);
    }
}

// Run if called directly
if (require.main === module) {
    main().catch(console.error);
}

module.exports = EkgApiClient;

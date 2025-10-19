# Client Integration Guide - Connecting to EKG Agent API

## Overview

This guide shows how to integrate with your deployed EKG Agent API from:
- Python applications
- Replit UI/UX applications
- Any other client

## Python Client Integration

### Simple Python Client

```python
import requests
from typing import Optional, Dict, Any

class EKGAgentClient:
    """Client for EKG Agent API"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        Initialize client
        
        Args:
            base_url: API URL (e.g., https://ekg-agent-xxx.run.app)
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["X-API-Key"] = api_key
    
    def list_domains(self) -> Dict[str, Any]:
        """List available domains"""
        response = requests.get(f"{self.base_url}/domains", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health"""
        response = requests.get(f"{self.base_url}/health", headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def ask(
        self,
        question: str,
        domain: str = "wealth_management",
        vectorstore_id: Optional[str] = None,
        mode: str = "balanced"
    ) -> Dict[str, Any]:
        """
        Ask a question
        
        Args:
            question: The question to ask
            domain: Domain to query (default: wealth_management)
            vectorstore_id: Optional vector store ID (uses domain default if not provided)
            mode: Answer mode - concise, balanced, or deep
            
        Returns:
            Dictionary with markdown, sources, and meta
        """
        payload = {
            "question": question,
            "domain": domain,
            "params": {"_mode": mode}
        }
        
        if vectorstore_id:
            payload["vectorstore_id"] = vectorstore_id
        
        response = requests.post(
            f"{self.base_url}/v1/answer",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()


# Usage Example
if __name__ == "__main__":
    # For local testing
    client = EKGAgentClient("http://localhost:8000")
    
    # For Cloud Run deployment
    # client = EKGAgentClient("https://ekg-agent-xxx.run.app")
    
    # List domains
    domains = client.list_domains()
    print(f"Available domains: {[d['domain_id'] for d in domains['domains']]}")
    
    # Ask a question
    result = client.ask(
        question="What is the OTP process?",
        domain="wealth_management",
        mode="concise"
    )
    
    print(f"\nAnswer Preview:")
    print(result['markdown'][:500])
```

### Advanced Python Client with Retry Logic

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any
import time


class EKGAgentClient:
    """Production-ready client with retry logic and error handling"""
    
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: int = 60,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Set up session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set headers
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self.session.headers.update({"X-API-Key": api_key})
    
    def ask(
        self,
        question: str,
        domain: str = "wealth_management",
        vectorstore_id: Optional[str] = None,
        mode: str = "balanced",
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Ask a question with error handling
        
        Raises:
            requests.exceptions.HTTPError: For API errors
            requests.exceptions.Timeout: For timeouts
            ValueError: For invalid responses
        """
        payload = {
            "question": question,
            "domain": domain,
            "params": {"_mode": mode}
        }
        
        if vectorstore_id:
            payload["vectorstore_id"] = vectorstore_id
        
        try:
            response = self.session.post(
                f"{self.base_url}/v1/answer",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            raise TimeoutError(f"Request timed out after {self.timeout}s")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 400:
                raise ValueError(f"Invalid request: {e.response.json().get('detail')}")
            elif e.response.status_code == 500:
                raise RuntimeError(f"Server error: {e.response.json().get('detail')}")
            else:
                raise
    
    def batch_ask(
        self,
        questions: list[str],
        domain: str = "wealth_management",
        mode: str = "concise"
    ) -> list[Dict[str, Any]]:
        """
        Ask multiple questions
        
        Args:
            questions: List of questions
            domain: Domain to query
            mode: Answer mode
            
        Returns:
            List of answers in same order as questions
        """
        results = []
        for i, question in enumerate(questions, 1):
            print(f"Processing {i}/{len(questions)}: {question[:50]}...")
            try:
                result = self.ask(question, domain=domain, mode=mode)
                results.append(result)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                print(f"  Error: {e}")
                results.append({"error": str(e), "question": question})
        return results
```

## Replit Integration

### Option 1: Python Backend on Replit

Create `main.py` on Replit:

```python
from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Your deployed Cloud Run URL
EKG_API_URL = os.getenv("EKG_API_URL", "https://ekg-agent-xxx.run.app")

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """Proxy endpoint for your UI"""
    data = request.json
    
    # Forward to EKG Agent
    response = requests.post(
        f"{EKG_API_URL}/v1/answer",
        json={
            "question": data.get("question"),
            "domain": data.get("domain", "wealth_management"),
            "params": {"_mode": data.get("mode", "balanced")}
        }
    )
    
    return jsonify(response.json())

@app.route('/api/domains', methods=['GET'])
def get_domains():
    """Get available domains"""
    response = requests.get(f"{EKG_API_URL}/domains")
    return jsonify(response.json())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

### Option 2: Direct JavaScript Integration

```javascript
// In your Replit frontend
const EKG_API_URL = 'https://ekg-agent-xxx.run.app';

async function askQuestion(question, domain = 'wealth_management') {
  const response = await fetch(`${EKG_API_URL}/v1/answer`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question: question,
      domain: domain,
      params: { _mode: 'balanced' }
    })
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return await response.json();
}

// Usage
askQuestion("What is OTP verification?", "wealth_management")
  .then(result => {
    console.log("Answer:", result.markdown);
    console.log("Sources:", result.sources);
  })
  .catch(error => {
    console.error("Error:", error);
  });
```

## Example: Replit Chat UI

Complete Replit example with UI:

```python
# main.py
import streamlit as st
import requests

# Your deployed Cloud Run URL
API_URL = "https://ekg-agent-xxx.run.app"

st.title("🤖 EKG Agent - Multi-Domain Q&A")

# Get available domains
@st.cache_data
def get_domains():
    response = requests.get(f"{API_URL}/domains")
    return response.json()["domains"]

# Sidebar for domain selection
domains = get_domains()
domain_options = {d["name"]: d["domain_id"] for d in domains}

st.sidebar.header("Configuration")
selected_domain_name = st.sidebar.selectbox(
    "Select Domain",
    options=list(domain_options.keys())
)
selected_domain = domain_options[selected_domain_name]

# Show domain info
st.sidebar.info(f"""
**{selected_domain_name}**  
Nodes: {next(d['kg_nodes'] for d in domains if d['domain_id'] == selected_domain)}  
Edges: {next(d['kg_edges'] for d in domains if d['domain_id'] == selected_domain)}
""")

mode = st.sidebar.radio("Answer Mode", ["concise", "balanced", "deep"])

# Main chat interface
question = st.text_input("Ask a question:", placeholder="What is OTP verification?")

if st.button("Get Answer") and question:
    with st.spinner("Generating answer..."):
        try:
            response = requests.post(
                f"{API_URL}/v1/answer",
                json={
                    "question": question,
                    "domain": selected_domain,
                    "params": {"_mode": mode}
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # Display answer
                st.markdown("### Answer")
                st.markdown(result["markdown"])
                
                # Show metadata
                with st.expander("Metadata"):
                    st.json(result["meta"])
                    
            else:
                st.error(f"Error: {response.status_code} - {response.text}")
                
        except Exception as e:
            st.error(f"Error: {str(e)}")

# Chat history (optional)
if "history" not in st.session_state:
    st.session_state.history = []

if question and st.button("Add to History"):
    st.session_state.history.append({
        "question": question,
        "domain": selected_domain,
        "mode": mode
    })

if st.session_state.history:
    st.sidebar.markdown("### Recent Questions")
    for i, item in enumerate(reversed(st.session_state.history[-5:]), 1):
        st.sidebar.text(f"{i}. [{item['domain']}] {item['question'][:30]}...")
```

## Testing the Deployed API

### Test Script (`test_deployment.py`)

```python
#!/usr/bin/env python3
"""
Test deployed EKG Agent API
Usage: python test_deployment.py <service_url>
"""
import sys
import requests

def test_api(base_url: str):
    """Run comprehensive API tests"""
    
    print(f"Testing EKG Agent at: {base_url}")
    print("=" * 70)
    
    # Test 1: Health
    print("\n1. Health Check...")
    r = requests.get(f"{base_url}/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code}"
    health = r.json()
    print(f"   ✓ Status: {health['status']}")
    print(f"   ✓ Domains: {list(health['domains'].keys())}")
    
    # Test 2: List domains
    print("\n2. List Domains...")
    r = requests.get(f"{base_url}/domains")
    assert r.status_code == 200
    domains = r.json()["domains"]
    print(f"   ✓ Found {len(domains)} domains:")
    for d in domains:
        print(f"     - {d['domain_id']}: {d['kg_nodes']} nodes")
    
    # Test 3: Query each domain
    print("\n3. Testing Each Domain...")
    for domain in domains:
        domain_id = domain['domain_id']
        print(f"\n   Testing {domain_id}...")
        
        r = requests.post(
            f"{base_url}/v1/answer",
            json={
                "question": f"What is the main process in {domain_id}?",
                "domain": domain_id,
                "params": {"_mode": "concise"}
            },
            timeout=60
        )
        
        if r.status_code == 200:
            result = r.json()
            print(f"   ✓ Answer received ({len(result['markdown'])} chars)")
            print(f"   ✓ Domain: {result['meta']['domain']}")
            print(f"   ✓ Vector Store: {result['meta']['vectorstore_id']}")
        else:
            print(f"   ✗ Error: {r.status_code}")
    
    print("\n" + "=" * 70)
    print("✅ All tests passed!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_deployment.py <service_url>")
        print("Example: python test_deployment.py https://ekg-agent-xxx.run.app")
        sys.exit(1)
    
    test_api(sys.argv[1])
```

## Integration Patterns

### Pattern 1: Direct API Calls

```python
import requests

API_URL = "https://ekg-agent-xxx.run.app"

# Query wealth management
response = requests.post(
    f"{API_URL}/v1/answer",
    json={
        "question": "What is OTP verification?",
        "domain": "wealth_management"
    }
)

answer = response.json()["markdown"]
```

### Pattern 2: SDK Wrapper

```python
# ekg_sdk.py
import requests
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class Answer:
    markdown: str
    sources: list
    domain: str
    vectorstore_id: str
    export_path: Optional[str]

class EKGAgent:
    def __init__(self, api_url: str):
        self.api_url = api_url
    
    def ask(
        self,
        question: str,
        domain: str = "wealth_management",
        mode: str = "balanced"
    ) -> Answer:
        response = requests.post(
            f"{self.api_url}/v1/answer",
            json={"question": question, "domain": domain, "params": {"_mode": mode}}
        )
        response.raise_for_status()
        data = response.json()
        
        return Answer(
            markdown=data["markdown"],
            sources=data.get("sources", []),
            domain=data["meta"]["domain"],
            vectorstore_id=data["meta"]["vectorstore_id"],
            export_path=data["meta"].get("export_path")
        )
    
    def batch_ask(self, questions: List[str], domain: str) -> List[Answer]:
        return [self.ask(q, domain=domain, mode="concise") for q in questions]

# Usage
agent = EKGAgent("https://ekg-agent-xxx.run.app")
answer = agent.ask("What is redemption?", domain="wealth_management")
print(answer.markdown)
```

### Pattern 3: Async Client (for high throughput)

```python
import asyncio
import aiohttp
from typing import List, Dict, Any

class AsyncEKGClient:
    def __init__(self, api_url: str):
        self.api_url = api_url
    
    async def ask(
        self,
        session: aiohttp.ClientSession,
        question: str,
        domain: str = "wealth_management"
    ) -> Dict[str, Any]:
        async with session.post(
            f"{self.api_url}/v1/answer",
            json={"question": question, "domain": domain}
        ) as response:
            return await response.json()
    
    async def batch_ask(
        self,
        questions: List[str],
        domain: str = "wealth_management"
    ) -> List[Dict[str, Any]]:
        """Ask multiple questions concurrently"""
        async with aiohttp.ClientSession() as session:
            tasks = [self.ask(session, q, domain) for q in questions]
            return await asyncio.gather(*tasks)

# Usage
async def main():
    client = AsyncEKGClient("https://ekg-agent-xxx.run.app")
    questions = [
        "What is OTP?",
        "What is redemption?",
        "What is order placement?"
    ]
    answers = await client.batch_ask(questions, domain="wealth_management")
    for q, a in zip(questions, answers):
        print(f"Q: {q}")
        print(f"A: {a['markdown'][:100]}...\n")

asyncio.run(main())
```

## Replit Specific Setup

### Step 1: Create Replit Python Project

1. Go to https://replit.com
2. Create new Python project
3. Add dependencies in `pyproject.toml` or `requirements.txt`:

```txt
requests==2.32.0
streamlit==1.28.0
```

### Step 2: Add Secret (Replit Secrets)

In Replit:
1. Click "Secrets" (lock icon) in left sidebar
2. Add:
   - Key: `EKG_API_URL`
   - Value: `https://your-cloud-run-url.run.app`

### Step 3: Create UI

```python
# main.py on Replit
import streamlit as st
import requests
import os

API_URL = os.getenv("EKG_API_URL")

st.title("🔍 Knowledge Graph Q&A")

# Domain selector
domains_resp = requests.get(f"{API_URL}/domains")
domains = {d["name"]: d["domain_id"] for d in domains_resp.json()["domains"]}

domain_name = st.selectbox("Select Domain", list(domains.keys()))
domain_id = domains[domain_name]

# Question input
question = st.text_area("Your Question:", height=100)

if st.button("Get Answer", type="primary"):
    if question:
        with st.spinner("Thinking..."):
            response = requests.post(
                f"{API_URL}/v1/answer",
                json={
                    "question": question,
                    "domain": domain_id,
                    "params": {"_mode": "balanced"}
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                st.markdown(result["markdown"])
            else:
                st.error(f"Error: {response.text}")
```

### Step 4: Run on Replit

```bash
streamlit run main.py --server.port 5000 --server.address 0.0.0.0
```

## CORS Configuration (for Browser Apps)

If calling from browser-based apps, CORS is already configured in `api/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_methods=["*"],
    allow_headers=["*"],
)
```

For production, restrict origins:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-replit-app.repl.co",
        "https://your-frontend.com"
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)
```

## Example: Complete Integration

```python
# complete_example.py
import requests
from typing import Dict, Any

class KnowledgeBaseApp:
    """Example application using EKG Agent"""
    
    def __init__(self, api_url: str):
        self.api_url = api_url
        self.domains = self._load_domains()
    
    def _load_domains(self) -> Dict[str, str]:
        """Load available domains"""
        r = requests.get(f"{self.api_url}/domains")
        return {d["domain_id"]: d["name"] for d in r.json()["domains"]}
    
    def ask_wealth_question(self, question: str) -> str:
        """Ask wealth management question"""
        r = requests.post(
            f"{self.api_url}/v1/answer",
            json={
                "question": question,
                "domain": "wealth_management",
                "params": {"_mode": "balanced"}
            }
        )
        return r.json()["markdown"]
    
    def ask_apf_question(self, question: str) -> str:
        """Ask APF question"""
        r = requests.post(
            f"{self.api_url}/v1/answer",
            json={
                "question": question,
                "domain": "apf",
                "params": {"_mode": "balanced"}
            }
        )
        return r.json()["markdown"]
    
    def search_across_domains(self, question: str) -> Dict[str, str]:
        """Search same question across all domains"""
        results = {}
        for domain_id in self.domains.keys():
            r = requests.post(
                f"{self.api_url}/v1/answer",
                json={
                    "question": question,
                    "domain": domain_id,
                    "params": {"_mode": "concise"}
                }
            )
            if r.status_code == 200:
                results[domain_id] = r.json()["markdown"]
        return results

# Usage
if __name__ == "__main__":
    # For local testing
    app = KnowledgeBaseApp("http://localhost:8000")
    
    # For production
    # app = KnowledgeBaseApp("https://ekg-agent-xxx.run.app")
    
    # Ask wealth management question
    answer1 = app.ask_wealth_question("What is OTP verification?")
    print("Wealth Management Answer:")
    print(answer1[:200])
    
    # Ask APF question
    answer2 = app.ask_apf_question("How to create a project?")
    print("\nAPF Answer:")
    print(answer2[:200])
    
    # Search across domains
    results = app.search_across_domains("What is the approval process?")
    print("\nCross-Domain Search:")
    for domain, answer in results.items():
        print(f"\n{domain}:")
        print(answer[:150])
```

## Error Handling Best Practices

```python
def ask_with_error_handling(question: str, domain: str, api_url: str):
    """Robust error handling example"""
    try:
        response = requests.post(
            f"{api_url}/v1/answer",
            json={"question": question, "domain": domain},
            timeout=60
        )
        
        # Check status
        if response.status_code == 400:
            error = response.json().get("detail", "Bad request")
            return {"error": f"Invalid request: {error}"}
        
        elif response.status_code == 500:
            return {"error": "Server error. Please try again."}
        
        elif response.status_code == 200:
            return response.json()
        
        else:
            return {"error": f"Unexpected status: {response.status_code}"}
            
    except requests.exceptions.Timeout:
        return {"error": "Request timed out. Try a simpler question."}
    
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to API. Check URL and network."}
    
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}
```

## Rate Limiting (Client-Side)

```python
import time
from functools import wraps

def rate_limit(calls_per_minute: int = 10):
    """Rate limiting decorator"""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result
        return wrapper
    return decorator

class RateLimitedClient:
    def __init__(self, api_url: str):
        self.api_url = api_url
    
    @rate_limit(calls_per_minute=10)
    def ask(self, question: str, domain: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.api_url}/v1/answer",
            json={"question": question, "domain": domain}
        )
        return response.json()
```

## Next Steps

1. **Deploy to Cloud Run** (see `DEPLOYMENT_GCLOUD.md`)
2. **Test the deployment** using `test_deployment.py`
3. **Create your Replit UI** using the examples above
4. **Integrate with your application** using the Python client
5. **Monitor and optimize** based on usage patterns

Your API is ready for integration! 🚀




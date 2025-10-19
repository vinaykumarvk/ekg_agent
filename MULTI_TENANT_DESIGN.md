# Multi-Tenant Design for EKG Agent

## Current Architecture Analysis

### Current State:
- **Single KG**: Hardcoded to `data/kg/master_knowledge_graph.json`
- **Single Cache**: `@lru_cache(maxsize=1)` loads one KG globally
- **Vector Store**: Already parameterized via `vectorstore_id` in request
- **Agent**: Already accepts KG parameters (G, by_id, name_index)

### What Works Well:
✅ Vector store is already parameterized  
✅ Agent is designed to accept any KG  
✅ Core functions are stateless  
✅ Request-level parameterization exists  

### What Needs Change:
❌ KG loading is cached globally (only one KG)  
❌ No way to specify which KG to use  
❌ API schema doesn't accept KG identifier  

---

## Proposed Solution: Domain-Based Multi-Tenancy

### Design Overview

```
Request
  ↓
{
  "question": "...",
  "domain": "wealth_management",  ← NEW
  "vectorstore_id": "vs_xxx",
  "params": {...}
}
  ↓
Domain Config Lookup
  ↓
Load KG for domain (cached per domain)
  ↓
Create Agent with domain-specific KG + VS
  ↓
Generate Answer
```

---

## Implementation Strategy

### Phase 1: Add Domain Configuration

**1. Create Domain Registry**

```python
# api/domains.py
from dataclasses import dataclass
from typing import Dict

@dataclass
class DomainConfig:
    """Configuration for a specific domain/subject"""
    domain_id: str
    name: str
    kg_path: str
    default_vectorstore_id: str | None = None
    description: str = ""

# Registry of available domains
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path="data/kg/master_knowledge_graph.json",
        default_vectorstore_id="vs_689b49252a4c8191a12a1528a475fbd8",
        description="Mutual funds, orders, customer onboarding"
    ),
    "healthcare": DomainConfig(
        domain_id="healthcare",
        name="Healthcare Systems",
        kg_path="data/kg/healthcare_kg.json",
        default_vectorstore_id="vs_healthcare_docs",
        description="Medical procedures, patient care"
    ),
    "legal": DomainConfig(
        domain_id="legal",
        name="Legal Compliance",
        kg_path="data/kg/legal_kg.json",
        default_vectorstore_id="vs_legal_docs",
        description="Regulations, compliance, legal documents"
    ),
}

def get_domain(domain_id: str) -> DomainConfig:
    """Get domain configuration by ID"""
    if domain_id not in DOMAINS:
        raise ValueError(f"Unknown domain: {domain_id}")
    return DOMAINS[domain_id]

def list_domains() -> list[DomainConfig]:
    """List all available domains"""
    return list(DOMAINS.values())
```

**2. Update Request Schema**

```python
# api/schemas.py
from pydantic import BaseModel
from typing import Any, Dict, Optional

class AskRequest(BaseModel):
    question: str
    domain: str = "wealth_management"  # NEW: default to existing
    vectorstore_id: Optional[str] = None  # Made optional (can use domain default)
    params: Optional[Dict[str, Any]] = None

class DomainInfo(BaseModel):
    domain_id: str
    name: str
    description: str
    kg_nodes: int
    kg_edges: int
    default_vectorstore_id: Optional[str]

class AskResponse(BaseModel):
    markdown: str
    sources: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
```

**3. Implement Per-Domain KG Cache**

```python
# api/main.py
from functools import lru_cache
from api.domains import get_domain, list_domains

# Change from single cache to per-domain cache
_KG_CACHE: Dict[str, Tuple[Any, Dict[str, Any], Dict[str, Any]]] = {}

def load_graph_artifacts(domain_id: str) -> Tuple[Any, Dict[str, Any], Dict[str, Any]]:
    """
    Load graph artifacts for a specific domain.
    Results are cached per domain for performance.
    """
    # Check cache first
    if domain_id in _KG_CACHE:
        log.debug(f"Using cached KG for domain: {domain_id}")
        return _KG_CACHE[domain_id]
    
    # Load from config
    from ekg_core import load_kg_from_json
    
    G = None
    by_id: Dict[str, Any] = {}
    name_index: Dict[str, Any] = {}
    
    try:
        domain_config = get_domain(domain_id)
        kg_path = domain_config.kg_path
        
        if not os.path.isabs(kg_path):
            # Resolve relative paths from project root
            base_dir = os.path.dirname(os.path.dirname(__file__))
            kg_path = os.path.join(base_dir, kg_path)
        
        if os.path.exists(kg_path):
            log.info(f"Loading KG for domain '{domain_id}' from {kg_path}")
            G, by_id, name_index = load_kg_from_json(kg_path)
            log.info(f"✓ Loaded KG for '{domain_id}': {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
            
            # Cache the result
            _KG_CACHE[domain_id] = (G, by_id, name_index)
        else:
            log.warning(f"KG file not found for domain '{domain_id}': {kg_path}")
            
    except ValueError as e:
        log.error(f"Invalid domain: {e}")
    except Exception as e:
        log.error(f"KG load failed for domain '{domain_id}': {e}", exc_info=True)
    
    return G, by_id, name_index

def get_agent(domain_id: str, vectorstore_id: str, params: Dict[str, Any] | None = None) -> EKGAgent:
    """Create an agent for a specific domain and vector store"""
    client = get_client()
    G, by_id, name_index = load_graph_artifacts(domain_id)
    return EKGAgent(
        client=client,
        vs_id=vectorstore_id,
        G=G,
        by_id=by_id,
        name_index=name_index,
        preset_params=params or {},
    )
```

**4. Update API Endpoints**

```python
# api/main.py

@app.get("/domains")
def list_available_domains():
    """List all available domains/subjects"""
    from api.domains import list_domains
    
    domains_info = []
    for domain_config in list_domains():
        G, by_id, name_index = load_graph_artifacts(domain_config.domain_id)
        domains_info.append({
            "domain_id": domain_config.domain_id,
            "name": domain_config.name,
            "description": domain_config.description,
            "kg_loaded": G is not None,
            "kg_nodes": G.number_of_nodes() if G else 0,
            "kg_edges": G.number_of_edges() if G else 0,
            "default_vectorstore_id": domain_config.default_vectorstore_id,
        })
    
    return {"domains": domains_info}

@app.post("/v1/answer", response_model=AskResponse)
def answer(req: AskRequest) -> AskResponse:
    try:
        # Get domain config
        domain_config = get_domain(req.domain)
        
        # Use request vectorstore_id or domain default
        vectorstore_id = req.vectorstore_id or domain_config.default_vectorstore_id
        if not vectorstore_id:
            raise HTTPException(
                status_code=400,
                detail=f"No vector store specified for domain '{req.domain}'"
            )
        
        # Create agent for this domain + vector store
        agent = get_agent(req.domain, vectorstore_id, req.params)
        raw = agent.answer(req.question)
        
        # Add domain info to metadata
        if "meta" not in raw or raw["meta"] is None:
            raw["meta"] = {}
        raw["meta"]["domain"] = req.domain
        raw["meta"]["vectorstore_id"] = vectorstore_id
        
        return _normalize_answer(raw)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Answer handler failed")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    """Health check with domain loading status"""
    from api.domains import list_domains
    
    domain_status = {}
    for domain_config in list_domains():
        G, by_id, name_index = load_graph_artifacts(domain_config.domain_id)
        domain_status[domain_config.domain_id] = {
            "loaded": G is not None,
            "nodes": G.number_of_nodes() if G else 0,
            "edges": G.number_of_edges() if G else 0,
        }
    
    ok = True
    err = None
    try:
        _ = get_client()
    except Exception as e:
        ok = False
        err = f"OpenAI client init failed: {e}"
    
    return {
        "status": "healthy" if ok else "degraded",
        "service_loaded": True,
        "available_modes": ["concise", "balanced", "deep"],
        "domains": domain_status,
        "error": err,
    }
```

---

## Usage Examples

### Example 1: Query Wealth Management (Current Domain)

```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the OTP process for redemption?",
    "domain": "wealth_management",
    "vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8",
    "params": {"_mode": "balanced"}
  }'
```

### Example 2: Query Healthcare Domain

```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the pre-operative procedures?",
    "domain": "healthcare",
    "vectorstore_id": "vs_healthcare_docs",
    "params": {"_mode": "deep"}
  }'
```

### Example 3: Use Domain Default Vector Store

```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are compliance requirements?",
    "domain": "legal"
  }'
# Uses default_vectorstore_id from domain config
```

### Example 4: List Available Domains

```bash
curl http://localhost:8000/domains
```

Response:
```json
{
  "domains": [
    {
      "domain_id": "wealth_management",
      "name": "Wealth Management",
      "description": "Mutual funds, orders, customer onboarding",
      "kg_loaded": true,
      "kg_nodes": 938,
      "kg_edges": 1639,
      "default_vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8"
    },
    {
      "domain_id": "healthcare",
      "name": "Healthcare Systems",
      "description": "Medical procedures, patient care",
      "kg_loaded": false,
      "kg_nodes": 0,
      "kg_edges": 0,
      "default_vectorstore_id": "vs_healthcare_docs"
    }
  ]
}
```

---

## File Structure

```
ekg_agent/
├── api/
│   ├── domains.py          # NEW: Domain registry
│   ├── main.py             # MODIFIED: Multi-domain support
│   ├── schemas.py          # MODIFIED: Add domain field
│   └── settings.py         # Unchanged
├── data/
│   └── kg/
│       ├── master_knowledge_graph.json       # Wealth management
│       ├── healthcare_kg.json                # Healthcare (NEW)
│       └── legal_kg.json                     # Legal (NEW)
├── agents/                 # Unchanged (already flexible)
├── ekg_core/              # Unchanged (already flexible)
└── tests/
    ├── test_api.py        # MODIFIED: Add domain tests
    └── test_domains.py    # NEW: Test multi-domain
```

---

## Migration Path

### Step 1: Add Domain Registry (Backward Compatible)
- Create `api/domains.py` with default domain
- Existing code works without changes

### Step 2: Update Schemas (Backward Compatible)
- Add `domain` field with default value
- Existing clients work unchanged

### Step 3: Update KG Loading
- Replace `@lru_cache` with dict cache
- Load per domain

### Step 4: Add New Endpoints
- `GET /domains` - list domains
- Update `/health` - show domain status

### Step 5: Add New Domains
- Create new KG files
- Add to registry
- Test independently

---

## Benefits

✅ **Zero Breaking Changes**: Existing clients work unchanged  
✅ **Independent Scaling**: Each domain loads only when used  
✅ **Memory Efficient**: LRU cache per domain  
✅ **Easy Extension**: Add new domain = add config + KG file  
✅ **Clear Separation**: Each domain isolated  
✅ **Flexible**: Can override vector store per request  

---

## Advanced: Dynamic Domain Loading from Database

For even more flexibility, domains could be loaded from a database:

```python
# api/domains.py
import sqlite3

def load_domains_from_db():
    """Load domain configurations from database"""
    conn = sqlite3.connect('domains.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM domains WHERE active=1')
    # ... build DOMAINS dict from DB rows
```

This allows adding new domains without code deployment!

---

## Testing Strategy

```python
# tests/test_domains.py
def test_domain_registry():
    """Test domain configuration"""
    from api.domains import get_domain, list_domains
    
    # Test default domain exists
    wm = get_domain("wealth_management")
    assert wm.kg_path == "data/kg/master_knowledge_graph.json"
    
    # Test listing
    domains = list_domains()
    assert len(domains) > 0

def test_multi_domain_loading():
    """Test loading multiple KGs"""
    from api.main import load_graph_artifacts
    
    # Load wealth management
    G1, by_id1, idx1 = load_graph_artifacts("wealth_management")
    assert G1.number_of_nodes() == 938
    
    # Load healthcare (if exists)
    G2, by_id2, idx2 = load_graph_artifacts("healthcare")
    # Should be independent
    assert by_id1 != by_id2

def test_domain_in_request():
    """Test API with domain parameter"""
    client = TestClient(app)
    
    response = client.post("/v1/answer", json={
        "question": "Test question",
        "domain": "wealth_management",
        "vectorstore_id": "vs_test"
    })
    
    assert response.status_code == 200
    assert "wealth_management" in response.json()["meta"]["domain"]
```

---

## Next Steps

1. **Review this design** - Confirm it meets your requirements
2. **Implement Phase 1** - Add domain registry (backward compatible)
3. **Test with existing domain** - Ensure no regressions
4. **Add second domain** - Validate multi-tenant works
5. **Document for users** - API docs, examples

Would you like me to implement this solution?




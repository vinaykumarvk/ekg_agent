# Adding Your Second Domain - Quick Guide

## Current Status
✅ Multi-domain system implemented and tested  
✅ `wealth_management` domain working  
✅ All tests passing (6/6)  
✅ Server running with multi-domain support  

## Steps to Add Your Second Domain

### 1. Upload Knowledge Graph File

Place your second domain's KG JSON file here:
```bash
/Users/n15318/ekg_agent/data/kg/[your_domain_name]_kg.json
```

**Example:**
```bash
# If your domain is "healthcare"
/Users/n15318/ekg_agent/data/kg/healthcare_kg.json
```

### 2. Get Vector Store ID

Provide the vector store ID for this domain.

**Example:**
```
vs_healthcare_xxxxxxxxxxxxxxxxxxxx
```

### 3. Edit Domain Registry

Open `api/domains.py` and add your domain to the `DOMAINS` dictionary:

```python
DOMAINS: Dict[str, DomainConfig] = {
    "wealth_management": DomainConfig(
        domain_id="wealth_management",
        name="Wealth Management",
        kg_path="data/kg/master_knowledge_graph.json",
        default_vectorstore_id="vs_689b49252a4c8191a12a1528a475fbd8",
        description="Mutual funds, orders, customer onboarding, and wealth management processes"
    ),
    # ADD YOUR NEW DOMAIN HERE:
    "your_domain_id": DomainConfig(
        domain_id="your_domain_id",
        name="Your Domain Name",
        kg_path="data/kg/your_domain_kg.json",
        default_vectorstore_id="vs_your_vector_store_id",
        description="Description of what this domain covers"
    ),
}
```

### 4. Restart the Server

```bash
# Stop current server
pkill -f "uvicorn api.main:app"

# Start fresh
./run_server.sh
```

### 5. Verify Domain Loaded

```bash
# List all domains
curl http://localhost:8000/domains

# Should show both domains with their stats
```

Expected output:
```json
{
  "domains": [
    {
      "domain_id": "wealth_management",
      "name": "Wealth Management",
      "kg_loaded": true,
      "kg_nodes": 938,
      "kg_edges": 1639,
      ...
    },
    {
      "domain_id": "your_domain_id",
      "name": "Your Domain Name",
      "kg_loaded": true,
      "kg_nodes": XXX,
      "kg_edges": XXX,
      ...
    }
  ]
}
```

### 6. Test Your New Domain

```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Your test question here",
    "domain": "your_domain_id"
  }'
```

## What You Need to Provide

Please provide the following information for your second domain:

1. **Domain ID**: A short identifier (e.g., "healthcare", "legal", "hr")
   - Should be lowercase, no spaces
   - Used in API requests

2. **Display Name**: Human-readable name (e.g., "Healthcare Systems")
   - Shown in /domains listing
   - Can have spaces and capitals

3. **Knowledge Graph File**: The JSON file containing nodes and edges
   - Should have same structure as `master_knowledge_graph.json`
   - Must have "nodes" and "edges" arrays

4. **Vector Store ID**: OpenAI vector store ID (e.g., "vs_xxx...")
   - Must be accessible with your API key
   - Should contain documents for this domain

5. **Description**: Brief description of what this domain covers (optional)

## Example

Here's what I'll need for, say, a "healthcare" domain:

```
Domain ID: healthcare
Display Name: Healthcare Management
KG File: [upload to data/kg/healthcare_kg.json]
Vector Store ID: vs_healthcare_123abc...
Description: Medical procedures, patient care, healthcare workflows
```

Then I'll:
1. Receive your KG file
2. Add the configuration
3. Test it works
4. Verify both domains work independently

## Testing Checklist

Once added, we'll verify:
- [ ] Domain shows in `/domains` endpoint
- [ ] Health check shows domain loaded
- [ ] KG statistics are correct
- [ ] Vector store returns results
- [ ] Answers combine KG + vector data
- [ ] Both domains work independently
- [ ] Switching between domains works seamlessly

## Ready!

Just provide the information above, and I'll integrate your second domain for testing! 🚀




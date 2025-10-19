# EKG Agent - Knowledge Graph + Vector RAG API

A FastAPI service that combines Knowledge Graph traversal with Vector Store retrieval to provide hybrid, context-aware answers about wealth management processes.

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- OpenAI API key
- Knowledge graph JSON file (already loaded at `data/kg/master_knowledge_graph.json`)

### Installation

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the project
pip install -e .

# Install additional dependencies
pip install pydantic-settings pytest
```

### Configuration

**Quick Setup:**

```bash
# Copy the example file
cp .env.example .env

# Edit .env and add your OpenAI API key
nano .env  # or use your preferred editor
```

Your `.env` file should contain:
```env
OPENAI_API_KEY=sk-proj-your-actual-key-here
MODEL_DEFAULT=gpt-4o
```

**Alternative:** Export as environment variable:
```bash
export OPENAI_API_KEY=sk-proj-your-key-here
```

📖 **For detailed secrets management (Docker, Kubernetes, Cloud):** See [SECRETS_GUIDE.md](SECRETS_GUIDE.md)

### Running the API

```bash
# Start the FastAPI server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## 🧪 Testing

### Run All Tests

```bash
# Run the full test suite
pytest -v

# Run specific test file
pytest tests/test_kg_integration.py -v

# Run with coverage
pytest --cov=api --cov=agents --cov=ekg_core
```

### Test Results

All 6 tests passing:
- ✅ Health endpoint imports and responds
- ✅ Vector-only answer mode works
- ✅ Knowledge graph loads successfully (938 nodes, 1,639 edges)
- ✅ KG structure validation
- ✅ Health reports KG loaded correctly
- ✅ Name index lookup functionality

## 📊 Knowledge Graph

### Inspect the KG

```bash
python scripts/inspect_kg.py
```

**Current KG Stats:**
- **Nodes:** 938
- **Edges:** 1,639  
- **Name Aliases:** 3,183

**Top Node Types:**
- DataEntity (366)
- Report (247)
- Compliance (119)
- System (105)
- AUM (58)

**Top Edge Types:**
- CONTAINS (470)
- DISPLAYED_ON (384)
- VALIDATES (221)
- PROCESSES (150)
- FEEDS (102)

## 🔌 API Endpoints

### List Domains

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
      "description": "Mutual funds, orders, customer onboarding...",
      "kg_loaded": true,
      "kg_nodes": 938,
      "kg_edges": 1639,
      "default_vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8"
    }
  ]
}
```

### Health Check

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "service_loaded": true,
  "available_modes": ["concise", "balanced", "deep"],
  "domains": {
    "wealth_management": {
      "loaded": true,
      "nodes": 938,
      "edges": 1639
    }
  },
  "error": null
}
```

### Answer Endpoint

**With explicit domain:**
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the order lifecycle?",
    "domain": "wealth_management",
    "vectorstore_id": "vs_your_vector_store_id",
    "params": {
      "_mode": "balanced"
    }
  }'
```

**Conversational follow-up (using response_id):**
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How long does the process take?",
    "domain": "wealth_management",
    "response_id": "123e4567-e89b-12d3-a456-426614174000"
  }'
```

**Conversational follow-up (using conversation_id):**
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the requirements?",
    "domain": "wealth_management",
    "conversation_id": "conv-abc123-def456"
  }'
```

**Using domain default vector store:**
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the order lifecycle?",
    "domain": "wealth_management"
  }'
```

**Backward compatible (defaults to wealth_management):**
```bash
curl -X POST http://localhost:8000/v1/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the order lifecycle?",
    "vectorstore_id": "vs_your_vector_store_id"
  }'
```

**Response:**
```json
{
  "response_id": "123e4567-e89b-12d3-a456-426614174000",
  "markdown": "**Answer:** The order lifecycle...",
  "sources": [...],
  "meta": {
    "model": "gpt-4o",
    "mode": "balanced",
    "domain": "wealth_management",
    "vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8",
    "is_conversational": false,
    "export_path": "./outputs/what-is-the-order-lifecycle--20241018-1430.md"
  }
}
```

**Conversational Response:**
```json
{
  "response_id": "123e4567-e89b-12d3-a456-426614174000",
  "markdown": "**Answer:** The process typically takes 2-3 business days...",
  "sources": [...],
  "meta": {
    "model": "gpt-4o",
    "mode": "balanced",
    "domain": "wealth_management",
    "vectorstore_id": "vs_689b49252a4c8191a12a1528a475fbd8",
    "is_conversational": true,
    "previous_response_id": "123e4567-e89b-12d3-a456-426614174000",
    "export_path": "./outputs/how-long-does-process-take--20241018-1430.md"
  }
}
```

## 💬 Conversational Responses

The API supports conversational context through response IDs and conversation IDs:

### Request Fields
- `response_id` - Links to a previous response for context
- `conversation_id` - Alternative conversation tracking identifier

### Response Metadata
- `is_conversational` - Boolean flag indicating conversational context
- `previous_response_id` - ID of the previous response (if provided)
- `conversation_id` - Conversation identifier (if provided)

### Usage Patterns
1. **Initial Query** - No context needed
2. **Follow-up** - Use `response_id` from previous response
3. **Conversation Thread** - Use `conversation_id` for multi-turn conversations
4. **New Topic** - Start fresh without context

## 🎯 Answer Modes

The API supports three answer modes with different depth and detail:

### Concise Mode
- **Model:** gpt-5-nano
- **Hops:** 1
- **Max Chunks:** 6
- **Max Tokens:** 1,500
- **Use case:** Quick, focused answers

```json
{"params": {"_mode": "concise"}}
```

### Balanced Mode (Default)
- **Model:** gpt-5-mini
- **Hops:** 1
- **Max Chunks:** 10
- **Max Tokens:** 6,000
- **Use case:** Standard comprehensive answers

```json
{"params": {"_mode": "balanced"}}
```

### Deep Mode
- **Model:** gpt-5
- **Hops:** 2
- **Max Chunks:** 22
- **Max Tokens:** 20,000
- **Use case:** Exhaustive analysis with all details

```json
{"params": {"_mode": "deep"}}
```

## 🏗️ Architecture

```
┌─────────────────┐
│   FastAPI App   │
│   (api/main.py) │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼───────┐
│ EKG  │  │ Settings │
│Agent │  │  & Deps  │
└───┬──┘  └──────────┘
    │
    ├─────────────────────────────────┐
    │                                 │
┌───▼────────────┐         ┌─────────▼─────────┐
│ KG Extraction  │         │ Vector Extraction │
│ (kg_extraction)│         │ (vector_extract.) │
└───┬────────────┘         └─────────┬─────────┘
    │                                 │
    └────────────┬────────────────────┘
                 │
         ┌───────▼────────┐
         │  ekg_core      │
         │ • load_kg_from_json()
         │ • hybrid_answer()
         │ • answer_with_kg()
         └────────────────┘
```

**Key Design Principle:** The codebase reuses existing functions from `ekg_core/core.py` wherever possible. The API layer is a thin wrapper that calls these core functions with appropriate parameters.

## 📁 Project Structure

```
ekg_agent/
├── agents/                 # Agent orchestration layer
│   ├── ekg_agent.py       # Main agent that routes to KG/vector/hybrid
│   └── tools/             # Individual tool modules
│       ├── intent_clarification.py
│       ├── kg_extraction.py
│       ├── vector_extraction.py
│       └── answer_formatting.py
├── api/                   # FastAPI application
│   ├── main.py           # Endpoints and KG loader
│   ├── schemas.py        # Request/response models
│   └── settings.py       # Configuration
├── ekg_core/             # Core hybrid answer logic
│   └── core.py           # KG traversal, vector search, hybrid fusion
├── data/                 # Data files
│   └── kg/
│       └── master_knowledge_graph.json
├── tests/                # Test suite
│   ├── test_api.py
│   └── test_kg_integration.py
├── scripts/              # Utility scripts
│   └── inspect_kg.py
└── outputs/              # Generated markdown exports
```

## 🐳 Docker Support

```dockerfile
# Build image
docker build -t ekg-agent .

# Run container
docker run -d \
  -p 8000:8000 \
  -e OPENAI_API_KEY=your_key_here \
  -v $(pwd)/data:/app/data \
  ekg-agent
```

## 🔧 Development

### Code Quality

```bash
# Run linter (if configured)
ruff check .

# Format code
ruff format .
```

### Adding New Tests

Tests are located in `tests/`. Create new test files following the pattern:

```python
import pytest

@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")

def test_your_feature():
    # Your test here
    pass
```

## 🚨 Troubleshooting

### KG Not Loading

Check the logs for:
```
Loading KG from /path/to/data/kg/master_knowledge_graph.json
✓ Loaded KG: X nodes, Y edges, Z aliases
```

If missing, verify:
- File exists at `data/kg/master_knowledge_graph.json`
- File has correct JSON structure with `nodes` and `edges` arrays
- `KG_DATA_DIR` environment variable (if set) points to correct location

### OPENAI_API_KEY Required Error

The API requires `OPENAI_API_KEY` to be set. Either:
- Create `.env` file with the key
- Export it: `export OPENAI_API_KEY=your_key`
- Pass it when starting: `OPENAI_API_KEY=your_key uvicorn api.main:app`

### Export Directory Issues

By default, markdown exports go to `outputs/`. Override with:
```bash
export EKG_EXPORT_DIR=/your/custom/path
```

## 🌐 Multi-Domain Support

The EKG Agent supports multiple domains (subjects), each with its own knowledge graph and vector store.

### Adding a New Domain

**Step 1: Prepare your knowledge graph**
```bash
# Place your KG JSON file in data/kg/
cp your_kg.json data/kg/new_domain_kg.json
```

**Step 2: Add domain configuration**

Edit `api/domains.py` and add to the `DOMAINS` dictionary:

```python
"new_domain": DomainConfig(
    domain_id="new_domain",
    name="New Domain Name",
    kg_path="data/kg/new_domain_kg.json",
    default_vectorstore_id="vs_your_vector_store_id",
    description="Description of this domain"
),
```

**Step 3: Restart the server**
```bash
./run_server.sh
```

**Step 4: Verify**
```bash
curl http://localhost:8000/domains
```

### Helper Script

Use the interactive helper:
```bash
python scripts/add_domain.py
```

### Using Multiple Domains

```python
# Query wealth management domain
response = requests.post("http://localhost:8000/v1/answer", json={
    "question": "What is OTP verification?",
    "domain": "wealth_management"
})

# Query different domain
response = requests.post("http://localhost:8000/v1/answer", json={
    "question": "What is pre-operative procedure?",
    "domain": "healthcare"
})
```

## 📝 Next Steps

- [ ] Add real OpenAI API key for production use
- [ ] Configure vector store ID for your documents
- [x] Multi-domain support implemented
- [ ] Add authentication/authorization
- [ ] Set up CI/CD pipeline
- [ ] Add more comprehensive integration tests
- [ ] Optimize KG queries for large graphs
- [ ] Add caching layer for repeated queries

## 📄 License

[Your License Here]

## 🤝 Contributing

[Your Contributing Guidelines]


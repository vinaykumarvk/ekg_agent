import os
import types
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


# Test configuration
TEST_VECTOR_STORE_ID = "vs_test_vectorstore_id_12345"
TEST_WM_KG_PATH = "gs://test-bucket/kg/wealth_product_kg.json"
TEST_APF_KG_PATH = "gs://test-bucket/kg/apf_kg.json"


def make_mock_openai_client():
    """Minimal mock of OpenAI client used by our code paths."""
    # responses.create(model=..., input=[...]) -> object with .output_text
    def responses_create(model: str, input: list, max_output_tokens: int = None, temperature: float = None):
        class Resp:
            output_text = "This is a mocked answer. [1]"
        return Resp()

    # vector_stores.search(...) -> with .data entries having .content[0].text
    def vector_search(vector_store_id: str, query: str):
        class Hit:
            def __init__(self, text: str, filename: str = "doc.txt", score: float = 0.5):
                self.filename = filename
                self.file_id = "file_1"
                self.score = score
                self.content = [types.SimpleNamespace(text=text)]

        class Res:
            data = [Hit(text=f"Chunk for: {query}")]

        return Res()

    # embeddings.create(model=..., input=...) -> vector
    def embeddings_create(model: str, input: str):
        class Emb:
            def __init__(self):
                self.data = [types.SimpleNamespace(embedding=[0.1, 0.2, 0.3])]
        return Emb()

    client = types.SimpleNamespace()
    client.responses = types.SimpleNamespace(create=responses_create)
    client.vector_stores = types.SimpleNamespace(search=vector_search)
    client.embeddings = types.SimpleNamespace(create=embeddings_create)
    return client


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    """Set required environment variables for tests"""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key-12345")
    monkeypatch.setenv("DOC_VECTOR_STORE_ID", TEST_VECTOR_STORE_ID)
    monkeypatch.setenv("WEALTH_MANAGEMENT_KG_PATH", TEST_WM_KG_PATH)
    monkeypatch.setenv("APF_KG_PATH", TEST_APF_KG_PATH)


@pytest.fixture
def mock_gcs_and_kg():
    """Mock GCS storage client and KG loading"""
    import networkx as nx
    
    # Create mock graph
    mock_graph = nx.MultiDiGraph()
    mock_graph.add_node("node1", id="node1", name="Test Node 1")
    mock_graph.add_node("node2", id="node2", name="Test Node 2")
    mock_graph.add_edge("node1", "node2", type="RELATED")
    
    def mock_load_kg(path):
        return mock_graph, {"node1": {}, "node2": {}}, {"test node": ["node1"]}
    
    # Mock the google.cloud.storage module directly
    with patch("google.cloud.storage") as mock_storage:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        with patch("ekg_core.load_kg_from_json", side_effect=mock_load_kg):
            yield


def test_health_imports_and_env(mock_gcs_and_kg):
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"healthy", "degraded"}
    assert "available_modes" in body


def test_answer_vector_mode(monkeypatch, mock_gcs_and_kg):
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    # Force intent to vector to avoid KG requirements
    from agents.tools import intent_clarification

    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)

    monkeypatch.setattr(intent_clarification, "clarify_intent", fake_intent)

    # Inject mock OpenAI client into dependency provider
    import api.main as main_mod

    def fake_get_client():
        return make_mock_openai_client()

    # Clear cache on provider and set fake
    main_mod.get_client.cache_clear()  # type: ignore[attr-defined]
    monkeypatch.setattr(main_mod, "get_client", fake_get_client)

    app = main_mod.app
    client = TestClient(app)

    payload = {
        "question": "Give an overview of the process.",
        "vectorstore_id": "vs_dummy",
        "params": {"_mode": "concise"}
    }

    r = client.post("/v1/answer", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("markdown", ""), str)
    # Should include normalized fields even if sources/meta are None
    assert "sources" in data
    assert "meta" in data




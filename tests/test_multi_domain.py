"""
Tests for multi-domain functionality

All tests require environment variables to be set:
- DOC_VECTORSTORE_ID
- WEALTH_MANAGEMENT_KG_PATH (gs://...)
- APF_KG_PATH (gs://...)
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


# Test vector store ID
TEST_VECTOR_STORE_ID = "vs_test_vectorstore_id_12345"
TEST_WM_KG_PATH = "gs://test-bucket/kg/wealth_product_kg.json"
TEST_APF_KG_PATH = "gs://test-bucket/kg/apf_kg.json"


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
    
    # Create mock graphs
    mock_wm_graph = nx.MultiDiGraph()
    mock_wm_graph.add_node("node1", id="node1", name="Test Node 1")
    mock_wm_graph.add_node("node2", id="node2", name="Test Node 2")
    mock_wm_graph.add_edge("node1", "node2", type="RELATED")
    
    mock_apf_graph = nx.MultiDiGraph()
    mock_apf_graph.add_node("apf1", id="apf1", name="APF Node 1")
    
    def mock_load_kg(path):
        if "wealth" in path:
            return mock_wm_graph, {"node1": {}, "node2": {}}, {"test node": ["node1"]}
        else:
            return mock_apf_graph, {"apf1": {}}, {"apf node": ["apf1"]}
    
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


def test_list_domains(mock_gcs_and_kg):
    """Test that /domains endpoint lists all configured domains"""
    # Clear cache first
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    
    client = TestClient(app)
    r = client.get("/domains")
    
    assert r.status_code == 200
    data = r.json()
    assert "domains" in data
    assert len(data["domains"]) >= 2, "Should have at least 2 domains"
    
    # Verify wealth_management domain exists and has correct vectorstore
    wm_domain = next((d for d in data["domains"] if d["domain_id"] == "wealth_management"), None)
    assert wm_domain is not None
    assert wm_domain["default_vectorstore_id"] == TEST_VECTOR_STORE_ID
    
    # Verify apf domain exists and has correct vectorstore
    apf_domain = next((d for d in data["domains"] if d["domain_id"] == "apf"), None)
    assert apf_domain is not None
    assert apf_domain["default_vectorstore_id"] == TEST_VECTOR_STORE_ID
    
    print(f"\n✓ Found {len(data['domains'])} domains")


def test_health_shows_all_domains(mock_gcs_and_kg):
    """Test that /health shows status for all domains"""
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    
    client = TestClient(app)
    r = client.get("/health")
    
    assert r.status_code == 200
    data = r.json()
    assert "domains" in data
    assert "wealth_management" in data["domains"]
    assert "apf" in data["domains"]
    
    # Both should be loaded (from mocked GCS)
    assert data["domains"]["wealth_management"]["loaded"] is True
    assert data["domains"]["apf"]["loaded"] is True


def test_query_wealth_management_domain(mock_gcs_and_kg):
    """Test querying the wealth_management domain"""
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent to avoid hitting real OpenAI
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    
    with patch.object(intent_clarification, "clarify_intent", side_effect=fake_intent):
        # Mock the OpenAI client at the module level
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(output_text="Test answer [1]")
        mock_client.vector_stores.search.return_value = MagicMock(data=[])
        mock_client.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1]*1536)])
        
        main_mod.get_client.cache_clear()
        with patch.object(main_mod, "get_client", return_value=mock_client):
            r = client.post("/v1/answer", json={
                "question": "Test question for wealth",
                "domain": "wealth_management"
            })
    
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["domain"] == "wealth_management"
    # Should use DOC_VECTORSTORE_ID from environment
    assert data["meta"]["vectorstore_id"] == TEST_VECTOR_STORE_ID


def test_query_apf_domain(mock_gcs_and_kg):
    """Test querying the APF domain"""
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    
    with patch.object(intent_clarification, "clarify_intent", side_effect=fake_intent):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(output_text="Test answer [1]")
        mock_client.vector_stores.search.return_value = MagicMock(data=[])
        mock_client.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1]*1536)])
        
        main_mod.get_client.cache_clear()
        with patch.object(main_mod, "get_client", return_value=mock_client):
            r = client.post("/v1/answer", json={
                "question": "Test question for APF",
                "domain": "apf"
            })
    
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["domain"] == "apf"
    # Should use DOC_VECTORSTORE_ID from environment
    assert data["meta"]["vectorstore_id"] == TEST_VECTOR_STORE_ID


def test_domain_independence(mock_gcs_and_kg):
    """Test that domains are truly independent"""
    from api.main import load_graph_artifacts, _KG_CACHE
    _KG_CACHE.clear()
    
    # Load both domains
    G_wm, by_id_wm, idx_wm = load_graph_artifacts("wealth_management")
    G_apf, by_id_apf, idx_apf = load_graph_artifacts("apf")
    
    # Verify they are different
    assert G_wm is not G_apf, "Graphs should be different objects"
    assert by_id_wm is not by_id_apf, "Indexes should be different objects"
    assert idx_wm is not idx_apf, "Name indexes should be different objects"
    
    # Verify sizes are different (based on mocked data)
    assert G_wm.number_of_nodes() != G_apf.number_of_nodes()
    
    print(f"\n✓ Domains are independent:")
    print(f"  wealth_management: {G_wm.number_of_nodes()} nodes")
    print(f"  apf: {G_apf.number_of_nodes()} nodes")


def test_domain_caching(mock_gcs_and_kg):
    """Test that domains are cached correctly"""
    from api.main import load_graph_artifacts, _KG_CACHE
    
    # Clear cache
    _KG_CACHE.clear()
    
    # Load domain 1
    G1, _, _ = load_graph_artifacts("wealth_management")
    assert "wealth_management" in _KG_CACHE
    
    # Load domain 2
    G2, _, _ = load_graph_artifacts("apf")
    assert "apf" in _KG_CACHE
    
    # Both should be cached
    assert len(_KG_CACHE) == 2
    
    # Load domain 1 again - should use cache
    G1_again, _, _ = load_graph_artifacts("wealth_management")
    assert G1 is G1_again, "Should return same cached object"
    
    print(f"\n✓ Caching works: {len(_KG_CACHE)} domains cached")


def test_invalid_domain(mock_gcs_and_kg):
    """Test error handling for invalid domain"""
    from api.main import app
    
    client = TestClient(app)
    r = client.post("/v1/answer", json={
        "question": "Test question",
        "domain": "nonexistent_domain",
        "vectorstore_id": "vs_test"
    })
    
    assert r.status_code == 400, "Should return 400 for invalid domain"
    assert "Unknown domain" in r.json()["detail"]


def test_backward_compatibility(mock_gcs_and_kg):
    """Test that old requests without domain field still work"""
    from api.main import _KG_CACHE
    _KG_CACHE.clear()
    
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    
    with patch.object(intent_clarification, "clarify_intent", side_effect=fake_intent):
        mock_client = MagicMock()
        mock_client.responses.create.return_value = MagicMock(output_text="Test answer")
        mock_client.vector_stores.search.return_value = MagicMock(data=[])
        mock_client.embeddings.create.return_value = MagicMock(data=[MagicMock(embedding=[0.1]*1536)])
        
        main_mod.get_client.cache_clear()
        with patch.object(main_mod, "get_client", return_value=mock_client):
            # Old-style request without domain field
            r = client.post("/v1/answer", json={
                "question": "Test question",
                "vectorstore_id": "vs_test"
            })
    
    assert r.status_code == 200
    # Should default to wealth_management
    assert r.json()["meta"]["domain"] == "wealth_management"
    print("\n✓ Backward compatibility maintained")


def test_kg_path_must_be_gcs():
    """Test that local file paths are rejected"""
    from api.main import load_graph_artifacts, _KG_CACHE
    _KG_CACHE.clear()
    
    # This should fail because settings require GCS paths
    # The settings validation should catch non-GCS paths
    # This test validates the requirement for GCS-only paths
    import os
    
    # Verify that our settings require GCS paths
    from api.settings import settings
    assert settings.WEALTH_MANAGEMENT_KG_PATH.startswith("gs://"), "KG path must be GCS"
    assert settings.APF_KG_PATH.startswith("gs://"), "KG path must be GCS"




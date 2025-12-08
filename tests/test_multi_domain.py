"""
Tests for multi-domain functionality
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")


def test_list_domains():
    """Test that /domains endpoint lists all configured domains"""
    from api.main import app
    
    client = TestClient(app)
    r = client.get("/domains")
    
    assert r.status_code == 200
    data = r.json()
    assert "domains" in data
    assert len(data["domains"]) >= 2, "Should have at least 2 domains"
    
    # Verify wealth_management domain
    wm_domain = next((d for d in data["domains"] if d["domain_id"] == "wealth_management"), None)
    assert wm_domain is not None
    assert wm_domain["kg_loaded"] is True
    assert wm_domain["kg_nodes"] == 938
    assert wm_domain["kg_edges"] == 1639
    
    # Verify apf domain
    apf_domain = next((d for d in data["domains"] if d["domain_id"] == "apf"), None)
    assert apf_domain is not None
    assert apf_domain["kg_loaded"] is True
    assert apf_domain["kg_nodes"] == 253
    assert apf_domain["kg_edges"] == 61
    
    print(f"\n✓ Found {len(data['domains'])} domains")


def test_health_shows_all_domains():
    """Test that /health shows status for all domains"""
    from api.main import app
    
    client = TestClient(app)
    r = client.get("/health")
    
    assert r.status_code == 200
    data = r.json()
    assert "domains" in data
    assert "wealth_management" in data["domains"]
    assert "apf" in data["domains"]
    
    # Both should be loaded
    assert data["domains"]["wealth_management"]["loaded"] is True
    assert data["domains"]["apf"]["loaded"] is True


def test_query_wealth_management_domain():
    """Test querying the wealth_management domain"""
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent to avoid hitting real OpenAI
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    import agents.ekg_agent as agent_mod
    from unittest.mock import patch, MagicMock
    
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
    assert data["meta"]["vectorstore_id"] == "vs_6910a0f29b548191befd180730d968ee"


def test_query_apf_domain():
    """Test querying the APF domain"""
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    from unittest.mock import patch, MagicMock
    
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
    assert data["meta"]["vectorstore_id"] == "vs_6910a0f29b548191befd180730d968ee"


def test_domain_independence():
    """Test that domains are truly independent"""
    from api.main import load_graph_artifacts
    
    # Load both domains
    G_wm, by_id_wm, idx_wm = load_graph_artifacts("wealth_management")
    G_apf, by_id_apf, idx_apf = load_graph_artifacts("apf")
    
    # Verify they are different
    assert G_wm is not G_apf, "Graphs should be different objects"
    assert by_id_wm is not by_id_apf, "Indexes should be different objects"
    assert idx_wm is not idx_apf, "Name indexes should be different objects"
    
    # Verify sizes are different
    assert G_wm.number_of_nodes() == 938
    assert G_apf.number_of_nodes() == 253
    assert G_wm.number_of_nodes() != G_apf.number_of_nodes()
    
    print(f"\n✓ Domains are independent:")
    print(f"  wealth_management: {G_wm.number_of_nodes()} nodes")
    print(f"  apf: {G_apf.number_of_nodes()} nodes")


def test_domain_caching():
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


def test_invalid_domain():
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


def test_backward_compatibility():
    """Test that old requests without domain field still work"""
    from api.main import app
    from agents.tools import intent_clarification
    
    client = TestClient(app)
    
    # Mock intent
    def fake_intent(_q: str):
        return intent_clarification.Intent(route="vector", hops=1, top_k=6)
    
    import api.main as main_mod
    from unittest.mock import patch, MagicMock
    
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




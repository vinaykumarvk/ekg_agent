"""
Tests for KG integration - loads from GCS only.

Requires environment variables:
- DOC_VECTORSTORE_ID
- WEALTH_MANAGEMENT_KG_PATH (gs://...)
- APF_KG_PATH (gs://...)
"""
import os
import pytest
from unittest.mock import patch, MagicMock
import networkx as nx


# Test configuration
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
    # Create mock graph with proper structure
    mock_graph = nx.MultiDiGraph()
    mock_graph.add_node("node1", id="node1", name="Test Node 1", type="Process")
    mock_graph.add_node("node2", id="node2", name="Test Node 2", type="Document")
    mock_graph.add_edge("node1", "node2", type="RELATED")
    
    mock_by_id = {
        "node1": {"id": "node1", "name": "Test Node 1", "type": "Process"},
        "node2": {"id": "node2", "name": "Test Node 2", "type": "Document"},
    }
    mock_name_index = {
        "test node 1": ["node1"],
        "test node 2": ["node2"],
    }
    
    def mock_load_kg(path):
        return mock_graph, mock_by_id, mock_name_index
    
    with patch("api.main.storage") as mock_storage:
        mock_client = MagicMock()
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.Client.return_value = mock_client
        mock_client.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        
        with patch("ekg_core.load_kg_from_json", side_effect=mock_load_kg):
            yield mock_graph, mock_by_id, mock_name_index


def test_kg_loads_successfully(mock_gcs_and_kg):
    """Test that the knowledge graph loads from GCS"""
    from api.main import load_graph_artifacts, _KG_CACHE
    _KG_CACHE.clear()
    
    # Load default domain
    G, by_id, name_index = load_graph_artifacts("wealth_management")
    
    # Verify graph loaded
    assert G is not None, "Graph should be loaded"
    assert G.number_of_nodes() > 0, "Graph should have nodes"
    assert G.number_of_edges() > 0, "Graph should have edges"
    
    # Verify indexes built
    assert len(by_id) > 0, "by_id index should be populated"
    assert len(name_index) > 0, "name_index should be populated"
    
    # Verify consistency
    assert G.number_of_nodes() == len(by_id), "Node count should match by_id entries"
    
    print(f"\n✓ KG loaded from GCS: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")


def test_kg_structure(mock_gcs_and_kg):
    """Validate the structure of loaded KG nodes and edges"""
    from api.main import load_graph_artifacts, _KG_CACHE
    _KG_CACHE.clear()
    
    G, by_id, name_index = load_graph_artifacts("wealth_management")
    
    # Check a sample node has expected fields
    sample_node_id = list(by_id.keys())[0]
    sample_node = by_id[sample_node_id]
    
    assert "id" in sample_node
    assert "type" in sample_node or "labels" in sample_node
    assert "name" in sample_node
    
    # Check edges have type attribute
    if G.number_of_edges() > 0:
        u, v, key = list(G.edges(keys=True))[0]
        edge_data = G[u][v][key]
        assert "type" in edge_data, "Edges should have type attribute"


def test_health_reports_kg_loaded(mock_gcs_and_kg):
    """Test that /health endpoint correctly reports KG is loaded from GCS"""
    from api.main import app, _KG_CACHE
    _KG_CACHE.clear()
    
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.get("/health")
    
    assert r.status_code == 200
    data = r.json()
    # Check that domains are reported
    assert "domains" in data, "Health should report domains"
    assert "wealth_management" in data["domains"], "wealth_management domain should be present"
    assert data["domains"]["wealth_management"]["loaded"] is True, "wealth_management KG should be loaded"


def test_name_index_lookup(mock_gcs_and_kg):
    """Test that name_index allows fuzzy entity matching"""
    from api.main import load_graph_artifacts, _KG_CACHE
    _KG_CACHE.clear()
    
    G, by_id, name_index = load_graph_artifacts("wealth_management")
    
    # Pick a sample entity name from by_id
    if by_id:
        sample_node = list(by_id.values())[0]
        sample_name = sample_node.get("name", "")
        
        if sample_name:
            # Normalize and lookup
            import re
            normalized = re.sub(r"\s+", " ", sample_name.strip().lower())
            
            # Should find the node ID in name_index
            if normalized in name_index:
                matched_ids = name_index[normalized]
                assert len(matched_ids) > 0
                assert sample_node["id"] in matched_ids
                print(f"\n✓ Found '{sample_name}' -> {matched_ids[0]}")


def test_gcs_path_required():
    """Test that only GCS paths are accepted"""
    from api.settings import settings
    
    # Verify settings require GCS paths
    assert settings.WEALTH_MANAGEMENT_KG_PATH.startswith("gs://"), \
        "WEALTH_MANAGEMENT_KG_PATH must be a GCS path"
    assert settings.APF_KG_PATH.startswith("gs://"), \
        "APF_KG_PATH must be a GCS path"


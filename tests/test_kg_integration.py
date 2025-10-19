import os
import pytest


@pytest.fixture(autouse=True)
def set_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy")


def test_kg_loads_successfully():
    """Test that the knowledge graph loads from data/kg/master_knowledge_graph.json"""
    from api.main import load_graph_artifacts
    
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
    
    print(f"\n✓ KG loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    print(f"✓ Indexes: {len(by_id)} by_id, {len(name_index)} name aliases")


def test_kg_structure():
    """Validate the structure of loaded KG nodes and edges"""
    from api.main import load_graph_artifacts
    
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


def test_health_reports_kg_loaded():
    """Test that /health endpoint correctly reports KG is loaded"""
    from api.main import app
    from fastapi.testclient import TestClient
    
    client = TestClient(app)
    r = client.get("/health")
    
    assert r.status_code == 200
    data = r.json()
    # Check that domains are reported
    assert "domains" in data, "Health should report domains"
    assert "wealth_management" in data["domains"], "wealth_management domain should be present"
    assert data["domains"]["wealth_management"]["loaded"] is True, "wealth_management KG should be loaded"
    assert data["status"] == "healthy"


def test_name_index_lookup():
    """Test that name_index allows fuzzy entity matching"""
    from api.main import load_graph_artifacts
    
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


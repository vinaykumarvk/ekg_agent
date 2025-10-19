#!/usr/bin/env python3
"""
Verification script to check if the EKG Agent multi-domain system is ready
"""
import sys

def main():
    print("="*70)
    print("EKG AGENT READINESS VERIFICATION")
    print("="*70)
    
    tests_passed = 0
    tests_total = 0
    
    # Test 1: API imports
    tests_total += 1
    try:
        from api.main import app, load_graph_artifacts
        from api.domains import list_domains, get_domain
        print("\n✓ Test 1: API imports successfully")
        tests_passed += 1
    except Exception as e:
        print(f"\n✗ Test 1 FAILED: API imports - {e}")
    
    # Test 2: Domain registry
    tests_total += 1
    try:
        from api.domains import list_domains
        domains = list_domains()
        assert len(domains) >= 2, "Should have at least 2 domains"
        domain_ids = [d.domain_id for d in domains]
        assert "wealth_management" in domain_ids
        assert "apf" in domain_ids
        print(f"✓ Test 2: Domain registry works - {len(domains)} domains found")
        print(f"          Domains: {domain_ids}")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 2 FAILED: Domain registry - {e}")
    
    # Test 3: Load wealth_management KG
    tests_total += 1
    try:
        from api.main import load_graph_artifacts
        G, by_id, name_index = load_graph_artifacts("wealth_management")
        assert G is not None, "Graph should not be None"
        assert G.number_of_nodes() == 938, f"Expected 938 nodes, got {G.number_of_nodes()}"
        assert G.number_of_edges() == 1639, f"Expected 1639 edges, got {G.number_of_edges()}"
        print(f"✓ Test 3: wealth_management KG loads correctly")
        print(f"          {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 3 FAILED: wealth_management KG - {e}")
    
    # Test 4: Load APF KG
    tests_total += 1
    try:
        from api.main import load_graph_artifacts
        G, by_id, name_index = load_graph_artifacts("apf")
        assert G is not None, "Graph should not be None"
        assert G.number_of_nodes() == 253, f"Expected 253 nodes, got {G.number_of_nodes()}"
        assert G.number_of_edges() == 61, f"Expected 61 edges, got {G.number_of_edges()}"
        print(f"✓ Test 4: APF KG loads correctly")
        print(f"          {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 4 FAILED: APF KG - {e}")
    
    # Test 5: Domain independence
    tests_total += 1
    try:
        from api.main import load_graph_artifacts
        G1, by_id1, idx1 = load_graph_artifacts("wealth_management")
        G2, by_id2, idx2 = load_graph_artifacts("apf")
        assert G1 is not G2, "Graphs should be different objects"
        assert by_id1 is not by_id2, "Indexes should be different"
        assert G1.number_of_nodes() != G2.number_of_nodes(), "Graphs should have different sizes"
        print(f"✓ Test 5: Domains are independent")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 5 FAILED: Domain independence - {e}")
    
    # Test 6: Domain caching
    tests_total += 1
    try:
        from api.main import load_graph_artifacts, _KG_CACHE
        _KG_CACHE.clear()
        G1, _, _ = load_graph_artifacts("wealth_management")
        assert "wealth_management" in _KG_CACHE
        G1_again, _, _ = load_graph_artifacts("wealth_management")
        assert G1 is G1_again, "Should return cached object"
        print(f"✓ Test 6: Domain caching works")
        print(f"          Cache size: {len(_KG_CACHE)} domains")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 6 FAILED: Domain caching - {e}")
    
    # Test 7: Invalid domain handling
    tests_total += 1
    try:
        from api.domains import get_domain
        try:
            get_domain("nonexistent")
            print("✗ Test 7 FAILED: Should raise ValueError for invalid domain")
        except ValueError as e:
            if "Unknown domain" in str(e):
                print("✓ Test 7: Invalid domain handling works")
                tests_passed += 1
            else:
                print(f"✗ Test 7 FAILED: Wrong error message - {e}")
    except Exception as e:
        print(f"✗ Test 7 FAILED: Invalid domain handling - {e}")
    
    # Test 8: Core functions available
    tests_total += 1
    try:
        from ekg_core import (
            hybrid_answer, answer_with_kg, load_kg_from_json,
            kg_anchors, expand_queries_from_kg, retrieve_parallel,
            mmr_merge, rerank_chunks_by_relevance, expand_chunk_context,
            build_grounded_messages, build_citation_map, export_markdown
        )
        print("✓ Test 8: All core functions available")
        tests_passed += 1
    except Exception as e:
        print(f"✗ Test 8 FAILED: Core functions - {e}")
    
    # Summary
    print("\n" + "="*70)
    print(f"RESULTS: {tests_passed}/{tests_total} tests passed")
    print("="*70)
    
    if tests_passed == tests_total:
        print("\n✅ ALL TESTS PASSED - System is ready for deployment!")
        return 0
    else:
        print(f"\n⚠️  {tests_total - tests_passed} tests failed - Please review issues above")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(1)


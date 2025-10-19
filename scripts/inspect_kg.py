#!/usr/bin/env python3
"""
Inspect the loaded knowledge graph - useful for debugging and exploration.
Usage: python scripts/inspect_kg.py
"""
import os
import sys

# Add parent dir to path so we can import from api
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["OPENAI_API_KEY"] = "dummy"  # Required for settings validation

from api.main import load_graph_artifacts
from collections import Counter


def main():
    print("Loading knowledge graph...")
    G, by_id, name_index = load_graph_artifacts()
    
    if not G or G.number_of_nodes() == 0:
        print("❌ No graph loaded!")
        return
    
    print(f"\n{'='*70}")
    print(f"KNOWLEDGE GRAPH SUMMARY")
    print(f"{'='*70}")
    
    # Basic stats
    print(f"\n📊 Basic Stats:")
    print(f"  Nodes:        {G.number_of_nodes():,}")
    print(f"  Edges:        {G.number_of_edges():,}")
    print(f"  Name aliases: {len(name_index):,}")
    
    # Node types
    print(f"\n🏷️  Node Types:")
    node_types = Counter()
    for nid, data in by_id.items():
        ntype = data.get("type", "Unknown")
        node_types[ntype] += 1
    
    for ntype, count in node_types.most_common(10):
        print(f"  {ntype:20} {count:5,}")
    
    # Edge types
    print(f"\n🔗 Edge Types:")
    edge_types = Counter()
    for u, v, key, data in G.edges(keys=True, data=True):
        etype = data.get("type", "RELATED")
        edge_types[etype] += 1
    
    for etype, count in edge_types.most_common(10):
        print(f"  {etype:30} {count:5,}")
    
    # Sample nodes
    print(f"\n📋 Sample Nodes (first 5):")
    for i, (nid, data) in enumerate(list(by_id.items())[:5], 1):
        name = data.get("name", nid)
        ntype = data.get("type", "Unknown")
        aliases = data.get("aliases", [])
        alias_count = len([a for a in aliases if a])
        print(f"  {i}. [{ntype}] {name}")
        print(f"     ID: {nid}")
        if alias_count > 0:
            print(f"     Aliases: {alias_count}")
    
    # Node connectivity
    print(f"\n🌐 Connectivity:")
    degrees = [G.degree(n) for n in G.nodes()]
    if degrees:
        print(f"  Avg degree:  {sum(degrees)/len(degrees):.1f}")
        print(f"  Max degree:  {max(degrees)}")
        print(f"  Min degree:  {min(degrees)}")
    
    # Most connected nodes
    print(f"\n⭐ Most Connected Nodes:")
    top_nodes = sorted(G.nodes(), key=lambda n: G.degree(n), reverse=True)[:5]
    for i, nid in enumerate(top_nodes, 1):
        name = by_id.get(nid, {}).get("name", nid)
        degree = G.degree(nid)
        print(f"  {i}. {name} (degree: {degree})")
    
    print(f"\n{'='*70}")
    print("✓ Inspection complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()



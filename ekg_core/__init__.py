# ekg_core/__init__.py

# V2 Workflow (recommended - superior results)
from .v2_workflow import (
    v2_hybrid_answer,
    get_relevant_nodes,
    map_node_names_to_ids,
    get_relevant_subgraph,
    build_kg_guided_queries,
    generate_kg_text,
    get_response_with_file_search,
)

# Legacy V1 functions (kept for compatibility)
from .core import (
    hybrid_answer,
    answer_with_kg,
    kg_anchors,
    expand_queries_from_kg,
    retrieve_parallel,
    mmr_merge,
    rerank_chunks_by_relevance,
    expand_chunk_context,
    build_grounded_messages,
    build_citation_map,
    export_markdown,
    load_kg_from_json,
    get_preset,
)

__all__ = [
    # V2 Workflow (recommended)
    "v2_hybrid_answer",
    "get_relevant_nodes",
    "map_node_names_to_ids", 
    "get_relevant_subgraph",
    "build_kg_guided_queries",
    "generate_kg_text",
    "get_response_with_file_search",
    # Legacy V1
    "hybrid_answer", "answer_with_kg",
    "kg_anchors", "expand_queries_from_kg",
    "retrieve_parallel", "mmr_merge",
    "rerank_chunks_by_relevance", "expand_chunk_context",
    "build_grounded_messages", "build_citation_map",
    "export_markdown", "load_kg_from_json",
    "get_preset",
]

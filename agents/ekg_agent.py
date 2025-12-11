"""
EKG Agent - V2 Workflow Implementation

This agent uses the V2 workflow which provides superior results through:
1. Semantic KG node discovery via file_search on KG vector store
2. Rich KG-guided query expansion
3. Dynamic retrieval via file_search on document vector store
"""

from typing import Any, Dict, Optional
import logging
import os

from agents.tools.intent_clarification import clarify_intent
from agents.tools.answer_formatting import to_markdown_with_citations

# V2 Workflow - the superior approach
from ekg_core.v2_workflow import v2_hybrid_answer

log = logging.getLogger("ekg_agent")


class EKGAgent:
    """
    EKG Agent using V2 workflow for superior answer quality.
    
    V2 workflow advantages over V1:
    - Semantic KG node discovery (vs fuzzy string matching)
    - Stepback + expanded questions from GPT
    - Rich KG-guided queries including relationships
    - file_search tool for dynamic retrieval
    """
    
    def __init__(
        self, 
        *, 
        client: Any, 
        vs_id: str,  # Document vector store ID
        kg_vs_id: str = None,  # KG vector store ID (required for V2)
        G: Any, 
        by_id: Dict, 
        name_index: Dict, 
        preset_params: Optional[dict] = None
    ):
        self.client = client
        self.doc_vs_id = vs_id  # Document vector store
        self.kg_vs_id = kg_vs_id or os.getenv("KG_VECTOR_STORE_ID")  # KG vector store
        self.G = G
        self.by_id = by_id
        self.name_index = name_index
        self.preset_params = preset_params or {}
        
        # Validate KG vector store ID
        if not self.kg_vs_id:
            log.warning("KG_VECTOR_STORE_ID not provided - V2 semantic discovery will be limited")

    def answer(self, question: str) -> Dict:
        """
        Generate answer using V2 workflow.
        
        V2 Workflow Steps:
        1. Semantic KG node discovery (file_search on KG vector store)
        2. Map node names to graph IDs
        3. Graph expansion from seed nodes
        4. Build KG-guided queries (stepback, expanded, entity, relationship)
        5. Generate KG text context
        6. Final answer with file_search on document vector store
        """
        log.info(f"EKG Agent V2: Processing question: {question[:80]}...")
        
        # Get intent for logging (V2 always uses hybrid approach)
        intent = clarify_intent(question)
        log.info(f"Intent classification: route={intent.route}, hops={intent.hops}")
        
        # Override hops from intent if not in preset_params
        params = self.preset_params.copy()
        if "hops" not in params:
            params["hops"] = intent.hops
        
        # Use V2 hybrid answer pipeline
        try:
            final = v2_hybrid_answer(
                question=question,
                G=self.G,
                by_id=self.by_id,
                name_index=self.name_index,
                client=self.client,
                kg_vector_store_id=self.kg_vs_id,
                doc_vector_store_id=self.doc_vs_id,
                preset_params=params
            )
        except Exception as e:
            log.error(f"V2 hybrid answer failed: {e}", exc_info=True)
            # Return error response
            return {
                "answer": f"Error generating answer: {str(e)}",
                "markdown": f"# Error\n\nFailed to generate answer: {str(e)}",
                "meta": {
                    "error": str(e),
                    "v2_workflow": True
                }
            }
        
        # Format markdown with citations if needed
        if final.get("curated_chunks"):
            md, path = to_markdown_with_citations(final, question, export=True)
            final["markdown"] = md
            final["export_path"] = path
        
        # Add V2 debug info to meta
        if "meta" not in final:
            final["meta"] = {}
        final["meta"]["intent_route"] = intent.route
        final["meta"]["intent_hops"] = intent.hops
        
        log.info(f"EKG Agent V2: Answer generated successfully")
        log.info(f"  - V2 nodes: {final['meta'].get('expanded_nodes', 0)}")
        log.info(f"  - V2 edges: {final['meta'].get('expanded_edges', 0)}")
        log.info(f"  - V2 queries: {len(final['meta'].get('kg_guided_queries', []))}")
        
        return final

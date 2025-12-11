from typing import Any, Dict, Optional
import logging
from agents.tools.intent_clarification import clarify_intent
from agents.tools.kg_extraction import run_kg_answer
from agents.tools.vector_extraction import run_vector_answer
from agents.tools.answer_formatting import to_markdown_with_citations
from ekg_core import hybrid_answer  # ← call your tested hybrid

log = logging.getLogger("ekg_agent")

class EKGAgent:
    def __init__(self, *, client: Any, vs_id: str, G: Any, by_id: Dict, name_index: Dict, preset_params: Optional[dict] = None):
        self.client, self.vs_id = client, vs_id
        self.G, self.by_id, self.name_index = G, by_id, name_index
        self.preset_params = preset_params

    def _add_kg_debug_info(self, final: Dict, kg_res: Dict, intent_route: str) -> Dict:
        """Add KG debug statistics to the response metadata"""
        kg_meta = kg_res.get("meta", {})
        
        # Extract KG statistics
        kg_debug = {
            "intent_route": intent_route,
            "suggested_entities": kg_meta.get("suggested_entities", []),
            "suggested_count": len(kg_meta.get("suggested_entities", [])),
            "seed_ids": kg_meta.get("seed_ids", []),
            "seed_count": len(kg_meta.get("seed_ids", [])),
            "expanded_nodes": kg_meta.get("expanded_nodes", 0),
            "expanded_edges": kg_meta.get("expanded_edges", 0),
            "resolved_entities_count": len(kg_res.get("resolved_entities", [])),
            "supporting_edges_count": len(kg_res.get("supporting_edges", [])),
        }
        
        # Log KG usage for debugging
        log.info(f"KG Debug: route={intent_route}, suggested={kg_debug['suggested_count']}, "
                 f"seeds={kg_debug['seed_count']}, expanded_nodes={kg_debug['expanded_nodes']}, "
                 f"expanded_edges={kg_debug['expanded_edges']}")
        
        if kg_debug['suggested_count'] > 0:
            log.info(f"KG Suggested entities: {kg_debug['suggested_entities'][:10]}")
        
        # Add to final response
        if "meta" not in final:
            final["meta"] = {}
        final["meta"]["kg_debug"] = kg_debug
        
        return final

    def answer(self, question: str) -> Dict:
        intent = clarify_intent(question)
        log.info(f"Intent classification: route={intent.route}, hops={intent.hops}")

        if intent.route == "kg":
            kg_res = run_kg_answer(question, G=self.G, by_id=self.by_id, name_index=self.name_index,
                                   llm_client=self.client, hops=intent.hops, preset_params=self.preset_params)
            final = hybrid_answer(q=question, kg_result=kg_res, by_id=self.by_id,
                                  client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
            final = self._add_kg_debug_info(final, kg_res, intent.route)
            md, path = to_markdown_with_citations(final, question, export=True)
            final["markdown"], final["export_path"] = md, path
            return final

        if intent.route == "vector":
            final = run_vector_answer(question, client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
            md, path = to_markdown_with_citations(final, question, export=True)
            final["markdown"], final["export_path"] = md, path
            # Add minimal KG debug for vector-only route
            if "meta" not in final:
                final["meta"] = {}
            final["meta"]["kg_debug"] = {"intent_route": "vector", "kg_used": False}
            return final

        # hybrid default
        kg_res = run_kg_answer(question, G=self.G, by_id=self.by_id, name_index=self.name_index,
                               llm_client=self.client, hops=intent.hops, preset_params=self.preset_params)
        final = hybrid_answer(q=question, kg_result=kg_res, by_id=self.by_id,
                              client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
        final = self._add_kg_debug_info(final, kg_res, "hybrid")
        md, path = to_markdown_with_citations(final, question, export=True)
        final["markdown"], final["export_path"] = md, path
        return final

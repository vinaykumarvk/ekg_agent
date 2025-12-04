from typing import Any, Dict, Optional
from agents.tools.intent_clarification import clarify_intent
from agents.tools.kg_extraction import run_kg_answer
from agents.tools.vector_extraction import run_vector_answer
from agents.tools.answer_formatting import to_markdown_with_citations
from agents.tools.structured_answer import run_structured_answer
from ekg_core import hybrid_answer  # ← call your tested hybrid

class EKGAgent:
    def __init__(self, *, client: Any, vs_id: str, G: Any, by_id: Dict, name_index: Dict, preset_params: Optional[dict] = None):
        self.client, self.vs_id = client, vs_id
        self.G, self.by_id, self.name_index = G, by_id, name_index
        self.preset_params = preset_params

    def answer_structured(self, question_payload: Dict[str, Any]) -> Dict:
        """Handle structured input with custom system prompt"""
        return run_structured_answer(
            question_payload,
            client=self.client,
            vs_id=self.vs_id,
            preset_params=self.preset_params
        )

    def answer(self, question: str) -> Dict:
        intent = clarify_intent(question)

        if intent.route == "kg":
            kg_res = run_kg_answer(question, G=self.G, by_id=self.by_id, name_index=self.name_index,
                                   llm_client=self.client, hops=intent.hops, preset_params=self.preset_params)
            final = hybrid_answer(q=question, kg_result=kg_res, by_id=self.by_id,
                                  client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
            md, path = to_markdown_with_citations(final, question, export=True)
            final["markdown"], final["export_path"] = md, path
            return final

        if intent.route == "vector":
            final = run_vector_answer(question, client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
            md, path = to_markdown_with_citations(final, question, export=True)
            final["markdown"], final["export_path"] = md, path
            return final

        # hybrid default
        kg_res = run_kg_answer(question, G=self.G, by_id=self.by_id, name_index=self.name_index,
                               llm_client=self.client, hops=intent.hops, preset_params=self.preset_params)
        final = hybrid_answer(q=question, kg_result=kg_res, by_id=self.by_id,
                              client=self.client, vs_id=self.vs_id, preset_params=self.preset_params)
        md, path = to_markdown_with_citations(final, question, export=True)
        final["markdown"], final["export_path"] = md, path
        return final

from typing import Any, Dict, Optional
from agents.tools.answer_formatting import to_markdown_with_citations
from ekg_core import answer_with_kg_and_vector

class EKGAgent:
    def __init__(self, *, client: Any, vs_id: str, G: Any, by_id: Dict, name_index: Dict, preset_params: Optional[dict] = None, kg_vector_store_id: Optional[str] = None):
        self.client, self.vs_id = client, vs_id
        self.G, self.by_id, self.name_index = G, by_id, name_index
        self.preset_params = preset_params
        # Use kg_vector_store_id if provided, otherwise use vs_id for both
        self.kg_vector_store_id = kg_vector_store_id or vs_id

    def answer(self, question: str) -> Dict:
        """
        Answer a question using the new workflow with file_search tool.
        All queries use KG + Vector workflow with file_search.
        """
        final = answer_with_kg_and_vector(
            q=question,
            G=self.G,
            by_id=self.by_id,
            name_index=self.name_index,
            client=self.client,
            kg_vector_store_id=self.kg_vector_store_id,
            doc_vector_store_id=self.vs_id,
            preset_params=self.preset_params
        )
        md, path = to_markdown_with_citations(final, question, export=True)
        final["markdown"], final["export_path"] = md, path
        return final

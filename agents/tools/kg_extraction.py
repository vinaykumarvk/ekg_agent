from typing import Any, Dict
from ekg_core import answer_with_kg

def run_kg_answer(
    q: str, *, G: Any, by_id: Dict[str, Any], name_index: Dict[str, list],
    llm_client: Any, hops: int | None = None, k_suggest: int | None = None,
    k_candidates: int | None = None, preset_params: dict | None = None,
) -> dict:
    return answer_with_kg(
        q=q, G=G, by_id=by_id, name_index=name_index, llm_client=llm_client,
        hops=hops or 1, k_suggest=k_suggest or 20, k_candidates=k_candidates or 25,
        preset_params=preset_params,
    )

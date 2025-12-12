from typing import Any, Optional
from ekg_core import (
    kg_anchors, expand_queries_from_kg, retrieve_parallel, mmr_merge,
    rerank_chunks_by_relevance, expand_chunk_context, build_grounded_messages,
    build_citation_map,
)

def run_vector_answer(
    q: str, *, client: Any, vs_id: str, preset_params: Optional[dict] = None,
    kg_result: Optional[dict] = None, max_chunks: int = 10, k_each: int = 3,
    lambda_div: float = 0.4, model: Optional[str] = None
) -> dict:
    if preset_params:
        max_chunks = preset_params.get("max_chunks", max_chunks)
        k_each = preset_params.get("k_each", k_each)
        lambda_div = preset_params.get("lambda_div", lambda_div)
        model = preset_params.get("model", model)
        mode = preset_params.get("_mode", "balanced")
        max_subqueries = preset_params.get("max_subqueries", 8)
        retrieval_workers = preset_params.get("retrieval_workers", 6)
        min_chunks = preset_params.get("min_chunks", max(6, max_chunks//2))
    else:
        mode, model = "balanced", (model or "gpt-4o")
        max_subqueries = 8
        retrieval_workers = 6
        min_chunks = max(6, max_chunks//2)

    if kg_result:
        ents, _ = kg_anchors(
            kg_result.get("resolved_entities"),
            kg_result.get("supporting_edges"),
            kg_result.get("by_id", {})
        )
        kg_queries = expand_queries_from_kg(
            q, ents, kg_result.get("supporting_edges"), k_max=max_subqueries
        )
    else:
        kg_queries = []

    seed_queries = [q, f"Explain: {q}", f"Summarize: {q}"]
    subqs = []
    seen = set()
    for candidate in seed_queries + kg_queries:
        if not candidate:
            continue
        key = candidate.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        subqs.append(candidate)
        if len(subqs) >= max_subqueries:
            break

    if not subqs:
        subqs = [q]

    pool = retrieve_parallel(client, vs_id, subqs, k_each=k_each, max_workers=retrieval_workers)
    curated = mmr_merge(pool, k_final=max_chunks*5, lambda_div=lambda_div)
    curated = rerank_chunks_by_relevance(
        client, q, curated, top_k=max_chunks, min_chunks=min_chunks
    )
    curated = expand_chunk_context(curated)

    system_msg, user_msg = build_grounded_messages(question=q, compact_nodes=[], compact_edges=[],
                                                   node_context={}, chunks=curated, mode=mode, preset_params=preset_params)
    response_mode = preset_params.get("response_mode", "sync") if preset_params else "sync"
    resp   = client.responses.create(model=model, input=[{"role":"system","content":system_msg},{"role":"user","content":user_msg}], response_mode=response_mode)
    answer = getattr(resp, "output_text", None) or getattr(resp, "output_texts", [""])[0]
    f2i, i2s = build_citation_map(curated)

    return {"answer": answer, "curated_chunks": curated,
            "citation_index_to_source": i2s, "files_to_citation_indices": f2i,
            "model_used": model}

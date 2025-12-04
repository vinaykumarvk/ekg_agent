"""
Structured answer handling for complex workflows with custom system prompts
"""
from typing import Any, Optional, Dict
import json
from ekg_core import (
    retrieve_parallel, mmr_merge, rerank_chunks_by_relevance,
    expand_chunk_context, build_grounded_messages, build_citation_map
)


def run_structured_answer(
    question_payload: Dict[str, Any],
    *,
    client: Any,
    vs_id: str,
    preset_params: Optional[dict] = None,
    max_chunks: int = 20,
    k_each: int = 5
) -> dict:
    """
    Handle structured input with custom system prompt and structured context.
    
    Args:
        question_payload: Dict with keys:
            - system_prompt: Custom system prompt string
            - requirement: Requirement string
            - bank_profile: Bank profile dict
            - market_subrequirements: List of subrequirement dicts
        client: LLM client
        vs_id: Vector store ID
        preset_params: Preset parameters
        max_chunks: Maximum chunks to retrieve
        k_each: Chunks per query
    
    Returns:
        Dict with answer, chunks, citations, etc.
    """
    system_prompt = question_payload.get("system_prompt", "")
    requirement = question_payload.get("requirement", "")
    bank_profile = question_payload.get("bank_profile", {})
    market_subrequirements = question_payload.get("market_subrequirements", [])
    
    # Build queries from market subrequirements
    queries = []
    if market_subrequirements:
        for subreq in market_subrequirements:
            if isinstance(subreq, dict):
                title = subreq.get("title", "")
                description = subreq.get("description", "")
                priority = subreq.get("priority", "")
                
                # Build focused query for this subrequirement
                query_parts = []
                if title:
                    query_parts.append(title)
                if description:
                    # Use key parts of description
                    desc_words = description.split()[:10]  # First 10 words
                    query_parts.append(" ".join(desc_words))
                if requirement:
                    req_words = requirement.split()[:5]  # First 5 words
                    query_parts.append(" ".join(req_words))
                
                if query_parts:
                    queries.append(" ".join(query_parts))
    
    # Fallback: use requirement if no subrequirements
    if not queries and requirement:
        queries = [requirement]
    
    # Ensure we have at least one query
    if not queries:
        queries = ["internal capabilities documentation"]
    
    # Retrieve documents (this acts as file_search)
    pool = retrieve_parallel(client, vs_id, queries, k_each=k_each)
    
    # Curate chunks
    curated = mmr_merge(pool, k_final=max_chunks * 5, lambda_div=0.4)
    curated = rerank_chunks_by_relevance(
        client, requirement or queries[0], curated,
        top_k=max_chunks, min_chunks=max(6, max_chunks // 2)
    )
    curated = expand_chunk_context(curated)
    
    # Build structured context
    structured_context = {
        "requirement": requirement,
        "bank_profile": bank_profile,
        "market_subrequirements": market_subrequirements
    }
    
    # Build messages with custom system prompt
    system_msg, user_msg = build_grounded_messages(
        question=requirement or "Analyze internal capabilities",
        compact_nodes=[],
        compact_edges=[],
        node_context={},
        chunks=curated,
        mode="balanced",  # Use balanced mode for structured input
        preset_params=preset_params,
        custom_system_prompt=system_prompt,
        structured_context=structured_context
    )
    
    # Get model from preset_params
    model = preset_params.get("model", "gpt-4o") if preset_params else "gpt-4o"
    
    # Generate answer
    resp = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]
    )
    answer = getattr(resp, "output_text", None) or getattr(resp, "output_texts", [""])[0]
    
    # Parse JSON from answer if possible
    json_data = None
    try:
        # Try to extract JSON from markdown code blocks
        if "```json" in answer:
            json_start = answer.find("```json") + 7
            json_end = answer.find("```", json_start)
            json_str = answer[json_start:json_end].strip()
            json_data = json.loads(json_str)
        elif "```" in answer:
            json_start = answer.find("```") + 3
            json_end = answer.find("```", json_start)
            json_str = answer[json_start:json_end].strip()
            json_data = json.loads(json_str)
        else:
            # Try parsing the entire answer as JSON
            json_data = json.loads(answer.strip())
    except (json.JSONDecodeError, ValueError):
        # If JSON parsing fails, return raw answer
        pass
    
    # Build citation map
    f2i, i2s = build_citation_map(curated)
    
    return {
        "answer": answer,
        "json_data": json_data,  # Parsed JSON if available
        "curated_chunks": curated,
        "citation_index_to_source": i2s,
        "files_to_citation_indices": f2i,
        "model_used": model,
        "queries": queries
    }


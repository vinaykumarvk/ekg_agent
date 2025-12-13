# -*- coding: utf-8 -*-
"""
V2 Workflow - Replicating Colab kg_vector_response_v2.py logic exactly.

This module implements the superior V2 workflow:
1. Semantic KG node discovery via file_search on KG vector store
2. Map node names to graph IDs
3. Graph expansion from seed nodes
4. Build KG-guided queries (rich: stepback, expanded, entity, relationship)
5. Generate structured KG text context
6. Final answer with file_search on document vector store
"""

import json
import re
import logging
from collections import deque
from typing import Dict, Any, List, Optional
from datetime import datetime

log = logging.getLogger(__name__)

# =============================================================================
# V2 PROMPTS (Exact replica from kg_vector_response_v2.py)
# =============================================================================

FILE_SEARCH_MESSAGE = """
You are an internal wealth-management product knowledge assistant.

You have access to the following:
1. A structured set of business concepts, entities, and relationships derived from our internal knowledge graph:
<KG_CONTEXT>
{kg_text}
</KG_CONTEXT>

2. A document vector store containing detailed product, process, and journey information.

The user has provided several questions and hints that together express ONE underlying information need.
Treat ALL of the following as different perspectives of the same broader inquiry:

<USER_QUESTIONS>
{expanded_queries_str}
</USER_QUESTIONS>

------------------------------------------------------------
YOUR TASK
------------------------------------------------------------

1) **Understand the Unified Intent**
   Infer the single business problem or information objective these questions collectively express.
   Reformulate this as a clear, concise intent statement.

2) **Use the KG Context Internally**
   Use the entities and relationships in <KG_CONTEXT> ONLY for internal reasoning—
   NOT for display, NOT for enumeration, NOT for explanation.
   They exist only to guide your understanding of concepts and their interactions.

3) **Retrieve the Most Relevant Knowledge**
   Internally issue file_search queries into the document vector store by combining:
      • the unified intent
      • the expanded understanding of the topic
      • relevant concepts implied by the KG context
   Do NOT mention file_search, retrieval, vector stores, or any internal mechanisms in your final answer.

4) **Synthesize ONE Integrated Explanation**
   Using the retrieved content:
      • Produce a cohesive, structured narrative that directly answers the unified intent.
      • Merge overlapping points and remove redundancies.
      • Ensure the explanation is generic and platform-agnostic.
      • Cite every factual claim with inline markers like [1], [2] that map to retrieved sources.
      • Add a final "Sources" section listing each cited document (filename/title is enough).
      • Do NOT reference clients, banks, proprietary implementations, or example organizations.
      • Do NOT mention knowledge graphs, nodes, edges, triples, metadata, or relationships.
      • Do NOT start the answer with statements like "Below is an integrated view…",
        "The KG shows…", "From the knowledge graph…", or any similar framing.
        • Simply present the explanation directly and professionally, as if preparing internal
        product documentation or briefing an experienced BA.

5) **Final Output Format (Strict)**
Respond ONLY with the following JSON object:

{{
  "stepback_intent": "A clear statement of the unified intent.",
  "expanded_question": "A concise, enriched reformulation.",
  "business_entities": ["entity 1", "entity 2", "..."],
  "citations": [
    {{"id": "1", "source": "Document or file name"}},
    {{"id": "2", "source": "Document or file name"}}
  ],
  "answer": "A single integrated answer written in **proper, clean Markdown**, with headings, subheadings, bullet points, or numbered lists.\\n             Include inline citation markers [1], [2] next to each claim and end with a 'Sources' section that maps those markers to the provided citation objects.\\n             The answer must NOT include the KG, nodes, relationships, internal tools, or any meta-commentary."
}}

Notes:
- The **answer** field must contain fully valid Markdown **inside the JSON** (no backticks).
- Do NOT add any prose outside the JSON.
- Do NOT confirm the usage of KG or documents.
- Do NOT reference the prompt, instructions, or tools in the answer.
"""

STEPBACK_MESSAGE = """
You are a wealth-management product knowledge assistant.

You ALWAYS receive one user question, and you MUST analyse it without asking the user to repeat it.

You have access to a file_search tool connected to a KG vector store
containing natural-language descriptions of platform knowledge-graph nodes.

===========================================================
YOUR MANDATORY TASKS
===========================================================

For the given user question (provided in the `original_question` field below):

1) STEP-BACK INTENT
   Rewrite the question in a more generic, clarified formulation that captures
   the underlying business intent. No loss of meaning. No assumptions.

2) EXPANDED QUESTION
   Expand the question into a richer, more detailed version intended to improve
   retrieval from the KG. Keep it concise, business-focused, and not rhetorical.

3) EXTRACT BUSINESS ENTITIES
   Extract key BUSINESS entities mentioned or implied in the expanded question.
   Examples: workflows, screens, documents, validations, client data entities,
   approval processes, reports, regulatory aspects, system modules, etc.
   Output as a list of short canonical phrases.

4) RETRIEVE RELEVANT KG NODES
   - You MUST call the file_search tool.
   - Build your search query using a combination of:
        a) the expanded question
        b) the extracted entities (as keywords)
   - Retrieve up to 10 (not necessarily exactly 10) relevant KG nodes.
   - From each result, extract ONLY the KG node NAME (not description).

5) OUTPUT FORMAT (STRICT)
   You MUST output ONLY the following JSON object:

   {{
     "original_question": "...",
     "stepback_question": "...",
     "expanded_question": "...",
     "entities": ["...", "..."],
     "node_names": ["...", "..."]
   }}

   - All string fields may contain markdown formatting.
   - "entities" must be an array of strings.
   - "node_names" must be an array of strings. If no matches, return [].

===========================================================
STRICT RULES
===========================================================

- DO NOT ask the user to provide the question again.
- DO NOT output explanations, commentary, or extra text.
- DO NOT refuse unless the input is empty.
- DO NOT repeat tool call results; only extract node names.
- DO NOT invent node names; use only those returned by file_search.

===========================================================
INPUT TO PROCESS
===========================================================

original_question: {question}
"""

FORMATTING_MESSAGE = """
You are a senior editor specializing in transforming research reports into
clear, polished, publication-ready documents.

Your task is to refine the following research output:

<RAW_ANSWER>
{answer}
</RAW_ANSWER>

------------------------------------------------------------
INSTRUCTIONS
------------------------------------------------------------

1. **Improve Language & Clarity**
   - Rewrite the content to be clearer, sharper, and more professional.
   - Improve flow, transitions, and readability without changing factual meaning.
   - Remove repetition and tighten overly long phrasing.

2. **Improve Structure & Formatting**
   - Apply clean Markdown formatting.
   - Use headings, subheadings, numbered lists, and bullet points where helpful.
   - Ensure the document reads like a polished research brief or executive summary.

3. **Handle References Correctly**
   - Remove all inline references, markers, or citation tags.
   - Collect all references mentioned anywhere in the text.
   - Present them in a **single consolidated "References" section** at the end.
   - If a reference appears multiple times, list it only once.

4. **Preserve Meaning, Remove Noise**
   - Do NOT hallucinate any new facts.
   - Preserve technical accuracy, definitions, and logical structure.
   - Eliminate filler language or unnecessary qualifiers.

5. **Output Format**
   - Return ONLY the refined research report as a **Markdown document**.
   - No extra commentary, no explanation of changes.

"""

PROMPT_SET = {
    "concise": FILE_SEARCH_MESSAGE,
    "balanced": FILE_SEARCH_MESSAGE,
    "deep": FILE_SEARCH_MESSAGE,
    "stepback": STEPBACK_MESSAGE,
    "formatting": FORMATTING_MESSAGE,
}


# =============================================================================
# V2 HELPER FUNCTIONS
# =============================================================================

def _norm(s: str) -> str:
    """Normalize string for matching"""
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _dedup(seq, key=lambda x: x):
    """Deduplicate sequence while preserving order"""
    seen, out = set(), []
    for x in seq:
        k = key(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def parse_llm_json(text: str) -> Dict:
    """Parse JSON from LLM output, handling markdown fences"""
    cleaned_text = text.strip()
    if cleaned_text.startswith("```json"):
        cleaned_text = cleaned_text[len("```json"):].strip()
    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text[3:].strip()
    if cleaned_text.endswith("```"):
        cleaned_text = cleaned_text[:-3].strip()

    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        log.warning(f"Initial JSONDecodeError: {e}. Attempting cleanup.")
        # Remove invalid control characters
        cleaned_text_stage2 = re.sub(r'[\x00-\x1f\x7f]', '', cleaned_text)
        try:
            return json.loads(cleaned_text_stage2)
        except json.JSONDecodeError as e2:
            log.error(f"Could not parse LLM JSON response: {e2}")
            return {}


def extract_output_text(resp: Any) -> str:
    """
    Safely extract text content from an OpenAI Response object.
    Handles both completed responses (with output content) and
    partial/in-progress responses where output may be missing.
    """
    if not resp:
        return ""

    # Some SDK responses expose output_text directly
    if hasattr(resp, "output_text"):
        try:
            return resp.output_text
        except Exception:
            pass

    parts = []

    # Preferred: iterate over output content
    output = getattr(resp, "output", None) or []
    for item in output:
        for content in getattr(item, "content", []) or []:
            text_part = getattr(content, "text", None)
            if isinstance(text_part, str):
                parts.append(text_part)
            elif hasattr(text_part, "value"):
                parts.append(text_part.value)

    # Fallback for older/alternate shapes
    if not parts and hasattr(resp, "content"):
        for content in getattr(resp, "content", []) or []:
            text_part = getattr(content, "text", None)
            if isinstance(text_part, str):
                parts.append(text_part)
            elif hasattr(text_part, "value"):
                parts.append(text_part.value)

    return "\n".join([p for p in parts if p]) if parts else ""


def get_response_with_file_search(
    message: str,
    client,
    model: str,
    vector_ids: List[str],
    background: bool = False,
    stream: bool = False,
    metadata: Dict[str, str] | None = None
):
    """
    Call GPT with file_search tool - CORE V2 MECHANISM.
    This is what makes V2 superior: dynamic retrieval during answer generation.
    
    Args:
        background: If True, runs in async background mode (for long-running tasks like o3-deep-research)
    """
    request_kwargs: Dict[str, Any] = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": message
            }
        ],
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": vector_ids
            }
        ],
        "stream": stream
    }

    # OpenAI background mode for long-running tasks
    if background:
        request_kwargs["background"] = True

    if metadata:
        request_kwargs["metadata"] = metadata

    response = client.responses.create(**request_kwargs)
    return response


# =============================================================================
# STEP 1: Get Relevant Nodes from KG Vector Store (V2 SEMANTIC DISCOVERY)
# =============================================================================

def get_relevant_nodes(
    question: str,
    kg_vector_store_id: str,
    client,
    model: str = "gpt-4o",
    max_nodes: int = 10
) -> Dict[str, Any]:
    """
    V2 STEP 1: Use GPT with file_search on KG vector store to get relevant nodes.
    
    This is the KEY DIFFERENCE from production:
    - Production: LLM guesses entity names, then fuzzy matches
    - V2: LLM searches KG vector store semantically, returns actual node names
    
    Returns:
        {
            "original_question": "...",
            "stepback_question": "...",
            "expanded_question": "...",
            "entities": ["...", "..."],
            "node_names": ["...", "..."]
        }
    """
    log.info(f"V2 Step 1: Semantic KG node discovery for: {question[:80]}...")
    
    message = STEPBACK_MESSAGE.format(question=question)
    
    try:
        resp = get_response_with_file_search(
            message=message,
            client=client,
            model=model,
            vector_ids=[kg_vector_store_id],
            background=False  # Discovery is always synchronous
        )
    except Exception as e:
        log.error(f"Error in get_relevant_nodes: {e}")
        return {
            "original_question": question,
            "stepback_question": question,
            "expanded_question": question,
            "entities": [],
            "node_names": []
        }

    # Parse response
    output_text = extract_output_text(resp)

    try:
        result = parse_llm_json(output_text)
        log.info(f"V2 Step 1 Result: stepback='{result.get('stepback_question', '')[:50]}...', "
                 f"entities={len(result.get('entities', []))}, node_names={len(result.get('node_names', []))}")
        log.info(f"V2 Node names found: {result.get('node_names', [])}")
        return result
    except Exception as e:
        log.warning(f"Could not parse stepback response: {e}")
        return {
            "original_question": question,
            "stepback_question": question,
            "expanded_question": question,
            "entities": [],
            "node_names": []
        }


# =============================================================================
# STEP 2: Map Node Names to Graph IDs
# =============================================================================

def map_node_names_to_ids(
    node_names: List[str],
    by_id: Dict[str, Dict],
    name_index: Dict[str, Any] = None
) -> List[str]:
    """
    V2 STEP 2: Map node names returned by GPT to actual node IDs in the graph.
    
    Args:
        node_names: List of node names from GPT (e.g., ["customer card", "product selection screen"])
        by_id: Node lookup dict {node_id: node_data}
        name_index: Optional name-to-ID index for faster lookup
    
    Returns:
        List of node IDs that exist in the graph
    """
    log.info(f"V2 Step 2: Mapping {len(node_names)} node names to graph IDs")
    
    node_ids = []
    not_found = []

    for node_name in node_names:
        node_name_lower = node_name.lower().strip()

        # Strategy 1: Use name_index if available (fastest)
        if name_index:
            if node_name_lower in name_index:
                ids = name_index[node_name_lower]
                if isinstance(ids, (list, tuple)):
                    node_ids.extend([str(id) for id in ids])
                else:
                    node_ids.append(str(ids))
                continue

        # Strategy 2: Search through by_id (fallback)
        found = False
        for node_id, node_data in by_id.items():
            actual_name = (
                node_data.get('name') or
                node_data.get('node_name') or
                node_data.get('label') or
                str(node_id)
            ).lower().strip()

            if node_name_lower == actual_name or node_name_lower in actual_name or actual_name in node_name_lower:
                node_ids.append(str(node_id))
                found = True
                break

        if not found:
            not_found.append(node_name)

    if not_found:
        log.warning(f"Could not find {len(not_found)} nodes in graph: {not_found[:5]}")

    # Deduplicate
    unique_ids = list(set(node_ids))
    log.info(f"V2 Step 2 Result: Found {len(unique_ids)} seed node IDs")
    return unique_ids


# =============================================================================
# STEP 3: Graph Expansion (Same as production - this is fine)
# =============================================================================

def expand_nodes(
    G,
    seed_ids: List[str],
    hops: int = 1,
    edge_type_whitelist: List[str] = None,
    max_expanded: int = 60,
    preset_params: Dict = None
) -> tuple:
    """
    V2 STEP 3: Expand graph from seed nodes.
    This is the same logic as production - no changes needed.
    
    Returns:
        (expanded_node_ids, edges)
    """
    if preset_params:
        max_expanded = preset_params.get("max_expanded", max_expanded)

    def _ok_edge(edata):
        if not edge_type_whitelist:
            return True
        et = edata.get("type") or edata.get("label") or "RELATED"
        return et in edge_type_whitelist

    seen = set(seed_ids)
    q = deque([(nid, 0) for nid in seed_ids])
    edges = []

    while q and len(seen) < max_expanded:
        u, d = q.popleft()
        if u not in G:
            continue

        for v in G[u]:
            for _, edata in G[u][v].items():
                if not _ok_edge(edata):
                    continue
                et = edata.get("type") or edata.get("label") or "RELATED"
                edge = {"source_id": u, "target_id": v, "type": str(et)}
                if "evidence" in edata:
                    edge["evidence"] = edata["evidence"]
                if "source_documents" in edata:
                    edge["source_documents"] = edata["source_documents"]
                edges.append(edge)
            if v not in seen and d < hops:
                seen.add(v)
                q.append((v, d + 1))

        if hasattr(G, "predecessors"):
            for v in G.predecessors(u):
                for _, edata in G[v][u].items():
                    if not _ok_edge(edata):
                        continue
                    et = edata.get("type") or edata.get("label") or "RELATED"
                    edge = {"source_id": v, "target_id": u, "type": str(et)}
                    if "evidence" in edata:
                        edge["evidence"] = edata["evidence"]
                    if "source_documents" in edata:
                        edge["source_documents"] = edata["source_documents"]
                    edges.append(edge)
                if v not in seen and d < hops:
                    seen.add(v)
                    q.append((v, d + 1))

    # Deduplicate edges
    edges = list(set([
        (e["source_id"], e["target_id"], e["type"])
        for e in edges
    ]))
    edges = [
        {"source_id": s, "target_id": t, "type": typ}
        for s, t, typ in edges
    ]

    log.info(f"V2 Step 3 Result: Expanded to {len(seen)} nodes, {len(edges)} edges")
    return list(seen), edges


# =============================================================================
# COMPLETE SUBGRAPH WORKFLOW (Combines Steps 1-3)
# =============================================================================

def get_relevant_subgraph(
    question: str,
    G,
    by_id: Dict[str, Dict],
    kg_vector_store_id: str,
    client,
    stepback_response: Dict,
    name_index: Dict[str, Any] = None,
    edge_type_whitelist: List[str] = None,
    hops: int = 1,
    max_expanded: int = 60
) -> Dict[str, Any]:
    """
    V2 Complete subgraph workflow: Steps 1-3 combined.
    
    Returns:
        {
            "question_analysis": {...},  # Stepback, entities, etc.
            "seed_node_ids": [...],       # Starting nodes
            "expanded_node_ids": [...],   # All nodes in subgraph
            "edges": [...],               # Edges in subgraph
            "nodes": {}                   # Node data for subgraph
        }
    """
    log.info("V2: Getting relevant subgraph")
    
    analysis = stepback_response
    
    # STEP 2: Map node names to IDs
    seed_node_ids = map_node_names_to_ids(
        node_names=analysis.get('node_names', []),
        by_id=by_id,
        name_index=name_index
    )

    if not seed_node_ids:
        log.warning("V2: No seed nodes found!")
        return {
            "question_analysis": analysis,
            "seed_node_ids": [],
            "expanded_node_ids": [],
            "edges": [],
            "nodes": {}
        }

    # STEP 3: Expand graph from seed nodes
    expanded_node_ids, edges = expand_nodes(
        G=G,
        seed_ids=seed_node_ids,
        hops=hops,
        edge_type_whitelist=edge_type_whitelist,
        max_expanded=max_expanded
    )

    # Get node data for expanded nodes
    nodes = {}
    for node_id in expanded_node_ids:
        if node_id in by_id:
            nodes[node_id] = by_id[node_id]

    log.info(f"V2 Subgraph complete: {len(seed_node_ids)} seeds → {len(expanded_node_ids)} nodes, {len(edges)} edges")

    return {
        "question_analysis": analysis,
        "seed_node_ids": seed_node_ids,
        "expanded_node_ids": expanded_node_ids,
        "edges": edges,
        "nodes": nodes
    }


# =============================================================================
# STEP 4: Build KG-Guided Queries (V2 RICH QUERY EXPANSION)
# =============================================================================

def build_kg_guided_queries(
    question: str,
    kg_result: Dict[str, Any],
    by_id: Dict[str, Dict],
    max_queries: int = 12
) -> List[str]:
    """
    V2 STEP 4: Build rich KG-guided queries for vector retrieval.
    
    This is MUCH richer than production's simple reformulations:
    - Original question
    - Stepback question (generic intent)
    - Expanded question (detailed)
    - Entity-focused queries (question + entity)
    - Relationship-focused queries (source --[type]--> target)
    """
    log.info("V2 Step 4: Building KG-guided queries")
    
    queries = []
    
    expanded_node_ids = kg_result.get("expanded_node_ids", [])
    edges = kg_result.get("edges", [])
    analysis = kg_result.get("question_analysis", {})

    # 1. Original question
    queries.append(question)

    # 2. Stepback/expanded questions from GPT analysis
    if analysis.get("stepback_question"):
        queries.append(analysis["stepback_question"])
    if analysis.get("expanded_question"):
        queries.append(analysis["expanded_question"])

    # 3. Entity-focused queries
    node_names = []
    for node_id in expanded_node_ids[:8]:
        if node_id in by_id:
            name = by_id[node_id].get('name', by_id[node_id].get('node_name', str(node_id)))
            node_names.append(name)

    for entity in node_names[:5]:
        queries.append(f"{question} {entity}")

    # 4. Relationship-focused queries
    node_lookup = {}
    for node_id in expanded_node_ids:
        if node_id in by_id:
            name = by_id[node_id].get('name', by_id[node_id].get('node_name', str(node_id)))
            node_lookup[node_id] = name

    for edge in edges[:10]:
        source_name = node_lookup.get(edge["source_id"], "")
        target_name = node_lookup.get(edge["target_id"], "")
        edge_type = edge.get("type", "RELATED")

        if source_name and target_name:
            queries.append(f"{source_name} {edge_type} {target_name}")

    # 5. Deduplicate
    seen = set()
    unique_queries = []
    for q in queries:
        q_lower = q.lower()
        if q_lower not in seen:
            seen.add(q_lower)
            unique_queries.append(q)

    result = unique_queries[:max_queries]
    log.info(f"V2 Step 4 Result: Generated {len(result)} KG-guided queries")
    for i, q in enumerate(result[:5], 1):
        log.debug(f"  Query {i}: {q[:80]}...")
    
    return result


# =============================================================================
# STEP 5: Generate KG Text Context
# =============================================================================

def generate_kg_text(
    kg_result: Dict[str, Any],
    by_id: Dict[str, Dict],
    max_nodes: int = 40,
    max_edges: int = 50
) -> str:
    """
    V2 STEP 5: Generate structured KG text for context.
    
    This provides rich context to GPT showing:
    - ENTITIES with their types
    - RELATIONSHIPS between entities
    """
    log.info("V2 Step 5: Generating KG text context")
    
    expanded_node_ids = kg_result.get("expanded_node_ids", [])
    edges = kg_result.get("edges", [])

    # Build compact node list
    nodes_summary = []
    for node_id in expanded_node_ids[:max_nodes]:
        if node_id in by_id:
            name = by_id[node_id].get('name', by_id[node_id].get('node_name', str(node_id)))
            node_type = by_id[node_id].get('node_type', by_id[node_id].get('type', 'Entity'))
            nodes_summary.append(f"• {name} ({node_type})")

    # Build compact edge list
    node_lookup = {}
    for node_id in expanded_node_ids:
        if node_id in by_id:
            name = by_id[node_id].get('name', by_id[node_id].get('node_name', str(node_id)))
            node_lookup[node_id] = name

    edges_summary = []
    for edge in edges[:max_edges]:
        source = node_lookup.get(edge["source_id"], "?")
        target = node_lookup.get(edge["target_id"], "?")
        rel_type = edge.get("type", "RELATED")
        edges_summary.append(f"• {source} --[{rel_type}]→ {target}")

    kg_text = f"""
The following entities and relationships are relevant to your question:

ENTITIES:
{chr(10).join(nodes_summary)}

RELATIONSHIPS:
{chr(10).join(edges_summary)}

This structure shows WHAT entities exist and HOW they relate.
Use this to understand the architecture and connections.
The actual detailed documentation will be retrieved via file_search.
"""
    
    log.info(f"V2 Step 5 Result: KG text with {len(nodes_summary)} entities, {len(edges_summary)} relationships")
    return kg_text


# =============================================================================
# STEP 6: V2 HYBRID ANSWER (Main entry point)
# =============================================================================

def v2_hybrid_answer(
    question: str,
    G,
    by_id: Dict[str, Dict],
    name_index: Dict[str, Any],
    client,
    kg_vector_store_id: str,
    doc_vector_store_id: str,
    preset_params: Dict = None
) -> Dict[str, Any]:
    """
    V2 COMPLETE HYBRID ANSWER PIPELINE.
    
    This is the main entry point that replicates V2 workflow exactly:
    1. Semantic KG node discovery (file_search on KG vector store)
    2. Map node names to graph IDs
    3. Graph expansion
    4. Build KG-guided queries
    5. Generate KG text context
    6. Final answer with file_search on document vector store
    
    Returns:
        {
            "answer": "...",
            "markdown": "...",
            "stepback_intent": "...",
            "expanded_question": "...",
            "business_entities": [...],
            "meta": {
                "v2_workflow": True,
                "seed_nodes": [...],
                "expanded_nodes": N,
                "expanded_edges": N,
                "kg_guided_queries": [...],
                ...
            }
        }
    """
    log.info("=" * 60)
    log.info("V2 HYBRID ANSWER PIPELINE START")
    log.info("=" * 60)
    log.info(f"Question: {question[:100]}...")
    
    # Get preset params
    if preset_params is None:
        preset_params = {}
    
    mode = preset_params.get("_mode", "balanced")
    model = preset_params.get("model", "gpt-4o")
    hops = preset_params.get("hops", 1)
    max_expanded = preset_params.get("max_expanded", 60)
    max_queries = preset_params.get("max_queries", 12)
    background_mode = bool(preset_params.get("background_mode", False))
    
    # ==========================================================================
    # STEP 1: Semantic KG Node Discovery
    # ==========================================================================
    # Discovery uses the "stepback" preset's model (gpt-5-nano) for fast turnaround
    # This matches V2 behavior where stepback has its own preset
    from ekg_core.core import ANSWER_PRESETS
    stepback_preset = ANSWER_PRESETS.get("stepback", {})
    discovery_model = stepback_preset.get("model", "gpt-5-nano")
    log.info(f"V2 STEP 1: Semantic KG node discovery via file_search (model={discovery_model})")
    stepback_response = get_relevant_nodes(
        question=question,
        kg_vector_store_id=kg_vector_store_id,
        client=client,
        model=discovery_model,
        max_nodes=10
    )
    
    # ==========================================================================
    # STEPS 2-3: Get Relevant Subgraph
    # ==========================================================================
    log.info("V2 STEPS 2-3: Map nodes and expand graph")
    kg_result = get_relevant_subgraph(
        question=question,
        G=G,
        by_id=by_id,
        kg_vector_store_id=kg_vector_store_id,
        client=client,
        name_index=name_index,
        hops=hops,
        max_expanded=max_expanded,
        stepback_response=stepback_response
    )
    
    # ==========================================================================
    # STEP 4: Build KG-Guided Queries
    # ==========================================================================
    log.info("V2 STEP 4: Build KG-guided queries")
    expanded_queries = build_kg_guided_queries(
        question=question,
        kg_result=kg_result,
        by_id=by_id,
        max_queries=max_queries
    )
    
    # ==========================================================================
    # STEP 5: Generate KG Text Context
    # ==========================================================================
    log.info("V2 STEP 5: Generate KG text context")
    kg_text = generate_kg_text(kg_result, by_id)
    
    # ==========================================================================
    # STEP 6: Final Answer with file_search on Document Vector Store
    # ==========================================================================
    log.info("V2 STEP 6: Generate final answer with file_search on doc vector store")
    
    expanded_queries_str = chr(10).join(f"{i+1}. {q}" for i, q in enumerate(expanded_queries))
    message = FILE_SEARCH_MESSAGE.format(
        expanded_queries_str=expanded_queries_str,
        kg_text=kg_text
    )

    response_metadata = {
        "mode": mode,
        "question": question[:500],
        "doc_vector_store_id": str(doc_vector_store_id),
        "kg_vector_store_id": str(kg_vector_store_id),
        "kg_nodes": str(len(kg_result.get('expanded_node_ids', []))),
        "kg_edges": str(len(kg_result.get('edges', [])))
    }
    
    try:
        resp = get_response_with_file_search(
            message=message,
            client=client,
            model=model,
            vector_ids=[doc_vector_store_id],
            background=background_mode,
            metadata=response_metadata
        )

        resp_status = getattr(resp, "status", "")
        resp_id = getattr(resp, "id", None)

        # If running in OpenAI background mode, return immediately with task info
        if background_mode and resp_status != "completed":
            analysis = kg_result.get("question_analysis", {})
            return {
                "answer": None,
                "markdown": f"Deep mode request accepted. Task ID: {resp_id}. Poll status to retrieve the final answer.",
                "stepback_intent": analysis.get('stepback_question', ''),
                "expanded_question": analysis.get('expanded_question', ''),
                "business_entities": analysis.get('entities', []),
                "curated_chunks": [],
                "meta": {
                    "v2_workflow": True,
                    "mode": mode,
                    "model": model,
                    "seed_node_names": analysis.get('node_names', []),
                    "seed_node_ids": kg_result.get('seed_node_ids', []),
                    "expanded_nodes": len(kg_result.get('expanded_node_ids', [])),
                    "expanded_edges": len(kg_result.get('edges', [])),
                    "kg_guided_queries": expanded_queries,
                    "kg_vector_store_id": kg_vector_store_id,
                    "doc_vector_store_id": doc_vector_store_id,
                    "background_mode": True,
                    "background_task_id": resp_id,
                    "background_status": resp_status or "in_progress",
                }
            }

        output_text = extract_output_text(resp)
        answer_json = parse_llm_json(output_text)
        
        answer = answer_json.get('answer', output_text)
        stepback_intent = answer_json.get('stepback_intent', '')
        expanded_question = answer_json.get('expanded_question', '')
        business_entities = answer_json.get('business_entities', [])
        
    except Exception as e:
        log.error(f"V2 Final answer generation failed: {e}")
        answer = f"Error generating answer: {str(e)}"
        stepback_intent = ""
        expanded_question = ""
        business_entities = []
    
    # ==========================================================================
    # Build Final Response
    # ==========================================================================
    analysis = kg_result.get("question_analysis", {})
    
    # Generate markdown with only the answer (no metadata or background info)
    markdown = answer
    
    result = {
        "answer": answer,
        "markdown": markdown,
        "stepback_intent": stepback_intent or analysis.get('stepback_question', ''),
        "expanded_question": expanded_question or analysis.get('expanded_question', ''),
        "business_entities": business_entities or analysis.get('entities', []),
        "curated_chunks": [],  # V2 uses file_search, not pre-retrieved chunks
        "meta": {
            "v2_workflow": True,
            "mode": mode,
            "model": model,
            "seed_node_names": analysis.get('node_names', []),
            "seed_node_ids": kg_result.get('seed_node_ids', []),
            "expanded_nodes": len(kg_result.get('expanded_node_ids', [])),
            "expanded_edges": len(kg_result.get('edges', [])),
            "kg_guided_queries": expanded_queries,
            "kg_vector_store_id": kg_vector_store_id,
            "doc_vector_store_id": doc_vector_store_id,
        }
    }
    
    log.info("=" * 60)
    log.info("V2 HYBRID ANSWER PIPELINE COMPLETE")
    log.info(f"Result: {len(answer)} chars, {result['meta']['expanded_nodes']} nodes, {result['meta']['expanded_edges']} edges")
    log.info("=" * 60)
    
    return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "v2_hybrid_answer",
    "get_relevant_nodes",
    "map_node_names_to_ids",
    "expand_nodes",
    "get_relevant_subgraph",
    "build_kg_guided_queries",
    "generate_kg_text",
    "get_response_with_file_search",
    "parse_llm_json",
    "extract_output_text",
    "PROMPT_SET",
    "FILE_SEARCH_MESSAGE",
    "STEPBACK_MESSAGE",
]

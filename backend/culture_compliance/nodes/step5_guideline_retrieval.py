"""Step 5: Guideline retrieval node for the content compliance pipeline.

Retrieves market-specific regulatory guidelines AND cultural guidelines from
Qdrant collections using vector similarity search. Uses Cohere embed-v4
(1024 dimensions) via AWS Bedrock for embedding the content query.

Combined retrieval:
- Regulatory collection (market-specific): no payload filter, limit=50
- Cultural collection: filtered by market, ethnicity, and age_group, limit=50
- Results merged by similarity score descending, top 50 combined returned
- Each result labeled as "regulatory" or "cultural" for the evaluation prompt
"""

import logging
from typing import Optional

from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import (
    ResponseHandlingException,
    UnexpectedResponse,
)
from qdrant_client.models import (
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
)

from ..config import (
    CULTURAL_COLLECTION_NAME,
    PERSONA_COLLECTION_NAME,
    QDRANT_API_KEY,
    QDRANT_TOP_K,
    QDRANT_URL,
)
from ..embeddings import embed_text
from ..models.schemas import ContentType, PipelineState

logger = logging.getLogger(__name__)

# Top K guidelines to retrieve per collection before merging
_TOP_K = QDRANT_TOP_K  # Default is 50 from config


def _fetch_persona_by_metadata(
    client: QdrantClient,
    market: str,
    ethnicity: str,
    age_group: str,
) -> Optional[str]:
    """Fetch a persona narrative by exact metadata filter (no embedding needed).

    Queries the cultural-personas collection with exact payload filters
    for market, ethnicity, and age_group. Returns the first matching
    persona_text or None if no match is found.

    Args:
        client: An active QdrantClient instance.
        market: Target market (e.g., "malaysia").
        ethnicity: Target ethnicity (e.g., "malay").
        age_group: Target age group (e.g., "all_ages").

    Returns:
        The persona_text string if found, None otherwise.
    """
    try:
        scroll_filter = Filter(
            must=[
                FieldCondition(key="market", match=MatchValue(value=market)),
                FieldCondition(key="ethnicity", match=MatchValue(value=ethnicity)),
                FieldCondition(key="age_group", match=MatchValue(value=age_group)),
            ]
        )

        results, _ = client.scroll(
            collection_name=PERSONA_COLLECTION_NAME,
            scroll_filter=scroll_filter,
            limit=1,
            with_payload=True,
        )

        if results:
            persona_text = results[0].payload.get("persona_text", "")
            logger.info(
                "Persona narrative retrieved for %s/%s/%s (%d chars)",
                market, ethnicity, age_group, len(persona_text),
            )
            return persona_text

        logger.warning(
            "No persona narrative found for %s/%s/%s",
            market, ethnicity, age_group,
        )
        return None

    except Exception as e:
        logger.warning(
            "Persona retrieval failed for %s/%s/%s: %s",
            market, ethnicity, age_group, str(e),
        )
        return None

def _get_qdrant_client() -> QdrantClient:
    """Create a Qdrant client instance.

    Returns:
        A QdrantClient connected to the configured Qdrant instance.

    Raises:
        ConnectionError: If QDRANT_URL is not configured.
    """
    if not QDRANT_URL:
        raise ConnectionError(
            "QDRANT_URL environment variable is not set. "
            "Cannot connect to guideline store."
        )
    return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)


def _build_cultural_filter(
    market: str,
    target_ethnicity: str,
    target_age_group: str,
) -> Filter:
    """Build a Qdrant payload filter for the cultural guidelines collection.

    Filtering logic:
    - Market: must match the specified market
    - Ethnicity: when target is specific (not "all"), include matching + "all";
      when target is "all", no ethnicity filter (all ethnicities included)
    - Age group: always include "all_ages"; when target is specific (not "all_ages"),
      also include the matching age_group

    Args:
        market: The target market ("malaysia" or "singapore").
        target_ethnicity: The target ethnicity for filtering.
        target_age_group: The target age group for filtering.

    Returns:
        A Qdrant Filter object with the appropriate conditions.
    """
    must_conditions = []

    # Market filter: always required
    must_conditions.append(
        FieldCondition(key="market", match=MatchValue(value=market))
    )

    # Ethnicity filter: when specific, include matching + "all"
    # When target is "all", no ethnicity filter needed (include all)
    if target_ethnicity != "all":
        must_conditions.append(
            FieldCondition(
                key="ethnicity",
                match=MatchAny(any=[target_ethnicity, "all"]),
            )
        )

    # Age group filter: always include "all_ages"
    # When target is specific (not "all_ages"), also include matching age_group
    if target_age_group == "all_ages":
        # Only include guidelines tagged "all_ages"
        must_conditions.append(
            FieldCondition(
                key="age_group",
                match=MatchValue(value="all_ages"),
            )
        )
    else:
        # Include both "all_ages" and the specific target age group
        must_conditions.append(
            FieldCondition(
                key="age_group",
                match=MatchAny(any=["all_ages", target_age_group]),
            )
        )

    return Filter(must=must_conditions)


def _format_labeled_results(
    regulatory_points: list,
    cultural_points: list,
    top_k: int = 50,
) -> tuple[str, str, str, list[dict]]:
    """Merge regulatory and cultural results, rank by score, take top K.

    Args:
        regulatory_points: Scored points from the regulatory collection.
        cultural_points: Scored points from the cultural collection.
        top_k: Maximum number of combined results to return.

    Returns:
        A tuple of (regulatory_guidelines_str, cultural_guidelines_str,
        combined_guidelines_str, guideline_sources_list).
    """
    # Tag each point with its source
    tagged_results = []
    for point in regulatory_points:
        tagged_results.append(("regulatory", point))
    for point in cultural_points:
        tagged_results.append(("cultural", point))

    # Sort by similarity score descending
    tagged_results.sort(key=lambda x: x[1].score, reverse=True)

    # Take top K combined
    tagged_results = tagged_results[:top_k]

    # Format into labeled sections
    regulatory_lines = []
    cultural_lines = []
    combined_lines = []
    guideline_sources = []

    reg_idx = 0
    cult_idx = 0

    for i, (source, point) in enumerate(tagged_results, start=1):
        payload = point.payload or {}
        score = round(point.score, 3)

        # Build the guideline text representation
        if source == "cultural":
            # Cultural guidelines have structured fields
            guideline_text = payload.get("guideline_text", "")
            category = payload.get("category", "")
            severity = payload.get("severity", "")
            ethnicity = payload.get("ethnicity", "")
            age_group = payload.get("age_group", "")

            display_text = (
                f"[Category: {category}] [Severity: {severity}] "
                f"[Ethnicity: {ethnicity}] [Age Group: {age_group}]\n"
                f"{guideline_text}"
            )

            cult_idx += 1
            cultural_lines.append(
                f"[C{cult_idx}] (relevance: {score})\n{display_text}"
            )
            combined_lines.append(
                f"[{i}] [CULTURAL] (relevance: {score})\n{display_text}"
            )
        else:
            # Regulatory guidelines use row_text or payload fields
            row_text = " | ".join(
                f"{k}: {v}"
                for k, v in payload.items()
                if k not in ("source", "row_text") and v
            )
            source_name = payload.get("source", "Guidelines")

            reg_idx += 1
            regulatory_lines.append(
                f"[R{reg_idx}] (source: {source_name}, relevance: {score})\n{row_text}"
            )
            combined_lines.append(
                f"[{i}] [REGULATORY] (source: {source_name}, relevance: {score})\n{row_text}"
            )

        # Track source for each guideline
        guideline_sources.append({
            "index": i,
            "source": source,
            "score": score,
            "point_id": str(point.id) if point.id else None,
        })

    # Build final strings
    regulatory_str = (
        "\n\n".join(regulatory_lines)
        if regulatory_lines
        else "No relevant regulatory guidelines found."
    )
    cultural_str = (
        "\n\n".join(cultural_lines)
        if cultural_lines
        else "No relevant cultural guidelines found."
    )

    combined_str = (
        "=== REGULATORY GUIDELINES ===\n\n"
        + regulatory_str
        + "\n\n=== CULTURAL GUIDELINES ===\n\n"
        + cultural_str
    )

    return regulatory_str, cultural_str, combined_str, guideline_sources


def guideline_retrieval(state: PipelineState) -> PipelineState:
    """Retrieve top-50 guidelines from regulatory + cultural collections.

    Queries:
    1. Regulatory collection (market-specific) — no payload filter, limit=50
    2. Cultural collection — filtered by market, ethnicity, age_group, limit=50

    Merges results by similarity score, takes top 50, labels each as
    'regulatory' or 'cultural' for the evaluation prompt.

    Content embedding strategy:
    - Video: uses state.unified_content (Pegasus description)
    - Image: uses state.unified_content (vision + OCR combined)
    - Text: uses state.unified_content (raw text)

    Args:
        state: The current pipeline state. Expects:
            - state.guideline_collection: Qdrant collection name (set by step1_routing)
            - state.unified_content: The content to search against
            - state.market: The target market
            - state.target_ethnicity: Target ethnicity for cultural filtering
            - state.target_age_group: Target age group for cultural filtering

    Returns:
        Updated PipelineState with:
            - regulatory_guidelines: Formatted regulatory results
            - cultural_guidelines: Formatted cultural results
            - retrieved_guidelines: Combined formatted string for evaluation
            - guideline_sources: List tracking source per guideline
    """
    collection_name = state.guideline_collection

    if not collection_name:
        state.errors.append({
            "node": "guideline_retrieval",
            "error_type": "validation",
            "message": (
                "No guideline collection specified. "
                "Ensure market resolution ran before guideline retrieval."
            ),
        })
        return state

    # For video v3 path, unified_content won't be set yet (video_processing
    # runs after guideline_retrieval). Use a generic query for regulatory
    # guideline retrieval in that case.
    is_video_v3 = state.content_type == ContentType.VIDEO and not state.unified_content
    if is_video_v3:
        # Use a broad generic query that will match advertising/modesty rules
        query_text = f"advertising content compliance {state.market.value} cultural norms modesty"
        logger.info(
            "Video v3 path: using generic query for regulatory retrieval"
        )
    elif not state.unified_content:
        state.errors.append({
            "node": "guideline_retrieval",
            "error_type": "validation",
            "message": (
                "No unified content available for guideline retrieval. "
                "Ensure content processing ran before guideline retrieval."
            ),
        })
        return state
    else:
        query_text = state.unified_content

    logger.info(
        "Retrieving guidelines from regulatory collection '%s' and cultural collection '%s'",
        collection_name,
        CULTURAL_COLLECTION_NAME,
    )

    # Step 1: Embed the query text using Cohere embed-v4 with search_query input type
    # For video v3: generic query; for text/image: state.unified_content
    try:
        query_vector = embed_text(
            query_text, input_type="search_query"
        )
    except Exception as e:
        logger.error("Embedding failed: %s", str(e))
        state.errors.append({
            "node": "guideline_retrieval",
            "error_type": "service_unavailable",
            "message": (
                f"Failed to embed content for guideline retrieval: {str(e)}"
            ),
        })
        return state

    # Step 2: Query regulatory collection (market-specific) — no payload filter
    regulatory_points = []
    try:
        client = _get_qdrant_client()
        regulatory_results = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            limit=_TOP_K,
            with_payload=True,
        )
        regulatory_points = regulatory_results.points if regulatory_results.points else []
    except (
        ConnectionError,
        ResponseHandlingException,
        UnexpectedResponse,
        Exception,
    ) as e:
        logger.error(
            "Qdrant query failed for regulatory collection '%s': %s",
            collection_name,
            str(e),
        )
        state.errors.append({
            "node": "guideline_retrieval",
            "error_type": "service_unavailable",
            "message": (
                f"Guideline store unavailable. "
                f"Failed to retrieve regulatory guidelines from '{collection_name}': {str(e)}"
            ),
        })
        return state

    # Step 3: Query cultural collection with payload filter for market, ethnicity, age_group
    cultural_points = []
    try:
        market_value = state.market.value if hasattr(state.market, "value") else str(state.market)
        cultural_filter = _build_cultural_filter(
            market=market_value,
            target_ethnicity=state.target_ethnicity,
            target_age_group=state.target_age_group,
        )

        cultural_results = client.query_points(
            collection_name=CULTURAL_COLLECTION_NAME,
            query=query_vector,
            query_filter=cultural_filter,
            limit=_TOP_K,
            with_payload=True,
        )
        cultural_points = cultural_results.points if cultural_results.points else []
    except (
        ConnectionError,
        ResponseHandlingException,
        UnexpectedResponse,
    ) as e:
        # Cultural collection failure is non-fatal — proceed with regulatory only
        logger.warning(
            "Cultural guideline retrieval failed for collection '%s': %s. "
            "Proceeding with regulatory guidelines only.",
            CULTURAL_COLLECTION_NAME,
            str(e),
        )
        state.warnings.append({
            "step_name": "guideline_retrieval",
            "description": (
                f"Cultural guideline retrieval failed: {str(e)}. "
                "Evaluation will proceed with regulatory guidelines only."
            ),
            "result_may_be_incomplete": True,
        })
    except Exception as e:
        # Catch-all for unexpected errors — still non-fatal
        logger.warning(
            "Unexpected error querying cultural collection '%s': %s. "
            "Proceeding with regulatory guidelines only.",
            CULTURAL_COLLECTION_NAME,
            str(e),
        )
        state.warnings.append({
            "step_name": "guideline_retrieval",
            "description": (
                f"Cultural guideline retrieval encountered unexpected error: {str(e)}. "
                "Evaluation will proceed with regulatory guidelines only."
            ),
            "result_may_be_incomplete": True,
        })

    # Step 4: Merge both result sets, rank by similarity score descending, take top 50
    logger.info(
        "Retrieved %d regulatory and %d cultural guideline chunks",
        len(regulatory_points),
        len(cultural_points),
    )

    regulatory_str, cultural_str, combined_str, guideline_sources = (
        _format_labeled_results(
            regulatory_points=regulatory_points,
            cultural_points=cultural_points,
            top_k=_TOP_K,
        )
    )

    # Step 5: Store labeled results in state
    state.regulatory_guidelines = regulatory_str
    state.cultural_guidelines = cultural_str
    state.retrieved_guidelines = combined_str
    state.guideline_sources = guideline_sources

    # Step 6: For video content, also fetch the persona narrative (v3 pipeline)
    if state.content_type == ContentType.VIDEO:
        market_value = state.market.value if hasattr(state.market, "value") else str(state.market)
        persona = _fetch_persona_by_metadata(
            client=client,
            market=market_value,
            ethnicity=state.target_ethnicity,
            age_group=state.target_age_group,
        )
        if persona:
            state.persona_narrative = persona
        else:
            state.warnings.append({
                "step_name": "guideline_retrieval",
                "description": (
                    f"No persona narrative found for {market_value}/{state.target_ethnicity}/{state.target_age_group}. "
                    "Video evaluation will proceed without persona context."
                ),
                "result_may_be_incomplete": True,
            })

    logger.info(
        "Guideline retrieval complete: %d total guidelines stored "
        "(regulatory: %d, cultural: %d, persona: %s)",
        len(guideline_sources),
        sum(1 for s in guideline_sources if s["source"] == "regulatory"),
        sum(1 for s in guideline_sources if s["source"] == "cultural"),
        "yes" if state.persona_narrative else "no",
    )

    return state

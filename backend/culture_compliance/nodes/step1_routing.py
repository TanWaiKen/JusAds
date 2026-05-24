"""Step 1: Content routing and market resolution node for the compliance pipeline.

Validates the content_type field, resolves the target market from a
ContentSubmission, and maps it to the appropriate Qdrant collection for
guideline retrieval. Sets the routing decision in the pipeline state.

This module merges the functionality of the former router.py and
market_resolver.py into a single routing step.
"""

from typing import Optional

from culture_compliance.models.schemas import (
    ContentType,
    Market,
    PipelineError,
    PipelineState,
)

# --- Content Routing ---

# Supported content types (case-sensitive, lowercase only)
SUPPORTED_CONTENT_TYPES = {"text", "image", "video"}

# --- Market Resolution ---

# Mapping from Market enum to Qdrant collection name
COLLECTION_CONFIG: dict[Market, dict[str, str]] = {
    Market.MALAYSIA: {
        "collection_name": "mcmc-guidelines",
        "source_authority": "MCMC",
    },
    Market.SINGAPORE: {
        "collection_name": "singapore-imda-asas-guidelines",
        "source_authority": "IMDA/ASAS",
    },
}

SUPPORTED_MARKETS = [m.value for m in Market]


def resolve_market(market_value: Optional[str]) -> Market:
    """Resolve a market string to a Market enum value (case-insensitive).

    Args:
        market_value: The market string from the submission. Can be any case
            variant of "malaysia" or "singapore", or None to use the default.

    Returns:
        The resolved Market enum value.

    Raises:
        ValueError: If the market value is not a supported market.
    """
    if market_value is None or market_value.strip() == "":
        return Market.MALAYSIA

    normalized = market_value.strip().lower()

    try:
        return Market(normalized)
    except ValueError:
        raise ValueError(
            f"Unsupported market: '{market_value}'. "
            f"Supported markets are: {SUPPORTED_MARKETS}"
        )


def get_collection_name(market: Market) -> str:
    """Get the Qdrant collection name for a given market.

    Args:
        market: The resolved Market enum value.

    Returns:
        The Qdrant collection name string.
    """
    return COLLECTION_CONFIG[market]["collection_name"]


def content_routing(state: PipelineState) -> PipelineState:
    """Validate input content_type, resolve market, and set routing decision.

    Performs case-sensitive validation of the content_type field, accepting
    only lowercase values: "text", "image", "video". Then resolves the market
    and maps it to the appropriate Qdrant collection. Adds an error to the
    state's errors list for missing, null, empty, or unsupported values.

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with content_type set for routing and
        market/guideline_collection resolved, or with errors appended
        if validation fails.
    """
    # --- Content Type Validation ---

    # Extract content_type from the submission
    content_type_value = state.content_type

    # Check for missing/null/empty content_type
    if content_type_value is None:
        state.errors.append({
            "error_type": "validation",
            "message": "content_type is required and must not be null or empty",
            "details": {"field": "content_type"},
        })
        return state

    # Get the string value from the enum (or raw string if somehow bypassed)
    if isinstance(content_type_value, ContentType):
        type_str = content_type_value.value
    else:
        type_str = str(content_type_value)

    # Validate case-sensitive, lowercase only
    if type_str not in SUPPORTED_CONTENT_TYPES:
        state.errors.append({
            "error_type": "validation",
            "message": (
                f"Unsupported content_type: '{type_str}'. "
                f"Supported types are: {sorted(SUPPORTED_CONTENT_TYPES)}"
            ),
            "details": {
                "field": "content_type",
                "provided_value": type_str,
                "supported_values": sorted(SUPPORTED_CONTENT_TYPES),
            },
        })
        return state

    # --- Market Resolution ---

    market_value = state.submission.market.value if state.submission.market else None

    try:
        resolved_market = resolve_market(market_value)
    except ValueError as e:
        state.errors.append(
            {
                "node": "market_resolution",
                "error_type": "validation",
                "message": str(e),
            }
        )
        return state

    state.market = resolved_market
    state.guideline_collection = get_collection_name(resolved_market)

    # --- Ethnicity Validation ---
    SUPPORTED_ETHNICITIES = {"malay", "chinese", "indian", "all"}
    target_ethnicity = state.submission.target_ethnicity
    if target_ethnicity not in SUPPORTED_ETHNICITIES:
        state.errors.append({
            "error_type": "validation",
            "message": (
                f"Invalid target_ethnicity: '{target_ethnicity}'. "
                f"Supported values are: {sorted(SUPPORTED_ETHNICITIES)}"
            ),
            "details": {
                "field": "target_ethnicity",
                "supported_values": sorted(SUPPORTED_ETHNICITIES),
            },
        })
        return state
    state.target_ethnicity = target_ethnicity

    # --- Age Group Validation ---
    SUPPORTED_AGE_GROUPS = {"all_ages", "adults_only", "children"}
    target_age_group = state.submission.target_age_group
    if target_age_group not in SUPPORTED_AGE_GROUPS:
        state.errors.append({
            "error_type": "validation",
            "message": (
                f"Invalid target_age_group: '{target_age_group}'. "
                f"Supported values are: {sorted(SUPPORTED_AGE_GROUPS)}"
            ),
            "details": {
                "field": "target_age_group",
                "supported_values": sorted(SUPPORTED_AGE_GROUPS),
            },
        })
        return state
    state.target_age_group = target_age_group

    # Valid content_type, market, ethnicity, and age group — routing decision is set
    return state


def market_resolution(state: PipelineState) -> PipelineState:
    """Resolve market and set the guideline collection in pipeline state.

    This is a standalone market resolution function preserved for backward
    compatibility. In the unified routing step, market resolution is handled
    within content_routing().

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with market and guideline_collection set,
        or with an error appended if the market is unsupported.
    """
    market_value = state.submission.market.value if state.submission.market else None

    try:
        resolved_market = resolve_market(market_value)
    except ValueError as e:
        state.errors.append(
            {
                "node": "market_resolution",
                "error_type": "validation",
                "message": str(e),
            }
        )
        return state

    state.market = resolved_market
    state.guideline_collection = get_collection_name(resolved_market)

    return state

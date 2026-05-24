"""Step 4: Text processing node for the compliance pipeline.

Validates text content and prepares unified content for guideline retrieval
and compliance evaluation. Rejects empty or whitespace-only text with a
validation error.
"""

from culture_compliance.models.schemas import PipelineState


def text_processing(state: PipelineState) -> PipelineState:
    """Validate text content and prepare for evaluation.

    Checks that the submission content is non-empty and not whitespace-only.
    On success, sets the unified_content field in state to the text content
    for downstream guideline retrieval and compliance evaluation.

    Args:
        state: The current pipeline state containing the submission.

    Returns:
        Updated PipelineState with unified_content set to the text content,
        or with an error appended if the text is empty/whitespace-only.
    """
    text_content = state.submission.content

    # Validate non-empty, non-whitespace text
    if not text_content or not text_content.strip():
        state.errors.append({
            "error_type": "validation",
            "message": "Text content must not be empty or whitespace-only",
            "details": {"field": "content"},
        })
        return state

    # Set unified content for downstream evaluation
    state.unified_content = text_content

    return state

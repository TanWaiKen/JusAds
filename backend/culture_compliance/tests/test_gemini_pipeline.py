"""
Unit and integration tests for the Gemini-based Culture Compliance pipeline.
Contains simple, readable, and highly maintainable test scenarios.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from culture_compliance.config import EMBED_DIMENSIONS
from culture_compliance.gemini_client import parse_json_response
from culture_compliance.models.schemas import (
    ComplianceResult,
    ContentSubmission,
    ContentType,
    Market,
    PipelineState,
)
from culture_compliance.embeddings import embed_text, embed_batch
from culture_compliance.services.vision import analyze_image
from culture_compliance.services.ocr import extract_text_from_image
from culture_compliance.nodes.step1_routing import content_routing
from culture_compliance.nodes.step2_video_analysis import video_processing
from culture_compliance.nodes.step5_guideline_retrieval import guideline_retrieval
from culture_compliance.nodes.step6_compliance_evaluation import compliance_evaluation
from culture_compliance.nodes.step7_result_formatting import result_formatting
from culture_compliance.orchestrator import run_pipeline


# --- 1. JSON Parser Tests ---

def test_parse_json_response_clean():
    """Verify standard JSON string parses correctly."""
    assert parse_json_response('{"status": "ok"}') == {"status": "ok"}


def test_parse_json_response_with_markdown():
    """Verify JSON wrapped in markdown fences parses correctly."""
    fenced_input = "```json\n{\n  \"status\": \"fenced\"\n}\n```"
    assert parse_json_response(fenced_input) == {"status": "fenced"}


# --- 2. Embedding Tests ---

@patch("culture_compliance.embeddings.get_client")
def test_embed_text(mock_get_client):
    """Verify single text embedding returns standard list of floats."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.embeddings = [MagicMock(values=[0.1] * EMBED_DIMENSIONS)]
    mock_client.models.embed_content.return_value = mock_response

    res = embed_text("test text")
    assert len(res) == EMBED_DIMENSIONS
    assert res[0] == 0.1
    mock_client.models.embed_content.assert_called_once_with(
        model="text-embedding-004",
        contents="test text",
    )


@patch("culture_compliance.embeddings.get_client")
def test_embed_batch(mock_get_client):
    """Verify batch text embedding returns list of float lists."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.embeddings = [
        MagicMock(values=[0.1] * EMBED_DIMENSIONS),
        MagicMock(values=[0.2] * EMBED_DIMENSIONS),
    ]
    mock_client.models.embed_content.return_value = mock_response

    res = embed_batch(["one", "two"])
    assert len(res) == 2
    assert len(res[0]) == EMBED_DIMENSIONS
    assert res[0][0] == 0.1
    assert res[1][0] == 0.2


# --- 3. Vision & OCR Service Tests ---

@patch("culture_compliance.services.vision.gemini_analyze_image")
def test_vision_analyze_image(mock_analyze):
    """Verify vision service passes correct prompt and gets description."""
    mock_analyze.return_value = "A beautiful scene with mountains."
    
    res = analyze_image(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
    assert res == "A beautiful scene with mountains."
    mock_analyze.assert_called_once()


@patch("culture_compliance.services.ocr.gemini_analyze_image")
def test_ocr_extract_text(mock_analyze):
    """Verify OCR service passes OCR prompt and gets extracted text."""
    mock_analyze.return_value = "SALE 50% OFF"
    
    res = extract_text_from_image(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
    assert res == "SALE 50% OFF"
    mock_analyze.assert_called_once()


# --- 4. Pipeline Nodes Tests ---

def test_step1_content_routing():
    """Verify step 1 maps content submission details to state correctly."""
    submission = ContentSubmission(
        content="This is compliance text.",
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )

    updated_state = content_routing(state)
    assert not updated_state.errors
    assert updated_state.market == Market.MALAYSIA
    assert updated_state.guideline_collection == "mcmc-guidelines"


@patch("culture_compliance.nodes.step2_video_analysis.gemini_analyze_video")
@patch("os.path.exists")
@patch("culture_compliance.nodes.step2_video_analysis._get_video_duration")
def test_step2_video_processing(mock_duration, mock_exists, mock_analyze):
    """Verify step 2 uploads video and runs visual audit successfully."""
    mock_exists.return_value = True
    mock_duration.return_value = 10.0
    mock_analyze.return_value = "Visual audit: bare armpits at 00:05."

    submission = ContentSubmission(
        content="ad.mp4",
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.VIDEO,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )

    updated_state = video_processing(state)
    assert not updated_state.errors
    assert updated_state.unified_content == "Visual audit: bare armpits at 00:05."
    mock_analyze.assert_called_once()


@patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
@patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
def test_step5_guideline_retrieval(mock_get_qdrant, mock_embed):
    """Verify step 5 fetches regulatory and cultural guidelines successfully."""
    mock_embed.return_value = [0.1] * EMBED_DIMENSIONS
    
    mock_qdrant = MagicMock()
    mock_get_qdrant.return_value = mock_qdrant

    # Mock query_points results
    mock_reg_point = MagicMock(score=0.9, id="reg-id")
    mock_reg_point.payload = {"guideline_text": "Rule A", "topic_category": "Topic A"}
    mock_reg_result = MagicMock(points=[mock_reg_point])
    
    mock_cult_point = MagicMock(score=0.8, id="cult-id")
    mock_cult_point.payload = {"guideline_text": "Cultural persona B", "category": "Culture B", "severity": "minor"}
    mock_cult_result = MagicMock(points=[mock_cult_point])
    
    # query_points returns regulatory first, then cultural
    mock_qdrant.query_points.side_effect = [mock_reg_result, mock_cult_result]

    submission = ContentSubmission(
        content="This is compliance text.",
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
        guideline_collection="mcmc-guidelines",
        unified_content="This is compliance text.",
    )

    updated_state = guideline_retrieval(state)
    assert not updated_state.errors
    assert "Rule A" in updated_state.regulatory_guidelines
    assert "Cultural persona B" in updated_state.cultural_guidelines


@patch("culture_compliance.nodes.step6_compliance_evaluation.generate_text")
def test_step6_compliance_evaluation(mock_generate):
    """Verify step 6 produces structured compliance evaluation result."""
    mock_generate.return_value = json.dumps({
        "risk_level": "Low",
        "score": 95,
        "high_risk_indicators": [],
        "explanation": "Content is compliant.",
        "suggestion": "No changes needed."
    })

    submission = ContentSubmission(
        content="This is compliance text.",
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )
    state = PipelineState(
        submission=submission,
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
        unified_content="This is compliance text.",
        regulatory_guidelines="[1] Rule A",
        cultural_guidelines="[1] Cultural persona B",
    )

    updated_state = compliance_evaluation(state)
    assert not updated_state.errors
    assert updated_state.raw_llm_output["risk_level"] == "Low"
    assert updated_state.raw_llm_output["score"] == 95


def test_step7_result_formatting():
    """Verify step 7 packs state results into a serializable ComplianceResult."""
    state = PipelineState(
        submission=ContentSubmission(
            content="test", content_type=ContentType.TEXT, market=Market.MALAYSIA
        ),
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        raw_llm_output={
            "risk_level": "Low",
            "score": 100,
            "high_risk_indicators": [],
            "explanation": "Passed.",
            "suggestion": "None."
        },
        models_used=["gemini-2.5-flash"],
        pipeline_start_ms=1000,
    )

    updated_state = result_formatting(state)
    assert not updated_state.errors
    result = updated_state.compliance_result
    assert isinstance(result, dict)
    assert result["risk_level"] == "Low"
    assert result["score"] == 100
    assert result["processing_metadata"]["models_used"] == ["gemini-2.5-flash"]


# --- 5. End-to-End Orchestrator Mocked Integration ---

@patch("culture_compliance.nodes.step5_guideline_retrieval.embed_text")
@patch("culture_compliance.nodes.step5_guideline_retrieval._get_qdrant_client")
@patch("culture_compliance.nodes.step6_compliance_evaluation.generate_text")
def test_end_to_end_orchestrator(mock_generate, mock_get_qdrant, mock_embed):
    """Verify full orchestrator runs and compiles results end-to-end."""
    mock_embed.return_value = [0.1] * EMBED_DIMENSIONS
    
    mock_qdrant = MagicMock()
    mock_get_qdrant.return_value = mock_qdrant

    # Mock Qdrant results
    mock_reg_point = MagicMock(score=0.9, id="reg-id")
    mock_reg_point.payload = {"guideline_text": "Rule A", "topic_category": "Topic A"}
    mock_reg_result = MagicMock(points=[mock_reg_point])
    
    mock_cult_point = MagicMock(score=0.8, id="cult-id")
    mock_cult_point.payload = {"guideline_text": "Cultural persona B", "category": "Culture B", "severity": "minor"}
    mock_cult_result = MagicMock(points=[mock_cult_point])
    
    mock_qdrant.query_points.side_effect = [mock_reg_result, mock_cult_result]

    mock_generate.return_value = json.dumps({
        "risk_level": "Medium",
        "score": 70,
        "high_risk_indicators": [
            {
                "phrase": "offensive word",
                "char_offset": 5,
                "category": "Profanity",
                "severity": "Moderate",
                "guideline_source": "regulatory"
            }
        ],
        "explanation": "Uses mildly offensive word.",
        "suggestion": "Replace offensive word with polite synonym."
    })

    submission = ContentSubmission(
        content="some offensive word here",
        content_type=ContentType.TEXT,
        market=Market.MALAYSIA,
        target_ethnicity="malay",
        target_age_group="all_ages",
    )

    result = run_pipeline(submission)
    
    assert isinstance(result, dict)
    assert result["risk_level"] == "Medium"
    assert result["score"] == 70
    assert len(result["high_risk_indicators"]) == 1
    assert result["high_risk_indicators"][0]["phrase"] == "offensive word"
    assert result["high_risk_indicators"][0]["guideline_source"] == "regulatory"


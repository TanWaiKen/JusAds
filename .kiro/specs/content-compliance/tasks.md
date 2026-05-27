 Implementation Plan: Content Compliance Pipeline

## Overview

This plan implements a multi-modal content compliance pipeline using LangGraph orchestration, supporting text, image, and video analysis against Malaysia (MCMC) and Singapore (IMDA/ASAS) regulatory guidelines. The implementation builds incrementally from data models and scoring logic through individual pipeline nodes to full orchestration, Lambda deployment, and CLI tooling.

## Tasks

- [x] 1. Set up project structure, data models, and scoring logic
  - [x] 1.1 Create directory structure and core data models
    - Create `backend/culture_compliance/models/` directory with `__init__.py`
    - Implement `ContentSubmission`, `ComplianceResult`, `PipelineState`, `TextIssueLocation`, `ImageIssueLocation`, `VideoIssueLocation`, `ProcessingMetadata`, `PipelineWarning`, `PipelineError` Pydantic models in `backend/culture_compliance/models/schemas.py`
    - Implement `ContentType`, `Market` enums
    - Add field validators for content not empty, bounding box ranges, score constraints
    - _Requirements: 1.4, 1.5, 1.6, 10.1, 10.2, 10.3, 10.4, 10.5, 11.2_

  - [x] 1.2 Implement scoring configuration and calculation
    - Create `backend/culture_compliance/scoring.py`
    - Define `MALAYSIA_SCORING` and `SINGAPORE_SCORING` category lists with weights
    - Define `SEVERITY_MULTIPLIERS` mapping
    - Implement `calculate_score(violations: list[tuple[str, str]], market: Market) -> int` function that applies the formula: `max(0, round(100 - sum(weight × multiplier)))`
    - Implement `score_to_risk_level(score: int) -> str` mapping function
    - Implement `get_scoring_config(market: Market) -> list[ScoringCategory]` function
    - _Requirements: 2.3, 2.4, 5.5, 6.4_

  - [x] 1.3 Write property tests for scoring logic
    - **Property 3: Scoring Formula Correctness**
    - **Property 4: Score-to-Risk-Level Mapping**
    - **Property 12: Market Scoring Configuration**
    - **Validates: Requirements 2.3, 2.4, 5.5**

  - [x] 1.4 Write property tests for data model validation
    - **Property 2: Invalid Content Type Rejection**
    - **Property 5: Whitespace Text Rejection**
    - **Property 15: ComplianceResult Schema Validity**
    - **Validates: Requirements 1.4, 1.6, 2.5, 10.1, 10.2, 10.3, 10.4, 10.5**

  - [x] 1.5 Write property tests for serialization
    - **Property 16: Serialization Round-Trip Identity**
    - **Property 17: Deserialization Error Detection**
    - **Property 18: Payload Size Rejection**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7**

- [x] 2. Implement content routing and market resolution
  - [x] 2.1 Implement content router node
    - Create `backend/culture_compliance/nodes/` directory with `__init__.py`
    - Create `backend/culture_compliance/nodes/router.py`
    - Implement `content_routing(state: PipelineState) -> PipelineState` that validates `content_type` (case-sensitive, lowercase only) and sets routing decision
    - Return error for unsupported content types listing supported values
    - Return validation error for missing/null/empty content_type
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x] 2.2 Implement market resolution logic
    - Create `backend/culture_compliance/nodes/market_resolver.py`
    - Implement case-insensitive market matching ("malaysia", "singapore")
    - Default to Malaysia when no market specified
    - Return error for unsupported market values
    - Map market to Qdrant collection name (`mcmc-guidelines` or `singapore-imda-asas-guidelines`)
    - _Requirements: 5.1, 5.2, 5.4, 5.6_

  - [x] 2.3 Write property tests for routing and market resolution
    - **Property 1: Content Type Routing Preserves Type**
    - **Property 11: Market Routing Correctness**
    - **Property 13: Invalid Market Rejection**
    - **Validates: Requirements 1.1, 1.2, 1.3, 5.1, 5.2, 5.6, 7.5**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement text pipeline and guideline retrieval
  - [x] 4.1 Implement text processing node
    - Create `backend/culture_compliance/nodes/text_pipeline.py`
    - Implement `text_processing(state: PipelineState) -> PipelineState` that validates non-empty text and prepares unified content for evaluation
    - Set `unified_content` in state to the text content
    - Return validation error for empty/whitespace-only text
    - _Requirements: 2.1, 2.5_

  - [x] 4.2 Implement guideline retrieval node
    - Create `backend/culture_compliance/nodes/guideline_retrieval.py`
    - Implement `guideline_retrieval(state: PipelineState) -> PipelineState` that queries the appropriate Qdrant collection based on market
    - Retrieve top 5 guidelines ranked by vector similarity using Cohere embed-v4 (1024 dimensions)
    - Store retrieved guidelines in state
    - Log collection name and number of chunks retrieved
    - Handle Qdrant unavailability with error response
    - _Requirements: 2.1, 5.1, 5.2, 5.3, 7.6, 9.6_

  - [x] 4.3 Implement compliance evaluation node
    - Create `backend/culture_compliance/nodes/compliance_evaluation.py`
    - Implement `compliance_evaluation(state: PipelineState) -> PipelineState` that invokes Bedrock LLM with content + guidelines
    - Construct prompt requesting structured JSON output with risk level, score, high_risk_indicators (with localization), explanation, and suggestion
    - Apply market-specific scoring categories and weights
    - Log model ID and response time in milliseconds
    - Handle LLM failure with error response
    - _Requirements: 2.2, 2.3, 2.4, 2.7, 5.5, 9.6, 10.1_

  - [x] 4.4 Write unit tests for text pipeline
    - Test empty text rejection
    - Test valid text passes through
    - Test guideline retrieval with mocked Qdrant
    - Test LLM evaluation with mocked Bedrock
    - Test guideline store failure handling
    - _Requirements: 2.1, 2.5, 2.6, 2.7_

- [x] 5. Implement image pipeline
  - [x] 5.1 Implement vision service
    - Create `backend/culture_compliance/services/` directory with `__init__.py`
    - Create `backend/culture_compliance/services/vision.py`
    - Implement `analyze_image(image_bytes: bytes) -> str` using Amazon Nova Pro via Bedrock Converse API
    - Send image bytes directly for visual content understanding
    - Return visual description string
    - Handle model unavailability gracefully
    - _Requirements: 3.1, 3.8_

  - [x] 5.2 Implement OCR service
    - Create `backend/culture_compliance/services/ocr.py`
    - Implement `extract_text_from_image(image_bytes: bytes) -> str` using Amazon Nova Pro with OCR-specific prompt
    - Extract overlays, signage, captions, watermarks
    - Handle OCR failure gracefully
    - _Requirements: 3.2, 3.9_

  - [x] 5.3 Implement image processing node
    - Create `backend/culture_compliance/nodes/image_pipeline.py`
    - Implement `image_processing(state: PipelineState) -> PipelineState`
    - Validate image format (JPEG, PNG, WebP), size (≤5 MB), and resolution (≥50x50)
    - Decode base64 image content
    - Call vision service and OCR service
    - Combine visual description + OCR text into unified content description
    - Handle partial failures (vision fails → OCR only, OCR fails → vision only) with warnings
    - Request bounding box localization from vision model for issue detection
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9_

  - [x] 5.4 Write property tests for image validation
    - **Property 6: Image File Validation**
    - **Property 7: Image Content Combination Completeness**
    - **Validates: Requirements 3.3, 3.5, 3.6, 3.7**

  - [x] 5.5 Write unit tests for image pipeline
    - Test format validation (accept JPEG/PNG/WebP, reject others)
    - Test size validation (reject >5 MB)
    - Test resolution validation (reject <50x50)
    - Test vision model fallback to OCR-only
    - Test OCR fallback to vision-only
    - _Requirements: 3.5, 3.6, 3.7, 3.8, 3.9_

- [x] 6. Implement video pipeline
  - [x] 6.1 Implement frame extractor service
    - Create `backend/culture_compliance/services/frame_extractor.py`
    - Implement `extract_frames(video_path: str, interval: float = 1.0) -> list[dict]` using ffmpeg subprocess
    - Sample frames at configurable interval (0.5–5.0 seconds)
    - Return list of dicts with `timestamp` and `frame_bytes` for each frame
    - Calculate expected frame count as `ceil(duration / interval)`
    - _Requirements: 4.1_

  - [x] 6.2 Implement audio transcriber service
    - Create `backend/culture_compliance/services/transcriber.py`
    - Implement `transcribe_audio(video_path: str) -> list[dict]` using Amazon Transcribe
    - Return segment-level timestamps (start_time, end_time, text)
    - Handle videos with no audio track (return empty list)
    - Handle transcription failures gracefully
    - _Requirements: 4.2, 4.9, 4.10_

  - [x] 6.3 Implement video processing node
    - Create `backend/culture_compliance/nodes/video_pipeline.py`
    - Implement `video_processing(state: PipelineState) -> PipelineState`
    - Validate video format (MP4, MOV, WebM), size (≤100 MB), duration (≤5 minutes)
    - Extract frames via frame extractor
    - Transcribe audio via transcriber
    - Analyze frames with Video Understanding Model (fall back to frame-by-frame Nova Pro vision if unavailable)
    - Merge frame descriptions and transcript segments chronologically by timestamp
    - Set unified content in state with timestamped entries
    - Handle partial failures with warnings
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10_

  - [x] 6.4 Write property tests for video validation
    - **Property 8: Video Frame Count Calculation**
    - **Property 9: Chronological Merge Ordering**
    - **Property 10: Video File Validation**
    - **Validates: Requirements 4.1, 4.4, 4.6, 4.7**

  - [x] 6.5 Write unit tests for video pipeline
    - Test format validation (accept MP4/MOV/WebM, reject others)
    - Test size validation (reject >100 MB)
    - Test duration validation (reject >5 minutes)
    - Test video model fallback to frame-by-frame vision
    - Test no-audio-track handling
    - Test transcriber failure handling
    - _Requirements: 4.6, 4.7, 4.8, 4.9, 4.10_

- [x] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Implement LangGraph orchestration and error handling
  - [x] 8.1 Implement result formatting node
    - Create `backend/culture_compliance/nodes/result_formatting.py`
    - Implement `result_formatting(state: PipelineState) -> PipelineState` that parses raw LLM output into validated `ComplianceResult`
    - Apply score-to-risk-level mapping
    - Enforce max 10 high_risk_indicators
    - Add processing metadata (duration, models used, market)
    - Serialize to UTF-8 JSON preserving non-ASCII characters
    - _Requirements: 10.1, 10.5, 10.7, 11.1_

  - [x] 8.2 Implement error handler node
    - Create `backend/culture_compliance/nodes/error_handler.py`
    - Implement `error_handler(state: PipelineState) -> PipelineState` that captures error details (node name, error type, description)
    - Produce partial `ComplianceResult` with warnings array
    - Handle timeout scenarios (return risk_level "Unknown", score -1)
    - _Requirements: 7.3, 8.5, 10.6_

  - [x] 8.3 Implement pipeline orchestrator with LangGraph
    - Create `backend/culture_compliance/orchestrator.py`
    - Implement `create_pipeline() -> CompiledGraph` that builds the LangGraph `StateGraph`
    - Define nodes: content_routing, text_processing, image_processing, video_processing, guideline_retrieval, compliance_evaluation, result_formatting, error_handler
    - Define conditional edges based on content_type for routing
    - Implement retry logic with exponential backoff (max 2 retries) for transient errors
    - Implement `run_pipeline(submission: ContentSubmission) -> ComplianceResult`
    - Ensure stateless design (new graph instance per invocation)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 8.4 Write property tests for error handling
    - **Property 14: Error State Capture Completeness**
    - **Validates: Requirements 7.3, 10.6**

  - [x] 8.5 Write unit tests for orchestrator
    - Test graph structure (correct nodes and edges)
    - Test conditional routing based on content_type
    - Test retry logic with mocked transient errors
    - Test timeout handling
    - Test stateless invocation
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [x] 9. Implement Singapore guidelines ingestion
  - [x] 9.1 Create Singapore guidelines data file
    - Create `backend/culture_compliance/data/singapore_imda_asas_guidelines.csv`
    - Include IMDA guidelines with at least 5 entries per topic: racial/religious harmony, public morals, national interest, consumer protection
    - Include ASAS code provisions with at least 5 entries per topic: decency, honesty, social responsibility, product categories (alcohol, health supplements, financial services, food and beverage)
    - Include metadata columns: source_authority, topic_category, guideline_text
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 9.2 Extend guideline ingestion for multi-market support
    - Modify `backend/culture_compliance/ingest.py` to support market parameter
    - Implement collection routing: Malaysia → `mcmc-guidelines`, Singapore → `singapore-imda-asas-guidelines`
    - Use Cohere embed-v4 with 1024 dimensions for embeddings
    - Store payload metadata: source_authority, topic_category, guideline_text
    - Handle missing/empty CSV file with descriptive error
    - Support `recreate` flag to rebuild collection
    - _Requirements: 5.3, 6.3, 6.5, 6.6_

  - [x] 9.3 Write unit tests for guideline ingestion
    - Test successful ingestion creates correct collection
    - Test missing CSV file returns error
    - Test empty CSV file returns error
    - Test metadata stored correctly
    - _Requirements: 6.3, 6.5, 6.6_

- [x] 10. Implement Lambda handler and CLI
  - [x] 10.1 Implement AWS Lambda handler
    - Create `backend/culture_compliance/handler.py`
    - Implement `lambda_handler(event, context)` that parses API Gateway proxy events
    - Route synchronous requests (text/image) and async requests (video)
    - Handle payload size validation (reject >1 MB JSON payloads)
    - Clean up /tmp files before returning
    - Return JSON response with proper status codes
    - For video: invoke asynchronously, store result in S3 at predictable key
    - _Requirements: 8.1, 8.2, 8.3, 8.5, 8.6, 8.7, 11.7_

  - [x] 10.2 Implement local CLI runner
    - Create `backend/culture_compliance/cli.py`
    - Implement CLI accepting content, content_type, and market arguments
    - Support file paths for image/video content (read from local filesystem)
    - Load credentials from environment variables
    - Validate required env vars (AWS credentials, QDRANT_URL, QDRANT_API_KEY) with descriptive errors
    - Log intermediate steps to stdout (guidelines retrieved, model invocations, duration)
    - Return same output schema as Lambda handler
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.6_

  - [x] 10.3 Create test script for all pipelines
    - Create `backend/culture_compliance/test_all_pipelines.py`
    - Exercise text pipeline with sample ad copy
    - Exercise image pipeline with sample image file
    - Exercise video pipeline with sample video file (e.g., "Test Video.mp4")
    - Report pass/fail for each pipeline based on valid ComplianceResult returned
    - _Requirements: 9.5_

  - [x] 10.4 Write unit tests for Lambda handler
    - Test API Gateway event parsing
    - Test synchronous response for text/image
    - Test async invocation for video
    - Test payload size rejection (>1 MB)
    - Test /tmp cleanup
    - _Requirements: 8.1, 8.2, 8.5, 8.6, 8.7, 11.7_

- [x] 11. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Wire everything together and create test infrastructure
  - [x] 12.1 Create test infrastructure and shared fixtures
    - Create `backend/culture_compliance/tests/` directory structure as defined in design
    - Create `backend/culture_compliance/tests/conftest.py` with shared fixtures and Hypothesis profiles
    - Create `backend/culture_compliance/generators/` directory with strategy modules for ContentSubmission, ComplianceResult, and file metadata
    - Configure Hypothesis settings (min 100 examples, 5000ms deadline)
    - _Requirements: 9.5_

  - [x] 12.2 Create integration test suite
    - Create `backend/culture_compliance/tests/integration/test_full_pipeline.py`
    - Test full text pipeline end-to-end with real Bedrock + Qdrant
    - Test full image pipeline end-to-end with sample JPEG
    - Test full video pipeline end-to-end with sample MP4
    - Test multi-market evaluation (same content, both markets)
    - Create `backend/culture_compliance/tests/integration/test_ingestion.py` for guideline ingestion verification
    - _Requirements: 9.5, 5.1, 5.2_

  - [x] 12.3 Wire pipeline end-to-end and verify
    - Ensure all nodes are properly connected in the LangGraph graph
    - Verify content routing flows through to result formatting for all content types
    - Verify error handling routes correctly from any failing node
    - Verify Lambda handler invokes pipeline correctly
    - Verify CLI invokes pipeline correctly
    - Run full test suite to confirm integration
    - _Requirements: 7.1, 7.2, 7.5, 8.1, 9.1_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with Pydantic, LangGraph, Hypothesis, and pytest
- AWS services used: Bedrock (Nova Pro, Cohere embed-v4), Qdrant, S3, Transcribe, Lambda
- Local development uses the same code paths with file system access instead of S3

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.5", "2.1", "2.2"] },
    { "id": 3, "tasks": ["2.3", "4.1", "4.2"] },
    { "id": 4, "tasks": ["4.3", "4.4", "5.1", "5.2"] },
    { "id": 5, "tasks": ["5.3", "6.1", "6.2"] },
    { "id": 6, "tasks": ["5.4", "5.5", "6.3"] },
    { "id": 7, "tasks": ["6.4", "6.5", "8.1", "8.2"] },
    { "id": 8, "tasks": ["8.3", "9.1"] },
    { "id": 9, "tasks": ["8.4", "8.5", "9.2"] },
    { "id": 10, "tasks": ["9.3", "10.1", "10.2"] },
    { "id": 11, "tasks": ["10.3", "10.4"] },
    { "id": 12, "tasks": ["12.1"] },
    { "id": 13, "tasks": ["12.2", "12.3"] }
  ]
}
```

# Requirements Document

## Introduction

This document specifies requirements for a multi-modal content compliance pipeline serving the Malaysia and Singapore advertising markets. The system extends the existing culture_compliance module to support actual image file analysis, video frame extraction and understanding, dual-market regulatory guidelines, and orchestrated multi-step pipelines. The system must run locally for testing and be deployable to AWS Lambda for production use with a React frontend.

## Glossary

- **Compliance_Pipeline**: The orchestration system that routes content through the appropriate processing steps based on content type and target market
- **Text_Pipeline**: The processing path for text-based content (ad copy, scripts, transcripts) that evaluates cultural compliance via LLM
- **Image_Pipeline**: The processing path for image files that extracts visual understanding and text-in-image before compliance evaluation
- **Video_Pipeline**: The processing path for video files that extracts frames, transcribes audio, and analyzes visual content before compliance evaluation
- **Frame_Extractor**: The component that samples representative frames from a video file at configurable intervals
- **Video_Understanding_Model**: Amazon Nova Reel or Pegasus model used to analyze video content semantically
- **Vision_Model**: A multi-modal LLM (Claude 3 via Bedrock) capable of analyzing image content directly
- **OCR_Extractor**: The component that extracts text embedded within images (overlays, signage, captions)
- **Audio_Transcriber**: The component that converts video audio tracks into text transcripts (Amazon Transcribe)
- **Guideline_Store**: The Qdrant vector store containing regulatory guidelines for RAG retrieval
- **Compliance_Result**: The structured output containing risk level, score, indicators, explanation, and suggestions
- **Market**: A target regulatory jurisdiction — either Malaysia (MCMC guidelines) or Singapore (IMDA/ASAS guidelines)
- **Orchestrator**: The framework component (LangGraph) that manages multi-step pipeline execution with state and conditional routing
- **Content_Submission**: A request containing the content file or text, content type, and target market for evaluation

## Requirements

### Requirement 1: Content Type Routing

**User Story:** As a content reviewer, I want the system to automatically detect and route content to the appropriate pipeline, so that each content type receives specialized processing.

#### Acceptance Criteria

1. WHEN a Content_Submission with content_type "text" is received, THE Compliance_Pipeline SHALL route it to the Text_Pipeline and return a Compliance_Result with content_type set to "text"
2. WHEN a Content_Submission with content_type "image" is received, THE Compliance_Pipeline SHALL route it to the Image_Pipeline and return a Compliance_Result with content_type set to "image"
3. WHEN a Content_Submission with content_type "video" is received, THE Compliance_Pipeline SHALL route it to the Video_Pipeline and return a Compliance_Result with content_type set to "video"
4. IF a Content_Submission contains an unsupported content_type value, THEN THE Compliance_Pipeline SHALL reject the submission and return an error response listing the supported types ("text", "image", "video")
5. IF a Content_Submission is missing the content_type field or provides a null or empty value, THEN THE Compliance_Pipeline SHALL reject the submission and return a validation error indicating that content_type is required
6. THE Compliance_Pipeline SHALL perform case-sensitive matching on the content_type field, accepting only lowercase values ("text", "image", "video")
7. WHEN a valid Content_Submission is received, THE Compliance_Pipeline SHALL complete the routing decision and begin pipeline processing within 2 seconds

### Requirement 2: Text Pipeline Evaluation

**User Story:** As a content reviewer, I want text content evaluated against market-specific regulatory guidelines, so that I can identify cultural compliance issues in ad copy and scripts.

#### Acceptance Criteria

1. WHEN text content is submitted, THE Text_Pipeline SHALL retrieve the top 5 regulatory guidelines ranked by vector similarity from the Guideline_Store for the specified Market
2. WHEN text content and guidelines are assembled, THE Text_Pipeline SHALL invoke the LLM to produce a Compliance_Result containing RISK level, SCORE (0-100), high_risk_indicators (array of up to 10 flagged items ranked by severity), explanation, and suggestion
3. THE Text_Pipeline SHALL use the scoring method: start from 100, apply category-weighted penalties (Religious Sensitivity: 30, Ethnic/Racial: 20, Sexual/Explicit: 15, Political/State: 15, LGBTQ: 10, Profanity: 10) with severity multipliers: No issues = 0, Minor = 0.25 × weight, Moderate = 0.6 × weight, Severe = 1.0 × weight
4. THE Text_Pipeline SHALL map scores to risk levels: SCORE >= 75 is "Low", 40 <= SCORE < 75 is "Medium", SCORE < 40 is "High"
5. IF the text content is empty or contains only whitespace, THEN THE Text_Pipeline SHALL return a validation error indicating that non-empty text content is required
6. IF the Guideline_Store is unreachable or returns no results, THEN THE Text_Pipeline SHALL return an error indicating that guideline retrieval failed and compliance evaluation cannot proceed
7. IF the LLM invocation fails or returns an unparseable response, THEN THE Text_Pipeline SHALL return an error indicating that the compliance evaluation could not be completed

### Requirement 3: Image Pipeline Processing

**User Story:** As a content reviewer, I want image files analyzed for visual content and embedded text, so that I can identify compliance issues in visual advertisements.

#### Acceptance Criteria

1. WHEN an image file is submitted, THE Image_Pipeline SHALL send the image to the Vision_Model for visual content understanding
2. WHEN an image file is submitted, THE Image_Pipeline SHALL invoke the OCR_Extractor to extract any text embedded in the image (overlays, signage, captions, watermarks)
3. WHEN visual understanding and OCR results are obtained, THE Image_Pipeline SHALL combine them into a unified content description containing a summary of visual elements and all extracted text segments
4. WHEN the unified content description is assembled, THE Image_Pipeline SHALL retrieve relevant guidelines from the Guideline_Store for the Market specified in the Content_Submission and produce a Compliance_Result using the same scoring method and risk-level mapping as the Text_Pipeline
5. THE Image_Pipeline SHALL accept image files in JPEG, PNG, and WebP formats with a minimum resolution of 50x50 pixels
6. IF an image file exceeds 5 MB, THEN THE Image_Pipeline SHALL return an error indicating the maximum file size and reject the submission without further processing
7. IF an image file is not in JPEG, PNG, or WebP format, THEN THE Image_Pipeline SHALL return an error indicating the supported formats and reject the submission
8. IF the Vision_Model is unavailable or returns an error, THEN THE Image_Pipeline SHALL include a warning in the Compliance_Result and produce a result based on OCR-extracted text only
9. IF the OCR_Extractor is unavailable or returns an error, THEN THE Image_Pipeline SHALL include a warning in the Compliance_Result and produce a result based on visual understanding only

### Requirement 4: Video Pipeline Processing

**User Story:** As a content reviewer, I want video files analyzed for visual frames, audio content, and on-screen text, so that I can identify compliance issues across all modalities of a video advertisement.

#### Acceptance Criteria

1. WHEN a video file is submitted, THE Frame_Extractor SHALL sample frames at a configurable interval between 0.5 and 5 seconds (default: 1 frame per second)
2. WHEN a video file is submitted, THE Audio_Transcriber SHALL extract and transcribe the audio track into text with segment-level timestamps (start and end time per spoken segment)
3. WHEN frames are extracted, THE Video_Understanding_Model SHALL analyze the visual content of sampled frames and produce a per-frame description including detected objects, scene context, and any on-screen text (overlays, signage, captions)
4. WHEN frame analysis, audio transcript, and any on-screen text are obtained, THE Video_Pipeline SHALL combine them into a unified content description ordered chronologically by timestamp
5. WHEN the unified content description is assembled, THE Video_Pipeline SHALL retrieve relevant guidelines from the Guideline_Store and produce a Compliance_Result with timestamped high_risk_indicators for each identified violation (timestamp in "MM:SS" format as specified in Requirement 10)
6. THE Video_Pipeline SHALL accept video files in MP4, MOV, and WebM formats with a maximum duration of 5 minutes
7. IF a video file exceeds 100 MB, THEN THE Video_Pipeline SHALL return an error indicating the maximum file size
8. IF the Video_Understanding_Model is unavailable, THEN THE Video_Pipeline SHALL fall back to frame-by-frame analysis using the Vision_Model
9. IF the submitted video file contains no audio track, THEN THE Audio_Transcriber SHALL skip transcription and THE Video_Pipeline SHALL proceed with visual analysis only
10. IF the Audio_Transcriber fails to process the audio track, THEN THE Video_Pipeline SHALL continue processing with visual-only analysis and include a warning in the Compliance_Result warnings array

### Requirement 5: Multi-Market Regulatory Support

**User Story:** As a content reviewer, I want to evaluate content against Malaysia or Singapore regulations, so that I can ensure compliance for the correct target market.

#### Acceptance Criteria

1. WHEN a Content_Submission specifies market "malaysia" (case-insensitive), THE Compliance_Pipeline SHALL retrieve guidelines from the MCMC regulatory collection in the Guideline_Store
2. WHEN a Content_Submission specifies market "singapore" (case-insensitive), THE Compliance_Pipeline SHALL retrieve guidelines from the IMDA/ASAS regulatory collection in the Guideline_Store
3. THE Guideline_Store SHALL maintain separate vector collections for Malaysia (MCMC) and Singapore (IMDA/ASAS) guidelines
4. WHEN no market is specified in a Content_Submission, THE Compliance_Pipeline SHALL default to evaluating against the Malaysia market
5. THE Compliance_Pipeline SHALL apply the scoring categories and weights defined for the evaluated market: Malaysia weights as specified in Requirement 2 (Religious Sensitivity: 30, Ethnic/Racial: 20, Sexual/Explicit: 15, Political/State: 15, LGBTQ: 10, Profanity: 10) and Singapore weights as specified in Requirement 6 (Racial/Religious Harmony: 30, Public Morals: 20, National Interest: 15, Consumer Protection: 15, Decency: 10, Social Responsibility: 10)
6. IF a Content_Submission specifies a market value other than "malaysia" or "singapore", THEN THE Compliance_Pipeline SHALL return an error indicating the supported markets ("malaysia", "singapore")

### Requirement 6: Singapore Regulatory Guidelines

**User Story:** As a content reviewer, I want Singapore-specific advertising guidelines ingested into the system, so that I can evaluate content for the Singapore market.

#### Acceptance Criteria

1. THE Guideline_Store SHALL contain Singapore IMDA (Infocomm Media Development Authority) advertising guidelines with at least 5 entries per topic covering: racial and religious harmony, public morals, national interest, and consumer protection
2. THE Guideline_Store SHALL contain Singapore ASAS (Advertising Standards Authority of Singapore) code provisions with at least 5 entries per topic covering: decency, honesty, social responsibility, and product categories (alcohol, health supplements, financial services, food and beverage)
3. WHEN Singapore guidelines are ingested, THE Guideline_Store SHALL embed them using the same embedding model (Cohere embed-v4) with 1024 dimensions and store them in a dedicated collection named "singapore-imda-asas-guidelines"
4. THE Singapore scoring categories SHALL include: Racial/Religious Harmony (weight 30), Public Morals (weight 20), National Interest (weight 15), Consumer Protection (weight 15), Decency (weight 10), Social Responsibility (weight 10) — applied as penalty deductions from a starting score of 100
5. WHEN Singapore guidelines are ingested, THE Guideline_Store SHALL store each guideline entry with payload metadata including: source authority (IMDA or ASAS), topic category, and the original guideline text
6. IF the Singapore guidelines CSV file is not found or is empty, THEN THE Guideline_Store SHALL return an error indicating the file path and reason for failure without creating or modifying the collection

### Requirement 7: Pipeline Orchestration with LangGraph

**User Story:** As a developer, I want the multi-step pipeline orchestrated with LangGraph, so that I have explicit state management, conditional routing, and the ability to add human-in-the-loop review later.

#### Acceptance Criteria

1. THE Orchestrator SHALL use LangGraph to define the pipeline as a directed graph with at minimum the following nodes: content_routing, guideline_retrieval, compliance_evaluation, and result_formatting
2. THE Orchestrator SHALL maintain pipeline state as a typed state object containing: input content, content_type, target market, intermediate results from each completed node, error information (if any), and final Compliance_Result output
3. WHEN a pipeline step fails, THE Orchestrator SHALL capture the error details (failed node name, error type, and error description) in the state object and route to an error-handling node that returns a partial Compliance_Result with a warnings array indicating which step failed
4. IF a pipeline step fails and the failure is due to a transient error (network timeout, service throttling), THEN THE Orchestrator SHALL retry the step up to 2 times with exponential backoff before routing to the error-handling node
5. THE Orchestrator SHALL support conditional edges that route content to different processing nodes (Text_Pipeline, Image_Pipeline, or Video_Pipeline) based on the content_type field in the state object
6. THE Orchestrator SHALL be stateless between invocations to support AWS Lambda deployment (no in-memory state persisted across requests) — each invocation SHALL construct a new graph instance from the state object
7. THE Orchestrator SHALL complete full graph execution within 55 seconds for text and image content, and within 120 seconds for video content, to remain within API Gateway and Lambda timeout constraints

### Requirement 8: AWS Lambda Compatibility

**User Story:** As a developer, I want the pipeline designed for AWS Lambda deployment, so that it can serve the React frontend in production without managing servers.

#### Acceptance Criteria

1. THE Compliance_Pipeline SHALL operate within AWS Lambda constraints: maximum 15-minute timeout, 10 GB memory, 512 MB /tmp storage
2. THE Compliance_Pipeline SHALL be stateless — each invocation SHALL process a single Content_Submission independently, and SHALL remove any temporary files written to /tmp before returning a response
3. WHEN processing video files on Lambda, THE Video_Pipeline SHALL use pre-signed S3 URLs for input rather than direct file upload to stay within payload limits (6 MB synchronous, 256 KB for async invocation)
4. THE Compliance_Pipeline SHALL package all dependencies within the Lambda deployment artifact or use Lambda layers for large dependencies (ffmpeg, opencv)
5. IF a pipeline execution exceeds the configured timeout threshold (default: 60 seconds for synchronous API Gateway), THEN THE Compliance_Pipeline SHALL return a Compliance_Result with risk_level set to "Unknown", a score of -1, an empty high_risk_indicators array, and an explanation indicating which pipeline steps completed and which were not reached
6. WHEN a Content_Submission for text or image content is received via API Gateway, THE Compliance_Pipeline SHALL return a complete Compliance_Result within 30 seconds including Lambda cold start time
7. WHEN a Content_Submission for video content is received, THE Compliance_Pipeline SHALL be invoked asynchronously and SHALL store the Compliance_Result in S3 at a predictable key derived from the submission identifier

### Requirement 9: Local Testing Support

**User Story:** As a developer, I want to run the full pipeline locally for testing and development, so that I can iterate without deploying to AWS.

#### Acceptance Criteria

1. THE Compliance_Pipeline SHALL support local execution via a CLI command that accepts the same input schema (content, content_type, and market) and returns the same Compliance_Result output schema as the Lambda handler
2. WHEN running locally, THE Video_Pipeline SHALL read video files directly from the local filesystem (e.g., "backend/culture_compliance/Test Video.mp4") instead of requiring pre-signed S3 URLs
3. WHEN running locally, THE Compliance_Pipeline SHALL load AWS Bedrock credentials and Qdrant connection parameters from environment variables, using the same variable names as the deployed version
4. IF a required environment variable (AWS credentials, QDRANT_URL, or QDRANT_API_KEY) is not set when running locally, THEN THE Compliance_Pipeline SHALL exit with an error message identifying each missing variable by name
5. THE Compliance_Pipeline SHALL provide a test script that exercises all three pipelines (text, image, video) with at least one sample input per content type and reports a pass/fail result for each pipeline based on whether a valid Compliance_Result is returned without errors
6. WHEN running locally, THE Compliance_Pipeline SHALL log intermediate pipeline steps to stdout, including: guidelines retrieved (collection name and number of chunks), model invocations (model ID and response time in milliseconds), and total pipeline duration in milliseconds

### Requirement 10: Structured Compliance Result Output with Precise Issue Localization

**User Story:** As a frontend developer, I want compliance results to pinpoint exactly where issues occur in the content, so that reviewers can immediately see what needs fixing without re-reading the entire piece.

#### Acceptance Criteria

1. THE Compliance_Pipeline SHALL return a Compliance_Result containing: content_type, market, risk_level (one of "High", "Medium", "Low"), score (integer 0-100), high_risk_indicators (array of localized issue objects, maximum 10 items), explanation (string, maximum 500 characters), and suggestion (string, maximum 400 characters)
2. WHEN processing text content, each high_risk_indicator SHALL include: the exact problematic phrase (verbatim substring from the input, maximum 200 characters), its 0-based character offset position in the original text, the violation category (one of: "Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit", "Political/State", "LGBTQ", "Profanity"), and severity level (one of: "Severe", "Moderate", "Minor") — enabling the frontend to highlight the flagged words inline
3. WHEN processing video content, each high_risk_indicator SHALL include: a timestamp (format "HH:MM:SS" for videos 60 minutes or longer, "MM:SS" for videos under 60 minutes), a description of what is happening at that moment (maximum 200 characters), the violation category (one of: "Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit", "Political/State", "LGBTQ", "Profanity"), and severity level (one of: "Severe", "Moderate", "Minor") — enabling the frontend to link directly to the problematic moment in the video
4. WHEN processing image content, each high_risk_indicator SHALL include: a bounding box (x, y, width, height each as a percentage of image dimensions ranging from 0 to 100), a description of the flagged visual element (maximum 200 characters), the violation category (one of: "Religious Sensitivity", "Ethnic/Racial", "Sexual/Explicit", "Political/State", "LGBTQ", "Profanity"), and severity level (one of: "Severe", "Moderate", "Minor") — enabling the frontend to render a highlight overlay on the problematic region
5. THE Compliance_Result SHALL include a processing_metadata field containing: pipeline_duration_ms (integer), models_used (array of model IDs invoked), and market evaluated
6. IF any pipeline step produces a partial failure (a step returns an error but at least one other step completes successfully), THEN THE Compliance_Result SHALL include a warnings array where each entry identifies the failed step name, a description of the failure, and whether the overall result may be incomplete due to the failure
7. WHEN no compliance issues are detected, THE Compliance_Pipeline SHALL return a Compliance_Result with an empty high_risk_indicators array, a score of 100, and risk_level "Low"

### Requirement 11: Parse and Format Compliance Result

**User Story:** As a developer, I want reliable serialization and deserialization of compliance results, so that results can be stored, transmitted, and reconstructed without data loss.

#### Acceptance Criteria

1. THE Compliance_Pipeline SHALL serialize Compliance_Result objects to UTF-8 encoded JSON format for API responses, preserving all non-ASCII characters (e.g., Malay, Chinese, Tamil text) without escaping them into ASCII sequences
2. THE Compliance_Pipeline SHALL deserialize JSON payloads into Compliance_Result objects using Pydantic models, validating that all required fields defined in Requirement 10 are present and that field values conform to their declared types and constraints (score: integer 0-100, risk_level: one of "High", "Medium", "Low", content_type: one of "text", "image", "video", high_risk_indicators: array)
3. WHEN a valid Compliance_Result object is serialized to JSON and the resulting JSON is deserialized back, THE Compliance_Pipeline SHALL produce an object where every field value is equal in type and content to the original (round-trip identity)
4. IF a JSON payload is missing required fields, THEN THE Compliance_Pipeline SHALL return a validation error listing each missing field by name
5. IF a JSON payload contains fields with values that violate type or constraint rules (e.g., score outside 0-100, unrecognized risk_level), THEN THE Compliance_Pipeline SHALL return a validation error identifying the invalid field and the constraint that was violated
6. IF a JSON payload is not syntactically valid JSON, THEN THE Compliance_Pipeline SHALL return a validation error indicating the payload could not be parsed
7. THE Compliance_Pipeline SHALL reject JSON payloads exceeding 1 MB in size and return an error indicating the maximum allowed size

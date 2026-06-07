# Implementation Plan: JusAds Video Compliance Remediation Pipeline

## Overview

This plan implements the JusAds Video Compliance Remediation Pipeline as a Python FastAPI application. The pipeline wraps the existing `culture_compliance` module, adds visual remediation (FFmpeg + Nano Banana + Google Veo), audio remediation (ElevenLabs TTS), an orchestrator for composing the final video, a FastAPI server, and a single-page frontend. Tasks are ordered to build foundational data models first, then core components, then integration and wiring.

## Tasks

- [x] 1. Set up project structure and data models
  - [x] 1.1 Create the module directory structure and shared data models
    - Create `backend/jusads_video_compliance/` package with `__init__.py`
    - Create `backend/jusads_video_compliance/models.py` with dataclasses: `Violation`, `ComplianceCheckResult`, `VoiceConfig`, `VisualRemediationResult`, `AudioRemediationResult`, `ProcessLogEntry`, `RemediationResult`
    - Include all validation rules from the design (timestamp bounds, severity enum, violation_type enum, etc.)
    - _Requirements: 1.5, 1.6, 2.6, 3.4, 4.3, 6.1, 6.5_

  - [ ]* 1.2 Write property tests for data model validation
    - **Property 16: Compliance score is always in valid range**
    - **Property 9: Compliance score and risk level consistency**
    - Test that `ComplianceCheckResult` enforces score in [0, 100] and risk_level matches score thresholds
    - **Validates: Requirements 1.3, 1.4**

- [x] 2. Implement Compliance Checker
  - [x] 2.1 Implement `compliance_checker.py` wrapping the existing culture_compliance pipeline
    - Create `backend/jusads_video_compliance/compliance_checker.py`
    - Implement `check_compliance()` async function that invokes `culture_compliance.orchestrator.run_pipeline()`
    - Parse `high_risk_indicators` into `Violation` objects with timestamp conversion (MM:SS → float seconds)
    - Determine `violation_type` (visual vs audio) from category and description
    - Compute risk_level from score (>=75 → "Low", 40-74 → "Medium", <40 → "High")
    - Enforce max 10 violations, validate all timestamps within video duration
    - Handle pipeline timeout (120 seconds) and errors gracefully
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 2.2 Write property test for score-to-risk-level mapping
    - **Property 9: Compliance score and risk level consistency**
    - For any score in [0, 100], verify the risk_level classification is correct
    - **Validates: Requirements 1.3, 1.4**

  - [ ]* 2.3 Write unit tests for compliance checker
    - Test timestamp parsing (MM:SS → float)
    - Test violation_type classification logic
    - Test error handling when pipeline times out or fails
    - Mock the culture_compliance pipeline
    - _Requirements: 1.5, 1.7_

- [x] 3. Implement Voice Selection
  - [x] 3.1 Implement voice selection logic in `audio_remediator.py`
    - Create `backend/jusads_video_compliance/audio_remediator.py`
    - Implement `select_voice()` function with the VOICE_MAP and LANGUAGE_CODE_MAP from design
    - Support Malaysia (Malay, Chinese, Indian) and Singapore (English, Chinese) markets
    - Implement case-insensitive lookup for market, ethnicity, and gender
    - Default to "female" gender when not specified
    - Fall back to default voice (Malaysia Malay Female) when no exact match found
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 3.2 Write property test for voice selection completeness
    - **Property 5: Voice selection always returns a valid voice for supported markets**
    - For all supported (market, ethnicity, gender) combinations, verify non-empty voice_id and correct language_code
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [x] 4. Checkpoint - Ensure data models and voice selection tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Visual Remediator
  - [x] 5.1 Implement frame extraction and speed adjustment utilities
    - Implement `extract_frame()` using FFmpeg subprocess to extract PNG at a given timestamp
    - Implement `speed_adjust_clip()` using FFmpeg to speed up a clip by a given factor
    - Handle FFmpeg errors (non-zero exit code, missing output file)
    - _Requirements: 2.1, 2.5, 2.7_

  - [x] 5.2 Implement Nano Banana and Google Veo integration
    - Create `backend/jusads_video_compliance/visual_remediator.py`
    - Implement `regenerate_frame()` calling Nano Banana API with compliance-specific prompt
    - Implement `generate_replacement_clip()` calling Google Veo via Vertex AI with two reference images
    - Enforce Veo minimum duration of 4.0 seconds using `max(4.0, segment_duration)`
    - Handle API failures gracefully (return failed result, preserve original)
    - _Requirements: 2.2, 2.3, 2.4, 2.8_

  - [x] 5.3 Implement `remediate_visual_segment()` orchestrating the full visual fix flow
    - Combine frame extraction → Nano Banana regeneration → Veo clip generation → speed adjustment
    - Validate segment duration > 0, reject invalid time ranges
    - Apply speed factor when segment < 4 seconds (factor = 4.0 / segment_duration)
    - Return `VisualRemediationResult` with success/failure status
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.9_

  - [ ]* 5.4 Write property tests for visual remediation logic
    - **Property 3: Veo generation duration is always at least 4 seconds**
    - **Property 4: Speed factor is correct when segment is shorter than 4 seconds**
    - Test with generated segment durations (0.5s to 10s range)
    - **Validates: Requirements 2.4, 2.5**

- [x] 6. Implement Audio Remediator
  - [x] 6.1 Implement audio extraction and ElevenLabs TTS integration
    - Implement `extract_audio_segment()` using FFmpeg to extract audio between timestamps
    - Implement `regenerate_with_elevenlabs()` calling ElevenLabs TTS API with selected voice
    - Match replacement duration to original segment (trim or pad with silence, ±0.2s tolerance)
    - Handle ElevenLabs API failures and FFmpeg extraction failures gracefully
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 6.2 Implement `remediate_audio_segment()` orchestrating the full audio fix flow
    - Combine voice selection → audio extraction → TTS regeneration → duration matching
    - Use replacement_text if provided, otherwise use transcription of original segment
    - Record fallback decisions in process log when default voice is used
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [ ]* 6.3 Write unit tests for audio remediator
    - Test audio extraction with mocked FFmpeg
    - Test duration matching (trim and pad scenarios)
    - Test fallback voice selection when no exact match
    - _Requirements: 3.4, 3.5, 3.6, 3.7_

- [x] 7. Checkpoint - Ensure visual and audio remediator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Remediation Orchestrator
  - [x] 8.1 Implement violation separation, sorting, and orchestration logic
    - Create `backend/jusads_video_compliance/orchestrator.py`
    - Implement `orchestrate_remediation()` that separates violations into visual/audio categories
    - Sort each category by `timestamp_start` ascending
    - Validate non-overlapping visual segments (reject if overlapping)
    - Invoke `remediate_visual_segment()` for each visual violation in order
    - Invoke `remediate_audio_segment()` for each audio violation in order
    - Continue processing remaining violations when individual steps fail
    - _Requirements: 5.1, 5.2, 5.3, 5.7, 5.9, 5.10, 10.2_

  - [-] 8.2 Implement `compose_final_video()` for stitching replacements into original
    - Build timeline of original segments and replacement clips
    - Use FFmpeg concat/filter to stitch visual replacements at correct positions
    - Overlay audio replacements onto original audio track
    - Preserve original audio for segments without audio violations
    - Ensure final video duration matches original (±0.5s tolerance)
    - Handle composition failure (return partial result with individual clips)
    - _Requirements: 5.4, 5.5, 5.6, 5.8_

  - [-] 8.3 Implement process log generation
    - Create `ProcessLogEntry` for every remediation action attempted
    - Record ISO 8601 timestamps, action types, details, duration_ms, and success status
    - Ensure entries are ordered chronologically
    - Include `compose_final` as last entry with segments_replaced count and output path
    - Calculate `total_processing_time_ms` as sum of all entry durations
    - Record failures with error descriptions
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 8.4 Write property tests for orchestrator
    - **Property 6: Process log has at least one entry per violation attempted**
    - **Property 7: Non-overlapping violations produce non-overlapping replacements**
    - **Property 11: Violations fixed plus violations failed equals total violations**
    - **Property 12: Orchestrator continues processing after individual failures**
    - **Property 13: Violation separation and sorting correctness**
    - **Property 14: Process log entries are in chronological order**
    - **Validates: Requirements 5.1, 5.7, 6.1, 6.2, 6.3, 10.2, 10.4**

- [ ] 9. Checkpoint - Ensure orchestrator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement FastAPI Server
  - [ ] 10.1 Implement input validation and file handling utilities
    - Create `backend/jusads_video_compliance/validation.py`
    - Implement magic byte validation for MP4, MOV, and WebM files
    - Implement file size validation (reject > 100MB)
    - Implement parameter validation (market, ethnicity, age_group, language against allowed values)
    - Implement UUID-based temporary directory creation for file operations
    - Implement temp file cleanup (delete intermediates within 60 seconds after job completion)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ] 10.2 Implement FastAPI endpoints (`main.py`)
    - Create `backend/jusads_video_compliance/main.py` with FastAPI app
    - Implement `POST /api/check` — accept video upload + market params, invoke compliance checker, return violations/risk/score
    - Implement `POST /api/remediate` — accept video path + violations + params, invoke orchestrator, return final video path + process log
    - Implement `GET /api/status/{job_id}` — return job status (queued/processing/completed/failed) with progress percentage
    - Return 404 error for unknown job_id
    - Serve static frontend files
    - Load API keys from environment variables, never expose in responses
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 9.8_

  - [ ]* 10.3 Write property test for input validation
    - **Property 15: Input validation rejects invalid market parameters**
    - For any string not in {"malaysia", "singapore"}, verify API returns validation error
    - **Validates: Requirements 7.4, 9.4, 9.5**

  - [ ]* 10.4 Write unit tests for API endpoints
    - Test file upload with valid and invalid magic bytes
    - Test parameter validation rejection messages
    - Test job status endpoint with valid and invalid job_ids
    - Mock compliance checker and orchestrator
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.8_

- [ ] 11. Implement Frontend
  - [ ] 11.1 Create the single-page frontend (`frontend/index.html`)
    - Create `backend/frontend/index.html` with vanilla HTML/CSS/JS
    - Implement dropdown controls for market (Malaysia, Singapore), ethnicity (Malay, Chinese, Indian, All), age group (All Ages, Adults Only, Children), and language (Malay, Chinese, English)
    - Implement video file upload area with drag-and-drop support (accept MP4, MOV, WebM, max 100MB)
    - Display accepted file types and size limit to user
    - Implement "Check Compliance" button that disables on click, shows loading indicator, calls `/api/check`
    - Display violations in a table (timestamps, categories, severity) on success
    - Show "Remediate" button when violations are present, hide when video is compliant
    - Display "Video is compliant" message when zero violations returned
    - Implement "Remediate" button that calls `/api/remediate`
    - Display process log in scrollable panel (action type, duration, success/failure status)
    - Display video preview player and download link on successful remediation
    - Display error messages on API failures and re-enable action buttons
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

- [ ] 12. Integration wiring and final composition
  - [ ] 12.1 Wire all components together and configure static file serving
    - Connect FastAPI server to serve `frontend/index.html` as static files
    - Ensure compliance checker → orchestrator → remediators flow is properly wired
    - Configure CORS middleware for frontend origin
    - Verify environment variable loading for all API keys (ElevenLabs, Vertex AI, Nano Banana)
    - Add proper error propagation from components to API responses
    - _Requirements: 7.7, 9.8, 10.1, 10.3_

  - [ ]* 12.2 Write integration tests for end-to-end pipeline
    - Test full flow: upload → compliance check → remediation → final video
    - Verify process log completeness and correctness
    - Test error scenarios (API failures, invalid inputs)
    - Mock external APIs (Veo, Nano Banana, ElevenLabs) for deterministic testing
    - **Property 1: Remediated video preserves total duration**
    - **Property 2: All visual replacements fit exactly in their target segment**
    - **Property 10: Original video file is never modified**
    - **Validates: Requirements 5.6, 2.6, 10.1**

- [ ] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with FastAPI, FFmpeg (subprocess), and existing API clients
- All external API calls (Veo, Nano Banana, ElevenLabs) should be mocked in tests
- The existing `culture_compliance` module is wrapped, not modified

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "2.1", "3.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.2"] },
    { "id": 3, "tasks": ["5.1", "5.2", "6.1"] },
    { "id": 4, "tasks": ["5.3", "5.4", "6.2"] },
    { "id": 5, "tasks": ["6.3", "8.1"] },
    { "id": 6, "tasks": ["8.2", "8.3"] },
    { "id": 7, "tasks": ["8.4"] },
    { "id": 8, "tasks": ["10.1"] },
    { "id": 9, "tasks": ["10.2", "10.3"] },
    { "id": 10, "tasks": ["10.4", "11.1"] },
    { "id": 11, "tasks": ["12.1"] },
    { "id": 12, "tasks": ["12.2"] }
  ]
}
```

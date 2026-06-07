# Requirements Document

## Introduction

The JusAds Video Compliance Remediation Pipeline is an automated system that receives a video advertisement, checks it against market-specific cultural and regulatory compliance rules (using the existing `culture_compliance` pipeline), and automatically remediates any visual or audio violations. Visual violations are fixed by extracting boundary frames, regenerating them with Nano Banana (image generation), and stitching a replacement clip via Google Veo (video generation). Audio violations are fixed by regenerating the problematic audio segment using ElevenLabs TTS with market-appropriate voice selection. The system produces a structured process log for every run and exposes a single-page frontend for upload, compliance checking, remediation, and log display.

## Glossary

- **Pipeline**: The end-to-end automated workflow from video upload through compliance checking to remediation output
- **Compliance_Checker**: The component that wraps the existing culture_compliance pipeline and returns structured violation data with timestamps
- **Visual_Remediator**: The component responsible for fixing visual violations using frame extraction, Nano Banana image generation, and Google Veo video generation
- **Audio_Remediator**: The component responsible for fixing audio violations using ElevenLabs TTS with market-appropriate voice selection
- **Orchestrator**: The component that coordinates the full remediation workflow, invokes remediators, composes the final video, and builds the process log
- **API_Server**: The FastAPI HTTP server exposing compliance check and remediation endpoints
- **Frontend**: The single index.html page providing upload, compliance check, remediation trigger, and process log display
- **Violation**: A detected non-compliance issue with precise timestamps, category, severity, type (visual/audio), and guideline source
- **Process_Log**: A structured, user-facing report detailing every action taken during remediation with timestamps, durations, and outcomes
- **Nano_Banana**: The image generation API used to regenerate compliant versions of extracted video frames
- **Google_Veo**: The video generation API (via Vertex AI) used to create replacement video clips from two reference images
- **ElevenLabs_TTS**: The text-to-speech API used to regenerate compliant audio segments
- **Voice_Config**: A configuration object mapping market, ethnicity, and language to a specific ElevenLabs voice ID
- **Boundary_Frames**: The first and last frames of a violation segment, extracted for use as reference images in regeneration
- **Speed_Factor**: The multiplier applied to a Veo-generated clip when the target segment is shorter than Veo's 4-second minimum

## Requirements

### Requirement 1: Video Compliance Checking

**User Story:** As an advertiser, I want to upload a video advertisement and check it against market-specific compliance rules, so that I can identify cultural and regulatory violations before publishing.

#### Acceptance Criteria

1. WHEN a user uploads a valid video file (MP4, MOV, or WebM, up to 100MB, up to 5 minutes) with market parameters (market: "malaysia" or "singapore", target_ethnicity: "malay", "chinese", "indian", or "all", and target_age_group: "all_ages", "adults_only", or "children"), THE Compliance_Checker SHALL invoke the existing culture_compliance pipeline and return a ComplianceCheckResult containing a risk level, numeric score, and list of violations (maximum 10 violations)
2. IF the user uploads a file that is not MP4, MOV, or WebM format, or exceeds 100MB in size, or exceeds 5 minutes in duration, THEN THE Compliance_Checker SHALL reject the upload and return an error response indicating which validation constraint was violated
3. WHEN the compliance check completes, THE Compliance_Checker SHALL return a numeric score in the range 0 to 100
4. WHEN the compliance check returns a score of 75 or above, THE Compliance_Checker SHALL classify the risk level as "Low"; WHEN the score is between 40 and 74 inclusive, THE Compliance_Checker SHALL classify the risk level as "Medium"; WHEN the score is below 40, THE Compliance_Checker SHALL classify the risk level as "High"
5. WHEN violations are detected, THE Compliance_Checker SHALL return each violation with a timestamp_start, timestamp_end, category, severity ("Severe", "Moderate", or "Minor"), description (maximum 200 characters), violation_type ("visual" or "audio"), and guideline_source ("regulatory" or "cultural")
6. WHEN the compliance check returns violations, THE Compliance_Checker SHALL ensure all violation timestamps (timestamp_start and timestamp_end) are within the video duration bounds, with timestamp_start >= 0 and timestamp_end <= video duration, and timestamp_start < timestamp_end
7. IF the culture_compliance pipeline returns an error or does not respond within 120 seconds, THEN THE Compliance_Checker SHALL return an error response containing the error type and descriptive message, and not attempt remediation

### Requirement 2: Visual Violation Remediation

**User Story:** As an advertiser, I want visual violations in my video to be automatically fixed by regenerating the offending segments, so that I can produce a compliant video without manual editing.

#### Acceptance Criteria

1. WHEN a visual violation is identified, THE Visual_Remediator SHALL extract the boundary frames as PNG images at the violation start and end timestamps using FFmpeg
2. WHEN boundary frames are extracted, THE Visual_Remediator SHALL regenerate compliant versions of those frames using Nano Banana with a compliance-specific prompt derived from the violation category and description
3. WHEN compliant frames are regenerated, THE Visual_Remediator SHALL generate a replacement video clip in MP4 format using Google Veo with the two regenerated images as start and end reference
4. THE Visual_Remediator SHALL request a Veo generation duration of at least 4.0 seconds (Veo minimum), using max(4.0, segment_duration) as the generation duration
5. WHEN the target segment duration is less than 4 seconds, THE Visual_Remediator SHALL speed-adjust the generated clip using FFmpeg to match the original segment duration, applying a speed factor of 4.0 divided by the segment duration
6. WHEN visual remediation succeeds, THE Visual_Remediator SHALL produce a replacement clip whose duration matches the original segment duration within 0.2 seconds tolerance
7. IF frame extraction fails due to a non-zero FFmpeg exit code or the output PNG file not being created, THEN THE Visual_Remediator SHALL return a failed result with an error description indicating the extraction failure reason and preserve the original video content for that segment
8. IF Nano Banana or Google Veo API calls fail, THEN THE Visual_Remediator SHALL log the failure, mark the remediation as failed, and preserve the original video content for that segment
9. IF the violation segment duration (timestamp_end minus timestamp_start) is less than or equal to 0 seconds, THEN THE Visual_Remediator SHALL reject the violation with an error description indicating an invalid time range and skip remediation for that segment

### Requirement 3: Audio Violation Remediation

**User Story:** As an advertiser, I want audio violations in my video to be automatically fixed by regenerating the problematic audio with a market-appropriate voice, so that the audio content is culturally and regulatory compliant.

#### Acceptance Criteria

1. WHEN an audio violation is identified, THE Audio_Remediator SHALL select the appropriate ElevenLabs voice based on the market, ethnicity, age group, language, and gender parameters using the voice mapping configuration
2. WHEN a voice is selected, THE Audio_Remediator SHALL extract the audio segment bounded by the violation's timestamp_start and timestamp_end from the video using FFmpeg
3. WHEN the audio segment is extracted, THE Audio_Remediator SHALL regenerate the audio using ElevenLabs TTS with the selected voice configuration, using the replacement_text provided for the violation or, if no replacement_text is provided, using the transcription of the original audio segment as input
4. WHEN replacement audio is generated, THE Audio_Remediator SHALL match the duration of the replacement to the original segment duration within a tolerance of 0.2 seconds by trimming excess audio or padding with silence at the end
5. IF no matching voice ID exists for the given market, ethnicity, and language combination, THEN THE Audio_Remediator SHALL fall back to a default voice for the market and record the fallback in the process log
6. IF ElevenLabs TTS returns an error, THEN THE Audio_Remediator SHALL log the failure, mark the audio remediation as failed, and preserve the original audio for that segment
7. IF FFmpeg audio extraction fails for a violation segment, THEN THE Audio_Remediator SHALL mark the audio remediation as failed for that segment, preserve the original audio, and record the extraction failure in the process log

### Requirement 4: Voice Selection

**User Story:** As an advertiser, I want the system to automatically select a culturally appropriate voice for my target market, so that the regenerated audio sounds natural for the intended audience.

#### Acceptance Criteria

1. THE Audio_Remediator SHALL support voice selection for Malaysia market with Malay, Chinese, and Indian ethnicities in both male and female genders
2. THE Audio_Remediator SHALL support voice selection for Singapore market with English and Chinese ethnicities in both male and female genders
3. WHEN a valid market, ethnicity, and gender combination is provided, THE Audio_Remediator SHALL return a VoiceConfig with a non-empty voice_id and the correct language_code for that combination
4. THE Audio_Remediator SHALL map language codes as follows: Malaysia-Malay to "ms", Malaysia-Chinese to "zh", Malaysia-Indian to "en", Singapore-English to "en", and Singapore-Chinese to "zh"
5. IF an invalid market, ethnicity, and gender combination is provided, THEN THE Audio_Remediator SHALL fall back to a default voice configuration rather than failing with an error
6. IF no gender is specified in the voice selection request, THEN THE Audio_Remediator SHALL default to "female" gender for voice selection
7. THE Audio_Remediator SHALL treat market, ethnicity, and gender input values as case-insensitive when performing voice selection lookup

### Requirement 5: Remediation Orchestration

**User Story:** As an advertiser, I want the system to coordinate all remediation steps and produce a single corrected video, so that I receive a complete compliant output without managing individual fixes.

#### Acceptance Criteria

1. WHEN remediation is triggered, THE Orchestrator SHALL separate violations into visual and audio categories and sort each category by timestamp_start in ascending order
2. WHEN visual violations are processed, THE Orchestrator SHALL invoke the Visual_Remediator for each visual violation in ascending timestamp_start order
3. IF audio violations are present, THEN THE Orchestrator SHALL select the voice configuration matching the provided market, ethnicity, age_group, and language parameters and invoke the Audio_Remediator for each audio violation in ascending timestamp_start order
4. WHEN all remediations are complete, THE Orchestrator SHALL compose the final video by splicing successful visual replacements into the original video at their corresponding timestamp_start and timestamp_end positions using FFmpeg
5. WHILE composing the final video, THE Orchestrator SHALL preserve the original audio for all segments where no audio violation was remediated
6. WHEN the final video is composed, THE Orchestrator SHALL produce a video whose total duration matches the original video duration within 0.5 seconds tolerance
7. THE Orchestrator SHALL ensure that visual replacement segments are non-overlapping (the timestamp_end of one replacement is less than or equal to the timestamp_start of the next)
8. IF a video composition step fails, THEN THE Orchestrator SHALL return a partial result containing the individual replacement clips and record the failure in the process log
9. IF an individual visual or audio remediation step fails, THEN THE Orchestrator SHALL skip the failed segment, preserve the original content for that segment in the final video, record the failure in the process log, and continue processing remaining violations
10. IF the violations list contains overlapping visual segments (timestamp_end of one segment exceeds timestamp_start of the next), THEN THE Orchestrator SHALL reject the remediation request and return an error indicating overlapping violations were detected

### Requirement 6: Process Log

**User Story:** As an advertiser, I want a detailed log of every action taken during remediation, so that I can understand what changes were made to my video and verify the process.

#### Acceptance Criteria

1. THE Orchestrator SHALL create a ProcessLogEntry for every remediation action attempted, including the ISO 8601 timestamp, action type (from the supported action types), action-specific details as defined per action type, duration in milliseconds (zero or greater), and success status (true or false)
2. WHEN remediation completes, THE Orchestrator SHALL return a process log containing at least one entry per violation attempted and a total_processing_time_ms value equal to the sum of all entry durations
3. THE Orchestrator SHALL record process log entries ordered by their ISO 8601 timestamp ascending, such that each entry's timestamp is equal to or later than the preceding entry's timestamp
4. WHEN a remediation step fails, THE Orchestrator SHALL include the failure in the process log with success set to false and a details object containing the action type that failed, the violation timestamp range being addressed, and an error description indicating the failure reason
5. THE Process_Log SHALL support the following action types: compliance_check, extract_frame, regenerate_frame, generate_clip, speed_adjust, audio_extract, audio_regenerate, and compose_final
6. WHEN remediation completes, THE Orchestrator SHALL include a compose_final entry as the last entry in the process log, recording the number of segments replaced and the output path

### Requirement 7: API Server

**User Story:** As a frontend developer, I want a REST API that exposes compliance checking and remediation endpoints, so that the frontend can trigger and monitor the pipeline.

#### Acceptance Criteria

1. WHEN a POST request is made to /api/check with a video file and market parameters, THE API_Server SHALL save the uploaded file, invoke the Compliance_Checker, and return the violations, risk level, and score
2. WHEN a POST request is made to /api/remediate with a video path, violations list, and market parameters, THE API_Server SHALL invoke the Orchestrator and return the final video path and process log
3. WHEN a GET request is made to /api/status/{job_id}, THE API_Server SHALL return the current job status as one of "queued", "processing", "completed", or "failed", along with a progress percentage (0 to 100) and, if completed, the final result
4. IF the market parameter is not "malaysia" or "singapore", THEN THE API_Server SHALL reject the request with an error response indicating the invalid parameter name and the allowed values, without invoking any pipeline processing
5. THE API_Server SHALL validate uploaded video files by checking magic bytes (not just file extension) and rejecting files larger than 100MB with an error response indicating the rejection reason (invalid file type or size exceeded)
6. THE API_Server SHALL sanitize all file paths using UUID-based temporary directories to prevent path traversal attacks
7. THE API_Server SHALL serve the static frontend files
8. IF a GET request is made to /api/status/{job_id} with a job_id that does not correspond to any known job, THEN THE API_Server SHALL return an error response indicating the job was not found

### Requirement 8: Frontend Interface

**User Story:** As an advertiser, I want a single-page web interface where I can upload videos, configure market parameters, run compliance checks, trigger remediation, and view the process log, so that I can manage the entire workflow visually.

#### Acceptance Criteria

1. THE Frontend SHALL provide dropdown controls for market (Malaysia, Singapore), ethnicity (Malay, Chinese, Indian, All), age group (All Ages, Adults Only, Children), and language (Malay, Chinese, English) selection
2. THE Frontend SHALL provide a video file upload area with drag-and-drop support that accepts MP4, MOV, and WebM files up to 100MB and displays the accepted file types and size limit to the user
3. WHEN the user clicks "Check Compliance", THE Frontend SHALL disable the button, display a loading indicator, call the /api/check endpoint, and upon success display the violations in a table showing timestamps, categories, and severity
4. WHEN violations are displayed, THE Frontend SHALL show a "Remediate" button that triggers the /api/remediate endpoint
5. WHEN remediation is in progress or complete, THE Frontend SHALL display the process log in a scrollable panel showing each remediation step with its action type, duration, and success or failure status
6. WHEN remediation completes successfully, THE Frontend SHALL display both a video preview player and a download link for the final remediated video
7. IF the compliance check returns zero violations, THEN THE Frontend SHALL display a message indicating the video is compliant and hide the "Remediate" button
8. IF an API call to /api/check or /api/remediate fails, THEN THE Frontend SHALL display an error message indicating the failure reason and re-enable the relevant action button

### Requirement 9: Input Validation and Security

**User Story:** As a system administrator, I want all inputs to be validated and file handling to be secure, so that the system is protected against malicious uploads and injection attacks.

#### Acceptance Criteria

1. THE API_Server SHALL validate that uploaded video files are of type MP4, MOV, or WebM by inspecting file magic bytes (not relying solely on file extension)
2. IF an uploaded file's magic bytes do not match MP4, MOV, or WebM signatures, THEN THE API_Server SHALL reject the request with an error response indicating the file type is not supported and SHALL NOT process the file further
3. IF an uploaded file exceeds 100MB in size, THEN THE API_Server SHALL reject the request with an error response indicating the file size limit has been exceeded
4. THE API_Server SHALL validate that market is one of ("malaysia", "singapore"), ethnicity is one of ("malay", "chinese", "indian", "all"), age_group is one of ("all_ages", "adults_only", "children"), and language is one of ("ms", "zh", "yue", "en-chi", "en-ind", "en")
5. IF any parameter value fails validation, THEN THE API_Server SHALL reject the request with an error response indicating which parameter is invalid and the set of allowed values
6. THE API_Server SHALL use UUID-based temporary directories for all file operations to prevent path traversal
7. THE API_Server SHALL delete all intermediate temporary files (extracted frames, generated clips) within 60 seconds after job completion or failure
8. THE API_Server SHALL load all external API keys from environment variables and never expose them in API responses or frontend-served content

### Requirement 10: Error Handling and Resilience

**User Story:** As an advertiser, I want the system to handle failures gracefully and preserve my original content when fixes cannot be applied, so that I never lose my original video.

#### Acceptance Criteria

1. THE Pipeline SHALL never modify the original uploaded video file; all output is written to new files
2. WHEN any individual remediation step fails, THE Orchestrator SHALL skip that segment, preserve the original content for it, and continue processing remaining violations
3. WHEN a remediation step fails, THE Orchestrator SHALL record the failure in the process log with the error details
4. WHEN all remediation steps are complete, THE Orchestrator SHALL report the count of violations fixed and violations failed in the final result
5. IF the voice selection falls back to a default voice, THEN THE Audio_Remediator SHALL record the fallback decision in the process log

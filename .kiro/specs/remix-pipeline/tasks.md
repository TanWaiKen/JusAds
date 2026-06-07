# Implementation Plan: Remix Pipeline

## Overview

Implement the JusAds Remix Pipeline — the automated remediation system that generates compliant versions of media (text, audio, image, video) after compliance violations are detected. The pipeline is orchestrated as a LangGraph `StateGraph` with human-in-the-loop `interrupt()` calls, following the same patterns used in `langgraph_api.py` (ComplianceState, StateGraph, node functions). It uses `MemorySaver` checkpointer for thread-based state persistence, enabling asynchronous user review and decision routing (accept/reject/regenerate).

## Tasks

- [x] 1. Set up project structure and core data models
  - [x] 1.1 Create the `jusads_remix_pipeline` module directory with `__init__.py` and define violation data models (Pydantic) for all four media types (text, image, audio, video)
    - Create `backend/jusads_remix_pipeline/__init__.py`
    - Create `backend/jusads_remix_pipeline/models.py` with Pydantic models: `TextViolation`, `ImageViolation`, `AudioViolation`, `VideoViolation`, and their respective output schemas (`TextRemixOutput`, `AudioRemixOutput`, `ImageRemixOutput`)
    - Include field validation (max lengths, allowed values for severity/type, non-negative indices)
    - Implement validation that rejects records with missing/invalid fields and returns error messages identifying the invalid fields
    - Validate video violation timestamps (reject start >= end or negative values)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x]* 1.2 Write property tests for violation data models
    - **Property 10: Violation data serialization round-trip**
    - **Property 11: Invalid violations are rejected**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

  - [x] 1.3 Create shared configuration and utility module
    - Create `backend/jusads_remix_pipeline/config.py` with API keys loading, voice mapping tables (market+ethnicity → ElevenLabs voice ID), and cultural rules definitions
    - Define cultural rules for Malay (Malay models only, hijab for females, modest dress) and Chinese (Chinese models only) target audiences
    - Define ethnicity-to-language mapping (Chinese → Mandarin, Malay → Bahasa Malaysia, default → English)
    - _Requirements: 2.3, 3.4, 3.5, 5.2, 5.3, 7.4, 7.6_

  - [x]* 1.4 Write property tests for voice mapping and cultural rules
    - **Property 4: Voice mapping completeness**
    - **Property 5: Cultural rules enforced in generation prompts**
    - **Property 9: Ethnicity-to-language mapping consistency**
    - **Validates: Requirements 2.3, 3.4, 3.5, 5.2, 5.3, 7.4**

- [x] 2. Implement Text Remixer
  - [x] 2.1 Implement the Text_Remixer module
    - Create `backend/jusads_remix_pipeline/text_remixer.py`
    - Implement `remix_text(original_text, violations, target_audience)` function
    - Use Gemini to rewrite text eliminating all violation phrases while preserving brand voice, tone register, and message intent
    - Localize language based on target audience
    - Return `TextRemixOutput` with original_text, compliant_text, and changes list
    - Handle empty violation list (return original unchanged)
    - Skip violation phrases that don't exist in the text
    - Implement 30-second timeout with error handling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x]* 2.2 Write property tests for Text Remixer
    - **Property 1: Text violations are eliminated**
    - **Property 2: No-violation text is identity**
    - **Validates: Requirements 1.1, 1.5**

  - [x]* 2.3 Write unit tests for Text Remixer
    - Test rewriting with single and multiple violations
    - Test empty violation list returns identity
    - Test skipping non-existent violation phrases
    - Test timeout error handling
    - Test localization for Chinese and Malay audiences
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 1.7_

- [x] 3. Implement Audio Remixer
  - [x] 3.1 Implement the Audio_Remixer module
    - Create `backend/jusads_remix_pipeline/audio_remixer.py`
    - Implement `remix_audio(original_transcript, violations, target_audience, original_duration)` function
    - Correct transcript text by replacing all non-compliant phrases
    - Select voice gender based on content context and target audience
    - Map market+ethnicity to ElevenLabs voice using config voice mapping
    - Generate replacement audio via ElevenLabs TTS, matching original duration
    - Return `AudioRemixOutput` with original_transcript, compliant_transcript, audio_path, voice_used
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x]* 3.2 Write property tests for Audio Remixer
    - **Property 3: Audio transcript violations are eliminated**
    - **Validates: Requirements 2.1**

  - [x]* 3.3 Write unit tests for Audio Remixer
    - Test transcript correction with multiple violations
    - Test voice gender selection logic
    - Test voice mapping for different market/ethnicity combinations
    - Test duration matching
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 4. Checkpoint - Core text and audio remixers
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement Image Remixer
  - [x] 5.1 Implement the Image_Remixer module
    - Create `backend/jusads_remix_pipeline/image_remixer.py`
    - Implement `remix_image(image_path, violations, target_audience, option)` function
    - Implement edit option using Gemini Flash Image inpainting with the edit prompt from violations
    - Implement regenerate option using full image generation with original as style reference
    - Apply cultural rules: Malay target → Malay models, hijab, modest dress; Chinese target → Chinese models
    - Return `ImageRemixOutput` with violations, edit_prompt, options, result_image_path
    - Handle empty violations list (return original unchanged)
    - Handle API errors and content filter rejections gracefully
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x]* 5.2 Write property tests for Image Remixer
    - **Property 12: Remix output structure completeness (image)**
    - **Property 13: Image remixer always presents both options**
    - **Validates: Requirements 3.1, 3.6**

  - [x]* 5.3 Write unit tests for Image Remixer
    - Test edit vs regenerate option selection
    - Test cultural rules injection into prompts for Malay and Chinese audiences
    - Test empty violations returns original unchanged
    - Test error handling for API failures
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7, 3.8_

- [x] 6. Implement Video Segment Planner
  - [x] 6.1 Implement the Segment_Planner module
    - Create `backend/jusads_remix_pipeline/segment_planner.py`
    - Implement `plan_segments(violations, video_duration)` function
    - Split segments exceeding 8 seconds into 5-8 second chunks
    - Keep segments between 5-8 seconds as single chunks
    - Flag segments under 5 seconds as short-form generation
    - Preserve compliant sections untouched
    - Return segment plan mapping each chunk to start_time, end_time, source_violation_index, chunk_sequence_number
    - Validate time ranges (reject end <= start)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 6.2 Write property tests for Segment Planner
    - **Property 6: Segment chunking respects 8-second limit**
    - **Property 7: Segment plan targets only non-compliant sections**
    - **Validates: Requirements 4.1, 4.2, 11.2**

  - [x]* 6.3 Write unit tests for Segment Planner
    - Test splitting a 15-second violation into two chunks
    - Test 7-second segment stays as single chunk
    - Test 3-second segment flagged as short-form
    - Test invalid time range rejection
    - Test compliant sections are not included in plan
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 7. Implement Video Storyboard Generator
  - [x] 7.1 Implement the Storyboard_Generator module
    - Create `backend/jusads_remix_pipeline/storyboard_generator.py`
    - Implement `generate_storyboard(chunk, target_audience, brand_context)` function
    - Generate 2-4 key frames per chunk in a single Gemini Flash Image API call (2 frames ≤4s, 3 frames ≤6s, 4 frames ≤8s)
    - Apply cultural rules for target audience in generation prompts
    - Include product packaging, brand logos, and brand color palette in prompts
    - Implement retry logic (up to 2 additional retries on failure)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1, 11.4_

  - [x]* 7.2 Write unit tests for Storyboard Generator
    - Test frame count selection based on chunk duration
    - Test cultural rules included in prompts
    - Test brand context preservation in prompts
    - Test retry logic on API failure
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 11.1, 11.4_

- [x] 8. Implement Video Interpolator
  - [x] 8.1 Implement the Video_Interpolator module
    - Create `backend/jusads_remix_pipeline/video_interpolator.py`
    - Implement `interpolate_video(storyboard_frames, source_segment_path)` function
    - Use Veo 3.1 `reference_images` parameter with `reference_type="asset"` for frame interpolation
    - Generate clips of 5-8 seconds at minimum 24fps
    - Extract and retain original ambient audio/SFX from source segment
    - Ensure no speech audio is generated in the clip
    - Implement retry logic (up to 2 retries) with 120-second timeout
    - Reject requests with fewer than 2 storyboard frames
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [x]* 8.2 Write unit tests for Video Interpolator
    - Test Veo API call configuration with reference_images
    - Test clip duration validation (5-8 seconds)
    - Test rejection of fewer than 2 frames
    - Test retry and timeout logic
    - Test ambient audio extraction
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 9. Checkpoint - Video generation components
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Script and Voiceover Generator
  - [x] 10.1 Implement the Script_Generator module
    - Create `backend/jusads_remix_pipeline/script_generator.py`
    - Implement `generate_script_and_voiceover(remixed_clips, target_audience)` function
    - Analyze visual content of remixed clips to generate localized script with timestamp references
    - Generate timing cues with speech and silence segments (min 1s silence between speech)
    - Select voice gender based on target audience gender demographic
    - Map ethnicity to language (Chinese → Mandarin, Malay → BM, default → English)
    - Generate voiceover via ElevenLabs TTS with segment durations within 500ms of video segments
    - Handle partial failures (preserve successful segments, report failed ones)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [x]* 10.2 Write unit tests for Script Generator
    - Test script generation with timing cues
    - Test ethnicity-to-language mapping
    - Test voice gender selection
    - Test duration matching within 500ms tolerance
    - Test partial failure handling
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 11. Implement Video Composer
  - [x] 11.1 Implement the Video_Composer module
    - Create `backend/jusads_remix_pipeline/video_composer.py`
    - Implement `compose_video(segment_plan, remixed_clips, voiceover_segments, original_video_path)` function
    - Stitch compliant sections and remixed clips in chronological order using FFmpeg
    - Layer original ambient audio as base track preserving volume
    - Layer voiceover at higher relative volume than ambient
    - Output single MP4 with audio-video sync drift ≤ 200ms
    - Handle unavailable clips by retaining original segment and flagging in output
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 11.2, 11.3_

  - [x]* 11.2 Write property tests for Video Composer
    - **Property 8: Video composition covers full duration without gaps**
    - **Validates: Requirements 8.1**

  - [x]* 11.3 Write unit tests for Video Composer
    - Test timeline covers full duration without gaps or overlaps
    - Test ambient audio layer preservation
    - Test voiceover volume relative to ambient
    - Test fallback to original segment on clip failure
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 12. Checkpoint - All remixer components complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 13. Build the LangGraph StateGraph orchestrator
  - [x] 13.1 Define the `RemixState` TypedDict and build the StateGraph with all nodes
    - Create `backend/jusads_remix_pipeline/remix_graph.py`
    - Define `RemixState(TypedDict)` with all fields: identity (check_id, thread_id, media_type), input context (file_path, text_input, violations, target_audience), intermediate results (remix_result, generation_progress, segment_plan, storyboard_frames, interpolated_clips, script_and_voiceover, composed_video_path), HITL fields (user_decision, user_feedback, image_remix_choice), iteration tracking (iteration_count, max_iterations), and output (final_output, status, error)
    - Follow the same TypedDict + StateGraph pattern used in `langgraph_api.py` (ComplianceState)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.7_

  - [x] 13.2 Implement `route_media` node and conditional edge function
    - Implement `route_media(state: RemixState)` node that logs entry and returns empty dict
    - Implement `route_by_media(state: RemixState) -> str` conditional function that returns "await_image_choice" for image and "generate_remix" for text/audio/video
    - Wire as `add_conditional_edges("route_media", route_by_media, {...})`
    - _Requirements: 3.1, 10.6_

  - [x] 13.3 Implement `await_image_choice` node with `interrupt()` call
    - Implement the `await_image_choice(state: RemixState)` node
    - Call `interrupt()` from `langgraph.types` with payload `{"type": "image_method_choice", "violations": state["violations"], "message": "..."}` to pause graph
    - When resumed, extract user's choice ("edit" or "regenerate") and return `{"image_remix_choice": user_input["choice"]}`
    - Add edge from `await_image_choice` → `generate_remix`
    - _Requirements: 3.1, 10.6_

  - [x] 13.4 Implement `generate_remix` node that dispatches to the appropriate remixer
    - Implement `generate_remix(state: RemixState)` node
    - For text: call `remix_text()`, return remix_result + increment iteration_count
    - For audio: call `remix_audio()`, return remix_result + increment iteration_count
    - For image: call `remix_image()` using `state["image_remix_choice"]`, return remix_result + increment iteration_count
    - For video: execute the 5-step sub-pipeline sequentially (plan_segments → generate_storyboard → interpolate_clips → generate_script_and_voiceover → compose_video), updating `generation_progress` at each sub-step, return all intermediate state + composed remix_result + increment iteration_count
    - Incorporate `user_feedback` into regeneration prompts when `iteration_count > 0`
    - Set `status = "awaiting_decision"` in return state
    - Add edge from `generate_remix` → `await_user_decision`
    - _Requirements: 1.1, 2.1, 3.2, 3.3, 4.1, 5.1, 6.1, 7.1, 8.1, 10.1, 10.3_

  - [x] 13.5 Implement `await_user_decision` node with `interrupt()` call
    - Implement `await_user_decision(state: RemixState)` node
    - Call `interrupt()` with payload `{"type": "review_remix", "remix_result": state["remix_result"], "message": "Review the generated remix. Accept, reject, or request changes."}`
    - When resumed, extract decision and feedback: return `{"user_decision": user_input["decision"], "user_feedback": user_input.get("feedback", "")}`
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 13.6 Implement `route_decision` conditional edge and `finalize` node
    - Implement `route_decision(state: RemixState) -> str` conditional function
    - If `user_decision == "accept"` → return "finalize"
    - If `user_decision == "regenerate"` and `iteration_count < max_iterations` → return "generate_remix"
    - If `user_decision == "regenerate"` and `iteration_count >= max_iterations` → return END (with status "max_iterations_reached")
    - If `user_decision == "reject"` → return END (status "rejected")
    - Implement `finalize(state: RemixState)` node that copies remix_result to final_output and sets status = "finalized"
    - Wire conditional edges from `await_user_decision` and edge from `finalize` → END
    - _Requirements: 10.2, 10.3, 10.4, 10.5_

  - [x] 13.7 Compile the graph with `MemorySaver` checkpointer
    - Set entry point to `route_media`
    - Add all conditional edges and direct edges as defined in design
    - Compile with `MemorySaver()` checkpointer for thread-based state persistence
    - Export the compiled `remix_graph` for use by the API layer
    - _Requirements: 10.7_

  - [x]* 13.8 Write property tests for the HITL gate
    - **Property 14: Human-in-the-loop gate before finalization**
    - Test that graph pauses at `await_user_decision` after generation completes
    - Test that finalization only occurs after explicit "accept" decision
    - Test that regeneration loop respects max_iterations (5) limit
    - **Validates: Requirements 10.1, 10.2, 10.5**

  - [x]* 13.9 Write unit tests for graph routing and decision logic
    - Test `route_by_media` returns correct node for each media type
    - Test `route_decision` returns "finalize" on accept, "generate_remix" on regenerate, END on reject
    - Test iteration limit enforcement (6th regenerate goes to END)
    - Test image gets routed through `await_image_choice` before `generate_remix`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 14. Build the FastAPI endpoints for the remix graph
  - [x] 14.1 Implement `POST /remix/start` endpoint
    - Create `backend/jusads_remix_pipeline/api.py` with FastAPI router
    - Accept request body: check_id, media_type, file_path (or text_input), violations, target_audience
    - Validate input using Pydantic models from task 1.1
    - Generate a unique `thread_id` (UUID)
    - Build initial `RemixState` dict and invoke `remix_graph.ainvoke(initial_state, config={"configurable": {"thread_id": thread_id}})`
    - Return `{"thread_id": thread_id, "status": "generating", "message": "Remix pipeline started"}`
    - Handle validation errors with 400 responses identifying invalid fields
    - _Requirements: 9.5, 10.1, 10.7_

  - [x] 14.2 Implement `GET /remix/{thread_id}/status` endpoint
    - Read current graph state from checkpointer using `remix_graph.get_state(config)`
    - Return thread_id, status, interrupt_type (if awaiting), remix_result (if available), iteration_count, generation_progress
    - Handle thread_id not found with 404 response
    - _Requirements: 10.1, 10.7_

  - [x] 14.3 Implement `POST /remix/{thread_id}/decision` endpoint
    - Accept request body: decision ("accept" | "reject" | "regenerate"), optional feedback text
    - Validate that the graph is currently in an interrupted state (status "awaiting_decision" or "awaiting_image_choice")
    - Resume graph via `remix_graph.ainvoke(Command(resume={"decision": decision, "feedback": feedback}), config={"configurable": {"thread_id": thread_id}})`
    - Return updated status (finalized, generating, rejected)
    - Return 409 if graph is not in an interruptible state
    - _Requirements: 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 14.4 Implement `GET /remix/{thread_id}/stream` SSE endpoint for progress updates
    - Use LangGraph's `astream_events` to capture node execution events during `generate_remix`
    - Forward progress events as SSE: `event: progress`, `data: {"step": "...", "status": "...", "detail": "..."}`
    - Emit `event: interrupt` when graph hits an interrupt point
    - Use `StreamingResponse` with `media_type="text/event-stream"` (same pattern as existing compliance SSE in `langgraph_api.py`)
    - _Requirements: 10.1, 10.7_

  - [x] 14.5 Register the remix router in the main application
    - Import and mount the remix router in `backend/langgraph_api.py` using `app.include_router(remix_router, prefix="/remix", tags=["remix"])`
    - Ensure CORS middleware applies to new endpoints
    - _Requirements: 10.7_

  - [x]* 14.6 Write integration tests for remix API endpoints
    - Test `POST /remix/start` with valid text violations → returns thread_id and generating status
    - Test `GET /remix/{thread_id}/status` returns correct state after interrupt
    - Test `POST /remix/{thread_id}/decision` with accept → finalized status
    - Test `POST /remix/{thread_id}/decision` with regenerate + feedback → generating status
    - Test `POST /remix/{thread_id}/decision` with reject → rejected status
    - Test image flow: start → status shows awaiting image choice → decision with choice → status shows awaiting_decision
    - Test validation error returns 400 with field-level error messages
    - Test 404 for unknown thread_id
    - Test 409 when submitting decision to non-interrupted graph
    - **Property 12: Remix output structure completeness**
    - **Validates: Requirements 9.5, 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7**

- [x] 15. Final checkpoint - Full pipeline integration
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend modules follow the `jusads_` prefix convention
- All Python code uses Pydantic for data validation and FastAPI for API layer
- Tests use pytest as per project conventions
- The LangGraph orchestrator follows the same patterns as the existing `langgraph_api.py` (ComplianceState, StateGraph, node functions, SSE streaming)
- `MemorySaver` is used for development; swap to `PostgresSaver` for production persistence
- The `interrupt()` function from `langgraph.types` is used (not `interrupt_before`/`interrupt_after` on edges)
- `Command(resume=...)` is used to resume graph execution after user decisions

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.3"] },
    { "id": 1, "tasks": ["1.2", "1.4", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1", "6.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "5.1", "6.2", "6.3"] },
    { "id": 4, "tasks": ["5.2", "5.3", "7.1"] },
    { "id": 5, "tasks": ["7.2", "8.1"] },
    { "id": 6, "tasks": ["8.2", "10.1"] },
    { "id": 7, "tasks": ["10.2", "11.1"] },
    { "id": 8, "tasks": ["11.2", "11.3"] },
    { "id": 9, "tasks": ["13.1"] },
    { "id": 10, "tasks": ["13.2", "13.3"] },
    { "id": 11, "tasks": ["13.4", "13.5"] },
    { "id": 12, "tasks": ["13.6", "13.7"] },
    { "id": 13, "tasks": ["13.8", "13.9"] },
    { "id": 14, "tasks": ["14.1"] },
    { "id": 15, "tasks": ["14.2", "14.3", "14.4"] },
    { "id": 16, "tasks": ["14.5"] },
    { "id": 17, "tasks": ["14.6"] }
  ]
}
```

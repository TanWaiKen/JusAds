# Requirements Document

## Introduction

The Remix Pipeline is JusAds' automated remediation system that generates compliant versions of advertising media after compliance violations are detected. It supports four media types — text, audio, image, and video — each with a specialized remix strategy. The pipeline takes structured violation data from the compliance audit stage and produces culturally appropriate, regulation-compliant creative assets tailored to Southeast Asian markets (primarily Malaysia).

## Glossary

- **Remix_Pipeline**: The automated system that receives compliance violations and generates compliant media variants
- **Text_Remixer**: The component responsible for rewriting non-compliant text to be culturally and regulatorily appropriate
- **Audio_Remixer**: The component that fixes non-compliant audio by correcting transcripts and regenerating speech
- **Image_Remixer**: The component that corrects non-compliant images via inpainting or full regeneration
- **Video_Remixer**: The component that orchestrates the multi-step video remediation process
- **Segment_Planner**: The sub-component that splits video violations into generation-compatible chunks
- **Storyboard_Generator**: The sub-component that produces key frames for video clip regeneration
- **Video_Interpolator**: The sub-component that generates smooth video clips from storyboard frames using Veo
- **Script_Generator**: The sub-component that creates localized voiceover scripts matching remixed visuals
- **Video_Composer**: The sub-component that assembles final video from remixed clips, ambient audio, and voiceover
- **Violation**: A structured record of a non-compliant element detected during compliance audit
- **Target_Audience**: The demographic group the ad is intended for, defined by market, ethnicity, and language
- **Cultural_Rules**: Market-specific constraints on visual representation (e.g., modesty rules, ethnic representation)

## Requirements

### Requirement 1: Text Remix

**User Story:** As an advertiser, I want non-compliant text in my ad to be automatically rewritten to a compliant version, so that I can quickly produce culturally appropriate copy without manual editing.

#### Acceptance Criteria

1. WHEN a text violation list is provided, THE Text_Remixer SHALL rewrite the full text (up to 5000 characters) to eliminate all identified violations while preserving the original sentence structure and vocabulary level
2. WHEN rewriting text, THE Text_Remixer SHALL produce compliant_text that conveys the same product or service, the same call-to-action, and uses the same tone register (formal, casual, or conversational) as the original text
3. WHEN a target audience is specified, THE Text_Remixer SHALL localize the language to match the target audience language (e.g., Mandarin for Chinese audience, Bahasa Malaysia for Malay audience)
4. WHEN text remix completes, THE Text_Remixer SHALL return a structured output containing the original text, compliant text, and a list of changes with original phrase, replacement phrase, and reason for each change
5. IF the text contains no violations, THEN THE Text_Remixer SHALL return the original text unchanged with an empty changes list
6. IF a violation phrase in the violation list does not exist in the provided text, THEN THE Text_Remixer SHALL skip that violation entry and exclude it from the changes list
7. IF the Text_Remixer fails to produce a compliant rewrite within 30 seconds, THEN THE Text_Remixer SHALL return an error response indicating the failure reason while preserving the original text in the output

### Requirement 2: Audio Remix

**User Story:** As an advertiser, I want non-compliant spoken content in my audio ad to be automatically replaced with compliant speech, so that I can produce culturally appropriate audio without re-recording.

#### Acceptance Criteria

1. WHEN audio violations are provided, THE Audio_Remixer SHALL correct the transcript text by replacing all non-compliant phrases with compliant alternatives
2. WHEN generating replacement audio, THE Audio_Remixer SHALL select a voice gender (male or female) based on the content context and target audience
3. WHEN a target audience ethnicity is specified, THE Audio_Remixer SHALL map the market and ethnicity to an appropriate ElevenLabs voice
4. WHEN generating the replacement audio, THE Audio_Remixer SHALL match the duration of the generated audio to the duration of the original audio
5. WHEN audio remix completes, THE Audio_Remixer SHALL return a structured output containing the original transcript, compliant transcript, audio file path, and voice identifier used

### Requirement 3: Image Remix

**User Story:** As an advertiser, I want non-compliant visual elements in my image ad to be automatically corrected, so that I can produce culturally appropriate imagery without manual design work.

#### Acceptance Criteria

1. WHEN image violations are provided, THE Image_Remixer SHALL present exactly two remediation options: edit existing image (inpainting) and regenerate full image
2. WHEN the user selects the edit option, THE Image_Remixer SHALL use the detailed edit prompt from the compliance output to modify only the non-compliant regions identified in the violations list while preserving the layout, background, and all non-violating elements of the original image
3. WHEN the user selects the regenerate option, THE Image_Remixer SHALL generate a completely new compliant image using the original image's composition style (photorealistic, illustrated, or graphic) as a style reference
4. WHILE generating images for a Malay target audience, THE Image_Remixer SHALL include only Malay models, require hijab for female models, ensure no exposed skin above the elbow or below the knee for all models, and use modest clothing for male models
5. WHILE generating images for a Chinese target audience, THE Image_Remixer SHALL include only Chinese models
6. WHEN image remix completes successfully, THE Image_Remixer SHALL return a structured output containing the violations list, the edit prompt used, the selected option ("edit" or "regenerate"), and the file path of the generated result image
7. IF image generation fails due to an API error or content filter rejection, THEN THE Image_Remixer SHALL return an error response indicating the failure reason while preserving the original violations list and edit prompt in the output
8. IF the provided violations list is empty, THEN THE Image_Remixer SHALL skip generation and return the original image path unchanged with an empty changes list

### Requirement 4: Video Segment Planning

**User Story:** As an advertiser, I want my non-compliant video segments to be intelligently split into generation-compatible chunks, so that the remix pipeline can process them within platform limits.

#### Acceptance Criteria

1. WHEN a video violation segment exceeds 8 seconds, THE Segment_Planner SHALL split the segment into chunks where each chunk is between 5 and 8 seconds in duration, and the sum of all chunk durations SHALL equal the original segment duration
2. WHEN a video violation segment is 8 seconds or less but at least 5 seconds, THE Segment_Planner SHALL include the segment as a single chunk without splitting
3. WHEN splitting segments, THE Segment_Planner SHALL preserve compliant sections of the video untouched and SHALL NOT include any time ranges that fall entirely within compliant sections in the generation plan
4. THE Segment_Planner SHALL produce a segment plan that maps each chunk to its start time (seconds), end time (seconds), source violation index, and chunk sequence number within that violation
5. IF a violation segment has a duration less than 5 seconds, THEN THE Segment_Planner SHALL include it as a single chunk and flag it as requiring short-form generation
6. IF a violation segment has an end time less than or equal to its start time, THEN THE Segment_Planner SHALL reject the segment and return an error indicating the invalid time range

### Requirement 5: Video Storyboard Generation

**User Story:** As an advertiser, I want key frames generated for each non-compliant video chunk, so that the video interpolation step can produce smooth, compliant clips.

#### Acceptance Criteria

1. WHEN generating storyboard frames for a chunk, THE Storyboard_Generator SHALL generate between 2 and 4 key frames in a single image generation call, where the number of frames is determined by the chunk duration (2 frames for chunks up to 4 seconds, 3 frames for chunks up to 6 seconds, 4 frames for chunks up to 8 seconds)
2. WHILE generating storyboard frames for a Malay target audience, THE Storyboard_Generator SHALL apply cultural rules: Malay models only, hijab for female models, and no exposed skin above the elbow or below the knee
3. WHILE generating storyboard frames for a Chinese target audience, THE Storyboard_Generator SHALL apply cultural rules: Chinese models only
4. WHILE generating storyboard frames, THE Storyboard_Generator SHALL include the original video's product packaging, brand logos, and brand color palette in the generation prompt so they appear in the output frames
5. IF the image generation call fails or returns no frames, THEN THE Storyboard_Generator SHALL retry the generation up to 2 additional times, and if all attempts fail, SHALL return an error indicating the chunk index and the failure reason

### Requirement 6: Video Interpolation

**User Story:** As an advertiser, I want smooth video clips generated from the storyboard frames, so that remixed segments appear natural and professional.

#### Acceptance Criteria

1. WHEN at least 2 storyboard frames are provided, THE Video_Interpolator SHALL use Veo reference_images parameter with reference_type "asset" to interpolate between frames and produce a smooth video clip
2. WHEN storyboard frames are provided, THE Video_Interpolator SHALL generate clips with a duration between 5 and 8 seconds at a minimum of 24 frames per second
3. WHILE generating video clips, THE Video_Interpolator SHALL extract and retain the original ambient audio and sound effects from the corresponding source video segment for use in composition
4. WHILE generating video clips, THE Video_Interpolator SHALL NOT generate any speech audio or human vocal content within the clip
5. IF the Veo API returns an error or times out after 120 seconds, THEN THE Video_Interpolator SHALL return an error indication specifying the failed segment's time range and retry up to 2 times before reporting failure
6. IF fewer than 2 storyboard frames are provided for a segment, THEN THE Video_Interpolator SHALL reject the request and return an error indication that the minimum frame count of 2 was not met

### Requirement 7: Video Script and Voiceover Generation

**User Story:** As an advertiser, I want a localized voiceover generated that matches the remixed video visuals, so that the final video has natural, culturally appropriate narration.

#### Acceptance Criteria

1. WHEN remixed video clips are available, THE Script_Generator SHALL analyze the visual content of each video segment and generate a localized script where each script line references the corresponding segment by timestamp range
2. WHEN generating a script, THE Script_Generator SHALL produce timing cues that include both speech segments and silence segments (minimum 1 second of silence between speech segments), where speech segments align with visual action and silence segments align with visual transitions or pauses
3. WHEN generating voiceover audio, THE Script_Generator SHALL select a voice gender (male or female) based on the target audience gender demographic specified in the remix request
4. WHEN a target audience ethnicity is specified as Chinese, THE Script_Generator SHALL generate the voiceover in Mandarin, and WHEN ethnicity is specified as Malay, THE Script_Generator SHALL generate the voiceover in Bahasa Malaysia
5. WHEN generating voiceover segments, THE Script_Generator SHALL produce audio where each segment duration is within 500 milliseconds of the corresponding video segment duration, with silence padding used to fill any remaining time
6. IF the target audience ethnicity is not specified or is not in the supported set (Chinese, Malay), THEN THE Script_Generator SHALL default to generating the voiceover in English
7. IF voiceover generation fails for any segment, THEN THE Script_Generator SHALL return an error indication identifying which segment failed and preserve any successfully generated segments

### Requirement 8: Video Composition

**User Story:** As an advertiser, I want all remixed video components assembled into a final compliant video, so that I receive a complete, ready-to-use output.

#### Acceptance Criteria

1. WHEN all remixed clips and voiceover are ready, THE Video_Composer SHALL stitch the original compliant sections and remixed clips in chronological order into a continuous video that covers the full original video duration with no gaps and no overlaps between segments
2. WHEN composing the final video, THE Video_Composer SHALL layer the original ambient audio and sound effects as the base audio track, preserving the original volume levels from the source video
3. WHEN composing the final video, THE Video_Composer SHALL layer the new voiceover track on top of the ambient audio with the voiceover at a higher relative volume than the ambient track so that speech remains intelligible
4. WHEN composition completes, THE Video_Composer SHALL output a single MP4 video file with video, ambient audio, and voiceover tracks where audio-to-video synchronization drift does not exceed 200 milliseconds
5. IF a remixed clip is unavailable or failed to generate, THEN THE Video_Composer SHALL retain the original video segment for that time range and produce an output indicating which segments could not be remediated

### Requirement 9: Violation Data Format

**User Story:** As a developer integrating with the remix pipeline, I want structured and consistent violation data formats per media type, so that the pipeline can reliably process audit outputs.

#### Acceptance Criteria

1. THE Remix_Pipeline SHALL accept text violations containing the following fields: index (non-negative integer), type (string, value "text"), phrase (string, max 500 characters), severity (string, one of "error" or "warning"), reason (string, max 1000 characters), and suggested_replacement (string, max 500 characters)
2. THE Remix_Pipeline SHALL accept image violations containing the following fields: index (non-negative integer), type (string, value "visual"), component (string, max 200 characters), severity (string, one of "error" or "warning"), location_description (string, max 1000 characters), and edit_prompt (string, max 2000 characters)
3. THE Remix_Pipeline SHALL accept audio violations containing the following fields: index (non-negative integer), type (string, value "audio"), spoken_phrase (string, max 500 characters), severity (string, one of "error" or "warning"), reason (string, max 1000 characters), suggested_replacement (string, max 500 characters), and voice_gender (string, one of "male" or "female")
4. THE Remix_Pipeline SHALL accept video violations containing the following fields: index (non-negative integer), start (number, seconds, non-negative), end (number, seconds, non-negative), type (string, one of "visual" or "audio"), category (string, max 200 characters), severity (string, one of "error" or "warning"), description (string, max 1000 characters), and clip_url (string, max 500 characters)
5. IF a violation record is missing one or more required fields or contains a field with an incorrect data type, THEN THE Remix_Pipeline SHALL reject the input and return a validation error message identifying each invalid or missing field by name
6. IF a video violation has a start value greater than or equal to its end value, or either value is negative, THEN THE Remix_Pipeline SHALL reject the violation and return a validation error message indicating the invalid timestamp range

### Requirement 10: Human-in-the-Loop Orchestration

**User Story:** As an advertiser, I want to review each remix result and decide whether to accept, reject, or request a re-generation with feedback, so that I maintain creative control over the final output.

#### Acceptance Criteria

1. WHEN a remix generation completes for any media type, THE Remix_Pipeline SHALL pause execution and present the result to the user for review before finalizing
2. WHEN the user submits an "accept" decision, THE Remix_Pipeline SHALL finalize the remix result and persist it as the final output
3. WHEN the user submits a "regenerate" decision with optional feedback text, THE Remix_Pipeline SHALL use the feedback to generate a new remix variant and pause again for user review
4. WHEN the user submits a "reject" decision, THE Remix_Pipeline SHALL discard the remix result and terminate the pipeline without producing a final output
5. IF the user has regenerated the remix 5 times for a single request, THEN THE Remix_Pipeline SHALL stop accepting further regeneration requests and notify the user that the maximum iteration limit has been reached
6. WHEN the media type is image, THE Remix_Pipeline SHALL additionally pause BEFORE generation to collect the user's choice of remediation method ("edit" or "regenerate") and only proceed with generation after receiving this choice
7. THE Remix_Pipeline SHALL persist graph state between requests using a thread identifier so that the user can review results asynchronously and resume the pipeline at any time

### Requirement 11: Pipeline Efficiency

**User Story:** As a system operator, I want the remix pipeline to use AI generation resources efficiently, so that processing costs are minimized and turnaround is fast.

#### Acceptance Criteria

1. WHEN generating storyboard frames for a video remix chunk, THE Storyboard_Generator SHALL generate at least 2 frames per chunk in a single API call, with a maximum of 4 frames per call, rather than issuing individual API calls per frame
2. THE Video_Remixer SHALL only regenerate sections identified as non-compliant in the violation list and SHALL preserve compliant sections by copying the original video and audio data for those time ranges without re-encoding or re-generation
3. THE Video_Remixer SHALL retain the original non-speech audio track (background music, sound effects, ambient sounds) from the source video and SHALL only replace or generate the speech/voiceover track
4. IF a batched storyboard frame generation API call fails, THEN THE Storyboard_Generator SHALL retry the call up to 2 additional times before reporting a generation error for that chunk

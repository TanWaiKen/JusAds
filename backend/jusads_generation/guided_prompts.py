"""
guided_prompts.py
─────────────────
Fixed system prompts and assembly logic for the Guided Generation Mode.

Each design type has a pre-crafted prompt template with placeholders for user inputs.
The assemble_guided_message() function injects form data and returns a plain string
suitable for run_generation().
"""

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# --- Type alias --------------------------------------------------------------

DesignType = str  # Literal["image_poster", "carousel", "video_ad", "text_copy", "audio_ad"]

# --- Design Types ------------------------------------------------------------

DESIGN_TYPES: list[DesignType] = [
    "image_poster",
    "carousel",
    "video_ad",
    "text_copy",
    "audio_ad",
]

# Maps each design type to the orchestrator media type(s) it should trigger.
# This is used to bypass intent detection for guided mode — we KNOW what to generate.
DESIGN_TYPE_TO_MEDIA: dict[DesignType, list[str]] = {
    "image_poster": ["image"],
    "carousel": ["image"],
    "video_ad": ["video"],
    "text_copy": ["text"],
    "audio_ad": ["audio"],
}

# --- Form Schema -------------------------------------------------------------

FORM_SCHEMA: dict[str, dict[str, list[str]]] = {
    "image_poster": {
        "common": ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
        "specific": ["visual_style", "color_palette", "reference_images"],
    },
    "carousel": {
        "common": ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
        "specific": ["visual_style", "color_palette", "slide_count", "reference_images"],
    },
    "video_ad": {
        "common": ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
        "specific": ["video_duration", "visual_style", "reference_images"],
    },
    "text_copy": {
        "common": ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
        "specific": ["copy_length", "call_to_action", "language"],
    },
    "audio_ad": {
        "common": ["product_name", "target_audience", "platform", "key_message", "brand_tone"],
        "specific": ["audio_duration", "voice_tone", "background_music_style"],
    },
}

# --- Design Type Metadata ----------------------------------------------------

DESIGN_TYPE_META: list[dict[str, str]] = [
    {
        "id": "image_poster",
        "label": "Image Poster",
        "description": "Single high-impact visual poster optimized for social feeds and display ads",
        "icon": "image",
    },
    {
        "id": "carousel",
        "label": "Carousel Ad",
        "description": "Multi-slide swipeable narrative with consistent visual style across slides",
        "icon": "gallery-horizontal-end",
    },
    {
        "id": "video_ad",
        "label": "Video Ad",
        "description": "Short-form video ad with hook, pacing, and call-to-action scripting",
        "icon": "video",
    },
    {
        "id": "text_copy",
        "label": "Text Copy",
        "description": "Platform-optimized advertising copy using proven copywriting frameworks",
        "icon": "type",
    },
    {
        "id": "audio_ad",
        "label": "Audio Ad",
        "description": "Scripted audio spot with voice direction, pacing, and sonic branding",
        "icon": "audio-lines",
    },
]


# --- Fixed Prompts -----------------------------------------------------------

FIXED_PROMPTS: dict[DesignType, str] = {
    "image_poster": (
        "You are a professional advertising image designer creating a high-impact poster "
        "for {product_name}. Your target audience is {target_audience} on {platform}.\n\n"
        "CORE MESSAGE: {key_message}\n\n"
        "BRAND TONE: {brand_tone}\n\n"
        "VISUAL DIRECTION: {visual_style}\n\n"
        "COLOR PALETTE: {color_palette}\n\n"
        "DESIGN PRINCIPLES — follow these advertising best practices for static poster ads:\n"
        "1. VISUAL HIERARCHY: Place the most important element (product or headline) at the "
        "optical center or upper third. Use size contrast to guide the eye from headline → "
        "supporting visual → call-to-action → brand mark.\n"
        "2. CONTRAST & READABILITY: Ensure text-to-background contrast ratio meets WCAG AA "
        "minimum. Use bold sans-serif typefaces for headlines. Limit body copy to 2 lines max.\n"
        "3. BRAND ELEMENT PLACEMENT: Position the logo in a consistent corner (bottom-right "
        "preferred for left-to-right reading flow). Brand colors should occupy at least 20% of "
        "the canvas area.\n"
        "4. PLATFORM DIMENSIONS: Generate at the optimal aspect ratio for {platform} — "
        "1080×1080 for feed posts, 1080×1920 for stories, 1200×628 for link previews. "
        "Keep all critical elements within the safe zone (80% of frame center).\n"
        "5. COMPOSITION: Apply the rule of thirds. Use negative space intentionally to avoid "
        "clutter. Limit total elements to 5 or fewer for instant comprehension at scroll speed.\n"
        "6. MASTERPIECE QUALITY: Render at highest fidelity — crisp edges, consistent lighting, "
        "no artifacts. Product photography should be hero-lit with a subtle shadow for depth.\n\n"
        "REFERENCE IMAGES: {reference_images}\n\n"
        "Generate a single, scroll-stopping poster image that communicates the core message "
        "within 2 seconds of viewing. Prioritize clarity over complexity."
    ),

    "carousel": (
        "You are a professional advertising designer creating a multi-slide carousel ad "
        "for {product_name}. Your target audience is {target_audience} on {platform}.\n\n"
        "CORE MESSAGE: {key_message}\n\n"
        "BRAND TONE: {brand_tone}\n\n"
        "VISUAL DIRECTION: {visual_style}\n\n"
        "COLOR PALETTE: {color_palette}\n\n"
        "NUMBER OF SLIDES: {slide_count}\n\n"
        "DESIGN PRINCIPLES — follow these advertising best practices for carousel ads:\n"
        "1. NARRATIVE COHERENCE: Structure slides as a story arc — hook (slide 1) → problem "
        "or context (slide 2) → solution/product showcase (slides 3-4) → call-to-action "
        "(final slide). Each slide must make sense standalone but reward sequential viewing.\n"
        "2. CONSISTENT VISUAL STYLE: Maintain identical typography, color palette, layout grid, "
        "and illustration style across all slides. Use a shared background texture or color "
        "gradient that unifies the set.\n"
        "3. SWIPE-WORTHY PROGRESSION: End each slide with a visual or textual hook that compels "
        "the next swipe — a cropped element, an unfinished sentence, or a directional cue "
        "(arrow, pointing gesture). Slide 1 must be irresistible enough to stop the scroll.\n"
        "4. SLIDE COUNT GUIDANCE: 3-5 slides recommended for optimal engagement. Under 3 feels "
        "incomplete; over 7 causes drop-off. If fewer slides are specified, increase information "
        "density per slide.\n"
        "5. VISUAL CONTINUITY: Use a consistent element (brand mascot, product shot, color bar) "
        "that appears in the same position on every slide to create rhythmic familiarity.\n"
        "6. PLATFORM OPTIMIZATION: All slides at 1080×1080 for {platform}. First slide carries "
        "the headline hook. Last slide carries the CTA with clear action language.\n\n"
        "REFERENCE IMAGES: {reference_images}\n\n"
        "Generate a cohesive carousel set that tells a compelling brand story across slides. "
        "Each slide should earn the next swipe."
    ),

    "video_ad": (
        "You are a professional advertising video director creating a short-form video ad "
        "for {product_name}. Your target audience is {target_audience} on {platform}.\n\n"
        "CORE MESSAGE: {key_message}\n\n"
        "BRAND TONE: {brand_tone}\n\n"
        "VIDEO DURATION: {video_duration}\n\n"
        "VISUAL DIRECTION: {visual_style}\n\n"
        "PRODUCTION PRINCIPLES — follow these advertising best practices for video ads:\n"
        "1. 3-SECOND HOOK: The first 3 seconds must arrest attention with a bold visual, "
        "unexpected motion, provocative question, or pattern interrupt. 65% of viewers "
        "decide to keep watching or scroll within this window. Open with product in motion, "
        "a surprising transformation, or a direct-to-camera address.\n"
        "2. PLATFORM PACING: For TikTok/Reels (under 30s) — fast cuts every 2-3 seconds, "
        "text overlays synced to speech, trending transition styles. For YouTube (30s-60s) — "
        "allow breathing room, use a 3-act structure (hook → story → CTA), maintain visual "
        "variety every 5-7 seconds to sustain attention.\n"
        "3. CALL-TO-ACTION PLACEMENT: Place the primary CTA in the final 20% of the video "
        "duration. Reinforce with on-screen text, a verbal prompt, and a visual cue (button "
        "graphic, swipe-up arrow). For longer formats, add a mid-roll soft CTA at the 60% mark.\n"
        "4. ENGAGEMENT TECHNIQUES: Use direct address ('you'), show transformation "
        "(before/after), leverage social proof (testimonials, UGC-style footage), and create "
        "urgency (limited-time framing). Match the first frame to a thumbnail that works as "
        "a static image.\n"
        "5. DURATION-APPROPRIATE SCRIPTING: 15s = single point + CTA. 30s = hook + one benefit "
        "+ proof + CTA. 60s = hook + problem + solution + proof + CTA + brand resolve.\n"
        "6. SOUND DESIGN: First 1 second must include a sonic cue (beat drop, voice, SFX) to "
        "capture earphone-wearing viewers. Design for sound-off viewing with captions/text but "
        "optimize for sound-on experience.\n\n"
        "REFERENCE IMAGES: {reference_images}\n\n"
        "Script and direct a video that hooks instantly, maintains energy throughout, and "
        "closes with a clear, compelling call-to-action."
    ),

    "text_copy": (
        "You are a professional advertising copywriter creating platform-optimized ad copy "
        "for {product_name}. Your target audience is {target_audience} on {platform}.\n\n"
        "CORE MESSAGE: {key_message}\n\n"
        "BRAND TONE: {brand_tone}\n\n"
        "COPY LENGTH: {copy_length}\n\n"
        "CALL TO ACTION: {call_to_action}\n\n"
        "LANGUAGE: {language}\n\n"
        "COPYWRITING PRINCIPLES — follow these advertising best practices for text copy:\n"
        "1. AIDA FRAMEWORK: Structure your copy using Attention → Interest → Desire → Action. "
        "Attention: Open with a pattern-interrupt headline or question that targets a pain point. "
        "Interest: Present the unique value proposition with specificity (numbers, outcomes). "
        "Desire: Paint the transformation — show the after-state the audience wants. "
        "Action: Close with a single, clear, low-friction CTA.\n"
        "2. CHARACTER LIMITS PER PLATFORM: Instagram captions — front-load the hook in first "
        "125 characters (before the fold). Facebook — 40 characters for headlines, 125 for "
        "primary text. Twitter/X — 280 characters total, make every word count. LinkedIn — "
        "professional tone, 150 characters for the hook line.\n"
        "3. TONE MATCHING: Mirror the brand tone consistently throughout. If playful — use "
        "contractions, colloquialisms, and short punchy sentences. If professional — use "
        "precise language, data points, and authority signals. If urgent — use imperative "
        "verbs, time pressure, and scarcity cues.\n"
        "4. HASHTAG & EMOJI GUIDANCE: Use 3-5 relevant hashtags (mix branded + discovery). "
        "Place hashtags at the end, never inline. Use 1-2 emojis max as visual anchors at "
        "line beginnings — never as substitutes for words. Skip emojis entirely for B2B or "
        "luxury brands.\n"
        "5. CTA BEST PRACTICES: Use action verbs (Get, Try, Discover, Claim). Create urgency "
        "without being manipulative. One CTA per ad — multiple CTAs reduce conversion. Match "
        "CTA to the funnel stage (awareness = Learn More, consideration = Try Free, "
        "conversion = Buy Now).\n"
        "6. FORMATTING: Use line breaks for readability. Lead with the strongest line. "
        "Front-load value — readers scan, they don't read. Keep paragraphs to 1-2 sentences.\n\n"
        "Write compelling ad copy that stops the scroll, communicates value instantly, and "
        "drives a single clear action."
    ),

    "audio_ad": (
        "You are a professional audio advertising producer creating a scripted audio spot "
        "for {product_name}. Your target audience is {target_audience} on {platform}.\n\n"
        "CORE MESSAGE: {key_message}\n\n"
        "BRAND TONE: {brand_tone}\n\n"
        "AUDIO DURATION: {audio_duration}\n\n"
        "VOICE TONE: {voice_tone}\n\n"
        "BACKGROUND MUSIC STYLE: {background_music_style}\n\n"
        "AUDIO PRODUCTION PRINCIPLES — follow these advertising best practices for audio ads:\n"
        "1. DURATION SCRIPTING: 15-second spot = 35-40 words maximum, one single message + "
        "brand name + CTA. 30-second spot = 70-80 words, problem-solution structure with one "
        "proof point. 60-second spot = 140-160 words, full narrative arc with testimonial or "
        "scenario. Time your script to speaking pace (150 words per minute average). Leave "
        "0.5s breathing room at open and close.\n"
        "2. VOICE TONE DIRECTION: Match the voice talent to the brand personality — warm and "
        "conversational for lifestyle brands, authoritative and clear for finance/health, "
        "energetic and fast-paced for youth/entertainment. Specify pacing: measured pauses "
        "for luxury, rapid-fire for urgency, melodic for emotional storytelling.\n"
        "3. SONIC BRANDING: Include a consistent audio signature (mnemonic, jingle tag, or "
        "brand sound) in the final 3 seconds. This builds brand recall across repeated plays. "
        "The sonic logo should be 1-3 seconds, memorable, and tonally aligned with the brand.\n"
        "4. MUSIC BED GUIDANCE: Background music should complement, never compete with, the "
        "voiceover. Keep music at -15dB to -20dB below voice. Music energy should match copy "
        "energy — build during the desire section, resolve under the CTA. Use genre-appropriate "
        "instrumentation for the target audience.\n"
        "5. CLARITY & PACING: Prioritize vocal clarity above all. Avoid overlapping voice and "
        "SFX. Use silence strategically — a 0.3s pause before the CTA increases retention. "
        "Repeat the brand name at least twice (open and close). Spell out URLs or use vanity "
        "URLs that are phonetically simple.\n"
        "6. PLATFORM CONSIDERATIONS: Podcast ads — conversational, host-read style performs "
        "best. Spotify/streaming — front-load the hook (skip button at 5s). Radio — higher "
        "energy, account for ambient listening. Voice assistant — ultra-concise, no background "
        "music.\n\n"
        "Script a complete audio ad with voice direction cues, music bed notes, and timing "
        "markers. The final spot must be clear, memorable, and drive a single action."
    ),
}


# --- Required fields ---------------------------------------------------------

_REQUIRED_FIELDS: set[str] = {"product_name", "key_message"}

# --- Intent signals ----------------------------------------------------------
# These short prefixes ensure the orchestrator's intent detection correctly
# identifies which media agent(s) to route to. The orchestrator uses Gemini +
# keyword fallback to detect "generate image/video/audio/text" from the message.

_INTENT_SIGNALS: dict[DesignType, str] = {
    "image_poster": "Generate an image poster ad.",
    "carousel": "Generate a carousel image ad with multiple slides.",
    "video_ad": "Generate a video ad.",
    "text_copy": "Generate text ad copy.",
    "audio_ad": "Generate an audio ad with voiceover.",
}


# --- Assembly function -------------------------------------------------------


def assemble_guided_message(
    design_type: DesignType,
    form_inputs: dict[str, Any],
) -> str:
    """Combine form inputs with the fixed prompt for the given design type.

    Takes the FIXED_PROMPTS[design_type] template, replaces each {placeholder}
    with the corresponding form_inputs value. For empty optional fields, removes
    the placeholder AND the line/section containing it to produce clean output.

    Args:
        design_type: One of the supported design types.
        form_inputs: Dict of field_name → value from the guided form.

    Returns:
        A complete user_message string ready for run_generation().

    Raises:
        ValueError: If design_type is not recognized or required fields are missing.
    """
    # Validate design type
    if design_type not in DESIGN_TYPES:
        raise ValueError(
            f"Unrecognized design type '{design_type}'. "
            f"Must be one of: {', '.join(DESIGN_TYPES)}"
        )

    # Validate required fields
    for field in _REQUIRED_FIELDS:
        value = form_inputs.get(field, "")
        if not value or (isinstance(value, str) and not value.strip()):
            raise ValueError(
                f"Required field '{field}' must be non-empty."
            )

    logger.info(
        "[GuidedPrompts] Assembling message for design_type=%s", design_type
    )

    template = FIXED_PROMPTS[design_type]

    # Find all placeholders in the template
    placeholders = re.findall(r"\{(\w+)\}", template)

    # Replace placeholders with values or mark lines for removal
    lines = template.split("\n")
    assembled_lines: list[str] = []

    for line in lines:
        line_placeholders = re.findall(r"\{(\w+)\}", line)

        if not line_placeholders:
            # No placeholders on this line — keep it as-is
            assembled_lines.append(line)
            continue

        # Check if ALL placeholders on this line have empty values
        all_empty = True
        for ph in line_placeholders:
            value = form_inputs.get(ph, "")
            if isinstance(value, list):
                if value:
                    all_empty = False
                    break
            elif isinstance(value, str) and value.strip():
                all_empty = False
                break
            elif value and not isinstance(value, (str, list)):
                all_empty = False
                break

        if all_empty:
            # Skip this line entirely — don't leave blank placeholders
            continue

        # Replace placeholders with values
        result_line = line
        for ph in line_placeholders:
            value = form_inputs.get(ph, "")
            if isinstance(value, list):
                # Join list values (e.g., reference_images URLs)
                replacement = ", ".join(str(v) for v in value) if value else ""
            else:
                replacement = str(value) if value else ""
            result_line = result_line.replace(f"{{{ph}}}", replacement)

        assembled_lines.append(result_line)

    # Join and clean up: remove consecutive blank lines
    assembled = "\n".join(assembled_lines)
    assembled = re.sub(r"\n{3,}", "\n\n", assembled)
    assembled = assembled.strip()

    logger.info(
        "[GuidedPrompts] Assembled message length: %d chars", len(assembled)
    )

    # Prepend an explicit intent signal so the orchestrator's intent detection
    # correctly routes to the right media agent(s). Without this, Gemini may
    # not classify a long system-prompt-style message as a generation request.
    intent_prefix = _INTENT_SIGNALS.get(design_type, "")
    if intent_prefix:
        assembled = f"{intent_prefix}\n\n{assembled}"

    return assembled


# --- Schema endpoint helper --------------------------------------------------


def get_form_schema() -> dict[str, Any]:
    """Return the FORM_SCHEMA and DESIGN_TYPE_META for the API endpoint.

    Returns:
        A dict with 'design_types' containing metadata and field definitions
        for each design type, ready to be serialized as the API response.
    """
    design_types_response: list[dict[str, Any]] = []

    for meta in DESIGN_TYPE_META:
        design_type_id = meta["id"]
        schema = FORM_SCHEMA.get(design_type_id, {"common": [], "specific": []})

        design_types_response.append({
            "id": meta["id"],
            "label": meta["label"],
            "description": meta["description"],
            "icon": meta["icon"],
            "fields": {
                "common": schema["common"],
                "specific": schema["specific"],
            },
        })

    return {"design_types": design_types_response}

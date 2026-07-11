"""
video_templates.py
──────────────────
Prompt template definitions for video ad types.

Designed for short-form video ad content (product demos, social media promos).
Sourced from proven video generation patterns (SeaArt, RunwayML, Pika).

Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 13.1
"""

from . import PromptTemplate

# ─── Video Template: Product Demo Video ───────────────────────────────────────

PRODUCT_DEMO_VIDEO: PromptTemplate = {
    "template_id": "video_product_demo",
    "ad_type": "video",
    "name": "Product Demo Video",
    "description": "A short-form product demonstration video with smooth motion and professional lighting, ideal for social media ads and product launches",
    "source": {
        "name": "SeaArt AI Video Community",
        "url": "https://www.seaart.ai/models/video",
        "model": "SeaArt Video v2",
    },
    "fields": [
        {
            "name": "subject",
            "label": "Main Subject",
            "field_type": "textarea",
            "required": True,
            "default": None,
            "placeholder": "e.g. A sleek smartphone rotating slowly on a reflective surface",
            "help_text": "Describe the product or subject clearly. Include material, color, and key features. Keep descriptions concise for better video coherence.",
            "options": None,
            "max_length": 200,
            "group": "composition",
        },
        {
            "name": "style",
            "label": "Visual Style",
            "field_type": "select",
            "required": True,
            "default": "cinematic commercial",
            "placeholder": None,
            "help_text": "The overall visual aesthetic of the video. Cinematic styles produce higher perceived quality in short-form ads.",
            "options": [
                {"value": "cinematic commercial", "label": "Cinematic Commercial", "preview_url": None},
                {"value": "product showcase", "label": "Product Showcase", "preview_url": None},
                {"value": "social media reels", "label": "Social Media Reels", "preview_url": None},
                {"value": "motion graphics", "label": "Motion Graphics", "preview_url": None},
                {"value": "lifestyle vlog", "label": "Lifestyle Vlog", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "mood",
            "label": "Mood / Atmosphere",
            "field_type": "tags",
            "required": True,
            "default": "dynamic, professional",
            "placeholder": "e.g. energetic, luxurious, playful",
            "help_text": "Emotional tone keywords that guide color grading and pacing. Multiple tags create richer atmosphere.",
            "options": [
                {"value": "dynamic", "label": "Dynamic", "preview_url": None},
                {"value": "professional", "label": "Professional", "preview_url": None},
                {"value": "energetic", "label": "Energetic", "preview_url": None},
                {"value": "luxurious", "label": "Luxurious", "preview_url": None},
                {"value": "playful", "label": "Playful", "preview_url": None},
                {"value": "calm", "label": "Calm", "preview_url": None},
                {"value": "bold", "label": "Bold", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "duration",
            "label": "Video Duration",
            "field_type": "select",
            "required": True,
            "default": "5s",
            "placeholder": None,
            "help_text": "Target video length. Shorter clips (3-5s) work best for social ads. Longer clips (10-15s) suit product demos.",
            "options": [
                {"value": "3s", "label": "3 seconds (Quick Hook)", "preview_url": None},
                {"value": "5s", "label": "5 seconds (Standard)", "preview_url": None},
                {"value": "10s", "label": "10 seconds (Extended)", "preview_url": None},
                {"value": "15s", "label": "15 seconds (Full Demo)", "preview_url": None},
            ],
            "max_length": None,
            "group": "technical",
        },
        {
            "name": "motion_style",
            "label": "Motion Style",
            "field_type": "select",
            "required": True,
            "default": "smooth orbit",
            "placeholder": None,
            "help_text": "Camera or subject movement type. Smooth motions convey premium feel; dynamic motions increase energy and engagement.",
            "options": [
                {"value": "smooth orbit", "label": "Smooth Orbit (360° rotation)", "preview_url": None},
                {"value": "slow zoom in", "label": "Slow Zoom In", "preview_url": None},
                {"value": "dolly forward", "label": "Dolly Forward", "preview_url": None},
                {"value": "parallax pan", "label": "Parallax Pan", "preview_url": None},
                {"value": "static reveal", "label": "Static Reveal (fade/dissolve)", "preview_url": None},
                {"value": "dynamic tracking", "label": "Dynamic Tracking", "preview_url": None},
            ],
            "max_length": None,
            "group": "composition",
        },
        {
            "name": "aspect_ratio",
            "label": "Aspect Ratio",
            "field_type": "select",
            "required": True,
            "default": "9:16",
            "placeholder": None,
            "help_text": "Platform sizing. TikTok/Reels = 9:16, YouTube Shorts = 9:16, Feed video = 1:1, YouTube/TV = 16:9.",
            "options": [
                {"value": "9:16", "label": "Vertical (9:16) — TikTok/Reels", "preview_url": None},
                {"value": "1:1", "label": "Square (1:1) — Feed Video", "preview_url": None},
                {"value": "16:9", "label": "Landscape (16:9) — YouTube/TV", "preview_url": None},
                {"value": "4:5", "label": "Portrait (4:5) — Instagram Feed", "preview_url": None},
            ],
            "max_length": None,
            "group": "technical",
        },
        {
            "name": "background",
            "label": "Background / Setting",
            "field_type": "text",
            "required": False,
            "default": "clean studio backdrop with soft gradient lighting",
            "placeholder": "e.g. futuristic neon environment, nature scene, abstract particles",
            "help_text": "Keep backgrounds simple for product focus. Animated backgrounds can distract from the subject.",
            "options": None,
            "max_length": 150,
            "group": "composition",
        },
        {
            "name": "lighting",
            "label": "Lighting",
            "field_type": "select",
            "required": False,
            "default": "studio three-point",
            "placeholder": None,
            "help_text": "Lighting setup affects product perception. Studio lighting conveys professionalism; neon suits tech products.",
            "options": [
                {"value": "studio three-point", "label": "Studio Three-Point", "preview_url": None},
                {"value": "dramatic rim light", "label": "Dramatic Rim Light", "preview_url": None},
                {"value": "soft natural light", "label": "Soft Natural Light", "preview_url": None},
                {"value": "neon accent", "label": "Neon Accent Lighting", "preview_url": None},
                {"value": "golden hour", "label": "Golden Hour", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
    ],
    "prompt_pattern": "{style} video, {subject}, {motion_style} camera movement, {mood} atmosphere, {lighting} lighting, {background}, {duration} duration, {aspect_ratio} format, high quality, smooth motion, professional color grading",
    "negative_prompt_pattern": "low quality, blurry, jittery motion, frame drops, watermark, distorted, flickering, amateur, noisy, abrupt cuts, static image, frozen frame",
    "example_output_url": None,
    "tags": ["product-demo", "short-form", "commercial", "social-media", "video-ad"],
}

# ─── Exported Templates List ──────────────────────────────────────────────────

TEMPLATES: list[PromptTemplate] = [
    PRODUCT_DEMO_VIDEO,
]

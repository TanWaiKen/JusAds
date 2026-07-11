"""
templates/poster_templates.py
─────────────────────────────
Prompt template definitions for poster ad types.

Templates are sourced from proven open-source image generation patterns
(Stable Diffusion, SDXL) via CivitAI and the SD community.

Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 13.1
"""

from . import PromptTemplate

# ─── Product Hero Shot ────────────────────────────────────────────────────────

POSTER_PRODUCT_HERO: PromptTemplate = {
    "template_id": "poster_product_hero",
    "ad_type": "poster",
    "name": "Product Hero Shot",
    "description": "A single hero product shot with clean background and text overlay",
    "source": {
        "name": "Stable Diffusion Community (CivitAI)",
        "url": "https://civitai.com/models/product-photography",
        "model": "SDXL 1.0",
    },
    "fields": [
        {
            "name": "subject",
            "label": "Main Subject",
            "field_type": "textarea",
            "required": True,
            "default": None,
            "placeholder": "e.g. A frosted glass bottle of perfume with gold cap",
            "help_text": (
                "Describe the product clearly. Include material, color, and "
                "distinguishing features. Based on SD product photography prompts."
            ),
            "options": None,
            "max_length": 200,
            "group": "composition",
        },
        {
            "name": "style",
            "label": "Visual Style",
            "field_type": "select",
            "required": True,
            "default": "editorial photography",
            "placeholder": None,
            "help_text": "The artistic style. Sourced from top SDXL photography prompts.",
            "options": [
                {"value": "editorial photography", "label": "Editorial Photography", "preview_url": None},
                {"value": "commercial product shot", "label": "Commercial Product Shot", "preview_url": None},
                {"value": "japanese minimalism", "label": "Japanese Minimalism (Muji style)", "preview_url": None},
                {"value": "flat lay overhead", "label": "Flat Lay Overhead", "preview_url": None},
                {"value": "lifestyle context", "label": "Lifestyle Context Shot", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "mood",
            "label": "Mood / Atmosphere",
            "field_type": "tags",
            "required": False,
            "default": "warm, inviting",
            "placeholder": "e.g. luxurious, energetic, calm",
            "help_text": "Emotional tone keywords. Multiple tags work best.",
            "options": [
                {"value": "warm", "label": "Warm", "preview_url": None},
                {"value": "cool", "label": "Cool", "preview_url": None},
                {"value": "luxurious", "label": "Luxurious", "preview_url": None},
                {"value": "energetic", "label": "Energetic", "preview_url": None},
                {"value": "minimal", "label": "Minimal", "preview_url": None},
                {"value": "bold", "label": "Bold", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "color_palette",
            "label": "Color Palette",
            "field_type": "text",
            "required": False,
            "default": None,
            "placeholder": "e.g. pastel pink, cream white, gold accent",
            "help_text": "Describe 2-4 colors. Comma-separated. Guides the overall tone.",
            "options": None,
            "max_length": 100,
            "group": "style",
        },
        {
            "name": "background",
            "label": "Background",
            "field_type": "text",
            "required": False,
            "default": "clean white studio background, soft shadows",
            "placeholder": "e.g. marble surface, tropical leaves, gradient",
            "help_text": "Keep it simple for product focus. Complex backgrounds distract.",
            "options": None,
            "max_length": 150,
            "group": "composition",
        },
        {
            "name": "text_overlay",
            "label": "Text Overlay",
            "field_type": "text",
            "required": False,
            "default": None,
            "placeholder": "e.g. Brand Name — Tagline Here",
            "help_text": "Text to render on the ad. Keep it short (under 8 words works best).",
            "options": None,
            "max_length": 80,
            "group": "composition",
        },
        {
            "name": "aspect_ratio",
            "label": "Aspect Ratio",
            "field_type": "select",
            "required": True,
            "default": "1:1",
            "placeholder": None,
            "help_text": "Platform sizing. Instagram feed = 1:1, Story = 9:16, Banner = 16:9.",
            "options": [
                {"value": "1:1", "label": "Square (1:1)", "preview_url": None},
                {"value": "4:5", "label": "Portrait (4:5)", "preview_url": None},
                {"value": "9:16", "label": "Story (9:16)", "preview_url": None},
                {"value": "16:9", "label": "Landscape (16:9)", "preview_url": None},
            ],
            "max_length": None,
            "group": "technical",
        },
    ],
    "prompt_pattern": (
        "masterpiece, {style}, {subject}, {mood}, {color_palette}, "
        "{background}, {text_overlay}, high quality, sharp focus, "
        "professional lighting, {aspect_ratio} aspect ratio"
    ),
    "negative_prompt_pattern": (
        "low quality, blurry, distorted, watermark, text artifacts, "
        "oversaturated, amateur, noisy, cropped"
    ),
    "example_output_url": None,
    "tags": ["product", "hero-shot", "clean", "commercial"],
}

# ─── Exports ──────────────────────────────────────────────────────────────────

TEMPLATES: list[PromptTemplate] = [
    POSTER_PRODUCT_HERO,
]

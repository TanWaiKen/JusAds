"""
carousel_templates.py
─────────────────────
Prompt template definitions for carousel ad type.

Carousel templates are designed for multi-slide ad content that tells a
product story or showcases features across sequential frames. Sourced from
proven open-source image generation patterns (SDXL, SeaArt).

Requirements: 1.3, 3.1, 3.2, 3.3, 3.4, 13.1
"""

from . import PromptTemplate

# ─── Product Story Carousel ───────────────────────────────────────────────────

PRODUCT_STORY_CAROUSEL: PromptTemplate = {
    "template_id": "carousel_product_story",
    "ad_type": "carousel",
    "name": "Product Story Carousel",
    "description": (
        "A multi-slide carousel that tells a product story across frames — "
        "from hero shot to detail close-ups to lifestyle context. "
        "Ideal for Instagram carousels and Facebook multi-image ads."
    ),
    "source": {
        "name": "SeaArt Community (Multi-frame Workflows)",
        "url": "https://www.seaart.ai/explore/carousel",
        "model": "SeaArt v3",
    },
    "fields": [
        {
            "name": "subject",
            "label": "Product / Subject",
            "field_type": "textarea",
            "required": True,
            "default": None,
            "placeholder": "e.g. A sleek wireless earbud case with matte black finish",
            "help_text": (
                "Describe the main product clearly. Include material, color, "
                "and key features. Each carousel slide will feature this subject "
                "from a different angle or context."
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
            "help_text": (
                "The consistent artistic style applied across all carousel slides. "
                "Maintaining a unified style ensures visual cohesion across frames."
            ),
            "options": [
                {"value": "editorial photography", "label": "Editorial Photography", "preview_url": None},
                {"value": "commercial product shot", "label": "Commercial Product Shot", "preview_url": None},
                {"value": "lifestyle storytelling", "label": "Lifestyle Storytelling", "preview_url": None},
                {"value": "flat lay sequence", "label": "Flat Lay Sequence", "preview_url": None},
                {"value": "3d render showcase", "label": "3D Render Showcase", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "mood",
            "label": "Mood / Atmosphere",
            "field_type": "tags",
            "required": True,
            "default": "modern, premium",
            "placeholder": "e.g. vibrant, trustworthy, youthful",
            "help_text": (
                "Emotional tone keywords applied consistently across all slides. "
                "Choose 2-3 moods for best results. Consistency across frames is key."
            ),
            "options": [
                {"value": "modern", "label": "Modern", "preview_url": None},
                {"value": "premium", "label": "Premium", "preview_url": None},
                {"value": "vibrant", "label": "Vibrant", "preview_url": None},
                {"value": "trustworthy", "label": "Trustworthy", "preview_url": None},
                {"value": "playful", "label": "Playful", "preview_url": None},
                {"value": "elegant", "label": "Elegant", "preview_url": None},
                {"value": "bold", "label": "Bold", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "color_palette",
            "label": "Color Palette",
            "field_type": "text",
            "required": True,
            "default": None,
            "placeholder": "e.g. deep navy, white, gold accent",
            "help_text": (
                "Define 2-4 colors for the carousel. A consistent palette ties "
                "all slides together visually. Comma-separated values."
            ),
            "options": None,
            "max_length": 100,
            "group": "style",
        },
        {
            "name": "background",
            "label": "Background",
            "field_type": "text",
            "required": False,
            "default": "clean gradient background, soft studio lighting",
            "placeholder": "e.g. textured concrete, botanical elements, gradient",
            "help_text": (
                "Background style for the carousel slides. Use a consistent "
                "background to unify the carousel. Simple backgrounds keep focus on the product."
            ),
            "options": None,
            "max_length": 150,
            "group": "composition",
        },
        {
            "name": "slide_narrative",
            "label": "Slide Narrative",
            "field_type": "textarea",
            "required": False,
            "default": "hero shot, detail close-up, lifestyle context, call to action",
            "placeholder": "e.g. unboxing, product front, features, in-use, price",
            "help_text": (
                "Describe the story arc across slides. List the progression "
                "of frames separated by commas. This guides the visual sequence."
            ),
            "options": None,
            "max_length": 300,
            "group": "composition",
        },
        {
            "name": "aspect_ratio",
            "label": "Aspect Ratio",
            "field_type": "select",
            "required": True,
            "default": "1:1",
            "placeholder": None,
            "help_text": (
                "Platform sizing for each carousel slide. Instagram carousel = 1:1, "
                "Facebook carousel = 1:1 or 4:5, Pinterest = 2:3."
            ),
            "options": [
                {"value": "1:1", "label": "Square (1:1)", "preview_url": None},
                {"value": "4:5", "label": "Portrait (4:5)", "preview_url": None},
                {"value": "2:3", "label": "Pinterest (2:3)", "preview_url": None},
                {"value": "9:16", "label": "Story (9:16)", "preview_url": None},
            ],
            "max_length": None,
            "group": "technical",
        },
    ],
    "prompt_pattern": (
        "masterpiece, {style}, {subject}, {mood}, {color_palette}, "
        "{background}, multi-frame carousel sequence, {slide_narrative}, "
        "cohesive visual series, high quality, sharp focus, "
        "professional lighting, {aspect_ratio} aspect ratio"
    ),
    "negative_prompt_pattern": (
        "low quality, blurry, distorted, watermark, text artifacts, "
        "oversaturated, amateur, noisy, cropped, inconsistent style between frames, "
        "mismatched colors, disjointed narrative"
    ),
    "example_output_url": None,
    "tags": ["carousel", "product-story", "multi-slide", "sequential", "e-commerce"],
}

# ─── Feature Showcase Carousel ────────────────────────────────────────────────

FEATURE_SHOWCASE_CAROUSEL: PromptTemplate = {
    "template_id": "carousel_feature_showcase",
    "ad_type": "carousel",
    "name": "Feature Showcase Carousel",
    "description": (
        "A carousel that highlights individual product features one per slide. "
        "Each frame isolates a specific benefit or feature with bold typography "
        "guidance. Great for tech products, SaaS, and feature-rich items."
    ),
    "source": {
        "name": "Stable Diffusion Community (CivitAI)",
        "url": "https://civitai.com/models/product-photography",
        "model": "SDXL 1.0",
    },
    "fields": [
        {
            "name": "subject",
            "label": "Product / Subject",
            "field_type": "textarea",
            "required": True,
            "default": None,
            "placeholder": "e.g. A smart fitness watch with AMOLED display",
            "help_text": (
                "The product whose features are being showcased. Be specific about "
                "form factor, materials, and visual identity. Each slide will "
                "emphasize a different feature of this product."
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
            "default": "commercial product shot",
            "placeholder": None,
            "help_text": (
                "Photography or render style for the feature slides. "
                "Clean, focused styles work best for feature isolation."
            ),
            "options": [
                {"value": "commercial product shot", "label": "Commercial Product Shot", "preview_url": None},
                {"value": "tech product render", "label": "Tech Product Render", "preview_url": None},
                {"value": "macro detail photography", "label": "Macro Detail Photography", "preview_url": None},
                {"value": "infographic style", "label": "Infographic Style", "preview_url": None},
                {"value": "editorial photography", "label": "Editorial Photography", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "mood",
            "label": "Mood / Atmosphere",
            "field_type": "tags",
            "required": True,
            "default": "professional, innovative",
            "placeholder": "e.g. futuristic, clean, confident",
            "help_text": (
                "The emotional tone for each feature slide. Keep moods consistent "
                "to maintain carousel cohesion. 2-3 tags recommended."
            ),
            "options": [
                {"value": "professional", "label": "Professional", "preview_url": None},
                {"value": "innovative", "label": "Innovative", "preview_url": None},
                {"value": "futuristic", "label": "Futuristic", "preview_url": None},
                {"value": "clean", "label": "Clean", "preview_url": None},
                {"value": "confident", "label": "Confident", "preview_url": None},
                {"value": "dynamic", "label": "Dynamic", "preview_url": None},
            ],
            "max_length": None,
            "group": "style",
        },
        {
            "name": "color_palette",
            "label": "Color Palette",
            "field_type": "text",
            "required": True,
            "default": None,
            "placeholder": "e.g. matte black, electric blue accent, white",
            "help_text": (
                "2-4 colors that define the visual identity across all feature "
                "slides. Use brand colors for consistency. Comma-separated."
            ),
            "options": None,
            "max_length": 100,
            "group": "style",
        },
        {
            "name": "background",
            "label": "Background",
            "field_type": "text",
            "required": False,
            "default": "solid dark background with subtle gradient, dramatic lighting",
            "placeholder": "e.g. pure white, dark gradient, abstract geometric",
            "help_text": (
                "Keep backgrounds minimal to let the product feature stand out. "
                "Dark backgrounds with accent lighting work well for tech products."
            ),
            "options": None,
            "max_length": 150,
            "group": "composition",
        },
        {
            "name": "aspect_ratio",
            "label": "Aspect Ratio",
            "field_type": "select",
            "required": True,
            "default": "1:1",
            "placeholder": None,
            "help_text": (
                "Platform sizing for carousel slides. Square (1:1) is standard "
                "for Instagram and Facebook carousels."
            ),
            "options": [
                {"value": "1:1", "label": "Square (1:1)", "preview_url": None},
                {"value": "4:5", "label": "Portrait (4:5)", "preview_url": None},
                {"value": "2:3", "label": "Pinterest (2:3)", "preview_url": None},
                {"value": "16:9", "label": "Landscape (16:9)", "preview_url": None},
            ],
            "max_length": None,
            "group": "technical",
        },
    ],
    "prompt_pattern": (
        "masterpiece, {style}, {subject}, {mood}, {color_palette}, "
        "{background}, isolated feature highlight, bold clean composition, "
        "high quality, sharp focus, professional product lighting, "
        "{aspect_ratio} aspect ratio"
    ),
    "negative_prompt_pattern": (
        "low quality, blurry, distorted, watermark, text artifacts, "
        "oversaturated, amateur, noisy, cropped, cluttered background, "
        "multiple products, busy composition"
    ),
    "example_output_url": None,
    "tags": ["carousel", "feature-showcase", "tech", "product-features", "benefits"],
}

# ─── Exported list ────────────────────────────────────────────────────────────

TEMPLATES: list[PromptTemplate] = [
    PRODUCT_STORY_CAROUSEL,
    FEATURE_SHOWCASE_CAROUSEL,
]

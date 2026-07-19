You are a professional short-form video ad Director.
Plan exactly {clip_count} scenes for a {duration}-second video. Every scene MUST have a fixed duration of {clip_seconds} seconds. The final scene count and fixed durations must exactly total {duration} seconds.

Brief: "{brief}"
Target audience: {ethnicity} in {market}
Platform: TikTok/Reels (vertical 9:16)

For EACH scene provide:
- "scene_index": number (1-based)
- "visual_description": what happens visually (setting, action, lighting)
- "camera_angle": shot type + movement (e.g. "CU slow push in", "WS static")
- "character_action": what the character does (pose, expression, gesture)
- "character_requirements": clothing/appearance for THIS scene
- "subtitle": on-screen text (max 8 words, punchy)
- "voiceover": spoken line (max 15 words)
- "transition_to_next": how this flows to next ("character turns", "zoom in", "cut")

STRUCTURE: Scene 1-2 = HOOK (attention grabber). Middle = PRODUCT. Final = CTA.

- "character_summary": overall character appearance (for character sheet generation, described as a real human model, photorealistic, with clothing details). Leave empty if no human character is present.
- "skip_character_creation": boolean. Set to true if the ad focuses entirely on product closeups, scenery, environment, or text/motion graphics without any recurring human character, or if a dedicated character sheet is unnecessary. Otherwise, set to false.
- "product_integration": how product appears across scenes
- "visual_style": ONE consistent photography/visual style for ALL scenes. It MUST be a photorealistic real human style. Always DEFAULT to "photorealistic commercial photography, cinematic lighting, real human model, shot on Sony A7IV". Under no circumstances generate character descriptions that imply cartoon, anime, 3D render, illustration, drawings, or sketches. Ads perform best with REAL HUMAN models — not illustrations.

Return JSON: {{"character_summary": "...", "skip_character_creation": true/false, "product_integration": "...", "visual_style": "...", "scenes": [...]}}

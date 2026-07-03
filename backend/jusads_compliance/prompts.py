"""
prompts.py
──────────
All fixed prompts used by the compliance pipeline.
Separated for easy editing and version control.
"""

# ── Unified output template (shared across all compliance checks) ─────────────
UNIFIED_OUTPUT_TEMPLATE = """{{"risk_percentage": 35, "risk_level": "Moderate", "compliance_verdict": "needs_remediation", "high_risk_indicator": ["flagged item 1", "flagged item 2"], "violations_timeline": null, "localization_plan": "Use appropriate model, translate to target language, target relevant platform", "explanation": "35% risk due to...", "suggestion": "Replace or modify...", "cultural_fit_score": 70, "language_compliance": {{"detected_language": "english", "required_language": "malay", "is_compliant": false, "language_note": "Target audience (Malay Baby Boomers) requires Bahasa Melayu"}}}}"""


# ── Contextual Decision Framework (injected into all compliance prompts) ──────

CONTEXT_FRAMEWORK = """
## CRITICAL: Context-Aware Decision Framework

You are evaluating advertising content. Your job is to assess cultural appropriateness — NOT to be overly conservative.

### LANGUAGE COMPLIANCE (HARD RULE — Non-Negotiable)
Language mismatch is the ONLY absolute violation. If the ad language does not match what the target audience expects:
- Malay Baby Boomers / Gen X → Must be in Bahasa Melayu (formal)
- Malay Gen Z / Millennial → Bahasa Melayu or Manglish (code-switching OK)
- Chinese Baby Boomers → Must be in Cantonese/Mandarin (Chinese script)
- Chinese Gen Z → Mandarin + English mix acceptable
- Indian Baby Boomers → Must be in Tamil
- Indian Gen Z → Tamil-English mix (Tanglish) acceptable

A Malay-language ad targeting Chinese audiences = CRITICAL violation (auto-reject).
An English-only ad targeting Malay Baby Boomers = HIGH risk.

### CONTEXTUAL EVALUATION (Flexible — Use Judgment)
For visual and content elements, evaluate based on PRODUCT CONTEXT:

**Before flagging skin exposure, ASK:**
1. What product is being advertised? (skincare, fashion, fitness = exposure often justified)
2. Is the exposure integral to demonstrating the product? (showing cream application on arm = OK)
3. Does it match what REAL ads on this platform show for this product category?
4. What is the target ethnicity's actual tolerance? (Chinese audiences accept beauty ads with arm/shoulder exposure)

**Escalation levels by platform placement:**
- TikTok / Instagram → Most relaxed (matches what's already on the platform)
- Facebook / YouTube → Moderate (broader audience)
- TV / Government / Official → Strictest (public broadcast standards)

### BUSINESS CONTEXT
{business_context}

### PRODUCT CONTEXT RULES
- Skincare/Beauty: Showing product application on skin (arms, face, neck) is STANDARD — do not flag as violation
- Kids Clothing: Children in age-appropriate clothing is STANDARD — do not flag
- Fitness/Sportswear: Athletic wear showing arms/legs is STANDARD for the category
- Lingerie/Underwear: Still requires careful handling — flag for Malay audiences but acceptable for Chinese on Instagram/TikTok

### OUTPUT MUST INCLUDE
- compliance_verdict: "accepted" / "needs_remediation" / "rejected"
- cultural_fit_score: 0-100 (how well the ad fits the specific target audience)
- language_compliance: object with detected_language, required_language, is_compliant, language_note
"""


# ── Pre-scan prompts (describe media content before compliance check) ─────────

IMAGE_PRESCAN_PROMPT = "What is in this image? Directly state: what product, what people are doing, what they are wearing, any text or numbers shown, and the setting. Be factual."

VIDEO_PRESCAN_PROMPT = "What is happening in this video? Describe: people, clothing, actions, products, text on screen, setting. Be factual."


# ── Compliance check prompts ──────────────────────────────────────────────────

TEXT_COMPLIANCE_PROMPT = """You are a {market} Cultural Appropriateness Evaluator. Evaluate ad text for compliance.

""" + CONTEXT_FRAMEWORK + """

INPUT (ad text):
{text}

### Regulatory & Platform Guidelines ({market} + {platform})
{rules_text}

### Target Audience Persona
{persona_text}

TASK: Detect phrases or themes that are culturally sensitive, offensive, or non-compliant.

Risk Logic: Severe regulatory +30%, Moderate +20%, Minor +10%, Severe cultural +25%, Moderate +15%, Minor +8%. Cap 100%.

Return ONLY a JSON object with this EXACT structure:
- risk_percentage: integer 0-100
- risk_level: "Low" (0-30) / "Moderate" (31-60) / "High" (61-80) / "Critical" (81-100)
- high_risk_indicator: array of flagged phrases (max 10, ranked by severity)
- violations_timeline: null (not applicable for text)
- localization_plan: string with localization advice for this audience
- explanation: concise reasoning (max 300 words)
- suggestion: actionable fix advice (max 200 words)

OUTPUT FORMAT:
{output_template}"""


IMAGE_COMPLIANCE_PROMPT = """You are a {market} Visual Ad Compliance Evaluator. Evaluate this image for compliance.

""" + CONTEXT_FRAMEWORK + """### Regulatory & Platform Guidelines ({market} + {platform})
{rules_text}

### Target Audience Persona
{persona_text}

TASK: Analyze the image for visual elements that are culturally sensitive, offensive, or non-compliant.

Risk Logic: Severe regulatory +30%, Moderate +20%, Minor +10%, Severe cultural +25%, Moderate +15%, Minor +8%. Cap 100%.

Return ONLY a JSON object with this EXACT structure:
- risk_percentage: integer 0-100
- risk_level: "Low" / "Moderate" / "High" / "Critical"
- high_risk_indicator: array of flagged visual elements (max 10)
- violations_timeline: array of objects with region description (e.g. "top-left quadrant") and type "visual"
- localization_plan: string with localization advice
- explanation: concise reasoning (max 300 words)
- suggestion: actionable fix advice (max 200 words)

OUTPUT FORMAT:
{output_template}"""


AUDIO_COMPLIANCE_PROMPT = """You are a {market} Audio Ad Compliance Evaluator.

""" + CONTEXT_FRAMEWORK + """

FIRST: You have been provided a transcript of this audio. Use it as the source of truth for what is said.

TRANSCRIPT:
{transcript}

DETECTED LANGUAGE: {language}

### Regulatory & Platform Guidelines ({market} + {platform})
{rules_text}

### Target Audience Persona
{persona_text}

TASK: Evaluate the CONTENT (what is said) for regulatory compliance only.
- Detect culturally sensitive, offensive, or non-compliant spoken content
- Check for misleading claims, unsubstantiated health/performance claims
- Check for prohibited product advertising (alcohol, gambling, tobacco to minors)
- Note if content could cause racial or religious disharmony

DO NOT penalize:
- Aggressive, energetic, or fast-paced delivery style (this is creative choice)
- Loud volume or excitement (not a compliance issue)
- Background music style or tempo

Risk Logic: Severe regulatory violation +30%, Misleading/unsubstantiated claims +25%, Prohibited content +20%, Cultural/religious insensitivity +15%, Minor phrasing issue +8%. Cap 100%.

Return ONLY a JSON object with this EXACT structure:
- risk_percentage: integer 0-100
- risk_level: "Low" (0-30) / "Moderate" (31-60) / "High" (61-80) / "Critical" (81-100)
- high_risk_indicator: array of flagged content issues (max 10)
- violations_timeline: null (not applicable for audio-only)
- localization_plan: string with localization advice
- explanation: concise reasoning focused on CONTENT violations only (max 300 words)
- suggestion: actionable fix advice (max 200 words)

OUTPUT FORMAT:
{output_template}"""


VIDEO_COMPLIANCE_PROMPT = """You are a {market} Video Ad Compliance Evaluator. Watch this video and evaluate for compliance.

""" + CONTEXT_FRAMEWORK + """
### Regulatory & Platform Guidelines ({market} + {platform})
{rules_text}

### Target Audience Persona
{persona_text}

TASK: Evaluate ALL dimensions — visuals, spoken audio, text overlays, and delivery.
- Flag visual violations with timestamps [SS-SS]
- Analyze spoken content and tone/delivery
- Check text overlays for misleading claims
- Note scene transitions and background audio

Risk Logic: Severe regulatory +30%, Visual modesty +25%, Aggressive tone +20%, Misleading text +15%, Minor +8%. Cap 100%.

Return ONLY a JSON object with this EXACT structure:
- risk_percentage: integer 0-100
- risk_level: "Low" / "Moderate" / "High" / "Critical"
- high_risk_indicator: array with timestamps like "[00:03-00:08] exposed shoulders" (max 10)
- violations_timeline: array of objects with start_seconds, end_seconds, type ("visual"/"audio"/"text"), description
- localization_plan: string with language, model talent, platform recommendations
- explanation: concise reasoning (max 300 words)
- suggestion: actionable fix advice (max 200 words)

OUTPUT FORMAT:
{output_template}"""


# ── Bias & Hallucination evaluator prompt ─────────────────────────────────────

BIAS_HALLUCINATION_PROMPT = """You are an expert evaluator assessing compliance analysis output for bias AND hallucination.

## BIAS CHECK
Biased or unfair content includes:
- Stereotyping based on race, gender, age, religion, nationality, disability, or sexuality
- Unequal or inconsistent treatment of comparable groups or individuals
- Language that demeans, marginalizes, or excludes a group
- Outputs that reflect historical or systemic prejudices without critical framing
- Recommendations or decisions that disadvantage protected groups without justification

Not considered bias:
- Factual reporting of demographic differences with appropriate context
- Discussing bias itself in an analytical or educational frame
- Personal preferences that do not implicate protected characteristics

## HALLUCINATION CHECK
Check whether the compliance analysis:
- Made up rules or violations not present in the provided regulatory context
- Cited non-existent regulations or policies
- Attributed claims to sources without basis
- Invented cultural norms not supported by the persona data

## INPUT
Regulatory context (rules the model had access to):
{context_rules}

Persona context:
{persona}

Compliance analysis output to evaluate:
{compliance_result}

## TASK
Evaluate the compliance analysis for BOTH bias and hallucination.

Return ONLY a JSON object:
{{
    "bias_detected": true/false,
    "bias_issues": ["issue 1", "issue 2"],
    "hallucination_score": 1-5 (1=severe hallucination, 5=fully grounded),
    "hallucinated_claims": ["claim 1", "claim 2"],
    "overall_pass": true/false,
    "explanation": "brief reasoning"
}}

overall_pass is TRUE only if bias_detected is false AND hallucination_score >= 4."""



# ── Text Rewrite prompt (Remix Remediation) ──────────────────────────────────

TEXT_REWRITE_PROMPT = """You are an expert ad copywriter and compliance specialist.

Rewrite the following ad text to fix ALL identified compliance violations while preserving brand voice and marketing intent.

ORIGINAL TEXT:
{text}

VIOLATIONS TO FIX:
{violations_text}

TARGET CONTEXT:
- Market: {market}
- Platform: {platform}
- Ethnicity: {ethnicity}
- Age Group: {age_group}

{feedback_section}

LANGUAGE REQUIREMENT:
The original text is written in {detected_language}. You MUST produce the rewritten text in the SAME language ({detected_language}). Do NOT translate to English or any other language.

PLATFORM TONE GUIDE:
- TikTok: casual, short, punchy, emoji OK, Gen Z slang acceptable, vibrant
- Meta: slightly formal, family-friendly, clear CTA, clean professional tone
- Instagram: aspirational, lifestyle-focused, hashtag-friendly

LENGTH CONSTRAINT:
The original text is {original_length} characters. Your rewritten text MUST be between {min_length} and {max_length} characters (within 20% of original length).

RULES:
1. Fix ONLY the flagged compliance violations
2. Preserve the original product, brand name, and call-to-action
3. Match the platform tone and target audience age group
4. Localize appropriately for the {ethnicity} audience in {market}
5. Maintain the same language as the original
6. Stay within the length constraint

Return ONLY a JSON object:
{{"rewritten_text": "the compliant rewritten text", "changes_made": ["description of change 1", "description of change 2"]}}

The "changes_made" list must have at least one entry explaining what was modified and why."""


# ── Segmentation prompt (CLIPSeg) ────────────────────────────────────────────

SEGMENTATION_PROMPT = """Look at this image carefully. Identify the people or objects that are non-compliant based on these violations:
{violations}

The image is {width}x{height} pixels.

IMPORTANT: Do NOT segment individual body parts (arms, legs, hair, armpits separately).
Instead, draw ONE bounding box around each WHOLE PERSON or WHOLE OBJECT that is violating.

For example:
- If a woman is showing exposed arms + legs + hair → draw ONE box around her entire body
- If multiple women are non-compliant → draw ONE box per woman
- Label each box with a summary like "Woman in underwear (exposed body, uncovered hair)"

Return a JSON array where each item has:
- "label": summary of what makes this person/object non-compliant
- "box": [x1, y1, x2, y2] as pixel coordinates (integers, top-left origin)

Rules:
- x1,y1 = top-left corner of the bounding box
- x2,y2 = bottom-right corner
- Values must be 0 to {width} for x, 0 to {height} for y
- ONE box per violating person/entity — not per body part
- Maximum 10 boxes (one per person or distinct violating object)
- Return [] if nothing found
- Make boxes tight around the full person/object

Example: [{{"label": "Woman in revealing clothing (exposed arms, legs, uncovered hair)", "box": [50, 30, 300, 500]}}]"""


# ── SCULPT framework prompt for image editing ─────────────────────────────────

SCULPT_PROMPT_TEMPLATE = """You are an expert image editing prompt engineer. Generate a SCULPT framework prompt for editing an advertising image.

VIOLATIONS TO FIX:
{violations}

LOCALIZATION & COMPLIANCE GUIDANCE:
{localization_plan}

TARGET AUDIENCE:
- Market: {market}
- Platform: {platform}
- Ethnicity: {ethnicity}
- Age group: {age_group}

PLATFORM STYLE GUIDE:
{platform_style}

Generate a structured image editing prompt using the SCULPT framework. Each component MUST be present:

1. **Subject**: What should appear in the edited region — follow the localization guidance strictly
   (e.g. if guidance says "show product only, no face" — describe the product placement, not a person)
2. **Context**: Platform aesthetic, market context, and cultural considerations from the localization plan
3. **Use**: The advertising purpose and compliance goal of this edit
4. **Look**: Visual style that matches the original image's tone and branding
5. **Photographic**: Lighting direction, perspective, depth of field choices
6. **Technical**: Resolution requirements, edge quality, and constraints

MANDATORY REQUIREMENTS — you MUST include these exact phrases in the Technical section:
- "preserve sharp edges"
- "no text"
- "maintain lighting direction"

MANDATORY REQUIREMENTS — include platform keywords:
Include these platform-specific style keywords in the output: {platform_keywords}

Return the prompt as a single cohesive paragraph combining all SCULPT components, clearly labeled with [Subject], [Context], [Use], [Look], [Photographic], [Technical] markers.
"""

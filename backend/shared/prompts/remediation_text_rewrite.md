You are an expert ad copywriter and compliance specialist.

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

LOCALIZATION PLAN:
{localization_plan}

{feedback_section}

LANGUAGE REQUIREMENT:
{language_instruction}

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
4. Localize appropriately for the {ethnicity} audience in {market}, following the localization plan
5. Follow the language requirement above; it takes precedence over the source language
6. Stay within the length constraint

Return ONLY a JSON object:
{{"rewritten_text": "the compliant rewritten text", "changes_made": ["description of change 1", "description of change 2"]}}

The "changes_made" list must have at least one entry explaining what was modified and why.

You are an expert image editing prompt engineer. Generate a SCULPT framework prompt for editing an advertising image.

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
- "no unapproved text"
- "maintain lighting direction"

MANDATORY REQUIREMENTS — include platform keywords:
Include these platform-specific style keywords in the output: {platform_keywords}

Return the prompt as a single cohesive paragraph combining all SCULPT components, clearly labeled with [Subject], [Context], [Use], [Look], [Photographic], [Technical] markers.

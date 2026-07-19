"""Localization planning agent shared by every remediation modality.

The compliance task already contains the explicitly selected audience persona
and the language requirement determined during compliance analysis. This agent
turns those saved task fields into one concrete generation instruction before a
media model or TTS provider runs. It is intentionally deterministic: language
choice should be auditable and must not consume another model call.
"""

from __future__ import annotations


_LANGUAGE_SPECS = {
    "malay": ("Bahasa Melayu", "latin"),
    "english": ("English", "latin"),
    "chinese": ("Simplified Chinese (Mandarin)", "han"),
    "cantonese": ("Chinese (Cantonese)", "han"),
    "tamil": ("Tamil", "tamil"),
    # These are deliberately mixed-language labels. The persona's `script`
    # determines whether the generated copy must include Tamil characters.
    "english_tamil": ("English–Tamil mix", "latin"),
}


def _script_from_persona(value: object, default: str) -> str:
    """Translate the persona dataset's script label to the validation guard."""
    label = str(value or "").lower()
    if "tamil" in label:
        return "tamil"
    if "chinese" in label or "han" in label:
        return "han"
    return default


def plan_localization(
    *,
    market: str,
    ethnicity: str,
    age_group: str,
    platform: str,
    required_language: str = "",
    localization_plan: str = "",
) -> dict:
    """Choose the locale from the same persisted persona used by compliance.

    ``localization_plan`` remains model guidance about compliant claims,
    imagery and tone. It is never parsed to choose language.
    """
    required = required_language.lower().strip()
    persona = ethnicity.lower().strip()

    # Resolve the full age-specific persona from the same Supabase table used
    # in fetch_rules_and_personas.  This allows, for example, Chinese Gen Z
    # (Chinese-first) and Chinese millennials (English-first) to differ.
    try:
        from jusads_compliance.rules_client import get_persona

        persona_data = get_persona(market=market, ethnicity=persona, age_group=age_group)
    except Exception:
        persona_data = {}

    age_details = persona_data.get("age_group_details", {}) if isinstance(persona_data, dict) else {}
    preferred = age_details.get("preferred_language", {}) if isinstance(age_details, dict) else {}
    primary = str(preferred.get("primary", "")).lower()
    if primary in _LANGUAGE_SPECS:
        language, default_script = _LANGUAGE_SPECS[primary]
        script = _script_from_persona(preferred.get("script"), default_script)
        source = "compliance_persona"
    # For a generic persona, a single explicit language finding from the
    # compliance result is the next safest authoritative source.
    elif required in {"bahasa melayu", "malay"}:
        language, script = "Bahasa Melayu", "latin"
        source = "compliance_language_requirement"
    elif required in {"mandarin", "simplified chinese"}:
        language, script = "Simplified Chinese (Mandarin)", "han"
        source = "compliance_language_requirement"
    elif required in {"cantonese", "traditional chinese"}:
        language, script = "Traditional Chinese (Cantonese)", "han"
        source = "compliance_language_requirement"
    elif required == "tamil":
        language, script = "Tamil", "tamil"
        source = "compliance_language_requirement"
    elif required == "english":
        language, script = "English", "latin"
        source = "compliance_language_requirement"
    else:
        language, script = required_language.strip() or "English", "latin"
        source = "compliance_language_requirement"

    tone_by_platform = {
        "tiktok": "concise, conversational, energetic, and suitable for short-form video",
        "instagram": "aspirational, visual-first, and concise",
        "meta": "clear, professional, and family-safe",
    }
    return {
        "market": market,
        "audience_persona": ethnicity,
        "age_group": age_group,
        "platform": platform,
        "output_language": language,
        "required_script": script,
        "secondary_language": preferred.get("secondary", "") if isinstance(preferred, dict) else "",
        "code_switch": bool(preferred.get("code_switch")) if isinstance(preferred, dict) else False,
        "register": preferred.get("register", "") if isinstance(preferred, dict) else "",
        "tone": tone_by_platform.get(platform.lower(), "clear, respectful, and audience-appropriate"),
        "source": source,
    }


def has_required_script(text: str, script: str) -> bool:
    """Cheap pre-TTS guard for scripts where Unicode provides a clear signal."""
    if script == "han":
        return any("\u3400" <= character <= "\u9fff" for character in text)
    if script == "tamil":
        return any("\u0b80" <= character <= "\u0bff" for character in text)
    return True

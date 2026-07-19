"""Audio remediation agent using the production rewrite and TTS tools."""

from jusads_compliance.remix_tools import remix_audio, rewrite_text


def remediate_audio(state: dict) -> dict:
    result = state.get("compliance_result", {})
    plan = state.get("remediation_plan", {})
    transcript = result.get("transcript") or result.get("_transcript") or {}
    source_text = transcript.get("transcript") if isinstance(transcript, dict) else ""
    language_compliance = result.get("language_compliance") or {}
    required_language = language_compliance.get("required_language", "") if isinstance(language_compliance, dict) else ""
    localization = plan.get("localization") or {}
    rewrite = rewrite_text.invoke({
        "text": source_text or plan.get("suggestion", "Create a compliant replacement."),
        "violations": plan.get("high_risk_indicators", []),
        "market": result.get("market", "malaysia"),
        "platform": state.get("platform_target", "general"),
        "ethnicity": result.get("ethnicity", "all"),
        "age_group": result.get("age_group", "all_ages"),
        "required_language": localization.get("output_language", required_language),
        "localization_plan": plan.get("localization_plan", ""),
    })
    if rewrite.get("script_valid") is False:
        return {
            "error": (
                f"The rewrite did not satisfy the required output language "
                f"({rewrite.get('target_language', localization.get('output_language', required_language))}). No audio was generated."
            )
        }
    timeline = plan.get("violations_timeline") or [{"start": 0, "end": 30}]
    generated = remix_audio.invoke({
        "audio_path": state["source_media_url"],
        "violations": timeline,
        "replacement_text": rewrite.get("rewritten_text", ""),
        "market": result.get("market", "malaysia"),
        "ethnicity": result.get("ethnicity", "all"),
    })
    if generated.get("error"):
        return generated
    return {
        "output_path": generated["output_path"],
        "strategy": "audio_tts",
        "voice_id": generated.get("voice_id"),
        "duration_seconds": generated.get("duration_seconds"),
        "rewritten_text": rewrite.get("rewritten_text", ""),
    }

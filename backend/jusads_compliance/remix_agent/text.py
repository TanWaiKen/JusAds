"""Text remediation agent."""

import os
import tempfile

from jusads_compliance.remix_tools import rewrite_text


def remediate_text(state: dict) -> dict:
    result = state.get("compliance_result", {})
    plan = state.get("remediation_plan", {})
    localization = plan.get("localization") or {}
    text = result.get("original_text") or result.get("text_input")
    if not text:
        return {"error": "No original text was stored for this compliance check."}

    rewritten = rewrite_text.invoke({
        "text": text,
        "violations": plan.get("high_risk_indicators", []),
        "market": result.get("market", "malaysia"),
        "platform": state.get("platform_target", "general"),
        "ethnicity": result.get("ethnicity", "all"),
        "age_group": result.get("age_group", "all_ages"),
        "required_language": localization.get("output_language", ""),
        "localization_plan": plan.get("localization_plan", ""),
    })
    if rewritten.get("script_valid") is False:
        return {"error": f"The rewrite did not satisfy {rewritten.get('target_language', 'the required language')}."}
    output_path = os.path.join(tempfile.gettempdir(), f"remediated_text_{state['task_id']}.txt")
    with open(output_path, "w", encoding="utf-8") as output:
        output.write(rewritten.get("rewritten_text", text))
    return {"output_path": output_path, "strategy": "text_rewrite", "changes_made": rewritten.get("changes_made", [])}

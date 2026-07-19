"""Image remediation agent using the production Imagen edit tool."""

from jusads_compliance.remix_tools import edit_image


def remediate_image(state: dict) -> dict:
    result = state.get("compliance_result", {})
    plan = state.get("remediation_plan", {})
    localization = plan.get("localization") or {}
    localization_plan = plan.get("localization_plan", "")
    if localization.get("output_language"):
        localization_plan = f"{localization_plan}\nRequired generated copy language: {localization['output_language']}."
    edit = edit_image.invoke({
        "project_id": str(state.get("project_id") or state["task_id"]),
        "task_id": state["task_id"],
        "violations": plan.get("high_risk_indicators", []),
        "market": result.get("market", "malaysia"),
        "platform": state.get("platform_target", "general"),
        "ethnicity": result.get("ethnicity", "all"),
        "age_group": result.get("age_group", "all_ages"),
        "localization_plan": localization_plan,
    })
    if edit.get("error"):
        return edit
    return {"output_path": edit.get("output_path"), "asset_url": edit.get("s3_url"), "strategy": "image_inpaint", "quality_score": edit.get("quality_score")}

"""Normalised, immutable provenance persisted with every generated asset."""

from __future__ import annotations

from typing import Any, Mapping


def generated_ad_context_fields(context: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return the generated_ads columns derived from an orchestration context.

    The explicit columns support filtering and reporting; JSON snapshots preserve
    the exact settings and research that produced this particular version.
    """
    data = dict(context or {})
    localization = {
        "plan": data.pop("localization_plan", ""),
        "sources": data.pop("localization_sources", []),
        "target_language": data.get("language", "auto"),
    }
    brand = data.pop("brand_snapshot", {}) or {}
    parent_ad_id = data.pop("parent_ad_id", None)
    return {
        "asset_role": "output",
        "generation_mode": data.pop("generation_mode", "advanced"),
        "parent_ad_id": parent_ad_id,
        "market": data.get("market"),
        "ethnicity": data.get("target_ethnicity"),
        "age_group": data.get("age_group"),
        "target_language": data.get("language"),
        "generation_context": data,
        "brand_snapshot": brand,
        "localization_snapshot": localization,
    }

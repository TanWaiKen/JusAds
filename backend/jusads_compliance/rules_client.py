"""
rules_client.py
───────────────
Query regulatory rules and personas from Supabase (replaces Qdrant RAG).

Since the dataset is small, we fetch rules by source/category filters
and pass them directly to the AI model for evaluation.
"""

import logging
from typing import Optional

from shared.clients import supabase

logger = logging.getLogger(__name__)

# UI-friendly labels used by task creation mapped to the stable persona keys
# stored in the personas table and migration JSON.
_AGE_GROUP_ALIASES = {
    "teens": "gen_z",
}


def get_rules(
    market: str,
    platform: Optional[str] = None,
    category: Optional[str] = None,
) -> list[dict]:
    """Fetch ad policy rules from Supabase filtered by market/source.

    Args:
        market: Market source to filter (e.g. 'malaysia', 'singapore').
        platform: Optional platform source to include (e.g. 'tiktok', 'meta').
        category: Optional category filter.

    Returns:
        List of rule dicts with keys: id, source, regulator, framework,
        category, rule_title, rule_text, applies_to, enforcement, tags.
    """
    try:
        # Build source filter: always include market, optionally platform
        sources = [market.lower()]
        if platform:
            sources.append(platform.lower())

        query = (
            supabase.table("ad_policy_rules")
            .select("id, source, regulator, framework, category, rule_title, rule_text, applies_to, enforcement, tags")
            .in_("source", sources)
        )

        if category:
            query = query.eq("category", category)

        response = query.execute()
        rules = response.data or []
        logger.info(f"[RulesClient] Fetched {len(rules)} rules for sources={sources}")
        return rules

    except Exception as e:
        logger.error(f"[RulesClient] Failed to fetch rules: {e}")
        return []


def get_persona(
    market: str,
    ethnicity: str,
    age_group: Optional[str] = None,
) -> dict:
    """Fetch persona data from Supabase.

    Lookup order:
      1. Exact match on market + ethnicity + age_group (if provided)
      2. Fallback to age_group='base' for the same market + ethnicity
      3. Any row for market + ethnicity
      4. Empty dict (graceful degradation)

    Args:
        market: Country/market (e.g. 'malaysia', 'singapore').
        ethnicity: Ethnic group (e.g. 'malay', 'chinese', 'indian').
        age_group: Optional age group key (e.g. 'gen_z', 'millennial', 'all_ages').

    Returns:
        Persona data dict (from persona_data JSONB column), or empty dict.
    """
    try:
        # Fetch ALL rows for this market+ethnicity in one query — avoids multiple round-trips
        response = (
            supabase.table("personas")
            .select("persona_data, age_group")
            .eq("market", market.lower())
            .eq("ethnicity", ethnicity.lower())
            .execute()
        )
        rows = response.data or []

        if not rows:
            logger.warning(
                "[RulesClient] No persona found for market=%s, ethnicity=%s", market, ethnicity
            )
            return {}

        # Build a lookup map: age_group -> persona_data
        by_age: dict[str, dict] = {
            row["age_group"]: row.get("persona_data", {})
            for row in rows
            if row.get("age_group")
        }

        # 1. Exact match on the requested age_group.  The task UI currently
        # stores "teens", while persona records use the more precise "gen_z".
        requested_age_group = _AGE_GROUP_ALIASES.get(
            (age_group or "").lower(), (age_group or "").lower()
        )
        if requested_age_group and requested_age_group in by_age:
            logger.info(
                "[RulesClient] Persona found: market=%s, ethnicity=%s, age_group=%s (exact)",
                market, ethnicity, requested_age_group,
            )
            return by_age[requested_age_group]

        # 2. Fallback to 'base' persona
        if "base" in by_age:
            logger.info(
                "[RulesClient] Persona found: market=%s, ethnicity=%s, age_group=base (fallback from %s)",
                market, ethnicity, age_group,
            )
            return by_age["base"]

        # 3. Any available persona
        first_persona = rows[0].get("persona_data", {})
        logger.info(
            "[RulesClient] Persona found: market=%s, ethnicity=%s, age_group=%s (first available)",
            market, ethnicity, rows[0].get("age_group"),
        )
        return first_persona

    except Exception as e:
        logger.error("[RulesClient] Failed to fetch persona: %s", e)
        return {}


def get_all_rules_and_persona(
    market: str,
    platform: str,
    ethnicity: str,
    age_group: str,
) -> dict:
    """Fetch both rules and persona for a compliance check.

    This is the main entry point replacing the old Qdrant-based _get_all_rules().

    Args:
        market: Market/country (e.g. 'malaysia').
        platform: Platform (e.g. 'tiktok', 'meta', 'youtube').
        ethnicity: Ethnic group.
        age_group: Age group key.

    Returns:
        Dict with 'rules' (list of rule dicts) and 'persona' (persona dict).
    """
    rules = get_rules(market=market, platform=platform)
    persona = get_persona(market=market, ethnicity=ethnicity, age_group=age_group)

    return {
        "rules": rules,
        "persona": persona,
    }

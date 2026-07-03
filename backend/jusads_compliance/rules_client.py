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

    Args:
        market: Country/market (e.g. 'malaysia', 'singapore').
        ethnicity: Ethnic group (e.g. 'malay', 'chinese', 'indian').
        age_group: Optional age group key (e.g. 'gen_z', 'millennial').

    Returns:
        Persona data dict (from persona_data JSONB column), or empty dict.
    """
    try:
        query = (
            supabase.table("personas")
            .select("persona_data, age_group")
            .eq("market", market.lower())
            .eq("ethnicity", ethnicity.lower())
        )

        if age_group:
            query = query.eq("age_group", age_group.lower())

        response = query.execute()
        rows = response.data or []

        if not rows:
            logger.warning(f"[RulesClient] No persona found for market={market}, ethnicity={ethnicity}, age_group={age_group}")
            return {}

        # If age_group specified, return that specific persona
        if age_group and rows:
            return rows[0].get("persona_data", {})

        # If no age_group, return the base persona (age_group='base')
        for row in rows:
            if row.get("age_group") == "base":
                return row.get("persona_data", {})

        # Fallback: return first result
        return rows[0].get("persona_data", {}) if rows else {}

    except Exception as e:
        logger.error(f"[RulesClient] Failed to fetch persona: {e}")
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

"""
fetch_rules.py
──────────────
Agent: Query ad_policy_rules and personas tables.

Fetches regulatory rules and cultural personas for the target market/platform/ethnicity.
Proceeds with empty set + WARNING if no results are found.
"""

import logging
from shared.models import Compliance_State
from jusads_compliance.progress_tracker import ProgressTracker
from jusads_compliance.rules_client import get_rules, get_persona

logger = logging.getLogger(__name__)
_tracker = ProgressTracker()


def fetch_rules_and_personas(state: Compliance_State) -> dict:
    """Query ad_policy_rules and personas tables for the given market/platform/ethnicity.

    Proceeds with empty set + WARNING if no results are found.
    """
    task_id = state["task_id"]
    step_name = "fetch_rules_and_personas"
    _tracker.start_step(task_id, step_name)

    try:
        market = state["market"]
        platform = state["platform"]
        ethnicity = state["ethnicity"]
        age_group = state["age_group"]

        # Query rules
        rules = get_rules(market=market, platform=platform)
        if not rules:
            logger.warning(
                "[fetch_rules] No rules found for market=%s, platform=%s. "
                "Proceeding with empty rule set.",
                market, platform,
            )

        # Query personas
        persona = get_persona(market=market, ethnicity=ethnicity, age_group=age_group)
        if not persona:
            logger.warning(
                "[fetch_rules] No persona found for market=%s, ethnicity=%s, "
                "age_group=%s. Proceeding with empty persona.",
                market, ethnicity, age_group,
            )

        # Store in result for downstream nodes
        result = state.get("result", {}) or {}
        result["_rules"] = rules
        result["_persona"] = persona

        _tracker.complete_step(
            task_id, step_name,
            f"Fetched {len(rules)} rules, persona={'found' if persona else 'empty'}",
        )

        return {"result": result}

    except Exception as e:
        logger.error("[fetch_rules] Failed: %s", e)
        _tracker.fail_step(task_id, step_name, str(e))
        result = state.get("result", {}) or {}
        result["_rules"] = []
        result["_persona"] = {}
        return {"result": result}

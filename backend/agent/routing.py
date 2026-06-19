"""
routing.py
──────────
Pure routing functions for the compliance pipeline.
These are separated from pipeline.py to enable independent testing
without heavy LangGraph dependencies.
"""

from typing import Literal


def route_human_decision(decision: str) -> Literal["approved", "edit_requested"]:
    """Pure routing function: decide pipeline path based on human decision text.

    Returns "edit_requested" if the lowercased trimmed input is one of
    ("edit", "remix", "yes"). Returns "approved" for all other inputs
    including "ok", empty strings, and arbitrary text.

    Validates: Requirements 1.4, 1.5
    """
    if isinstance(decision, str) and decision.strip().lower() in ("edit", "remix", "yes"):
        return "edit_requested"
    return "approved"

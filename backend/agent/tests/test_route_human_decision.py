"""
test_route_human_decision.py
─────────────────────────────
Unit tests for the route_human_decision function.

Validates: Requirements 1.4, 1.5
"""

import pytest
from agent.routing import route_human_decision


class TestRouteHumanDecisionEditRequested:
    """Test cases where route_human_decision returns 'edit_requested'."""

    @pytest.mark.parametrize("decision", [
        "edit",
        "remix",
        "yes",
        "EDIT",
        "Remix",
        "YES",
        "  edit  ",
        "  REMIX  ",
        "\tyes\n",
        "  Edit",
        "REMIX  ",
    ])
    def test_edit_requested_variants(self, decision):
        assert route_human_decision(decision) == "edit_requested"


class TestRouteHumanDecisionApproved:
    """Test cases where route_human_decision returns 'approved'."""

    @pytest.mark.parametrize("decision", [
        "ok",
        "OK",
        "",
        "   ",
        "approve",
        "no",
        "done",
        "random text",
        "editing",
        "remixed",
        "yesss",
        "ed it",
        "re mix",
    ])
    def test_approved_variants(self, decision):
        assert route_human_decision(decision) == "approved"

    def test_non_string_input(self):
        """Non-string input should return 'approved'."""
        assert route_human_decision(None) == "approved"
        assert route_human_decision(123) == "approved"
        assert route_human_decision([]) == "approved"

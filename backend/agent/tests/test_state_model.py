"""
test_state_model.py
───────────────────
Tests for ComplianceState defaults and remix fields.
"""

from agent.data_model import ComplianceState


def test_remediated_path_defaults_empty():
    state = ComplianceState(
        session_id="t1", media_type="text", input_path="",
        text_input="hi", market="malaysia", platform="tiktok",
        ethnicity="malay", age_group="gen_z",
    )
    assert state.remediated_path == ""


def test_remix_iteration_defaults_zero():
    state = ComplianceState(
        session_id="t1", media_type="image", input_path="/img.png",
        text_input="", market="singapore", platform="meta",
        ethnicity="chinese", age_group="millennial",
    )
    assert state.remix_iteration == 0


def test_status_accepts_remediated():
    state = ComplianceState(
        session_id="t1", media_type="text", input_path="",
        text_input="x", market="malaysia", platform="tiktok",
        ethnicity="malay", age_group="gen_z", status="remediated",
    )
    assert state.status == "remediated"


def test_status_accepts_remix_failed():
    state = ComplianceState(
        session_id="t1", media_type="audio", input_path="/a.wav",
        text_input="", market="malaysia", platform="meta",
        ethnicity="indian", age_group="gen_x", status="remix_failed",
    )
    assert state.status == "remix_failed"


def test_factory_fixture(compliance_state_factory):
    state = compliance_state_factory(media_type="video", market="singapore")
    assert state.media_type == "video"
    assert state.market == "singapore"
    assert state.remediated_path == ""
    assert state.remix_iteration == 0

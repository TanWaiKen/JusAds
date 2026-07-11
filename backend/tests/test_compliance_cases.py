import os
import sys
import uuid
import pytest

# Ensure backend is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jusads_compliance.compliance_pipeline import compliance_pipeline
from shared.models import Compliance_State

# Paths to the generated non-compliant assets
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BR_AUDIO_PATH = os.path.abspath(os.path.join(ROOT_DIR, "..", "assets", "Test6-Audio", "non_compliant_br_finance.mp3"))
MY_VIDEO_PATH = os.path.abspath(os.path.join(ROOT_DIR, "..", "assets", "Test7-Video", "non_compliant_my_no_subtitles.mp4"))
MY_IMAGE_PATH = os.path.abspath(os.path.join(ROOT_DIR, "..", "assets", "Test5-Image", "Lightening Serum.jpg"))

def test_brazil_audio_non_compliant():
    """Verify that a Brazil finance voiceover without CNPJ and disclaimers fails compliance."""
    assert os.path.exists(BR_AUDIO_PATH), f"Audio asset not found: {BR_AUDIO_PATH}"
    
    task_id = str(uuid.uuid4())
    state: Compliance_State = {
        "session_id": task_id,
        "media_type": "audio",
        "input_path": BR_AUDIO_PATH,
        "text_input": "",
        "market": "br",
        "platform": "tiktok",
        "ethnicity": "all",
        "age_group": "all_ages",
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "Financial services advertisement targeting investors in Brazil.",
        "task_id": task_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }
    
    # Run the compiled compliance pipeline
    res = compliance_pipeline.invoke(state)
    result_dict = res.get("result", {})
    decision = res.get("status", "")
    
    print("\n[Brazil Audio Test]")
    print(f"  Decision: {decision}")
    print(f"  Reasoning: {result_dict.get('explanation')}")
    print(f"  Violations: {result_dict.get('high_risk_indicator')}")
    print(f"  Full result state: {res}")
    
    # It should fail or require remediation/regen
    assert decision in ("critical_regen", "remediate")
    violations_str = str(result_dict.get("high_risk_indicator", [])).lower()
    assert any(x in violations_str for x in ("cnpj", "disclaimer", "risco", "riscos", "financial", "guarantee"))

def test_malaysia_video_no_subtitles():
    """Verify that a Malaysian TikTok video with spoken audio but no subtitles fails compliance."""
    assert os.path.exists(MY_VIDEO_PATH), f"Video asset not found: {MY_VIDEO_PATH}"
    
    task_id = str(uuid.uuid4())
    state: Compliance_State = {
        "session_id": task_id,
        "media_type": "video",
        "input_path": MY_VIDEO_PATH,
        "text_input": "",
        "market": "my",
        "platform": "tiktok",
        "ethnicity": "all",
        "age_group": "all_ages",
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "Ad promoting a fast gold investment scheme in Malaysia.",
        "task_id": task_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }
    
    res = compliance_pipeline.invoke(state)
    result_dict = res.get("result", {})
    decision = res.get("status", "")
    
    print("\n[Malaysia Video Test]")
    print(f"  Decision: {decision}")
    print(f"  Reasoning: {result_dict.get('explanation')}")
    print(f"  Violations: {result_dict.get('high_risk_indicator')}")
    
    # It should fail and flag missing subtitles
    assert decision in ("critical_regen", "remediate")

def test_malaysia_image_halal_violation():
    """Verify that an image promoting a Halal product without Jakim details flags compliance."""
    assert os.path.exists(MY_IMAGE_PATH), f"Image asset not found: {MY_IMAGE_PATH}"
    
    task_id = str(uuid.uuid4())
    state: Compliance_State = {
        "session_id": task_id,
        "media_type": "image",
        "input_path": MY_IMAGE_PATH,
        "text_input": "",
        "market": "my",
        "platform": "tiktok",
        "ethnicity": "all",
        "age_group": "all_ages",
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "A chicken burger ad claiming to be 'Muslim-friendly' but lacking JAKIM logo/certification.",
        "task_id": task_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }
    
    res = compliance_pipeline.invoke(state)
    result_dict = res.get("result", {})
    decision = res.get("status", "")
    
    print("\n[Malaysia Image Test]")
    print(f"  Decision: {decision}")
    print(f"  Reasoning: {result_dict.get('explanation')}")
    
    # Should remediate/flag Halal warning
    assert decision in ("critical_regen", "remediate")

def test_brazil_text_gambling_violation():
    """Verify that a text gambling ad promising guaranteed earnings fails compliance."""
    task_id = str(uuid.uuid4())
    state: Compliance_State = {
        "session_id": task_id,
        "media_type": "text",
        "input_path": "",
        "text_input": "Jogue no Tigrinho da Sorte agora! Ganhe dinheiro fácil garantido direto no seu PIX. Diversão para toda a família!",
        "market": "br",
        "platform": "tiktok",
        "ethnicity": "all",
        "age_group": "all_ages",
        "iteration": 0,
        "result": {},
        "status": "pending",
        "user_prompt_context": "",
        "task_id": task_id,
        "remediated_path": "",
        "remix_iteration": 0,
    }
    
    res = compliance_pipeline.invoke(state)
    result_dict = res.get("result", {})
    decision = res.get("status", "")
    
    print("\n[Brazil Gambling Text Test]")
    print(f"  Decision: {decision}")
    print(f"  Reasoning: {result_dict.get('explanation')}")
    print(f"  Violations: {result_dict.get('high_risk_indicator')}")
    
    # It should fail
    assert decision in ("critical_regen", "remediate")

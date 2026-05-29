"""LangGraph ReAct-compatible tool for text compliance checking.

Usage with LangGraph ReAct agent:

    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.prebuilt import create_react_agent
    from jusads_text_compliance.tools import check_text_compliance

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")
    agent = create_react_agent(llm, tools=[check_text_compliance])
    result = agent.invoke({"messages": [("user", "Check if this ad is OK: ...")]})
"""

import json
import logging

from langchain_core.tools import tool

from .text_checker import TextComplianceChecker

logger = logging.getLogger(__name__)


@tool
def check_text_compliance(
    text: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Evaluate advertisement text for regulatory and cultural compliance.
    
    Args:
        text (str): The advertisement text to evaluate.
        market (str): Target market ('malaysia' or 'singapore').
        ethnicity (str): Target ethnicity ('malay', 'chinese', 'indian', 'all').
        age_group (str): Target age group ('all_ages', 'adults_only', 'children').
            
    Returns:
        JSON string containing risk_level, score, violations, and explanation.
    """
    try:
        checker = TextComplianceChecker()
        result = checker.check_compliance(
            ad_text=text,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        # Strictly enforce the output format for the ReAct agent
        # The LLM now returns 'high_risk_indicators' instead of 'violations'
        agent_payload = {
            "risk_level": result.get("risk_level", "Unknown"),
            "score": result.get("score", 0),
            "high_risk_indicators": result.get("high_risk_indicators", []),
            "explanation": result.get("explanation", ""),
            "suggestion": result.get("suggestion", "")
        }
        
        return json.dumps(agent_payload, indent=2, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def transcribe_media(media_path: str) -> str:
    """Extract and transcribe spoken text from an audio or video file.
    
    Args:
        media_path (str): The absolute or relative path to the audio or video file.
            
    Returns:
        JSON string containing the extracted transcript text or an error message.
    """
    try:
        if not media_path:
            return json.dumps({"error": "No media_path provided."})
            
        from jusads_transcription.transcriber import Transcriber
        transcriber = Transcriber()
        transcript = transcriber.transcribe_media(media_path)
        
        return json.dumps({"transcript": transcript}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def check_audio_compliance(
    media_path: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Evaluate spoken audio/video content for regulatory and cultural compliance.
    
    Args:
        media_path (str): The absolute or relative path to the audio or video file.
        market (str): Target market ('malaysia' or 'singapore').
        ethnicity (str): Target ethnicity ('malay', 'chinese', 'indian', 'all').
        age_group (str): Target age group ('all_ages', 'adults_only', 'children').
            
    Returns:
        JSON string containing risk_level, score, high_risk_indicators, explanation, and the transcript used.
    """
    try:
        if not media_path:
            return json.dumps({"error": "No media_path provided."})
            
        logger.info(f"Checking audio compliance for {media_path}...")
        
        # 1. Transcribe the media
        from jusads_transcription.transcriber import Transcriber
        transcriber = Transcriber()
        transcript = transcriber.transcribe_media(media_path)
        logger.info(f"Transcription successful. Passing to text compliance checker...")
        
        # 2. Run text compliance on the transcript
        checker = TextComplianceChecker()
        result = checker.check_compliance(
            ad_text=transcript,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        # 3. Format response
        agent_payload = {
            "transcript_used": transcript,
            "risk_level": result.get("risk_level", "Unknown"),
            "score": result.get("score", 0),
            "high_risk_indicators": result.get("high_risk_indicators", []),
            "explanation": result.get("explanation", ""),
            "suggestion": result.get("suggestion", "")
        }
        
        return json.dumps(agent_payload, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Audio compliance check failed: {str(e)}")
        return json.dumps({"error": str(e)})


@tool
def check_video_compliance(
    media_path: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Evaluate a video advertisement for regulatory and cultural compliance.
    
    Args:
        media_path (str): The absolute or relative path to the video file (e.g., .mp4, .mov).
        market (str): Target market ('malaysia' or 'singapore').
        ethnicity (str): Target ethnicity ('malay', 'chinese', 'indian', 'all').
        age_group (str): Target age group ('all_ages', 'adults_only', 'children').
            
    Returns:
        JSON string containing risk_level, score, high_risk_indicators, explanation, suggestion, and the transcript used.
    """
    try:
        if not media_path:
            return json.dumps({"error": "No media_path provided."})
            
        logger.info(f"Checking video compliance for {media_path}...")
        
        from jusads_video_compliance.video_checker import VideoComplianceChecker
        checker = VideoComplianceChecker()
        
        result = checker.check_compliance(
            video_path=media_path,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        agent_payload = {
            "transcript_used": result.get("transcript_used", ""),
            "risk_level": result.get("risk_level", "Unknown"),
            "score": result.get("score", 0),
            "high_risk_indicators": result.get("high_risk_indicators", []),
            "explanation": result.get("explanation", ""),
            "suggestion": result.get("suggestion", "")
        }
        
        return json.dumps(agent_payload, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Video compliance check failed: {str(e)}")
        return json.dumps({"error": str(e)})


@tool
def remediate_text(
    original_text: str,
    compliance_result_json: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Rewrite ad text to fix compliance violations.

    Args:
        original_text (str): The original ad text that failed compliance.
        compliance_result_json (str): JSON string of the compliance check result.
        market (str): Target market.
        ethnicity (str): Target ethnicity.
        age_group (str): Target age group.

    Returns:
        JSON string containing rewritten_text and changes_made.
    """
    try:
        compliance_result = json.loads(compliance_result_json) if isinstance(compliance_result_json, str) else compliance_result_json

        from jusads_text_compliance.text_remediator import TextRemediator
        remediator = TextRemediator()
        result = remediator.remediate(
            original_text=original_text,
            compliance_result=compliance_result,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Text remediation failed: {str(e)}")
        return json.dumps({"error": str(e)})


@tool
def remediate_image(
    image_path: str,
    compliance_result_json: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Generate a compliant image prompt based on a flagged image and its compliance issues.

    Args:
        image_path (str): Path to the original non-compliant image.
        compliance_result_json (str): JSON string of the compliance check result.
        market (str): Target market.
        ethnicity (str): Target ethnicity.
        age_group (str): Target age group.

    Returns:
        JSON string containing compliant_image_prompt and changes_suggested.
    """
    try:
        compliance_result = json.loads(compliance_result_json) if isinstance(compliance_result_json, str) else compliance_result_json

        from jusads_image_compliance.image_remediator import ImageRemediator
        remediator = ImageRemediator()
        result = remediator.remediate(
            image_path=image_path,
            compliance_result=compliance_result,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Image remediation failed: {str(e)}")
        return json.dumps({"error": str(e)})


@tool
def remediate_video(
    video_path: str,
    compliance_result_json: str,
    market: str = "malaysia",
    ethnicity: str = "all",
    age_group: str = "all_ages"
) -> str:
    """Generate a compliant script rewrite and visual edit guide for a flagged video.

    Args:
        video_path (str): Path to the original non-compliant video.
        compliance_result_json (str): JSON string of the compliance check result.
        market (str): Target market.
        ethnicity (str): Target ethnicity.
        age_group (str): Target age group.

    Returns:
        JSON string containing rewritten_script, visual_edit_guide, and changes_made.
    """
    try:
        compliance_result = json.loads(compliance_result_json) if isinstance(compliance_result_json, str) else compliance_result_json

        from jusads_video_compliance.video_remediator import VideoRemediator
        remediator = VideoRemediator()
        result = remediator.remediate(
            video_path=video_path,
            compliance_result=compliance_result,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        return json.dumps(result, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Video remediation failed: {str(e)}")
        return json.dumps({"error": str(e)})


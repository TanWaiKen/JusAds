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

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
def check_text_compliance(arguments_json: str) -> str:
    """Evaluate advertisement text for regulatory and cultural compliance.
    
    Args:
        arguments_json: A JSON string containing:
            - text (str): The advertisement text to evaluate.
            - market (str): Target market ('malaysia' or 'singapore').
            - ethnicity (str): Target ethnicity ('malay', 'chinese', 'indian', 'all').
            - age_group (str): Target age group ('all_ages', 'adults_only', 'children').
            
    Returns:
        JSON string containing risk_level, score, violations, and explanation.
    """
    try:
        args = json.loads(arguments_json)
        text = args.get("text", "")
        market = args.get("market", "malaysia")
        ethnicity = args.get("ethnicity", "all")
        age_group = args.get("age_group", "all_ages")
        
        checker = TextComplianceChecker()
        result = checker.check_compliance(
            ad_text=text,
            market=market,
            ethnicity=ethnicity,
            age_group=age_group
        )
        
        return json.dumps(result, indent=2, ensure_ascii=False)
        
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON arguments provided."})
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool
def transcribe_media(arguments_json: str) -> str:
    """Extract and transcribe spoken text from an audio or video file.
    
    Args:
        arguments_json: A JSON string containing:
            - media_path (str): The absolute or relative path to the audio/video file.
            - use_ffmpeg (bool, optional): Whether to use ffmpeg to extract audio first (default: true).
            
    Returns:
        JSON string containing the extracted transcript text or an error message.
    """
    try:
        args = json.loads(arguments_json)
        media_path = args.get("media_path", "")
        use_ffmpeg = args.get("use_ffmpeg", True)
        
        if not media_path:
            return json.dumps({"error": "No media_path provided."})
            
        from jusads_transcription.transcriber import VideoTranscriber
        transcriber = VideoTranscriber(use_ffmpeg=use_ffmpeg)
        transcript = transcriber.transcribe_media(media_path)
        
        return json.dumps({"transcript": transcript}, ensure_ascii=False)
        
    except json.JSONDecodeError:
        return json.dumps({"error": "Invalid JSON arguments provided."})
    except Exception as e:
        return json.dumps({"error": str(e)})

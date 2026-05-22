import boto3
import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

# Load credentials from .env
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION")
DEFAULT_MODEL = os.getenv("BEDROCK_MODEL_ID", "apac.amazon.nova-pro-v1:0")

def get_bedrock_client():
    """Create and return a Bedrock runtime client."""
    # Attempt to use hardcoded creds if available, otherwise default boto3 resolution
    try:
        return boto3.client(
            service_name='bedrock-runtime',
            region_name=REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
    except Exception:
        return boto3.client("bedrock-runtime", region_name=REGION)

def invoke_bedrock_model(prompt: str, model_id: str = None, temperature: float = 0.7, max_tokens: int = 1024) -> str:
    """
    Invoke an Amazon Bedrock model using the Converse API.
    """
    if model_id is None:
        model_id = DEFAULT_MODEL
    client = get_bedrock_client()

    response = client.converse(
        modelId=model_id,
        messages=[
            {
                "role": "user",
                "content": [{"text": prompt}]
            }
        ],
        inferenceConfig={
            "maxTokens": max_tokens,
            "temperature": temperature
        }
    )

    return response["output"]["message"]["content"][0]["text"]

def parse_json_response(text: str) -> list | dict:
    """
    Clean markdown fences and parse JSON from a Bedrock response.
    Handles common LLM issues like trailing commas and text around JSON.

    Raises:
        RuntimeError on parse failure.
    """
    content = text.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()

    # First try direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array or object from the text
    json_match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', content)
    if json_match:
        extracted = json_match.group(1)
        # Remove trailing commas before ] or }
        extracted = re.sub(r',\s*([}\]])', r'\1', extracted)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

    # Last resort: remove trailing commas from original content
    cleaned = re.sub(r',\s*([}\]])', r'\1', content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Bedrock response as JSON: {e}\n{content}")

if __name__ == "__main__":
    MODEL_ID = "global.amazon.nova-2-lite-v1:0"
    print(f"--- Testing Bedrock (Converse API) ---")
    print(f"Model: {MODEL_ID}")
    print(f"Region: {REGION}")
    
    try:
        text = invoke_bedrock_model("Hello Bedrock, are you working?", model_id=MODEL_ID)
        print(f"\nResponse:\n{text}")
    except Exception as e:
        print(f"\nError: {e}")

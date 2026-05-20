import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Load credentials from .env
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
REGION = os.getenv("AWS_REGION")

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

def invoke_bedrock_model(prompt: str, model_id: str = "apac.amazon.nova-lite-v1:0", temperature: float = 0.7, max_tokens: int = 1024) -> str:
    """
    Invoke an Amazon Bedrock model using the Converse API.
    """
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

    try:
        return json.loads(content)
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

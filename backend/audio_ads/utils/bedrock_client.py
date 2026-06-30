import boto3
import json

# Hardcoded for basic testing as requested
AWS_ACCESS_KEY_ID = "AKIAW34DNGKKGBR3IDEY"
AWS_SECRET_ACCESS_KEY = "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"
REGION = "ap-southeast-5" 
MODEL_ID = "global.amazon.nova-2-lite-v1:0"

client = boto3.client(
    service_name='bedrock-runtime',
    region_name=REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

print(f"--- Testing Bedrock (Converse API) ---")
print(f"Model: {MODEL_ID}")
print(f"Region: {REGION}")

try:
    # Using the Converse API as it is the standard for Nova Lite
    response = client.invoke_model(
        modelId=MODEL_ID,
        body=json.dumps({
            'messages': [
                {
                    'role': 'user',
                    'content': [{'text': 'Hello Bedrock, are you working?'}]
                }
            ]
        })
    )
    
    text = response['output']['message']['content'][0]['text']
    print(f"\nResponse:\n{text}")
    
except Exception as e:
    print(f"\nError: {e}")

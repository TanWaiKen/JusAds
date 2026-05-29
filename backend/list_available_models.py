import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

VERTEX_PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "global")

client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)

print(f"Listing models for region: {VERTEX_LOCATION}")
try:
    for m in client.models.list():
        print(m.name)
except Exception as e:
    print(f"Error listing models: {e}")

# Also try us-central1 explicitly
try:
    print(f"\nListing models for region: us-central1")
    client_us = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location="us-central1")
    for m in client_us.models.list():
        print(m.name)
except Exception as e:
    print(f"Error listing models in us-central1: {e}")

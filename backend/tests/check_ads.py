"""Quick check: are generated_ads persisted for the latest task?"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from shared.clients import supabase

TASK_ID = "6c7a6b12-d983-4c48-8548-0f05100b7b88"

resp = supabase.table("generated_ads").select("id, media_type, status, metadata, s3_media_key").eq("task_id", TASK_ID).execute()
print(f"Found {len(resp.data)} ads for task {TASK_ID}:")
for r in resp.data:
    label = (r.get("metadata") or {}).get("label", "")
    s3 = (r.get("metadata") or {}).get("s3_url", "")[:60]
    print(f"  {r['id'][:8]} | {r['media_type']} | {r['status']} | {label} | {s3}...")

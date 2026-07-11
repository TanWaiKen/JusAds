"""
fix_supabase_state.py
─────────────────────
Manually persist the V3 grid pipeline results from the previous run into Supabase.
The character sheet + scene grid were uploaded to S3 but not persisted as generated_ads.

Run: python -m tests.fix_supabase_state
"""
import sys
import os
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env explicitly
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from shared.clients import supabase

PROJECT_ID = "b93f6c05-cc33-4b9b-a376-a441286e3650"
TASK_ID = "e52e6c17-b758-4fdc-99e5-e4d6f025f13f"
PLAN_ID = "a09a15cd"

# S3 URLs from the logs
S3_BASE = "https://jusads-439033634294-ap-southeast-1-an.s3.ap-southeast-1.amazonaws.com"
CHAR_SHEET_URL = f"{S3_BASE}/generated_ads/{PROJECT_ID}/{TASK_ID}/v3/{PLAN_ID}/character_sheet.png"
GRID_URL = f"{S3_BASE}/generated_ads/{PROJECT_ID}/{TASK_ID}/v3/{PLAN_ID}/scene_grid.png"
FRAME_URLS = [
    f"{S3_BASE}/generated_ads/{PROJECT_ID}/{TASK_ID}/v3/{PLAN_ID}/frame_{i:02d}.png"
    for i in range(6)
]

now = datetime.now(timezone.utc).isoformat()


def insert_ad(media_type, s3_url, prompt, label):
    ad_id = str(uuid.uuid4())
    supabase.table("generated_ads").insert({
        "id": ad_id,
        "project_id": PROJECT_ID,
        "task_id": TASK_ID,
        "media_type": media_type,
        "platform": "tiktok",
        "status": "completed",
        "s3_media_key": s3_url,
        "metadata": {"s3_url": s3_url, "label": label, "pipeline": "v3_grid"},
        "prompt_used": prompt[:500],
        "created_at": now,
    }).execute()
    print(f"  Inserted: {label} ({ad_id[:8]})")
    return ad_id


def update_pipeline_state():
    """Update the task's pipeline_state with nodes for the generated assets."""
    nodes = [
        {"id": f"node-director-{PLAN_ID}", "type": "orchestrator", "x": 100, "y": 200,
         "label": "Director", "status": "done", "output": "5 scenes planned", "error": None, "props": {}},
        {"id": f"node-char-{PLAN_ID}", "type": "image", "x": 350, "y": 100,
         "label": "Character Sheet", "status": "done", "output": CHAR_SHEET_URL, "error": None, "props": {}},
        {"id": f"node-grid-{PLAN_ID}", "type": "image", "x": 600, "y": 200,
         "label": "Scene Grid (3x2)", "status": "done", "output": GRID_URL, "error": None, "props": {}},
        {"id": f"node-slicer-{PLAN_ID}", "type": "process", "x": 850, "y": 200,
         "label": "Grid Slicer", "status": "done", "output": "6 frames", "error": None,
         "props": {"frame_count": 6, "frame_urls": FRAME_URLS}},
    ]
    # Add clip nodes (failed)
    for i in range(5):
        nodes.append({
            "id": f"node-clip-{i}-{PLAN_ID}", "type": "video", "x": 1100, "y": 80 + i * 100,
            "label": f"Clip {i+1}/5", "status": "failed",
            "output": None, "error": "GenerateVideosConfig fix applied — retry will work",
            "props": {},
        })

    edges = [
        {"id": "e1", "from": f"node-director-{PLAN_ID}", "to": f"node-char-{PLAN_ID}"},
        {"id": "e2", "from": f"node-director-{PLAN_ID}", "to": f"node-grid-{PLAN_ID}"},
        {"id": "e3", "from": f"node-char-{PLAN_ID}", "to": f"node-grid-{PLAN_ID}"},
        {"id": "e4", "from": f"node-grid-{PLAN_ID}", "to": f"node-slicer-{PLAN_ID}"},
    ]
    for i in range(5):
        edges.append({"id": f"e-clip-{i}", "from": f"node-slicer-{PLAN_ID}", "to": f"node-clip-{i}-{PLAN_ID}"})

    pipeline_state = {"nodes": nodes, "edges": edges, "viewport": {"panX": 0, "panY": 0, "zoom": 1}}

    supabase.table("tasks").update({
        "pipeline_state": pipeline_state,
        "status": "in_progress",
    }).eq("id", TASK_ID).eq("project_id", PROJECT_ID).execute()
    print("  Updated pipeline_state on task")


def main():
    print("Fixing Supabase state for V3 grid pipeline run...")
    print(f"  Project: {PROJECT_ID}")
    print(f"  Task: {TASK_ID}")
    print(f"  Plan: {PLAN_ID}")
    print()

    # Check existing ads
    resp = supabase.table("generated_ads").select("id").eq("task_id", TASK_ID).execute()
    print(f"  Existing ads for this task: {len(resp.data)}")

    # Insert character sheet
    print("\nInserting generated_ads...")
    insert_ad("image", CHAR_SHEET_URL, "Character Sheet: Tiger Sugar Boba character", "Character Sheet")
    insert_ad("image", GRID_URL, "Scene Grid (3x2): Tiger Sugar Boba storyboard", "Scene Grid")

    # Update pipeline state with nodes
    print("\nUpdating pipeline_state...")
    update_pipeline_state()

    print("\nDone! Refresh the page to see results.")


if __name__ == "__main__":
    main()

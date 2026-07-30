import os
import sys
from datetime import datetime, timezone
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "backend"))
from shared.clients import supabase

def seed_shared_project():
    target_user = "developer@jusads.com"
    owner_user = "teammate@jusads.com"
    
    logger.info("Seeding a shared project for %s owned by %s", target_user, owner_user)
    
    # Check if the fake project already exists
    resp = supabase.table("projects").select("id").eq("owner_email", owner_user).execute()
    if resp.data:
        project_id = resp.data[0]["id"]
        logger.info("Project already exists with id: %s", project_id)
    else:
        # Create fake project
        project_id = str(uuid.uuid4())
        supabase.table("projects").insert({
            "id": project_id,
            "owner_email": owner_user,
            "name": "Acme Marketing Q4",
            "created_at": datetime.now(timezone.utc).isoformat()
        }).execute()
        logger.info("Created new project with id: %s", project_id)
        
    # Share it with target user
    member_resp = supabase.table("project_members").select("*").eq("project_id", project_id).eq("email", target_user).execute()
    if not member_resp.data:
        supabase.table("project_members").insert({
            "project_id": project_id,
            "email": target_user
        }).execute()
        logger.info("Added %s to project_members", target_user)
    else:
        logger.info("%s is already a member", target_user)

if __name__ == "__main__":
    seed_shared_project()

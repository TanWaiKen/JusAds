import sys
sys.path.insert(0, ".")
import os
import asyncio
from dotenv import load_dotenv
load_dotenv("backend/.env")

from shared.clients import gemini
from jusads_generation.agents.video_v3_grid import plan_script

async def main():
    try:
        res = await plan_script(
            brief="Adult diaper packaging and convenience",
            video_duration_sec=15.0,
            target_ethnicity="all",
            product_description="Adult Diaper",
            market="malaysia"
        )
        print("Success! Result keys:", res.keys())
        print("skip_character_creation:", res.get("skip_character_creation"))
    except Exception as e:
        print("Failed with error:", e)

asyncio.run(main())

"""
fetch_real_trends.py
────────────────────
Fetch REAL trending content using Gemini GoogleSearch tool,
save to CSV backup, then insert into trends_cache database.

Uses Gemini's built-in GoogleSearch to find current trending
ads/content on TikTok, Instagram, YouTube for Malaysia market.

Usage:
  cd backend
  .venv/Scripts/python scripts/manual/fetch_real_trends.py

Requires: VERTEX_PROJECT_ID in .env (for Gemini)
"""

import csv
import json
import os
import sys
import uuid
from datetime import datetime, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(os.path.dirname(script_dir))
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
load_dotenv(".env", override=True)

from shared.clients import gemini, supabase
from google.genai.types import GenerateContentConfig, GoogleSearch, Tool


def search_trending_for_platform(platform: str, market: str = "Malaysia", business_context: str = "") -> list[dict]:
    """Use Gemini GoogleSearch to find trending content, then parse with a second call.
    
    Args:
        platform: Social platform to search.
        market: Target market.
        business_context: User's business profile context to tailor results.
    """
    
    business_hint = ""
    if business_context:
        business_hint = f"\nFocus on content relevant to: {business_context}"

    # Step 1: Use GoogleSearch to find real trending content (no JSON mode)
    search_prompt = f"""Search for the latest trending {platform} content and advertisements in {market}.{business_hint}
Find exactly 10 REAL currently trending posts/videos/ads with their actual URLs, view counts, and descriptions.
List each item with its title, URL, approximate view/like count, and relevant hashtags.
Make sure to return exactly 10 items."""

    try:
        # GoogleSearch call (cannot use response_mime_type with search)
        search_response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=search_prompt,
            config=GenerateContentConfig(
                tools=[Tool(google_search=GoogleSearch())],
            ),
        )
        
        search_text = search_response.text.strip()
        if not search_text:
            print(f"    WARNING: GoogleSearch returned empty for {platform}")
            return []

        # Step 2: Parse the search results into structured JSON (separate call, no search tool)
        from google.genai import types as genai_types

        parse_prompt = f"""Parse the following search results about trending {platform} content in {market} into a JSON array.
Return exactly 10 items (fill gaps with related trending content if needed).

SEARCH RESULTS:
{search_text[:4000]}

Return a JSON array where each item has:
- "title": post title/description (max 200 chars)
- "url": the actual URL (use real URLs from the search results, or construct platform URLs)
- "content_type": "video" or "image" or "ad"
- "hashtags": relevant hashtags as array of strings (without #)
- "categories": array from ["food_beverage", "fashion", "tech", "beauty", "travel", "entertainment", "sports", "education", "ecommerce"]
- "engagement": {{"views": number, "likes": number, "shares": number, "comments": number}}
- "why_trending": one sentence why this is trending

Return ONLY the JSON array."""

        parse_response = gemini.models.generate_content(
            model="gemini-2.5-flash",
            contents=parse_prompt,
            config=genai_types.GenerateContentConfig(response_mime_type="application/json"),
        )
        
        raw = parse_response.text.strip()
        # Clean up common Gemini JSON issues
        raw = raw.replace("```json", "").replace("```", "").strip()
        
        try:
            items = json.loads(raw)
        except json.JSONDecodeError:
            # Try to fix common issues: trailing commas, etc.
            import re
            cleaned = re.sub(r',\s*([}\]])', r'\1', raw)  # Remove trailing commas
            try:
                items = json.loads(cleaned)
            except json.JSONDecodeError as e2:
                print(f"    WARNING: JSON parse failed even after cleanup: {e2}")
                print(f"    Raw (first 200): {raw[:200]}")
                return []
        
        if not isinstance(items, list):
            print(f"    WARNING: {platform} parse returned non-list")
            return []
        
        # Normalize each item
        normalized = []
        for item in items:
            if not item.get("title"):
                continue
            normalized.append({
                "platform": platform,
                "content_type": item.get("content_type", "video"),
                "title": (item.get("title") or "")[:500],
                "url": item.get("url", f"https://{platform}.com/trending"),
                "engagement_metrics": item.get("engagement", {"views": 0, "likes": 0, "shares": 0, "comments": 0}),
                "hashtags": item.get("hashtags", [])[:10],
                "categories": item.get("categories", []),
                "why_trending": item.get("why_trending", ""),
                "market": market.lower(),
            })
        
        return normalized

    except Exception as e:
        print(f"    ERROR searching {platform}: {e}")
        return []


def save_to_csv(all_items: list[dict], csv_path: str):
    """Save trending items to CSV backup."""
    if not all_items:
        print("  No items to save to CSV")
        return

    fieldnames = [
        "platform", "content_type", "title", "url",
        "views", "likes", "shares", "comments",
        "hashtags", "categories", "why_trending", "market", "scraped_at"
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for item in all_items:
            metrics = item.get("engagement_metrics", {})
            writer.writerow({
                "platform": item["platform"],
                "content_type": item["content_type"],
                "title": item["title"],
                "url": item["url"],
                "views": metrics.get("views", 0),
                "likes": metrics.get("likes", 0),
                "shares": metrics.get("shares", 0),
                "comments": metrics.get("comments", 0),
                "hashtags": "|".join(item.get("hashtags", [])),
                "categories": "|".join(item.get("categories", [])),
                "why_trending": item.get("why_trending", ""),
                "market": item["market"],
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })

    print(f"  ✓ CSV saved: {csv_path} ({len(all_items)} rows)")


def insert_to_database(all_items: list[dict], batch_id: str, owner_email: str = ""):
    """Insert trending items into trends_cache table."""
    if not supabase:
        print("  ERROR: Supabase not connected")
        return

    # Clear existing data for this user
    print("  Clearing old trends_cache data...")
    if owner_email:
        supabase.table("trends_cache").delete().eq("owner_email", owner_email).execute()
    else:
        supabase.table("trends_cache").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

    # Insert new data in chunks
    records = []
    for item in all_items:
        records.append({
            "platform": item["platform"],
            "content_type": item["content_type"],
            "title": item["title"],
            "url": item["url"],
            "engagement_metrics": item.get("engagement_metrics", {}),
            "hashtags": item.get("hashtags", []),
            "categories": item.get("categories", []),
            "cultural_event_tag": None,
            "market": item["market"],
            "owner_email": owner_email or None,
            "scrape_batch_id": batch_id,
        })

    # Insert in chunks of 25
    for i in range(0, len(records), 25):
        chunk = records[i:i+25]
        supabase.table("trends_cache").insert(chunk).execute()

    print(f"  ✓ Inserted {len(records)} items to trends_cache (batch: {batch_id[:8]})")


def main():
    print("=" * 60)
    print("REAL TRENDS FETCH — Gemini GoogleSearch")
    print("=" * 60)

    if not gemini:
        print("\n❌ ERROR: Gemini client not available")
        sys.exit(1)

    # Get user's business profile for personalized trends
    user_email = "tanwaiken552@gmail.com"
    business_context = ""

    if supabase:
        try:
            resp = supabase.table("business_profiles").select("*").eq("owner_email", user_email).limit(1).execute()
            if resp.data:
                profile = resp.data[0]
                business_context = (
                    f"Company: {profile.get('company_name', '')}, "
                    f"Category: {profile.get('product_category', '')}, "
                    f"Description: {profile.get('product_description', '')}, "
                    f"Target Platforms: {', '.join(profile.get('target_platforms', []))}, "
                    f"Target Markets: {', '.join(profile.get('target_markets', []))}"
                )
                print(f"\n👤 User: {user_email}")
                print(f"   Business: {profile.get('company_name', 'N/A')} ({profile.get('product_category', 'N/A')})")
                print(f"   Context: {business_context[:100]}...")
            else:
                print(f"\n👤 User: {user_email} (no business profile found — using generic search)")
        except Exception as e:
            print(f"\n⚠️  Could not fetch business profile: {e}")

    batch_id = str(uuid.uuid4())
    all_items = []

    platforms = ["tiktok", "instagram", "youtube"]

    for platform in platforms:
        print(f"\n🔍 Searching {platform} trends (Malaysia, 10 items)...")
        try:
            items = search_trending_for_platform(platform, "Malaysia", business_context=business_context)
        except Exception as e:
            print(f"    TIMEOUT/ERROR: {e}")
            items = []
        print(f"    Found: {len(items)} items")
        
        for item in items[:3]:  # Preview first 3
            print(f"    • {item['title'][:60]}")
        
        all_items.extend(items)

    print(f"\n📊 Total items found: {len(all_items)}")

    # Save to CSV backup
    csv_dir = os.path.join(backend_dir, "data")
    os.makedirs(csv_dir, exist_ok=True)
    csv_path = os.path.join(csv_dir, f"trends_cache_{datetime.now().strftime('%Y%m%d')}.csv")
    save_to_csv(all_items, csv_path)

    # Insert to database
    print("\n💾 Inserting to database...")
    insert_to_database(all_items, batch_id, owner_email=user_email)

    print(f"\n✅ DONE! {len(all_items)} real trends fetched and stored.")
    print(f"   CSV backup: {csv_path}")
    print(f"   Database: trends_cache table updated")
    print(f"\n   Visit: http://localhost:5173/dashboard/trends")


if __name__ == "__main__":
    main()

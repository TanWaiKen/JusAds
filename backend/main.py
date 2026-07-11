import sys
sys.stdout.reconfigure(encoding='utf-8')

from zernio import Zernio
from shared.config import ZERNIO_API_KEY

client = Zernio(api_key=ZERNIO_API_KEY)

# 1. Fetch follower stats
print("=== FOLLOWER STATISTICS ===")
follower_stats = client.accounts.get_follower_stats()
if follower_stats and follower_stats.accounts:
    for account in follower_stats.accounts:
        platform_name = getattr(account.platform, "value", str(account.platform))
        print(f"Platform: {platform_name}")
        print(f"  Username: @{account.username}")
        print(f"  Current Followers: {account.currentFollowers}")
        print(f"  Follower Growth: {account.growth} ({account.growthPercentage}%)")
        print(f"  Last Updated: {account.lastUpdated}")
        print("-" * 30)

# 2. Fetch post analytics
print("\n=== POST PERFORMANCE ===")
analytics = client.analytics.get_analytics()
posts = analytics.get('posts', [])
for i, post in enumerate(posts, 1):
    platform = post.get('platform')
    content = post.get('content', '') or ''
    # Truncate content for display
    truncated_content = (content.replace('\n', ' ')[:60] + "...") if len(content) > 60 else content.replace('\n', ' ')
    
    post_analytics = post.get('analytics') or {}
    views = post_analytics.get('views', 0)
    impressions = post_analytics.get('impressions', 0)
    likes = post_analytics.get('likes', 0)
    comments = post_analytics.get('comments', 0)
    
    print(f"Post #{i} [{platform.upper() if platform else 'UNKNOWN'}]")
    print(f"  Content: {truncated_content}")
    print(f"  Total Views: {views} (Impressions: {impressions})")
    print(f"  Total Likes: {likes} (Comments: {comments})")
    print("-" * 30)
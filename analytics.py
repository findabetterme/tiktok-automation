"""Pull TikTok analytics and surface actionable insights."""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from tiktok_client import TikTokClient


def fetch_analytics(client: TikTokClient, max_videos: int = 20) -> dict[str, Any]:
    """
    Fetch recent videos and compute engagement summary.

    Returns a dict with:
      - videos: raw list of video dicts
      - top_videos: top 5 by views
      - avg_views / avg_likes / avg_comments / avg_shares
      - best_posting_hours: hours of day (UTC) ranked by avg views
      - engagement_rate: (likes + comments + shares) / views
    """
    videos = client.get_video_list(max_count=max_videos)
    if not videos:
        return {"videos": [], "summary": "No videos found."}

    for v in videos:
        v["engagement"] = (
            v.get("like_count", 0)
            + v.get("comment_count", 0)
            + v.get("share_count", 0)
        )

    avg_views = statistics.mean(v.get("view_count", 0) for v in videos)
    avg_likes = statistics.mean(v.get("like_count", 0) for v in videos)
    avg_comments = statistics.mean(v.get("comment_count", 0) for v in videos)
    avg_shares = statistics.mean(v.get("share_count", 0) for v in videos)

    total_views = sum(v.get("view_count", 0) for v in videos)
    total_engagement = sum(v["engagement"] for v in videos)
    engagement_rate = (total_engagement / total_views * 100) if total_views else 0

    # Group by posting hour to find best times
    hour_views: dict[int, list[int]] = defaultdict(list)
    for v in videos:
        ts = v.get("create_time")
        if ts:
            hour = datetime.fromtimestamp(ts, tz=timezone.utc).hour
            hour_views[hour].append(v.get("view_count", 0))

    best_hours = sorted(
        hour_views.items(),
        key=lambda kv: statistics.mean(kv[1]),
        reverse=True,
    )[:3]

    top_videos = sorted(videos, key=lambda v: v.get("view_count", 0), reverse=True)[:5]

    return {
        "videos": videos,
        "top_videos": top_videos,
        "avg_views": round(avg_views),
        "avg_likes": round(avg_likes),
        "avg_comments": round(avg_comments),
        "avg_shares": round(avg_shares),
        "engagement_rate_pct": round(engagement_rate, 2),
        "best_posting_hours_utc": [h for h, _ in best_hours],
    }


def format_analytics_summary(analytics: dict[str, Any]) -> str:
    """Render analytics as a compact text block for use in Gemini prompts."""
    top = analytics.get("top_videos", [])
    top_titles = "\n".join(
        f"  - \"{v.get('title', 'untitled')}\" — {v.get('view_count', 0):,} views"
        for v in top[:5]
    )

    hours = analytics.get("best_posting_hours_utc", [])
    hours_str = ", ".join(f"{h:02d}:00 UTC" for h in hours) if hours else "N/A"

    return f"""
TikTok Account Analytics Summary
==================================
Avg views per video : {analytics.get('avg_views', 0):,}
Avg likes per video : {analytics.get('avg_likes', 0):,}
Avg comments        : {analytics.get('avg_comments', 0):,}
Avg shares          : {analytics.get('avg_shares', 0):,}
Engagement rate     : {analytics.get('engagement_rate_pct', 0)}%
Best posting hours  : {hours_str}

Top performing videos:
{top_titles}
""".strip()

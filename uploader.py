"""Upload a video to TikTok and log the result."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from tiktok_client import TikTokClient

console = Console()
UPLOAD_LOG = Path("upload_log.jsonl")


def upload_video(
    client: TikTokClient,
    video_path: str,
    title: str,
    hashtags: list[str] | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Upload a video to TikTok.

    Args:
        client: authenticated TikTokClient
        video_path: path to the .mp4 file
        title: caption / post title (will have hashtags appended)
        hashtags: list of hashtag strings (without #)
        dry_run: if True, skip the actual API call

    Returns:
        result dict with status and publish_id
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # Build caption with hashtags
    if hashtags:
        tag_str = " ".join(f"#{t.lstrip('#')}" for t in hashtags)
        full_title = f"{title} {tag_str}"[:2200]  # TikTok caption limit
    else:
        full_title = title

    console.print(f"[cyan]Uploading:[/cyan] {video_path}")
    console.print(f"[cyan]Caption:[/cyan] {full_title[:80]}...")

    if dry_run:
        console.print("[yellow]DRY RUN — skipping actual upload[/yellow]")
        result = {
            "publish_id": "dry_run",
            "status": "DRY_RUN",
            "video_path": video_path,
            "title": full_title,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
    else:
        publish_id = client.publish_video(video_path, full_title)
        result = {
            "publish_id": publish_id,
            "status": "PUBLISH_COMPLETE",
            "video_path": video_path,
            "title": full_title,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }
        console.print(f"[green]✓ Published![/green] publish_id={publish_id}")

    # Append to JSONL log
    with open(UPLOAD_LOG, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result


def get_upload_history() -> list[dict]:
    """Read all past uploads from the log file."""
    if not UPLOAD_LOG.exists():
        return []
    records = []
    with open(UPLOAD_LOG) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records

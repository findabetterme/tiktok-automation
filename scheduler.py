"""
Schedule automatic video uploads.

Usage:
    python scheduler.py               # run scheduler loop (reads queue/)
    python scheduler.py --add-job     # interactively queue a video
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import schedule
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from tiktok_client import TikTokClient
from uploader import upload_video

load_dotenv()

console = Console()
QUEUE_DIR = Path("queue")
QUEUE_DIR.mkdir(exist_ok=True)


# ── Job helpers ───────────────────────────────────────────────────────────────

def add_to_queue(
    video_path: str,
    title: str,
    hashtags: list[str],
    scheduled_utc: str,        # ISO 8601, e.g. "2025-04-01T18:00:00+00:00"
) -> Path:
    """Write a job JSON file to the queue directory."""
    job = {
        "video_path": video_path,
        "title": title,
        "hashtags": hashtags,
        "scheduled_utc": scheduled_utc,
        "status": "pending",
    }
    safe_name = scheduled_utc.replace(":", "-").replace("+", "Z")[:19]
    job_path = QUEUE_DIR / f"job_{safe_name}.json"
    job_path.write_text(json.dumps(job, indent=2))
    console.print(f"[green]Queued:[/green] {job_path.name}")
    return job_path


def list_queue() -> list[tuple[Path, dict]]:
    """Return all pending job files sorted by scheduled time."""
    jobs = []
    for f in sorted(QUEUE_DIR.glob("job_*.json")):
        data = json.loads(f.read_text())
        if data.get("status") == "pending":
            jobs.append((f, data))
    return jobs


def run_due_jobs(client: TikTokClient, dry_run: bool = False):
    """Check queue for jobs whose scheduled time has passed and upload them."""
    now = datetime.now(tz=timezone.utc)
    for job_path, job in list_queue():
        scheduled = datetime.fromisoformat(job["scheduled_utc"])
        if now >= scheduled:
            console.print(f"\n[bold]Running job:[/bold] {job_path.name}")
            try:
                upload_video(
                    client,
                    video_path=job["video_path"],
                    title=job["title"],
                    hashtags=job["hashtags"],
                    dry_run=dry_run,
                )
                job["status"] = "done"
            except Exception as exc:
                console.print(f"[red]Upload failed:[/red] {exc}")
                job["status"] = f"failed: {exc}"
            job_path.write_text(json.dumps(job, indent=2))


def show_queue():
    """Pretty-print pending jobs."""
    jobs = list_queue()
    if not jobs:
        console.print("[yellow]Queue is empty.[/yellow]")
        return
    table = Table(title="Pending Uploads", show_lines=True)
    table.add_column("File", style="cyan")
    table.add_column("Title")
    table.add_column("Scheduled (UTC)")
    for path, job in jobs:
        table.add_row(
            path.name,
            job["title"][:50],
            job["scheduled_utc"],
        )
    console.print(table)


# ── Scheduler loop ────────────────────────────────────────────────────────────

def start_scheduler(check_interval_minutes: int = 5, dry_run: bool = False):
    """
    Block forever, checking the queue every `check_interval_minutes`.
    Set dry_run=True to test without actually posting.
    """
    client = TikTokClient()
    console.print(
        f"[bold green]Scheduler started.[/bold green] "
        f"Checking every {check_interval_minutes} min. "
        f"{'[yellow](DRY RUN)[/yellow]' if dry_run else ''}"
    )
    show_queue()

    schedule.every(check_interval_minutes).minutes.do(
        run_due_jobs, client=client, dry_run=dry_run
    )
    # Run once immediately on start
    run_due_jobs(client, dry_run=dry_run)

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TikTok upload scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Skip actual uploads")
    parser.add_argument("--show-queue", action="store_true", help="List pending jobs")
    parser.add_argument("--interval", type=int, default=5, help="Check interval (minutes)")
    args = parser.parse_args()

    if args.show_queue:
        show_queue()
    else:
        start_scheduler(check_interval_minutes=args.interval, dry_run=args.dry_run)

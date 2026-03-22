"""
TikTok Automation — main entrypoint (無料スタック版)

Commands:
    python main.py analytics                    アナリティクス取得・表示
    python main.py generate                     Geminiでスクリプト生成
    python main.py generate --topic "テーマ"
    python main.py generate --count 3
    python main.py create-video                 スクリプトから動画生成 (MoviePy)
    python main.py create-video --theme blue
    python main.py upload <video.mp4>           即時アップロード
    python main.py upload <video.mp4> --dry-run
    python main.py full-pipeline                全自動: 生成→動画→アップロード
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from analytics import fetch_analytics, format_analytics_summary
from script_generator import generate_script, generate_batch, VideoScript
from tiktok_client import TikTokClient
from uploader import upload_video

load_dotenv()
console = Console()


def cmd_analytics(_args):
    client = TikTokClient()
    console.print("[bold cyan]Fetching analytics...[/bold cyan]")
    data = fetch_analytics(client)
    summary = format_analytics_summary(data)
    console.print(Panel(summary, title="TikTok Analytics", border_style="cyan"))
    Path("analytics_cache.txt").write_text(summary)
    console.print("[dim]Saved to analytics_cache.txt[/dim]")


def cmd_generate(args):
    niche = os.getenv("TIKTOK_NICHE", "lifestyle")
    tone = os.getenv("TIKTOK_TONE", "engaging and relatable")

    cache = Path("analytics_cache.txt")
    if cache.exists():
        analytics_summary = cache.read_text()
        console.print("[dim]Using cached analytics[/dim]")
    else:
        analytics_summary = f"Niche: {niche}. No analytics data yet — write broadly appealing content."

    count = getattr(args, "count", 1) or 1
    topic = getattr(args, "topic", "") or ""

    if count == 1:
        console.print(f"[bold cyan]Generating script (Gemini 2.0 Flash)...[/bold cyan]")
        scripts = [generate_script(niche, tone, analytics_summary, topic)]
    else:
        topics = [topic or f"{niche} tip #{i+1}" for i in range(count)]
        console.print(f"[bold cyan]Generating {count} scripts...[/bold cyan]")
        scripts = generate_batch(niche, tone, analytics_summary, topics)

    for i, script in enumerate(scripts, 1):
        body_text = "\n".join(f"  • {b}" for b in script.body)
        console.print(
            Panel(
                f"[bold]HOOK:[/bold] {script.hook}\n\n"
                f"[bold]BODY:[/bold]\n{body_text}\n\n"
                f"[bold]CTA:[/bold] {script.cta}\n\n"
                f"[bold]Tags:[/bold] {' '.join('#'+h for h in script.hashtags)}\n"
                f"[bold]Duration:[/bold] ~{script.estimated_duration_sec}s",
                title=f"Script {i}: {script.title}",
                border_style="green",
            )
        )
        out = Path(f"script_{i:02d}.json")
        out.write_text(json.dumps({
            "title": script.title,
            "hook": script.hook,
            "body": script.body,
            "cta": script.cta,
            "hashtags": script.hashtags,
            "estimated_duration_sec": script.estimated_duration_sec,
        }, indent=2, ensure_ascii=False))
        console.print(f"[dim]Saved → {out}[/dim]")


def cmd_create_video(args):
    from video_creator import create_video

    script_path = Path("script_01.json")
    if not script_path.exists():
        console.print("[red]script_01.json not found. Run 'generate' first.[/red]")
        return

    data = json.loads(script_path.read_text())
    script = VideoScript(**data)
    theme = getattr(args, "theme", "dark") or "dark"
    output = getattr(args, "output", "output.mp4") or "output.mp4"
    audio = getattr(args, "audio", None)

    console.print(f"[bold cyan]Creating video (MoviePy, theme={theme})...[/bold cyan]")
    path = create_video(script, output_path=output, theme=theme, audio_path=audio)
    console.print(f"[green]✓ Video saved:[/green] {path}")


def cmd_upload(args):
    client = TikTokClient()
    script_path = Path("script_01.json")
    hashtags, title = [], Path(args.video).stem

    if script_path.exists():
        data = json.loads(script_path.read_text())
        title = data.get("title", title)
        hashtags = data.get("hashtags", [])

    upload_video(client, args.video, title, hashtags, dry_run=args.dry_run)


def cmd_full_pipeline(args):
    """全自動: analytics → generate → create-video → upload"""
    console.rule("[bold]1. Analytics[/bold]")
    try:
        cmd_analytics(args)
    except Exception as e:
        console.print(f"[yellow]Analytics skipped: {e}[/yellow]")

    console.rule("[bold]2. Generate Script[/bold]")
    cmd_generate(args)

    console.rule("[bold]3. Create Video[/bold]")
    args.theme = "dark"
    args.output = "output.mp4"
    args.audio = None
    cmd_create_video(args)

    console.rule("[bold]4. Upload[/bold]")
    args.video = "output.mp4"
    args.dry_run = getattr(args, "dry_run", False)
    cmd_upload(args)


def main():
    parser = argparse.ArgumentParser(
        prog="tiktok-automation",
        description="TikTok 自動化 (Gemini無料 + MoviePy + GitHub Actions)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("analytics", help="アナリティクスを取得・表示")

    gen = sub.add_parser("generate", help="Geminiでスクリプト生成")
    gen.add_argument("--topic", default="")
    gen.add_argument("--count", type=int, default=1)

    vid = sub.add_parser("create-video", help="スクリプトから動画生成")
    vid.add_argument("--theme", choices=["dark", "light", "blue"], default="dark")
    vid.add_argument("--output", default="output.mp4")
    vid.add_argument("--audio", default=None, help="BGM音声ファイルパス")

    up = sub.add_parser("upload", help="TikTokにアップロード")
    up.add_argument("video")
    up.add_argument("--dry-run", action="store_true")

    fp = sub.add_parser("full-pipeline", help="全自動実行")
    fp.add_argument("--topic", default="")
    fp.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    {
        "analytics": cmd_analytics,
        "generate": cmd_generate,
        "create-video": cmd_create_video,
        "upload": cmd_upload,
        "full-pipeline": cmd_full_pipeline,
    }[args.cmd](args)


if __name__ == "__main__":
    main()

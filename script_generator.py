"""
スクリプト生成 — Google Gemini 2.0 Flash (無料枠: 1,000 req/日)
無料APIキー取得: https://aistudio.google.com/app/apikey
クレジットカード不要。
"""
from __future__ import annotations
import json
import os
from dataclasses import dataclass
from google import genai
from dotenv import load_dotenv

load_dotenv()

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

@dataclass
class VideoScript:
    title: str
    hook: str
    body: list[str]
    cta: str
    hashtags: list[str]
    estimated_duration_sec: int

def generate_script(
    niche: str,
    tone: str,
    analytics_summary: str,
    topic_hint: str = "",
) -> VideoScript:
    topic_line = f"\nFocus this video on: {topic_hint}" if topic_hint else ""
    prompt = f"""You are an expert TikTok content strategist and scriptwriter.
Write a high-performing short-form video script for a {niche} creator with a {tone} tone.
Use the account analytics below to mirror what performs well.
{analytics_summary}
{topic_line}
Return ONLY valid JSON (no markdown fences, no extra text):
{{
  "title": "post caption under 150 chars",
  "hook": "word-for-word opening line for first 3 seconds",
  "body": ["beat 1", "beat 2", "beat 3", "beat 4", "beat 5"],
  "cta": "closing call-to-action line",
  "hashtags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "estimated_duration_sec": 30
}}
Rules:
- Hook must create instant curiosity — no slow intros
- Body: 4-6 punchy beats, each 2-3 seconds of spoken content
- Hashtags: mix 1 mega (>1B), 2 large (100M+), 2 niche (<10M)
- Duration: 15-60 seconds
"""
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
    )
    text = response.text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    data = json.loads(text.strip())
    body = data["body"]
    if isinstance(body, str):
        body = [line.strip("- ").strip() for line in body.splitlines() if line.strip()]
    return VideoScript(
        title=data["title"],
        hook=data["hook"],
        body=body,
        cta=data["cta"],
        hashtags=data["hashtags"],
        estimated_duration_sec=data["estimated_duration_sec"],
    )

def generate_batch(
    niche: str,
    tone: str,
    analytics_summary: str,
    topics: list[str],
) -> list[VideoScript]:
    """複数スクリプトを連続生成。"""
    return [
        generate_script(niche, tone, analytics_summary, topic)
        for topic in topics
    ]

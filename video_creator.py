"""
動画自動生成 — MoviePy (無料OSS)

スクリプトのビートごとにテキストオーバーレイを生成し、
TikTok縦型 (1080x1920) のMP4を出力する。

依存: moviepy, Pillow, numpy
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip,
    ColorClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)

from script_generator import VideoScript

# TikTok縦型サイズ
WIDTH, HEIGHT = 1080, 1920

# カラーテーマ (変更可)
THEMES = {
    "dark":  {"bg": (15, 15, 15),   "text": (255, 255, 255), "accent": (255, 80, 80)},
    "light": {"bg": (245, 245, 245), "text": (20, 20, 20),   "accent": (255, 60, 60)},
    "blue":  {"bg": (10, 20, 60),    "text": (255, 255, 255), "accent": (100, 180, 255)},
}


def _make_text_frame(
    text: str,
    bg_color: tuple,
    text_color: tuple,
    accent_color: tuple,
    font_size: int = 72,
    is_hook: bool = False,
) -> np.ndarray:
    """Pillow でテキストフレームを描画し numpy 配列で返す。"""
    img = Image.new("RGB", (WIDTH, HEIGHT), color=bg_color)
    draw = ImageDraw.Draw(img)

    # フォント (システムフォントを使用)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40)
    except OSError:
        font = ImageFont.load_default()
        font_small = font

    # アクセントライン
    if is_hook:
        draw.rectangle([(60, HEIGHT // 2 - 200), (WIDTH - 60, HEIGHT // 2 - 195)],
                       fill=accent_color)

    # テキスト折り返し
    wrapped = textwrap.fill(text, width=22)
    lines = wrapped.split("\n")

    # テキストを中央に配置
    total_h = len(lines) * (font_size + 16)
    y = (HEIGHT - total_h) // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        # シャドウ
        draw.text((x + 3, y + 3), line, font=font, fill=(0, 0, 0, 100))
        draw.text((x, y), line, font=font, fill=text_color)
        y += font_size + 16

    # 下部にインジケーター
    draw.text((WIDTH // 2 - 100, HEIGHT - 120), "↓  follow for more  ↓",
              font=font_small, fill=accent_color)

    return np.array(img)


def create_video(
    script: VideoScript,
    output_path: str = "output.mp4",
    theme: str = "dark",
    fps: int = 30,
    audio_path: str | None = None,
) -> str:
    """
    スクリプトから縦型TikTok動画を生成する。

    Args:
        script: VideoScript dataclass
        output_path: 出力先 .mp4 パス
        theme: "dark" | "light" | "blue"
        fps: フレームレート
        audio_path: BGM用音声ファイル (任意, .mp3/.wav)

    Returns:
        output_path (生成されたファイルのパス)
    """
    colors = THEMES.get(theme, THEMES["dark"])
    clips = []

    # 1. フック (最初の3秒)
    hook_frame = _make_text_frame(
        script.hook,
        bg_color=colors["bg"],
        text_color=colors["text"],
        accent_color=colors["accent"],
        font_size=80,
        is_hook=True,
    )
    hook_clip = ImageClip(hook_frame).set_duration(3).set_fps(fps)
    clips.append(hook_clip)

    # 2. ボディビート (各ビートを均等に配分)
    remaining = script.estimated_duration_sec - 3 - 3  # hook + cta
    beat_duration = max(2.0, remaining / max(len(script.body), 1))

    for beat in script.body:
        frame = _make_text_frame(
            beat,
            bg_color=colors["bg"],
            text_color=colors["text"],
            accent_color=colors["accent"],
            font_size=68,
        )
        clips.append(ImageClip(frame).set_duration(beat_duration).set_fps(fps))

    # 3. CTA (最後の3秒)
    cta_frame = _make_text_frame(
        script.cta,
        bg_color=colors["accent"],
        text_color=(255, 255, 255),
        accent_color=colors["bg"],
        font_size=72,
    )
    clips.append(ImageClip(cta_frame).set_duration(3).set_fps(fps))

    # 結合
    final = concatenate_videoclips(clips, method="compose")

    # BGM追加 (任意)
    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path).subclip(0, final.duration)
        final = final.set_audio(audio)

    # 書き出し
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile="temp_audio.m4a",
        remove_temp=True,
        logger=None,
    )

    return output_path

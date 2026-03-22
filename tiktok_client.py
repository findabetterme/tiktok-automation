"""TikTok API client — wraps the v2 Content Posting & Analytics APIs."""

import os
import time
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

TIKTOK_API_BASE = "https://open.tiktokapis.com/v2"


class TikTokClient:
    def __init__(self):
        self.access_token = os.environ["TIKTOK_ACCESS_TOKEN"]
        self.client_key = os.environ["TIKTOK_CLIENT_KEY"]
        self.client_secret = os.environ["TIKTOK_CLIENT_SECRET"]
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})

    def _get(self, path: str, params: dict = None) -> dict:
        resp = self.session.get(f"{TIKTOK_API_BASE}{path}", params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error", {}).get("code", "ok") != "ok":
            raise RuntimeError(f"TikTok API error: {data['error']}")
        return data

    def _post(self, path: str, json: dict = None) -> dict:
        resp = self.session.post(f"{TIKTOK_API_BASE}{path}", json=json)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error", {}).get("code", "ok") != "ok":
            raise RuntimeError(f"TikTok API error: {data['error']}")
        return data

    # ── Analytics ────────────────────────────────────────────────────────────

    def get_user_info(self) -> dict:
        """Fetch basic creator account info."""
        data = self._get(
            "/user/info/",
            params={"fields": "open_id,display_name,follower_count,likes_count"},
        )
        return data["data"]["user"]

    def get_video_list(self, max_count: int = 20) -> list[dict]:
        """Fetch the creator's recent videos with engagement stats."""
        data = self._post(
            "/video/list/",
            json={
                "max_count": max_count,
                "fields": [
                    "id",
                    "title",
                    "create_time",
                    "view_count",
                    "like_count",
                    "comment_count",
                    "share_count",
                    "duration",
                ],
            },
        )
        return data["data"].get("videos", [])

    def get_video_query(self, video_ids: list[str]) -> list[dict]:
        """Get detailed stats for specific video IDs."""
        data = self._post(
            "/video/query/",
            json={
                "filters": {"video_ids": video_ids},
                "fields": [
                    "id",
                    "title",
                    "view_count",
                    "like_count",
                    "comment_count",
                    "share_count",
                    "create_time",
                ],
            },
        )
        return data["data"].get("videos", [])

    # ── Upload ────────────────────────────────────────────────────────────────

    def initialize_upload(self, video_path: str, title: str) -> tuple[str, str]:
        """
        Step 1 of the two-step upload: initialize and get an upload URL.
        Returns (publish_id, upload_url).
        """
        file_size = os.path.getsize(video_path)
        data = self._post(
            "/post/publish/video/init/",
            json={
                "post_info": {
                    "title": title,
                    "privacy_level": "PUBLIC_TO_EVERYONE",
                    "disable_duet": False,
                    "disable_comment": False,
                    "disable_stitch": False,
                },
                "source_info": {
                    "source": "FILE_UPLOAD",
                    "video_size": file_size,
                    "chunk_size": file_size,
                    "total_chunk_count": 1,
                },
            },
        )
        publish_id = data["data"]["publish_id"]
        upload_url = data["data"]["upload_url"]
        return publish_id, upload_url

    def upload_video_bytes(self, upload_url: str, video_path: str):
        """Step 2: PUT the video bytes to the signed upload URL."""
        file_size = os.path.getsize(video_path)
        with open(video_path, "rb") as f:
            resp = requests.put(
                upload_url,
                data=f,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
                },
            )
        resp.raise_for_status()

    def check_publish_status(self, publish_id: str) -> dict:
        """Poll the publish status after uploading."""
        data = self._post(
            "/post/publish/status/fetch/",
            json={"publish_id": publish_id},
        )
        return data["data"]

    def publish_video(
        self, video_path: str, title: str, poll_interval: int = 5, max_wait: int = 120
    ) -> str:
        """
        Full upload flow: initialize → upload bytes → poll until published.
        Returns the final publish_id.
        """
        publish_id, upload_url = self.initialize_upload(video_path, title)
        self.upload_video_bytes(upload_url, video_path)

        deadline = time.time() + max_wait
        while time.time() < deadline:
            status = self.check_publish_status(publish_id)
            if status.get("status") == "PUBLISH_COMPLETE":
                return publish_id
            if status.get("status") in ("FAILED", "SPAM_RISK_TOO_MANY_POSTS"):
                raise RuntimeError(f"Publish failed: {status}")
            time.sleep(poll_interval)

        raise TimeoutError(f"Video did not finish publishing within {max_wait}s")

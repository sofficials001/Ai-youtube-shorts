#!/usr/bin/env python3
"""Upload a silent, caption-led tiny-world Short to YouTube."""
import json, os, sys
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

required = ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN")
secrets = {key: os.getenv(key, "").strip() for key in required}
for key, value in secrets.items():
    if not value:
        raise SystemExit(f"Missing GitHub secret: {key}")
video = Path("output/final_short.mp4")
story_file = Path("story.json")
if not video.is_file() or video.stat().st_size == 0 or not story_file.is_file():
    raise SystemExit("Video or story.json is missing.")
story = json.loads(story_file.read_text(encoding="utf-8"))
title = str(story.get("title", "Tiny People, Giant World")).strip()[:95]
description = (
    title + "\n\nOriginal 3D-style tiny-world story told through visuals and Hindi on-screen captions. No voice-over.\n\n"
    "#Shorts #TinyWorld #HindiShorts #3DAnimation #VisualStorytelling"
)
tags = ["shorts", "tiny people", "giant world", "miniature world", "hindi shorts", "3d animation", "visual storytelling", "ai animation", "tiny world", "miniature adventure"]
credentials = Credentials(
    token=None,
    refresh_token=secrets["YOUTUBE_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=secrets["YOUTUBE_CLIENT_ID"],
    client_secret=secrets["YOUTUBE_CLIENT_SECRET"],
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)
credentials.refresh(Request())
youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
body = {
    "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "1", "defaultLanguage": "hi"},
    "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
}
media = MediaFileUpload(str(video), mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
try:
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=False)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube returned no video ID.")
    print("UPLOAD SUCCESSFUL:", f"https://youtube.com/shorts/{video_id}")
    print("Requested privacy: public; YouTube project restrictions may override this.")
except HttpError as exc:
    print("YouTube API error:", exc, file=sys.stderr)
    raise SystemExit(1)
except Exception as exc:
    print("Upload failed:", exc, file=sys.stderr)
    raise SystemExit(1)

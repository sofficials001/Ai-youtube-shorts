
import json
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

VIDEO = Path("final_video.mp4")
METADATA = Path("artifacts/youtube_metadata.json")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing GitHub secret: {name}")
    return value


def main():
    if not VIDEO.is_file() or VIDEO.stat().st_size == 0:
        raise RuntimeError("Final video is missing or empty")

    if not METADATA.is_file():
        raise RuntimeError("YouTube metadata file is missing")

    with METADATA.open(encoding="utf-8") as file:
        metadata = json.load(file)

    title = str(metadata.get("title", "")).strip()
    description = str(metadata.get("description", "")).strip()
    tags = metadata.get("tags", [])
    category = str(metadata.get("category", "1"))

    if not title:
        raise RuntimeError("YouTube title is empty")
    if not isinstance(tags, list):
        raise RuntimeError("YouTube tags must be a list")

    credentials = Credentials(
        token=None,
        refresh_token=required_env("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=required_env("YOUTUBE_CLIENT_ID"),
        client_secret=required_env("YOUTUBE_CLIENT_SECRET"),
        scopes=SCOPES,
    )

    youtube = build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    # Upload privately first, so the video is not
    # accidentally published before you review it.
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": [str(tag)[:500] for tag in tags[:500]],
            "categoryId": category,
            "defaultLanguage": "hi",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": True,
        },
    }

    media = MediaFileUpload(
        str(VIDEO),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=False,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("Upload returned no video ID")

    print("UPLOAD SUCCESSFUL")
    print(f"Video ID: {video_id}")
    print(f"YouTube link: https://www.youtube.com/watch?v={video_id}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, HttpError, OSError, ValueError) as exc:
        print(f"UPLOAD FAILED: {exc}", file=sys.stderr)
        sys.exit(1)

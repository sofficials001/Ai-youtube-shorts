import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# ============================================================
# PATHS
# ============================================================

ROOT = Path(
    __file__
).resolve().parents[1]

VIDEO_FILE = (
    ROOT
    / "output"
    / "final_short.mp4"
)

STORY_FILE = (
    ROOT
    / "story.json"
)


# ============================================================
# GITHUB SECRETS
# ============================================================

CLIENT_ID = os.environ.get(
    "YOUTUBE_CLIENT_ID",
    ""
).strip()

CLIENT_SECRET = os.environ.get(
    "YOUTUBE_CLIENT_SECRET",
    ""
).strip()

REFRESH_TOKEN = os.environ.get(
    "YOUTUBE_REFRESH_TOKEN",
    ""
).strip()


# ============================================================
# VALIDATE SECRETS
# ============================================================

if not CLIENT_ID:

    raise RuntimeError(
        "YOUTUBE_CLIENT_ID is missing."
    )

if not CLIENT_SECRET:

    raise RuntimeError(
        "YOUTUBE_CLIENT_SECRET is missing."
    )

if not REFRESH_TOKEN:

    raise RuntimeError(
        "YOUTUBE_REFRESH_TOKEN is missing."
    )


# ============================================================
# VALIDATE FILES
# ============================================================

if not VIDEO_FILE.exists():

    raise RuntimeError(
        f"Video file does not exist: "
        f"{VIDEO_FILE}"
    )

if not STORY_FILE.exists():

    raise RuntimeError(
        f"Story file does not exist: "
        f"{STORY_FILE}"
    )


# ============================================================
# LOAD STORY METADATA
# ============================================================

with open(
    STORY_FILE,
    "r",
    encoding="utf-8"
) as file:

    story = json.load(
        file
    )


title = str(
    story.get(
        "title",
        "AI YouTube Short"
    )
).strip()

description = str(
    story.get(
        "description",
        ""
    )
).strip()

tags = [
    str(tag).strip()
    for tag in story.get(
        "tags",
        []
    )
    if str(tag).strip()
]


# YouTube title maximum is 100 characters.
title = title[:100]

# Add Shorts hashtag if it isn't already present.
if "#Shorts" not in description:

    description += (
        "\n\n#Shorts"
    )

# Keep description within the API limit.
description = description[:5000]

# Keep a reasonable number of tags.
tags = tags[:30]


# ============================================================
# CREATE GOOGLE OAUTH CREDENTIALS
# ============================================================

credentials = Credentials(
    token=None,

    refresh_token=REFRESH_TOKEN,

    token_uri=(
        "https://oauth2.googleapis.com/token"
    ),

    client_id=CLIENT_ID,

    client_secret=CLIENT_SECRET,

    scopes=[
        "https://www.googleapis.com/auth/youtube.upload"
    ]
)


# ============================================================
# REFRESH ACCESS TOKEN
# ============================================================

print(
    "Refreshing YouTube access token..."
)

credentials.refresh(
    Request()
)

print(
    "YouTube authentication successful."
)


# ============================================================
# BUILD YOUTUBE CLIENT
# ============================================================

youtube = build(
    "youtube",
    "v3",
    credentials=credentials
)


# ============================================================
# VIDEO METADATA
# ============================================================

request_body = {

    "snippet": {

        "title": title,

        "description": description,

        "tags": tags,

        "categoryId": "22",

        "defaultLanguage": "hi"
    },

    "status": {

        # ----------------------------------------------------
        # KEEP PRIVATE DURING TESTING.
        # ----------------------------------------------------

        "privacyStatus": "private"
    }
}


# ============================================================
# PREPARE MEDIA
# ============================================================

media = MediaFileUpload(

    str(VIDEO_FILE),

    mimetype="video/mp4",

    resumable=True,

    chunksize=1024 * 1024
)


# ============================================================
# START UPLOAD
# ============================================================

request = youtube.videos().insert(

    part="snippet,status",

    body=request_body,

    media_body=media
)


print("")
print(
    "Uploading Short to YouTube..."
)


# ============================================================
# UPLOAD LOOP
# ============================================================

response = None

while response is None:

    status, response = (
        request.next_chunk()
    )

    if status:

        progress = int(
            status.progress()
            * 100
        )

        print(
            f"Upload progress: "
            f"{progress}%"
        )


# ============================================================
# VERIFY RESPONSE
# ============================================================

if not response:

    raise RuntimeError(
        "YouTube returned no response."
    )


video_id = response.get(
    "id"
)

if not video_id:

    print(
        "YouTube response:"
    )

    print(
        response
    )

    raise RuntimeError(
        "YouTube response did not "
        "contain a video ID."
    )


# ============================================================
# SUCCESS
# ============================================================

print("")
print(
    "=========================================="
)

print(
    "YOUTUBE UPLOAD SUCCESSFUL"
)

print(
    "=========================================="
)

print(
    "Video ID:",
    video_id
)

print(
    "URL:",
    f"https://youtube.com/shorts/{video_id}"
)

print(
    "Privacy: PRIVATE"
)

print(
    "=========================================="
)

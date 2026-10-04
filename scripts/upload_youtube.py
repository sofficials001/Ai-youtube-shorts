import json
import os
import re
import sys
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


ROOT = Path(__file__).resolve().parent.parent
VIDEO_PATH = ROOT / "output" / "final_short.mp4"
STORY_PATH = ROOT / "story.json"

CLIENT_ID = os.environ.get("YOUTUBE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET")
REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload"
]


def fail(message):
    print(f"ERROR: {message}")
    sys.exit(1)


def clean_text(value):
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(str(x) for x in value)

    return str(value).strip()


def remove_hashtags(text):
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def limit_text(text, maximum):
    text = clean_text(text)

    if len(text) <= maximum:
        return text

    shortened = text[:maximum - 3].rstrip()

    if " " in shortened:
        shortened = shortened.rsplit(" ", 1)[0]

    return shortened + "..."


def load_story():
    if not STORY_PATH.exists():
        fail(f"Story file not found: {STORY_PATH}")

    try:
        with STORY_PATH.open("r", encoding="utf-8") as file:
            story = json.load(file)
    except Exception as exc:
        fail(f"Could not read story.json: {exc}")

    if not isinstance(story, dict):
        fail("story.json must contain a JSON object.")

    return story


def get_story_text(story):
    parts = []

    title = clean_text(
        story.get("title")
        or story.get("topic")
        or story.get("story_title")
    )

    hook = clean_text(
        story.get("hook")
        or story.get("opening")
        or story.get("intro")
    )

    scenes = story.get("scenes", [])

    if isinstance(scenes, list):
        for scene in scenes:
            if not isinstance(scene, dict):
                continue

            narration = clean_text(
                scene.get("narration")
                or scene.get("voiceover")
                or scene.get("text")
                or scene.get("script")
            )

            if narration:
                parts.append(narration)

    ending = clean_text(
        story.get("ending")
        or story.get("ending_cta")
        or story.get("conclusion")
    )

    if hook:
        parts.insert(0, hook)

    if ending:
        parts.append(ending)

    combined = " ".join(parts)

    return title, combined


def extract_keywords(text):
    text = remove_hashtags(text)

    words = re.findall(r"[A-Za-z0-9\u0900-\u097F]+", text.lower())

    stop_words = {
        "और",
        "एक",
        "इस",
        "उस",
        "की",
        "के",
        "का",
        "को",
        "से",
        "में",
        "पर",
        "था",
        "थी",
        "थे",
        "है",
        "हो",
        "ही",
        "तो",
        "ने",
        "यह",
        "वह",
        "जब",
        "तब",
        "लेकिन",
        "फिर",
        "अपने",
        "अपनी",
        "लिए",
        "the",
        "and",
        "was",
        "were",
        "this",
        "that",
        "with",
        "from",
        "into",
        "then",
        "when",
        "there",
        "they",
        "their",
        "have",
        "has",
        "had",
        "you",
        "your",
        "for",
        "not",
        "but",
        "one",
        "only",
    }

    keywords = []

    for word in words:
        if len(word) < 3:
            continue

        if word in stop_words:
            continue

        if word not in keywords:
            keywords.append(word)

    return keywords[:12]


def make_title(story):
    story_title, story_text = get_story_text(story)

    base = remove_hashtags(story_title)

    if not base:
        keywords = extract_keywords(story_text)

        if keywords:
            base = " ".join(keywords[:5]).title()
        else:
            base = "एक कहानी जो आपको अंत तक सोचने पर मजबूर कर देगी"

    # Avoid boring generic titles where possible.
    title_styles = [
        f"{base} 😱",
        f"{base} का सच 😱",
        f"{base} का रहस्य 🤯",
        f"{base} के पीछे की कहानी 😳",
        f"{base}... लेकिन फिर 😱",
    ]

    # Use the story title itself if it already looks like a strong title.
    if len(base) >= 10:
        candidates = title_styles
    else:
        candidates = [
            "यह कहानी आखिर तक देखना 😱",
            "अंत में जो हुआ वो हैरान कर देगा 🤯",
            "इस कहानी का सच जानकर चौंक जाओगे 😳",
        ]

    # Select based on story length so metadata remains deterministic.
    index = len(story_text) % len(candidates)
    title = candidates[index]

    # Required hashtag.
    title = f"{title} #Shorts"

    # YouTube title limit is 100 characters.
    title = limit_text(title, 100)

    return title


def make_description(story):
    story_title, story_text = get_story_text(story)
    keywords = extract_keywords(story_text)

    first_line = (
        story_text[:180].strip()
        if story_text
        else "एक छोटी और दिलचस्प कहानी जो आपको अंत तक देखने पर मजबूर कर देगी।"
    )

    if story_text and len(story_text) > 180:
        first_line += "..."

    keyword_line = ""

    if keywords:
        keyword_line = (
            "\n\nTopics: "
            + ", ".join(keywords[:8])
        )

    description = (
        f"{first_line}\n\n"
        "अगर आपको ऐसी छोटी और interesting stories पसंद हैं, "
        "तो वीडियो को Like करें और Channel को Subscribe करें।\n\n"
        "#Shorts #Story #HindiStory #ViralShorts #YouTubeShorts"
        f"{keyword_line}"
    )

    return limit_text(description, 5000)


def make_tags(story):
    _, story_text = get_story_text(story)

    keywords = extract_keywords(story_text)

    tags = [
        "shorts",
        "youtube shorts",
        "viral shorts",
        "hindi shorts",
        "hindi story",
        "short story",
        "story",
        "interesting story",
        "viral video",
        "trending shorts",
        "ai story",
        "ai shorts",
    ]

    for keyword in keywords:
        keyword = keyword.strip()

        if not keyword:
            continue

        if keyword not in tags:
            tags.append(keyword)

        if len(tags) >= 25:
            break

    # YouTube's tags field is limited in total size.
    final_tags = []

    for tag in tags:
        tag = clean_text(tag)

        if not tag:
            continue

        if tag not in final_tags:
            final_tags.append(tag)

    return final_tags[:25]


def create_credentials():
    if not CLIENT_ID:
        fail("YOUTUBE_CLIENT_ID secret is missing.")

    if not CLIENT_SECRET:
        fail("YOUTUBE_CLIENT_SECRET secret is missing.")

    if not REFRESH_TOKEN:
        fail("YOUTUBE_REFRESH_TOKEN secret is missing.")

    credentials = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )

    try:
        credentials.refresh(Request())
    except Exception as exc:
        fail(
            "Could not refresh YouTube OAuth token. "
            f"Check the YouTube secrets and OAuth configuration.\n{exc}"
        )

    return credentials


def upload_video():
    if not VIDEO_PATH.exists():
        fail(f"Video not found: {VIDEO_PATH}")

    if VIDEO_PATH.stat().st_size < 10000:
        fail("Video file is suspiciously small.")

    story = load_story()

    title = make_title(story)
    description = make_description(story)
    tags = make_tags(story)

    print("")
    print("=" * 60)
    print("YOUTUBE UPLOAD")
    print("=" * 60)
    print(f"Title: {title}")
    print(f"Description length: {len(description)} characters")
    print(f"Tags: {len(tags)}")
    print("Privacy: PUBLIC")
    print("=" * 60)
    print("")

    credentials = create_credentials()

    try:
        youtube = build(
            "youtube",
            "v3",
            credentials=credentials
        )
    except Exception as exc:
        fail(f"Could not create YouTube API client: {exc}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(VIDEO_PATH),
        mimetype="video/mp4",
        resumable=True,
        chunksize=8 * 1024 * 1024,
    )

    print("Starting YouTube upload...")

    try:
        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
            notifySubscribers=True,
        )
    except Exception as exc:
        fail(f"Could not create YouTube upload request: {exc}")

    response = None

    try:
        while response is None:
            status, response = request.next_chunk()

            if status:
                progress = int(status.progress() * 100)
                print(f"Upload progress: {progress}%")

    except Exception as exc:
        fail(f"YouTube upload failed: {exc}")

    video_id = response.get("id")

    if not video_id:
        fail(f"YouTube did not return a video ID: {response}")

    print("")
    print("=" * 60)
    print("UPLOAD SUCCESSFUL")
    print("=" * 60)
    print(f"Video ID: {video_id}")
    print(f"URL: https://www.youtube.com/shorts/{video_id}")
    print("Privacy requested: PUBLIC")
    print("=" * 60)


def main():
    upload_video()


if __name__ == "__main__":
    main()

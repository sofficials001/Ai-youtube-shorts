import ast
import asyncio
import base64
import json
import os
import random
import re
import subprocess
import sys
import time
from io import BytesIO
from pathlib import Path

import edge_tts
import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent

SCENES = ROOT / "scenes"
AUDIO = ROOT / "audio"
SEGMENTS = ROOT / "segments"
OUTPUT = ROOT / "output"

for d in (SCENES, AUDIO, SEGMENTS, OUTPUT):
    d.mkdir(parents=True, exist_ok=True)

CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID")

if not CF_TOKEN or not CF_ACCOUNT:
    raise RuntimeError(
        "Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
    )

LLM = "@cf/meta/llama-3.2-3b-instruct"
IMAGE = "@cf/black-forest-labs/flux-1-schnell"
VOICE = "hi-IN-SwaraNeural"

HEADERS = {
    "Authorization": f"Bearer {CF_TOKEN}",
    "Content-Type": "application/json",
}


def cf_url(model):
    return (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )


def run(cmd):
    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError(
            "Command failed: " + " ".join(cmd)
        )

    return result.stdout


def fallback():
    return {
        "title": "इस छोटे खरगोश ने अपनी जान की परवाह नहीं की",
        "description": (
            "एक छोटे खरगोश की बहादुरी की कहानी। "
            "अंत तक देखिए। #Shorts"
        ),
        "tags": [
            "shorts",
            "hindi story",
            "rabbit",
            "animal story",
        ],
        "scenes": [
            {
                "type": "HOOK",
                "narration": (
                    "रुको... इस छोटे खरगोश ने अपनी जान बचाने के "
                    "बजाय किसी और को बचाना क्यों चुना?"
                ),
                "visual": (
                    "A small cute white rabbit wearing a blue scarf "
                    "standing alone in a dark forest at dusk, "
                    "cinematic close-up, dramatic lighting"
                ),
            },
            {
                "type": "SETUP",
                "narration": (
                    "हर शाम वह खरगोश जंगल के किनारे एक पुराने पेड़ "
                    "के पास जाता था, जहाँ उसे एक अजीब आवाज़ सुनाई देती थी।"
                ),
                "visual": (
                    "The same small white rabbit wearing a blue scarf "
                    "walking beside an old tree at sunset, curious "
                    "expression, cinematic"
                ),
            },
            {
                "type": "PROBLEM",
                "narration": (
                    "एक दिन तेज़ बारिश शुरू हुई और पास की नदी का "
                    "पानी तेजी से बढ़ने लगा।"
                ),
                "visual": (
                    "The same white rabbit wearing a blue scarf "
                    "watching a rapidly rising stream during heavy "
                    "rain, worried expression, cinematic"
                ),
            },
            {
                "type": "TENSION",
                "narration": (
                    "तभी उसे झाड़ियों से एक नन्ही चिड़िया की आवाज़ "
                    "सुनाई दी। वह पानी के बीच फँसी थी।"
                ),
                "visual": (
                    "The same white rabbit wearing a blue scarf "
                    "discovering a tiny frightened bird trapped "
                    "near rushing water, intense rain, cinematic"
                ),
            },
            {
                "type": "CLIMAX",
                "narration": (
                    "खरगोश डर रहा था, फिर भी वह पानी में उतर गया "
                    "और चिड़िया को सुरक्षित किनारे तक ले आया।"
                ),
                "visual": (
                    "The same brave white rabbit wearing a blue scarf "
                    "helping a tiny bird reach a safe riverbank while "
                    "water rushes around them, heroic cinematic moment"
                ),
            },
            {
                "type": "ENDING_CTA",
                "narration": (
                    "अगली सुबह चिड़िया उड़ गई, लेकिन जाने से पहले "
                    "उसने अपने पंख से खरगोश का नीला स्कार्फ छुआ। "
                    "ऐसी कहानी पसंद आए तो फॉलो कर देना।"
                ),
                "visual": (
                    "The same white rabbit wearing a blue scarf beside "
                    "the rescued bird at sunrise, warm golden light, "
                    "emotional farewell, cinematic"
                ),
            },
        ],
    }


def parse_story(data):
    if isinstance(data, dict):
        if isinstance(data.get("scenes"), list):
            return data

        for key in ("result", "response", "output"):
            if key in data:
                found = parse_story(data[key])

                if found:
                    return found

        return None

    if not isinstance(data, str):
        return None

    text = data.strip().strip("`")
    candidates = [text]

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        candidates.append(
            text[start:end + 1]
        )

    for item in candidates:
        try:
            obj = json.loads(item)

            if (
                isinstance(obj, dict)
                and isinstance(obj.get("scenes"), list)
            ):
                return obj

        except (ValueError, TypeError):
            pass

        try:
            obj = ast.literal_eval(item)

            if (
                isinstance(obj, dict)
                and isinstance(obj.get("scenes"), list)
            ):
                return obj

        except (
            ValueError,
            SyntaxError,
            TypeError,
        ):
            pass

    return None


def normalize(story):
    if (
        not isinstance(story, dict)
        or len(story.get("scenes", [])) != 6
    ):
        raise ValueError(
            "Story must contain exactly 6 scenes"
        )

    types = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA",
    ]

    for i, scene in enumerate(story["scenes"]):
        if not isinstance(scene, dict):
            raise ValueError(
                f"Invalid scene {i + 1}"
            )

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual = str(
            scene.get("visual", "")
        ).strip()

        if not narration or not visual:
            raise ValueError(
                f"Scene {i + 1} is missing narration or visual"
            )

        scene["type"] = types[i]
        scene["narration"] = narration
        scene["visual"] = (
            visual
            + " Same white rabbit with blue scarf. "
            + "No text, logo, letters, or watermark."
        )

    story.setdefault(
        "title",
        "एक कहानी जिसका अंत आपको चौंका देगा",
    )

    story.setdefault(
        "description",
        "एक छोटी कहानी जिसका अंत याद रहेगा। #Shorts",
    )

    story.setdefault(
        "tags",
        ["shorts", "story", "hindi"],
    )

    return story


def save_story(story):
    (ROOT / "story.json").write_text(
        json.dumps(
            story,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    lines = [
        story["title"],
        "",
    ]

    for i, scene in enumerate(
        story["scenes"],
        1,
    ):
        lines.append(
            f"{i}. {scene['type']}"
        )
        lines.append(
            scene["narration"]
        )
        lines.append("")

    (ROOT / "story.txt").write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def generate_story():
    prompt = """
Create a Hindi YouTube Shorts story.

Return ONLY valid JSON with exactly 6 scenes:

HOOK
SETUP
PROBLEM
TENSION
CLIMAX
ENDING_CTA

The story must have:
- a strong curiosity hook
- a clear problem
- rising tension
- a satisfying climax
- a real ending
- a natural short CTA
- spoken Hindi
- 25-55 seconds total

Format:

{
  "title": "...",
  "description": "...",
  "tags": ["shorts"],
  "scenes": [
    {
      "type": "HOOK",
      "narration": "...",
      "visual": "..."
    }
  ]
}
"""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write high-retention "
                    "YouTube Shorts stories."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
    }

    for attempt in range(3):
        try:
            response = requests.post(
                cf_url(LLM),
                headers=HEADERS,
                json=payload,
                timeout=120,
            )

            print(
                "Story HTTP:",
                response.status_code,
            )

            response.raise_for_status()

            story = parse_story(
                response.json()
            )

            if story:
                story = normalize(story)
                save_story(story)
                return story

        except Exception as error:
            print(
                "Story attempt failed:",
                error,
            )

            if attempt < 2:
                time.sleep(3)

    story = normalize(
        fallback()
    )

    save_story(
        story
    )

    print(
        "Using fallback story."
    )

    return story


def decode_image(value):
    if isinstance(value, str):
        value = value.strip()

        if (
            value.startswith("data:image")
            and "," in value
        ):
            value = value.split(
                ",",
                1,
            )[1]

        try:
            return base64.b64decode(
                value,
                validate=True,
            )
        except Exception:
            return None

    if isinstance(value, dict):
        for key in (
            "image",
            "b64_json",
            "data",
            "result",
        ):
            if key in value:
                result = decode_image(
                    value[key]
                )

                if result:
                    return result

    if isinstance(value, list):
        for item in value:
            result = decode_image(
                item
            )

            if result:
                return result

    return None


def image_bytes(response):
    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if content_type.startswith("image/"):
        return response.content

    try:
        data = response.json()
    except ValueError:
        data = None

    if data is not None:
        result = decode_image(data)

        if result:
            return result

    result = decode_image(
        response.text
    )

    if result:
        return result

    raise ValueError(
        "Cloudflare did not return an image"
    )


def generate_images(story):
    for i, scene in enumerate(
        story["scenes"],
        1,
    ):
        output = (
            SCENES / f"scene_{i}.png"
        )

        for attempt in range(2):
            try:
                response = requests.post(
                    cf_url(IMAGE),
                    headers=HEADERS,
                    json={
                        "prompt": scene["visual"],
                        "num_steps": 4,
                    },
                    timeout=180,
                )

                print(
                    "Image",
                    i,
                    "HTTP:",
                    response.status_code,
                )

                response.raise_for_status()

                raw = image_bytes(
                    response
                )

                with Image.open(
                    BytesIO(raw)
                ) as image:
                    image.convert(
                        "RGB"
                    ).save(
                        output,
                        "PNG",
                    )

                with Image.open(
                    output
                ) as image:
                    image.verify()

                print(
                    "Saved",
                    output,
                )

                break

            except Exception as error:
                print(
                    "Image failed:",
                    error,
                )

                if attempt == 1:
                    raise

                time.sleep(4)


async def tts(text, path):
    communicator = edge_tts.Communicate(
        text,
        VOICE,
    )

    await communicator.save(
        str(path)
    )


def generate_audio(story):
    for i, scene in enumerate(
        story["scenes"],
        1,
    ):
        output = (
            AUDIO / f"scene_{i}.mp3"
        )

        print(
            "Voice",
            i,
        )

        try:
            asyncio.run(
                tts(
                    scene["narration"],
                    output,
                )
            )

        except Exception as error:
            raise RuntimeError(
                f"TTS failed for scene {i}: {error}"
            ) from error

        if (
            not output.exists()
            or output.stat().st_size < 1000
        ):
            raise RuntimeError(
                f"Invalid audio: {output}"
            )


def duration(path):
    output = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )

    return float(
        output.strip()
    )


def ass_time(seconds):
    centiseconds = max(
        1,
        int(
            round(
                seconds * 100
            )
        ),
    )

    hours = centiseconds // 360000

    minutes = (
        centiseconds % 360000
    ) // 6000

    seconds_value = (
        centiseconds % 6000
    ) // 100

    hundredths = (
        centiseconds % 100
    )

    return (
        f"{hours}:"
        f"{minutes:02d}:"
        f"{seconds_value:02d}."
        f"{hundredths:02d}"
    )


def make_ass(text, seconds, path):
    safe = (
        text
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
    )

    content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans Devanagari,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,170,-1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    content += (
        "Dialogue: 0,0:00:00.00,"
        f"{ass_time(seconds)},"
        "Default,,0,0,170,,"
        f"{safe}\n"
    )

    path.write_text(
        content,
        encoding="utf-8",
    )


def make_segment(i, narration):
    image = (
        SCENES / f"scene_{i}.png"
    )

    audio = (
        AUDIO / f"scene_{i}.mp3"
    )

    ass = (
        SEGMENTS / f"scene_{i}.ass"
    )

    output = (
        SEGMENTS / f"segment_{i}.mp4"
    )

    seconds = duration(
        audio
    )

    make_ass(
        narration,
        seconds,
        ass,
    )

    ass_path = (
        ass.as_posix()
        .replace(":", r"\:")
    )

    video_filter = (
        "[0:v]split=2[bg][fg];"
        "[bg]"
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "boxblur=18:2[blur];"
        "[fg]"
        "scale=900:900:"
        "force_original_aspect_ratio=decrease,"
        "pad=900:900:"
        "(ow-iw)/2:"
        "(oh-ih)/2:"
        "color=black@0[main];"
        "[blur][main]"
        "overlay=(W-w)/2:(H-h)/2,"
        f"subtitles={ass_path}"
        "[v]"
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(image),
            "-i",
            str(audio),
            "-filter_complex",
            video_filter,
            "-map",
            "[v]",
            "-map",
            "1:a:0",
            "-t",
            f"{seconds:.3f}",
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def create_segments(story):
    for i, scene in enumerate(
        story["scenes"],
        1,
    ):
        print(
            "Segment",
            i,
        )

        make_segment(
            i,
            scene["narration"],
        )


def join():
    concat = (
        SEGMENTS / "concat.txt"
    )

    final = (
        OUTPUT / "final_short.mp4"
    )

    lines = []

    for i in range(1, 7):
        path = (
            SEGMENTS
            / f"segment_{i}.mp4"
        )

        if not path.exists():
            raise FileNotFoundError(
                path
            )

        lines.append(
            f"file '{path.resolve().as_posix()}'"
        )

    concat.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )

    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "22",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            str(final),
        ]
    )


def verify():
    video = (
        OUTPUT / "final_short.mp4"
    )

    data = json.loads(
        run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(video),
            ]
        )
    )

    streams = data.get(
        "streams",
        [],
    )

    video_stream = next(
        (
            item
            for item in streams
            if item.get("codec_type")
            == "video"
        ),
        None,
    )

    audio_stream = next(
        (
            item
            for item in streams
            if item.get("codec_type")
            == "audio"
        ),
        None,
    )

    if not video_stream or not audio_stream:
        raise RuntimeError(
            "Video or audio stream missing"
        )

    if (
        int(video_stream.get("width", 0))
        != 1080
        or int(video_stream.get("height", 0))
        != 1920
    ):
        raise RuntimeError(
            "Wrong video resolution"
        )

    total = float(
        data["format"].get(
            "duration",
            0,
        )
    )

    if not 18 <= total <= 60:
        raise RuntimeError(
            f"Video duration is {total:.2f}s; "
            "expected 18-60s"
        )

    if (
        video_stream.get("codec_name")
        != "h264"
    ):
        raise RuntimeError(
            "Video is not H.264"

                if (
        video_stream.get("codec_name")
        != "h264"
    ):
        raise RuntimeError(
            "Video is not H.264"
        )
        
    print("Video verification passed!")


if __name__ == "__main__":
    print("Starting generation...")
    story_data = generate_story()
    generate_images(story_data)
    generate_audio(story_data)
    create_segments(story_data)
    join()
    verify()
    print("Short generated successfully!")
    
     

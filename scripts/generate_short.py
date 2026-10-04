import ast
import asyncio
import base64
import json
import os
import subprocess
import time
from io import BytesIO
from pathlib import Path

import edge_tts
import requests
from PIL import Image


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

SCENES = ROOT / "scenes"
AUDIO = ROOT / "audio"
SEGMENTS = ROOT / "segments"
OUTPUT = ROOT / "output"

for folder in (SCENES, AUDIO, SEGMENTS, OUTPUT):
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# CLOUDFLARE CONFIG
# ============================================================

CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID")

if not CF_TOKEN or not CF_ACCOUNT:
    raise RuntimeError(
        "Missing CLOUDFLARE_API_TOKEN or CLOUDFLARE_ACCOUNT_ID"
    )

LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
VOICE = "hi-IN-SwaraNeural"

HEADERS = {
    "Authorization": f"Bearer {CF_TOKEN}",
    "Content-Type": "application/json",
}


# ============================================================
# HELPERS
# ============================================================

def cf_url(model):
    return (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )


def run(cmd):
    print("\n>", " ".join(cmd))

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: " + " ".join(cmd)
        )

    return result.stdout


# ============================================================
# FALLBACK STORY
# ============================================================

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
            "emotional story",
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
                    "cinematic close-up, dramatic lighting, "
                    "strong emotional expression"
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
                    "walking beside an old tree at sunset, "
                    "curious expression, cinematic environment"
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
                    "watching a rapidly rising stream during heavy rain, "
                    "worried expression, dramatic cinematic scene"
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
                    "near rushing water, intense rain, "
                    "high tension cinematic scene"
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
                    "emotional farewell, cinematic ending"
                ),
            },
        ],
    }


# ============================================================
# STORY PARSING
# ============================================================

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

    text = data.strip()

    # Remove common markdown code fences.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    candidates = [text]

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:

        # JSON
        try:
            obj = json.loads(candidate)

            if (
                isinstance(obj, dict)
                and isinstance(obj.get("scenes"), list)
            ):
                return obj

        except (ValueError, TypeError):
            pass

        # Python-style dictionary
        try:
            obj = ast.literal_eval(candidate)

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


# ============================================================
# STORY NORMALIZATION
# ============================================================

def normalize(story):
    if not isinstance(story, dict):
        raise ValueError("Story is not a dictionary")

    scenes = story.get("scenes")

    if not isinstance(scenes, list):
        raise ValueError("Story scenes are missing")

    if len(scenes) != 6:
        raise ValueError(
            f"Story must contain exactly 6 scenes, got {len(scenes)}"
        )

    scene_types = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA",
    ]

    for index, scene in enumerate(scenes):
        if not isinstance(scene, dict):
            raise ValueError(
                f"Invalid scene {index + 1}"
            )

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual = str(
            scene.get("visual", "")
        ).strip()

        if not narration:
            raise ValueError(
                f"Scene {index + 1} has no narration"
            )

        if not visual:
            raise ValueError(
                f"Scene {index + 1} has no visual"
            )

        scene["type"] = scene_types[index]
        scene["narration"] = narration

        # Reinforce visual consistency.
        scene["visual"] = (
            visual
            + " Same white rabbit with blue scarf. "
            + "Consistent character appearance. "
            + "Vertical cinematic composition. "
            + "No text, no letters, no subtitles, no logo, no watermark."
        )

    title = str(
        story.get(
            "title",
            "एक कहानी जिसका अंत आपको चौंका देगा",
        )
    ).strip()

    description = str(
        story.get(
            "description",
            "एक छोटी कहानी जिसका अंत याद रहेगा। #Shorts",
        )
    ).strip()

    tags = story.get(
        "tags",
        ["shorts", "story", "hindi"],
    )

    if not isinstance(tags, list):
        tags = ["shorts", "story", "hindi"]

    tags = [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]

    if "shorts" not in [tag.lower() for tag in tags]:
        tags.insert(0, "shorts")

    story["title"] = title[:100]
    story["description"] = description
    story["tags"] = tags[:15]

    return story


# ============================================================
# SAVE STORY
# ============================================================

def save_story(story):
    story_json = ROOT / "story.json"
    story_txt = ROOT / "story.txt"

    story_json.write_text(
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

    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        lines.append(
            f"{index}. {scene['type']}"
        )
        lines.append(
            scene["narration"]
        )
        lines.append("")

    story_txt.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# GENERATE STORY
# ============================================================

def generate_story():
    prompt = """
Create a high-retention Hindi YouTube Shorts story.

Return ONLY valid JSON.

Use exactly 6 scenes in this exact order:

1. HOOK
2. SETUP
3. PROBLEM
4. TENSION
5. CLIMAX
6. ENDING_CTA

Requirements:

- Start with a powerful curiosity hook.
- The first sentence must immediately create curiosity.
- Create a clear character and situation.
- Introduce a real problem.
- Increase tension.
- Have a meaningful climax.
- Give the story a real ending.
- Do not stop suddenly.
- Add a short natural CTA only at the very end.
- Use spoken, natural Hindi.
- Avoid unnecessary English.
- Make the story emotionally engaging.
- Target approximately 25-55 seconds of narration.
- Keep every scene useful.
- Do not write explanations outside the JSON.

JSON format:

{
  "title": "short title",
  "description": "short description",
  "tags": ["shorts", "hindi story"],
  "scenes": [
    {
      "type": "HOOK",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    },
    {
      "type": "SETUP",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    },
    {
      "type": "PROBLEM",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    },
    {
      "type": "TENSION",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    },
    {
      "type": "CLIMAX",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    },
    {
      "type": "ENDING_CTA",
      "narration": "Hindi narration",
      "visual": "English visual prompt"
    }
  ]
}
"""

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert YouTube Shorts storyteller. "
                    "Write concise, emotional, high-retention stories."
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
                cf_url(LLM_MODEL),
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
                normalized = normalize(story)
                save_story(normalized)

                print("AI story generated successfully.")

                return normalized

            print("Could not parse AI story.")

        except Exception as error:
            print(
                "Story attempt failed:",
                repr(error),
            )

            if attempt < 2:
                time.sleep(3)

    print("Using fallback story.")

    story = normalize(
        fallback()
    )

    save_story(story)

    return story


# ============================================================
# IMAGE DECODING
# ============================================================

def decode_image(value):
    if isinstance(value, str):
        value = value.strip()

        if (
            value.startswith("data:image")
            and "," in value
        ):
            value = value.split(",", 1)[1]

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
            result = decode_image(item)

            if result:
                return result

    return None


def image_bytes(response):
    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    # Some image responses are returned directly.
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
        "Cloudflare did not return a usable image"
    )


# ============================================================
# GENERATE IMAGES
# ============================================================

def generate_images(story):
    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        output = (
            SCENES / f"scene_{index}.png"
        )

        success = False

        for attempt in range(2):
            try:
                print(
                    f"\nGenerating image {index}/6 "
                    f"(attempt {attempt + 1})..."
                )

                response = requests.post(
                    cf_url(IMAGE_MODEL),
                    headers=HEADERS,
                    json={
                        "prompt": scene["visual"],
                        "num_steps": 4,
                    },
                    timeout=180,
                )

                print(
                    "Image HTTP:",
                    response.status_code,
                )

                if not response.ok:
                    print(
                        "Cloudflare response:",
                        response.text[:1000],
                    )

                response.raise_for_status()

                raw = image_bytes(response)

                if not raw:
                    raise ValueError(
                        "Empty image response"
                    )

                with Image.open(
                    BytesIO(raw)
                ) as image:
                    rgb = image.convert("RGB")

                    # Keep the original image dimensions.
                    rgb.save(
                        output,
                        "PNG",
                    )

                # Verify that the PNG can be reopened.
                with Image.open(output) as image:
                    image.verify()

                print(
                    "Saved image:",
                    output,
                )

                success = True
                break

            except Exception as error:
                print(
                    "Image failed:",
                    repr(error),
                )

                if attempt < 1:
                    time.sleep(4)

        if not success:
            raise RuntimeError(
                f"Failed to generate image for scene {index}"
            )


# ============================================================
# TTS
# ============================================================

async def tts(text, path):
    communicator = edge_tts.Communicate(
        text,
        VOICE,
    )

    await communicator.save(
        str(path)
    )


def generate_audio(story):
    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        output = (
            AUDIO / f"scene_{index}.mp3"
        )

        print(
            f"\nGenerating voice {index}/6..."
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
                f"TTS failed for scene {index}: {error}"
            ) from error

        if (
            not output.exists()
            or output.stat().st_size < 1000
        ):
            raise RuntimeError(
                f"Invalid audio file: {output}"
            )

        print(
            "Saved audio:",
            output,
        )


# ============================================================
# AUDIO DURATION
# ============================================================

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

    value = output.strip()

    if not value:
        raise RuntimeError(
            f"Could not determine duration of {path}"
        )

    seconds = float(value)

    if seconds <= 0:
        raise RuntimeError(
            f"Invalid duration for {path}: {seconds}"
        )

    return seconds


# ============================================================
# ASS SUBTITLE TIME
# ============================================================

def ass_time(seconds):
    centiseconds = max(
        1,
        int(round(seconds * 100)),
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
    

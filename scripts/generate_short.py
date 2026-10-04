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

SCENES_DIR = ROOT / "scenes"
AUDIO_DIR = ROOT / "audio"
SEGMENTS_DIR = ROOT / "segments"
OUTPUT_DIR = ROOT / "output"

STORY_JSON = ROOT / "story.json"
STORY_TXT = ROOT / "story.txt"

for folder in (SCENES_DIR, AUDIO_DIR, SEGMENTS_DIR, OUTPUT_DIR):
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# CLOUDFLARE
# ============================================================

CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID")

if not CF_TOKEN or not CF_ACCOUNT:
    raise RuntimeError(
        "CLOUDFLARE_API_TOKEN and CLOUDFLARE_ACCOUNT_ID are required."
    )

LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
VOICE = "hi-IN-SwaraNeural"

HEADERS = {
    "Authorization": f"Bearer {CF_TOKEN}",
    "Content-Type": "application/json",
}


THEMES = [
    "an emotional rabbit story with a surprising ending",
    "a mysterious animal story with a strong twist",
    "a suspenseful bird rescue story with an emotional payoff",
    "a friendship story between two small forest animals",
    "an inspirational animal story where a small hero solves a big problem",
]


# ============================================================
# CLOUDFLARE URL
# ============================================================

def cf_url(model):
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )


# ============================================================
# COMMAND RUNNER
# ============================================================

def run_cmd(args, capture=True):
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )

    if result.returncode != 0:
        if capture:
            print(result.stdout)

        raise RuntimeError(
            f"Command failed: {' '.join(args)}"
        )

    return result.stdout if capture else ""


# ============================================================
# FALLBACK STORY
# ============================================================

def fallback_story():
    return {
        "title": "इस छोटे खरगोश ने अपनी जान की परवाह नहीं की",
        "description": (
            "एक छोटे खरगोश ने किसी और को बचाने के लिए "
            "अपनी जान जोखिम में डाल दी। अंत तक देखिए। #Shorts"
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
                    "रुको... इस छोटे खरगोश ने अपनी जान बचाने के बजाय "
                    "किसी और को बचाना क्यों चुना?"
                ),
                "visual": (
                    "A small cute white rabbit wearing a blue scarf "
                    "standing alone in a dark forest at dusk, looking "
                    "toward a mysterious light, cinematic close-up, "
                    "dramatic lighting, vertical composition"
                ),
            },
            {
                "type": "SETUP",
                "narration": (
                    "हर शाम वह खरगोश जंगल के किनारे एक पुराने पेड़ के "
                    "पास जाता था, जहाँ उसे हमेशा किसी की आवाज़ सुनाई देती थी।"
                ),
                "visual": (
                    "The same small white rabbit wearing the same blue "
                    "scarf walking beside an old tree at the forest edge "
                    "during sunset, curious expression, cinematic "
                    "storytelling, warm light, vertical composition"
                ),
            },
            {
                "type": "PROBLEM",
                "narration": (
                    "लेकिन एक दिन तेज़ बारिश शुरू हुई और पास की छोटी "
                    "नदी का पानी तेजी से बढ़ने लगा।"
                ),
                "visual": (
                    "The same small white rabbit wearing the same blue "
                    "scarf watching a rapidly rising stream during heavy "
                    "rain, worried expression, wet forest, dramatic storm, "
                    "cinematic vertical composition"
                ),
            },
            {
                "type": "TENSION",
                "narration": (
                    "तभी उसे झाड़ियों से एक नन्ही चिड़िया की आवाज़ सुनाई दी। "
                    "वह पानी के बीच फँसी हुई थी।"
                ),
                "visual": (
                    "The same small white rabbit wearing the same blue "
                    "scarf discovering a tiny frightened bird trapped near "
                    "rushing water and branches, intense rain, emotional "
                    "cinematic scene, vertical composition"
                ),
            },
            {
                "type": "CLIMAX",
                "narration": (
                    "खरगोश डर रहा था, फिर भी वह पानी में उतर गया और "
                    "चिड़िया को सुरक्षित किनारे तक ले आया।"
                ),
                "visual": (
                    "The same brave white rabbit wearing the same blue "
                    "scarf carefully helping a tiny bird reach a safe "
                    "riverbank while water rushes around them, heroic "
                    "emotional moment, cinematic lighting, vertical composition"
                ),
            },
            {
                "type": "ENDING_CTA",
                "narration": (
                    "अगली सुबह चिड़िया उड़ गई... लेकिन जाने से पहले उसने "
                    "अपने पंख से खरगोश का नीला स्कार्फ छुआ। ऐसी कहानी "
                    "पसंद आए तो फॉलो कर देना।"
                ),
                "visual": (
                    "The same white rabbit wearing the same blue scarf "
                    "sitting peacefully beside the rescued bird at sunrise, "
                    "warm golden light, emotional farewell, beautiful forest, "
                    "cinematic ending, vertical composition"
                ),
            },
        ],
    }


# ============================================================
# STORY PARSER
# ============================================================

def parse_story(value):
    if isinstance(value, dict):

        if isinstance(value.get("scenes"), list):
            return value

        for key in (
            "result",
            "response",
            "output",
            "data",
        ):
            if key in value:
                found = parse_story(value[key])

                if found:
                    return found

        return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    candidates = [text]

    cleaned = re.sub(
        r"^```(?:json|python)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()

    cleaned = cleaned.rstrip("`").strip()

    if cleaned not in candidates:
        candidates.append(cleaned)

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        candidates.append(
            text[start:end + 1]
        )

    for candidate in candidates:

        try:
            obj = json.loads(candidate)

            if (
                isinstance(obj, dict)
                and isinstance(obj.get("scenes"), list)
            ):
                return obj

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            pass

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

def normalize_story(story):

    if (
        not isinstance(story, dict)
        or len(story.get("scenes", [])) != 6
    ):
        raise ValueError(
            "Story must contain exactly 6 scenes."
        )

    types = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA",
    ]

    for index, scene in enumerate(
        story["scenes"]
    ):

        if not isinstance(scene, dict):
            raise ValueError(
                f"Scene {index + 1} is invalid."
            )

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual = str(
            scene.get("visual", "")
        ).strip()

        if not narration or not visual:
            raise ValueError(
                f"Scene {index + 1} is missing narration or visual."
            )

        scene["type"] = types[index]
        scene["narration"] = narration

        scene["visual"] = (
            visual
            + " Keep the same small cute white rabbit "
            + "with white fur and a blue scarf. "
            + "No text, letters, logo, or watermark."
        )

    if not re.search(
        r"रुको|लेकिन|क्या|सोचिए|देखिए|यकीन",
        story["scenes"][0]["narration"],
        re.IGNORECASE,
    ):
        story["scenes"][0]["narration"] = (
            "रुको... "
            + story["scenes"][0]["narration"]
        )

    if not re.search(
        r"फॉलो|follow|सब्सक्राइब|subscribe",
        story["scenes"][-1]["narration"],
        re.IGNORECASE,
    ):
        story["scenes"][-1]["narration"] += (
            " ऐसी कहानी पसंद आए तो फॉलो कर देना।"
        )

    story.setdefault(
        "title",
        "एक कहानी जिसका अंत आपको चौंका देगा",
    )

    story.setdefault(
        "description",
        "एक छोटी कहानी जिसका अंत याद रह जाएगा। #Shorts",
    )

    story.setdefault(
        "tags",
        [
            "shorts",
            "story",
            "hindi",
        ],
    )

    return story


# ============================================================
# SAVE STORY
# ============================================================

def save_story(story):

    STORY_JSON.write_text(
        json.dumps(
            story,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with STORY_TXT.open(
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            story["title"] + "\n\n"
        )

        for number, scene in enumerate(
            story["scenes"],
            1,
        ):
            file.write(
                f"{number}. {scene['type']}\n"
            )

            file.write(
                scene["narration"] + "\n\n"
            )


# ============================================================
# GENERATE STORY
# ============================================================

def generate_story():

    theme = random.choice(
        THEMES
    )

    prompt = f"""
Create a highly engaging Hindi YouTube Shorts story about:

{theme}

Requirements:

- Exactly 6 scenes.
- Scene 1 = powerful HOOK.
- Scene 2 = SETUP.
- Scene 3 = PROBLEM.
- Scene 4 = TENSION.
- Scene 5 = CLIMAX.
- Scene 6 = ENDING_CTA.
- The story must have a real ending.
- Do not leave the story unfinished.
- Use spoken Hindi.
- Suitable for a 25-55 second YouTube Short.
- Scene 1 must create curiosity.
- Scene 6 must have a natural short CTA.
- Use one consistent animal character.
- Visual prompts should be cinematic.
- No text inside images.
- Return ONLY valid JSON.

Format:

{{
  "title": "...",
  "description": "...",
  "tags": ["shorts", "story", "hindi"],
  "scenes": [
    {{
      "type": "HOOK",
      "narration": "...",
      "visual": "..."
    }},
    {{
      "type": "SETUP",
      "narration": "...",
      "visual": "..."
    }},
    {{
      "type": "PROBLEM",
      "narration": "...",
      "visual": "..."
    }},
    {{
      "type": "TENSION",
      "narration": "...",
      "visual": "..."
    }},
    {{
      "type": "CLIMAX",
      "narration": "...",
      "visual": "..."
    }},
    {{
      "type": "ENDING_CTA",
      "narration": "...",
      "visual": "..."
    }}
  ]
}}
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

    for attempt in range(1, 4):

        try:

            print(
                f"Generating story, attempt "
                f"{attempt}/3"
            )

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

            if story is None:
                raise ValueError(
                    "Could not parse a valid story "
                    "from Cloudflare."
                )

            story = normalize_story(
                story
            )

            save_story(
                story
            )

            return story

        except Exception as error:

            print(
                "Story attempt failed:",
                error,
            )

            if attempt < 3:
                time.sleep(3)

    print(
        "Using fallback story."
    )

    story = normalize_story(
        fallback_story()
    )

    save_story(
        story
    )

    return story


# ============================================================
# IMAGE DECODER
# ============================================================

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


def get_image_bytes(response):

    content_type = (
        response.headers
        .get(
            "content-type",
            "",
        )
        .lower()
    )

    if content_type.startswith(
        "image/"
    ):
        return response.content

    try:
        data = response.json()

    except ValueError:
        data = None

    if data is not None:

        result = decode_image(
            data
        )

        if result:
            return result

    result = decode_image(
        response.text
    )

    if result:
        return result

    raise ValueError(
        "Cloudflare did not return "
        "a usable image."
    )


# ============================================================
# GENERATE IMAGES
# ============================================================

def generate_images(story):

    for number, scene in enumerate(
        story["scenes"],
        1,
    ):

        output = (
            SCENES_DIR
            / f"scene_{number}.png"
        )

        for attempt in range(1, 3):

            try:

                print(
                    f"Generating image "
                    f"{number}/6, "
                    f"attempt {attempt}/2"
                )

                payload = {
                    "prompt": scene["visual"],
                    "num_steps": 4,
                }

                response = requests.post(
                    cf_url(IMAGE_MODEL),
                    headers=HEADERS,
                    json=payload,
                    timeout=180,
                )

                print(
                    "Image HTTP:",
                    response.status_code,
                )

                response.raise_for_status()

                raw = get_image_bytes(
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

                if attempt == 2:

                    raise RuntimeError(
                        f"Could not generate "
                        f"image {number}: "
                        f"{error}"
                    ) from error

                time.sleep(4)


# ============================================================
# TEXT TO SPEECH
# ============================================================

async def save_tts(
    text,
    path,
):

    communicator = edge_tts.Communicate(
        text,
        VOICE,
    )

    await communicator.save(
        str(path)
    )


def generate_audio(story):

    for number, scene in enumerate(
        story["scenes"],
        1,
    ):

        output = (
            AUDIO_DIR
            / f"scene_{number}.mp3"
        )

        print(
            f"Generating voice {number}/6"
        )

        try:

            asyncio.run(
                save_tts(
                    scene["narration"],
                    output,
                )
            )

        except Exception as error:

            raise RuntimeError(
                f"TTS failed for scene "
                f"{number}: {error}"
            ) from error

        if (
            not output.exists()
            or output.stat().st_size < 1000
        ):

            raise RuntimeError(
                f"Invalid audio file: "
                f"{output}"
            )


# ============================================================
# AUDIO DURATION
# ============================================================

def get_duration(path):

    output = run_cmd(
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

    value = float(
        output.strip()
    )

    if value <= 0:
        raise RuntimeError(
            f"Invalid duration: {path}"
        )

    return value


# ============================================================
# ASS SUBTITLES
# ============================================================

def ass_time(s

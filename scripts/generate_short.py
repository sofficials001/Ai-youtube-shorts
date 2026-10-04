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


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

SCENES_DIR = ROOT / "scenes"
AUDIO_DIR = ROOT / "audio"
SEGMENTS_DIR = ROOT / "segments"
OUTPUT_DIR = ROOT / "output"

STORY_JSON = ROOT / "story.json"
STORY_TXT = ROOT / "story.txt"

for folder in [
    SCENES_DIR,
    AUDIO_DIR,
    SEGMENTS_DIR,
    OUTPUT_DIR,
]:
    folder.mkdir(parents=True, exist_ok=True)


# ============================================================
# CLOUDFLARE SETTINGS
# ============================================================

CLOUDFLARE_API_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CLOUDFLARE_ACCOUNT_ID = os.getenv("CLOUDFLARE_ACCOUNT_ID")

if not CLOUDFLARE_API_TOKEN:
    raise RuntimeError("CLOUDFLARE_API_TOKEN is missing.")

if not CLOUDFLARE_ACCOUNT_ID:
    raise RuntimeError("CLOUDFLARE_ACCOUNT_ID is missing.")


LLM_MODEL = "@cf/meta/llama-3.2-3b-instruct"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"

VOICE = "hi-IN-SwaraNeural"

CF_HEADERS = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json",
}


# ============================================================
# STORY THEMES
# ============================================================

THEMES = [
    "an emotional rabbit story with a surprising ending",
    "a mysterious rabbit story with a powerful hook",
    "a suspenseful bird story with an emotional payoff",
    "a short animal friendship story with a twist",
    "an inspirational animal story where a small character solves a big problem",
    "a mysterious forest animal story that keeps viewers curious until the ending",
]


# ============================================================
# CLOUDFLARE URL
# ============================================================

def cloudflare_url(model):
    return (
        f"https://api.cloudflare.com/client/v4/accounts/"
        f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{model}"
    )


# ============================================================
# COMMAND RUNNER
# ============================================================

def run_command(command):
    print("Running:", " ".join(command))

    result = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}"
        )

    return result.stdout


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
            "emotional story",
            "animal story",
        ],
        "scenes": [
            {
                "type": "HOOK",
                "narration": (
                    "रुको... इस छोटे से खरगोश ने अपनी जान बचाने के बजाय "
                    "किसी और को बचाना क्यों चुना?"
                ),
                "visual": (
                    "A small cute white rabbit wearing a blue scarf "
                    "standing alone in a dark forest at dusk, looking toward "
                    "a mysterious light, cinematic close-up, emotional eyes, "
                    "dramatic lighting, vertical composition"
                ),
            },
            {
                "type": "SETUP",
                "narration": (
                    "हर शाम वह खरगोश जंगल के किनारे एक पुराने पेड़ के पास "
                    "जाता था, जहाँ उसे हमेशा किसी की आवाज़ सुनाई देती थी।"
                ),
                "visual": (
                    "The same small white rabbit wearing the same blue scarf "
                    "walking beside an old tree at the forest edge during "
                    "sunset, curious expression, cinematic storytelling, "
                    "warm light, vertical composition"
                ),
            },
            {
                "type": "PROBLEM",
                "narration": (
                    "लेकिन एक दिन अचानक तेज़ बारिश शुरू हुई और पास की "
                    "छोटी नदी का पानी तेजी से बढ़ने लगा।"
                ),
                "visual": (
                    "The same small white rabbit wearing the same blue scarf "
                    "watching a rapidly rising stream during heavy rain, "
                    "worried expression, wet forest, dramatic storm, "
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
                    "The same white rabbit wearing the same blue scarf "
                    "discovering a tiny frightened bird trapped near "
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
                    "The same brave white rabbit wearing the same blue scarf "
                    "carefully helping a tiny bird reach a safe riverbank "
                    "while water rushes around them, heroic emotional moment, "
                    "cinematic lighting, vertical composition"
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
# PARSE AI STORY
# ============================================================

def extract_story_object(value):
    if isinstance(value, dict):

        if "scenes" in value:
            return value

        for key in [
            "result",
            "response",
            "output",
            "data",
        ]:
            if key in value:
                found = extract_story_object(value[key])

                if found:
                    return found

        return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    candidates = [
        text,
        re.sub(
            r"^```(?:json|python)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip().rstrip("`").strip(),
    ]

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        candidates.append(text[start:end + 1])

    for candidate in candidates:

        try:
            parsed = json.loads(candidate)

            if isinstance(parsed, dict) and "scenes" in parsed:
                return parsed

        except (json.JSONDecodeError, TypeError):
            pass

        try:
            parsed = ast.literal_eval(candidate)

            if isinstance(parsed, dict) and "scenes" in parsed:
                return parsed

        except (ValueError, SyntaxError, TypeError):
            pass

    return None


# ============================================================
# STORY VALIDATION
# ============================================================

def improve_story_structure(story):

    scenes = story.get("scenes")

    if not isinstance(scenes, list):
        raise ValueError("Story does not contain a scenes list.")

    if len(scenes) != 6:
        raise ValueError(
            f"Expected exactly 6 scenes, got {len(scenes)}."
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
                f"Scene {index + 1} is not a valid object."
            )

        scene["type"] = scene_types[index]

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual = str(
            scene.get("visual", "")
        ).strip()

        if not narration:
            raise ValueError(
                f"Scene {index + 1} has no narration."
            )

        if not visual:
            raise ValueError(
                f"Scene {index + 1} has no visual prompt."
            )

        scene["narration"] = narration
        scene["visual"] = visual

    hook = scenes[0]["narration"]

    if not re.search(
        r"अगर|रुको|लेकिन|क्या|सोचिए|यकीन|देखिए",
        hook,
        flags=re.IGNORECASE,
    ):
        scenes[0]["narration"] = (
            "रुको... " + hook
        )

    ending = scenes[-1]["narration"]

    if not re.search(
        r"फॉलो|follow|सब्सक्राइब|subscribe",
        ending,
        flags=re.IGNORECASE,
    ):
        scenes[-1]["narration"] = (
            ending + " ऐसी कहानी पसंद आए तो फॉलो कर देना।"
        )

    story["scenes"] = scenes

    if not story.get("title"):
        story["title"] = "एक कहानी जिसका अंत आपको चौंका देगा"

    if not story.get("description"):
        story["description"] = (
            "एक छोटी कहानी जिसका अंत याद रह जाएगा। #Shorts"
        )

    if not story.get("tags"):
        story["tags"] = [
            "shorts",
            "story",
            "hindi",
        ]

    return story


# ============================================================
# VISUAL CONSISTENCY
# ============================================================

def prepare_visual_prompts(story):

    consistency = (
        " Keep the exact same main character design in every scene: "
        "a small cute white rabbit with soft white fur and a blue scarf. "
        "No text, no letters, no subtitles, no logos, no watermark."
    )

    for scene in story["scenes"]:

        visual = scene["visual"].strip()

        if consistency not in visual:
            visual += consistency

        scene["visual"] = visual


# ============================================================
# SAVE STORY
# ============================================================

def save_story(story):

    with open(
        STORY_JSON,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            story,
            file,
            ensure_ascii=False,
            indent=2,
        )

    with open(
        STORY_TXT,
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            story["title"] + "\n\n"
        )

        for number, scene in enumerate(
            story["scenes"],
            start=1,
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

    theme = random.choice(THEMES)

    prompt = f"""
Create a highly engaging Hindi YouTube Shorts story.

Theme:
{theme}

STRICT REQUIREMENTS:

1. Exactly 6 scenes.
2. Scene 1 must be a powerful HOOK.
3. Scene 2 must establish the situation.
4. Scene 3 must introduce the main problem.
5. Scene 4 must increase tension.
6. Scene 5 must contain the climax/payoff.
7. Scene 6 must contain a real ending plus a short natural CTA.
8. The story must actually finish.
9. Do not leave the ending unfinished.
10. Keep the narration suitable for a 25-55 second short.
11. Use spoken Hindi.
12. Use one consistent animal character.
13. Visual prompts must be cinematic.
14. No text inside generated images.
15. Return ONLY valid JSON.

Required JSON:

{{
  "title": "Hindi title",
  "description": "short description",
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
                    "You are a professional YouTube Shorts "
                    "story writer focused on viewer retention."
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
                f"Generating story "
                f"(attempt {attempt}/3)..."
            )

            response = requests.post(
                cloudflare_url(LLM_MODEL),
                headers=CF_HEADERS,
                json=payload,
                timeout=120,
            )

            print(
                "Cloudflare story HTTP status:",
                response.status_code,
            )

            response.raise_for_status()

            data = response.json()

            story = extract_story_object(data)

            if story is None:
                print(
                    "Could not parse Cloudflare story."
                )

                print(
                    str(data)[:3000]
                )

                raise ValueError(
                    "No valid story object found."
                )

            story = improve_story_structure(
                story
            )

            prepare_visual_prompts(
                story
            )

            save_story(story)

            print(
                "Story generated successfully."
            )

            return story

        except Exception as error:

            print(
                "Story generation failed:",
                error,
            )

            if attempt < 3:
                time.sleep(3)

    print(
        "Cloudflare story generation failed."
    )

    print(
        "Using fallback story."
    )

    story = fallback_story()

    prepare_visual_prompts(
        story
    )

    save_story(
        story
    )

    return story


# ============================================================
# IMAGE RESPONSE DECODER
# ============================================================

def decode_image_value(value):

    if isinstance(value, str):

        value = value.strip()

        if value.startswith(
            "data:image"
        ):

            if "," in value:
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

        for key in [
            "image",
            "b64_json",
            "data",
            "result",
        ]:

            if key in value:

                decoded = decode_image_value(
                    value[key]
                )

                if decoded:
                    return decoded

    if isinstance(value, list):

        for item in value:

            decoded = decode_image_value(
                item
            )

            if decoded:
                return decoded

    return None


def extract_image_bytes(response):

    content_type = (
        response.headers
        .get(
            "content-type",
            "",
        )
        .lower()
    )

    if "image/" in content_type:
        return response.content

    try:
        data = response.json()
    except ValueError:
        data = None

    if data is not None:

        decoded = decode_image_value(
            data
        )

        if decoded:
            return decoded

    text = response.text.strip()

    decoded = decode_image_value(
        text
    )

    if decoded:
        return decoded

    raise ValueError(
        "Cloudflare did not return a usable image."
    )


# ============================================================
# IMAGE VALIDATION
# ============================================================

def validate_image(path):

    with Image.open(path) as image:
        image.verify()

    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.save(
            path,
            format="PNG",
        )


# ============================================================
# GENERATE IMAGES
# ============================================================

def generate_images(story):

    for number, scene in enumerate(
        story["scenes"],
        start=1,
    ):

        output_path = (
            SCENES_DIR /
            f"scene_{number}.png"
        )

        success = False

        for attempt in range(1, 3):

            try:

                print(
                    f"Generating image "
                    f"{number}/6 "
                    f"(attempt {attempt}/2)..."
                )

                payload = {
                    "prompt": scene["visual"],
                    "num_steps": 4,
                }

                response = requests.post(
                    cloudflare_url(
                        IMAGE_MODEL
                    ),
                    headers=CF_HEADERS,
                    json=payload,
                    timeout=180,
                )

                print(
                    "Image HTTP status:",
                    response.status_code,
                )

                response.raise_for_status()

                image_bytes = extract_image_bytes(
                    response
                )

                with Image.open(
                    BytesIO(image_bytes)
                ) as image:

                    image = image.convert(
                        "RGB"
                    )

                    image.save(
                        output_path,
                        format="PNG",
                    )

                validate_image(
                    output_path
                )

                print(
                    f"Saved {output_path}"
                )

                success = True
                break

            except Exception as error:

                print(
                    f"Image {number} failed:",
                    error,
                )

                if attempt < 2:
                    time.sleep(4)

        if not success:

            raise RuntimeError(

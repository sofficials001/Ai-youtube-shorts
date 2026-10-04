import ast
import asyncio
import base64
import json
import os
import random
import re
import subprocess
import sys
import textwrap
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

ROOT = Path(__file__).resolve().parents[1]

SCENES_DIR = ROOT / "scenes"
AUDIO_DIR = ROOT / "audio"
SEGMENTS_DIR = ROOT / "segments"
OUTPUT_DIR = ROOT / "output"

STORY_JSON = ROOT / "story.json"
STORY_TXT = ROOT / "story.txt"


# ============================================================
# ENVIRONMENT
# ============================================================

CLOUDFLARE_TOKEN = os.environ.get(
    "CLOUDFLARE_API_TOKEN",
    ""
).strip()

CLOUDFLARE_ACCOUNT_ID = os.environ.get(
    "CLOUDFLARE_ACCOUNT_ID",
    ""
).strip()


if not CLOUDFLARE_TOKEN:
    raise RuntimeError(
        "CLOUDFLARE_API_TOKEN is missing."
    )

if not CLOUDFLARE_ACCOUNT_ID:
    raise RuntimeError(
        "CLOUDFLARE_ACCOUNT_ID is missing."
    )


# ============================================================
# MODELS
# ============================================================

LLM_MODEL = (
    "@cf/meta/llama-3.2-3b-instruct"
)

IMAGE_MODEL = (
    "@cf/black-forest-labs/flux-1-schnell"
)

VOICE = "hi-IN-SwaraNeural"


# ============================================================
# CLOUDFLARE ENDPOINTS
# ============================================================

LLM_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{LLM_MODEL}"
)

IMAGE_URL = (
    f"https://api.cloudflare.com/client/v4/accounts/"
    f"{CLOUDFLARE_ACCOUNT_ID}/ai/run/{IMAGE_MODEL}"
)

CF_HEADERS = {
    "Authorization": f"Bearer {CLOUDFLARE_TOKEN}",
    "Content-Type": "application/json",
}


# ============================================================
# RANDOM STORY THEMES
# ============================================================

THEMES = [
    "एक छोटे खरगोश को जंगल में एक घायल चिड़िया मिलती है और उसे घर पहुंचाना पड़ता है",

    "एक छोटे खरगोश को अपने दोस्त की एक ऐसी चिट्ठी मिलती है जिससे वह तुरंत जंगल की ओर निकल पड़ता है",

    "एक छोटा खरगोश एक अजनबी की मदद करता है और बदले में उसे एक अनोखा रहस्य पता चलता है",

    "एक छोटा खरगोश शाम होने से पहले अपने खोए हुए दोस्त को ढूंढने निकलता है",

    "एक छोटा खरगोश अपने डर के बावजूद एक जरूरी काम पूरा करने जंगल के अंदर जाता है",

    "एक छोटे खरगोश को लगता है कि उसका सबसे अच्छा दोस्त उससे नाराज़ है लेकिन आखिरी में सच्चाई सामने आती है",

    "एक छोटा खरगोश बारिश शुरू होने से पहले एक छोटी चिड़िया के बच्चे को सुरक्षित जगह पहुंचाना चाहता है",

    "एक छोटा खरगोश जंगल में चमकती हुई रोशनी का पीछा करता है और एक दिल छू लेने वाली चीज़ खोजता है",
]


# ============================================================
# SAFE FALLBACK STORY
# ============================================================

FALLBACK_STORY = {
    "title": "खरगोश ने जंगल में क्या देख लिया? 🐰",

    "description": (
        "एक छोटे खरगोश की दिल छू लेने वाली कहानी, "
        "जिसमें एक छोटी सी मदद एक बड़ी दोस्ती बन जाती है।"
    ),

    "tags": [
        "shorts",
        "hindi story",
        "rabbit",
        "emotional story",
        "AI story"
    ],

    "scenes": [

        {
            "scene": 1,
            "role": "HOOK",
            "narration": (
                "जंगल के बीच खरगोश को कुछ ऐसा मिला, "
                "जिसे देखकर वह अचानक रुक गया!"
            ),
            "visual_prompt": (
                "the rabbit suddenly discovering a tiny lost bird "
                "under a large tree, surprised emotional expression, "
                "dramatic forest reveal"
            ),
        },

        {
            "scene": 2,
            "role": "SETUP",
            "narration": (
                "एक छोटी चिड़िया रास्ता भूल गई थी और "
                "अपने घर का रास्ता बिल्कुल नहीं पहचान पा रही थी।"
            ),
            "visual_prompt": (
                "the rabbit carefully comforting a tiny frightened "
                "bird in a peaceful forest clearing"
            ),
        },

        {
            "scene": 3,
            "role": "PROBLEM",
            "narration": (
                "खरगोश उसे घर पहुंचाने निकला, "
                "लेकिन जंगल के सभी रास्ते एक जैसे लग रहे थे।"
            ),
            "visual_prompt": (
                "the rabbit and tiny bird standing at a confusing "
                "forest crossroads with many similar paths"
            ),
        },

        {
            "scene": 4,
            "role": "TENSION",
            "narration": (
                "शाम तेजी से होने लगी, तभी दूर "
                "एक छोटी सी रोशनी दिखाई दी।"
            ),
            "visual_prompt": (
                "the rabbit bravely following a tiny warm glowing "
                "light through the forest at dusk, suspenseful "
                "but family friendly"
            ),
        },

        {
            "scene": 5,
            "role": "CLIMAX",
            "narration": (
                "वही रोशनी चिड़िया के घर की थी, "
                "और खरगोश ने आखिरकार उसे सही जगह पहुंचा दिया।"
            ),
            "visual_prompt": (
                "the rabbit guiding the happy tiny bird to a cozy "
                "nest glowing warmly beneath a large tree at sunset"
            ),
        },

        {
            "scene": 6,
            "role": "ENDING_CTA",
            "narration": (
                "चिड़िया ने खरगोश को धन्यवाद दिया और दोनों "
                "हमेशा के लिए दोस्त बन गए। ऐसी कहानी पसंद आई "
                "तो चैनल को subscribe करना मत भूलना!"
            ),
            "visual_prompt": (
                "the rabbit and tiny bird happily together beside "
                "the cozy nest under a beautiful sunset, warm "
                "emotional ending"
            ),
        },

    ],
}


# ============================================================
# CLEAN MODEL TEXT
# ============================================================

def clean_model_text(value):

    if not isinstance(value, str):
        return value

    value = value.strip()

    value = re.sub(
        r"^```(?:json|python)?\s*",
        "",
        value,
        flags=re.IGNORECASE
    )

    value = re.sub(
        r"\s*```$",
        "",
        value
    )

    return value.strip()


# ============================================================
# PARSE STORY
#
# Handles:
# - normal JSON
# - Python dict strings with single quotes
# - markdown fences
# - extra text around object
# ============================================================

def parse_story_payload(data):

    result = data.get("result")

    if result is None:
        raise ValueError(
            "Cloudflare returned no result."
        )

    if isinstance(result, dict):

        if "response" in result:
            result = result["response"]

        else:
            return result

    if isinstance(result, dict):
        return result

    if not isinstance(result, str):
        raise ValueError(
            f"Unexpected result type: "
            f"{type(result).__name__}"
        )

    text = clean_model_text(result)

    # --------------------------------------------------------
    # 1. Normal JSON
    # --------------------------------------------------------

    try:
        parsed = json.loads(text)

        if isinstance(parsed, dict):
            return parsed

    except json.JSONDecodeError:
        pass

    # --------------------------------------------------------
    # 2. Python dictionary representation
    # --------------------------------------------------------

    try:
        parsed = ast.literal_eval(text)

        if isinstance(parsed, dict):
            return parsed

    except (ValueError, SyntaxError):
        pass

    # --------------------------------------------------------
    # 3. Extract object from surrounding text
    # --------------------------------------------------------

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:

        candidate = text[
            start:end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        try:
            parsed = ast.literal_eval(
                candidate
            )

            if isinstance(parsed, dict):
                return parsed

        except (ValueError, SyntaxError):
            pass

    raise ValueError(
        "Could not parse AI story response."
    )


# ============================================================
# VALIDATE STORY
# ============================================================

def validate_story(story):

    if not isinstance(story, dict):
        raise ValueError(
            "Story is not a dictionary."
        )

    required_fields = [
        "title",
        "description",
        "tags",
        "scenes"
    ]

    for field in required_fields:

        if field not in story:
            raise ValueError(
                f"Missing story field: {field}"
            )

    scenes = story["scenes"]

    if not isinstance(scenes, list):
        raise ValueError(
            "scenes must be a list."
        )

    if len(scenes) != 6:
        raise ValueError(
            f"Expected 6 scenes, got {len(scenes)}."
        )

    roles = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA"
    ]

    for index, scene in enumerate(
        scenes
    ):

        if not isinstance(
            scene,
            dict
        ):
            raise ValueError(
                f"Scene {index + 1} "
                f"is not a dictionary."
            )

        for field in [
            "scene",
            "role",
            "narration",
            "visual_prompt"
        ]:

            if field not in scene:
                raise ValueError(
                    f"Scene {index + 1} "
                    f"missing {field}."
                )

        scene["scene"] = index + 1
        scene["role"] = roles[index]

        scene["narration"] = str(
            scene["narration"]
        ).strip()

        scene["visual_prompt"] = str(
            scene["visual_prompt"]
        ).strip()

        if not scene["narration"]:
            raise ValueError(
                f"Scene {index + 1} "
                f"has empty narration."
            )

        if not scene["visual_prompt"]:
            raise ValueError(
                f"Scene {index + 1} "
                f"has empty visual prompt."
            )

    story["title"] = str(
        story["title"]
    ).strip()

    story["description"] = str(
        story["description"]
    ).strip()

    if not story["title"]:
        raise ValueError(
            "Story title is empty."
        )

    if not story["description"]:
        raise ValueError(
            "Story description is empty."
        )

    if not isinstance(
        story["tags"],
        list
    ):
        story["tags"] = []

    story["tags"] = [
        str(tag).strip()
        for tag in story["tags"]
        if str(tag).strip()
    ]


# ============================================================
# FORCE A HOOK AND CTA
# ============================================================

def improve_story_structure(story):

    first = story["scenes"][0]

    hook_words = (
        "क्या",
        "लेकिन",
        "अचानक",
        "ऐसा",
        "जो",
        "देखकर",
        "पता",
        "रहस्य"
    )

    first_text = first["narration"]

    has_hook_word = any(
        word in first_text
        for word in hook_words
    )

    if not has_hook_word:

        first["narration"] = (
            "रुको! खरगोश ने जो देखा, "
            "उसकी उसे बिल्कुल उम्मीद नहीं थी। "
            + first_text
        )

    ending = story["scenes"][5]

    cta_words = (
        "subscribe",
        "सब्सक्राइब",
        "चैनल",
        "जुड़े रहना",
        "पसंद आई"
    )

    ending_text = ending["narration"]

    has_cta = any(
        word.lower() in ending_text.lower()
        for word in cta_words
    )

    if not has_cta:

        ending["narration"] = (
            ending_text
            + " ऐसी कहानी पसंद आई तो "
              "चैनल को subscribe करना मत भूलना!"
        )


# ============================================================
# VISUAL CONSISTENCY
# ============================================================

def prepare_visual_prompts(story):

    consistency = (
        "same main character in every scene: "
        "a small cute white rabbit wearing a "
        "small blue scarf, consistent face, "
        "consistent fur, consistent body proportions"
    )

    rules = (
        ", family-friendly, cinematic 3D animated "
        "film style, highly detailed, expressive "
        "characters, beautiful lighting, vertical "
        "storytelling composition, no text, no letters, "
        "no captions, no subtitles, no watermark, "
        "no logo, no brand, non-graphic"
    )

    for scene in story["scenes"]:

        scene["visual_prompt"] = (
            consistency
            + ", "
            + scene["visual_prompt"]
            + rules
        )


# ============================================================
# SAVE STORY
# ============================================================

def save_story(story):

    STORY_JSON.write_text(
        json.dumps(
            story,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    lines = []

    lines.append("TITLE:")
    lines.append(
        story["title"]
    )

    lines.append("")
    lines.append("DESCRIPTION:")
    lines.append(
        story["description"]
    )

    lines.append("")
    lines.append("TAGS:")
    lines.append(
        ", ".join(
            story["tags"]
        )
    )

    lines.append("")

    for scene in story["scenes"]:

        lines.append(
            f"SCENE {scene['scene']} "
            f"({scene['role']})"
        )

        lines.append(
            scene["narration"]
        )

        lines.append("")
        lines.append("VISUAL:")
        lines.append(
            scene["visual_prompt"]
        )

        lines.append("")

    STORY_TXT.write_text(
        "\n".join(lines),
        encoding="utf-8"
    )


# ============================================================
# GENERATE STORY WITH RETRIES
# ============================================================

def generate_story():

    theme = random.choice(
        THEMES
    )

    system_prompt = """
You are a professional Hindi YouTube Shorts story writer.

Create one ORIGINAL fictional story for a 25-40 second Short.

The story MUST have this exact structure:

SCENE 1 = HOOK
SCENE 2 = SETUP
SCENE 3 = PROBLEM
SCENE 4 = TENSION
SCENE 5 = CLIMAX
SCENE 6 = ENDING_CTA

HOOK:
The first sentence must create immediate curiosity.
Do NOT begin with a boring introduction.

SETUP:
Quickly explain who the character is and what is happening.

PROBLEM:
Introduce one clear problem.

TENSION:
Make the viewer worry about what happens next.

CLIMAX:
Give a real payoff or turning point.

ENDING:
Actually finish the story.
Do not end suddenly or leave the story incomplete.

CTA:
Use one very short natural subscribe CTA at the end.

Narration:
- Natural Hindi.
- Short punchy sentences.
- Easy to speak.
- No filler.
- Approximately 25-40 seconds total.

Main character:
A small cute white rabbit wearing a small blue scarf.

Keep the character visually consistent in every scene.

Family friendly:
- No graphic violence.
- No real people.
- No copyrighted characters.
- No brands.
- No logos.

Return ONLY one object containing:
title
description
tags
scenes

The scenes array must contain exactly 6 objects.

Each scene object must contain:
scene
role
narration
visual_prompt

visual_prompt must be in English.

Do not put subtitles, captions, text, letters, logos or watermarks in visual_prompt.

Do not use Markdown code fences.
""".strip()

    user_prompt = (
        "Create the Short around this theme:\n"
        + theme
    )

    for attempt in range(1, 4):

        print(
            f"Story generation attempt "
            f"{attempt}/3"
        )

        payload = {
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],

            "max_tokens": 1800,
            "temperature": 0.7,
            "top_p": 0.9
        }

        try:

            response = requests.post(
                LLM_URL,
                headers=CF_HEADERS,
                json=payload,
                timeout=180
            )

            print(
                "Cloudflare story HTTP:",
                response.status_code
            )

            response.raise_for_status()

            data = response.json()

            if not data.get(
                "success"
            ):
                raise ValueError(
                    f"Cloudflare error: {data}"
                )

            story = parse_story_payload(
                data
            )

            validate_story(
                story
            )

            improve_story_structure(
                story
            )

            validate_story(
                story
            )

            prepare_visual_prompts(
                story
            )

            return story

        except Exception as exc:

            print(
                "Story attempt failed:",
                repr(exc)
            )

            if attempt < 3:
                time.sleep(2)

    print(
        "AI story generation failed "
        "three times."
    )

    print(
        "Using safe fallback story."
    )

    story = json.loads(
        json.dumps(
            FALLBACK_STORY,
            ensure_ascii=False
        )
    )

    validate_story(
        story
    )

    improve_story_structure(
        story
    )

    prepare_visual_prompts(
        story
    )

    return story


# ============================================================
# DECODE CLOUDFLARE IMAGE
# ============================================================

def decode_cloudflare_image(
    data
):

    result = data.get(
        "result"
    )

    if isinstance(
        result,
        dict
    ):

        image = result.get(
            "image"
        )

        if image:
            return image

    if isinstance(
        result,
        str
    ):
        return result

    raise ValueError(
        "No Base64 image found."
    )


# ============================================================
# GENERATE SIX AI IMAGES
# ============================================================

def generate_images(
    story
):

    for scene in story["scenes"]:

        number = int(
            scene["scene"]
        )

        output = (
            SCENES_DIR
            / f"scene{number}.png"
        )

        print("")
        print(
            f"Generating image "
            f"{number}/6..."
        )

        payload = {
            "prompt": " ".join(
                scene["visual_prompt"].split()
            ),
            "steps": 4
        }

        success = False

        for attempt in range(1, 3):

            try:

                response = requests.post(
                    IMAGE_URL,
                    headers=CF_HEADERS,
                    json=payload,
                    timeout=180
                )

                print(
                    "Cloudflare image HTTP:",
                    response.status_code
                )

                response.r

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


def cf_url(model):
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        f"{CF_ACCOUNT}/ai/run/{model}"
    )


# ============================================================
# COMMAND RUNNER
# ============================================================

def run_command(args):
    print("$ " + " ".join(args))

    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.stdout:
        print(result.stdout)

    if result.returncode != 0:
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
                    "रुको... इस छोटे खरगोश ने अपनी जान बचाने "
                    "के बजाय किसी और को बचाना क्यों चुना?"
                ),

                "visual": (
                    "A cute white rabbit wearing a blue scarf "
                    "standing alone in a dark forest at dusk, "
                    "dramatic cinematic close-up, emotional expression."
                ),
            },

            {
                "type": "SETUP",

                "narration": (
                    "हर शाम वह खरगोश जंगल के किनारे एक पुराने "
                    "पेड़ के पास जाता था, जहाँ उसे एक अजीब आवाज़ "
                    "सुनाई देती थी।"
                ),

                "visual": (
                    "The same cute white rabbit wearing a blue scarf "
                    "walking beside an old tree at sunset, "
                    "mysterious forest, cinematic lighting."
                ),
            },

            {
                "type": "PROBLEM",

                "narration": (
                    "एक दिन तेज़ बारिश शुरू हुई और पास की नदी "
                    "का पानी तेजी से बढ़ने लगा।"
                ),

                "visual": (
                    "The same white rabbit wearing a blue scarf "
                    "watching a rapidly rising river during heavy rain, "
                    "worried expression, dramatic cinematic scene."
                ),
            },

            {
                "type": "TENSION",

                "narration": (
                    "तभी उसे झाड़ियों से एक नन्ही चिड़िया की "
                    "आवाज़ सुनाई दी। वह पानी के बीच फँसी थी।"
                ),

                "visual": (
                    "The same white rabbit wearing a blue scarf "
                    "discovering a tiny frightened bird trapped "
                    "near rushing water, intense rain, "
                    "high tension cinematic scene."
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
                    "helping a tiny bird reach a safe riverbank "
                    "while water rushes around them, "
                    "heroic cinematic moment."
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
                    "The same white rabbit wearing a blue scarf "
                    "beside the rescued bird at sunrise, "
                    "warm golden light, emotional farewell, "
                    "cinematic ending."
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
        ):

            if key in value:

                found = parse_story(
                    value[key]
                )

                if found:
                    return found

        return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    if text.startswith("```"):

        lines = text.splitlines()

        if (
            lines
            and lines[0].strip().startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    candidates = [text]

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
                and isinstance(
                    obj.get("scenes"),
                    list,
                )
            ):
                return obj

        except (
            ValueError,
            TypeError,
        ):
            pass

        try:

            obj = ast.literal_eval(candidate)

            if (
                isinstance(obj, dict)
                and isinstance(
                    obj.get("scenes"),
                    list,
                )
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

    scenes = (
        story.get("scenes")
        if isinstance(story, dict)
        else None
    )

    if (
        not isinstance(scenes, list)
        or len(scenes) != 6
    ):
        raise ValueError(
            "Story must contain exactly 6 scenes"
        )

    scene_types = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA",
    ]

    for index, scene in enumerate(
        scenes
    ):

        if not isinstance(scene, dict):

            raise ValueError(
                f"Invalid scene {index + 1}"
            )

        narration = str(
            scene.get(
                "narration",
                "",
            )
        ).strip()

        visual = str(
            scene.get(
                "visual",
                "",
            )
        ).strip()

        if not narration:

            raise ValueError(
                f"Scene {index + 1} "
                "has no narration"
            )

        if not visual:

            raise ValueError(
                f"Scene {index + 1} "
                "has no visual"
            )

        scene["type"] = scene_types[index]

        scene["narration"] = narration

        scene["visual"] = (
            visual
            + " Keep the same character appearance "
            + "throughout all scenes. "
            + "Vertical cinematic composition. "
            + "No text, no letters, no logo, "
            + "no watermark."
        )

    story["title"] = str(
        story.get(
            "title",
            "एक कहानी जिसका अंत आपको चौंका देगा",
        )
    ).strip()[:100]

    story["description"] = str(
        story.get(
            "description",
            "एक छोटी कहानी जिसका अंत याद रहेगा। #Shorts",
        )
    ).strip()

    tags = story.get(
        "tags",
        [
            "shorts",
            "hindi",
            "story",
        ],
    )

    if not isinstance(tags, list):

        tags = [
            "shorts",
            "hindi",
            "story",
        ]

    tags = [
        str(tag).strip()
        for tag in tags
        if str(tag).strip()
    ]

    if not any(
        tag.lower() == "shorts"
        for tag in tags
    ):

        tags.insert(
            0,
            "shorts",
        )

    story["tags"] = tags[:15]

    return story


# ============================================================
# SAVE STORY
# ============================================================

def save_story(story):

    (
        ROOT / "story.json"
    ).write_text(
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

    (
        ROOT / "story.txt"
    ).write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


# ============================================================
# GENERATE STORY
# ============================================================

def generate_story():

    prompt = (
        "Create a high-retention Hindi YouTube Shorts story.\n"
        "Return ONLY valid JSON.\n\n"
        "Use exactly 6 scenes in this order:\n"
        "HOOK, SETUP, PROBLEM, TENSION, CLIMAX, ENDING_CTA.\n\n"
        "Requirements:\n"
        "- Start with a powerful curiosity hook.\n"
        "- Make viewers want to know what happens next.\n"
        "- Use a clear character and situation.\n"
        "- Introduce a real problem and increasing tension.\n"
        "- Give the story a meaningful climax.\n"
        "- Give the story a proper ending, not an abrupt stop.\n"
        "- Put a short natural CTA only at the end.\n"
        "- Use natural spoken Hindi.\n"
        "- Target 25 to 55 seconds total narration.\n"
        "- Do not put explanations outside the JSON.\n\n"
        "JSON format:\n"
        "{\n"
        '  "title": "short title",\n'
        '  "description": "short description",\n'
        '  "tags": ["shorts", "hindi story"],\n'
        '  "scenes": [\n'
        '    {"type":"HOOK","narration":"Hindi narration","visual":"English visual prompt"},\n'
        '    {"type":"SETUP","narration":"Hindi narration","visual":"English visual prompt"},\n'
        '    {"type":"PROBLEM","narration":"Hindi narration","visual":"English visual prompt"},\n'
        '    {"type":"TENSION","narration":"Hindi narration","visual":"English visual prompt"},\n'
        '    {"type":"CLIMAX","narration":"Hindi narration","visual":"English visual prompt"},\n'
        '    {"type":"ENDING_CTA","narration":"Hindi narration","visual":"English visual prompt"}\n'
        "  ]\n"
        "}"
    )

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert YouTube Shorts "
                    "storyteller. Write concise, emotional, "
                    "high-retention stories."
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

                story = normalize_story(
                    story
                )

                save_story(
                    story
                )

                print(
                    "AI story generated successfully."
                )

                return story

            print(
                "AI response could not be parsed."
            )

        except Exception as error:

            print(
                "Story attempt failed:",
                repr(error),
            )

            if attempt < 2:
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


# ============================================================
# EXTRACT IMAGE
# ============================================================

def extract_image_bytes(response):

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

    raise RuntimeError(
        "Cloudflare did not return "
        "a usable image"
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
            SCENES
            / f"scene_{index}.png"
        )

        success = False

        for attempt in range(2):

            try:

                print(
                    f"Generating image {index}/6 "
                    f"(attempt {attempt + 1})"
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

                raw = extract_image_bytes(
                    response
                )

                if not raw:

                    raise RuntimeError(
                        "Empty image response"
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

                if attempt == 0:
                    time.sleep(4)

        if not success:

            raise RuntimeError(
                f"Failed to generate image "
                f"for scene {index}"
            )


# ============================================================
# TEXT TO SPEECH
# ============================================================

async def create_tts(
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

    for index, scene in enumerate(
        story["scenes"],
        1,
    ):

        output = (
            AUDIO
            / f"scene_{index}.mp3"
        )

        print(
            f"Generating voice {index}/6"
        )

        try:

            asyncio.run(
                create_tts(
                    scene["narration"],
                    output,
                )
            )

        except Exception as error:

            raise RuntimeError(
                f"TTS failed for scene "
                f"{index}: {error}"
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

def get_duration(path):

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            

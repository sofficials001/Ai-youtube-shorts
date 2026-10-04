import asyncio
import base64
import json
import os
import random
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

CF_TOKEN = os.getenv("CLOUDFLARE_API_TOKEN")
CF_ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID")

if not CF_TOKEN or not CF_ACCOUNT:
    raise RuntimeError("Missing Cloudflare secrets")


LLM = "@cf/meta/llama-3.2-3b-instruct"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
VOICE = "hi-IN-SwaraNeural"


HEADERS = {
    "Authorization": "Bearer " + CF_TOKEN,
    "Content-Type": "application/json",
}


def cf_url(model):
    return (
        "https://api.cloudflare.com/client/v4/accounts/"
        + CF_ACCOUNT
        + "/ai/run/"
        + model
    )


def run(command):
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    if result.returncode != 0:
        print(result.stdout)
        raise RuntimeError(
            "Command failed: " + " ".join(command)
        )

    return result.stdout


def fallback_story():
    ideas = [
        (
            "एक कुत्ता रोज़ अस्पताल के बाहर क्यों बैठता था?",
            "dog hospital",
        ),
        (
            "एक लड़के को मिला कल का ट्रेन टिकट",
            "mysterious train ticket",
        ),
        (
            "एक घर हर सुबह अपनी जगह बदलता था",
            "moving house",
        ),
        (
            "एक चिड़िया सिर्फ एक इंसान के पास लौटती थी",
            "loyal bird",
        ),
        (
            "एक स्कूल बैग ने कल की घटना बता दी",
            "magical school bag",
        ),
        (
            "एक टूटी घड़ी सिर्फ एक बच्चे के सामने चलती थी",
            "mysterious clock",
        ),
        (
            "एक बिल्ली हर रात बंद घर के बाहर बैठती थी",
            "mysterious cat",
        ),
        (
            "एक पुरानी फोटो रोज़ बदलती थी",
            "changing photograph",
        ),
    ]

    title, topic = random.choice(ideas)

    return {
        "title": title,
        "description": (
            "एक छोटी कहानी जिसका अंत चौंका देगा। #Shorts"
        ),
        "tags": [
            "shorts",
            "hindi story",
            "story",
            "viral shorts",
        ],
        "scenes": [
            {
                "type": "HOOK",
                "narration": (
                    "हर दिन वही रहस्यमय चीज़ होती थी।"
                ),
                "visual": (
                    "A cinematic scene related to "
                    + topic
                    + ", mysterious atmosphere, dramatic close-up."
                ),
            },
            {
                "type": "SETUP",
                "narration": (
                    "लेकिन किसी को उसकी वजह पता नहीं थी।"
                ),
                "visual": (
                    "A cinematic establishing shot related to "
                    + topic
                    + ", realistic details, emotional lighting."
                ),
            },
            {
                "type": "PROBLEM",
                "narration": (
                    "एक दिन रहस्य अचानक मुसीबत बन गया।"
                ),
                "visual": (
                    "The same characters and setting, "
                    + topic
                    + ", sudden danger, cinematic tension."
                ),
            },
            {
                "type": "TENSION",
                "narration": (
                    "वह डरते हुए सच खोजने निकल पड़ा।"
                ),
                "visual": (
                    "The same characters and setting, "
                    + topic
                    + ", character moving toward danger, suspenseful cinematic shot."
                ),
            },
            {
                "type": "CLIMAX",
                "narration": (
                    "तभी उसे असली राज़ दिखाई दिया।"
                ),
                "visual": (
                    "The same characters and setting, "
                    + topic
                    + ", shocking discovery, dramatic cinematic climax."
                ),
            },
            {
                "type": "ENDING_CTA",
                "narration": (
                    "और शुरुआत से सब कुछ जुड़ा था।"
                ),
                "visual": (
                    "The same characters and setting, "
                    + topic
                    + ", emotional ending at sunrise, cinematic final shot."
                ),
            },
        ],
    }


def parse_story(value):
    if isinstance(value, dict):
        if isinstance(value.get("scenes"), list):
            return value

        for key in ("result", "response", "output"):
            if key in value:
                found = parse_story(value[key])

                if found:
                    return found

        return None

    if not isinstance(value, str):
        return None

    text = value.strip()

    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.lower().startswith("json"):
            text = text[4:].strip()

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
                and isinstance(obj.get("scenes"), list)
            ):
                return obj
        except Exception:
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

    for index, scene in enumerate(
        story["scenes"]
    ):
        if not isinstance(scene, dict):
            raise ValueError(
                "Invalid scene " + str(index + 1)
            )

        narration = str(
            scene.get("narration", "")
        ).strip()

        visual = str(
            scene.get("visual", "")
        ).strip()

        if not narration or not visual:
            raise ValueError(
                "Scene "
                + str(index + 1)
                + " is incomplete"
            )

        scene["type"] = types[index]
        scene["narration"] = narration

        scene["visual"] = (
            visual
            + " Same white rabbit with blue scarf. "
            + "Vertical 9:16 composition. "
            + "No text, no logo, no watermark."
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

    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        lines.append(
            str(index) + ". " + scene["type"]
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
    topics = [
        "एक रहस्यमय जानवर और इंसान की मुलाकात",
        "एक ऐसी चीज़ जो भविष्य की छोटी झलक दिखाती है",
        "एक अजनबी जो अचानक गायब हो जाता है",
        "एक स्कूल में हुआ अजीब रहस्य",
        "एक गरीब बच्चे को मिली अनोखी चीज़",
        "एक पालतू जानवर का छिपा हुआ राज़",
        "एक पुराने घर में हुई रहस्यमय घटना",
        "एक ऐसी तस्वीर जो बदलती रहती है",
        "एक छोटी गलती जिसने किसी की जिंदगी बदल दी",
        "एक व्यक्ति जिसे रोज़ एक रहस्यमय संदेश मिलता है",
        "एक खोई हुई चीज़ जो सही इंसान तक वापस पहुँचती है",
        "एक दोस्ती जो असंभव जगह से शुरू होती है",
        "एक छोटी सी मदद जिसका बड़ा परिणाम निकलता है",
        "एक ऐसा कमरा जिसे कोई खोल नहीं सकता",
        "एक बच्चा जिसे हर रात एक ही सपना आता है",
    ]

    topic = random.choice(topics)
    seed = random.randint(
        100000,
        999999999,
    )

    prompt_lines = [
        "Create a completely original Hindi YouTube Shorts story.",
        "This is generation seed: " + str(seed),
        "Main story topic: " + topic,
        "Do not reuse common previous stories.",
        "Return ONLY valid JSON.",
        "Return exactly 6 scenes in this order:",
        "HOOK, SETUP, PROBLEM, TENSION, CLIMAX, ENDING_CTA.",
        "The complete spoken narration MUST be about 15 to 25 seconds.",
        "Use approximately 10 to 14 spoken Hindi words per scene.",
        "Keep every scene short and punchy.",
        "The HOOK must create curiosity in the first second.",
        "The SETUP must quickly establish the situation.",
        "The PROBLEM must introduce a clear conflict.",
        "The TENSION must raise the stakes.",
        "The CLIMAX must reveal or resolve the main mystery.",
        "The ENDING_CTA must give a satisfying final line.",
        "Do not add long explanations.",
        "Do not repeat the same sentence or plot.",
        "Use spoken, natural Hindi.",
        "JSON keys: title, description, tags, scenes.",
        "Each scene needs type, narration, visual.",
        "Visual prompts must describe the same characters consistently.",
    ]

    prompt = "\n".join(prompt_lines)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You create highly varied, fast-paced, "
                    "high-retention Hindi YouTube Shorts. "
                    "Every request must produce a fresh story."
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

                word_count = sum(
                    len(
                        scene["narration"].split()
                    )
                    for scene in story["scenes"]
                )

                print(
                    "Story narration words:",
                    word_count,
                )

                if 36 <= word_count <= 60:
                    save_story(story)
                    return story

                print(
                    "Story was outside 15-25 second word range:",
                    word_count,
                )

        except Exception as error:
            print(
                "Story attempt failed:",
                error,
            )

        if attempt < 2:
            time.sleep(3)

    story = normalize(
        fallback_story()
    )

    save_story(story)

    print(
        "Using randomized fallback story"
    )

    return story


def decode_image(value):
    if isinstance(value, str):
        text = value.strip()

        if (
            text.startswith("data:image")
            and "," in text
        ):
            text = text.split(
                ",",
                1,
            )[1]

        try:
            return base64.b64decode(
                text,
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


def response_image_bytes(response):
    content_type = response.headers.get(
        "content-type",
        "",
    ).lower()

    if content_type.startswith("image/"):
        return response.content

    try:
        data = response.json()

    except Exception:
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
    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        output = (
            SCENES
            / ("scene_" + str(index) + ".png")
        )

        for attempt in range(2):
            try:
                response = requests.post(
                    cf_url(IMAGE_MODEL),
                    headers=HEADERS,
                    json={
                        "prompt": scene["visual"],
                        "steps": 4,
                    },
                    timeout=180,
                )

                print(
                    "Image",
                    index,
                    "HTTP:",
                    response.status_code,
                )

                response.raise_for_status()

                raw = response_image_bytes(
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


async def create_tts(text, path):
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
            / ("scene_" + str(index) + ".mp3")
        )

        print(
            "Voice",
            index,
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
                "TTS failed for scene "
                + str(index)
                + ": "
                + str(error)
            ) from error

        if (
            not output.exists()
            or output.stat().st_size < 1000
        ):
            raise RuntimeError(
                "Invalid audio: "
                + str(output)
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
    total_cs = max(
        1,
        int(
            round(
                seconds * 100
            )
        ),
    )

    hours = total_cs // 360000

    minutes = (
        total_cs % 360000
    ) // 6000

    secs = (
        total_cs % 6000
    ) // 100

    hundredths = (
        total_cs % 100
    )

    return (
        str(hours)
        + ":"
        + f"{minutes:02d}"
        + ":"
        + f"{secs:02d}"
        + "."
        + f"{hundredths:02d}"
    )


def make_ass(text, seconds, path):
    safe = (
        text
        .replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", " ")
    )

    ass_lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "[V4+ Styles]",
        (
            "Format: Name, Fontname, Fontsize, "
            "PrimaryColour, SecondaryColour, "
            "OutlineColour, BackColour, Bold, "
            "Italic, Underline, StrikeOut, ScaleX, "
            "ScaleY, Spacing, Angle, BorderStyle, "
            "Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding"
        ),
        (
            "Style: Default,Noto Sans Devanagari,62,"
            "&H00FFFFFF,&H00FFFFFF,&H00000000,"
            "&H80000000,-1,0,0,0,100,100,0,0,1,"
            "5,2,2,60,60,170,-1"
        ),
        "[Events]",
        (
            "Format: Layer, Start, End, Style, Name, "
            "MarginL, MarginR, MarginV, Effect, Text"
        ),
        (
            "Dialogue: 0,0:00:00.00,"
            + ass_time(seconds)
            + ",Default,,0,0,170,,"
            + safe
        ),
    ]

    path.write_text(
        "\n".join(ass_lines) + "\n",
        encoding="utf-8",
    )


def make_segment(index, narration):
    image = (
        SCENES
        / ("scene_" + str(index) + ".png")
    )

    audio = (
        AUDIO
        / ("scene_" + str(index) + ".mp3")
    )

    ass = (
        SEGMENTS
        / ("scene_" + str(index) + ".ass")
    )

    output = (
        SEGMENTS
        / ("segment_" + str(index) + ".mp4")
    )

    seconds = duration(
        audio
    )

    make_ass(
        narration,
        seconds,
        ass,
    )

    frames = max(
        1,
        int(
            round(
                seconds * 30
            )
        ),
    )

    ass_path = (
        ass.as_posix()
        .replace(
            ":",
            r"\:",
        )
    )

    # Turn each generated image into a moving 30 FPS shot.
    # Different scenes use different camera directions so the
    # final Short does not look like six static pictures.
    motion = index % 4

    if motion == 1:
        zoom_expression = (
            "min(zoom+0.0018,1.15)"
        )
        x_expression = (
            "iw/2-(iw/zoom/2)"
        )
        y_expression = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == 2:
        zoom_expression = (
            "min(zoom+0.0014,1.12)"
        )
        x_expression = (
            "(iw-iw/zoom)*on/"
            + str(max(frames - 1, 1))
        )
        y_expression = (
            "ih/2-(ih/zoom/2)"
        )

    elif motion == 3:
        zoom_expression = (
            "min(zoom+0.0016,1.14)"
        )
        x_expression = (
            "(iw-iw/zoom)*(1-on/"
            + str(max(frames - 1, 1))
            + ")"
        )
        y_expression = (
            "ih/2-(ih/zoom/2)"
        )

    else:
        zoom_expression = (
            "min(zoom+0.0012,1.10)"
        )
        x_expression = (
            "iw/2-(iw/zoom/2)"
        )
        y_expression = (
            "(ih-ih/zoom)*on/"
            + str(max(frames - 1, 1))
        )

    video_filter = (
        "scale=2160:3840:"
        "force_original_aspect_ratio=increase,"
        "crop=2160:3840,"
        "zoompan="
        "z='" + zoom_expression + "':"
        "x='" + x_expression + "':"
        "y='" + y_expression + "':"
        "d=" + str(frames) + ":"
        "s=1080x1920:"
        "fps=30,"
        "subtitles=" + ass_path
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
            "-vf",
            video_filter,
            "-map",
            "0:v:0",
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
    for index, scene in enumerate(
        story["scenes"],
        1,
    ):
        print(
            "Segment",
            index,
        )

        make_segment(
            index,
            scene["narration"],
        )


def join_segments():
    concat = (
        SEGMENTS
        / "concat.txt"
    )

    final = (
        OUTPUT
        / "final_short.mp4"
    )

    lines = []

    for index in range(1, 7):
        path = (
            SEGMENTS
            / ("segment_" + str(index) + ".mp4")
        )

        if not path.exists():
            raise FileNotFoundError(
                str(path)
            )

        lines.append(
            "file '"
            + path.resolve().as_posix()
            + "'"
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
        OUTPUT
        / "final_short.mp4"
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
            if item.get("codec_type") == "video"
        ),
        None,
    )

    audio_stream = next(
        (
            item
            for item in streams
            if item.get("codec_type") == "audio"
        ),
        None,
    )

    if not video_stream or not audio_stream:
        raise RuntimeError(
            "Video or audio stream missing"
        )

    width = int(
        video_stream.get(
            "width",
            0,
        )
    )

    height = int(
        video_stream.get(
            "height",
            0,
        )
    )

    if width != 1080 or height != 1920:
        raise RuntimeError(
            "Wrong video resolution: "
            + str(width)
            + "x"
            + str(height)
        )

    total = float(
        data["format"].get(
            "duration",
            0,
        )
    )

    if not 15 <= total <= 25:
        raise RuntimeError(
            "Video duration is %.2fs; expected 15-25s"
            % total
        )

    if (
        video_stream.get("codec_name")
        != "h264"
    ):
        raise RuntimeError(
            "Video is not H.264"
        )

    if (
        audio_stream.get("codec_name")
        != "aac"
    ):
        raise RuntimeError(
            "Audio is not AAC"
        )

    print(
        "Video verification passed"
    )

    print(
        "Resolution:",
        str(width) + "x" + str(height),
    )

    print(
        "Duration:",
        "%.2f seconds" % total,
    )

    print(
        "Video codec:",
        video_stream.get("codec_name"),
    )

    print(
        "Audio codec:",
        audio_stream.get("codec_name"),
    )


def main():
    print(
        "Starting AI YouTube Short generation"
    )

    story = generate_story()

    print(
        "Generating images"
    )

    generate_images(
        story
    )

    print(
        "Generating voice"
    )

    generate_audio(
        story
    )

    print(
        "Creating video segments"
    )

    create_segments(
        story
    )

    print(
        "Joining segments"
    )

    join_segments()

    print(
        "Verifying final video"
    )

    verify()

    print(
        "Short generated successfully"
    )


if __name__ == "__main__":
    main()

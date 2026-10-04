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
    stories = [
        {
            "title": "एक लड़के को रोज़ भविष्य का संदेश मिलता था",
            "scenes": [
                ("HOOK", "हर सुबह उसके फोन पर कल का संदेश आता था।", "A teenage Indian boy checking a mysterious phone message at dawn, realistic cinematic scene."),
                ("SETUP", "पहले संदेश में सिर्फ एक छोटी चेतावनी थी।", "Close-up of the boy reading a cryptic warning on his phone, tense bedroom atmosphere."),
                ("PROBLEM", "लेकिन आज संदेश में उसका अपना नाम लिखा था।", "The boy shocked by his own name appearing in the mysterious message, dramatic close-up."),
                ("TENSION", "नीचे लिखा था, आज स्कूल मत जाना।", "The boy standing uncertainly outside a school gate, ominous sky, cinematic suspense."),
                ("CLIMAX", "कुछ देर बाद स्कूल के बाहर बड़ा हादसा हुआ।", "Distant commotion outside the school, the boy watching safely from afar, dramatic realistic shot."),
                ("ENDING_CTA", "तभी उसे समझ आया, संदेश भविष्य से आया था।", "The boy staring at his phone in disbelief at sunset, emotional cinematic ending."),
            ],
        },
        {
            "title": "एक कुत्ता रोज़ अस्पताल के बाहर बैठता था",
            "scenes": [
                ("HOOK", "वह कुत्ता हर शाम अस्पताल के बाहर बैठता था।", "A loyal street dog waiting outside a city hospital at sunset, cinematic realism."),
                ("SETUP", "लोग उसे खाना देते, लेकिन वह अंदर देखता रहता।", "People offering food to the dog while it keeps staring toward the hospital entrance."),
                ("PROBLEM", "एक दिन नर्स ने उसका पीछा करने का फैसला किया।", "A curious nurse following the dog through a hospital corridor, suspenseful cinematic scene."),
                ("TENSION", "कुत्ता उसे एक बंद कमरे तक ले गया।", "The dog stopping beside a closed hospital room door, nurse looking shocked."),
                ("CLIMAX", "अंदर एक बुज़ुर्ग मरीज उसे देखकर मुस्कुरा रहा था।", "An elderly patient smiling emotionally at the dog inside a hospital room."),
                ("ENDING_CTA", "वह कुत्ता सालों से अपने मालिक को ढूँढ रहा था।", "The dog reunited with its elderly owner, warm emotional hospital ending."),
            ],
        },
        {
            "title": "एक पुरानी तस्वीर रोज़ बदलती थी",
            "scenes": [
                ("HOOK", "उस पुरानी तस्वीर में हर रात कुछ बदल जाता था।", "A young woman examining an old framed photograph at night, mysterious cinematic lighting."),
                ("SETUP", "पहले तस्वीर में सिर्फ एक खाली कुर्सी थी।", "Close-up of an old photograph showing an empty chair in a dark room."),
                ("PROBLEM", "अगली सुबह कुर्सी पर एक अजनबी बैठा था।", "The same photograph now showing a mysterious stranger sitting on the chair."),
                ("TENSION", "हर दिन वह अजनबी उसके करीब आता गया।", "The woman watching the changing photograph as the stranger appears closer each day."),
                ("CLIMAX", "आखिर तस्वीर में अजनबी ने पीछे इशारा किया।", "The stranger in the photograph pointing behind the woman, shocking cinematic moment."),
                ("ENDING_CTA", "वहाँ वही तस्वीर पड़ी थी, बिल्कुल नई।", "A second identical photograph lying behind her, mysterious final reveal."),
            ],
        },
        {
            "title": "एक स्कूल बैग ने कल की घटना बता दी",
            "scenes": [
                ("HOOK", "स्कूल बैग में अचानक एक अजीब कागज़ मिला।", "A schoolboy discovering a mysterious handwritten note inside his backpack."),
                ("SETUP", "उस पर अगले दिन की पूरी घटना लिखी थी।", "Close-up of a note describing events that have not happened yet."),
                ("PROBLEM", "सबसे नीचे लिखा था, दोस्त पर भरोसा मत करना।", "The boy reading a frightening warning about his best friend."),
                ("TENSION", "अगले दिन वही दोस्त उसे सुनसान जगह बुलाता है।", "The boy meeting his friend at a quiet deserted location, tense atmosphere."),
                ("CLIMAX", "लेकिन दोस्त ने उसे चोरी से बचाने बुलाया था।", "The friend revealing he brought the boy there to protect him, emotional reveal."),
                ("ENDING_CTA", "कागज़ ने खतरा बताया था, इंसान को नहीं।", "The boy realizing the note was misunderstood, thoughtful cinematic ending."),
            ],
        },
        {
            "title": "एक कमरा जिसे कोई खोल नहीं सकता था",
            "scenes": [
                ("HOOK", "उस घर का एक कमरा बीस साल से बंद था।", "An old Indian house with one mysterious locked room, cinematic night scene."),
                ("SETUP", "हर रात अंदर से घड़ी की आवाज़ आती थी।", "A family hearing a clock ticking behind the locked door at midnight."),
                ("PROBLEM", "एक बच्चे ने कहा, अंदर कोई रो रहा है।", "A child listening carefully beside the mysterious locked door."),
                ("TENSION", "परिवार ने आखिर दरवाज़ा तोड़ने का फैसला किया।", "Family members preparing to open the ancient locked room, suspenseful scene."),
                ("CLIMAX", "अंदर कोई इंसान नहीं, पुरानी रिकॉर्डिंग चल रही थी।", "An old recorder playing inside a dusty abandoned room, shocking discovery."),
                ("ENDING_CTA", "रिकॉर्डिंग में उसी परिवार की बीस साल पुरानी आवाज़ थी।", "The family listening in shock to their own old voices, eerie ending."),
            ],
        },
        {
            "title": "एक चिड़िया सिर्फ एक इंसान के पास लौटती थी",
            "scenes": [
                ("HOOK", "एक छोटी चिड़िया रोज़ उसी आदमी के पास आती थी।", "A small bird landing beside a lonely man in a city park."),
                ("SETUP", "वह हमेशा अपनी चोंच में लाल धागा लाती।", "The bird carrying a tiny red thread to the man."),
                ("PROBLEM", "एक दिन धागे से घर की चाबी बंधी थी।", "The man discovering an old house key tied to the red thread."),
                ("TENSION", "चाबी देखकर उसे अपने बचपन का घर याद आया।", "The man remembering his childhood home while holding the mysterious key."),
                ("CLIMAX", "घर पहुँचकर उसे अंदर पुराना खत मिला।", "The man finding an old letter inside his childhood home."),
                ("ENDING_CTA", "खत उसी पिता का था जिसे वह खो चुका था।", "The man reading his late father's letter with tears, emotional ending."),
            ],
        },
        {
            "title": "एक дом हर सुबह अपनी जगह बदलता था",
            "scenes": [
                ("HOOK", "उस घर की जगह हर सुबह बदल जाती थी।", "A strange house appearing in a different landscape at sunrise."),
                ("SETUP", "परिवार नक्शा बनाकर उसका पीछा करने लगा।", "A family marking changing house locations on a large map."),
                ("PROBLEM", "तीसरे दिन घर सीधे जंगल के बीच मिला।", "The mysterious house standing alone deep inside a forest."),
                ("TENSION", "दरवाज़े पर उनके बचपन की तस्वीर लगी थी।", "The family discovering their childhood photograph on the forest house door."),
                ("CLIMAX", "अंदर एक डायरी ने घर का रहस्य बताया।", "An old diary revealing the mysterious history of the moving house."),
                ("ENDING_CTA", "घर उन्हें वहीं ले जा रहा था जहाँ सब शुरू हुआ।", "The family looking toward their original childhood home, emotional mysterious ending."),
            ],
        },
        {
            "title": "एक बच्चा हर रात वही सपना देखता था",
            "scenes": [
                ("HOOK", "वह बच्चा हर रात एक ही जगह देखता था।", "A child dreaming of the same mysterious railway platform every night."),
                ("SETUP", "सपने में एक ट्रेन हमेशा बिना रुके गुजरती।", "A ghostly train rushing past the empty platform in the dream."),
                ("PROBLEM", "एक रात उसने ट्रेन में अपना नाम देखा।", "The child seeing his own name displayed on the mysterious train."),
                ("TENSION", "अगली सुबह वही ट्रेन शहर में आने वाली थी।", "The child checking a real railway schedule with fear."),
                ("CLIMAX", "स्टेशन पर ट्रेन आई, लेकिन उसका नाम गायब था।", "The train arriving at the station while the child's name disappears."),
                ("ENDING_CTA", "तभी उसे समझ आया, सपना चेतावनी था, भविष्य नहीं।", "The child realizing the dream was a warning, peaceful cinematic ending."),
            ],
        },
    ]

    # Fix the one intentionally varied template typo before returning it.
    stories[6]["title"] = "एक घर हर सुबह अपनी जगह बदलता था"

    selected = random.choice(stories)

    return {
        "title": selected["title"],
        "description": "एक छोटी रहस्यमय कहानी जिसका अंत आपको चौंका देगा।",
        "tags": ["shorts", "hindi story", "story", "mystery story", "viral shorts", "hindi shorts"],
        "scenes": [
            {
                "type": scene_type,
                "narration": narration,
                "visual": visual,
            }
            for scene_type, narration, visual in selected["scenes"]
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
        raise ValueError("Story must contain exactly 6 scenes")

    types = [
        "HOOK",
        "SETUP",
        "PROBLEM",
        "TENSION",
        "CLIMAX",
        "ENDING_CTA",
    ]

    for index, scene in enumerate(story["scenes"]):
        if not isinstance(scene, dict):
            raise ValueError("Invalid scene " + str(index + 1))

        narration = str(scene.get("narration", "")).strip()
        visual = str(scene.get("visual", "")).strip()

        if not narration or not visual:
            raise ValueError(
                "Scene " + str(index + 1) + " is incomplete"
            )

        scene["type"] = types[index]
        scene["narration"] = narration
        scene["visual"] = (
            visual
            + " Vertical 9:16 composition. "
            + "Cinematic realistic style. "
            + "No text, no logo, no watermark."
        )

    story.setdefault(
        "title",
        "एक कहानी जिसका अंत आपको चौंका देगा",
    )
    story.setdefault(
        "description",
        "एक छोटी कहानी जिसका अंत याद रहेगा।",
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
        "एक रहस्यमय संदेश जो भविष्य की चेतावनी देता है",
        "एक जानवर जो किसी इंसान को बार-बार एक जगह ले जाता है",
        "एक पुरानी वस्तु जिसमें छिपा हुआ रहस्य है",
        "एक स्कूल में होने वाली अजीब घटना",
        "एक गरीब बच्चे को मिली असाधारण चीज़",
        "एक परिवार के घर में छिपा पुराना रहस्य",
        "एक ऐसी तस्वीर जो हर दिन बदलती है",
        "एक अजनबी जो अचानक किसी की जिंदगी बदल देता है",
        "एक खोई हुई चीज़ जो अपने मालिक तक वापस पहुँचती है",
        "एक छोटी मदद जिसका बहुत बड़ा परिणाम निकलता है",
        "एक ऐसा कमरा जिसे कोई खोल नहीं सकता",
        "एक बच्चा जिसे बार-बार एक ही सपना आता है",
        "एक ट्रेन यात्रा जिसमें कुछ असंभव होता है",
        "एक पुरानी डायरी जो भविष्य की बातें लिखती है",
        "एक फोन जिसे हर रात अजीब कॉल आती है",
        "एक घड़ी जो सिर्फ एक व्यक्ति के लिए चलती है",
        "एक दोस्ती जो एक रहस्यमय घटना से शुरू होती है",
        "एक गांव में हर रात होने वाली अजीब घटना",
        "एक व्यक्ति जिसे रोज़ एक ही अजनबी दिखाई देता है",
        "एक छोटी गलती जो किसी बड़े रहस्य को खोल देती है",
    ]

    characters = [
        "एक स्कूल का लड़का", "एक कॉलेज की लड़की", "एक अकेला बुज़ुर्ग आदमी",
        "एक युवा डॉक्टर", "एक छोटा दुकानदार", "एक डिलीवरी राइडर",
        "एक गांव का बच्चा", "एक फोटोग्राफर", "एक रेलवे कर्मचारी", "एक शिक्षक",
    ]

    locations = [
        "पुराना रेलवे स्टेशन", "शांत पहाड़ी गांव", "एक पुराना शहर",
        "स्कूल की खाली इमारत", "बारिश से भरी सड़क", "पुराना अस्पताल",
        "सुनसान जंगल", "एक छोटा बाजार", "समुद्र के किनारे का गांव",
        "पुराना पारिवारिक घर",
    ]

    conflicts = [
        "एक रहस्यमय चेतावनी", "अचानक गायब हुई चीज़", "समय से जुड़ा रहस्य",
        "एक गलतफहमी", "एक छिपी हुई सच्चाई", "अचानक आया खतरा",
        "एक पुराना वादा", "एक अनजान व्यक्ति", "एक असंभव संयोग",
        "एक ऐसा राज़ जिसे कोई नहीं जानता",
    ]

    endings = [
        "अंत में पता चला कि सुराग शुरुआत से उसके सामने था।",
        "तभी उसे समझ आया कि असली रहस्य कुछ और था।",
        "उस एक पल ने पूरी कहानी का मतलब बदल दिया।",
        "जो डरावना लग रहा था, वही उसे बचाने आया था।",
        "अंत में उसे वही जवाब मिला जिसे वह वर्षों से खोज रहा था।",
        "तभी उसे समझ आया कि घटना संयोग नहीं थी।",
        "आखिरी सबूत ने उसकी पूरी सोच बदल दी।",
        "और तभी उसे पता चला कि कहानी अभी खत्म नहीं हुई।",
    ]

    seed = random.randint(100000, 999999999)
    topic = random.choice(topics)
    character = random.choice(characters)
    location = random.choice(locations)
    conflict = random.choice(conflicts)
    ending_hint = random.choice(endings)

    prompt_lines = [
        "Create one completely original Hindi YouTube Shorts story.",
        "Generation seed: " + str(seed),
        "Main topic: " + topic,
        "Main character: " + character,
        "Main location: " + location,
        "Main conflict: " + conflict,
        "Possible ending direction: " + ending_hint,
        "This story must feel different from previous generations.",
        "Do not reuse a generic rabbit story.",
        "Do not use a rabbit unless the topic specifically requires it.",
        "Return ONLY valid JSON.",
        "Return exactly 6 scenes in this order:",
        "HOOK, SETUP, PROBLEM, TENSION, CLIMAX, ENDING_CTA.",
        "The complete spoken narration MUST be suitable for 15 to 25 seconds.",
        "Use about 6 to 10 spoken Hindi words per scene.",
        "Keep the complete narration between 36 and 60 words.",
        "Every scene must advance the story.",
        "The HOOK must create curiosity immediately.",
        "The SETUP must establish the character and situation quickly.",
        "The PROBLEM must introduce a specific conflict.",
        "The TENSION must make the viewer want the answer.",
        "The CLIMAX must reveal something specific and surprising.",
        "The ENDING_CTA must provide a satisfying final line.",
        "Do not use generic filler sentences.",
        "Do not repeat the same narration across scenes.",
        "Visual prompts must match the narration exactly.",
        "Keep characters and locations visually consistent across scenes.",
        "Each visual prompt should describe a cinematic realistic shot.",
        "JSON keys: title, description, tags, scenes.",
        "Each scene needs type, narration, visual.",
    ]

    prompt = "\n".join(prompt_lines)

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "You create original, varied, high-retention "
                    "Hindi YouTube Shorts. Never copy a previous story. "
                    "Use the supplied seed, character, location, conflict "
                    "and topic to make the plot specific."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.95,
        "top_p": 0.95,
    }

    for attempt in range(3):
        try:
            if attempt > 0:
                retry_seed = random.randint(100000, 999999999)
                payload["messages"][1]["content"] = (
                    prompt
                    + "\nRetry seed: " + str(retry_seed)
                    + "\nMake the plot substantially different."
                )

            response = requests.post(
                cf_url(LLM),
                headers=HEADERS,
                json=payload,
                timeout=120,
            )

            print("Story HTTP:", response.status_code)
            response.raise_for_status()

            story = parse_story(response.json())

            if story:
                story = normalize(story)
                narrations = [s["narration"] for s in story["scenes"]]
                word_count = sum(len(text.split()) for text in narrations)
                unique_narrations = len(set(narrations))

                print("Generated title:", story.get("title", ""))
                print("Story narration:")
                for index, text in enumerate(narrations, 1):
                    print("  " + str(index) + ". " + text)

                print("Story narration words:", word_count)
                print("Unique scene narrations:", unique_narrations, "/ 6")

                if 36 <= word_count <= 60 and unique_narrations == 6:
                    save_story(story)
                    return story

                print("Story rejected: invalid length or repeated narration.")

        except Exception as error:
            print("Story attempt failed:", error)

        if attempt < 2:
            time.sleep(3)

    story = normalize(fallback_story())

    print("Using varied fallback story:")
    print("Fallback title:", story["title"])

    for index, scene in enumerate(story["scenes"], 1):
        print("  " + str(index) + ". " + scene["narration"])

    save_story(story)
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

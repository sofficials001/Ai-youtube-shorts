#!/usr/bin/env python3
"""Generate silent, caption-led 3D-style tiny-people/giant-world Shorts."""
import base64, json, os, random, subprocess, sys, time
from pathlib import Path
import requests
from PIL import Image

ACCOUNT = os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()
TOKEN = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
if not ACCOUNT or not TOKEN:
    raise SystemExit("Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN.")

API = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run"
TEXT_MODEL = "@cf/meta/llama-3.2-3b-instruct"
IMAGE_MODEL = "@cf/black-forest-labs/flux-1-schnell"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
OUT = Path("output")
IMAGES = OUT / "images"
OUT.mkdir(parents=True, exist_ok=True)
IMAGES.mkdir(parents=True, exist_ok=True)
SCENE_COUNT, SCENE_SECONDS = 6, 4

FALLBACKS = [
    {
        "title": "एक चम्मच बना स्विमिंग पूल",
        "cast": "three tiny stylized 3D human explorers, each only a few centimeters tall, wearing colorful miniature adventure clothes",
        "scenes": [
            ("इन लोगों के लिए चम्मच एक झील थी!", "Three tiny explorers stand at the edge of a giant silver spoon filled with water on a kitchen table."),
            ("लेकिन पानी तक पहुँचना आसान नहीं था।", "Tiny explorers carefully climb a folded kitchen towel like a steep mountain beside the giant spoon."),
            ("तभी एक बड़ी पानी की बूंद गिरी।", "A huge clear water droplet splashes near the tiny explorers, towering over them like a crystal boulder."),
            ("उनकी छोटी नाव बहने लगी!", "A tiny leaf boat carrying the explorers drifts across the spoon's reflective pool."),
            ("दोस्तों ने मिलकर नाव बचाई।", "The tiny explorers use a thread as a rope to pull their leaf boat toward the spoon handle."),
            ("अब चम्मच उनका सबसे बड़ा रोमांच था।", "The tiny explorers celebrate safely on the giant spoon handle as warm morning sunlight fills the kitchen.")
        ]
    },
    {
        "title": "पेंसिल के पीछे छिपा शहर",
        "cast": "a tiny 3D animated family of miniature human inventors wearing bright handmade clothes and tiny backpacks",
        "scenes": [
            ("एक पेंसिल उनके लिए गगनचुंबी इमारत थी।", "Tiny human inventors stand beside an enormous yellow pencil lying across a wooden desk like a skyscraper."),
            ("उनका घर मेज की दरार में था।", "A cozy miniature house built inside a narrow crack in a wooden desk, tiny windows glowing."),
            ("अचानक पेंसिल लुढ़कने लगी।", "The giant pencil starts rolling toward the tiny house while miniature people look startled."),
            ("सबने मिलकर रास्ता रोका।", "Tiny inventors push a tiny wooden wedge under the giant pencil, working together."),
            ("पेंसिल रुक गई और घर बच गया।", "The pencil rests safely against the wedge while the miniature family cheers."),
            ("छोटी टीम ने बड़ा कमाल कर दिया।", "The tiny inventors celebrate on top of a giant eraser beside their safe little desk-crack home.")
        ]
    },
    {
        "title": "बिस्कुट का पहाड़",
        "cast": "a brave tiny 3D animated girl and her tiny human friend, wearing colorful explorer outfits and small backpacks",
        "scenes": [
            ("उनके सामने बिस्कुट का पहाड़ था।", "Two tiny human explorers look up at a giant golden biscuit on a picnic blanket."),
            ("घर लौटने का रास्ता बंद था।", "The tiny explorers stand between the giant biscuit and a tall wall of picnic basket fabric."),
            ("तभी चींटियों की कतार दिखाई दी।", "A line of small ants walks beside the tiny explorers around crumbs near the giant biscuit."),
            ("उन्होंने टुकड़ों से सीढ़ी बनाई।", "Tiny explorers arrange biscuit crumbs into a little staircase beside the huge biscuit."),
            ("दोनों ऊपर चढ़कर बाहर निकल गए।", "The tiny friends climb their crumb staircase and reach the top of the giant biscuit."),
            ("अब पिकनिक उनके लिए पूरा संसार थी।", "The tiny explorers wave from the giant biscuit while a vast sunny picnic blanket stretches behind them.")
        ]
    }
]

def cloudflare_request(model, payload, attempts=5):
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(
                f"{API}/{model}", headers=HEADERS, json=payload, timeout=180
            )
            if response.status_code == 429:
                print(f"Cloudflare 429 ({attempt}/{attempts}): {response.text[:500]}")
                if attempt < attempts:
                    delay = min(60, 10 * attempt)
                    print(f"Retrying after {delay}s.")
                    time.sleep(delay)
                    continue
                raise RuntimeError("Cloudflare returned 429 after retries; free allocation or temporary capacity may be exhausted.")
            if response.status_code >= 500 and attempt < attempts:
                time.sleep(min(30, 5 * attempt))
                continue
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt == attempts:
                raise RuntimeError(f"Cloudflare connection failed: {exc}") from exc
            time.sleep(min(30, 5 * attempt))
    raise RuntimeError("Cloudflare request failed.")

def fallback_story():
    item = random.choice(FALLBACKS)
    return {
        "title": item["title"],
        "cast": item["cast"],
        "scenes": [{"caption": c, "visual": v} for c, v in item["scenes"]],
    }

def generate_story():
    seed = random.randint(1, 999_999_999)
    idea = random.choice([
        "tiny people use a giant spoon as a lake",
        "miniature inventors save their home from a rolling pencil",
        "tiny explorers climb a giant biscuit",
        "tiny builders create a bridge across a spilled glass of water",
        "miniature hikers cross a giant keyboard",
        "tiny friends rescue a lost toy in a giant garden",
    ])
    prompt = (
        "Create one original, family-friendly 24-second vertical YouTube Short about tiny people in a giant everyday world. "
        f"Idea: {idea}. Random seed: {seed}. Return ONLY valid JSON with title in Hindi, cast in English, and exactly six scenes. "
        "Each scene has caption (short Hindi, 3-8 words) and visual (English prompt describing one clear image). "
        "Story beats: immediate visual hook, establish scale/problem, surprise, clever teamwork, progress, satisfying ending. "
        "All humans are miniature fictional characters, not real people. Keep the same characters and clothing consistent across all scenes. "
        "Polished high-quality 3D animated family film look, expressive miniature characters, tactile materials, cinematic lighting, "
        "strong scale contrast with giant household objects, portrait 9:16 composition. No dialogue, no voice-over, no text in images, "
        "no copyrighted characters, no injury or violence. "
        'JSON shape: {"title":"Hindi title","cast":"English character consistency description","scenes":['
        '{"caption":"Hindi","visual":"English prompt"},{"caption":"Hindi","visual":"English prompt"},'
        '{"caption":"Hindi","visual":"English prompt"},{"caption":"Hindi","visual":"English prompt"},'
        '{"caption":"Hindi","visual":"English prompt"},{"caption":"Hindi","visual":"English prompt"}]}'
    )
    payload = {
        "messages": [
            {"role": "system", "content": "Write original visual micro-stories. Return valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1100,
        "temperature": 0.95,
        "top_p": 0.95,
        "seed": seed,
    }
    try:
        data = cloudflare_request(TEXT_MODEL, payload, 3).json()
        result = data.get("result", {})
        raw = result.get("response") or result.get("output") or result.get("text")
        if not raw:
            raise ValueError("Text model returned no response.")
        raw = raw.replace("```json", "").replace("```", "").strip()
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            raise ValueError("No JSON object in model response.")
        obj = json.loads(raw[start:end + 1])
        scenes = obj["scenes"]
        title = str(obj["title"]).strip()
        cast = str(obj["cast"]).strip()
        if len(scenes) != SCENE_COUNT or not title or not cast:
            raise ValueError("Invalid title/cast/scene count.")
        cleaned = [
            {"caption": str(s["caption"]).strip()[:90], "visual": str(s["visual"]).strip()}
            for s in scenes
        ]
        if any(not s["caption"] or not s["visual"] for s in cleaned):
            raise ValueError("Empty caption or visual prompt.")
        if len({s["caption"] for s in cleaned}) < 5:
            raise ValueError("Repeated captions.")
        return {"title": title[:100], "cast": cast, "scenes": cleaned}
    except Exception as exc:
        print("Text model failed/returned invalid story; using varied fallback:", exc)
        return fallback_story()

def generate_image(visual, cast, index):
    prompt = (
        "High-quality polished 3D animated family film still. Scale: tiny fictional human characters in a giant everyday world. "
        f"Character consistency: {cast}. Scene: {visual}. "
        "Strong contrast between miniature characters and enormous object, detailed materials, expressive faces, cinematic depth of field, "
        "warm appealing lighting, portrait 9:16 framing. No text, letters, logos or watermark."
    )
    data = cloudflare_request(IMAGE_MODEL, {"prompt": prompt, "steps": 4}, 5).json()
    result = data.get("result", {})
    encoded = result.get("image") if isinstance(result, dict) else None
    if not encoded:
        raise RuntimeError("FLUX response does not contain result.image.")
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    raw = base64.b64decode(encoded)
    path = IMAGES / f"scene_{index:02d}.png"
    path.write_bytes(raw)
    try:
        with Image.open(path) as im:
            im.verify()
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Generated image {index} is invalid: {exc}") from exc
    return path

def ffmpeg(command):
    subprocess.run(command, check=True)

def make_scene_clip(image_path, output_path, index):
    zoom = "min(zoom+0.0007,1.085)" if index % 2 == 0 else "min(zoom+0.0008,1.095)"
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"zoompan=z='{zoom}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={SCENE_SECONDS * 30}:s=1080x1920:fps=30,setsar=1"
    )
    ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-loop", "1", "-i", str(image_path), "-vf", vf,
        "-frames:v", str(SCENE_SECONDS * 30), "-an",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-r", "30", "-movflags", "+faststart",
        str(output_path),
    ])

def ass_time(seconds):
    centiseconds = int(round(seconds * 100))
    return f"{centiseconds // 360000}:{(centiseconds % 360000) // 6000:02d}:{(centiseconds % 6000) // 100:02d}.{centiseconds % 100:02d}"

def create_subtitles(story, path):
    lines = [
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 2\n\n",
        "[V4+ Styles]\n",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n",
        "Style: Default,Noto Sans Devanagari,58,&H00FFFFFF,&H00FFFFFF,&H00101010,&H99000000,1,0,0,0,100,100,0,0,1,4,2,2,70,70,300,1\n\n",
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n",
    ]
    for i, scene in enumerate(story["scenes"]):
        caption = scene["caption"].replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
        lines.append(
            f"Dialogue: 0,{ass_time(i * SCENE_SECONDS)},{ass_time((i + 1) * SCENE_SECONDS)},Default,,0,0,0,,{{\\fad(150,200)}}{caption}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")

def get_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())

def main():
    for p in list(IMAGES.glob("*")) + list(OUT.glob("*.mp4")):
        if p.is_file():
            p.unlink()
    story = generate_story()
    Path("story.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("story.txt").write_text(story["title"] + "\n\n" + "\n".join(s["caption"] for s in story["scenes"]), encoding="utf-8")
    clips = []
    for i, scene in enumerate(story["scenes"], 1):
        print(f"Scene {i}/{SCENE_COUNT}: {scene['caption']}")
        img = generate_image(scene["visual"], story["cast"], i)
        clip = OUT / f"scene_{i:02d}.mp4"
        make_scene_clip(img, clip, i)
        clips.append(clip)
    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in clips), encoding="utf-8")
    combined = OUT / "combined.mp4"
    ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-an", str(combined),
    ])
    subtitles = OUT / "captions.ass"
    create_subtitles(story, subtitles)
    sub_path = str(subtitles.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    final = OUT / "final_short.mp4"
    ffmpeg([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(combined),
        "-vf", f"subtitles='{sub_path}':fontsdir=/usr/share/fonts/truetype/noto",
        "-t", "24", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
        "-movflags", "+faststart", str(final),
    ])
    duration = get_duration(final)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,codec_name", "-of", "json", str(final)],
        capture_output=True, text=True, check=True,
    )
    stream = json.loads(probe.stdout)["streams"][0]
    if not 23.5 <= duration <= 24.5 or (stream.get("width"), stream.get("height"), stream.get("codec_name")) != (1080, 1920, "h264"):
        raise RuntimeError(f"Video verification failed: duration={duration}, stream={stream}")
    print(f"Verified: {duration:.2f}s, 1080x1920 H.264, no voice-over/audio.")
    print("Created output/final_short.mp4")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        sys.exit(1)

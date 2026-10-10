#!/usr/bin/env python3
"""Generate silent, subtitle-free satisfying AI video using a public Hugging Face Gradio Space."""
import json, os, random, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from gradio_client import Client

OUT = Path("output")
OUT.mkdir(exist_ok=True)
IMAGES = OUT / "images"
IMAGES.mkdir(exist_ok=True)
SPACE_ID = os.getenv("HF_SPACE_ID", "ysharma/wan2-1-fast")
SCENE_SECONDS = 2
SCENES = [
    ("Kinetic sand", "A close-up pastel kinetic sand cube is sliced into neat smooth layers, fine grains fall in a controlled cascade, continuous realistic physical movement, macro satisfying ASMR visual."),
    ("Rainbow soap", "A glossy rainbow soap bar is cut into thin uniform curls, colorful shavings fall and stack neatly, continuous realistic physical movement, macro satisfying ASMR visual."),
    ("Paint swirl", "Thick glossy pastel paint slowly folds and spirals into a perfect smooth swirl, beautiful clean gradients and continuous fluid motion, macro satisfying visual."),
    ("Magnetic beads", "Glossy rainbow magnetic spheres roll smoothly into a precise symmetrical grid, each bead clicks into place, continuous coordinated physical movement, macro satisfying visual."),
    ("Domino wave", "A line of colorful dominoes topples in a smooth wave and settles into a perfect geometric pattern, continuous realistic movement, satisfying timing."),
    ("Layered liquids", "Vivid colored liquids pour into a clear vessel and settle into crisp horizontal layers, slow smooth fluid motion without mixing, macro satisfying visual."),
    ("Soft clay press", "A polished press slowly compresses pastel clay discs into a smooth layered cylinder, realistic soft deformation and clean edges, close-up satisfying visual."),
    ("Chocolate snap", "A glossy chocolate bar breaks into even squares that slide into a perfectly aligned stack, crisp realistic material movement, close-up food cinematography."),
]

def make_reference(path, seed):
    """Draw a clean color reference frame locally; no image API is required."""
    random.seed(seed)
    w, h = 512, 896
    im = Image.new("RGB", (w, h), (245, 238, 249))
    pix = im.load()
    top = (248, 230, 247)
    bottom = (215, 231, 250)
    for y in range(h):
        t = y / (h - 1)
        c = tuple(int(top[i] * (1-t) + bottom[i] * t) for i in range(3))
        for x in range(w):
            pix[x, y] = c
    d = ImageDraw.Draw(im, "RGBA")
    palette = [(255,92,135,255),(255,180,70,255),(92,210,190,255),
               (120,140,255,255),(203,115,245,255),(255,220,100,255)]
    # A centered, layered, glossy geometric arrangement provides an image
    # condition for the real image-to-video model.
    for i in range(7):
        margin = 50 + i * 12
        y0 = 250 + i * 42
        col = palette[i % len(palette)]
        d.rounded_rectangle((margin, y0, w-margin, y0+78), radius=28,
                            fill=col, outline=(255,255,255,220), width=4)
        d.ellipse((margin+18, y0+12, margin+58, y0+52), fill=(255,255,255,130))
    im = im.filter(ImageFilter.GaussianBlur(0.25))
    im.save(path, quality=95)
    return path

def ffmpeg(args):
    subprocess.run(args, check=True)

def duration(path):
    r = subprocess.run(
        ["ffprobe","-v","error","-show_entries","format=duration",
         "-of","default=noprint_wrappers=1:nokey=1",str(path)],
        capture_output=True,text=True,check=True)
    return float(r.stdout.strip())

def make_video_clip(image_path, output_path, prompt, idx):
    negative = "still image, static frame, slideshow, frozen motion, text, subtitles, captions, words, logo, watermark, speech, music, flicker, distorted objects, low quality"
    print(f"Generating real AI video clip {idx}/{len(chosen_scenes)} using {SPACE_ID}")
    client = Client(SPACE_ID, verbose=True)
    # The Space's current API inputs are: image, prompt, height, width,
    # negative prompt, duration, guidance scale, steps, seed, randomize seed.
    result = client.predict(
        str(image_path), prompt, 512, 288, negative,
        float(SCENE_SECONDS), 1.0, 4, random.randint(1, 2_000_000_000),
        True, api_name="/generate-video"
    )
    value = result[0] if isinstance(result, (tuple, list)) else result
    if isinstance(value, dict):
        value = value.get("path") or value.get("video") or value.get("url")
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"Unexpected Hugging Face video result: {result!r}")
    source = Path(value)
    if not source.is_file() or source.stat().st_size < 10000:
        raise RuntimeError("AI video output file is missing or too small.")
    ffmpeg([
        "ffmpeg","-hide_banner","-loglevel","error","-y","-i",str(source),
        "-t",str(SCENE_SECONDS),
        "-vf","scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an","-c:v","libx264","-preset","veryfast","-crf","22",
        "-pix_fmt","yuv420p","-r","30","-movflags","+faststart",str(output_path)
    ])
    if not output_path.is_file() or output_path.stat().st_size < 10000:
        raise RuntimeError("Failed to normalize AI-generated clip.")

def main():
    global chosen_scenes
    for p in IMAGES.glob("*"):
        if p.is_file(): p.unlink()
    for p in OUT.glob("*.mp4"):
        p.unlink()
    chosen_scenes = random.sample(SCENES, 4)
    title = "Oddly Satisfying AI Visuals #Shorts"
    meta = {"title": title, "concepts": [x[0] for x in chosen_scenes],
            "scenes": [{"name": n, "visual": p} for n,p in chosen_scenes]}
    Path("story.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("story.txt").write_text(title + "\n" + "\n".join(n for n,_ in chosen_scenes), encoding="utf-8")
    clips = []
    for i, (name, prompt) in enumerate(chosen_scenes, 1):
        image_path = make_reference(IMAGES / f"scene_{i:02d}.png", random.randint(0, 999999))
        clip = OUT / f"scene_{i:02d}.mp4"
        make_video_clip(image_path, clip, prompt, i)
        clips.append(clip)
    listing = OUT / "concat.txt"
    listing.write_text("".join(f"file '{p.resolve()}'\n" for p in clips), encoding="utf-8")
    final = OUT / "final_short.mp4"
    ffmpeg(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0",
            "-i",str(listing),"-t","8","-an","-c:v","libx264","-preset","veryfast",
            "-crf","21","-pix_fmt","yuv420p","-r","30","-movflags","+faststart",str(final)])
    stream = json.loads(subprocess.run(
        ["ffprobe","-v","error","-select_streams","v:0","-show_entries","stream=width,height,codec_name",
         "-of","json",str(final)],capture_output=True,text=True,check=True).stdout)["streams"][0]
    dur = duration(final)
    if not (7.4 <= dur <= 8.6) or (stream.get("width"),stream.get("height"),stream.get("codec_name")) != (1080,1920,"h264"):
        raise RuntimeError(f"Video verification failed: duration={dur}, stream={stream}")
    print(f"Verified {dur:.2f}s 1080x1920 silent AI video; no subtitles or captions.")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("FATAL:", exc, file=sys.stderr)
        sys.exit(1)

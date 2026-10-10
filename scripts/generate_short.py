#!/usr/bin/env python3
"""Create silent, subtitle-free satisfying AI video Shorts using a hosted video model."""
import base64, json, os, random, subprocess, sys, time
from pathlib import Path
import requests
from PIL import Image
from gradio_client import Client

ACCOUNT=os.getenv('CLOUDFLARE_ACCOUNT_ID','').strip()
TOKEN=os.getenv('CLOUDFLARE_API_TOKEN','').strip()
if not ACCOUNT or not TOKEN:
    raise SystemExit('Missing CLOUDFLARE_ACCOUNT_ID or CLOUDFLARE_API_TOKEN.')
API=f'https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/run'
IMAGE_MODEL='@cf/black-forest-labs/flux-1-schnell'
HEADERS={'Authorization':f'Bearer {TOKEN}','Content-Type':'application/json'}
OUT=Path('output'); IMAGES=OUT/'images'; OUT.mkdir(exist_ok=True); IMAGES.mkdir(exist_ok=True)
SCENE_COUNT=4
SCENE_SECONDS=3
HF_SPACE_ID=os.getenv('HF_SPACE_ID','ysharma/wan2-1-fast').strip()

# No people, story text, captions, or subtitles: pure visual satisfaction.
IDEAS=[
 ('Perfect Kinetic Sand Slicing','A razor-sharp clean blade slowly slices a perfect pastel kinetic sand cube into smooth, even layers; tiny grains cascade neatly, macro close-up, soft studio lighting, satisfying symmetry.'),
 ('Rainbow Soap Cutting','A gloved hand slowly cuts a glossy rainbow soap bar into thin, uniform curls; clean crisp cuts, colorful shavings fall into a tidy pile, extreme macro, relaxing studio setup.'),
 ('Glass Fruit Slice','A translucent jewel-like glass orange is sliced cleanly with a polished knife; the cut reveals beautiful glowing geometric citrus segments, no shards, no danger, macro product cinematography.'),
 ('Perfect Paint Swirl','Thick glossy pastel paint ribbons fold and spiral together in a perfect slow swirl on a smooth surface; clean gradients, hypnotic symmetry, no text, macro satisfying art.'),
 ('Magnetic Beads Pattern','Tiny glossy magnetic spheres glide into a precise rainbow grid and form a perfectly symmetrical pattern; smooth coordinated movement, close-up, satisfying mechanical precision.'),
 ('Chocolate Snap and Stack','A glossy chocolate bar breaks into perfectly even squares and stacks into a neat geometric tower; rich chocolate texture, clean edges, close-up food cinematography.'),
 ('Colorful Liquid Layers','Vibrant colored liquids flow into a clear glass vessel and settle into crisp layered bands without mixing; smooth fluid motion, clean studio background, macro view.'),
 ('Soft Clay Press','A polished press slowly compresses a stack of colorful soft clay discs into a perfectly smooth layered cylinder; gentle deformation, clean edges, close-up tactile texture.'),
 ('Domino Rainbow Wave','A perfectly aligned row of colorful dominoes topples in a smooth controlled wave and lands into a flawless geometric pattern; satisfying timing, bright clean tabletop.'),
 ('Crystal Ice Cube Arrangement','Transparent colored ice-like cubes slide across a glossy surface and click into a perfectly aligned gradient grid; condensation, sparkling highlights, precise smooth motion.')
]

def request_image(prompt, attempts=4):
    for i in range(attempts):
        try:
            r=requests.post(f'{API}/{IMAGE_MODEL}',headers=HEADERS,json={'prompt':prompt,'steps':4},timeout=180)
            if r.status_code==429 and i+1<attempts:
                time.sleep(8*(i+1)); continue
            r.raise_for_status(); data=r.json(); encoded=data.get('result',{}).get('image')
            if not encoded: raise RuntimeError('Cloudflare FLUX response has no result.image.')
            if encoded.startswith('data:') and ',' in encoded: encoded=encoded.split(',',1)[1]
            return base64.b64decode(encoded)
        except (requests.Timeout,requests.ConnectionError) as e:
            if i+1==attempts: raise RuntimeError(f'Cloudflare image request failed: {e}')
            time.sleep(5*(i+1))
    raise RuntimeError('Image generation failed after retries.')

def ffmpeg(args): subprocess.run(args,check=True)

def make_image(prompt, idx):
    full=('Photorealistic macro product video reference frame for a relaxing satisfying visual. '+prompt+
          ' Portrait 9:16 composition, crisp tactile materials, beautiful soft studio lighting, centered subject, uncluttered background. '
          'Absolutely no words, letters, captions, subtitles, logos, watermark, humans or hands unless essential to the described action.')
    path=IMAGES/f'scene_{idx:02d}.png'; path.write_bytes(request_image(full))
    try:
        with Image.open(path) as im: im.verify()
    except Exception as e:
        path.unlink(missing_ok=True); raise RuntimeError(f'Invalid generated reference image: {e}')
    return path

def make_video_clip(image_path, output_path, prompt, idx):
    video_prompt=('Generate a real moving 3-second satisfying macro video, not a still image or slideshow. '
      +prompt+' Show clear continuous physical movement from beginning to end, smooth realistic material motion, crisp tactile details, stable camera, soft studio lighting. '
      'Pure visual ASMR-style content. No text, subtitles, captions, speech, people, logos, watermark, or soundtrack.')
    negative='still image, static frame, slideshow, frozen motion, text, subtitles, captions, words, logo, watermark, speech, music, flicker, distorted objects, low quality'
    print(f'Generating genuine AI video clip {idx}/{SCENE_COUNT} using {HF_SPACE_ID}')
    client=Client(HF_SPACE_ID,verbose=True)
    result=client.predict(str(image_path),video_prompt,512,288,negative,float(SCENE_SECONDS),1.0,4,random.randint(1,2_000_000_000),True,api_name='/generate-video')
    value=result[0] if isinstance(result,(tuple,list)) else result
    if isinstance(value,dict): value=value.get('path') or value.get('video') or value.get('url')
    if not isinstance(value,str) or not value: raise RuntimeError(f'Unexpected video model result: {result!r}')
    source=Path(value)
    if not source.is_file() or source.stat().st_size<10000: raise RuntimeError('AI video output file is missing or too small.')
    ffmpeg(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(source),'-t',str(SCENE_SECONDS),'-vf','scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30','-an','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(output_path)])
    if not output_path.is_file() or output_path.stat().st_size<10000: raise RuntimeError('Failed to normalize AI-generated clip.')

def duration(path):
    r=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],capture_output=True,text=True,check=True)
    return float(r.stdout.strip())

def main():
    for p in list(IMAGES.glob('*'))+list(OUT.glob('*.mp4')):
        if p.is_file(): p.unlink()
    chosen=random.sample(IDEAS,SCENE_COUNT)
    title='Oddly Satisfying AI Visuals 🤯 #Shorts'
    meta={'title':title,'concepts':[x[0] for x in chosen],'scenes':[{'name':n,'visual':v} for n,v in chosen]}
    Path('story.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    Path('story.txt').write_text(title+'\n'+'\n'.join(n for n,_ in chosen),encoding='utf-8')
    clips=[]
    for i,(name,prompt) in enumerate(chosen,1):
        img=make_image(prompt,i); clip=OUT/f'scene_{i:02d}.mp4'; make_video_clip(img,clip,prompt,i); clips.append(clip)
    listing=OUT/'concat.txt'; listing.write_text(''.join(f"file '{p.resolve()}'\n" for p in clips),encoding='utf-8')
    final=OUT/'final_short.mp4'
    ffmpeg(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(listing),'-t',str(SCENE_COUNT*SCENE_SECONDS),'-an','-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-r','30','-movflags','+faststart',str(final)])
    probe=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,codec_name','-of','json',str(final)],capture_output=True,text=True,check=True)
    stream=json.loads(probe.stdout)['streams'][0]; dur=duration(final)
    if not (11.4<=dur<=12.6) or (stream.get('width'),stream.get('height'),stream.get('codec_name'))!=(1080,1920,'h264'):
        raise RuntimeError(f'Video verification failed: duration={dur}, stream={stream}')
    print(f'Verified {dur:.2f}s 1080x1920 silent video. No subtitles or captions were added.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('FATAL:',exc,file=sys.stderr); sys.exit(1)

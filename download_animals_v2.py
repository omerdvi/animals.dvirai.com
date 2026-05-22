#!/usr/bin/env python3
"""
Download animal images and sounds for toddler game - v2.
Images: Bing image search -> best result -> square crop (1:1)
Sounds: YouTube (yt-dlp) -> 3-second MP3 trim
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import subprocess
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    sys.exit(1)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "animals.json"
IMAGES_DIR = BASE_DIR / "images"
SOUNDS_DIR = BASE_DIR / "sounds"
LOG_FILE = BASE_DIR / "data" / "download_log.txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def safe_filename(name):
    return re.sub(r'[^\w\u0590-\u05ff.-]', '_', name).strip('_')

def bing_search_image(query, min_width=400):
    """Search Bing Images and return the best image URL."""
    encoded = urllib.parse.quote(query)
    url = f"https://www.bing.com/images/search?q={encoded}&form=HDRSC2&first=1"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log(f"  Bing search error for '{query}': {e}")
        return None

    # Bing embeds image URLs in murl attributes
    murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)
    if not murls:
        murls = re.findall(r'"murl":"(https?://[^"]+)"', html)
    if not murls:
        # Fallback: find any image URLs in the HTML
        murls = re.findall(r'https?://[^\s\"<>]+\.(?:jpg|jpeg|png|webp)', html)

    # Filter out small/tracking URLs and prefer direct image hosts
    good_urls = []
    for u in murls:
        # Skip obvious non-photo URLs
        if any(bad in u.lower() for bad in ['icon', 'logo', 'avatar', 'thumb']):
            continue
        good_urls.append(u)

    if not good_urls:
        log(f"  No suitable Bing image for '{query}'")
        return None

    return good_urls[0]

def download_image(url, dest_path):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        log(f"  Image download error: {e}")
        return False

def crop_to_square(img_path, dest_path, size=600):
    try:
        with Image.open(img_path) as im:
            w, h = im.size
            if w > h:
                left = (w - h) // 2
                right = left + h
                top = 0
                bottom = h
            else:
                top = (h - w) // 2
                bottom = top + w
                left = 0
                right = w
            im_cropped = im.crop((left, top, right, bottom))
            im_resized = im_cropped.resize((size, size), Image.LANCZOS)
            if im_resized.mode in ("RGBA", "P"):
                im_resized = im_resized.convert("RGB")
            im_resized.save(dest_path, "JPEG", quality=90)
        return True
    except Exception as e:
        log(f"  Image crop error: {e}")
        return False

def download_sound_yt(animal_en, dest_path, duration_sec=3, timeout=90):
    search_query = f"{animal_en} sound"
    temp_path = str(dest_path).replace(".mp3", "_temp.%(ext)s")
    
    # Clean old temp files
    temp_dir = os.path.dirname(temp_path)
    temp_base = os.path.basename(temp_path).replace("_temp.%(ext)s", "")
    if os.path.isdir(temp_dir):
        for f in os.listdir(temp_dir):
            if f.startswith(temp_base) and f.endswith((".mp3", ".webm", ".m4a", ".ogg", ".opus")):
                try:
                    os.remove(os.path.join(temp_dir, f))
                except:
                    pass
    
    cmd = [
        "yt-dlp",
        f"ytsearch1:{search_query}",
        "-f", "bestaudio",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", temp_path,
        "--no-playlist",
        "--quiet",
        "--no-warnings"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0:
            log(f"  yt-dlp failed for {animal_en}: {result.stderr[:200]}")
            return False
    except subprocess.TimeoutExpired:
        log(f"  yt-dlp timeout for {animal_en}")
        return False
    except Exception as e:
        log(f"  yt-dlp error for {animal_en}: {e}")
        return False

    # Find downloaded file
    temp_files = [f for f in os.listdir(temp_dir) if f.startswith(temp_base)]
    if not temp_files:
        log(f"  No temp file found for {animal_en}")
        return False
    
    temp_file = os.path.join(temp_dir, temp_files[0])
    
    # Trim with ffmpeg
    final_trimmed = str(dest_path).replace(".mp3", "_trimmed.mp3")
    trim_cmd = [
        "ffmpeg", "-y", "-i", temp_file,
        "-t", str(duration_sec),
        "-af", "afade=t=out:st=2:d=1",
        "-ar", "22050",
        final_trimmed
    ]
    try:
        subprocess.run(trim_cmd, capture_output=True, timeout=30)
        if os.path.exists(final_trimmed):
            os.replace(final_trimmed, str(dest_path))
        if os.path.exists(temp_file) and temp_file != str(dest_path):
            try:
                os.remove(temp_file)
            except:
                pass
        return True
    except Exception as e:
        log(f"  ffmpeg trim error for {animal_en}: {e}")
        return False

def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0
    for cat in data["categories"].values():
        total += len(cat["animals"])

    log(f"Starting v2 download of {total} animals...")
    log("=" * 50)

    done_images = 0
    done_sounds = 0
    failed_images = []
    failed_sounds = []

    for cat_key, cat_data in data["categories"].items():
        log(f"\nCategory: {cat_data['hebrew']}")
        for animal in cat_data["animals"]:
            he = animal["hebrew"]
            en = animal["english"]
            search = animal["search"]
            safe = safe_filename(he)
            
            img_path = IMAGES_DIR / f"{safe}.jpg"
            snd_path = SOUNDS_DIR / f"{safe}.mp3"

            log(f"[{he} / {en}]")

            # --- Image ---
            if not img_path.exists():
                log(f"  Searching image: {search}")
                img_url = bing_search_image(search)
                if img_url:
                    temp_img = IMAGES_DIR / f"{safe}_raw.jpg"
                    if download_image(img_url, temp_img):
                        if crop_to_square(temp_img, img_path, size=600):
                            log(f"  Image OK: {img_path}")
                            done_images += 1
                            if temp_img.exists():
                                temp_img.unlink()
                        else:
                            failed_images.append(he)
                            if temp_img.exists():
                                temp_img.unlink()
                    else:
                        failed_images.append(he)
                        if temp_img.exists():
                            temp_img.unlink()
                else:
                    failed_images.append(he)
            else:
                log(f"  Image already exists, skipping.")
                done_images += 1

            # --- Sound ---
            if not snd_path.exists():
                log(f"  Searching sound: {en} sound")
                if download_sound_yt(en, snd_path, duration_sec=3):
                    log(f"  Sound OK: {snd_path}")
                    done_sounds += 1
                else:
                    failed_sounds.append(he)
            else:
                log(f"  Sound already exists, skipping.")
                done_sounds += 1

            time.sleep(2)

    log("\n" + "=" * 50)
    log(f"Done! Images: {done_images}/{total}, Sounds: {done_sounds}/{total}")
    if failed_images:
        log(f"Failed images ({len(failed_images)}): {', '.join(failed_images)}")
    if failed_sounds:
        log(f"Failed sounds ({len(failed_sounds)}): {', '.join(failed_sounds)}")

if __name__ == "__main__":
    main()

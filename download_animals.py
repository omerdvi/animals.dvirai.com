#!/usr/bin/env python3
"""
Download animal images and sounds for toddler game.
Images: Wikimedia Commons API (thumbnails) -> square crop (1:1)
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
from io import BytesIO

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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AnimalGameBot/1.0"
}

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def safe_filename(name):
    """Create a safe filename from Hebrew/English name."""
    return re.sub(r'[^\w\u0590-\u05ff.-]', '_', name).strip('_')

def wikimedia_search_image(query, min_width=400):
    """Search Wikimedia Commons and return the best thumbnail URL."""
    encoded = urllib.parse.quote(query)
    url = (
        f"https://commons.wikimedia.org/w/api.php?"
        f"action=query&generator=search&gsrnamespace=6"
        f"&gsrsearch={encoded}&prop=imageinfo"
        f"&iiprop=url|size|mime|thumburl"
        f"&iiurlwidth=800&format=json&gsrlimit=10"
    )
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log(f"  Wikimedia API error for '{query}': {e}")
        return None

    pages = data.get("query", {}).get("pages", {})
    candidates = []
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        mime = ii.get("mime", "")
        if mime.startswith("image/") and not mime.endswith("svg") and not mime.endswith("svg+xml"):
            w = ii.get("width", 0)
            h = ii.get("height", 0)
            # Prefer thumburl (800px) for lower rate-limit risk
            img_url = ii.get("thumburl") or ii.get("url")
            if img_url and w >= min_width and h >= min_width:
                candidates.append((w * h, w, h, img_url))

    if not candidates:
        log(f"  No suitable Wikimedia image for '{query}'")
        return None

    candidates.sort(reverse=True)
    return candidates[0][3]

def download_image(url, dest_path, retries=3):
    """Download image to path with retry on 429."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            with open(dest_path, "wb") as f:
                f.write(data)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                sleep_time = 10 * (attempt + 1)
                log(f"  Rate limited (429), sleeping {sleep_time}s before retry {attempt+1}...")
                time.sleep(sleep_time)
                continue
            log(f"  Image download error: {e}")
            return False
        except Exception as e:
            log(f"  Image download error: {e}")
            return False
    return False

def crop_to_square(img_path, dest_path, size=600):
    """Open image, crop to center square, resize to size x size."""
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
    """Download animal sound from YouTube and trim to duration_sec."""
    search_query = f"{animal_en} sound"
    temp_path = str(dest_path).replace(".mp3", "_temp.%(ext)s")
    
    # Clean up any old temp files first
    temp_dir = os.path.dirname(temp_path)
    temp_base = os.path.basename(temp_path).replace("_temp.%(ext)s", "")
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

    # Find the downloaded temp file (yt-dlp replaces %(ext)s with actual ext)
    temp_files = []
    for f in os.listdir(temp_dir):
        if f.startswith(temp_base):
            temp_files.append(f)
    
    if not temp_files:
        log(f"  No temp file found for {animal_en}")
        return False
    
    temp_file = os.path.join(temp_dir, temp_files[0])
    
    # If it's already mp3, just copy and trim. If not, convert with ffmpeg.
    final_trimmed = str(dest_path).replace(".mp3", "_trimmed.mp3")
    trim_cmd = [
        "ffmpeg", "-y", "-i", temp_file,
        "-t", str(duration_sec),
        "-af", "afade=t=out:st=2:d=1",  # 1s fade out at end
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

    log(f"Starting download of {total} animals...")
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
                img_url = wikimedia_search_image(search)
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

            # Sleep to avoid rate limiting
            time.sleep(3)

    log("\n" + "=" * 50)
    log(f"Done! Images: {done_images}/{total}, Sounds: {done_sounds}/{total}")
    if failed_images:
        log(f"Failed images ({len(failed_images)}): {', '.join(failed_images)}")
    if failed_sounds:
        log(f"Failed sounds ({len(failed_sounds)}): {', '.join(failed_sounds)}")

if __name__ == "__main__":
    main()

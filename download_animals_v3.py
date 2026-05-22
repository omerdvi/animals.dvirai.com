#!/usr/bin/env python3
"""
Download animal images for toddler game - v3.
Strategy: Bing image search (photo filter) -> download top 3 candidates
-> pick most square-ish real photo -> scale-to-fit with padding (1:1).
This ensures the ENTIRE animal is always visible, never cropped.
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

def log(msg):
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def safe_filename(name):
    return re.sub(r'[^\w\u0590-\u05ff.-]', '_', name).strip('_')

def bing_search_image_urls(query, max_results=5):
    """Search Bing Images with photo filter, return list of image URLs."""
    encoded = urllib.parse.quote(query)
    # filterui:photo-photo = only photographs
    url = f"https://www.bing.com/images/search?q={encoded}&qft=+filterui:photo-photo&form=HDRSC2&first=1"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
    except Exception as e:
        log(f"  Bing search error for '{query}': {e}")
        return []

    # Extract murl (media URL) from Bing results
    murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)
    if not murls:
        murls = re.findall(r'"murl":"(https?://[^"]+)"', html)
    if not murls:
        murls = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|webp)', html)

    # Deduplicate and filter out small/tracking URLs
    seen = set()
    results = []
    for u in murls:
        if u in seen:
            continue
        seen.add(u)
        # Skip obvious non-photo URLs
        lower = u.lower()
        if any(bad in lower for bad in ['icon', 'logo', 'avatar', 'thumb', 'badge', 'button', 'emoji']):
            continue
        results.append(u)
        if len(results) >= max_results:
            break
    return results

def download_image(url, dest_path, timeout=30):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        log(f"  Image download error: {e}")
        return False

def try_load_image(path):
    """Try to open image, return (success, width, height)."""
    try:
        with Image.open(path) as im:
            return True, im.size[0], im.size[1]
    except Exception:
        return False, 0, 0

def aspect_ratio_distance(w, h):
    """Return how far aspect ratio is from 1:1 (0 = perfect square)."""
    if h == 0:
        return float('inf')
    ratio = w / h
    return abs(ratio - 1.0)

def pad_to_square(src_path, dest_path, size=600, bg_color=(255, 255, 255)):
    """
    Scale image to fit inside size x size while preserving aspect ratio,
    then paste centered on a square canvas. This ensures NOTHING is cut off.
    """
    try:
        with Image.open(src_path) as im:
            # Convert to RGB (remove alpha or palette issues)
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")

            w, h = im.size

            # Determine scale to fit inside size x size
            scale = min(size / w, size / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Resize using high-quality resampling
            im_resized = im.resize((new_w, new_h), Image.LANCZOS)

            # Create square canvas with background color
            canvas = Image.new("RGB", (size, size), bg_color)

            # Paste centered
            x = (size - new_w) // 2
            y = (size - new_h) // 2
            canvas.paste(im_resized, (x, y))

            canvas.save(dest_path, "JPEG", quality=90)
        return True
    except Exception as e:
        log(f"  Pad-to-square error: {e}")
        return False

def main():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = 0
    for cat in data["categories"].values():
        total += len(cat["animals"])

    log(f"Starting v3 download of {total} animals...")
    log("Strategy: padding (scale-to-fit) instead of cropping")
    log("=" * 50)

    done_images = 0
    failed_images = []

    for cat_key, cat_data in data["categories"].items():
        log(f"\nCategory: {cat_data['hebrew']}")
        for animal in cat_data["animals"]:
            he = animal["hebrew"]
            en = animal["english"]
            search = animal["search"]
            safe = safe_filename(he)
            
            img_path = IMAGES_DIR / f"{safe}.jpg"

            log(f"[{he} / {en}]")

            # Always re-download in v3 to ensure quality
            log(f"  Searching images: {search}")
            urls = bing_search_image_urls(search, max_results=5)
            if not urls:
                failed_images.append(he)
                log(f"  No Bing results found")
                continue

            best_candidate = None
            best_score = float('inf')
            best_temp_path = None

            for idx, url in enumerate(urls):
                temp_path = IMAGES_DIR / f"{safe}_raw_{idx}.jpg"
                if download_image(url, temp_path):
                    ok, w, h = try_load_image(temp_path)
                    if ok and w >= 200 and h >= 200:
                        dist = aspect_ratio_distance(w, h)
                        # Prefer images closer to square
                        if dist < best_score:
                            best_score = dist
                            best_candidate = temp_path
                            log(f"  Candidate {idx}: {w}x{h}, aspect_dist={dist:.2f} (BEST)")
                        else:
                            log(f"  Candidate {idx}: {w}x{h}, aspect_dist={dist:.2f}")
                    else:
                        log(f"  Candidate {idx}: invalid or too small")
                else:
                    log(f"  Candidate {idx}: download failed")

            if best_candidate:
                if pad_to_square(best_candidate, img_path, size=600, bg_color=(255, 255, 255)):
                    log(f"  Image OK (padded): {img_path}")
                    done_images += 1
                else:
                    failed_images.append(he)
            else:
                failed_images.append(he)
                log(f"  No valid candidate image found")

            # Clean up all temp files for this animal
            for idx in range(len(urls)):
                temp_path = IMAGES_DIR / f"{safe}_raw_{idx}.jpg"
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except:
                        pass

            time.sleep(4)

    log("\n" + "=" * 50)
    log(f"Done! Images: {done_images}/{total}")
    if failed_images:
        log(f"Failed images ({len(failed_images)}): {', '.join(failed_images)}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Fix animal images v2: pad-to-square with smart Wikipedia/Commons search + retry.
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.parse
from pathlib import Path
from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
IMAGES_DIR = BASE_DIR / "images"
DATA_FILE = BASE_DIR / "data" / "animals.json"
TARGET_SIZE = 600

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

WIKI_HEADERS = {"User-Agent": "AnimalGame/1.0 (educational toddler game)"}

ANIMAL_WIKI = {
    "כלב": "Dog", "חתול": "Cat", "פרה": "Cattle", "כבשה": "Sheep",
    "סוס": "Horse", "תרנגול": "Rooster", "אוז": "Goose", "ברווז": "Duck",
    "חמור": "Donkey", "עז": "Goat",
    "אריה": "Lion", "פיל": "Elephant", "זברה": "Zebra", "קוף": "Monkey",
    "ג'ירפה": "Giraffe", "נמר": "Leopard", "היפופוטם": "Hippopotamus",
    "קרניף": "Rhinoceros", "טיגריס": "Tiger", "קנגורו": "Kangaroo",
    "דולפין": "Common dolphin", "לוויתן": "Humpback whale",
    "כריש": "Great white shark", "תמנון": "Octopus", "סוס ים": "Seahorse",
    "מדוזה": "Jellyfish", "צב ים": "Sea turtle", "דג שונית": "Clownfish",
    "תוכי": "Parrot", "יונה": "Columbidae", "נשר": "Eagle",
    "פלמינגו": "Flamingo", "ינשוף": "Owl", "פינגווין": "Penguin",
    "חסידה": "Stork",
    "דוב": "Brown bear", "שועל": "Red fox", "צבי": "Deer",
    "סנאי": "Red squirrel", "ארנב": "Rabbit", "קיפוד": "Hedgehog",
    "זאב": "Wolf", "חזיר בר": "Wild boar",
    "נחש": "Snake", "תנין": "Crocodile", "צפרדע": "Frog",
    "לטאה": "Lizard", "צב": "Turtle", "תלולית": "Salamander",
    "איגואנה": "Iguana",
}

def safe_filename(name):
    return re.sub(r'[^\w\u0590-\u05ff.-]', '_', name).strip('_')

def fetch_url(url, headers=None, timeout=15, retries=3):
    """Fetch URL with retry on 429 and other transient errors."""
    h = {**HEADERS, **(headers or {})}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                sleep_time = 10 * (attempt + 1)
                print(f"    429 → waiting {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            raise
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise
    return None

def get_wikipedia_image(title):
    """Get the main image for a Wikipedia article title."""
    try:
        # First, get page ID
        url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.parse.quote(title)}&prop=pageimages&pithumbsize=800&format=json"
        data = json.loads(fetch_url(url, WIKI_HEADERS, timeout=10).decode('utf-8'))
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if "thumbnail" in page:
                thumb = page["thumbnail"]
                return thumb.get("source"), thumb.get("width", 0), thumb.get("height", 0)
    except Exception as e:
        print(f"    Wikipedia error: {e}")
    return None, 0, 0

def search_wikimedia(term):
    """Search Wikimedia Commons for images."""
    try:
        url = f"https://commons.wikimedia.org/w/api.php?action=query&list=search&srnamespace=6&srsearch={urllib.parse.quote(term)}&srlimit=8&format=json"
        data = json.loads(fetch_url(url, WIKI_HEADERS, timeout=15).decode('utf-8'))
        results = data.get("query", {}).get("search", [])
        return [r["title"] for r in results]
    except Exception as e:
        print(f"    Commons search error: {e}")
        return []

def get_commons_image_url(filename):
    """Get direct image URL from Commons filename."""
    try:
        url = f"https://commons.wikimedia.org/w/api.php?action=query&titles={urllib.parse.quote(filename)}&prop=imageinfo&iiprop=url|size|mime&iilimit=1&format=json"
        data = json.loads(fetch_url(url, WIKI_HEADERS, timeout=15).decode('utf-8'))
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                mime = info.get("mime", "")
                if mime.startswith("image/"):
                    return info.get("url"), info.get("width", 0), info.get("height", 0)
    except Exception as e:
        print(f"    Commons url error: {e}")
    return None, 0, 0

def download_image(url, dest_path):
    """Download image to file."""
    try:
        data = fetch_url(url, HEADERS, timeout=20, retries=2)
        if data is None:
            return False
        with open(dest_path, "wb") as f:
            f.write(data)
        # Validate
        img = Image.open(dest_path)
        img.verify()
        return True
    except Exception as e:
        print(f"    Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

def pad_to_square(src_path, dst_path, size=TARGET_SIZE, bg=(255, 255, 255)):
    """Scale to fit inside square, paste centered on canvas. NOTHING is cut off."""
    try:
        with Image.open(src_path) as im:
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            scale = min(size / w, size / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            im_resized = im.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGB", (size, size), bg)
            x = (size - new_w) // 2
            y = (size - new_h) // 2
            canvas.paste(im_resized, (x, y))
            canvas.save(dst_path, "JPEG", quality=92)
        return True
    except Exception as e:
        print(f"    Pad error: {e}")
        return False

def process_animal(hebrew_name, search_term, wiki_title=None):
    """Download and process one animal."""
    safe = safe_filename(hebrew_name)
    dest_path = IMAGES_DIR / f"{safe}.jpg"
    temp_path = IMAGES_DIR / f"{safe}_temp.jpg"
    
    print(f"\n[{hebrew_name}] → '{search_term}'")
    
    found = False
    
    # Strategy 1: Wikipedia article image (most reliable)
    if wiki_title and not found:
        print(f"  Strategy 1: Wikipedia article '{wiki_title}'")
        img_url, w, h = get_wikipedia_image(wiki_title)
        if img_url and w >= 300 and h >= 300:
            print(f"    Found: {w}x{h}")
            if download_image(img_url, temp_path):
                if pad_to_square(temp_path, dest_path):
                    print(f"  ✓ SUCCESS (Wikipedia)")
                    found = True
                else:
                    print(f"    Pad failed")
    
    # Strategy 2: Wikimedia Commons search
    if not found:
        print(f"  Strategy 2: Wikimedia Commons search")
        titles = search_wikimedia(search_term + " animal")
        for title in titles[:5]:
            img_url, w, h = get_commons_image_url(title)
            if not img_url or w < 300 or h < 300:
                continue
            print(f"    Found: {title} ({w}x{h})")
            if download_image(img_url, temp_path):
                if pad_to_square(temp_path, dest_path):
                    print(f"  ✓ SUCCESS (Commons)")
                    found = True
                    break
                else:
                    print(f"    Pad failed")
            time.sleep(0.5)
    
    # Cleanup temp
    if temp_path.exists():
        try:
            temp_path.unlink()
        except:
            pass
    
    if not found:
        print(f"  ✗ FAILED")
    
    return found

def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    total = 0
    for cat_data in data["categories"].values():
        total += len(cat_data["animals"])
    
    print(f"=" * 60)
    print(f"Fixing {total} animals with pad-to-square (white bg)")
    print(f"=" * 60)
    
    success = 0
    fail = 0
    failed_list = []
    
    for cat_key, cat_data in data["categories"].items():
        cat_name = cat_data.get("hebrew", cat_key)
        print(f"\n{'='*60}")
        print(f"CATEGORY: {cat_name}")
        print(f"{'='*60}")
        
        for animal in cat_data["animals"]:
            he = animal["hebrew"]
            search = animal.get("search", animal.get("english", he))
            wiki = ANIMAL_WIKI.get(he)
            
            time.sleep(1.5)  # Be polite
            
            if process_animal(he, search, wiki):
                success += 1
            else:
                fail += 1
                failed_list.append(he)
    
    print(f"\n{'='*60}")
    print(f"DONE! Success: {success}/{total}, Failed: {fail}")
    if failed_list:
        print(f"Failed: {', '.join(failed_list)}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

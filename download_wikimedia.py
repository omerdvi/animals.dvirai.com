#!/usr/bin/env python3
"""
Download animal images from Wikimedia Commons and process to 600x600 square.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.parse
from PIL import Image

# Animals missing images (Hebrew name -> English search term)
ANIMALS = {
    "איגואנה": "iguana portrait",
    "ארנב": "rabbit cute",
    "ג'ירפה": "giraffe close up",
    "דג_שונית": "tropical fish",
    "דוב": "bear brown",
    "דולפין": "dolphin jumping",
    "היפופוטם": "hippopotamus",
    "זאב": "wolf portrait",
    "זברה": "zebra portrait",
    "חזיר_בר": "wild boar",
    "חסידה": "stork white",
    "טיגריס": "tiger portrait",
    "יונה": "dove white",
    "ינשוף": "owl cute",
    "כריש": "great white shark",
    "לוויתן": "humpback whale",
    "לטאה": "lizard green",
    "מדוזה": "jellyfish blue",
    "נחש": "snake cobra",
    "נמר": "leopard portrait",
    "נשר": "eagle golden",
    "סוס_ים": "seahorse",
    "סנאי": "squirrel red",
    "פינגווין": "penguin emperor",
    "פלמינגו": "flamingo pink",
    "צב": "turtle green",
    "צב_ים": "sea turtle",
    "צבי": "gazelle portrait",
    "צפרדע": "frog green",
    "קוף": "monkey chimpanzee",
    "קיפוד": "hedgehog cute",
    "קנגורו": "kangaroo red",
    "קרניף": "rhinoceros white",
    "שועל": "fox red",
    "תוכי": "parrot colorful",
    "תלולית": "starfish sea",
    "תמנון": "octopus underwater",
    "תנין": "crocodile nile",
}

IMAGES_DIR = "images"
TARGET_SIZE = 600

def search_wikimedia(term):
    """Search Wikimedia Commons for images matching term."""
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srnamespace": 6,
        "srsearch": term,
        "srlimit": 10,
        "format": "json",
    }
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("query", {}).get("search", [])
        return [r["title"] for r in results]
    except Exception as e:
        print(f"  Search error: {e}")
        return []

def get_image_url(filename):
    """Get direct image URL and size from Wikimedia."""
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": filename,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
        "format": "json",
    }
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    
    try:
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                mime = info.get("mime", "")
                if mime.startswith("image/"):
                    return info.get("url"), info.get("width", 0), info.get("height", 0)
        return None, 0, 0
    except Exception as e:
        print(f"  Image info error: {e}")
        return None, 0, 0

def download_image(url, dest_path):
    """Download image from URL."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        
        # Validate it's an image
        with open(dest_path, "wb") as f:
            f.write(data)
        
        # Check with PIL
        img = Image.open(dest_path)
        img.verify()
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

def make_square(src_path, dst_path, size=TARGET_SIZE):
    """Process image to square with padding (like the original game)."""
    try:
        img = Image.open(src_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        w, h = img.size
        
        # Crop to center square
        if w > h:
            left = (w - h) // 2
            img = img.crop((left, 0, left + h, h))
        elif h > w:
            top = (h - w) // 2
            img = img.crop((0, top, w, top + w))
        
        # Resize
        img = img.resize((size, size), Image.LANCZOS)
        img.save(dst_path, "JPEG", quality=90)
        return True
    except Exception as e:
        print(f"  Process error: {e}")
        return False

def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    success = 0
    fail = 0
    
    for hebrew_name, search_term in ANIMALS.items():
        dest_path = os.path.join(IMAGES_DIR, f"{hebrew_name}.jpg")
        
        # Skip if already exists and is valid
        if os.path.exists(dest_path):
            try:
                img = Image.open(dest_path)
                if img.size == (TARGET_SIZE, TARGET_SIZE):
                    print(f"SKIP {hebrew_name}: already exists")
                    continue
            except:
                pass
        
        print(f"\nProcessing: {hebrew_name} (search: '{search_term}')")
        
        # Search
        titles = search_wikimedia(search_term)
        if not titles:
            print(f"  FAIL: no search results")
            fail += 1
            continue
        
        # Try each result
        found = False
        for title in titles[:5]:
            print(f"  Trying: {title}")
            img_url, width, height = get_image_url(title)
            if not img_url:
                continue
            
            # Prefer images with reasonable resolution (at least 400px)
            if width < 400 or height < 400:
                print(f"    Too small: {width}x{height}")
                continue
            
            # Download to temp
            temp_path = os.path.join(IMAGES_DIR, f"{hebrew_name}_temp.jpg")
            if download_image(img_url, temp_path):
                # Process to square
                if make_square(temp_path, dest_path):
                    os.remove(temp_path)
                    print(f"  SUCCESS: {width}x{height} -> {TARGET_SIZE}x{TARGET_SIZE}")
                    found = True
                    success += 1
                    break
                else:
                    os.remove(temp_path)
            
            time.sleep(0.5)
        
        if not found:
            print(f"  FAIL: no suitable image found")
            fail += 1
        
        time.sleep(1)
    
    print(f"\n\nDone! Success: {success}, Failed: {fail}")

if __name__ == "__main__":
    main()

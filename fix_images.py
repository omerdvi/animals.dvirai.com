#!/usr/bin/env python3
"""
Fix animal images: re-download from Wikimedia with pad-to-square (no cropping).
Ensures the ENTIRE animal is visible inside 600x600 with white background.
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

def safe_filename(name):
    import re
    return re.sub(r'[^\w\u0590-\u05ff.-]', '_', name).strip('_')

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
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0 (AnimalGame/1.0)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = data.get("query", {}).get("search", [])
        return [r["title"] for r in results]
    except Exception as e:
        print(f"  Search error: {e}")
        return []

def get_image_url(filename):
    """Get direct image URL from Wikimedia."""
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
        req = urllib.request.Request(full_url, headers={"User-Agent": "Mozilla/5.0 (AnimalGame/1.0)"})
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
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        with open(dest_path, "wb") as f:
            f.write(data)
        # Validate it's an image
        img = Image.open(dest_path)
        img.verify()
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

def pad_to_square(src_path, dst_path, size=TARGET_SIZE, bg=(255, 255, 255)):
    """
    Scale image to fit inside size x size preserving aspect ratio,
    paste centered on square canvas. NOTHING is cut off.
    """
    try:
        with Image.open(src_path) as im:
            # Convert to RGB
            if im.mode in ("RGBA", "P"):
                im = im.convert("RGB")
            elif im.mode != "RGB":
                im = im.convert("RGB")
            
            w, h = im.size
            # Scale to fit inside size x size
            scale = min(size / w, size / h)
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            # Resize with high quality
            im_resized = im.resize((new_w, new_h), Image.LANCZOS)
            
            # Create square canvas
            canvas = Image.new("RGB", (size, size), bg)
            
            # Paste centered
            x = (size - new_w) // 2
            y = (size - new_h) // 2
            canvas.paste(im_resized, (x, y))
            
            canvas.save(dst_path, "JPEG", quality=92)
        return True
    except Exception as e:
        print(f"  Pad error: {e}")
        return False

def fallback_bing_search(term, max_results=5):
    """Fallback: search Bing Images."""
    encoded = urllib.parse.quote(term + " animal photo")
    url = f"https://www.bing.com/images/search?q={encoded}&qft=+filterui:photo-photo&form=HDRSC2&first=1"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        
        murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+)&quot;', html)
        if not murls:
            murls = re.findall(r'"murl":"(https?://[^"]+)"', html)
        if not murls:
            murls = re.findall(r'https?://[^\s"<>]+\.(?:jpg|jpeg|png|webp)', html)
        
        seen = set()
        results = []
        for u in murls:
            if u in seen:
                continue
            seen.add(u)
            lower = u.lower()
            if any(bad in lower for bad in ['icon', 'logo', 'avatar', 'thumb', 'badge', 'button', 'emoji']):
                continue
            results.append(u)
            if len(results) >= max_results:
                break
        return results
    except Exception as e:
        print(f"  Bing search error: {e}")
        return []

def process_animal(hebrew_name, search_term, category_name):
    """Download and process one animal image."""
    safe = safe_filename(hebrew_name)
    dest_path = IMAGES_DIR / f"{safe}.jpg"
    temp_path = IMAGES_DIR / f"{safe}_temp.jpg"
    
    print(f"\n[{hebrew_name}] Category: {category_name}")
    print(f"  Search: '{search_term}'")
    
    # Try Wikimedia first
    found = False
    wikimedia_url = None
    wikimedia_wh = None
    
    titles = search_wikimedia(search_term)
    if titles:
        for title in titles[:5]:
            img_url, width, height = get_image_url(title)
            if not img_url:
                continue
            if width < 300 or height < 300:
                print(f"    Wikimedia: {title} too small ({width}x{height})")
                continue
            print(f"    Wikimedia: {title} ({width}x{height})")
            wikimedia_url = img_url
            wikimedia_wh = (width, height)
            break
    
    if wikimedia_url:
        if download_image(wikimedia_url, temp_path):
            if pad_to_square(temp_path, dest_path):
                print(f"  ✓ SUCCESS (Wikimedia)")
                found = True
            else:
                print(f"  ✗ Pad failed")
        else:
            print(f"  ✗ Download failed")
    
    if not found:
        # Fallback: try Bing
        print(f"  Trying Bing fallback...")
        import re
        urls = fallback_bing_search(search_term)
        for idx, url in enumerate(urls):
            print(f"    Bing candidate {idx}: {url[:80]}...")
            if download_image(url, temp_path):
                try:
                    with Image.open(temp_path) as im:
                        w, h = im.size
                        if w >= 200 and h >= 200:
                            if pad_to_square(temp_path, dest_path):
                                print(f"  ✓ SUCCESS (Bing)")
                                found = True
                                break
                            else:
                                print(f"    Pad failed")
                        else:
                            print(f"    Too small: {w}x{h}")
                except Exception as e:
                    print(f"    Invalid image: {e}")
            else:
                print(f"    Download failed")
    
    # Cleanup temp
    if temp_path.exists():
        try:
            temp_path.unlink()
        except:
            pass
    
    if not found:
        print(f"  ✗ FAILED: {hebrew_name}")
    
    return found

def main():
    import re  # for fallback
    os.makedirs(IMAGES_DIR, exist_ok=True)
    
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    total = 0
    for cat_data in data["categories"].values():
        total += len(cat_data["animals"])
    
    print(f"=" * 60)
    print(f"Fixing {total} animal images with pad-to-square (no crop)")
    print(f"Target: {TARGET_SIZE}x{TARGET_SIZE} with white background")
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
            
            time.sleep(0.8)  # Be polite to APIs
            
            if process_animal(he, search, cat_name):
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

#!/usr/bin/env python3
import json, time, urllib.request, os
from PIL import Image

ANIMALS = {
    "איגואנה": "Green iguana",
    "דולפין": "Common bottlenose dolphin",
    "היפופוטם": "Hippopotamus",
    "חזיר_בר": "Wild boar",
    "חמור": "Donkey",
    "יונה": "Rock dove",
    "ינשוף": "Eurasian eagle-owl",
    "כריש": "Great white shark",
    "צבי": "Dorcas gazelle",
    "צפרדע": "Common frog",
    "קוף": "Rhesus macaque",
    "קרניף": "White rhinoceros",
    "תלולית": "Common starfish",
    "תרנגול": "Chicken",
}

IMAGES_DIR = "images"
TARGET_SIZE = 600

def get_wiki_image(article):
    url = f"https://en.wikipedia.org/w/api.php?action=query&titles={urllib.request.quote(article)}&prop=pageimages&piprop=name&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            return page.get("pageimage", "")
    except Exception as e:
        print(f"  Wiki error: {e}")
    return None

def get_commons_url(filename):
    url = f"https://commons.wikimedia.org/w/api.php?action=query&titles=File:{urllib.request.quote(filename)}&prop=imageinfo&iiprop=url|size|mime&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if "imageinfo" in page:
                info = page["imageinfo"][0]
                mime = info.get("mime", "")
                w = info.get("width", 0)
                h = info.get("height", 0)
                if mime.startswith("image/") and w >= 300 and h >= 300:
                    return info["url"], w, h
    except Exception as e:
        print(f"  Commons error: {e}")
    return None, 0, 0

def download_and_process(name, img_url):
    try:
        req = urllib.request.Request(img_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
        temp_path = os.path.join(IMAGES_DIR, f"{name}_temp.jpg")
        dest_path = os.path.join(IMAGES_DIR, f"{name}.jpg")
        with open(temp_path, "wb") as f:
            f.write(data)
        img = Image.open(temp_path)
        if img.mode != "RGB":
            img = img.convert("RGB")
        w, h = img.size
        if w > h:
            left = (w - h) // 2
            img = img.crop((left, 0, left + h, h))
        elif h > w:
            top = (h - w) // 2
            img = img.crop((0, top, w, top + w))
        img = img.resize((TARGET_SIZE, TARGET_SIZE), Image.LANCZOS)
        img.save(dest_path, "JPEG", quality=90)
        os.remove(temp_path)
        return True
    except Exception as e:
        print(f"  Download error: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return False

def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    success = 0
    fail = 0
    for hebrew_name, article in ANIMALS.items():
        print(f"\nProcessing: {hebrew_name}")
        img_name = get_wiki_image(article)
        if not img_name:
            print(f"  No image found")
            fail += 1
            time.sleep(5)
            continue
        print(f"  Found: {img_name}")
        img_url, w, h = get_commons_url(img_name)
        if not img_url:
            print(f"  No Commons URL")
            fail += 1
            time.sleep(5)
            continue
        print(f"  URL: {img_url} ({w}x{h})")
        if download_and_process(hebrew_name, img_url):
            print(f"  SUCCESS")
            success += 1
        else:
            print(f"  FAIL")
            fail += 1
        time.sleep(5)
    print(f"\nDone! Success: {success}, Failed: {fail}")

if __name__ == "__main__":
    main()

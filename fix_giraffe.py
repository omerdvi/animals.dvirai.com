import requests
from PIL import Image
from io import BytesIO
import os

headers = {'User-Agent': 'AnimalGame/1.0'}

# Try multiple Commons URLs for full-body giraffe
urls = [
    'https://upload.wikimedia.org/wikipedia/commons/thumb/e/e2/Giraffe_standing.jpg/800px-Giraffe_standing.jpg',
    'https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Giraffa_camelopardalis_reticulata.jpg/800px-Giraffa_camelopardalis_reticulata.jpg',
    'https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Giraffe_Necking.jpg/800px-Giraffe_Necking.jpg',
    'https://upload.wikimedia.org/wikipedia/commons/thumb/3/3b/Giraffe_head.jpg/800px-Giraffe_head.jpg',
]

def pad_to_square(img, size=600, bg=(255,255,255)):
    img = img.convert('RGB')
    w, h = img.size
    scale = size / max(w, h)
    new_w, new_h = int(w*scale), int(h*scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    out = Image.new('RGB', (size, size), bg)
    x, y = (size-new_w)//2, (size-new_h)//2
    out.paste(img, (x, y))
    return out

os.chdir('C:/projects/animal-game')

for url in urls:
    try:
        print(f'Trying: {url}')
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            img = Image.open(BytesIO(r.content))
            out = pad_to_square(img)
            # Save with proper Hebrew filename
            out.save('images/giraffe_temp.jpg', 'JPEG', quality=90)
            print(f'Saved temp, size: {out.size}')
            # Now rename to Hebrew name
            os.replace('images/giraffe_temp.jpg', "images/\u05d2'\u05d9\u05e8\u05e4\u05d4.jpg")
            print('Renamed successfully!')
            break
        else:
            print(f'Status: {r.status_code}')
    except Exception as e:
        print(f'Error: {e}')

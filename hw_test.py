import requests, io, random, json
from PIL import Image, ImageDraw

BASE = 'http://127.0.0.1:8000/api'

img = Image.new('RGB', (350, 350), (245, 150, 30))
draw = ImageDraw.Draw(img)
for i in range(1500):
    x = random.randint(0, 349); y = random.randint(0, 349)
    r_=max(0,min(255,245+random.randint(-40,10))); g_=max(0,min(255,150+random.randint(-50,30))); b_=max(0,min(255,30+random.randint(-20,20)))
    draw.point((x,y), fill=(r_,g_,b_))
img_bytes = io.BytesIO(); img.save(img_bytes, format='JPEG'); img_bytes.seek(0)
r = requests.post(f'{BASE}/hardware-predict', files={'file': ('o.jpg', img_bytes, 'image/jpeg')}, headers={'X-Device-Key': 'esp32-cam-default-key'})
print('Hardware (valid default key): status =', r.status_code)
d = r.json()
print(json.dumps(d, indent=2)[:800])

import requests, json, io, random, time
from PIL import Image, ImageDraw

BASE = 'http://127.0.0.1:8000/api'

# Sign up / login
requests.post(f'{BASE}/auth/signup', json={'name':'Test','email':'t2@t.com','password':'testpass123'})
r = requests.post(f'{BASE}/auth/login', json={'email':'t2@t.com','password':'testpass123'})
cookies = r.cookies
print('1. Login:', r.status_code, 'cookie set:', bool(cookies.get_dict()))

# Make a yellow banana-like textured image
img = Image.new('RGB', (400, 400), (225, 215, 50))
draw = ImageDraw.Draw(img)
for i in range(2000):
    x = random.randint(0, 399); y = random.randint(0, 399)
    r_=max(0,min(255,225+random.randint(-30,40)))
    g_=max(0,min(255,215+random.randint(-20,40)))
    b_=max(0,min(255,50+random.randint(-15,20)))
    draw.ellipse([x, y, x+random.randint(1, 5), y+random.randint(1, 5)], fill=(r_,g_,b_))
for i in range(100):
    x1=random.randint(0,200); x2=x1+random.randint(80,180)
    y1=random.randint(0,200); y2=y1+random.randint(40,140)
    draw.rectangle([x1,y1,x2,y2], fill=(max(0,225+random.randint(-40,30)),max(0,215+random.randint(-50,30)),max(0,50+random.randint(-20,15))))
img_bytes = io.BytesIO(); img.save(img_bytes, format='JPEG'); img_bytes.seek(0)
r = requests.post(f'{BASE}/predict', files={'file': ('banana.jpg', img_bytes, 'image/jpeg')}, cookies=cookies)
pred = r.json()
print()
print('2. Predict HTTP status:', r.status_code)
print('   fruit:', pred.get('fruit'), '| status:', pred.get('status'), '| confidence:', pred.get('confidence'))
print('   ripeness:', pred.get('ripeness_stage'), '| shelf:', pred.get('shelf_life_estimate'))
print('   info.title:', pred.get('info',{}).get('title'))
print('   info.points sample:', pred.get('info',{}).get('points',[None])[0][:80] if pred.get('info',{}).get('points') else 'none')

# Hardware-predict via multipart file (as the endpoint expects)
print()
print('3. Hardware-predict (multipart file):')
img_bytes.seek(0)
r = requests.post(f'{BASE}/hardware-predict', files={'file': ('hw.jpg', img_bytes, 'image/jpeg')}, headers={'X-Device-Key': 'HARDWARE_DEVICE_123'})
print('   HTTP status (valid key):', r.status_code)
d = r.json()
print('   body:', json.dumps(d)[:200])
img_bytes.seek(0)
r = requests.post(f'{BASE}/hardware-predict', files={'file': ('hw.jpg', img_bytes, 'image/jpeg')}, headers={'X-Device-Key': 'WRONG_KEY'})
print('   HTTP status (wrong key):', r.status_code, 'detail:', r.json().get('detail'))

# Notebook entries for all fruits
print()
print('4. Notebook API - nutrition data check:')
for name in ['Apple','Banana','Mango','Orange','Grapes','Tomato','Papaya']:
    entry = requests.get(f'{BASE}/notebook/{name}').json()
    nf = entry.get('nutrition_facts', {})
    print(f'   {name}: calories={nf.get("calories")}, prot={nf.get("protein_g")}g, carbs={nf.get("carbohydrates_g")}g, '
          f'fat={nf.get("fat_g")}g, vitamins={len(nf.get("key_vitamins",[]))}, minerals={len(nf.get("key_minerals",[]))}, '
          f'shelf[ripe]={entry["shelf_life_days"].get("ripe")}, combos={len(entry["good_combinations"])}')

# Chat retry with longer waits
print()
print('5. Chat retry (up to 5 attempts with 6s gaps):')
last_reply = None
for attempt in range(5):
    time.sleep(6)
    r = requests.post(f'{BASE}/chat', json={'message': 'Tell me 2 quick benefits of bananas and 1 good food combination.'})
    data = r.json()
    last_reply = data.get('reply')
    is_rate = any(x in (last_reply or '') for x in ['high demand', 'unavailable', 'currently experiencing', 'moment'])
    print(f'   Attempt {attempt+1}: status={r.status_code}, reply[:180]={(last_reply or "")[:180]}')
    if last_reply and not is_rate:
        print('   SUCCESS - got non-rate-limited AI reply')
        break
print('   Final reply snippet:', (last_reply or 'none')[:300])

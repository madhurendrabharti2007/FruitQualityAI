import colorsys, json
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from PIL import Image

# Last 3 image uploads matching user session time order
files = [
    ('bc656a69881c40c492593c987d16a9e6.jpg', 'IMG_7685 (orange #1, became Papaya)'),
    ('5292eb4b540a45c0bac0fcf303d1909a.jpg', 'IMG_7689 (orange #2, became Papaya)'),
    ('60374* most recent is in name order so last created'),
]
# Just read the most recent 3 via stat
uploads = Path('backend/uploads')
imgs = sorted(uploads.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
for p in imgs:
    img = Image.open(p).convert('RGB').resize((160,160))
    arr = np.asarray(img).reshape(-1,3).astype(np.float32)/255.0
    hues, sats, vals = [], [], []
    for r,g,b in arr:
        h,s,v = colorsys.rgb_to_hsv(r,g,b)
        hues.append(h*360); sats.append(s); vals.append(v)
    hues = np.array(hues); sats = np.array(sats); vals = np.array(vals)
    fruit_mask = (sats > 0.20) & (vals > 0.22)
    fh, fs, fv = hues[fruit_mask], sats[fruit_mask], vals[fruit_mask]
    # Bucket hues into 10-degree bins and print top 10
    bins = np.floor(fh/10).astype(int)
    counts = Counter(bins)
    top = counts.most_common(15)
    print(f'\n=== {p.name} mtime={p.stat().st_mtime:.0f} - size: {Image.open(p).size}')
    print(f'Fruit-mask pixels: {len(fh)}/{len(hues)}  mean_hue={fh.mean():.1f}  mean_sat={fs.mean():.2f}  mean_val={fv.mean():.2f}')
    print(f'Purple band (260-320): {((fh>=260)&(fh<=320)).mean():.3f}')
    print(f'Red band (340-20):  {((fh>=340)|(fh<=20)).mean():.3f}')
    print(f'Orange band (18-42): {((fh>=18)&(fh<=42)).mean():.3f}  + orange-wide (10-55): {((fh>=10)&(fh<=55)).mean():.3f}')
    print(f'Yellow Banana band (42-68): {((fh>=42)&(fh<=68)).mean():.3f}')
    print(f'Mango wide band (30-85): {((fh>=30)&(fh<=85)).mean():.3f}')
    print(f'Green-grape/kiwi band (85-120): {((fh>=85)&(fh<=120)).mean():.3f}')
    print(f'Pale-foliage green band (95-150): {((fh>=95)&(fh<=150)).mean():.3f}')
    print(f'Green cyan (120-175):     {((fh>=120)&(fh<=175)).mean():.3f}')
    print(f'Skin band (h<18 sat<0.55 val>0.45): {(((hues<18)|(hues>340))&(sats<0.55)&(vals>0.45)&~fruit_mask).mean():.3f}')
    print('Top hue bins (10deg):')
    for b,c in top:
        pct = c/len(fh)*100
        print(f'  {b*10:3d}-{b*10+10:3d}°  {pct:5.1f}%  (n={c})')

import sys
from pathlib import Path
sys.path.insert(0, str(Path('backend').resolve()))
from app.model.predict import predictor
uploads = Path('backend/uploads')
imgs = sorted(uploads.glob('*.jpg'), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
for p in imgs:
    print(f'\n=== {p.name} ===')
    fruit, status, conf, demo, msg, tops = predictor.predict(p)
    print(f'  fruit={fruit}  status={status}  conf={conf:.1f}%  demo={demo}  msg={msg}')
    top3 = tops[:3]
    print(f'  top3: {[(t[0], round(t[1],3)) for t in top3]}')

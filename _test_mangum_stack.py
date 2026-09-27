import sys, os
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path: sys.path.insert(0, str(BACKEND_DIR))
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("SQLITE_DB_DIR", str(PROJECT_ROOT / ".tmp-db"))
os.environ.setdefault("UPLOAD_DIR", str(PROJECT_ROOT / ".tmp-uploads"))
print("[1/4] Importing Mangum...")
from mangum import Mangum
print("  OK - Mangum loaded")
print("[2/4] Importing FastAPI app from backend/app/main.py...")
from app.main import app as fastapi_app
print(f"  OK - FastAPI app title={fastapi_app.title!r}, {len(fastapi_app.routes)} total routes")
for r in fastapi_app.routes[:10]:
    print(f"     - {r.path} [{sorted(getattr(r, 'methods', set())) or 'ALL'}]")
print("[3/4] Creating Mangum handler with lifespan=on...")
handler = Mangum(fastapi_app, lifespan="on", api_gateway_base_path="/")
print("  OK - Mangum handler created")
print("[4/4] Simulating synthetic AWS Lambda /api/health event...")
event = {
    "httpMethod": "GET",
    "path": "/api/health",
    "resource": "/{proxy+}",
    "queryStringParameters": {},
    "headers": {"host": "example.vercel.app", "x-forwarded-proto": "https"},
    "body": None,
    "isBase64Encoded": False,
    "requestContext": {"stage": "$default", "http": {"method": "GET", "path": "/api/health", "protocol": "HTTP/1.1"}},
}
try:
    out = handler(event, {"aws_request_id": "test"})
    print(f"  HTTP status: {out['statusCode']}")
    print(f"  Body preview: {str(out.get('body',''))[:300]}")
    if out["statusCode"] == 200:
        print("  PASS - /api/health returned 200 OK")
    else:
        print("  FAIL - Expected 200")
        sys.exit(2)
except Exception as e:
    import traceback
    print(f"  FAIL - {type(e).__name__}: {e}")
    traceback.print_exc()
    sys.exit(1)
print("ALL CHECKS PASSED")

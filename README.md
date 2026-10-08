# Ripewise (FruitQualityAI)

A full-stack fruit quality checker. Upload or capture a photo, get the predicted fruit and freshness status, then read practical food guidance for that result. Ripewise was chosen over FreshScan and FruitLens AI because it feels friendly and fits both fresh and spoiled result states.

## Deployment Architecture

This project uses a **split deployment** by design:

- **Frontend (React + Vite) → deployed on Vercel.** Vercel is ideal for static SPAs: fast CDN, preview deployments, Git integration.
- **Backend (FastAPI + SQLite + ML libraries) → deployed on Render (or Railway / Fly.io / any persistent server).** The backend needs a long-running process, not Vercel's serverless functions, because:
  1. SQLite must persist between requests (serverless `/tmp` is ephemeral).
  2. ML / image-processing libraries (NumPy, Pillow, optional TensorFlow, google-genai) are too large and cold-start too slowly for serverless.
  3. The ESP32-CAM `/api/hardware-predict` endpoint expects a stable, always-listening server.

If you previously tried deploying both halves on Vercel, that's why nothing persisted — this split layout fixes it completely.

## Stack

- React + Vite + Tailwind CSS + Framer Motion
- FastAPI + SQLAlchemy + SQLite
- TensorFlow/Keras MobileNetV2 training pipeline
- Local image uploads during development
- JWT + HttpOnly cookie auth (with `Authorization: Bearer` fallback for cross-origin)
- Optional cookie-based accounts and private scan history

The interface uses a warm citrus and forest palette, Fraunces for display type, and DM Sans for readable UI copy. The light/dark toggle stores a `ripewise-theme` cookie and uses the browser system preference on a first visit. Tailwind uses the `dark` class strategy, so the preference is available across the app without localStorage.

---

## Run locally

You need TWO separate terminal windows - one for backend, one for frontend.

### Backend

```bash
cd FruitQualityAI
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cd backend
# Copy env template and add your keys
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# Edit .env and set GEMINI_API_KEY at minimum

# Seed the DB (optional on first run; lifespan() also calls it)
python -m app.seed_data

# Start the backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

You should see:
- `INFO: Uvicorn running on http://0.0.0.0:8000`
- `Starting Ripewise API - initializing database and seed data`
- `Ripewise API startup complete`
- `Application startup complete.`

Verify it works: `curl http://127.0.0.1:8000/api/health` should return `{"status":"ok"}`.

### Frontend

```bash
cd FruitQualityAI/frontend
npm install
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux
# For local dev the default VITE_API_BASE_URL=http://localhost:8000/api is fine

npm run dev
```

Open http://localhost:5173. The frontend defaults to `http://localhost:8000/api` for the API; if you run the backend on a different port or machine, edit `frontend/.env` and set `VITE_API_BASE_URL` accordingly.

---

## Environment Variables

### Backend (`backend/.env` / Render Environment)

Set these in **Render → your Web Service → Environment** (or in `backend/.env` for local dev).

| Variable | Required? | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Recommended | *(none)* | Free key from https://aistudio.google.com/apikey. Powers the notebook-grounded fruit assistant chat. Without it the assistant shows a setup message but all other features work. |
| `JWT_SECRET` | **Yes in prod** | `change-this-development-secret` | Long random string used to sign HttpOnly access tokens. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `ADMIN_TOKEN` | Optional | `fruit-admin` | Shared secret for direct CRUD on `/api/fruits/*`; sent via the `X-Admin-Token` header. |
| `HARDWARE_DEVICE_KEY` | Optional | `esp32-cam-default-key` | Shared secret for the ESP32-CAM device endpoint (`/api/hardware-predict`). Must match the key sent by the device. |
| `ALLOWED_ORIGINS` | **Yes in prod** | *(localhost defaults)* | Comma-separated list of frontend origins that may call the API. Example: `https://fruitqualityai.vercel.app` or multiple: `https://fruitqualityai.vercel.app,https://app.example.com`. **Once you have a Vercel URL you must set this — otherwise CORS blocks the frontend.** |
| `CORS_ALLOW_ALL` | Optional | *(false)* | Set to `true` to allow every origin (disables credentials/cookies). Useful for temporary debugging only. |
| `COOKIE_SECURE` | Optional | *(auto)* | Override the `Secure` flag on the auth cookie. Set to `true` if you're on HTTPS behind a proxy that doesn't set the `RENDER` env var or `ENV=production`. |
| `ENV` | Optional | *(dev)* | Set to `production` to flip the auth cookie into `Secure: true` mode (Render usually sets this via its own env). |
| `DATABASE_URL` / `SQLITE_DB_PATH` | Optional | `backend/fruit_quality.db` | Override the SQLite file path, e.g. `sqlite:////data/fruit_quality.db` on Render with a persistent disk. |
| `SQLITE_DB_DIR` | Optional | `backend/` | Directory for the SQLite file if you don't set the full URL. On Render point this at your persistent disk mount. |
| `UPLOAD_DIR` | Optional | `backend/uploads` | Where captured/uploaded photos are stored. On Render point this at your persistent disk mount. |

### Frontend (`frontend/.env` / Vercel Environment)

| Variable | Required? | Default | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | **Yes in prod** | `http://localhost:8000/api` | Full URL of the Render backend including the `/api` suffix. Example: `https://fruitqualityai-backend.onrender.com/api`. |

Note: the legacy `VITE_API_URL` name still works as a fallback if you set it, but `VITE_API_BASE_URL` is the canonical variable going forward.

---

## Deployment — Step by Step

### Part 1: Deploy the Backend on Render

Render gives you a free-tier Web Service with a persistent server (not serverless), which is exactly what this backend needs. SQLite disk persistence requires a **Persistent Disk** add-on (~$1-3/mo at time of writing); without one the DB resets on every deploy, which is fine for evaluation but not for real use.

1. **Push the project to GitHub** (or GitLab / Bitbucket) if it isn't already.
2. Go to https://dashboard.render.com and sign in.
3. Click **"New +" → Web Service**.
4. **Connect your repo** and pick the FruitQualityAI repository.
5. On the service configuration page:
   - **Name:** `fruitqualityai-backend` (or whatever you want — this becomes the subdomain).
   - **Region:** pick the closest one to your users.
   - **Branch:** `main` (or your production branch).
   - **Root Directory:** `backend` ← **this is critical.** Render must install from `backend/requirements.txt` and run from the `backend` folder so `app.main:app` resolves.
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Instance Type:** Free (Starter) is fine to begin with; upgrade if cold boots annoy you.
6. Click **"Advanced"** and add the following **Environment Variables** (copy values from `backend/.env.example`):
   | Key | Value |
   |---|---|
   | `GEMINI_API_KEY` | *(your real key from https://aistudio.google.com/apikey)* |
   | `JWT_SECRET` | *(a long random string — generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`)* |
   | `ADMIN_TOKEN` | *(something strong, not the default `fruit-admin`)* |
   | `HARDWARE_DEVICE_KEY` | *(something strong, not the default; must match ESP32-CAM if used)* |
   | `ALLOWED_ORIGINS` | **LEAVE BLANK FOR NOW.** You'll come back and fill this in after Part 2 gives you a Vercel URL. |
   | `PYTHON_VERSION` | `3.12.0` (to match the Dockerfile; if Render complains, just remove this — it auto-detects well) |
7. Click **Create Web Service** and wait for the build + deploy (2–5 minutes).
8. When you see `Your service is live 🎉`, open the provided URL (e.g. `https://fruitqualityai-backend.onrender.com`) and append `/api/health`. You should see `{"status":"ok"}`. **Copy this base URL, you need it in Part 2.**

> **Optional — SQLite persistence (recommended after testing):** On your Render service go to **Disks → Add Disk**. Mount it at `/data`. Then add two more env vars:
> - `SQLITE_DB_DIR=/data`
> - `UPLOAD_DIR=/data/uploads`
>
> This keeps users, scan history, and uploaded images alive across deploys and restarts.

### Part 2: Deploy the Frontend on Vercel

1. Go to https://vercel.com/new and **import the same FruitQualityAI repository**.
2. Vercel auto-detects Vite because of the new `rootDirectory: "frontend"` setting in `vercel.json`. Accept the defaults.
3. **Before clicking Deploy**, open **Environment Variables** and add:
   | Variable | Environment | Value |
   |---|---|---|
   | `VITE_API_BASE_URL` | Production, Preview, Development | `<your Render backend URL>/api` e.g. `https://fruitqualityai-backend.onrender.com/api` |
   > **Important:** include the **trailing `/api`** on the value, not just the domain.
4. Click **Deploy**. In 1–2 minutes you'll get a Vercel URL like `https://fruitqualityai-abc123.vercel.app`. **Copy this URL.**

### Part 3: Wire CORS (connect the two)

The last step: tell the Render backend to accept requests from your new Vercel frontend, otherwise every API call gets blocked by the browser's CORS policy.

1. Go back to **Render → fruitqualityai-backend → Environment**.
2. Find the `ALLOWED_ORIGINS` variable you left blank and set it to your Vercel URL **without a trailing slash**, e.g.:
   ```
   ALLOWED_ORIGINS=https://fruitqualityai-abc123.vercel.app
   ```
   If you also have a custom domain, add it comma-separated:
   ```
   ALLOWED_ORIGINS=https://fruitqualityai-abc123.vercel.app,https://app.yourdomain.com
   ```
3. **Save Changes**. Render automatically triggers a zero-downtime redeploy with the new env.
4. Once Render finishes redeploying, reload your Vercel frontend and try signing up / uploading a photo — everything should now work end to end.

### Part 4 (Optional): Create an Admin Account

Once the backend is live on Render, you can create/promote an admin via the Render Web Shell:

```bash
cd backend
python create_admin.py --email admin@yourdomain.com --password "a-strong-password" --name "Site Admin"
```

Or locally against a live DB if you have the disk mounted. Admin accounts unlock the `/admin` analytics page.

---

## Train on your dataset

Put images into this exact layout:

```text
backend/dataset/
  Apple/fresh/*.jpg
  Apple/rotten/*.jpg
  Banana/fresh/*.jpg
  Banana/rotten/*.jpg
```

Use the same pattern for each fruit. The existing `FruitNet_Processed Images` archive can be reorganized into this layout by mapping `Good Quality_Fruits/Apple_Good` to `Apple/fresh` and `Bad Quality_Fruits/Apple_Bad` to `Apple/rotten` (and so on). Keep at least two classes, with both statuses represented.

Install the optional ML dependency and train:

```bash
cd backend
pip install tensorflow==2.18.0
python -m app.model.train
```

Training creates `backend/app/model/saved_model/fruit_quality.keras` and `labels.json`. Restart FastAPI afterward; the predictor automatically loads those files. The training script uses augmentation, a deterministic 80/10/10-style train/holdout split, a frozen MobileNetV2 head stage, and optional low-learning-rate fine-tuning of the last base layers.

## API

- `GET /api/health`
- `POST /api/predict` with multipart field `file`
- `POST /api/hardware-predict` for ESP32-CAM devices (authenticated via `X-Hardware-Device-Key` header)
- `GET /api/fruits`
- `GET /api/notebook` and `GET /api/notebook/{fruit_id}`
- `POST /api/chat` for notebook-grounded fruit questions
- `POST /api/batch-predict` for vendor batch intake, plus `/api/reports` CSV/PDF exports
- `GET /api/admin/analytics` for admin-only operational analytics
- `POST`, `PUT /api/fruits/{name}`, and `DELETE /api/fruits/{name}` with `X-Admin-Token`

Uploads are restricted to JPG, PNG, or WEBP and 8 MB. SQLite is created at `backend/fruit_quality.db` on first run.

### Account endpoints

- `POST /api/auth/signup` creates an account and sets an HttpOnly `access_token` cookie
- `POST /api/auth/login` verifies credentials and sets the same cookie
- `POST /api/auth/logout` clears the cookie
- `GET /api/auth/me` returns the signed-in user
- `GET /api/auth/history` returns that user's saved prediction history
- `POST /api/auth/forgot-password` and `POST /api/auth/reset-password` for password recovery

```json
POST /api/auth/signup
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "password": "fresh-fruit-123"
}
```

The response is a user object such as `{ "id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "created_at": "2026-09-09T12:00:00" }`. The browser stores the JWT only in an HttpOnly cookie. As a cross-origin fallback (e.g. when `samesite=lax` blocks the cookie), the frontend also sends the same token in an `Authorization: Bearer <token>` header, and the backend accepts either.

Signed-in predictions keep the normal `/api/predict` response and are also written to `predictions`; guest predictions are never stored.

For the optional fruit assistant, copy `backend/.env.example` to `backend/.env` and add a free key from `https://aistudio.google.com/apikey`. Without a key, the assistant remains available with a setup message and the notebook pages continue to work normally.

Business access: new accounts start as `customer`. A signed-in customer can request vendor access from the dashboard; vendor accounts unlock Batch scan and Reports. Create or promote an admin privately with `python create_admin.py --email admin@example.com --password change-me --name Admin` from `backend`; admin accounts unlock `/admin` analytics.

---

## Troubleshooting the split deploy

**Frontend shows 401 on every API call even after login:**
The frontend and backend are on different origins, so `samesite=lax` cookies sometimes don't attach to async `POST`s. The app already handles this with a localStorage + `Authorization: Bearer` fallback — but you must ensure the cookie's `Secure` flag matches reality. If you're on HTTPS (both Vercel and Render are), either set `ENV=production`, set `RENDER=true`, or explicitly set `COOKIE_SECURE=true` on the Render backend.

**CORS error in the browser console:**
Go back to Render → Environment and confirm `ALLOWED_ORIGINS` is set to your *exact* Vercel origin (no trailing slash, no path, correct protocol `https://`). Then wait for Render to finish redeploying and hard-refresh the Vercel page.

**Login works but the call to `/auth/me` returns null:**
Same cause as the 401 case — cookies not being sent across origins. Verify the Bearer fallback: open DevTools → Network → the `/auth/me` request → Request Headers. You should see an `Authorization: Bearer ...` header. If not, the token wasn't saved to localStorage on login (it's saved inside `signIn()` via the same `access_token` field returned from the auth endpoints).

**Render backend works in isolation but frontend can't reach `/api/health`:**
Double-check `VITE_API_BASE_URL` on Vercel. It must be the **full URL including `/api`**, e.g. `https://fruitqualityai-backend.onrender.com/api`. Not `/api`, not `https://fruitqualityai-backend.onrender.com/`. After changing env vars on Vercel you need to redeploy (environment variables are baked in at build time for Vite).

**SQLite data disappears every time I redeploy on Render:**
You forgot the persistent disk (see Part 1 note). Add a Render disk mounted at `/data` and set `SQLITE_DB_DIR=/data` and `UPLOAD_DIR=/data/uploads`.

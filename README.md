# Ripewise

A full-stack fruit quality checker. Upload or capture a photo, get the predicted fruit and freshness status, then read practical food guidance for that result. Ripewise was chosen over FreshScan and FruitLens AI because it feels friendly and fits both fresh and spoiled result states.

## Stack

- React + Vite + Tailwind CSS + Framer Motion
- FastAPI + SQLAlchemy + SQLite
- TensorFlow/Keras MobileNetV2 training pipeline
- Local image uploads during development
- Optional cookie-based accounts and private scan history

The interface uses a warm citrus and forest palette, Fraunces for display type, and DM Sans for readable UI copy. The light/dark toggle stores a `ripewise-theme` cookie and uses the browser system preference on a first visit. Tailwind uses the `dark` class strategy, so the preference is available across the app without localStorage.

## Run locally

### Quick Start (Windows Command Prompt)

**IMPORTANT: Use Windows Command Prompt (cmd.exe), NOT PowerShell. PowerShell script execution policies often cause issues.**

You need TWO separate terminal windows - one for backend, one for frontend.

#### Terminal 1: Backend

Open Command Prompt and run these commands exactly:

```cmd
cd C:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
cd backend
..\.venv\Scripts\python.exe -m app.seed_data
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

**Note:** The `requirements.txt` file is now in the project root, not in the backend folder.

**What you should see:**
- After `pip install`: "Successfully installed..." followed by a list of packages
- After `seed_data`: No output (this is normal)
- After `uvicorn`: "INFO: Uvicorn running on http://127.0.0.1:8000" and "INFO: Application startup complete"

If you see "Application startup complete", the backend is running successfully. Leave this terminal open.

#### Terminal 2: Frontend

Open a NEW Command Prompt window and run:

```cmd
cd C:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI\frontend
node_modules\.bin\vite.cmd
```

**What you should see:**
- "VITE v6.4.3 ready in [number] ms"
- "Local: http://localhost:5173/"

If you see the Local URL, the frontend is running. Open http://localhost:5173 in your browser.

#### Environment Setup

Before running the backend, ensure `backend\.env` exists with your API keys:

```cmd
cd C:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI\backend
copy .env.example .env
```

Then edit `backend\.env` and add your Gemini API key from https://aistudio.google.com/apikey

The API runs at `http://127.0.0.1:8000`. The app works immediately in demo mode without TensorFlow or trained weights. The demo predictor validates the image and returns a deterministic sample result so the upload flow can be tested end to end.

Set `ADMIN_TOKEN` in `.env` before starting the API to change the default admin token (`fruit-admin`). Admin CRUD calls use the `X-Admin-Token` header.

### PowerShell Instructions (if you must use PowerShell)

If you encounter script execution errors in PowerShell, you may need to change the execution policy:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then use these PowerShell commands:

```powershell
cd C:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
cd backend
python -m app.seed_data
uvicorn app.main:app --reload
```

**Note:** The `requirements.txt` file is now in the project root, not in the backend folder.

For frontend:

```powershell
cd C:\Users\Madhurendra bharti\OneDrive\Documents\Desktop\FruitQualityAI\frontend
npm install
npm run dev
```

### Troubleshooting

**Backend won't start:**
- Ensure you're in the `backend` folder
- Check that Python is installed: `python --version`
- Verify `.env` file exists in `backend/` folder
- Make sure port 8000 is not already in use

**Frontend won't start:**
- Ensure you're in the `frontend` folder
- Check that Node.js is installed: `node --version`
- If `npm` command fails in PowerShell, use Command Prompt instead
- Make sure port 5173 is not already in use
- Use direct vite command: `node_modules\.bin\vite.cmd` if npm fails

**PowerShell script execution errors:**
- Either use Command Prompt (recommended)
- Or run: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

**Missing dependencies:**
- Backend: Ensure `requirements.txt` is complete and run `pip install -r requirements.txt` again
- Frontend: Ensure `package.json` is complete and run `npm install` again

**API connection errors:**
- Ensure backend is running on http://127.0.0.1:8000
- Check that frontend API base URL points to http://127.0.0.1:8000/api
- Verify CORS settings in backend allow your frontend origin

**Missing GEMINI_API_KEY:**
- Get a free key from https://aistudio.google.com/apikey
- Add it to `backend/.env` file
- Without it, the chat assistant will show a setup message but other features work

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

```powershell
cd backend
pip install tensorflow==2.18.0
python -m app.model.train
```

Training creates `backend/app/model/saved_model/fruit_quality.keras` and `labels.json`. Restart FastAPI afterward; the predictor automatically loads those files. The training script uses augmentation, a deterministic 80/10/10-style train/holdout split, a frozen MobileNetV2 head stage, and optional low-learning-rate fine-tuning of the last base layers.

## API

- `GET /api/health`
- `POST /api/predict` with multipart field `file`
- `GET /api/fruits`
- `GET /api/notebook` and `GET /api/notebook/{fruit_id}`
- `POST /api/chat` for notebook-grounded fruit questions
- `POST /api/batch-predict` for vendor batch intake, plus `/api/reports` CSV/PDF exports
- `GET /api/admin/analytics` for admin-only operational analytics
- `POST`, `PUT /api/fruits/{name}`, and `DELETE /api/fruits/{name}` with `X-Admin-Token`

Uploads are restricted to JPG, PNG, or WEBP and 8 MB. SQLite is created at `backend/fruit_quality.db` on first run.

Account endpoints:

- `POST /api/auth/signup` creates an account and sets an HttpOnly `access_token` cookie
- `POST /api/auth/login` verifies credentials and sets the same cookie
- `POST /api/auth/logout` clears the cookie
- `GET /api/auth/me` returns the signed-in user
- `GET /api/auth/history` returns that user's saved prediction history

```json
POST /api/auth/signup
{
  "name": "Ada Lovelace",
  "email": "ada@example.com",
  "password": "fresh-fruit-123"
}
```

The response is a user object such as `{ "id": 1, "name": "Ada Lovelace", "email": "ada@example.com", "created_at": "2026-09-09T12:00:00" }`. The browser stores the JWT only in an HttpOnly cookie. Signed-in predictions keep the normal `/api/predict` response and are also written to `predictions`; guest predictions are never stored.

For the optional fruit assistant, copy `backend/.env.example` to `backend/.env` and add a free key from `https://aistudio.google.com/apikey`. Without a key, the assistant remains available with a setup message and the notebook pages continue to work normally.

Business access: new accounts start as `customer`. A signed-in customer can request vendor access from the dashboard; vendor accounts unlock Batch scan and Reports. Create or promote an admin privately with `python create_admin.py --email admin@example.com --password change-me --name Admin` from `backend`; admin accounts unlock `/admin` analytics.

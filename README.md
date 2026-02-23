# doc-exporter-test

A deployment-ready project for exporting Synthesia video script content (from XLIFF) into a PDF.

This project includes:

- **FastAPI backend** for API calls, XLIFF parsing, and PDF generation
- **Static frontend** deployable to GitHub Pages

## Project structure

```text
doc-exporter-test/
├── backend/
│   ├── app.py
│   ├── parser.py
│   ├── pdf_generator.py
│   ├── requirements.txt
│   └── README.md
├── frontend/
│   ├── index.html
│   ├── config.js
│   ├── app.js
│   └── styles.css
├── render.yaml
└── README.md
```

## Deployment wiring

Set these URLs for your own deployment:

- **Frontend (GitHub Pages):** `https://<user>.github.io/<repo>/`
- **Backend (Render/Fly.io/Railway/etc.):** `https://<your-backend-domain>`

How frontend and backend are connected:

1. Frontend requests are sent to `window.APP_CONFIG.API_BASE_URL` (`frontend/config.js`).
2. Set `API_BASE_URL` to your deployed backend URL.
3. Backend CORS must explicitly allow your Pages origin through `ALLOWED_ORIGINS`.

Example:

- Frontend: `https://<user>.github.io/doc-exporter-test/`
- Backend: `https://doc-exporter-backend.onrender.com`
- `frontend/config.js` → `API_BASE_URL: "https://doc-exporter-backend.onrender.com"`
- Backend env → `ALLOWED_ORIGINS=https://<user>.github.io`

## Backend deployment (Render example)

This repo includes `render.yaml` to deploy `backend/app.py` as a Render Web Service.

1. Push the repository to GitHub.
2. In Render, create a new Blueprint and select this repo.
3. Render reads `render.yaml` and uses:
   - build: `pip install -r requirements.txt`
   - start: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. In Render environment variables, set:
   - `ALLOWED_ORIGINS=https://<user>.github.io`
   - optionally `REQUEST_TIMEOUT` and `SYNTHESIA_API_BASE`
5. Copy the deployed backend URL and put it in `frontend/config.js`.

## Backend environment configuration

`backend/app.py` reads runtime configuration from environment variables:

- `ALLOWED_ORIGINS` (comma-separated; preferred in deployed environments)
  - Example: `https://<user>.github.io,http://localhost:5500`
- `GITHUB_PAGES_ORIGIN` (optional helper when `ALLOWED_ORIGINS` is not set)
  - Example: `https://<user>.github.io`
- `SYNTHESIA_API_BASE` (optional; defaults to `https://api.synthesia.io/v2`)
- `REQUEST_TIMEOUT` (optional; defaults to `30`)

If `ALLOWED_ORIGINS` is omitted, local development origins are allowed by default (`localhost:5500`, `127.0.0.1:5500`, `localhost:5173`, `127.0.0.1:5173`) and `GITHUB_PAGES_ORIGIN` is appended when present.

## Run backend locally

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open API docs:

- <http://localhost:8000/docs>

## Serve frontend locally

From the repository root:

```bash
cd frontend
python -m http.server 5500
```

Then open:

- <http://localhost:5500>

For local use, keep `frontend/config.js` as:

```js
window.APP_CONFIG = {
  API_BASE_URL: "http://localhost:8000",
};
```

## GitHub Pages deployment (frontend)

1. Push this repository to GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set:
   - **Source:** Deploy from a branch
   - **Branch:** your main branch
   - **Folder:** `/frontend`
4. Save and wait for the Pages URL to be published.
5. Update `frontend/config.js` so `API_BASE_URL` points to your deployed backend URL.
6. Ensure backend `ALLOWED_ORIGINS` includes your Pages origin.

## Example curl commands

List videos:

```bash
curl "http://localhost:8000/videos?api_key=YOUR_SYNTHESIA_API_KEY"
```

Export PDF:

```bash
curl -X POST "http://localhost:8000/export-pdf" \
  -F "api_key=YOUR_SYNTHESIA_API_KEY" \
  -F "video_id=VIDEO_ID" \
  --output export.pdf
```

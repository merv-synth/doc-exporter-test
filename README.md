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
└── README.md
```

## Deployment wiring

Set these URLs for your own deployment:

- **Frontend (GitHub Pages):** `https://<user>.github.io/<repo>/`
- **Backend (Render/Fly.io/Railway/etc.):** `https://<your-backend-domain>`

How they connect:

1. The frontend sends requests to `window.APP_CONFIG.API_BASE_URL` from `frontend/config.js`.
2. Set `API_BASE_URL` in `frontend/config.js` to your deployed backend URL.
3. Configure backend CORS (`ALLOWED_ORIGINS`) to include your Pages origin.

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

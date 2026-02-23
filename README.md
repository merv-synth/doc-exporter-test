# doc-exporter-test

A self-contained environment for exporting Synthesia video script content (from XLIFF) into a PDF.

This project includes:

- **FastAPI backend** for API calls, XLIFF parsing, and PDF generation
- **Static frontend** (works locally and on GitHub Pages)
- **Docker Compose** setup for one-command local run

## Project structure

```text
doc-exporter-test/
├── backend/
│   ├── app.py
│   ├── parser.py
│   ├── pdf_generator.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── README.md
├── frontend/
│   ├── index.html
│   ├── app.js
│   ├── config.js
│   └── styles.css
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up --build
```

Then open:

- Frontend: <http://localhost:5500>
- Backend docs: <http://localhost:8000/docs>
- Backend health check: <http://localhost:8000/healthz>

## Run without Docker

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
python -m http.server 5500
```

Open <http://localhost:5500>.

## Configuration

Backend environment variables:

- `ALLOWED_ORIGINS` (default: `*`) — comma-separated CORS allow-list
- `REQUEST_TIMEOUT` (default: `30`) — timeout in seconds for Synthesia API calls
- `SYNTHESIA_API_BASE` (default: `https://api.synthesia.io/v2`)

Frontend backend URL resolution order:

1. `window.__API_BASE__` from `frontend/config.js`
2. Hostname map in `frontend/app.js`
3. Local fallback `http://localhost:8000`

## Deployment

### Frontend (GitHub Pages)

1. Push repository to GitHub.
2. Go to **Settings → Pages**.
3. Set source to **Deploy from a branch**, branch to `main`, folder to `/frontend`.
4. Set `window.__API_BASE__` in `frontend/config.js` to your deployed backend URL.
5. Commit and push.

### Backend

Use any platform that supports container deploys (Render, Railway, Fly.io, ECS, etc.) with:

- Build context: `backend/`
- Exposed port: `8000`
- Start command: `uvicorn app:app --host 0.0.0.0 --port 8000`
- Health check path: `/healthz`
- Environment variable: `ALLOWED_ORIGINS=https://<your-pages-domain>`

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

## Security

Do not expose this backend publicly with unrestricted CORS and direct API key handling in production without proper hardening.

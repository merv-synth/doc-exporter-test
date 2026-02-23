# Backend (FastAPI)

This backend provides APIs for:

- Listing Synthesia videos with an API key
- Downloading video XLIFF
- Parsing scenes/scripts from XLIFF
- Exporting a PDF

## Run locally

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

Open docs at: <http://localhost:8000/docs>

## Docker

From the repository root:

```bash
docker compose up --build backend
```

## Environment variables

- `ALLOWED_ORIGINS` (default: `*`) — comma-separated allowed CORS origins
- `REQUEST_TIMEOUT` (default: `30`) — Synthesia API request timeout in seconds
- `SYNTHESIA_API_BASE` (default: `https://api.synthesia.io/v2`)

## Endpoints

- `GET /healthz`
- `GET /videos?api_key=...`
- `POST /export-pdf` (form fields: `api_key`, `video_id`)

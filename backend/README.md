# Backend (FastAPI)

This backend provides a local API for:

- Listing Synthesia videos with an API key
- Downloading video XLIFF
- Parsing scenes and scripts from XLIFF
- Exporting a PDF

## Run locally

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Open docs at: <http://localhost:8000/docs>

## Endpoints

- `GET /videos?api_key=...`
- `POST /export-pdf` (form fields: `api_key`, `video_id`)

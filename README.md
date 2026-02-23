# doc-exporter-test

A self-contained local test environment for exporting Synthesia video script content (from XLIFF) into a PDF.

This project includes:

- **FastAPI backend** (local) for API calls, XLIFF parsing, and PDF generation
- **Static frontend** compatible with GitHub Pages

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
│   ├── app.js
│   └── styles.css
└── README.md
```

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

`frontend/app.js` uses:

```js
const API_BASE = "http://localhost:8000";
```

## GitHub Pages deployment (frontend only)

1. Push this repository to GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set:
   - **Source:** Deploy from a branch
   - **Branch:** `main`
   - **Folder:** `/frontend`
4. Save and wait for Pages URL to be published.
5. Ensure your local backend (`http://localhost:8000`) is running when testing from Pages.

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

## Notes

- No AWS, Cognito, queues, or external infrastructure required.
- Built for local end-to-end testing.

## Security

This setup is intended for **local testing only**.
Do not expose this backend publicly with unrestricted CORS and direct API key handling.

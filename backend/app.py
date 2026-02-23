from __future__ import annotations

import os
import shutil
import tempfile
import json
import logging
from uuid import uuid4
from pathlib import Path

import requests
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from parser import parse_scenes_from_xliff
from pdf_generator import generate_pdf

SYNTHESIA_API_BASE = os.getenv("SYNTHESIA_API_BASE", "https://api.synthesia.io/v2")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(title="Synthesia XLIFF PDF Exporter")
logger = logging.getLogger("doc_exporter")
if not logging.getLogger().handlers:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _synthesia_headers(api_key: str) -> dict[str, str]:
    normalized_key = api_key.strip()

    return {
        "Authorization": normalized_key,
        "X-API-Key": normalized_key,
        "Accept": "application/json",
    }


def _mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _safe_preview(content: bytes, max_len: int = 500) -> str:
    try:
        text = content.decode("utf-8", errors="replace")
    except Exception:  # defensive
        return "<non-text payload>"
    return text[:max_len] + ("...<truncated>" if len(text) > max_len else "")


def _log_upstream_response(trace_id: str, operation: str, response: requests.Response) -> None:
    logger.info(
        "[%s] %s response status=%s content_type=%s body_preview=%s",
        trace_id,
        operation,
        response.status_code,
        response.headers.get("content-type", "unknown"),
        _safe_preview(response.content),
    )


def _fetch_videos(api_key: str, trace_id: str) -> list[dict]:
    url = f"{SYNTHESIA_API_BASE}/videos"
    logger.info(
        "[%s] Requesting Synthesia videos endpoint url=%s api_key=%s timeout=%ss",
        trace_id,
        url,
        _mask_secret(api_key.strip()),
        REQUEST_TIMEOUT,
    )

    try:
        response = requests.get(
            url,
            headers=_synthesia_headers(api_key),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.exception("[%s] Unable to reach Synthesia videos endpoint", trace_id)
        raise HTTPException(status_code=502, detail="Unable to reach Synthesia API") from exc

    _log_upstream_response(trace_id, "fetch_videos", response)

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid Synthesia API key")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Failed to fetch videos from Synthesia")

    payload = response.json()
    logger.info("[%s] Parsed videos payload type=%s", trace_id, type(payload).__name__)
    return payload.get("videos", payload if isinstance(payload, list) else [])


def _download_xliff(api_key: str, video_id: str, trace_id: str) -> bytes:
    endpoints = [
        f"{SYNTHESIA_API_BASE}/videos/{video_id}/captions?format=xliff",
        f"{SYNTHESIA_API_BASE}/videos/{video_id}/xliff",
    ]

    last_error: str | None = None
    for url in endpoints:
        logger.info(
            "[%s] Attempting XLIFF download video_id=%s url=%s api_key=%s",
            trace_id,
            video_id,
            url,
            _mask_secret(api_key.strip()),
        )
        try:
            response = requests.get(
                url,
                headers=_synthesia_headers(api_key),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            logger.exception("[%s] XLIFF request failed for url=%s", trace_id, url)
            last_error = str(exc)
            continue

        _log_upstream_response(trace_id, "download_xliff", response)

        if response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid Synthesia API key")

        if response.status_code == 200 and response.content:
            logger.info("[%s] Successful XLIFF download from url=%s", trace_id, url)
            return _extract_xliff_payload(response)
        last_error = f"status={response.status_code}"

    raise HTTPException(
        status_code=502,
        detail=f"Failed to download XLIFF from Synthesia ({last_error})",
    )


def _extract_xliff_payload(response: requests.Response) -> bytes:
    """Extract raw XML from either direct XML or JSON-wrapped API responses."""
    content = response.content.strip()
    content_type = response.headers.get("content-type", "").lower()

    if "json" in content_type:
        try:
            payload = response.json()
        except json.JSONDecodeError:
            raise HTTPException(status_code=502, detail="Synthesia returned invalid JSON")

        if isinstance(payload, dict):
            for key in ("xliff", "content", "data"):
                value = payload.get(key)
                if isinstance(value, str) and "<xliff" in value:
                    return value.encode("utf-8")

        raise HTTPException(status_code=502, detail="Synthesia response does not contain XLIFF")

    if b"<xliff" in content:
        start = content.find(b"<")
        return content[start:]

    raise HTTPException(status_code=502, detail="Synthesia response is not valid XLIFF")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/videos")
def get_videos(api_key: str):
    trace_id = uuid4().hex[:8]
    logger.info("[%s] /videos request received", trace_id)
    videos = _fetch_videos(api_key, trace_id)
    result = [
        {
            "id": video.get("id"),
            "title": video.get("title") or video.get("name") or video.get("id"),
            "status": video.get("status"),
        }
        for video in videos
        if video.get("id")
    ]
    logger.info("[%s] Returning %s videos to client", trace_id, len(result))
    return {"videos": result}


@app.post("/export-pdf")
def export_pdf(
    background_tasks: BackgroundTasks,
    api_key: str = Form(...),
    video_id: str = Form(...),
):
    trace_id = uuid4().hex[:8]
    logger.info("[%s] /export-pdf request received video_id=%s", trace_id, video_id)
    xliff_content = _download_xliff(api_key, video_id, trace_id)

    temp_dir = Path(tempfile.mkdtemp(prefix="synthesia_export_"))
    xliff_path = temp_dir / f"{video_id}.xliff"
    pdf_path = temp_dir / f"{video_id}.pdf"

    try:
        xliff_path.write_bytes(xliff_content)
        logger.info("[%s] Wrote XLIFF to %s (%s bytes)", trace_id, xliff_path, len(xliff_content))
    except OSError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to store XLIFF locally") from exc

    try:
        xliff_content = xliff_path.read_bytes()
        logger.info("[%s] Re-read XLIFF from %s", trace_id, xliff_path)
    except OSError as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to read stored XLIFF") from exc

    try:
        scenes = parse_scenes_from_xliff(xliff_content)
        logger.info("[%s] Parsed XLIFF scenes count=%s", trace_id, len(scenes))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not scenes:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail="No scenes found in XLIFF")

    try:
        generate_pdf(scenes, pdf_path)
        logger.info("[%s] PDF generated at %s", trace_id, pdf_path)
    except Exception as exc:  # defensive
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to generate PDF") from exc

    background_tasks.add_task(shutil.rmtree, temp_dir, True)
    logger.info("[%s] Scheduled cleanup for %s", trace_id, temp_dir)

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{video_id}.pdf",
    )

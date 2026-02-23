from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import requests
from fastapi import BackgroundTasks, FastAPI, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from parser import parse_scenes_from_xliff
from pdf_generator import generate_pdf

SYNTHESIA_API_BASE = os.getenv("SYNTHESIA_API_BASE", "https://api.synthesia.io/v2").rstrip("/")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))


def _parse_allowed_origins() -> list[str]:
    configured = os.getenv("ALLOWED_ORIGINS")
    if configured:
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    default_origins = [
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    pages_origin = os.getenv("GITHUB_PAGES_ORIGIN")
    if pages_origin:
        default_origins.append(pages_origin.strip().rstrip("/"))

    return default_origins


ALLOWED_ORIGINS = _parse_allowed_origins()

app = FastAPI(title="Synthesia XLIFF PDF Exporter")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _synthesia_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": api_key,
        "Accept": "application/json",
    }


def _fetch_videos(api_key: str) -> list[dict]:
    try:
        response = requests.get(
            f"{SYNTHESIA_API_BASE}/videos",
            headers=_synthesia_headers(api_key),
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Unable to reach Synthesia API") from exc

    if response.status_code == 401:
        raise HTTPException(status_code=401, detail="Invalid Synthesia API key")
    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Failed to fetch videos from Synthesia")

    payload = response.json()
    return payload.get("videos", payload if isinstance(payload, list) else [])


def _download_xliff(api_key: str, video_id: str) -> bytes:
    endpoints = [
        f"{SYNTHESIA_API_BASE}/videos/{video_id}/captions?format=xliff",
        f"{SYNTHESIA_API_BASE}/videos/{video_id}/xliff",
    ]

    last_error: str | None = None
    for url in endpoints:
        try:
            response = requests.get(
                url,
                headers=_synthesia_headers(api_key),
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            last_error = str(exc)
            continue

        if response.status_code == 200 and response.content:
            return response.content
        last_error = f"status={response.status_code}"

    raise HTTPException(
        status_code=502,
        detail=f"Failed to download XLIFF from Synthesia ({last_error})",
    )


@app.get("/videos")
def get_videos(api_key: str):
    videos = _fetch_videos(api_key)
    result = [
        {
            "id": video.get("id"),
            "title": video.get("title") or video.get("name") or video.get("id"),
            "status": video.get("status"),
        }
        for video in videos
        if video.get("id")
    ]
    return {"videos": result}


@app.post("/export-pdf")
def export_pdf(
    background_tasks: BackgroundTasks,
    api_key: str = Form(...),
    video_id: str = Form(...),
):
    xliff_content = _download_xliff(api_key, video_id)

    try:
        scenes = parse_scenes_from_xliff(xliff_content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not scenes:
        raise HTTPException(status_code=422, detail="No scenes found in XLIFF")

    temp_dir = Path(tempfile.mkdtemp(prefix="synthesia_export_"))
    pdf_path = temp_dir / f"{video_id}.pdf"

    try:
        generate_pdf(scenes, pdf_path)
    except Exception as exc:  # defensive
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to generate PDF") from exc

    background_tasks.add_task(shutil.rmtree, temp_dir, True)

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"{video_id}.pdf",
    )

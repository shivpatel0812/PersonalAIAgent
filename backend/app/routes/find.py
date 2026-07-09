"""API routes for the universal Find feature."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.db.find_sessions import create_session
from app.universal.find.models import FindMessageFeedback, FindTurnResponse
from app.universal.find.service import get_session_response, handle_message, reset_session

router = APIRouter(prefix="/find", tags=["find"])

_IMAGE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


def _is_safe_image_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if host in {"localhost", "127.0.0.1"} or host.endswith(".local"):
        return False
    if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
        return False
    return True


class CreateSessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    feedback: FindMessageFeedback = None


@router.post("/sessions", response_model=CreateSessionResponse)
def create_find_session() -> CreateSessionResponse:
    try:
        row = create_session()
        return CreateSessionResponse(session_id=str(row["id"]))
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/sessions/{session_id}", response_model=FindTurnResponse)
def get_find_session(session_id: str) -> FindTurnResponse:
    try:
        return get_session_response(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/message", response_model=FindTurnResponse)
async def post_find_message(session_id: str, body: MessageRequest) -> FindTurnResponse:
    if not body.message.strip() and body.feedback is None:
        raise HTTPException(status_code=400, detail="message or feedback is required")
    try:
        return await handle_message(
            session_id,
            message=body.message,
            feedback=body.feedback,
        )
    except ValueError as exc:
        detail = str(exc)
        status = 404 if "not found" in detail.lower() else 503
        raise HTTPException(status_code=status, detail=detail) from exc


@router.post("/sessions/{session_id}/reset", response_model=FindTurnResponse)
def post_find_reset(session_id: str) -> FindTurnResponse:
    try:
        return reset_session(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/image-proxy")
def get_find_image_proxy(url: str = Query(..., min_length=8, max_length=2000)) -> Response:
    if not _is_safe_image_url(url):
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        response = httpx.get(
            url,
            headers=_IMAGE_HEADERS,
            follow_redirects=True,
            timeout=12.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch image: {exc}") from exc

    content_type = response.headers.get("content-type", "image/jpeg")
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=502, detail="URL did not return an image")

    return Response(
        content=response.content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )

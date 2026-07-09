"""API routes for the universal Find feature."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db.find_sessions import create_session
from app.universal.find.models import FindTurnResponse, ThumbFeedback
from app.universal.find.service import get_session_response, handle_message, reset_session

router = APIRouter(prefix="/find", tags=["find"])


class CreateSessionResponse(BaseModel):
    session_id: str


class MessageRequest(BaseModel):
    message: str = Field(default="", max_length=4000)
    feedback: ThumbFeedback | None = None


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
def post_find_message(session_id: str, body: MessageRequest) -> FindTurnResponse:
    if not body.message.strip() and body.feedback is None:
        raise HTTPException(status_code=400, detail="message or feedback is required")
    try:
        return handle_message(
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

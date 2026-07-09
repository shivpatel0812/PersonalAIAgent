"""Data models for the universal Find feature."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class FindRequest(BaseModel):
    subject: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ready", "needs_clarification"]
    missing: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None


class FindResult(BaseModel):
    index: int
    title: str
    snippet: str
    url: str
    image_url: str | None = None


class ThumbFeedback(BaseModel):
    type: Literal["thumb"] = "thumb"
    index: int = Field(ge=1, le=10)
    value: Literal["up", "down"]


class FindSessionState(BaseModel):
    phase: Literal["gathering", "results"] = "gathering"
    request: FindRequest | None = None
    last_query: str | None = None
    last_results: list[FindResult] = Field(default_factory=list)


class FindMessageRecord(BaseModel):
    id: str
    role: Literal["user", "assistant"]
    content: str
    payload: dict[str, Any] | None = None
    created_at: str | None = None


class FindTurnResponse(BaseModel):
    session_id: str
    phase: Literal["gathering", "results"]
    assistant_message: str | None = None
    request: FindRequest | None = None
    results: list[FindResult] = Field(default_factory=list)
    messages: list[FindMessageRecord] = Field(default_factory=list)

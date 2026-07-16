from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    profile_id: Literal["A", "B", "C", "D"] = "A"


class ChatAccepted(BaseModel):
    request_id: str
    status: str
    profile_id: str


class JobStatus(BaseModel):
    request_id: str
    status: str
    current_stage: str
    profile_id: str
    profile: dict[str, Any]
    started_at: str
    finished_at: str | None = None
    elapsed_seconds: float
    result: dict[str, Any] | None = None
    judge: dict[str, Any] | None = None
    error: str | None = None

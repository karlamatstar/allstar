from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from allstar.voc.api.validation import is_valid_question_text


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    profile_id: Literal["A", "B", "C", "D"] = "A"

    @field_validator("question")
    @classmethod
    def validate_question_text(cls, value: str) -> str:
        value = value.strip()
        if not is_valid_question_text(value):
            raise ValueError("질문 문자가 손상되었거나 유효한 내용이 없습니다. 한글 입력 상태를 확인해 주세요.")
        return value


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
    stage_states: list[str] | None = None
    stage_details: list[Any] | None = None

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, description="사용자 질문")
    is_latency_test: bool = Field(default=False, description="과금 방지용 성능 테스트 모드 여부")
    simulate_api_disconnect: bool = Field(default=False, description="의도적 API 끊김 에러 유도 여부")


class ChatResponse(BaseModel):
    answer: str = Field(description="API 기반 에이전트 답변 (주 답변)")
    rule_answer: str = Field(description="규칙 기반 에이전트 답변 (비교용)")
    latency_ms: float
    request_id: str | None = Field(default=None, description="대화와 백그라운드 채점을 연결하는 내부 식별자")


class HealthResponse(BaseModel):
    status: str

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from allstar.ai_agent.api.config import OPENAI_MODEL
from allstar.ai_agent.api.judge_agent import JudgeUnavailableError, get_evaluation_from_openai
from allstar.ai_agent.api.logger_config import log_conversation, log_evaluation, logger
from allstar.ai_agent.api.metrics import chat_request_latency_seconds, chat_requests_total, judge_axis_score, judge_evaluations_total, judge_score_total, metrics_app
from allstar.ai_agent.api.rule_based_agent import get_answer_from_rule_based_agent
from allstar.ai_agent.api.schemas import ChatRequest, ChatResponse, HealthResponse
from allstar.ai_agent.api.service_agent import ApiAgentUnavailableError, get_answer_from_api_agent
from allstar.shared.paths import REPORT_ROOT

AXES = ["accuracy", "groundedness", "helpfulness", "safety", "understandability"]

# Judge 지표/로그에 쓰는 모델 구분 라벨 (규칙기반 vs API기반 실시간 비교 채점)
MODEL_API = "api"
MODEL_RULE = "rule"
MODEL_LABELS = {MODEL_API: "실시간-API기반", MODEL_RULE: "실시간-규칙기반"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # API 키가 없어도 Health, Swagger, 규칙 기반 기능은 실행한다.
    # OpenAI 기능은 실제 호출 시 service_agent와 judge_agent가 키를 검증한다.
    yield


app = FastAPI(title="AI Agent Quality Portfolio", lifespan=lifespan)
app.mount("/metrics", metrics_app)
REPORT_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORT_ROOT)), name="reports")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")

@app.get("/fault-lab", tags=["Chaos Test"])
async def fault_lab(scenario: str = "normal", delay_seconds: float = 0.0):
    """
    장애 모의 훈련(Chaos Test)을 위한 엔드포인트입니다.
    """
    if scenario == "delay":
        await asyncio.sleep(delay_seconds)
        return {"status": "delayed", "delay_seconds": delay_seconds}
    elif scenario == "error500":
        raise HTTPException(status_code=500, detail="시스템 내부 오류가 발생했습니다.")
    elif scenario == "timeout":
        await asyncio.sleep(delay_seconds)
        raise HTTPException(status_code=504, detail="Gateway Timeout")
    elif scenario == "wrong":
        raise HTTPException(status_code=400, detail="잘못된 파라미터입니다.")

    return {"status": "ok", "scenario": scenario}

def _create_na_evaluation(reason: str) -> dict:
    return {
        "accuracy": {"score": 0, "reason": reason},
        "groundedness": {"score": 0, "reason": reason},
        "helpfulness": {"score": 0, "reason": reason},
        "safety": {"score": 0, "reason": reason},
        "understandability": {"score": 0, "reason": reason},
        "total_score": 0,
        "overall_decision": "N/A",
        "summary": reason,
    }


def _score_both_and_check_jira_background(question: str, api_answer: str, rule_answer: str, request_id: str, is_api_error: bool = False) -> None:
    api_eval = {}
    rule_eval = {}

    # Score API
    if is_api_error:
        api_eval = _create_na_evaluation("에이전트 API 호출이 실패(또는 타임아웃)하여 채점할 수 없습니다.")
        judge_evaluations_total.labels(decision="FAIL", model=MODEL_API).inc()
        log_evaluation(question, api_eval, model=MODEL_API, request_id=request_id)
    else:
        try:
            api_eval = get_evaluation_from_openai(user_question=question, ai_answer=api_answer, agent_label=MODEL_LABELS.get(MODEL_API))
            judge_evaluations_total.labels(decision=api_eval.get("overall_decision", "UNKNOWN"), model=MODEL_API).inc()
            judge_score_total.labels(model=MODEL_API).observe(api_eval.get("total_score", 0))
            for axis in AXES:
                score = api_eval.get(axis, {}).get("score")
                if score is not None:
                    judge_axis_score.labels(axis=axis, model=MODEL_API).observe(score)
            log_evaluation(question, api_eval, model=MODEL_API, request_id=request_id)
        except JudgeUnavailableError as error:
            api_eval = _create_na_evaluation(f"저지 에이전트 호출 실패: {error}")
            judge_evaluations_total.labels(decision="FAIL", model=MODEL_API).inc()
            log_evaluation(question, api_eval, model=MODEL_API, request_id=request_id)
        except Exception as error:
            logger.warning(f"실시간 채점 실패(model=api): {error}")

    # Score Rule
    try:
        rule_eval = get_evaluation_from_openai(user_question=question, ai_answer=rule_answer, agent_label=MODEL_LABELS.get(MODEL_RULE))
        judge_evaluations_total.labels(decision=rule_eval.get("overall_decision", "UNKNOWN"), model=MODEL_RULE).inc()
        judge_score_total.labels(model=MODEL_RULE).observe(rule_eval.get("total_score", 0))
        for axis in AXES:
            score = rule_eval.get(axis, {}).get("score")
            if score is not None:
                judge_axis_score.labels(axis=axis, model=MODEL_RULE).observe(score)
        log_evaluation(question, rule_eval, model=MODEL_RULE, request_id=request_id)
    except JudgeUnavailableError as error:
        rule_eval = _create_na_evaluation(f"저지 에이전트 호출 실패: {error}")
        judge_evaluations_total.labels(decision="FAIL", model=MODEL_RULE).inc()
        log_evaluation(question, rule_eval, model=MODEL_RULE, request_id=request_id)
    except Exception as error:
        logger.warning(f"실시간 채점 실패(model=rule): {error}")

    # Check for FAIL or REVIEW
    api_decision = api_eval.get("overall_decision", "PASS")
    rule_decision = rule_eval.get("overall_decision", "PASS")

    if api_decision in ["FAIL", "REVIEW"] or rule_decision in ["FAIL", "REVIEW"]:
        import datetime
        from allstar.ai_agent.api.jira_client import create_jira_issue_for_question
        from allstar.ai_agent.evaluation.defect_logger import log_defect_to_markdown

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        target_eval = api_eval if api_decision in ["FAIL", "REVIEW"] else rule_eval
        target_model_name = "API 기반 챗봇" if api_decision in ["FAIL", "REVIEW"] else "Rule 기반 챗봇"

        log_defect_to_markdown(
            request_id=request_id,
            timestamp=timestamp,
            question=question,
            evaluation=target_eval,
            model_name=target_model_name,
            judge_name=OPENAI_MODEL
        )

        create_jira_issue_for_question(
            request_id=request_id,
            timestamp=timestamp,
            question=question,
            api_eval=api_eval,
            rule_eval=rule_eval,
            answer_model=OPENAI_MODEL,
            judge_model=OPENAI_MODEL
        )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, background_tasks: BackgroundTasks) -> ChatResponse:
    start = time.perf_counter()

    # 챗봇 UI에서 직접 에러 상황을 재현하기 위한 백도어(마법 단어)
    clean_question = request.question.replace(" ", "")
    if "퇴근" in clean_question:
        request.simulate_api_disconnect = True

    if "강사" in clean_question:
        # 504 타임아웃 모의 (10초 대기)
        time.sleep(10)
        chat_requests_total.labels(status="error").inc()
        logger.error("API 응답 타임아웃 장애 모의 발생 (504)")
        answer = "API 서버 응답 시간이 지연되어 타임아웃이 발생했습니다. 트래픽이 많거나 서버에 과부하가 걸렸습니다. (504 Gateway Timeout)"
        rule_answer = get_answer_from_rule_based_agent(request.question)
        latency_ms = (time.perf_counter() - start) * 1000
        request_id = uuid.uuid4().hex
        log_conversation(request.question, answer, latency_ms, rule_answer=rule_answer, request_id=request_id)
        background_tasks.add_task(_score_both_and_check_jira_background, request.question, answer, rule_answer, request_id, False)
        return ChatResponse(answer=answer, rule_answer=rule_answer, latency_ms=latency_ms)

    is_api_error = False
    try:
        answer = get_answer_from_api_agent(request.question, simulate_api_disconnect=request.simulate_api_disconnect)
    except ApiAgentUnavailableError as error:
        chat_requests_total.labels(status="error").inc()
        logger.error(f"API 끊김 장애 발생: {error}")
        answer = "현재 API 서버 점검 중이거나 일시적인 통신 장애가 발생했습니다. 잠시 후 다시 시도해 주세요. (503 Service Unavailable)"
        is_api_error = True

    # 규칙 기반 답변은 로컬 키워드 매칭이라 실패/지연 없이 즉시 생성된다 (비교용)
    rule_answer = get_answer_from_rule_based_agent(request.question)

    latency_ms = (time.perf_counter() - start) * 1000
    chat_request_latency_seconds.observe(latency_ms / 1000)
    chat_requests_total.labels(status="success").inc()

    if not request.is_latency_test:
        request_id = uuid.uuid4().hex
        log_conversation(request.question, answer, latency_ms, rule_answer=rule_answer, request_id=request_id)
        background_tasks.add_task(_score_both_and_check_jira_background, request.question, answer, rule_answer, request_id, is_api_error)

    return ChatResponse(answer=answer, rule_answer=rule_answer, latency_ms=round(latency_ms, 1))

@app.post("/chat_mock", response_model=ChatResponse, tags=["Performance Test"])
async def chat_mock(request: ChatRequest) -> ChatResponse:
    """
    K6 성능 테스트 전용 Mock API.
    실제 OpenAI 서버에 요청을 보내지 않고, 1~2초의 지연 후 더미 데이터를 반환하여
    과금 및 Rate Limit 방지와 함께 순수 서버 아키텍처 부하 처리량을 측정합니다.
    """
    start = time.perf_counter()

    # OpenAI API 응답 지연(Latency)을 흉내냅니다 (1.5초 대기)
    await asyncio.sleep(1.5)

    answer = "이것은 K6 부하 테스트를 위한 가짜(Mock) 응답입니다."
    rule_answer = "Mock 규칙 기반 응답입니다."

    latency_ms = (time.perf_counter() - start) * 1000

    # 프로메테우스 지표 수집
    chat_request_latency_seconds.observe(latency_ms / 1000)
    chat_requests_total.labels(status="success").inc()

    # Mock 테스트이므로 Background Task(AI Judge 채점)와 로깅은 생략합니다.
    return ChatResponse(answer=answer, rule_answer=rule_answer, latency_ms=round(latency_ms, 1))

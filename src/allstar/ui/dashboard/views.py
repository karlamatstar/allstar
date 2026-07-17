from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from allstar.ai_agent.evaluation.live_report_status import ACTIVE_STATES, STATUS_PATH, read_status
from allstar.shared.model_profiles import public_profiles
from allstar.shared.paths import (
    AI_AGENT_LOG_ROOT,
    AI_AGENT_REPORT_ROOT,
    PROJECT_ROOT,
    REPORT_ROOT,
    VOC_LOG_ROOT,
    VOC_REPORT_ROOT,
)
from allstar.voc.evaluation.progress import read_progress


PORTFOLIO_API = os.getenv("PORTFOLIO_API_URL", "http://localhost:8000")
VOC_API = os.getenv("VOC_API_URL", "http://localhost:8100")
GRAFANA = os.getenv("GRAFANA_URL", "http://localhost:3000").rstrip("/")
TIMEOUT = httpx.Timeout(190.0, connect=5.0)
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

AI_CASES_PATH = PROJECT_ROOT / "src" / "allstar" / "ai_agent" / "evaluation" / "test_cases.json"
VOC_CASES_PATH = PROJECT_ROOT / "src" / "allstar" / "voc" / "evaluation" / "test_cases.json"
AI_BATCH_REPORT = AI_AGENT_REPORT_ROOT / "batch" / "evaluation_result.csv"
AI_LIVE_REPORT = AI_AGENT_REPORT_ROOT / "live" / "live_report.csv"
AI_CONVERSATIONS = AI_AGENT_LOG_ROOT / "live" / "conversations" / "conversations.jsonl"
AI_JUDGMENTS = AI_AGENT_LOG_ROOT / "live" / "judgments" / "live_evaluations.jsonl"
PROCESS_LOG_ROOT = PROJECT_ROOT / "_OUTPUT" / "logs" / "services" / "launcher"
GRAFANA_DASHBOARD_PATHS = {
    "ai-agent-quality": PROJECT_ROOT / "ops" / "monitoring" / "grafana_dashboard.json",
    "k6-performance-test": PROJECT_ROOT / "ops" / "monitoring" / "k6_dashboard.json",
    "voc-live-operations": PROJECT_ROOT / "ops" / "monitoring" / "voc_live_dashboard.json",
    "voc-qa-abcd": PROJECT_ROOT / "ops" / "monitoring" / "voc_qa_dashboard.json",
}
GRAFANA_GRID_ROW_HEIGHT = 38
GRAFANA_FRAME_PADDING = 170
MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
LOCAL_TIMEZONE = datetime.now().astimezone().tzinfo
LOCAL_TIME_FORMAT = "%Y/%m/%d - %H:%M:%S"

DECISION_COLORS = {"PASS": "#188a4c", "REVIEW": "#c07a12", "FAIL": "#c0392b", "N/A": "#6b7280", "미채점": "#6b7280"}
SCORE_COLUMNS = ["accuracy_score", "groundedness_score", "helpfulness_score", "safety_score", "understandability_score"]
SCORE_LABELS = {
    "accuracy_score": "정확성",
    "groundedness_score": "근거성",
    "helpfulness_score": "유용성",
    "safety_score": "안전성",
    "understandability_score": "이해가능성",
}
STAGES = [
    ("Interpreter", "질문 의도 분석"),
    ("Retriever", "관련 의견 검색"),
    ("Summarizer", "내용 요약"),
    ("Evaluator", "초기 품질 평가"),
    ("Critic", "결과 검토"),
    ("Improver", "최종 답변 개선"),
    ("LLM Judge", "독립 품질 평가"),
]


def reasoning_text(value: str) -> str:
    return {"none": "추론 끔(none)", "low": "낮음(low)", "medium": "중간(medium)", "high": "높음(high)"}.get(value, value)


def _safe_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _local_time_text(value: Any = None) -> str:
    """UTC 문자열이나 datetime을 실행 컴퓨터의 로컬 시간 문자열로 표시한다."""
    if value is None:
        return datetime.now().astimezone().strftime(LOCAL_TIME_FORMAT)
    try:
        parsed = pd.to_datetime(value, errors="raise", utc=True)
        return parsed.tz_convert(LOCAL_TIMEZONE).strftime(LOCAL_TIME_FORMAT)
    except (TypeError, ValueError):
        return str(value)


def _localize_timestamp_columns(df: pd.DataFrame) -> pd.DataFrame:
    view = df.copy()
    for column in ("timestamp", "started_at", "updated_at", "completed_at"):
        if column in view:
            view[column] = view[column].map(_local_time_text)
    return view


def _clear_ai_live_caches() -> None:
    _read_csv.clear()
    _read_jsonl.clear()


def _ai_report_status() -> dict[str, Any]:
    return read_status(STATUS_PATH)


@st.cache_data(ttl=2)
def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    _read_json.clear()


@st.cache_data(ttl=2)
def _read_csv(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return None


@st.cache_data(ttl=2)
def _read_jsonl(path: Path, limit: int = 500) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return pd.DataFrame(rows)


@st.cache_data(ttl=2, show_spinner=False)
def _get_json(url: str) -> dict | list | None:
    try:
        timeout = httpx.Timeout(1.5, connect=0.5)
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


def _section(title: str, help_text: str | None = None) -> None:
    st.subheader(title)
    if help_text:
        st.caption(help_text)


def _required_api_confirmation(key: str, label: str) -> bool:
    """실제 외부 API 실행 전에 반드시 확인해야 하는 항목을 강조해 표시한다."""
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key)
    with st.container(key=f"required_api_confirm_{safe_key}"):
        st.markdown("<div class='required-confirm-title'>필수 체크 사항</div>", unsafe_allow_html=True)
        return st.checkbox(label, key=key)


def _render_dataframe(df: pd.DataFrame, height: int = 330) -> None:
    st.dataframe(_localize_timestamp_columns(df), width="stretch", height=height, hide_index=True)


def _render_decision_metrics(df: pd.DataFrame, decision_column: str = "overall_decision") -> None:
    values = df.get(decision_column, pd.Series(dtype=str)).fillna("N/A")
    cols = st.columns(5)
    for col, label in zip(cols, ["전체", "PASS", "REVIEW", "FAIL", "N/A"]):
        count = len(values) if label == "전체" else int((values == label).sum())
        col.metric(label, count)


def _next_case_id(cases: list[dict], digits: int) -> str:
    numbers = []
    for case in cases:
        match = re.fullmatch(r"TC-(\d+)", str(case.get("case_id", "")))
        if match:
            numbers.append(int(match.group(1)))
    return f"TC-{max(numbers, default=0) + 1:0{digits}d}"


def _launch_process(
    state_key: str,
    command: list[str],
    log_prefix: str,
    run_id: str | None = None,
) -> str:
    PROCESS_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = PROCESS_LOG_ROOT / f"{log_prefix}_{run_id}.log"
    stream = log_path.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=stream,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=CREATE_NO_WINDOW,
    )
    stream.close()
    st.session_state[state_key] = {"process": process, "log_path": str(log_path), "started_at": time.time(), "run_id": run_id}
    return run_id


def _read_process_output(path: Path) -> str:
    """신규 UTF-8 로그와 과거 Windows CP949 로그를 모두 읽는다."""
    if not path.exists():
        return ""
    raw = path.read_bytes()
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp949", errors="replace")


def _render_process(state_key: str, label: str) -> tuple[bool, str]:
    state = st.session_state.get(state_key)
    if not state:
        return False, ""
    process: subprocess.Popen = state["process"]
    log_path = Path(state["log_path"])
    output = _read_process_output(log_path)
    return_code = process.poll()
    elapsed = time.time() - state["started_at"]
    if return_code is None:
        st.info(f"{label} 실행 중 · {elapsed:.1f}초 경과")
        if st.button("실행 중지", key=f"stop_{state_key}"):
            process.terminate()
            st.session_state.pop(state_key, None)
            st.rerun()
        with st.expander("실행 내용 보기", expanded=True):
            st.code(output[-12000:] or "준비 중...", language="text")
        time.sleep(1)
        st.rerun()
    else:
        if return_code == 0:
            st.success(f"{label} 완료 · {elapsed:.1f}초")
        else:
            st.error(f"{label} 종료 코드 {return_code} · {elapsed:.1f}초")
        with st.expander("실행 내용 보기"):
            st.code(output[-12000:] or "출력 없음", language="text")
        if st.button("완료 상태 닫기", key=f"clear_{state_key}"):
            st.session_state.pop(state_key, None)
            _read_csv.clear()
            st.rerun()
    return return_code is None, output


def _status_stage_states(status: dict) -> list[str]:
    if status.get("_stage_states"):
        return list(status["_stage_states"])
    job_status = status.get("status")
    current = status.get("current_stage", "")
    if job_status == "queued":
        return ["pending"] * 7
    if job_status == "failed":
        return ["failed"] + ["skipped"] * 6
    if job_status == "completed":
        states = ["done"] * 7
        if status.get("error") and not status.get("judge"):
            states[-1] = "failed"
        return states
    if "Judge" in current:
        return ["done"] * 6 + ["running"]
    return ["running"] * 6 + ["pending"]


def _status_stage_details(status: dict) -> list[Any]:
    if status.get("_stage_details"):
        return list(status["_stage_details"])
    result = status.get("result") or {}
    trace = str(result.get("trace") or "")
    retriever = ""
    match = re.search(r"Retriever:count=([^;]+)", trace)
    if match:
        retriever = match.group(0)
    return [
        _safe_json(result.get("intent_json") or "아직 결과가 없습니다."),
        retriever or trace or "아직 결과가 없습니다.",
        result.get("summary") or "아직 결과가 없습니다.",
        _safe_json(result.get("eval_json") or "아직 결과가 없습니다."),
        _safe_json(result.get("summary_critic_json") or "아직 결과가 없습니다."),
        result.get("policy") or result.get("answer") or "아직 결과가 없습니다.",
        status.get("judge") or status.get("error") or "아직 결과가 없습니다.",
    ]


def _render_stage_flow(states: list[str]) -> None:
    state_labels = {"pending": "대기", "running": "처리 중", "done": "완료", "failed": "실패", "skipped": "건너뜀"}
    nodes = []
    for index, ((english, korean), state) in enumerate(zip(STAGES, states)):
        nodes.append(
            f"<div class='stage-node stage-{state}'><span>{index + 1}</span>"
            f"<b>{html.escape(korean)}</b><small>{html.escape(english)}</small>"
            f"<em>{state_labels[state]}</em></div>"
        )
        if index < len(STAGES) - 1:
            nodes.append("<div class='stage-arrow' aria-hidden='true'>→</div>")
    st.markdown(f"<div class='stage-flow'>{''.join(nodes)}</div>", unsafe_allow_html=True)


def _render_stage_explorer(status: dict, key_prefix: str, interactive: bool = True) -> None:
    states = _status_stage_states(status)
    details = _status_stage_details(status)
    symbols = {"pending": "○", "running": "◔", "done": "✓", "failed": "!", "skipped": "－"}
    state_labels = {"pending": "대기", "running": "처리 중", "done": "완료", "failed": "실패", "skipped": "건너뜀"}
    selected_key = f"{key_prefix}_selected_stage"
    st.session_state.setdefault(selected_key, 0)
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key_prefix)
    with st.container(key=f"stage_scroll_{safe_key}"):
        _render_stage_flow(states)
        if interactive:
            with st.container(horizontal=True, gap="small", key=f"stage_buttons_{safe_key}"):
                for index, (english, korean) in enumerate(STAGES):
                    state = states[index]
                    with st.container(width=180, key=f"stage_cell_{safe_key}_{index}"):
                        if st.button(
                            f"{symbols[state]} {index + 1}. {korean}\n({english}) {state_labels[state]}",
                            key=f"{key_prefix}_stage_{index}",
                            disabled=state in {"pending", "running"},
                            width="stretch",
                        ):
                            st.session_state[selected_key] = index
                    if index < len(STAGES) - 1:
                        with st.container(width=26, key=f"stage_arrow_{safe_key}_{index}"):
                            st.markdown(
                                "<div class='stage-button-arrow'>→</div>",
                                unsafe_allow_html=True,
                            )
    if not interactive:
        return
    selected = st.session_state[selected_key]
    english, korean = STAGES[selected]
    st.markdown(f"#### {selected + 1}단계 · {korean} ({english})")
    value = details[selected]
    if isinstance(value, (dict, list)):
        st.json(value)
    else:
        st.markdown(f"<div class='stage-detail'>{html.escape(str(value)).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)


def _latest_judgment_view(judgments: pd.DataFrame) -> pd.DataFrame:
    """원본 ID는 숨기고 같은 요청·모델의 최신 평가만 사람이 읽기 좋은 표로 만든다."""
    if judgments.empty:
        return judgments
    source = judgments.copy()
    source["_sort_time"] = pd.to_datetime(source.get("timestamp"), errors="coerce", utc=True)
    source = source.sort_values("_sort_time")
    if {"request_id", "model"}.issubset(source.columns):
        with_id = source["request_id"].notna()
        current = source[with_id].drop_duplicates(["request_id", "model"], keep="last")
        legacy = source[~with_id]
        source = pd.concat([current, legacy], ignore_index=True)

    evaluations = source.get("evaluation", pd.Series([{}] * len(source))).map(_safe_json)
    evaluations = evaluations.map(lambda value: value if isinstance(value, dict) else {})
    view = pd.DataFrame({
        "시간": source.get("timestamp", pd.Series([None] * len(source))).map(_local_time_text),
        "질문": source.get("question", pd.Series([""] * len(source))),
        "모델": source.get("model", pd.Series([""] * len(source))).map(
            {"api": "서버 연결 방식(API)", "rule": "규칙 기반"}
        ).fillna(source.get("model", pd.Series([""] * len(source)))),
        "총점": evaluations.map(lambda value: value.get("total_score")),
        "판정": evaluations.map(lambda value: value.get("overall_decision", "N/A")),
        "평가 내용(Evaluation)": evaluations.map(lambda value: json.dumps(value, ensure_ascii=False)),
    })
    return view.sort_values("시간", ascending=False)


def _conversation_log_view(conversations: pd.DataFrame, judgments: pd.DataFrame) -> pd.DataFrame:
    """대화 원본 ID는 숨기고 백그라운드 평가 진행 상태를 함께 표시한다."""
    view = conversations.copy()
    judgment_counts: dict[str, int] = {}
    if not judgments.empty and {"request_id", "model"}.issubset(judgments.columns):
        judgment_counts = judgments.dropna(subset=["request_id"]).groupby("request_id")["model"].nunique().to_dict()

    if "request_id" in view:
        view["채점 상태"] = view["request_id"].map(
            lambda request_id: (
                "완료" if judgment_counts.get(request_id, 0) >= 2
                else "진행 중" if judgment_counts.get(request_id, 0) == 1
                else "채점 대기"
            )
        )
    else:
        view["채점 상태"] = "상태 확인 불가"
    return view.drop(columns=["request_id"], errors="ignore")


def _render_ai_report_status(status: dict[str, Any], key: str) -> None:
    active = list(status.get("active_jobs") or [])
    latest = status.get("latest") or {}
    if active:
        completed = sum(int(job.get("completed", 0)) for job in active)
        total = sum(int(job.get("total", 2)) for job in active)
        message = latest.get("message") or "새로운 품질 보고서를 작성 중입니다."
        status_box = st.status(
            f"{message} 대기 작업 {len(active)}건 · 평가 {completed}/{max(total, 1)}",
            state="running",
            expanded=False,
        )
        status_box.caption("완료되면 품질 현황·유형별 비교·대화별 채점 상세가 자동 갱신됩니다.")
        status_box.update(state="running")
    elif latest.get("state") == "FAILED":
        st.error(f"{latest.get('message', '품질 보고서 작성에 실패했습니다.')} {latest.get('error', '')}".strip())
    elif latest.get("state") == "COMPLETED":
        st.success("새로운 품질 보고서가 반영되었습니다.")

    if st.button(
        "↻ AI 에이전트 데이터 갱신",
        key=f"ai_live_refresh_{key}",
        disabled=bool(active),
        help="누적 대화·채점 로그를 다시 읽고 최신 품질 보고서를 재생성합니다.",
    ):
        try:
            from allstar.ai_agent.evaluation.live_report_generator import generate_live_report

            with st.spinner("누적 로그로 최신 품질 보고서를 다시 작성하고 있습니다..."):
                generate_live_report()
            _clear_ai_live_caches()
            st.toast("AI 에이전트 품질 보고서를 갱신했습니다.", icon="✅")
            st.rerun(scope="app")
        except Exception as error:
            st.error(f"품질 보고서를 갱신하지 못했습니다: {error}")


def _render_ai_data_tab(kind: str, status: dict[str, Any]) -> None:
    active = bool(status.get("active_count"))
    conversations = _read_jsonl(AI_CONVERSATIONS)
    judgments = _read_jsonl(AI_JUDGMENTS)
    live_df = _read_csv(AI_LIVE_REPORT)

    if kind == "log":
        _render_ai_report_status(status, "log")
        if conversations.empty:
            st.info("아직 저장된 대화 로그가 없습니다.")
        else:
            conversation_view = _conversation_log_view(conversations, judgments)
            _render_dataframe(conversation_view.sort_values("timestamp", ascending=False))
        st.caption("백그라운드 독립 품질 평가 로그")
        if judgments.empty:
            st.info("아직 독립 품질평가 로그가 없습니다.")
        else:
            _render_dataframe(_latest_judgment_view(judgments), height=430)
    elif kind == "quality":
        _render_ai_report_status(status, "quality")
        if live_df is None or live_df.empty:
            if active:
                st.info("첫 품질 보고서를 작성하고 있습니다. 완료되면 자동으로 표시됩니다.")
            else:
                st.info("아직 자동 생성된 AI 에이전트 챗봇 품질 보고서가 없습니다.")
        else:
            _render_decision_metrics(live_df)
            chart_df = live_df.copy()
            if "timestamp" in chart_df:
                chart_df["표시 시간"] = chart_df["timestamp"].map(_local_time_text)
            chart = px.bar(
                chart_df,
                x="표시 시간" if "표시 시간" in chart_df else chart_df.index,
                y="total_score",
                color="overall_decision",
                color_discrete_map=DECISION_COLORS,
                hover_data=[column for column in ("question", "summary") if column in chart_df],
            )
            st.plotly_chart(chart, width="stretch")
    elif kind == "breakdown":
        _render_ai_report_status(status, "breakdown")
        _render_score_breakdown(live_df, model_column="model")
    elif kind == "detail":
        _render_ai_report_status(status, "detail")
        _render_quality_detail(live_df)


def _render_ai_data_tab_with_refresh(kind: str, initially_active: bool) -> None:
    @st.fragment(run_every="1s" if initially_active else None)
    def _poll_ai_data_tab() -> None:
        status = _ai_report_status()
        active = bool(status.get("active_count"))
        _render_ai_data_tab(kind, status)
        if initially_active and not active:
            _clear_ai_live_caches()
            st.rerun(scope="app")

    _poll_ai_data_tab()


def render_ai_chat() -> None:
    _section("AI 에이전트 챗봇", "기존 포트폴리오의 실시간 대화·로그·품질 분석 기능을 통합한 화면입니다.")
    tab_chat, tab_log, tab_quality, tab_breakdown, tab_detail = st.tabs(
        ["챗봇과 대화", "대화 로그", "품질 현황", "유형별 비교", "대화별 채점 상세"]
    )
    with tab_chat:
        history = st.session_state.setdefault("ai_chat_history", [])
        with st.container(height=520, border=True, autoscroll=True):
            if not history:
                st.caption("AI 에이전트에게 질문하면 이 영역에 메신저 형태로 대화가 표시됩니다.")
            for message in history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
                    label = message.get("label")
                    time_text = message.get("timestamp")
                    if label or time_text:
                        st.caption(" · ".join(value for value in (label, time_text) if value))
        api_confirmed = _required_api_confirmation(
            "ai_chat_api_confirm",
            "메시지 전송 시 외부 AI API 호출과 비용이 발생할 수 있음을 확인했습니다.",
        )
        question = st.chat_input(
            "AI 에이전트에게 질문하세요",
            key="ai_chat_input",
            disabled=not api_confirmed,
        )
        if question:
            history.append({"role": "user", "content": question, "label": "사용자", "timestamp": _local_time_text()})
            try:
                with st.spinner("답변을 생성하고 있습니다..."):
                    with httpx.Client(timeout=TIMEOUT) as client:
                        response = client.post(f"{PORTFOLIO_API}/chat", json={"question": question})
                        response.raise_for_status()
                        body = response.json()
                response_time = _local_time_text()
                history.append({
                    "role": "assistant", "content": body.get("answer", "응답이 없습니다."),
                    "label": "서버 연결 방식(API)", "timestamp": response_time,
                })
                if body.get("rule_answer"):
                    history.append({
                        "role": "assistant", "content": body["rule_answer"],
                        "label": "규칙 기반", "timestamp": response_time,
                    })
                _clear_ai_live_caches()
            except Exception as error:
                history.append({
                    "role": "assistant", "content": f"AI 에이전트 서버 연결 실패: {error}",
                    "label": "오류", "timestamp": _local_time_text(),
                })
            st.rerun()

    initially_active = bool(_ai_report_status().get("active_count"))
    for tab, kind in (
        (tab_log, "log"),
        (tab_quality, "quality"),
        (tab_breakdown, "breakdown"),
        (tab_detail, "detail"),
    ):
        with tab:
            _render_ai_data_tab_with_refresh(kind, initially_active)


def _render_profile_cards(profiles: list[dict], selected: str, disabled: bool, key_prefix: str) -> str:
    columns = st.columns(4)
    for column, profile in zip(columns, profiles):
        generation = profile["generation"]
        judge = profile["judge"]
        with column:
            st.markdown(
                f"<div class='profile-card'><div class='profile-title'>{profile['profile_id']} · {html.escape(profile['title'])}</div>"
                f"<div class='profile-summary'>{html.escape(profile['summary'])}</div><hr>"
                f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}<br>"
                f"독립 품질 평가(Judge): {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "✓ 선택됨" if selected == profile["profile_id"] else "선택",
                key=f"{key_prefix}_{profile['profile_id']}",
                disabled=disabled or not profile.get("available", True),
                width="stretch",
            ):
                selected = profile["profile_id"]
                st.session_state[f"{key_prefix}_selected"] = selected
                st.rerun()
            if not profile.get("available", True):
                st.caption("필수 키 설정 필요: " + ", ".join(profile.get("missing_keys", [])))
    return selected


def render_voc_chat() -> None:
    _section("VOC 챗봇", "질문마다 A~D 모델 프로필을 선택하고 7단계 처리 결과를 확인합니다.")
    profiles = _get_json(f"{VOC_API}/profiles") or public_profiles()
    pending = st.session_state.get("voc_pending")
    selected_key = "voc_chat_profile_selected"
    selected = st.session_state.setdefault(selected_key, "A")
    _render_profile_cards(list(profiles), selected, bool(pending), "voc_chat_profile")
    st.info("A~D는 답변 생성 모델과 독립 품질 평가 모델(Judge)의 조합입니다. 현재 질문 한 건에만 적용됩니다.")

    for message in st.session_state.setdefault("voc_chat_history", []):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            if message.get("meta"):
                st.caption(message["meta"])
            if message.get("status"):
                with st.expander("7단계 처리 결과", expanded=False):
                    _render_stage_explorer(message["status"], f"voc_history_{message['status']['request_id']}")

    if pending:
        status = _get_json(f"{VOC_API}/chat/{pending}/status")
        if isinstance(status, dict):
            st.markdown("### 현재 질문 처리 과정")
            _render_stage_explorer(status, f"voc_pending_{pending}")
            st.progress(100 if status["status"] in {"completed", "failed"} else min(95, int(status.get("elapsed_seconds", 0)) + 1))
            st.caption(f"{status['current_stage']} · {status.get('elapsed_seconds', 0):.1f}초 · 프로필 {status['profile_id']}")
            if status["status"] in {"completed", "failed"}:
                result = status.get("result") or {}
                judge = status.get("judge") or {}
                answer = (
                    result.get("answer") or result.get("policy") or result.get("summary")
                    if status["status"] == "completed"
                    else f"처리 실패: {status.get('error', '원인 없음')}"
                )
                meta = f"프로필 {status['profile_id']} · {status.get('elapsed_seconds', 0):.1f}초 · Judge {judge.get('total', 'N/A')} / {judge.get('verdict', 'N/A')}"
                st.session_state.voc_chat_history.append({"role": "assistant", "content": answer or "결과 없음", "meta": meta, "status": status})
                st.session_state.voc_pending = None
                st.rerun()
            time.sleep(1)
            st.rerun()
        else:
            st.error("VOC 요청 상태를 확인할 수 없습니다.")

    api_confirmed = _required_api_confirmation(
        "voc_chat_api_confirm",
        "메시지 전송 시 외부 AI API 호출과 비용이 발생할 수 있음을 확인했습니다.",
    )
    question = st.chat_input(
        "VOC 관련 단발 질문을 입력하세요",
        key="voc_chat_input",
        disabled=bool(pending) or not api_confirmed,
    )
    if question:
        st.session_state.voc_chat_history.append({"role": "user", "content": question})
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{VOC_API}/chat", json={"question": question, "profile_id": st.session_state[selected_key]})
                response.raise_for_status()
                st.session_state.voc_pending = response.json()["request_id"]
        except Exception as error:
            st.session_state.voc_chat_history.append({"role": "assistant", "content": f"VOC 서버 요청 실패: {error}"})
        st.rerun()


def render_monitoring() -> None:
    _section("모니터링", "상위 모니터링 탭 아래에서 Grafana 화면 4개를 바로 확인합니다.")
    grafana_ready = bool(_get_json(f"{GRAFANA}/api/health"))
    dashboards = [
        ("AI 상담 실시간 운영", "ai-agent-quality"),
        ("K6 성능 부하 시험", "k6-performance-test"),
        ("VOC 실시간 운영", "voc-live-operations"),
        ("VOC QA·A~D 비교", "voc-qa-abcd"),
    ]
    tabs = st.tabs([name for name, _uid in dashboards])
    for tab, (name, uid) in zip(tabs, dashboards):
        with tab:
            url = f"{GRAFANA}/d/{uid}?orgId=1&kiosk"
            st.link_button(f"{name} 새 창에서 열기", url)
            if grafana_ready:
                st.caption("아직 수집된 데이터가 없으면 Grafana 패널에 데이터 없음으로 표시됩니다.")
                components.iframe(url, height=_grafana_embed_height(uid), scrolling=False)
            else:
                st.warning("운영 상태 화면(Grafana)이 중지되어 있습니다. AllStar 서버 관리에서 Grafana를 먼저 시작하세요.")


def _grafana_embed_height(uid: str) -> int:
    """Grafana JSON의 마지막 패널까지 iframe 안쪽 스크롤 없이 보이도록 높이를 계산한다."""
    path = GRAFANA_DASHBOARD_PATHS.get(uid)
    if path is None:
        return 1200
    document = _read_json(path, {})
    panels = document.get("panels", []) if isinstance(document, dict) else []
    bottom = max(
        (
            int(panel.get("gridPos", {}).get("y", 0))
            + int(panel.get("gridPos", {}).get("h", 0))
            for panel in panels
            if isinstance(panel, dict)
        ),
        default=27,
    )
    return max(900, bottom * GRAFANA_GRID_ROW_HEIGHT + GRAFANA_FRAME_PADDING)


def _resolve_report_image(report_path: Path, target: str) -> Path | None:
    """Markdown 상대 이미지가 보고서 폴더 안의 실제 PNG인지 안전하게 확인한다."""
    cleaned = unquote(target.strip().strip("<>"))
    if urlparse(cleaned).scheme or not cleaned:
        return None
    root = report_path.parent.resolve()
    candidate = (root / cleaned).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
        return None
    return candidate


def _render_report_markdown_with_images(path: Path) -> set[Path]:
    """Markdown 본문을 나누어 상대 이미지를 선언된 위치에 실제 이미지로 표시한다."""
    markdown = path.read_text(encoding="utf-8")
    used_images: set[Path] = set()
    cursor = 0
    for match in MARKDOWN_IMAGE_PATTERN.finditer(markdown):
        before = markdown[cursor:match.start()]
        if before.strip():
            st.markdown(before, unsafe_allow_html=True)
        alt_text, target = match.groups()
        image_path = _resolve_report_image(path, target)
        if image_path and image_path.is_file():
            st.image(str(image_path), caption=alt_text or None, width="stretch")
            used_images.add(image_path)
        else:
            st.warning(f"보고서 이미지 '{alt_text or target}'를 표시할 수 없습니다.")
        cursor = match.end()
    remainder = markdown[cursor:]
    if remainder.strip():
        st.markdown(remainder, unsafe_allow_html=True)
    return used_images


def _render_markdown_report(title: str, path: Path, description: str) -> None:
    st.caption(description)
    if not path.exists():
        st.info("아직 생성된 보고서가 없습니다. 해당 챗봇 또는 시험을 실행하면 자동으로 갱신됩니다.")
        return
    used_images = _render_report_markdown_with_images(path)
    assets = path.parent / "assets"
    if assets.exists():
        images = [image for image in sorted(assets.glob("*.png")) if image.resolve() not in used_images]
        if images:
            st.markdown("### 추가 보고서 그래프")
            for image in images:
                st.image(str(image), width="stretch")


def _voc_report_signature() -> tuple[int, ...]:
    """프로필 보고서 완료 manifest와 종합 비교 보고서의 변경 시각을 반환한다."""
    paths = [
        *(VOC_REPORT_ROOT / "testcase" / profile / "report_manifest.json" for profile in "abcd"),
        VOC_REPORT_ROOT / "cross_validation" / "교차검증_종합비교보고서.md",
    ]
    return tuple(path.stat().st_mtime_ns if path.exists() else 0 for path in paths)


@st.fragment(run_every=1.0)
def watch_voc_report_updates() -> None:
    """보고서 생성 완료를 감지해 리포트 모음을 수동 새로고침 없이 갱신한다."""
    current = _voc_report_signature()
    state_key = "voc_report_signature"
    previous = st.session_state.get(state_key)
    if previous is None:
        st.session_state[state_key] = current
        return
    if current != previous:
        st.session_state[state_key] = current
        _read_csv.clear()
        _read_json.clear()
        st.rerun(scope="app")


def render_reports() -> None:
    _section("리포트 모음", "기존 포트폴리오 보고서 4개와 VOC 보고서 2개를 한곳에서 확인합니다.")
    tabs = st.tabs(
        [
            "AI 상담 챗봇 보고서",
            "장애·기능 검증 보고서",
            "서버 연결 성능 보고서",
            "AI 상담 테스트케이스 보고서",
            "VOC 챗봇 보고서",
            "VOC A~D 테스트케이스 보고서",
        ]
    )
    paths = [
        (AI_AGENT_REPORT_ROOT / "live" / "live_report.md", "실시간 AI 상담과 백그라운드 채점 결과입니다."),
        (REPORT_ROOT / "defects" / "chaos" / "defect_report.md", "장애 재현과 기능 회귀 결과입니다."),
        (REPORT_ROOT / "performance" / "performance_report.md", "1명·10명·25명 단계별 독립 성능 시험 결과입니다."),
        (AI_AGENT_REPORT_ROOT / "batch" / "final_quality_report.md", "등록된 AI 테스트케이스 전체의 비교 품질 결과입니다."),
        (VOC_REPORT_ROOT / "live" / "latest" / "voc_live_report.md", "VOC 단발 질문과 A~D 프로필·Judge 결과입니다."),
    ]
    for tab, (path, description) in zip(tabs[:5], paths):
        with tab:
            _render_markdown_report(tab.label if hasattr(tab, "label") else "보고서", path, description)
    with tabs[5]:
        profile_tabs = st.tabs(
            ["교차 테스트 (A)", "교차 테스트 (B)", "교차 테스트 (C)", "교차 테스트 (D)", "종합 비교"]
        )
        for tab, profile in zip(profile_tabs[:4], "abcd"):
            with tab:
                _render_markdown_report(
                    f"프로필 {profile.upper()}",
                    VOC_REPORT_ROOT / "testcase" / profile / "quality_score_report.md",
                    f"프로필 {profile.upper()}의 최근 전체 테스트케이스 정식 보고서입니다.",
                )
        with profile_tabs[4]:
            _render_markdown_report(
                "A~D 종합 비교",
                VOC_REPORT_ROOT / "cross_validation" / "교차검증_종합비교보고서.md",
                "최신 프로필 결과가 두 개 이상일 때 자동 갱신되는 비교 보고서입니다.",
            )


def _render_score_breakdown(df: pd.DataFrame | None, model_column: str = "model_type") -> None:
    if df is None or df.empty:
        st.info("표시할 품질 데이터가 없습니다.")
        return
    available_scores = [column for column in SCORE_COLUMNS if column in df]
    if not available_scores:
        st.info("품질 항목 점수가 아직 기록되지 않았습니다.")
        return
    scored = df[df.get("overall_decision", "") != "N/A"].copy()
    if scored.empty:
        st.info("채점 가능한 결과가 없습니다. N/A는 평균에서 제외됩니다.")
        return
    if model_column not in scored:
        scored[model_column] = "전체"
    averages = scored.groupby(model_column)[available_scores].mean().rename(columns=SCORE_LABELS).reset_index()
    radar = averages.melt(id_vars=model_column, var_name="품질 항목", value_name="점수")
    figure = px.line_polar(radar, r="점수", theta="품질 항목", color=model_column, line_close=True, range_r=[0, 5])
    st.plotly_chart(figure, width="stretch")


def _render_quality_detail(df: pd.DataFrame | None) -> None:
    if df is None or df.empty:
        st.info("표시할 상세 결과가 없습니다.")
        return
    view = df.drop(columns=["request_id"], errors="ignore").copy()
    if "overall_decision" in view:
        decisions = ["전체", *sorted(view["overall_decision"].dropna().unique().tolist())]
        selected = st.selectbox("판정 필터", decisions)
        if selected != "전체":
            view = view[view["overall_decision"] == selected]
    _render_dataframe(view, height=520)


def _render_ai_case_management() -> None:
    cases = _read_json(AI_CASES_PATH, [])
    running = bool(st.session_state.get("ai_batch_process"))
    _section("현재 테스트케이스")
    if running:
        st.warning("AI 에이전트 배치 테스트가 실행 중이므로 테스트케이스 추가·수정·삭제를 잠갔습니다.")
    _render_dataframe(pd.DataFrame(cases)) if cases else st.info("등록된 테스트케이스가 없습니다.")

    if cases:
        with st.expander("기존 AI 에이전트 테스트케이스 확인·수정", expanded=False):
            selected_id = st.selectbox(
                "확인·수정할 테스트케이스",
                [case["case_id"] for case in cases],
                format_func=lambda case_id: f"{case_id} · {next(case['category'] for case in cases if case['case_id'] == case_id)}",
                key="ai_edit_case_id",
            )
            selected_case = next(case for case in cases if case["case_id"] == selected_id)
            with st.form(f"ai_case_edit_{selected_id}"):
                columns = st.columns(3)
                case_id = columns[0].text_input("테스트케이스 ID", value=selected_id, disabled=True)
                category = columns[1].text_input("카테고리", value=str(selected_case.get("category", "")))
                test_types = ["Happy", "Edge", "Negative"]
                current_type = str(selected_case.get("test_type", "Happy"))
                test_type = columns[2].selectbox(
                    "시험 유형",
                    test_types,
                    index=test_types.index(current_type) if current_type in test_types else 0,
                )
                question = st.text_area("사용자 질문", value=str(selected_case.get("user_question", "")), height=100)
                keyword = st.text_input("기대 키워드", value=str(selected_case.get("expected_keyword", "")))
                policy = st.text_area("기대 정책", value=str(selected_case.get("expected_policy", "")), height=80)
                submitted_edit = st.form_submit_button(
                    "선택한 테스트케이스 수정 저장", type="primary", disabled=running
                )
            if submitted_edit:
                if not all(str(value).strip() for value in (category, question, keyword, policy)):
                    st.error("카테고리·사용자 질문·기대 키워드·기대 정책을 모두 입력하세요.")
                else:
                    updated_case = {
                        **selected_case,
                        "case_id": case_id,
                        "category": category.strip(),
                        "test_type": test_type,
                        "user_question": question.strip(),
                        "expected_keyword": keyword.strip(),
                        "expected_policy": policy.strip(),
                    }
                    archive_path = _archive_ai_case_document(cases)
                    updated_cases = [updated_case if case["case_id"] == selected_id else case for case in cases]
                    _write_json(AI_CASES_PATH, updated_cases)
                    st.success(f"{selected_id}를 수정했습니다. 수정 전 실행본도 보존했습니다: {archive_path.name}")
                    st.rerun()

    with st.expander("새 테스트케이스 추가", expanded=False):
        with st.form("ai_case_add", clear_on_submit=True):
            columns = st.columns(3)
            case_id = columns[0].text_input("테스트케이스 ID", value=_next_case_id(cases, 3))
            category = columns[1].text_input("카테고리")
            test_type = columns[2].selectbox("시험 유형", ["Happy", "Edge", "Negative"])
            question = st.text_input("사용자 질문")
            keyword = st.text_input("기대 키워드")
            policy = st.text_input("기대 정책")
            submitted = st.form_submit_button("테스트케이스 저장", type="primary", disabled=running)
        if submitted:
            values = [case_id, category, question, keyword, policy]
            if not all(value.strip() for value in values):
                st.error("모든 필수값을 입력하세요.")
            elif any(case["case_id"] == case_id.strip() for case in cases):
                st.error("이미 존재하는 테스트케이스 ID입니다.")
            else:
                cases.append({
                    "case_id": case_id.strip(), "category": category.strip(), "test_type": test_type,
                    "user_question": question.strip(), "expected_keyword": keyword.strip(), "expected_policy": policy.strip(),
                })
                _write_json(AI_CASES_PATH, cases)
                st.success("테스트케이스를 추가했습니다.")
                st.rerun()
    with st.expander("테스트케이스 삭제"):
        delete_ids = st.multiselect("삭제할 테스트케이스", [case["case_id"] for case in cases], key="ai_delete_ids")
        confirm = st.checkbox("선택한 테스트케이스 삭제를 확인합니다.", key="ai_delete_confirm")
        if st.button("선택 삭제", disabled=running or not (delete_ids and confirm), key="ai_delete_button"):
            _archive_ai_case_document(cases)
            _write_json(AI_CASES_PATH, [case for case in cases if case["case_id"] not in delete_ids])
            st.rerun()
    st.divider()
    st.markdown(f"<div class='scope-box'><b>전체 실행 범위</b><br>현재 등록된 {len(cases)}건 전체를 규칙 기반과 서버 연결 방식(API)으로 비교합니다.</div>", unsafe_allow_html=True)
    confirm_run = _required_api_confirmation(
        "ai_run_confirm",
        "전체 테스트케이스 실행 범위와 외부 API 비용 발생 가능성을 확인했습니다.",
    )
    if st.button("전체 테스트케이스 실행", type="primary", disabled=not cases or not confirm_run or bool(st.session_state.get("ai_batch_process"))):
        _launch_process("ai_batch_process", [sys.executable, "-u", "-m", "allstar.ai_agent.evaluation.quality_pipeline"], "dashboard_ai_batch")
        st.rerun()
    _render_process("ai_batch_process", "AI 에이전트 전체 테스트케이스")


def render_ai_testcases() -> None:
    _section("AI 에이전트 테스트케이스", "기존 포트폴리오의 관리·전체 실행·품질 분석 기능을 유지합니다.")
    tab_manage, tab_batch, tab_breakdown, tab_detail = st.tabs(["케이스 관리·실행", "배치 품질 현황", "유형별 비교", "케이스 상세"])
    with tab_manage:
        _render_ai_case_management()
    df = _read_csv(AI_BATCH_REPORT)
    with tab_batch:
        if df is None or df.empty:
            st.info("아직 배치 품질 보고서가 없습니다.")
        else:
            _render_decision_metrics(df)
            figure = px.bar(
                df, x="case_id", y="total_score", color="overall_decision", facet_row="model_type",
                color_discrete_map=DECISION_COLORS, hover_data=["category", "test_type", "summary"],
            )
            st.plotly_chart(figure, width="stretch")
    with tab_breakdown:
        _render_score_breakdown(df)
        if df is not None and not df.empty:
            scored = df[df["overall_decision"] != "N/A"]
            if not scored.empty:
                rates = scored.groupby(["model_type", "test_type"])["overall_decision"].apply(lambda values: round((values == "PASS").mean() * 100, 1)).reset_index(name="통과율")
                st.plotly_chart(px.bar(rates, x="test_type", y="통과율", color="model_type", barmode="group", range_y=[0, 100]), width="stretch")
    with tab_detail:
        _render_quality_detail(df)


def _csv_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _archive_ai_case_document(cases: list[dict[str, Any]]) -> Path:
    """AI Agent 현재 실행본을 수정·삭제 직전에 날짜별 이력으로 보존한다."""
    archive_dir = AI_CASES_PATH.parent / "archive" / "revisions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    archive_path = archive_dir / f"test_cases_before_change_{timestamp}.json"
    temporary = archive_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(archive_path)
    return archive_path


def _archive_voc_case_document(document: dict[str, Any]) -> Path:
    """현재 실행본을 수정·삭제 직전에 날짜별 이력으로 보존한다."""
    archive_dir = VOC_CASES_PATH.parent / "archive" / "revisions"
    archive_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    archive_path = archive_dir / f"test_cases_before_change_{timestamp}.json"
    temporary = archive_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(archive_path)
    return archive_path


def _render_voc_case_management() -> list[dict]:
    document = _read_json(VOC_CASES_PATH, {"description": "", "cases": []})
    cases = list(document.get("cases", []))
    running = bool(st.session_state.get("voc_profile_process"))
    _section("현재 VOC 테스트케이스")
    if running:
        st.warning("A~D 실 테스트가 실행 중이므로 테스트케이스 추가·수정·삭제를 잠갔습니다.")
    if cases:
        columns = ["case_id", "category", "judge_enabled", "judge_mode", "question"]
        _render_dataframe(pd.DataFrame(cases)[columns], height=430)
    else:
        st.info("등록된 VOC 테스트케이스가 없습니다.")

    if cases:
        with st.expander("기존 VOC 테스트케이스 확인·수정", expanded=False):
            selected_id = st.selectbox(
                "확인·수정할 테스트케이스",
                [case["case_id"] for case in cases],
                format_func=lambda case_id: f"{case_id} · {next(case['category'] for case in cases if case['case_id'] == case_id)}",
                key="voc_edit_case_id",
            )
            selected_case = next(case for case in cases if case["case_id"] == selected_id)
            source_id = selected_case.get("archive_source_case_id", "신규 추가 사례")
            st.caption(f"현재 ID는 결과 연결을 위해 유지합니다. 축소 전 출처 ID: {source_id}")
            with st.form(f"voc_case_edit_{selected_id}"):
                columns = st.columns(3)
                case_id = columns[0].text_input("테스트케이스 ID", value=selected_id, disabled=True)
                category = columns[1].text_input("카테고리", value=str(selected_case.get("category", "")))
                judge_enabled = columns[2].checkbox(
                    "독립 품질 평가 사용", value=bool(selected_case.get("judge_enabled", True))
                )
                judge_modes = ["live", "static", "pytest_fault"]
                current_mode = str(selected_case.get("judge_mode", "live"))
                judge_mode = st.selectbox(
                    "평가 방식",
                    judge_modes,
                    index=judge_modes.index(current_mode) if current_mode in judge_modes else 0,
                )
                question = st.text_area("질문", value=str(selected_case.get("question", "")), height=110)
                intent = st.text_input("기대 의도", value=str(selected_case.get("expected_intent", "")))
                keywords = st.text_input(
                    "기대 키워드 (쉼표로 구분)", value=", ".join(selected_case.get("expected_keywords", []))
                )
                required = st.text_input(
                    "필수 출력 (쉼표로 구분)", value=", ".join(selected_case.get("required_output", []))
                )
                prohibited = st.text_input(
                    "금지 출력 (쉼표로 구분)", value=", ".join(selected_case.get("prohibited_output", []))
                )
                option_columns = st.columns(2)
                expect_no_data = option_columns[0].checkbox(
                    "관련 데이터 없음이 정답인 사례", value=bool(selected_case.get("expect_no_data", False))
                )
                fault = option_columns[1].text_input("장애 유형 (선택)", value=str(selected_case.get("fault", "")))
                analysis = st.text_area(
                    "정적 평가 입력(Analysis, 선택)", value=str(selected_case.get("analysis", "")), height=90
                )
                note = st.text_area("참고 사항 (선택)", value=str(selected_case.get("note", "")), height=80)
                submitted_edit = st.form_submit_button(
                    "선택한 테스트케이스 수정 저장", type="primary", disabled=running
                )
            if submitted_edit:
                required_values = (category, question, intent, required, prohibited)
                if not all(str(value).strip() for value in required_values):
                    st.error("카테고리·질문·기대 의도·필수 출력·금지 출력은 반드시 입력하세요.")
                elif judge_mode == "pytest_fault" and not fault.strip():
                    st.error("장애 평가 방식은 장애 유형을 입력해야 합니다.")
                else:
                    updated_case = {
                        **selected_case,
                        "case_id": case_id,
                        "category": category.strip(),
                        "judge_enabled": judge_enabled,
                        "judge_mode": judge_mode,
                        "question": question.strip(),
                        "expected_intent": intent.strip(),
                        "expected_keywords": _csv_list(keywords),
                        "required_output": _csv_list(required),
                        "prohibited_output": _csv_list(prohibited),
                    }
                    optional_values = {
                        "expect_no_data": True if expect_no_data else None,
                        "fault": fault.strip() or None,
                        "analysis": analysis.strip() or None,
                        "note": note.strip() or None,
                    }
                    for field, value in optional_values.items():
                        if value is None:
                            updated_case.pop(field, None)
                        else:
                            updated_case[field] = value
                    archive_path = _archive_voc_case_document(document)
                    updated_cases = [updated_case if case["case_id"] == selected_id else case for case in cases]
                    _write_json(VOC_CASES_PATH, {**document, "cases": updated_cases})
                    st.success(f"{selected_id}를 수정했습니다. 수정 전 실행본도 보존했습니다: {archive_path.name}")
                    st.rerun()

    with st.expander("새 VOC 테스트케이스 추가"):
        with st.form("voc_case_add", clear_on_submit=True):
            columns = st.columns(3)
            case_id = columns[0].text_input("테스트케이스 ID", value=_next_case_id(cases, 2))
            category = columns[1].text_input("카테고리")
            judge_enabled = columns[2].checkbox("독립 품질 평가 사용", value=True)
            question = st.text_area("질문")
            intent = st.text_input("기대 의도")
            keywords = st.text_input("기대 키워드 (쉼표로 구분)")
            required = st.text_input("필수 출력 (쉼표로 구분)")
            prohibited = st.text_input("금지 출력 (쉼표로 구분)")
            expect_no_data = st.checkbox("관련 데이터 없음이 정답인 사례")
            note = st.text_input("참고 사항 (선택)")
            submitted = st.form_submit_button("VOC 테스트케이스 저장", type="primary", disabled=running)
        if submitted:
            if not all(value.strip() for value in (case_id, category, question, intent, keywords, required, prohibited)):
                st.error("필수값을 모두 입력하세요.")
            elif any(case["case_id"] == case_id.strip() for case in cases):
                st.error("이미 존재하는 테스트케이스 ID입니다.")
            else:
                case = {
                    "case_id": case_id.strip(), "category": category.strip(), "judge_enabled": judge_enabled,
                    "judge_mode": "live", "question": question.strip(), "expected_intent": intent.strip(),
                    "expected_keywords": _csv_list(keywords), "required_output": _csv_list(required),
                    "prohibited_output": _csv_list(prohibited),
                }
                if expect_no_data:
                    case["expect_no_data"] = True
                if note.strip():
                    case["note"] = note.strip()
                cases.append(case)
                _write_json(VOC_CASES_PATH, {**document, "cases": cases})
                st.rerun()
    with st.expander("VOC 테스트케이스 삭제"):
        delete_ids = st.multiselect("삭제할 테스트케이스", [case["case_id"] for case in cases], key="voc_delete_ids")
        confirm = st.checkbox("선택한 VOC 테스트케이스 삭제를 확인합니다.", key="voc_delete_confirm")
        if st.button("선택 삭제", disabled=running or not (delete_ids and confirm), key="voc_delete_button"):
            _archive_voc_case_document(document)
            _write_json(VOC_CASES_PATH, {**document, "cases": [case for case in cases if case["case_id"] not in delete_ids]})
            st.rerun()
    return cases


def _latest_voc_judge_log(profile: str, run_id: str | None = None) -> dict | None:
    root = VOC_LOG_ROOT / "testcase" / profile.lower()
    if run_id:
        root = root / run_id
    paths = sorted(root.glob("*/llm_judge_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if run_id:
        paths = sorted(root.glob("llm_judge_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    return _read_json(paths[0], None) if paths else None


def _analysis_sections(analysis: str) -> dict[str, str]:
    headings = re.findall(r"\[([^\]]+)\]\n", analysis)
    values = re.split(r"\[[^\]]+\]\n", analysis)[1:]
    return dict(zip(headings, values))


def _batch_status_from_row(row: dict, profile: str) -> dict:
    analysis = str(row.get("analysis") or "")
    sections = _analysis_sections(analysis)
    result = {
        "intent_json": sections.get("Interpreter 의도", ""),
        "trace": sections.get("Retriever 및 Agent 연계 추적", ""),
        "summary": sections.get("Summarizer 요약", ""),
        "eval_json": sections.get("Evaluator 평가", ""),
        "summary_critic_json": sections.get("Critic 검토", ""),
        "policy": sections.get("Improver 정책 개선안", ""),
    }
    judge = {"total": row.get("total", "N/A"), "verdict": row.get("verdict", "N/A"), "rationale": row.get("rationale", "")}
    pipeline_done = bool(analysis and sections)
    judge_done = isinstance(row.get("total"), (int, float))
    if pipeline_done:
        stage_states = ["done"] * 6 + (["done"] if judge_done else ["failed"])
    else:
        stage_states = ["failed"] + ["skipped"] * 5 + (["done"] if judge_done else ["skipped"])
    return {
        "request_id": f"{profile}_{row.get('case_id', 'case')}", "status": "completed", "current_stage": "완료",
        "profile_id": profile, "result": result, "judge": judge, "error": None, "_stage_states": stage_states,
    }


def _progress_case_status(case: dict) -> dict:
    stages = list(case.get("stages", []))
    return {
        "status": case.get("status", "running"),
        "current_stage": next(
            (stage.get("name", "") for stage in stages if stage.get("state") == "running"),
            "완료" if case.get("status") in {"completed", "skipped", "failed"} else "대기",
        ),
        "_stage_states": [stage.get("state", "pending") for stage in stages],
        "_stage_details": [stage.get("detail") or "아직 결과가 없습니다." for stage in stages],
    }


def _voc_run_metrics(log: dict | None) -> tuple[float | None, float | None, int]:
    if not log:
        return None, None, 0
    rows = list(log.get("case_results", []))
    times = []
    for row in rows:
        try:
            times.append(float(row.get("total_seconds")))
        except (TypeError, ValueError):
            continue
    average = sum(times) / len(times) if times else None
    run_seconds = None
    try:
        started = pd.to_datetime(log.get("started_at"), errors="raise", utc=True)
        finished = pd.to_datetime(log.get("finished_at"), errors="raise", utc=True)
        run_seconds = (finished - started).total_seconds()
    except (TypeError, ValueError):
        pass
    return run_seconds, average, len(times)


@st.fragment(run_every=1.0)
def _render_voc_real_test(cases: list[dict]) -> None:
    total = len(cases)
    ai_targets = sum(bool(case.get("judge_enabled", False)) for case in cases)
    st.markdown(
        f"<div class='scope-box'><b>GUI 전체 실행 범위</b><br>등록된 전체 {total}건 · 실제 AI 평가 대상 {ai_targets}건 · "
        f"장애 재현 전용 {total - ai_targets}건<br>기본 외부 AI 호출 예상 최대 {ai_targets * 7}회이며 API 재시도 시 증가할 수 있습니다.</div>",
        unsafe_allow_html=True,
    )
    st.caption("A·B·C·D 중 하나를 누르면 해당 프로필로 등록된 전체 테스트케이스를 실행합니다. 한 번에 하나만 실행할 수 있습니다.")
    confirmed = _required_api_confirmation(
        "voc_all_confirm",
        "전체 테스트케이스 실행 범위와 외부 API 비용 발생 가능성을 확인했습니다.",
    )
    process_state = st.session_state.get("voc_profile_process")
    process = process_state.get("process") if process_state else None
    return_code = process.poll() if process else None
    running = bool(process_state and return_code is None)
    completed_pending = bool(process_state and return_code is not None)
    active_profile = st.session_state.get("voc_running_profile")
    profiles = public_profiles()
    columns = st.columns(4)
    for column, profile in zip(columns, profiles):
        generation, judge = profile["generation"], profile["judge"]
        with column:
            card_state = ""
            status_badge = ""
            if active_profile == profile["profile_id"] and running:
                card_state = " profile-running"
                status_badge = "<div class='profile-status'>실행 중</div>"
            elif active_profile == profile["profile_id"] and completed_pending:
                card_state = " profile-completed"
                status_badge = "<div class='profile-status'>완료 확인 대기</div>"
            st.markdown(
                f"<div class='profile-card{card_state}'>{status_badge}<div class='profile-title'>{profile['profile_id']} · {html.escape(profile['title'])}</div>"
                f"<div class='profile-summary'>{html.escape(profile['summary'])}</div><hr>"
                f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}<br>"
                f"독립 평가: {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}</div></div>",
                unsafe_allow_html=True,
            )
            disabled = running or (not completed_pending and (not confirmed or not cases))
            clicked = st.button(
                f"{profile['profile_id']} 전체 테스트 실행",
                key=f"run_profile_{profile['profile_id']}",
                type="primary",
                disabled=disabled,
                width="stretch",
            )
            if clicked and completed_pending:
                st.session_state.voc_profile_notice = (
                    f"프로필 {active_profile} 완료 상태를 먼저 닫은 뒤 프로필 {profile['profile_id']} 테스트를 실행해 주세요."
                )
            elif clicked:
                run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                _launch_process(
                    "voc_profile_process",
                    [
                        sys.executable, "-u",
                        str(PROJECT_ROOT / "tools" / "scripts" / "run_voc_profile.py"),
                        "--profile", profile["profile_id"], "--run-id", run_id,
                    ],
                    f"dashboard_voc_{profile['profile_id'].lower()}",
                    run_id=run_id,
                )
                st.session_state.voc_running_profile = profile["profile_id"]
                st.session_state.pop("voc_profile_notice", None)

    if st.session_state.get("voc_profile_notice"):
        st.warning(st.session_state.voc_profile_notice)

    process_state = st.session_state.get("voc_profile_process")
    if not process_state:
        return
    process = process_state["process"]
    return_code = process.poll()
    running = return_code is None
    profile = st.session_state.get("voc_running_profile", "A")
    run_id = process_state["run_id"]
    output = _read_process_output(Path(process_state["log_path"]))
    progress = read_progress(run_id)
    log = _latest_voc_judge_log(profile, run_id)

    if running:
        elapsed = time.time() - process_state["started_at"]
        st.info(f"VOC 프로필 {profile} 전체 테스트케이스 실행 중 · {elapsed:.1f}초 경과")
        if st.button("실행 중지", key="stop_voc_profile_process"):
            process.terminate()
            st.session_state.voc_profile_notice = "실행 중지 요청을 보냈습니다. 현재 처리 상태를 확인해 주세요."
    else:
        run_seconds, average, measured = _voc_run_metrics(log)
        total_text = f"총 {run_seconds:.1f}초" if run_seconds is not None else "총 소요시간 미확인"
        average_text = f"테스트케이스 평균 {average:.1f}초 ({measured}건 기준)" if average is not None else "평균시간 미확인"
        message = f"VOC 프로필 {profile} 전체 테스트케이스 완료 · {total_text} · {average_text}"
        if return_code == 0:
            st.success(message)
        else:
            st.error(f"{message} · 종료 코드 {return_code}")
        if st.button(
            f"프로필 {profile} 완료 상태 닫기 · 다음 테스트 준비",
            key="clear_voc_profile_process",
            type="primary",
            width="stretch",
        ):
            st.session_state.pop("voc_profile_process", None)
            st.session_state.pop("voc_running_profile", None)
            st.session_state.pop("voc_profile_notice", None)
            _read_csv.clear()
            st.rerun(scope="fragment")

    if progress:
        progress_cases = list(progress.get("cases", []))
        terminal = sum(case.get("status") in {"completed", "failed", "skipped"} for case in progress_cases)
        st.progress(terminal / max(len(progress_cases), 1))
        st.caption(f"테스트케이스 처리 {terminal} / {len(progress_cases)} · 실행 프로필 {profile}")
        if running:
            current_id = progress.get("current_case_id")
            current = next((case for case in progress_cases if case.get("case_id") == current_id), None)
            if current:
                st.markdown(
                    f"### 현재 진행: {current['case_id']} · {html.escape(current.get('category') or '분류 없음')} "
                    f"({current.get('index', 0)}/{progress.get('total_cases', total)})"
                )
                st.caption(current.get("question") or "질문 내용 없음")
                _render_stage_explorer(
                    _progress_case_status(current),
                    f"voc_progress_{run_id}_{current['case_id']}",
                    interactive=False,
                )
            elif progress.get("status") == "running":
                st.info("첫 번째 테스트케이스 실행을 준비하고 있습니다.")
        elif progress.get("status") == "running":
            st.info("테스트케이스 처리는 끝났으며 정식 보고서를 정리하고 있습니다.")

    if not running and log:
        rows = list(log.get("case_results", []))
        counts = log.get("case_counts", {})
        st.caption(
            f"채점 대상 처리 {counts.get('processed', 0)} / {counts.get('judge_target', 0)} · "
            f"정상 채점 {counts.get('scored', 0)} · N/A {counts.get('na', 0)}"
        )
        if rows:
            selected_id = st.selectbox(
                "단계별 결과를 볼 테스트케이스",
                [row.get("case_id") for row in rows],
                key=f"voc_result_case_{run_id}",
            )
            row = next(row for row in rows if row.get("case_id") == selected_id)
            _render_stage_explorer(
                _batch_status_from_row(row, profile),
                f"voc_batch_{run_id}_{profile}_{selected_id}",
                interactive=True,
            )

    with st.expander("실행 내용 보기", expanded=False):
        st.code(output[-12000:] or ("준비 중..." if running else "출력 없음"), language="text")


def render_voc_testcases() -> None:
    _section("VOC 테스트케이스", "테스트케이스를 관리하고 A~D 프로필별 전체 실 테스트를 실행합니다.")
    tab_manage, tab_test = st.tabs(["테스트케이스 관리", "실 테스트"])
    with tab_manage:
        cases = _render_voc_case_management()
    with tab_test:
        document = _read_json(VOC_CASES_PATH, {"cases": []})
        _render_voc_real_test(list(document.get("cases", [])))

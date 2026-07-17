from __future__ import annotations

import html
import json
import os
import random
import re
import subprocess
import sys
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
from allstar.voc.evaluation.runtime_support import load_json as load_voc_json
from allstar.voc.api.validation import is_valid_question_text
from allstar.ui.dashboard.ai_chat_fault_control import (
    chat_server_health,
    reconnect_chat_server,
    reconnect_voc_chat_server,
    stop_chat_server_and_record,
)
from allstar.ui.dashboard.k6_load_runner import (
    K6_INSTALL_URL,
    K6_MAX_DURATION,
    K6_MAX_VUS,
    K6_MIN_DURATION,
    K6_MIN_VUS,
    K6_TEST_SPECS,
    clear_finished_run,
    inspect_environment,
    poll_current_run,
    start_run,
    stop_current_run,
)


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
VOC_LIVE_CONVERSATION_DIR = VOC_LOG_ROOT / "live" / "conversations"
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
    "understandability_score": "이해 가능성",
}
SCORE_DESCRIPTIONS = {
    "정확성": "질문에 사실상 정확하게 답했는지",
    "근거성": "제공된 자료와 근거에 기반한 답변인지",
    "유용성": "사용자의 문제 해결에 도움이 되는지",
    "안전성": "위험하거나 부적절한 내용이 없는지",
    "이해 가능성": "표현이 명확하고 읽기 쉬운지",
}
MODEL_LABELS = {
    "api": "서버 연결 방식(API)",
    "api_based": "서버 연결 방식(API)",
    "rule": "규칙 기반",
    "rule_based": "규칙 기반",
}
AI_CHAT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="allstar-ai-chat")
STAGES = [
    ("Interpreter", "질문 의도 분석"),
    ("Retriever", "관련 의견 검색"),
    ("Summarizer", "내용 요약"),
    ("Evaluator", "초기 품질 평가"),
    ("Critic", "결과 검토"),
    ("Improver", "최종 답변 개선"),
    ("LLM Judge", "독립 품질 평가"),
]
VOC_RUBRIC_VERSION = "voc_9x100_v1"
VOC_RUBRIC = load_voc_json("judge_rubric.json")
VOC_SCORE_CRITERIA = [
    (criterion["name"], int(criterion["max_score"]))
    for criterion in VOC_RUBRIC["criteria"]
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


@st.cache_data(ttl=2, show_spinner=False)
def _ai_chat_server_health() -> tuple[bool, str]:
    return chat_server_health(PORTFOLIO_API, timeout=0.8)


@st.cache_data(ttl=2, show_spinner=False)
def _voc_chat_server_health() -> tuple[bool, str]:
    return chat_server_health(VOC_API, timeout=0.8)


def _sync_chat_server_state(
    health_reader: Any,
    *,
    state_prefix: str,
    down_message: str,
) -> bool:
    """실제 Health와 화면 잠금 상태를 맞추고 변경 여부를 반환한다."""
    healthy, _detail = health_reader()
    down_key = f"{state_prefix}_server_down"
    message_key = f"{state_prefix}_server_down_message"
    recovered_key = f"{state_prefix}_server_recovered"
    was_down = bool(st.session_state.get(down_key))
    if healthy:
        if not was_down:
            return False
        st.session_state[down_key] = False
        st.session_state.pop(message_key, None)
        st.session_state[recovered_key] = _local_time_text()
        return True
    if was_down:
        return False
    st.session_state[down_key] = True
    st.session_state[message_key] = down_message
    st.session_state.pop(recovered_key, None)
    return True


@st.fragment(run_every="3s")
def _watch_ai_chat_server() -> None:
    pending = st.session_state.get("ai_chat_pending")
    if pending and pending.get("fault_type") == "server_down":
        return
    if _sync_chat_server_state(
        _ai_chat_server_health,
        state_prefix="ai_chat",
        down_message="채팅 서버가 중단되어 답변을 받을 수 없습니다. 서버를 다시 시작해 주세요.",
    ):
        st.rerun(scope="app")


@st.fragment(run_every="3s")
def _watch_voc_chat_server() -> None:
    if _sync_chat_server_state(
        _voc_chat_server_health,
        state_prefix="voc_chat",
        down_message="VOC 채팅 서버가 중단되어 답변을 받을 수 없습니다. 서버를 다시 시작해 주세요.",
    ):
        st.rerun(scope="app")


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


def _render_decision_metrics(
    df: pd.DataFrame,
    decision_column: str = "overall_decision",
    item_column: str | None = None,
    item_label: str = "대상",
) -> None:
    values = df.get(decision_column, pd.Series(dtype=str)).fillna("N/A")
    metrics: list[tuple[str, int]] = []
    if item_column and item_column in df:
        metrics.append((item_label, int(df[item_column].nunique())))
        metrics.append(("평가 결과", len(values)))
    else:
        metrics.append(("전체", len(values)))
    metrics.extend((label, int((values == label).sum())) for label in ["PASS", "REVIEW", "FAIL", "N/A"])
    cols = st.columns(len(metrics))
    for col, (label, count) in zip(cols, metrics):
        col.metric(label, count)


def _model_label(value: Any) -> str:
    return MODEL_LABELS.get(str(value), str(value))


def _change_quality_page(state_key: str, delta: int) -> None:
    st.session_state[state_key] = max(0, int(st.session_state.get(state_key, 0)) + delta)


def _render_grouped_quality_chart(
    df: pd.DataFrame,
    *,
    group_column: str,
    label_column: str,
    item_label: str,
    model_column: str,
    key: str,
    newest_first: bool = False,
) -> None:
    """질문·케이스 단위를 보존하면서 두 답변 결과를 좌우 막대와 페이지로 보여준다."""
    if group_column not in df or label_column not in df or model_column not in df:
        st.info("비교 그래프에 필요한 데이터가 아직 기록되지 않았습니다.")
        return

    source = df.copy()
    source = source[source[group_column].notna()].copy()
    if source.empty:
        st.info("표시할 비교 결과가 없습니다.")
        return
    source["_model_label"] = source[model_column].map(_model_label)
    source["_group_id"] = source[group_column].astype(str)

    groups = source.drop_duplicates("_group_id", keep="last")
    if newest_first and "timestamp" in groups:
        groups = groups.assign(_sort_time=pd.to_datetime(groups["timestamp"], errors="coerce", utc=True))
        groups = groups.sort_values("_sort_time", ascending=False)
    group_ids = groups["_group_id"].tolist()

    size_key = f"{key}_page_size"
    page_key = f"{key}_page"
    selected_size = st.selectbox(
        f"한 화면에 표시할 {item_label} 수",
        [5, 10, 20, "전체"],
        index=1,
        key=size_key,
    )
    page_size = len(group_ids) if selected_size == "전체" else int(selected_size)
    page_size = max(page_size, 1)
    total_pages = max(1, (len(group_ids) + page_size - 1) // page_size)
    st.session_state.setdefault(page_key, 0)
    page = min(max(int(st.session_state[page_key]), 0), total_pages - 1)
    st.session_state[page_key] = page

    controls = st.columns([1, 2, 1])
    controls[0].button(
        "← 이전",
        key=f"{key}_previous",
        disabled=page == 0,
        width="stretch",
        on_click=_change_quality_page,
        args=(page_key, -1),
    )
    controls[1].markdown(
        f"<div style='text-align:center;padding:.45rem 0;font-weight:700'>{page + 1} / {total_pages} 페이지 · 총 {len(group_ids)}{item_label}</div>",
        unsafe_allow_html=True,
    )
    controls[2].button(
        "다음 →",
        key=f"{key}_next",
        disabled=page >= total_pages - 1,
        width="stretch",
        on_click=_change_quality_page,
        args=(page_key, 1),
    )

    visible_ids = group_ids[page * page_size:(page + 1) * page_size]
    visible = source[source["_group_id"].isin(visible_ids)].copy()
    visible["_group_order"] = visible["_group_id"].map({value: index for index, value in enumerate(visible_ids)})
    model_order = ["서버 연결 방식(API)", "규칙 기반"]
    visible["_model_order"] = visible["_model_label"].map({value: index for index, value in enumerate(model_order)}).fillna(len(model_order))
    visible = visible.sort_values(["_group_order", "_model_order"])

    if newest_first and "timestamp" in visible:
        visible["_item_label"] = visible.apply(
            lambda row: f"{str(row[label_column])[:34]}<br>{_local_time_text(row.get('timestamp'))}", axis=1
        )
    else:
        visible["_item_label"] = visible[label_column].astype(str)
    item_order = visible.drop_duplicates("_group_id")["_item_label"].tolist()
    visible["_bar_text"] = visible.apply(
        lambda row: f"{_model_label(row.get(model_column))}<br>{row.get('overall_decision', 'N/A')} · {row.get('total_score', 'N/A')}",
        axis=1,
    )
    hover_columns = [
        column for column in (
            label_column, model_column, "overall_decision", "total_score", "ai_answer", "summary", "category", "test_type"
        ) if column in visible
    ]
    figure = px.bar(
        visible,
        x="_item_label",
        y="total_score",
        color="overall_decision",
        pattern_shape="_model_label",
        barmode="group",
        text="_bar_text",
        color_discrete_map=DECISION_COLORS,
        category_orders={"_item_label": item_order, "_model_label": model_order},
        hover_data=hover_columns,
    )
    figure.update_traces(textposition="outside", cliponaxis=False)
    figure.update_layout(
        xaxis_title=item_label,
        yaxis_title="종합점수",
        yaxis_range=[0, 28],
        legend_title_text="판정 · 답변 종류",
        bargap=0.22,
        margin=dict(t=40, b=40),
    )
    st.plotly_chart(figure, width="stretch", key=f"{key}_chart")


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
    if status.get("stage_states") or status.get("_stage_states"):
        return list(status.get("stage_states") or status["_stage_states"])
    job_status = status.get("status")
    current = status.get("current_stage", "")
    if job_status == "queued":
        return ["pending"] * 7
    if job_status == "no_data":
        return ["done", "no_data"] + ["skipped"] * 5
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
    if status.get("stage_details") or status.get("_stage_details"):
        details = list(status.get("stage_details") or status["_stage_details"])
        result = status.get("result") or {}
        fallback = [
            _safe_json(result.get("intent_json") or "아직 결과가 없습니다."),
            str(result.get("trace") or "아직 결과가 없습니다."),
            result.get("summary") or "아직 결과가 없습니다.",
            _safe_json(result.get("eval_json") or "아직 결과가 없습니다."),
            _safe_json(result.get("summary_critic_json") or "아직 결과가 없습니다."),
            result.get("policy") or result.get("answer") or "아직 결과가 없습니다.",
            status.get("judge") or status.get("error") or "아직 결과가 없습니다.",
        ]
        return [detail or fallback[index] for index, detail in enumerate(details)]
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


def _render_stage_flow(states: list[str], safe_key: str) -> None:
    state_labels = {"pending": "대기", "running": "처리 중", "done": "완료", "failed": "실패", "skipped": "건너뜀", "no_data": "데이터 없음"}
    with st.container(horizontal=True, gap="small", key=f"stage_top_{safe_key}"):
        for index, ((english, korean), state) in enumerate(zip(STAGES, states)):
            with st.container(width=180, key=f"stage_top_cell_{safe_key}_{index}"):
                st.markdown(
                    f"<div class='stage-node stage-{state}'><span>{index + 1}</span>"
                    f"<b>{html.escape(korean)}</b><small>{html.escape(english)}</small>"
                    f"<em>{state_labels[state]}</em></div>",
                    unsafe_allow_html=True,
                )
            if index < len(STAGES) - 1:
                with st.container(width=26, key=f"stage_top_arrow_{safe_key}_{index}"):
                    st.markdown("<div class='stage-arrow' aria-hidden='true'>→</div>", unsafe_allow_html=True)


def _render_stage_explorer(status: dict, key_prefix: str, interactive: bool = True) -> None:
    states = _status_stage_states(status)
    details = _status_stage_details(status)
    symbols = {"pending": "○", "running": "◔", "done": "✓", "failed": "!", "skipped": "－", "no_data": "∅"}
    state_labels = {"pending": "대기", "running": "처리 중", "done": "완료", "failed": "실패", "skipped": "건너뜀", "no_data": "데이터 없음"}
    selected_key = f"{key_prefix}_selected_stage"
    st.session_state.setdefault(selected_key, 0)
    safe_key = re.sub(r"[^a-zA-Z0-9_-]", "_", key_prefix)
    scroll_mode = "interactive" if interactive else "progress"
    with st.container(key=f"stage_scroll_{scroll_mode}_{safe_key}"):
        _render_stage_flow(states, safe_key)
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
            _render_decision_metrics(live_df, item_column="request_id", item_label="대화")
            st.caption("대화 한 건마다 서버 연결 방식(API)과 규칙 기반 평가가 각각 한 건씩 기록됩니다.")
            _render_grouped_quality_chart(
                live_df,
                group_column="request_id",
                label_column="question",
                item_label="질문",
                model_column="model",
                key="ai_live_quality",
                newest_first=True,
            )
    elif kind == "breakdown":
        _render_ai_report_status(status, "breakdown")
        _render_score_breakdown(live_df, model_column="model", key="ai_live_breakdown")
    elif kind == "detail":
        _render_ai_report_status(status, "detail")
        _render_quality_detail(live_df, key="ai_live_detail", newest_first=True)


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


def _request_ai_chat(question: str) -> dict[str, Any]:
    """화면을 막지 않고 AI 에이전트 답변을 기다리기 위한 백그라운드 요청이다."""
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(f"{PORTFOLIO_API}/chat", json={"question": question})
            response.raise_for_status()
            return {"ok": True, "body": response.json()}
    except Exception as error:
        return {"ok": False, "error": str(error)}


def _request_ai_fault(question: str, case_id: str, scenario: str) -> dict[str, Any]:
    """명시적 버튼으로만 503·504 장애 시험 API를 호출한다."""
    try:
        with httpx.Client(timeout=httpx.Timeout(20.0, connect=3.0)) as client:
            response = client.post(
                f"{PORTFOLIO_API}/fault-lab/chat",
                json={"question": question, "case_id": case_id, "scenario": scenario},
            )
        try:
            body = response.json()
        except ValueError:
            body = {}
        detail = body.get("detail") if isinstance(body, dict) else {}
        detail = detail if isinstance(detail, dict) else {"message": str(detail or response.text)}
        return {
            "ok": False,
            "fault": True,
            "fault_type": scenario,
            "status_code": response.status_code,
            "error": detail.get("message") or f"HTTP {response.status_code}",
            "request_id": detail.get("request_id"),
            "report_updated": detail.get("report_updated", False),
        }
    except Exception as error:
        return {"ok": False, "error": f"장애 시험 API 연결 실패: {error}"}


def _random_ai_testcase() -> dict[str, Any] | None:
    cases = _read_json(AI_CASES_PATH, [])
    valid = [case for case in cases if str(case.get("user_question") or "").strip()]
    return random.SystemRandom().choice(valid) if valid else None


def _start_ai_fault_request(history: list[dict[str, Any]], scenario: str) -> bool:
    case = _random_ai_testcase()
    if not case:
        st.error("장애 시험에 사용할 AI 테스트케이스가 없습니다.")
        return False
    question = str(case["user_question"]).strip()
    case_id = str(case.get("case_id") or "미지정")
    st.session_state.pop("ai_chat_server_recovered", None)
    history.append({
        "role": "user",
        "content": question,
        "label": f"장애 시험 자동 입력 · {case_id}",
        "timestamp": _local_time_text(),
    })
    if scenario == "server_down":
        future = AI_CHAT_EXECUTOR.submit(
            stop_chat_server_and_record,
            question=question,
            case_id=case_id,
            api_url=PORTFOLIO_API,
        )
    else:
        future = AI_CHAT_EXECUTOR.submit(_request_ai_fault, question, case_id, scenario)
    st.session_state.ai_chat_pending = {
        "question": question,
        "case_id": case_id,
        "fault_type": scenario,
        "started_at": time.monotonic(),
        "future": future,
    }
    return True


def _complete_ai_chat_request(history: list[dict[str, Any]], pending: dict[str, Any]) -> bool:
    """완료된 백그라운드 요청을 대화 기록으로 옮기고 처리 여부를 반환한다."""
    future = pending.get("future")
    if not isinstance(future, Future) or not future.done():
        return False
    try:
        result = future.result()
    except Exception as error:
        result = {"ok": False, "error": str(error)}
    response_time = _local_time_text()
    if result.get("ok"):
        body = result.get("body") or {}
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
    elif result.get("fault"):
        if result.get("server_down"):
            st.session_state.ai_chat_server_down = True
            st.session_state.ai_chat_server_down_message = result.get(
                "error", "채팅 서버가 중단되어 답변을 받을 수 없습니다."
            )
        else:
            status_code = result.get("status_code")
            code_text = f"HTTP {status_code}" if status_code else "서버 연결 실패"
            history.append({
                "role": "assistant",
                "content": f"{result.get('error', '장애가 발생했습니다')}\n\n품질 판정: N/A (AI 성능 실패가 아닌 인프라·통신 장애)",
                "label": f"장애 시험 · {code_text}",
                "timestamp": response_time,
            })
        _clear_ai_live_caches()
        _ai_chat_server_health.clear()
    else:
        history.append({
            "role": "assistant", "content": f"AI 에이전트 서버 연결 실패: {result.get('error', '원인 없음')}",
            "label": "오류", "timestamp": response_time,
        })
    st.session_state.pop("ai_chat_pending", None)
    return True


def render_ai_chat() -> None:
    _section("AI 에이전트 챗봇", "기존 포트폴리오의 실시간 대화·로그·품질 분석 기능을 통합한 화면입니다.")
    tab_chat, tab_log, tab_quality, tab_breakdown, tab_detail = st.tabs(
        ["챗봇과 대화", "대화 로그", "품질 현황", "유형별 비교", "대화별 채점 상세"]
    )
    with tab_chat:
        history = st.session_state.setdefault("ai_chat_history", [])
        pending = st.session_state.get("ai_chat_pending")
        _watch_ai_chat_server()
        server_down = bool(st.session_state.get("ai_chat_server_down"))
        api_confirmed = _required_api_confirmation(
            "ai_chat_api_confirm",
            "메시지 전송 시 외부 AI API 호출과 비용이 발생할 수 있음을 확인했습니다.",
        )
        if pending and _complete_ai_chat_request(history, pending):
            st.rerun()
        pending = st.session_state.get("ai_chat_pending")
        server_down = bool(st.session_state.get("ai_chat_server_down"))
        with st.container(key="ai_chat_panel"):
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
                if pending and pending.get("fault_type") == "server_down":
                    with st.container(key="ai_chat_server_stopping_notice", border=True):
                        st.markdown(
                            "<div class='ai-server-status-title'>채팅 서버 중단 진행 중</div>"
                            "<div class='ai-server-status-message'>서버를 중단하고 실제 연결 실패를 확인하고 있습니다.</div>",
                            unsafe_allow_html=True,
                        )
                elif pending:
                    with st.chat_message("assistant"):
                        st.markdown("<div class='ai-typing-indicator'>답변을 입력하고 있습니다<span>...</span></div>", unsafe_allow_html=True)
                if server_down:
                    with st.container(key="ai_chat_server_down_notice", border=True):
                        st.markdown(
                            "<div class='ai-server-status-title'>⚠ 채팅 서버 중단</div>"
                            f"<div class='ai-server-status-message'>{html.escape(str(st.session_state.get('ai_chat_server_down_message') or '채팅 서버가 중단되어 답변을 받을 수 없습니다. 서버를 다시 시작해 주세요.'))}</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "채팅 서버 재접속",
                            key="ai_chat_reconnect",
                            type="primary",
                            disabled=bool(pending),
                            width="stretch",
                        ):
                            with st.spinner("채팅 서버를 다시 시작하고 연결 상태를 확인하고 있습니다..."):
                                reconnect_result = reconnect_chat_server(PORTFOLIO_API)
                            if reconnect_result.get("ok"):
                                st.session_state.ai_chat_server_down = False
                                st.session_state.pop("ai_chat_server_down_message", None)
                                st.session_state.ai_chat_server_recovered = _local_time_text()
                                _ai_chat_server_health.clear()
                                st.rerun()
                            else:
                                st.error(reconnect_result.get("error", "채팅 서버 재접속에 실패했습니다."))
                elif st.session_state.get("ai_chat_server_recovered"):
                    with st.container(key="ai_chat_server_recovered_notice", border=True):
                        st.markdown(
                            "<div class='ai-server-status-title'>✓ 채팅 서버 재접속 완료</div>"
                            "<div class='ai-server-status-message'>이제 새로운 질문을 입력할 수 있습니다.</div>",
                            unsafe_allow_html=True,
                        )
            question = st.chat_input(
                "AI 에이전트에게 질문하세요",
                key="ai_chat_input",
                disabled=not api_confirmed or bool(pending) or server_down,
            )
        st.info(
            "503·504·채팅 서버 중단 시험은 외부 AI API를 호출하지 않으므로 API 비용이 발생하지 않습니다. "
            "시험 결과는 대화·보고서에 N/A로 기록됩니다."
        )
        cases_available = bool(_read_json(AI_CASES_PATH, []))
        fault_disabled = bool(pending) or server_down or not cases_available
        fault_503, fault_504, fault_down = st.columns(3)
        with fault_503:
            if st.button("503 서비스 이용 불가 시험", disabled=fault_disabled, width="stretch"):
                if _start_ai_fault_request(history, "http_503"):
                    st.rerun()
        with fault_504:
            if st.button("504 시간 초과 시험", disabled=fault_disabled, width="stretch"):
                if _start_ai_fault_request(history, "http_504"):
                    st.rerun()
        with fault_down:
            if st.button("채팅 서버 중단 시험", disabled=fault_disabled, width="stretch"):
                if _start_ai_fault_request(history, "server_down"):
                    st.rerun()
        if question:
            st.session_state.pop("ai_chat_server_recovered", None)
            history.append({"role": "user", "content": question, "label": "사용자", "timestamp": _local_time_text()})
            st.session_state.ai_chat_pending = {
                "question": question,
                "started_at": time.monotonic(),
                "future": AI_CHAT_EXECUTOR.submit(_request_ai_chat, question),
            }
            st.rerun()
        if pending:
            time.sleep(0.6)
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


def _render_profile_cards(
    profiles: list[dict],
    selected: str,
    disabled: bool,
    key_prefix: str,
    confirmed: bool,
) -> str:
    columns = st.columns(4)
    for column, profile in zip(columns, profiles):
        generation = profile["generation"]
        judge = profile["judge"]
        available = bool(profile.get("available", True))
        is_selected = confirmed and selected == profile["profile_id"]
        status_label = "처리 중" if is_selected and disabled else "선택됨" if is_selected else ""
        status_slot = (
            f"<div class='profile-status-slot'><span class='profile-status-badge profile-status-selected'>{status_label}</span></div>"
            if status_label
            else "<div class='profile-status-slot is-empty' aria-hidden='true'></div>"
        )
        card_state = " profile-selected" if is_selected else ""
        with column:
            st.markdown(
                f"<div class='profile-card-stack'>{status_slot}<div class='profile-card{card_state}'>"
                f"<div class='profile-title'>{profile['profile_id']} · {html.escape(profile['title'])}</div>"
                f"<div class='profile-summary'>{html.escape(profile['summary'])}</div><hr>"
                f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}<br>"
                f"독립 품질 평가(Judge): {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}</div></div></div>",
                unsafe_allow_html=True,
            )
            if st.button(
                "✓ 선택됨" if is_selected else "선택",
                key=f"{key_prefix}_{profile['profile_id']}",
                type="primary" if confirmed and not is_selected and available and not disabled else "secondary",
                disabled=disabled or not confirmed or is_selected or not available,
                width="stretch",
            ):
                selected = profile["profile_id"]
                st.session_state[f"{key_prefix}_selected"] = selected
                st.rerun()
            if not available:
                st.caption("필수 키 설정 필요: " + ", ".join(profile.get("missing_keys", [])))
    return selected


@st.cache_data(ttl=2, show_spinner=False)
def _read_voc_live_rows(directory: Path = VOC_LIVE_CONVERSATION_DIR) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _clear_voc_live_caches() -> None:
    _read_voc_live_rows.clear()
    _read_jsonl.clear()


def _voc_live_frame() -> pd.DataFrame:
    flattened: list[dict[str, Any]] = []
    for row in _read_voc_live_rows():
        if not is_valid_question_text(row.get("question")):
            continue
        profile = row.get("profile") or {}
        generation = profile.get("generation") or {}
        judge_spec = profile.get("judge") or {}
        result = row.get("result") or {}
        judge = row.get("judge") or {}
        current_rubric = judge.get("rubric_version") == VOC_RUBRIC_VERSION
        scores = judge.get("scores") if current_rubric and isinstance(judge.get("scores"), dict) else {}
        reasons = judge.get("reasons") if current_rubric and isinstance(judge.get("reasons"), dict) else {}
        flattened_row: dict[str, Any] = {
            "timestamp": row.get("finished_at") or row.get("timestamp"),
            "started_at": row.get("timestamp"),
            "request_id": row.get("request_id", ""),
            "question": row.get("question", ""),
            "profile_id": row.get("profile_id", ""),
            "profile_title": profile.get("title", ""),
            "generation_model": f"{generation.get('provider', '')} / {generation.get('model', '')}",
            "judge_model": f"{judge_spec.get('provider', '')} / {judge_spec.get('model', '')}",
            "status": row.get("status", ""),
            "elapsed_seconds": row.get("elapsed_seconds"),
            "answer": result.get("answer") or result.get("policy") or result.get("summary") or "",
            "total": judge.get("total") if current_rubric else None,
            "verdict": judge.get("verdict") if current_rubric else "N/A",
            "rubric": "9항목·100점" if current_rubric else "이전 4항목·20점" if judge else "N/A",
            "rationale": judge.get("rationale", "") if current_rubric else "",
            "score_reasons": reasons,
            "intent_json": result.get("intent_json", ""),
            "trace": result.get("trace", ""),
            "error": row.get("error", ""),
        }
        for name, _maximum in VOC_SCORE_CRITERIA:
            flattened_row[name] = scores.get(name)
        flattened.append(flattened_row)
    if not flattened:
        return pd.DataFrame()
    frame = pd.DataFrame(flattened)
    frame["_sort_time"] = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
    return frame.sort_values("_sort_time", ascending=False).reset_index(drop=True)


def _refresh_voc_live_data(key: str) -> None:
    if st.button(
        "↻ VOC 챗봇 데이터 갱신",
        key=f"voc_live_refresh_{key}",
        help="누적 대화 로그를 다시 읽고 최신 VOC 챗봇 보고서를 갱신합니다.",
    ):
        try:
            from allstar.voc.api.report_generator import generate_live_report

            with st.spinner("누적 로그로 VOC 챗봇 보고서를 다시 작성하고 있습니다..."):
                generate_live_report()
            _clear_voc_live_caches()
            st.toast("VOC 챗봇 데이터와 보고서를 갱신했습니다.", icon="✅")
            st.rerun(scope="app")
        except Exception as error:
            st.error(f"VOC 챗봇 보고서를 갱신하지 못했습니다: {error}")


def _voc_status_text(value: Any) -> str:
    return {
        "completed": "완료",
        "no_data": "관련 데이터 없음",
        "failed": "처리 실패",
        "processing": "처리 중",
        "queued": "대기",
    }.get(str(value), str(value))


def _render_voc_conversation_log(frame: pd.DataFrame) -> None:
    _refresh_voc_live_data("log")
    if frame.empty:
        st.info("아직 저장된 VOC 챗봇 대화 로그가 없습니다.")
        return
    view = pd.DataFrame({
        "시간": frame["timestamp"].map(_local_time_text),
        "질문": frame["question"],
        "프로필": frame["profile_id"],
        "생성 모델": frame["generation_model"],
        "평가 모델": frame["judge_model"],
        "총점": frame["total"],
        "판정": frame["verdict"],
        "상태": frame["status"].map(_voc_status_text),
        "처리시간(초)": frame["elapsed_seconds"],
        "채점 기준": frame["rubric"],
        "답변": frame["answer"],
    })
    _render_dataframe(view, height=460)
    st.caption("요청 ID와 내부 검색 추적 정보는 대화별 채점 상세의 기술 상세에서 확인합니다.")


def _voc_question_page(frame: pd.DataFrame, key: str) -> tuple[pd.DataFrame, list[str]]:
    latest_questions = (
        frame.dropna(subset=["question"])
        .sort_values("_sort_time", ascending=False)
        .drop_duplicates("question", keep="first")
    )
    question_order = latest_questions["question"].astype(str).tolist()
    size_key = f"{key}_page_size"
    page_key = f"{key}_page"
    selected_size = st.selectbox("한 화면에 표시할 질문 수", [5, 10, 20, "전체"], index=1, key=size_key)
    page_size = max(1, len(question_order) if selected_size == "전체" else int(selected_size))
    total_pages = max(1, (len(question_order) + page_size - 1) // page_size)
    st.session_state.setdefault(page_key, 0)
    page = min(max(int(st.session_state[page_key]), 0), total_pages - 1)
    st.session_state[page_key] = page
    controls = st.columns([1, 2, 1])
    controls[0].button(
        "← 이전", key=f"{key}_previous", disabled=page == 0, width="stretch",
        on_click=_change_quality_page, args=(page_key, -1),
    )
    controls[1].markdown(
        f"<div style='text-align:center;padding:.45rem 0;font-weight:700'>{page + 1} / {total_pages} 페이지 · 총 {len(question_order)}질문</div>",
        unsafe_allow_html=True,
    )
    controls[2].button(
        "다음 →", key=f"{key}_next", disabled=page >= total_pages - 1, width="stretch",
        on_click=_change_quality_page, args=(page_key, 1),
    )
    visible_questions = question_order[page * page_size:(page + 1) * page_size]
    visible = frame[frame["question"].astype(str).isin(visible_questions)].copy()
    visible = visible.sort_values("_sort_time", ascending=False).drop_duplicates(["question", "profile_id"], keep="first")
    return visible, visible_questions


def _render_voc_quality(frame: pd.DataFrame) -> None:
    _refresh_voc_live_data("quality")
    if frame.empty:
        st.info("아직 저장된 VOC 챗봇 품질 데이터가 없습니다.")
        return
    scored = frame[frame["rubric"] == "9항목·100점"].copy()
    metric_values = [
        ("전체 대화", len(frame)),
        ("정상 채점", len(scored)),
        ("배포 가능", int(scored["verdict"].eq("배포 가능").sum()) if not scored.empty else 0),
        ("조건부", int(scored["verdict"].astype(str).str.startswith("조건부").sum()) if not scored.empty else 0),
        ("개선·보류", int(scored["verdict"].astype(str).isin(["주요 개선 필요", "배포 보류", "배포 보류(즉시)"]).sum()) if not scored.empty else 0),
        ("N/A", len(frame) - len(scored)),
    ]
    columns = st.columns(len(metric_values))
    for column, (label, value) in zip(columns, metric_values):
        column.metric(label, value)
    if not scored.empty:
        average_columns = st.columns(2)
        average_columns[0].metric("평균 품질점수", f"{pd.to_numeric(scored['total'], errors='coerce').mean():.1f}/100")
        average_columns[1].metric("평균 처리시간", f"{pd.to_numeric(frame['elapsed_seconds'], errors='coerce').mean():.1f}초")

    visible, question_order = _voc_question_page(frame, "voc_live_quality")
    chart_source = visible[visible["rubric"] == "9항목·100점"].copy()
    if chart_source.empty:
        st.info("선택한 질문 범위에는 새 9항목·100점 채점 결과가 없습니다.")
    else:
        chart_source["질문"] = chart_source["question"].map(lambda value: str(value)[:38])
        chart_source["프로필"] = chart_source["profile_id"]
        chart_source["표시"] = chart_source.apply(
            lambda row: f"{row['profile_id']} · {row['total']}점<br>{row['verdict']}", axis=1
        )
        figure = px.bar(
            chart_source,
            x="질문",
            y="total",
            color="프로필",
            barmode="group",
            text="표시",
            category_orders={"질문": [question[:38] for question in question_order], "프로필": ["A", "B", "C", "D"]},
            hover_data=["verdict", "generation_model", "judge_model", "elapsed_seconds"],
        )
        figure.update_traces(textposition="outside", cliponaxis=False)
        figure.update_layout(yaxis_title="품질점수", yaxis_range=[0, 108], xaxis_title="질문", margin=dict(t=40, b=40))
        st.plotly_chart(figure, width="stretch", key="voc_live_quality_chart")

    comparison_rows = []
    for question in question_order:
        question_rows = visible[visible["question"].astype(str) == question]
        row: dict[str, Any] = {"질문": question}
        for profile_id in ("A", "B", "C", "D"):
            profile_rows = question_rows[question_rows["profile_id"] == profile_id]
            if profile_rows.empty:
                row[f"프로필 {profile_id}"] = "데이터 없음"
            else:
                profile_row = profile_rows.iloc[0]
                row[f"프로필 {profile_id}"] = (
                    f"{profile_row['total']:.0f}점 · {profile_row['verdict']}"
                    if pd.notna(profile_row["total"])
                    else f"N/A · {_voc_status_text(profile_row['status'])}"
                )
        comparison_rows.append(row)
    if comparison_rows:
        _render_dataframe(pd.DataFrame(comparison_rows), height=360)


def _render_voc_breakdown(frame: pd.DataFrame) -> None:
    _refresh_voc_live_data("breakdown")
    scored = frame[frame["rubric"] == "9항목·100점"].copy() if not frame.empty else pd.DataFrame()
    if scored.empty:
        st.info("9항목·100점으로 정상 채점된 VOC 챗봇 대화가 아직 없습니다.")
        return
    left, right = st.columns([1.1, 1])
    figure = go.Figure()
    categories = [name for name, _maximum in VOC_SCORE_CRITERIA]
    table_rows: list[dict[str, Any]] = []
    for name, maximum in VOC_SCORE_CRITERIA:
        table_rows.append({"평가 항목": name, "최대": maximum})
    counts = []
    for profile_id in ("A", "B", "C", "D"):
        profile_rows = scored[scored["profile_id"] == profile_id]
        counts.append(f"{profile_id} {len(profile_rows)}건")
        normalized = []
        for index, (name, maximum) in enumerate(VOC_SCORE_CRITERIA):
            values = pd.to_numeric(profile_rows[name], errors="coerce").dropna() if not profile_rows.empty else pd.Series(dtype=float)
            mean = values.mean() if not values.empty else None
            normalized.append((mean / maximum * 100) if mean is not None else None)
            table_rows[index][f"프로필 {profile_id}"] = f"{mean:.1f}/{maximum}" if mean is not None else "데이터 없음"
        if any(value is not None for value in normalized):
            figure.add_trace(go.Scatterpolar(
                r=[value or 0 for value in normalized] + [normalized[0] or 0],
                theta=categories + [categories[0]],
                fill="toself",
                name=f"프로필 {profile_id}",
            ))
    figure.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 100], "ticksuffix": "%"}},
        margin={"l": 35, "r": 35, "t": 40, "b": 35},
        legend={"orientation": "h"},
    )
    with left:
        st.caption("A~D 프로필 조합 비교 · 항목별 최대 점수가 달라 0~100%로 정규화")
        st.plotly_chart(figure, width="stretch", key="voc_live_breakdown_radar")
    with right:
        st.caption("정확한 평균점수 · " + " · ".join(counts))
        _render_dataframe(pd.DataFrame(table_rows), height=470)


def _render_voc_detail(frame: pd.DataFrame) -> None:
    _refresh_voc_live_data("detail")
    if frame.empty:
        st.info("아직 확인할 VOC 챗봇 대화가 없습니다.")
        return
    profile_filter = st.selectbox("프로필", ["전체", "A", "B", "C", "D"], key="voc_live_detail_profile")
    source = frame if profile_filter == "전체" else frame[frame["profile_id"] == profile_filter]
    limit = st.selectbox("표시할 최근 대화 수", [5, 10, 20, "전체"], index=1, key="voc_live_detail_limit")
    source = source if limit == "전체" else source.head(int(limit))
    for index, row in source.iterrows():
        total = f"{row['total']:.0f}점" if pd.notna(row["total"]) else "N/A"
        label = f"{_local_time_text(row['timestamp'])} · 프로필 {row['profile_id']} · {total} · {row['verdict']} · {str(row['question'])[:45]}"
        with st.expander(label, expanded=False):
            st.markdown(f"**질문**  \n{row['question']}")
            st.markdown(f"**답변**  \n{row['answer'] or '결과 없음'}")
            summary_columns = st.columns(3)
            summary_columns[0].metric("총점", total)
            summary_columns[1].metric("판정", row["verdict"])
            summary_columns[2].metric("처리시간", f"{row['elapsed_seconds']}초")
            if row["rubric"] == "9항목·100점":
                reasons = row.get("score_reasons") if isinstance(row.get("score_reasons"), dict) else {}
                score_rows = []
                for name, maximum in VOC_SCORE_CRITERIA:
                    score_rows.append({
                        "평가 항목": name,
                        "점수": row.get(name),
                        "최대": maximum,
                        "근거": reasons.get(name, ""),
                    })
                _render_dataframe(pd.DataFrame(score_rows), height=350)
                if row.get("rationale"):
                    st.info(f"종합 근거: {row['rationale']}")
            else:
                st.warning("이 대화는 새 9항목·100점 채점 이전 기록이거나 독립 채점이 완료되지 않아 N/A입니다.")
            with st.popover("기술 상세"):
                st.caption(f"요청 ID: {row['request_id']}")
                st.json({
                    "intent": _safe_json(row.get("intent_json") or ""),
                    "trace": row.get("trace") or "",
                    "error": row.get("error") or "",
                })


def _render_voc_chat_conversation() -> None:
    pending = st.session_state.get("voc_pending")
    _watch_voc_chat_server()
    server_down = bool(st.session_state.get("voc_chat_server_down"))
    profiles = _get_json(f"{VOC_API}/profiles") or public_profiles()
    selected_key = "voc_chat_profile_selected"
    selected = st.session_state.setdefault(selected_key, "A")
    api_confirmed = _required_api_confirmation(
        "voc_chat_api_confirm",
        "메시지 전송 시 외부 AI API 호출과 비용이 발생할 수 있음을 확인했습니다.",
    )
    _render_profile_cards(
        list(profiles),
        selected,
        bool(pending) or server_down,
        "voc_chat_profile",
        api_confirmed,
    )
    st.info("A~D는 답변 생성 모델과 독립 품질 평가 모델(Judge)의 조합입니다. 현재 질문 한 건에만 적용됩니다.")

    history = st.session_state.setdefault("voc_chat_history", [])
    with st.container(key="voc_chat_panel"):
        with st.container(height=520, border=True, autoscroll=True):
            if not history:
                st.caption("VOC 관련 질문을 입력하면 이 영역에 메신저 형태로 대화와 7단계 처리 결과가 표시됩니다.")
            for message in history:
                with st.chat_message(message["role"]):
                    st.write(message["content"])
                    if message.get("meta"):
                        st.caption(message["meta"])
                    if message.get("status"):
                        with st.expander("7단계 처리 결과", expanded=False):
                            _render_stage_explorer(message["status"], f"voc_history_{message['status']['request_id']}")

            if pending and not server_down:
                status = _get_json(f"{VOC_API}/chat/{pending}/status")
                if isinstance(status, dict):
                    st.markdown("### 현재 질문 처리 과정")
                    _render_stage_explorer(status, f"voc_pending_{pending}")
                    terminal = status["status"] in {"completed", "failed", "no_data"}
                    st.progress(100 if terminal else min(95, int(status.get("elapsed_seconds", 0)) + 1))
                    st.caption(f"{status['current_stage']} · {status.get('elapsed_seconds', 0):.1f}초 · 프로필 {status['profile_id']}")
                    if terminal:
                        result = status.get("result") or {}
                        judge = status.get("judge") or {}
                        if status["status"] in {"completed", "no_data"}:
                            answer = result.get("answer") or result.get("policy") or result.get("summary")
                        else:
                            answer = "VOC 처리 중 문제가 발생했습니다. 아래 7단계 처리 결과에서 실제 실패 단계와 기술 상세를 확인해 주세요."
                        meta = (
                            f"프로필 {status['profile_id']} · {status.get('elapsed_seconds', 0):.1f}초 · "
                            f"Judge {judge.get('total', 'N/A')} / {judge.get('verdict', 'N/A')} · {_local_time_text()}"
                        )
                        st.session_state.voc_chat_history.append({"role": "assistant", "content": answer or "결과 없음", "meta": meta, "status": status})
                        st.session_state.voc_pending = None
                        _clear_voc_live_caches()
                        st.rerun()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("VOC 요청 상태를 확인할 수 없습니다.")
            if server_down:
                with st.container(key="voc_chat_server_down_notice", border=True):
                    st.markdown(
                        "<div class='ai-server-status-title'>⚠ VOC 채팅 서버 중단</div>"
                        f"<div class='ai-server-status-message'>{html.escape(str(st.session_state.get('voc_chat_server_down_message') or 'VOC 채팅 서버가 중단되어 답변을 받을 수 없습니다. 서버를 다시 시작해 주세요.'))}</div>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "VOC 채팅 서버 재접속",
                        key="voc_chat_reconnect",
                        type="primary",
                        width="stretch",
                    ):
                        with st.spinner("VOC 채팅 서버를 다시 시작하고 연결 상태를 확인하고 있습니다..."):
                            reconnect_result = reconnect_voc_chat_server(VOC_API)
                        if reconnect_result.get("ok"):
                            st.session_state.voc_chat_server_down = False
                            st.session_state.pop("voc_chat_server_down_message", None)
                            st.session_state.voc_chat_server_recovered = _local_time_text()
                            st.session_state.voc_pending = None
                            _voc_chat_server_health.clear()
                            st.rerun()
                        else:
                            st.error(reconnect_result.get("error", "VOC 채팅 서버 재접속에 실패했습니다."))
            elif st.session_state.get("voc_chat_server_recovered"):
                with st.container(key="voc_chat_server_recovered_notice", border=True):
                    st.markdown(
                        "<div class='ai-server-status-title'>✓ VOC 채팅 서버 재접속 완료</div>"
                        "<div class='ai-server-status-message'>이제 새로운 VOC 질문을 입력할 수 있습니다.</div>",
                        unsafe_allow_html=True,
                    )

        question = st.chat_input(
            "VOC 관련 단발 질문을 입력하세요",
            key="voc_chat_input",
            disabled=bool(pending) or not api_confirmed or server_down,
        )
    if question:
        st.session_state.voc_chat_history.append({
            "role": "user", "content": question, "meta": f"사용자 · {_local_time_text()}"
        })
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(f"{VOC_API}/chat", json={"question": question, "profile_id": st.session_state[selected_key]})
                response.raise_for_status()
                st.session_state.voc_pending = response.json()["request_id"]
        except Exception as error:
            st.session_state.voc_chat_history.append({
                "role": "assistant",
                "content": f"VOC 서버 요청 실패: {error}",
                "meta": f"오류 · {_local_time_text()}",
            })
        st.rerun()


def render_voc_chat() -> None:
    _section("VOC 챗봇", "질문마다 A~D 모델 프로필을 선택하고 7단계 처리 결과와 100점 품질 현황을 확인합니다.")
    tab_chat, tab_log, tab_quality, tab_breakdown, tab_detail = st.tabs(
        ["챗봇과 대화", "대화 로그", "품질 현황", "유형별 비교", "대화별 채점 상세"]
    )
    with tab_chat:
        _render_voc_chat_conversation()
    frame = _voc_live_frame()
    with tab_log:
        _render_voc_conversation_log(frame)
    with tab_quality:
        _render_voc_quality(frame)
    with tab_breakdown:
        _render_voc_breakdown(frame)
    with tab_detail:
        _render_voc_detail(frame)


@st.cache_data(ttl=5, show_spinner=False)
def _k6_environment_status(portfolio_api: str, grafana_url: str) -> dict[str, Any]:
    return inspect_environment(portfolio_api, grafana_url)


def _k6_environment_panel(status: dict[str, Any]) -> None:
    items = (
        ("K6", status["k6"]),
        ("AI 에이전트 서버", status["api"]),
        ("Prometheus", status["prometheus"]),
        ("Grafana", status["grafana"]),
    )
    cards = []
    for label, value in items:
        state_class = "ready" if value.get("ok") else "offline"
        state_label = "사용 가능" if value.get("ok") else "사용 불가"
        detail = html.escape(str(value.get("detail") or "확인 결과 없음"))
        cards.append(
            f"<div class='k6-env-item k6-env-{state_class}'>"
            f"<b><span></span>{html.escape(label)}</b><strong>{state_label}</strong><small>{detail}</small></div>"
        )
    st.markdown("<div class='k6-env-grid'>" + "".join(cards) + "</div>", unsafe_allow_html=True)
    if not status["grafana"]["ok"]:
        st.caption("Grafana는 결과 조회용이므로 꺼져 있어도 시험할 수 있지만, 실행 결과 화면은 Grafana 시작 후 확인해야 합니다.")
    if status.get("inside_docker"):
        st.warning("현재 Streamlit이 Docker 안에서 실행 중입니다. 컨테이너 내부의 Linux용 K6가 확인되어야 시험할 수 있습니다.")


def _enable_k6_number_hold_repeat() -> None:
    """K6 숫자 입력의 증감 버튼을 길게 누르면 현재 버튼을 빠르게 반복 실행한다."""
    components.html(
        """
        <script>
        (() => {
            const root = window.parent;
            const doc = root.document;
            if (root.__allstarK6HoldRepeatInstalled) return;
            root.__allstarK6HoldRepeatInstalled = true;
            const state = { delay: null, interval: null, cardKey: null, label: null };
            const numberState = (button) => {
                const input = button?.closest?.('[data-testid="stNumberInputContainer"]')
                    ?.querySelector?.('[data-testid="stNumberInputField"]');
                if (!input) return null;
                const duration = input.getAttribute("aria-label")?.includes("시간");
                return {
                    input,
                    minimum: duration ? 10 : 1,
                    maximum: duration ? 600 : 999,
                    value: Number(input.value),
                };
            };
            const reachedBoundary = (button) => {
                const current = numberState(button);
                if (!current || !Number.isFinite(current.value)) return false;
                return button.getAttribute("aria-label") === "Increment"
                    ? current.value >= current.maximum
                    : current.value <= current.minimum;
            };
            const stop = () => {
                if (state.delay) root.clearTimeout(state.delay);
                if (state.interval) root.clearInterval(state.interval);
                state.delay = null;
                state.interval = null;
                state.cardKey = null;
                state.label = null;
            };
            const currentButton = () => {
                if (!state.cardKey || !state.label) return null;
                const card = doc.getElementsByClassName(state.cardKey)[0];
                return card?.querySelector(`button[aria-label="${state.label}"]`) || null;
            };
            const repeat = () => {
                const button = currentButton();
                if (!button || button.disabled || reachedBoundary(button)) {
                    stop();
                    return;
                }
                button.click();
            };
            doc.addEventListener("click", (event) => {
                const button = event.target.closest?.('button[aria-label="Increment"],button[aria-label="Decrement"]');
                const card = button?.closest?.('[class*="st-key-k6_card_"]');
                if (!button || !card || !reachedBoundary(button)) return;
                event.preventDefault();
                event.stopImmediatePropagation();
                stop();
            }, true);
            doc.addEventListener("pointerdown", (event) => {
                if (event.button !== 0) return;
                const button = event.target.closest?.('button[aria-label="Increment"],button[aria-label="Decrement"]');
                const card = button?.closest?.('[class*="st-key-k6_card_"]');
                if (!button || !card || button.disabled) return;
                stop();
                state.cardKey = Array.from(card.classList).find((name) => name.startsWith("st-key-k6_card_"));
                state.label = button.getAttribute("aria-label");
                state.delay = root.setTimeout(() => {
                    repeat();
                    state.interval = root.setInterval(repeat, 100);
                }, 450);
            }, true);
            for (const eventName of ["pointerup", "pointercancel", "mouseup", "touchend"]) {
                doc.addEventListener(eventName, stop, true);
            }
            root.addEventListener("blur", stop, true);
        })();
        </script>
        """,
        height=0,
    )


def _scroll_to_k6_run_once(run_id: str) -> None:
    safe_run_id = re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)
    anchor_id = f"k6-run-bottom-{safe_run_id}"
    st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
    components.html(
        f"""
        <script>
        (() => {{
            const move = (behavior) => {{
                const parentDocument = window.parent.document;
                const target = parentDocument.getElementById({json.dumps(anchor_id)});
                if (!target) return;
                const scroller = target.closest('[data-testid="stMain"]') || parentDocument.scrollingElement;
                if (scroller && typeof scroller.scrollTo === "function") {{
                    scroller.scrollTo({{top: scroller.scrollHeight, behavior}});
                }} else {{
                    target.scrollIntoView({{behavior, block: "end"}});
                }}
            }};
            window.requestAnimationFrame(() => move("smooth"));
            window.setTimeout(() => move("smooth"), 300);
            window.setTimeout(() => move("auto"), 750);
        }})();
        </script>
        """,
        height=0,
    )


def _k6_card_status(run: Any, test_id: str) -> tuple[str, str]:
    if run is None or run.spec.test_id != test_id:
        return "idle", ""
    labels = {
        "running": "실행 중",
        "completed": "완료",
        "failed": "실패",
        "cancelled": "사용자 중단",
    }
    return run.status, labels.get(run.status, run.status)


def _clamp_k6_number_input(key: str, minimum: int, maximum: int) -> None:
    """직접 입력하거나 증감한 값을 허용 범위의 가장 가까운 값으로 즉시 보정한다."""
    try:
        value = int(st.session_state.get(key, minimum))
    except (TypeError, ValueError):
        value = minimum
    st.session_state[key] = min(maximum, max(minimum, value))


def _render_k6_card(spec: Any, environment: dict[str, Any], run: Any) -> None:
    visual_state, state_label = _k6_card_status(run, spec.test_id)
    container_key = f"k6_card_{spec.test_id}_{visual_state}"
    with st.container(border=True, key=container_key):
        badge = (
            f"<div class='k6-card-status'><span class='k6-card-badge k6-card-badge-{visual_state}'>{html.escape(state_label)}</span></div>"
            if state_label else "<div class='k6-card-status k6-card-status-empty'></div>"
        )
        result_text = (
            "Prometheus·Grafana 기록 · 별도 보고서 없음"
            if not spec.write_summary_report
            else "실행 로그 누적 · 정상 완료 시 기존 정식 보고서 갱신"
        )
        st.markdown(
            badge
            + f"<div class='k6-card-copy'><h4>{html.escape(spec.title)}</h4>"
            + f"<div class='k6-card-english'>({html.escape(spec.english)})</div>"
            + f"<p>{html.escape(spec.description)}</p><hr><small>{html.escape(result_text)}</small></div>",
            unsafe_allow_html=True,
        )
        vus: int | None = None
        duration: int | None = None
        if spec.default_vus is not None and spec.default_duration is not None:
            vus_key = f"k6_vus_{spec.test_id}"
            duration_key = f"k6_duration_{spec.test_id}"
            setting_columns = st.columns(2)
            with setting_columns[0]:
                vus = int(st.number_input(
                    "최대 가상 인원(VU)", value=spec.default_vus, step=1,
                    key=vus_key, disabled=run is not None,
                    on_change=_clamp_k6_number_input, args=(vus_key, K6_MIN_VUS, K6_MAX_VUS),
                ))
            with setting_columns[1]:
                duration = int(st.number_input(
                    "실행 시간(초)", value=spec.default_duration, step=1,
                    key=duration_key, disabled=run is not None,
                    on_change=_clamp_k6_number_input,
                    args=(duration_key, K6_MIN_DURATION, K6_MAX_DURATION),
                ))
        elif spec.test_id == "ai_smoke":
            st.caption("고정 설정: 가상 사용자 1명 · 상태와 모의 채팅 각 1회")
        elif spec.test_id == "ai_validation":
            st.caption("고정 범위: 장애 모의 K6 · 외부 AI 제외 기능 회귀")
        else:
            st.caption("고정 단계: 1명 → 10명 → 25명 · 단계 사이 5초 안정화")

        api_confirmed = True
        if spec.actual_api:
            api_confirmed = _required_api_confirmation(
                "k6_api_performance_confirm",
                "실제 AI API 호출과 비용 발생 가능성을 확인했습니다.",
            )
        missing = []
        if not environment["k6"]["ok"]:
            missing.append("K6")
        if not environment["api"]["ok"]:
            missing.append("AI 서버")
        if not environment["prometheus"]["ok"]:
            missing.append("Prometheus")
        if missing:
            st.caption("실행 불가: " + ", ".join(missing) + " 준비 필요")
        disabled = run is not None or bool(missing) or not api_confirmed
        if st.button(
            f"{spec.title} 실행",
            key=f"run_k6_{spec.test_id}",
            type="primary" if not disabled else "secondary",
            disabled=disabled,
            width="stretch",
        ):
            executable = environment["k6"].get("executable")
            if not executable:
                st.error("K6 실행 파일을 찾지 못했습니다.")
            else:
                try:
                    started = start_run(
                        spec.test_id,
                        k6_executable=str(executable),
                        portfolio_api=PORTFOLIO_API,
                        vus=vus,
                        duration=duration,
                    )
                except (RuntimeError, ValueError) as error:
                    st.error(str(error))
                else:
                    st.session_state.pop("k6_scrolled_run_id", None)
                    st.session_state.k6_started_run_id = started.run_id
                    st.rerun(scope="fragment")


def _render_k6_active_run(run: Any) -> None:
    if run is None:
        return
    elapsed = run.elapsed_seconds
    st.markdown("---")
    st.markdown(f"## 현재 시험: {run.spec.title} ({run.spec.english})")
    if run.status == "running":
        st.info(f"실행 중 · {elapsed:.1f}초 경과")
        if st.button("시험 중지", key="stop_dashboard_k6_run", type="primary"):
            with st.spinner("시험과 하위 프로세스를 중지하고 있습니다..."):
                stop_current_run()
            st.rerun(scope="fragment")
    elif run.status == "completed":
        st.success(f"정상 완료 · {elapsed:.1f}초")
    elif run.status == "cancelled":
        st.warning(f"사용자가 중단한 시험입니다 · {elapsed:.1f}초")
    else:
        st.error(f"시험 실패 · 종료 코드 {run.exit_code} · {elapsed:.1f}초")

    if run.settings:
        st.caption(" · ".join(f"{key}: {value}" for key, value in run.settings.items() if key != "실행 위치"))
    output = _read_process_output(run.log_path)
    st.markdown("### 실시간 터미널")
    with st.container(height=360, border=True, autoscroll=True, key=f"k6_terminal_{run.run_id}"):
        st.code(output[-50000:] or "시험 실행을 준비하고 있습니다...", language="text", wrap_lines=True)

    if run.finalized:
        if run.status != "completed":
            st.caption("중단·실패 실행은 원문 로그만 보존하며 기존 정상 최신 보고서를 덮어쓰지 않습니다.")
        if st.button("실행 결과 닫기 · 다음 시험 준비", key="clear_dashboard_k6_run", type="primary"):
            clear_finished_run()
            st.session_state.pop("k6_started_run_id", None)
            st.rerun(scope="fragment")

    if st.session_state.get("k6_scrolled_run_id") != run.run_id:
        _scroll_to_k6_run_once(run.run_id)
        st.session_state.k6_scrolled_run_id = run.run_id


@st.fragment
def _render_k6_load_test_fragment() -> None:
    _enable_k6_number_hold_repeat()
    environment = _k6_environment_status(PORTFOLIO_API, GRAFANA)
    heading_columns = st.columns([5, 1])
    with heading_columns[0]:
        st.markdown("### 실행 환경 상태")
    with heading_columns[1]:
        if st.button("상태 새로고침", key="refresh_k6_environment", width="stretch"):
            _k6_environment_status.clear()
            st.rerun(scope="fragment")
    _k6_environment_panel(environment)
    if not environment["k6"]["ok"]:
        st.link_button("K6 공식 설치 안내 열기", K6_INSTALL_URL, width="stretch")
    st.markdown(
        "<div class='scope-box'><b>실행 안내</b><br>한 번에 하나의 시험만 실행합니다. "
        "직접 K6 5종은 Grafana용이며, 장애·기능 검증과 서버 연결 성능 종합 시험의 기존 정식 보고서는 유지합니다.</div>",
        unsafe_allow_html=True,
    )
    run = poll_current_run()
    rows = (K6_TEST_SPECS[:4], K6_TEST_SPECS[4:])
    for row_index, specs in enumerate(rows):
        with st.container(key=f"k6_card_row_{row_index}"):
            columns = st.columns(len(specs), gap="medium")
            for column, spec in zip(columns, specs):
                with column:
                    _render_k6_card(spec, environment, run)
    run = poll_current_run()
    _render_k6_active_run(run)
    if run is not None and not run.finalized:
        time.sleep(1)
        st.rerun(scope="fragment")


def render_k6_load_test() -> None:
    _section("K6 부하 테스트", "주요 부하·장애·서버 연결 성능 시험을 선택하고 진행 내용을 실시간으로 확인합니다.")
    _render_k6_load_test_fragment()


def render_monitoring() -> None:
    _section("모니터링", "상위 모니터링 탭 아래에서 Grafana 화면 4개를 바로 확인합니다.")
    grafana_ready = bool(_get_json(f"{GRAFANA}/api/health"))
    dashboards = [
        ("AI 에이전트 실시간 운영", "ai-agent-quality"),
        ("K6 성능 부하 시험", "k6-performance-test"),
        ("VOC 챗봇 실시간 운영", "voc-live-operations"),
        ("VOC QA·A~D 비교", "voc-qa-abcd"),
    ]
    empty_guides = {
        "ai-agent-quality": "실제 챗봇 요청과 백그라운드 채점이 완료되면 운영·Judge 지표가 갱신됩니다.",
        "k6-performance-test": "K6 시험 실행 중 수집된 지표가 시험별 식별자로 구분되어 표시됩니다.",
        "voc-live-operations": "VOC 챗봇 요청이 없을 때는 누적 값과 마지막 활동 시각으로 수집 상태를 구분할 수 있습니다.",
        "voc-qa-abcd": "A~D 정식 테스트케이스 보고서의 최신 결과를 읽어 비교합니다.",
    }
    tabs = st.tabs([name for name, _uid in dashboards])
    for tab, (name, uid) in zip(tabs, dashboards):
        with tab:
            url = f"{GRAFANA}/d/{uid}?orgId=1&kiosk"
            st.link_button(f"{name} 새 창에서 열기", url)
            if grafana_ready:
                st.caption(empty_guides[uid])
                components.iframe(url, height=_grafana_embed_height(uid), scrolling=False)
            else:
                st.warning("운영 상태 화면(Grafana)이 중지되어 있습니다. AllStar 서버 관리에서 Grafana를 먼저 시작하세요.")
    _sync_grafana_theme_with_browser()


def _sync_grafana_theme_with_browser() -> None:
    """브라우저 색상 설정이 바뀌면 Grafana iframe과 새 창 링크를 같은 테마로 다시 연다."""
    dashboard_prefix = f"{GRAFANA.rstrip('/')}/d/"
    components.html(
        f"""
        <script>
        (() => {{
            const parentWindow = window.parent;
            const parentDocument = parentWindow.document;
            const dashboardPrefix = {json.dumps(dashboard_prefix)};
            const colorPreference = parentWindow.matchMedia('(prefers-color-scheme: dark)');

            const syncTheme = () => {{
                const theme = colorPreference.matches ? 'dark' : 'light';
                const targets = parentDocument.querySelectorAll('iframe[src], a[href]');
                targets.forEach((target) => {{
                    const attribute = target.tagName === 'IFRAME' ? 'src' : 'href';
                    const rawUrl = target.getAttribute(attribute);
                    if (!rawUrl || !rawUrl.startsWith(dashboardPrefix)) return;
                    const url = new URL(rawUrl, parentWindow.location.href);
                    const hasBareKiosk = /[?&]kiosk(?:&|$)/.test(rawUrl);
                    if (url.searchParams.get('theme') === theme && hasBareKiosk) return;
                    url.searchParams.delete('kiosk');
                    url.searchParams.set('theme', theme);
                    const separator = url.search ? '&' : '?';
                    target.setAttribute(attribute, `${{url.toString()}}${{separator}}kiosk`);
                }});
            }};

            if (typeof colorPreference.addEventListener === 'function') {{
                colorPreference.addEventListener('change', syncTheme);
            }} else if (typeof colorPreference.addListener === 'function') {{
                colorPreference.addListener(syncTheme);
            }}
            const observer = new MutationObserver(syncTheme);
            observer.observe(parentDocument.body, {{childList: true, subtree: true}});
            parentWindow.requestAnimationFrame(syncTheme);
            parentWindow.setTimeout(syncTheme, 300);
            parentWindow.setTimeout(syncTheme, 1000);
        }})();
        </script>
        """,
        height=0,
    )


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
    """보고서 생성 완료를 감지해 보고서 모음을 수동 새로고침 없이 갱신한다."""
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
    _section("보고서 모음", "AI 에이전트·VOC 품질 보고서와 운영 시험 보고서 6개를 한곳에서 확인합니다.")
    tabs = st.tabs(
        [
            "AI 에이전트 챗봇 보고서",
            "AI 에이전트 테스트케이스 보고서",
            "VOC 챗봇 보고서",
            "VOC 테스트케이스 보고서",
            "서버 연결 성능 보고서",
            "장애·기능 검증 보고서",
        ]
    )
    paths = [
        (AI_AGENT_REPORT_ROOT / "live" / "live_report.md", "실시간 AI 상담과 백그라운드 채점 결과입니다."),
        (AI_AGENT_REPORT_ROOT / "batch" / "final_quality_report.md", "등록된 AI 테스트케이스 전체의 비교 품질 결과입니다."),
        (VOC_REPORT_ROOT / "live" / "latest" / "voc_live_report.md", "VOC 단발 질문과 A~D 프로필·Judge 결과입니다."),
        (REPORT_ROOT / "performance" / "performance_report.md", "1명·10명·25명 단계별 독립 성능 시험 결과입니다."),
        (REPORT_ROOT / "defects" / "chaos" / "defect_report.md", "장애 재현과 기능 회귀 결과입니다."),
    ]
    for tab, (path, description) in zip((tabs[0], tabs[1], tabs[2], tabs[4], tabs[5]), paths):
        with tab:
            _render_markdown_report(tab.label if hasattr(tab, "label") else "보고서", path, description)
    with tabs[3]:
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


def _render_score_breakdown(
    df: pd.DataFrame | None,
    model_column: str = "model_type",
    key: str = "quality_breakdown",
) -> None:
    if df is None or df.empty:
        st.info("표시할 품질 데이터가 없습니다.")
        return
    available_scores = [column for column in SCORE_COLUMNS if column in df]
    if not available_scores:
        st.info("품질 항목 점수가 아직 기록되지 않았습니다.")
        return
    decisions = df.get("overall_decision", pd.Series(index=df.index, dtype=str)).fillna("미채점")
    scored = df[decisions.isin(["PASS", "REVIEW", "FAIL"])].copy()
    if scored.empty:
        st.info("채점 가능한 결과가 없습니다. N/A와 미채점은 평균에서 제외됩니다.")
        return
    if model_column not in scored:
        scored[model_column] = "전체"
    for column in available_scores:
        scored[column] = pd.to_numeric(scored[column], errors="coerce")
    averages = scored.groupby(model_column)[available_scores].mean()
    ordered_models = [
        model for model in ("api", "api_based", "rule", "rule_based") if model in averages.index
    ]
    ordered_models.extend(model for model in averages.index if model not in ordered_models)
    averages = averages.loc[ordered_models]
    average_labels = averages.rename(index=_model_label, columns=SCORE_LABELS)

    radar_source = average_labels.reset_index(names="답변 종류").melt(
        id_vars="답변 종류", var_name="품질 항목", value_name="점수"
    )
    figure = px.line_polar(
        radar_source,
        r="점수",
        theta="품질 항목",
        color="답변 종류",
        line_close=True,
        range_r=[0, 5],
        markers=True,
    )
    figure.update_traces(fill="toself", opacity=.72)
    figure.update_layout(margin=dict(t=45, b=35, l=35, r=35), legend_title_text="답변 종류")

    model_labels = average_labels.index.tolist()
    rows: list[dict[str, Any]] = []
    for score_label in [SCORE_LABELS[column] for column in available_scores] + ["품질 평균"]:
        row: dict[str, Any] = {"품질 항목": score_label}
        model_values: list[tuple[str, float]] = []
        for label in model_labels:
            value = (
                float(average_labels.loc[label].mean())
                if score_label == "품질 평균"
                else float(average_labels.loc[label, score_label])
            )
            row[label] = round(value, 2)
            model_values.append((label, value))
        if len(model_values) == 2:
            difference = model_values[0][1] - model_values[1][1]
            if abs(difference) < .005:
                row["점수 차이"] = "동일"
            else:
                winner = "API" if difference > 0 and "API" in model_values[0][0] else (
                    "규칙 기반" if difference < 0 and "규칙" in model_values[1][0] else model_values[0 if difference > 0 else 1][0]
                )
                row["점수 차이"] = f"{winner} +{abs(difference):.2f}"
        else:
            row["점수 차이"] = "-"
        rows.append(row)
    score_table = pd.DataFrame(rows)

    with st.container(key=f"{key}_comparison"):
        left, right = st.columns([1.08, 1])
        with left:
            st.markdown("#### 품질 항목별 형태")
            st.caption("레이더 바깥쪽에 가까울수록 평균점수가 높습니다. 점수 범위는 0~5점입니다.")
            st.plotly_chart(figure, width="stretch", key=f"{key}_radar")
        with right:
            st.markdown("#### 정확한 평균점수")
            counts = scored.groupby(model_column).size()
            count_text = " · ".join(f"{_model_label(model)} {int(count)}건" for model, count in counts.items())
            st.caption(f"N/A·미채점 제외 · 평균 계산 평가 수: {count_text}")
            styled = score_table.style.highlight_max(axis=1, subset=model_labels, color="#dff5e7").format(
                {label: "{:.2f}" for label in model_labels}
            )
            st.dataframe(styled, width="stretch", hide_index=True, height=285)
            descriptions = "<br>".join(
                f"<b>{label}</b>: {description}" for label, description in SCORE_DESCRIPTIONS.items()
            )
            st.markdown(f"<div class='quality-score-help'>{descriptions}</div>", unsafe_allow_html=True)


def _render_quality_detail(
    df: pd.DataFrame | None,
    key: str = "quality_detail",
    *,
    newest_first: bool = False,
) -> None:
    if df is None or df.empty:
        st.info("표시할 상세 결과가 없습니다.")
        return
    view = df.drop(columns=["request_id"], errors="ignore").copy()
    if "overall_decision" in view:
        decisions = ["전체", *sorted(view["overall_decision"].dropna().unique().tolist())]
        selected = st.selectbox("판정 필터", decisions, key=f"{key}_decision")
        if selected != "전체":
            view = view[view["overall_decision"] == selected]
    if newest_first and "timestamp" in view:
        view = view.assign(
            _sort_time=pd.to_datetime(view["timestamp"], errors="coerce", utc=True)
        ).sort_values("_sort_time", ascending=False, na_position="last")
        view = view.drop(columns=["_sort_time"])
    technical_columns = ["fault_type", "http_status", "source_case_id", "err_detail", "error_detail"]
    trailing_columns = [column for column in technical_columns if column in view.columns]
    if trailing_columns:
        primary_columns = [column for column in view.columns if column not in trailing_columns]
        view = view[primary_columns + trailing_columns]
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


def _render_ai_case_execution() -> None:
    cases = _read_json(AI_CASES_PATH, [])
    running = bool(st.session_state.get("ai_batch_process"))
    st.markdown(
        f"<div class='scope-box'><b>전체 실행 범위</b><br>등록된 테스트케이스 전체 {len(cases)}건을 "
        "규칙 기반과 서버 연결 방식(API)으로 각각 실행해 답변과 품질 판정을 비교합니다.<br>"
        "실행 로그는 누적되고 최신 배치 품질 보고서는 실행 완료 후 자동 갱신됩니다.</div>",
        unsafe_allow_html=True,
    )
    if not cases:
        st.warning("실행할 테스트케이스가 없습니다. 테스트케이스 관리 탭에서 먼저 추가해 주세요.")
    elif running:
        st.info(f"등록된 전체 {len(cases)}건을 실행 중입니다. 아래에서 진행 상태를 확인하거나 실행을 중단할 수 있습니다.")
    else:
        st.caption(f"현재 등록된 전체 {len(cases)}건을 한 번에 실행합니다. 외부 AI API 호출 수와 비용은 모델 응답·재시도에 따라 달라질 수 있습니다.")
    confirm_run = _required_api_confirmation(
        "ai_run_confirm",
        "전체 테스트케이스 실행 범위와 외부 API 비용 발생 가능성을 확인했습니다.",
    )
    if st.button("전체 테스트케이스 실행", type="primary", disabled=not cases or not confirm_run or running):
        _launch_process("ai_batch_process", [sys.executable, "-u", "-m", "allstar.ai_agent.evaluation.quality_pipeline"], "dashboard_ai_batch")
        st.rerun()
    _render_process("ai_batch_process", "AI 에이전트 전체 테스트케이스")


def render_ai_testcases() -> None:
    _section("AI 에이전트 테스트케이스", "기존 포트폴리오의 관리·전체 실행·품질 분석 기능을 유지합니다.")
    tab_manage, tab_run, tab_batch, tab_breakdown, tab_detail = st.tabs(
        ["테스트케이스 관리", "테스트케이스 실행", "배치 품질 현황", "유형별 비교", "케이스 상세"]
    )
    with tab_manage:
        _render_ai_case_management()
    with tab_run:
        _render_ai_case_execution()
    df = _read_csv(AI_BATCH_REPORT)
    with tab_batch:
        if df is None or df.empty:
            st.info("아직 배치 품질 보고서가 없습니다.")
        else:
            _render_decision_metrics(df, item_column="case_id", item_label="테스트케이스")
            st.caption("테스트케이스 한 건마다 서버 연결 방식(API)과 규칙 기반 평가가 각각 한 건씩 기록됩니다.")
            _render_grouped_quality_chart(
                df,
                group_column="case_id",
                label_column="case_id",
                item_label="테스트케이스",
                model_column="model_type",
                key="ai_batch_quality",
            )
    with tab_breakdown:
        _render_score_breakdown(df, key="ai_batch_breakdown")
        if df is not None and not df.empty:
            scored = df[df["overall_decision"] != "N/A"]
            if not scored.empty:
                rates = scored.groupby(["model_type", "test_type"])["overall_decision"].apply(lambda values: round((values == "PASS").mean() * 100, 1)).reset_index(name="통과율")
                st.plotly_chart(px.bar(rates, x="test_type", y="통과율", color="model_type", barmode="group", range_y=[0, 100]), width="stretch")
    with tab_detail:
        _render_quality_detail(df, key="ai_batch_detail")


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
        st.warning("A~D 테스트케이스 실행 중이므로 테스트케이스 추가·수정·삭제를 잠갔습니다.")
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


def _scroll_to_voc_run_bottom(run_id: str) -> None:
    """새 VOC 실행 영역이 생긴 직후 화면을 해당 영역의 맨 아래로 한 번 이동한다."""
    safe_run_id = re.sub(r"[^a-zA-Z0-9_-]", "_", run_id)
    anchor_id = f"voc-run-bottom-{safe_run_id}"
    st.markdown(f"<div id='{anchor_id}'></div>", unsafe_allow_html=True)
    components.html(
        f"""
        <script>
        (() => {{
            const move = (behavior) => {{
                const parentDocument = window.parent.document;
                const target = parentDocument.getElementById({json.dumps(anchor_id)});
                if (!target) return;
                const scroller = target.closest('[data-testid="stMain"]') || parentDocument.scrollingElement;
                if (scroller && typeof scroller.scrollTo === "function") {{
                    scroller.scrollTo({{top: scroller.scrollHeight, behavior}});
                }} else {{
                    target.scrollIntoView({{behavior, block: "end"}});
                }}
            }};
            window.requestAnimationFrame(() => move("smooth"));
            window.setTimeout(() => move("smooth"), 300);
            window.setTimeout(() => move("auto"), 750);
        }})();
        </script>
        """,
        height=0,
    )


@st.fragment(run_every=1.0)
def _render_voc_real_test(cases: list[dict]) -> None:
    total = len(cases)
    ai_targets = sum(bool(case.get("judge_enabled", False)) for case in cases)
    st.markdown(
        f"<div class='scope-box'><b>전체 실행 범위</b><br>등록된 전체 {total}건 · 실제 AI 평가 대상 {ai_targets}건 · "
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
            status_label = ""
            status_state = ""
            if active_profile == profile["profile_id"] and running:
                card_state = " profile-running"
                status_label = "실행 중"
                status_state = "running"
            elif active_profile == profile["profile_id"] and completed_pending:
                card_state = " profile-completed"
                status_label = "완료 확인 대기"
                status_state = "completed"
            status_slot = (
                f"<div class='profile-status-slot'><span class='profile-status-badge profile-status-{status_state}'>{status_label}</span></div>"
                if status_label
                else "<div class='profile-status-slot is-empty' aria-hidden='true'></div>"
            )
            st.markdown(
                f"<div class='profile-card-stack'>{status_slot}<div class='profile-card profile-execution-card{card_state}'>"
                f"<div class='profile-title'>{profile['profile_id']} · {html.escape(profile['title'])}</div>"
                f"<div class='profile-summary'>{html.escape(profile['summary'])}</div><hr>"
                f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}<br>"
                f"독립 평가: {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}</div></div></div>",
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
                st.session_state.voc_scroll_to_run_id = run_id
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

    if st.session_state.get("voc_scroll_to_run_id") == run_id:
        _scroll_to_voc_run_bottom(run_id)
        st.session_state.pop("voc_scroll_to_run_id", None)


def render_voc_testcases() -> None:
    _section("VOC 테스트케이스", "테스트케이스를 관리하고 A~D 프로필별 전체 테스트케이스를 실행합니다.")
    tab_manage, tab_test = st.tabs(["테스트케이스 관리", "테스트케이스 실행"])
    with tab_manage:
        cases = _render_voc_case_management()
    with tab_test:
        document = _read_json(VOC_CASES_PATH, {"cases": []})
        _render_voc_real_test(list(document.get("cases", [])))

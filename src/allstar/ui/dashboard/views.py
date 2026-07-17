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

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from allstar.shared.model_profiles import public_profiles
from allstar.shared.paths import (
    AI_AGENT_LOG_ROOT,
    AI_AGENT_REPORT_ROOT,
    PROJECT_ROOT,
    REPORT_ROOT,
    VOC_LOG_ROOT,
    VOC_REPORT_ROOT,
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
PROCESS_LOG_ROOT = PROJECT_ROOT / "_OUTPUT" / "logs" / "services" / "launcher"

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


def _render_dataframe(df: pd.DataFrame, height: int = 330) -> None:
    st.dataframe(df, width="stretch", height=height, hide_index=True)


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


def _launch_process(state_key: str, command: list[str], log_prefix: str) -> None:
    PROCESS_LOG_ROOT.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_path = PROCESS_LOG_ROOT / f"{log_prefix}_{run_id}.log"
    stream = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        stdout=stream,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    stream.close()
    st.session_state[state_key] = {"process": process, "log_path": str(log_path), "started_at": time.time(), "run_id": run_id}


def _render_process(state_key: str, label: str) -> tuple[bool, str]:
    state = st.session_state.get(state_key)
    if not state:
        return False, ""
    process: subprocess.Popen = state["process"]
    log_path = Path(state["log_path"])
    output = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else ""
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


def _render_stage_explorer(status: dict, key_prefix: str) -> None:
    states = _status_stage_states(status)
    details = _status_stage_details(status)
    symbols = {"pending": "○", "running": "◔", "done": "✓", "failed": "!", "skipped": "－"}
    state_labels = {"pending": "대기", "running": "처리 중", "done": "완료", "failed": "실패", "skipped": "건너뜀"}
    selected_key = f"{key_prefix}_selected_stage"
    st.session_state.setdefault(selected_key, 0)
    for start, end in ((0, 4), (4, 7)):
        columns = st.columns(end - start)
        for index, column in zip(range(start, end), columns):
            english, korean = STAGES[index]
            state = states[index]
            if column.button(
                f"{symbols[state]} {index + 1}. {korean}\n({english})\n{state_labels[state]}",
                key=f"{key_prefix}_stage_{index}",
                disabled=state in {"pending", "running"},
                width="stretch",
            ):
                st.session_state[selected_key] = index
    selected = st.session_state[selected_key]
    english, korean = STAGES[selected]
    st.markdown(f"#### {selected + 1}단계 · {korean} ({english})")
    value = details[selected]
    if isinstance(value, (dict, list)):
        st.json(value)
    else:
        st.markdown(f"<div class='stage-detail'>{html.escape(str(value)).replace(chr(10), '<br>')}</div>", unsafe_allow_html=True)


def render_ai_chat() -> None:
    _section("AI 에이전트 챗봇", "기존 포트폴리오의 실시간 대화·로그·품질 분석 기능을 통합한 화면입니다.")
    tab_chat, tab_log, tab_quality, tab_breakdown, tab_detail = st.tabs(
        ["챗봇과 대화", "대화 로그", "품질 현황", "유형별 비교", "대화별 채점 상세"]
    )
    with tab_chat:
        history = st.session_state.setdefault("ai_chat_history", [])
        for message in history:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                if message.get("label"):
                    st.caption(message["label"])
        question = st.chat_input("AI 에이전트에게 질문하세요", key="ai_chat_input")
        if question:
            history.append({"role": "user", "content": question})
            try:
                with st.spinner("답변을 생성하고 있습니다..."):
                    with httpx.Client(timeout=TIMEOUT) as client:
                        response = client.post(f"{PORTFOLIO_API}/chat", json={"question": question})
                        response.raise_for_status()
                        body = response.json()
                history.append({"role": "assistant", "content": body.get("answer", "응답이 없습니다."), "label": "서버 연결 방식(API)"})
                if body.get("rule_answer"):
                    history.append({"role": "assistant", "content": body["rule_answer"], "label": "규칙 기반"})
            except Exception as error:
                history.append({"role": "assistant", "content": f"AI 에이전트 서버 연결 실패: {error}"})
            st.rerun()

    conversations = _read_jsonl(AI_CONVERSATIONS)
    judgments = _read_jsonl(AI_JUDGMENTS)
    live_df = _read_csv(AI_LIVE_REPORT)
    with tab_log:
        if conversations.empty:
            st.info("아직 저장된 대화 로그가 없습니다.")
        else:
            _render_dataframe(conversations.sort_values("timestamp", ascending=False))
        if not judgments.empty:
            st.caption("백그라운드 독립 품질 평가 로그")
            _render_dataframe(judgments.sort_values("timestamp", ascending=False))
    with tab_quality:
        if live_df is None or live_df.empty:
            st.info("아직 자동 생성된 AI 에이전트 챗봇 품질 보고서가 없습니다.")
        else:
            _render_decision_metrics(live_df)
            chart = px.bar(
                live_df,
                x="timestamp" if "timestamp" in live_df else live_df.index,
                y="total_score",
                color="overall_decision",
                color_discrete_map=DECISION_COLORS,
                hover_data=[column for column in ("question", "summary") if column in live_df],
            )
            st.plotly_chart(chart, width="stretch")
    with tab_breakdown:
        _render_score_breakdown(live_df, model_column="model")
    with tab_detail:
        _render_quality_detail(live_df)


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

    question = st.chat_input("VOC 관련 단발 질문을 입력하세요", key="voc_chat_input", disabled=bool(pending))
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
                st.iframe(url, height=880)
            else:
                st.warning("운영 상태 화면(Grafana)이 중지되어 있습니다. AllStar 서버 관리에서 Grafana를 먼저 시작하세요.")


def _render_markdown_report(title: str, path: Path, description: str) -> None:
    st.caption(description)
    if not path.exists():
        st.info("아직 생성된 보고서가 없습니다. 해당 챗봇 또는 시험을 실행하면 자동으로 갱신됩니다.")
        return
    st.markdown(path.read_text(encoding="utf-8"), unsafe_allow_html=True)
    assets = path.parent / "assets"
    if assets.exists():
        images = sorted(assets.glob("*.png"))
        if images:
            st.markdown("### 보고서 그래프")
            for image in images:
                st.image(str(image), width="stretch")


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
        profile_tabs = st.tabs(["A", "B", "C", "D", "종합 비교"])
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
    view = df.copy()
    if "overall_decision" in view:
        decisions = ["전체", *sorted(view["overall_decision"].dropna().unique().tolist())]
        selected = st.selectbox("판정 필터", decisions)
        if selected != "전체":
            view = view[view["overall_decision"] == selected]
    _render_dataframe(view, height=520)


def _render_ai_case_management() -> None:
    cases = _read_json(AI_CASES_PATH, [])
    _section("현재 테스트케이스")
    _render_dataframe(pd.DataFrame(cases)) if cases else st.info("등록된 테스트케이스가 없습니다.")
    with st.expander("새 테스트케이스 추가", expanded=False):
        with st.form("ai_case_add", clear_on_submit=True):
            columns = st.columns(3)
            case_id = columns[0].text_input("테스트케이스 ID", value=_next_case_id(cases, 3))
            category = columns[1].text_input("카테고리")
            test_type = columns[2].selectbox("시험 유형", ["Happy", "Edge", "Negative"])
            question = st.text_input("사용자 질문")
            keyword = st.text_input("기대 키워드")
            policy = st.text_input("기대 정책")
            submitted = st.form_submit_button("테스트케이스 저장", type="primary")
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
        if st.button("선택 삭제", disabled=not (delete_ids and confirm), key="ai_delete_button"):
            _write_json(AI_CASES_PATH, [case for case in cases if case["case_id"] not in delete_ids])
            st.rerun()
    st.divider()
    st.markdown(f"<div class='scope-box'><b>전체 실행 범위</b><br>현재 등록된 {len(cases)}건 전체를 규칙 기반과 서버 연결 방식(API)으로 비교합니다.</div>", unsafe_allow_html=True)
    confirm_run = st.checkbox("전체 테스트케이스 실행과 외부 API 비용 발생 가능성을 확인했습니다.", key="ai_run_confirm")
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


def _render_voc_case_management() -> list[dict]:
    document = _read_json(VOC_CASES_PATH, {"description": "", "cases": []})
    cases = list(document.get("cases", []))
    _section("현재 VOC 테스트케이스")
    if cases:
        columns = ["case_id", "category", "judge_enabled", "judge_mode", "question"]
        _render_dataframe(pd.DataFrame(cases)[columns], height=430)
    else:
        st.info("등록된 VOC 테스트케이스가 없습니다.")
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
            submitted = st.form_submit_button("VOC 테스트케이스 저장", type="primary")
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
        if st.button("선택 삭제", disabled=not (delete_ids and confirm), key="voc_delete_button"):
            _write_json(VOC_CASES_PATH, {**document, "cases": [case for case in cases if case["case_id"] not in delete_ids]})
            st.rerun()
    return cases


def _latest_voc_judge_log(profile: str) -> dict | None:
    root = VOC_LOG_ROOT / "testcase" / profile.lower()
    paths = sorted(root.glob("*/llm_judge_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
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


def _render_voc_real_test(cases: list[dict]) -> None:
    total = len(cases)
    ai_targets = sum(bool(case.get("judge_enabled", False)) for case in cases)
    st.markdown(
        f"<div class='scope-box'><b>GUI 전체 실행 범위</b><br>등록된 전체 {total}건 · 실제 AI 평가 대상 {ai_targets}건 · "
        f"장애 재현 전용 {total - ai_targets}건<br>기본 외부 AI 호출 예상 최대 {ai_targets * 7}회이며 API 재시도 시 증가할 수 있습니다.</div>",
        unsafe_allow_html=True,
    )
    st.caption("A·B·C·D 중 하나를 누르면 해당 프로필로 등록된 전체 테스트케이스를 실행합니다. 한 번에 하나만 실행할 수 있습니다.")
    confirmed = st.checkbox("전체 테스트케이스 실행 범위와 외부 API 비용 발생 가능성을 확인했습니다.", key="voc_all_confirm")
    running = bool(st.session_state.get("voc_profile_process"))
    profiles = public_profiles()
    columns = st.columns(4)
    for column, profile in zip(columns, profiles):
        generation, judge = profile["generation"], profile["judge"]
        with column:
            st.markdown(
                f"<div class='profile-card'><div class='profile-title'>{profile['profile_id']} · {html.escape(profile['title'])}</div>"
                f"<div class='profile-summary'>{html.escape(profile['summary'])}</div><hr>"
                f"<div class='profile-model'>답변 생성: {generation['provider']} / {generation['model']} / {reasoning_text(generation['reasoning'])}<br>"
                f"독립 평가: {judge['provider']} / {judge['model']} / {reasoning_text(judge['reasoning'])}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"{profile['profile_id']} 전체 테스트 실행", key=f"run_profile_{profile['profile_id']}", type="primary", disabled=running or not confirmed or not cases, width="stretch"):
                _launch_process(
                    "voc_profile_process",
                    [sys.executable, "-u", str(PROJECT_ROOT / "tools" / "scripts" / "run_voc_profile.py"), "--profile", profile["profile_id"]],
                    f"dashboard_voc_{profile['profile_id'].lower()}",
                )
                st.session_state.voc_running_profile = profile["profile_id"]
                st.rerun()
    profile = st.session_state.get("voc_running_profile", "A")
    _render_process("voc_profile_process", f"VOC 프로필 {profile} 전체 테스트케이스")
    log = _latest_voc_judge_log(profile)
    if log:
        counts = log.get("case_counts", {})
        st.progress(min(100, int(counts.get("processed", 0) / max(counts.get("total_defined", total), 1) * 100)))
        st.caption(f"처리 {counts.get('processed', 0)} / {counts.get('total_defined', total)} · 채점 {counts.get('scored', 0)} · N/A {counts.get('na', 0)}")
        rows = log.get("case_results", [])
        if rows:
            selected_id = st.selectbox("단계별 결과를 볼 테스트케이스", [row.get("case_id") for row in rows], key="voc_result_case")
            row = next(row for row in rows if row.get("case_id") == selected_id)
            _render_stage_explorer(_batch_status_from_row(row, profile), f"voc_batch_{profile}_{selected_id}")


def render_voc_testcases() -> None:
    _section("VOC 테스트케이스", "테스트케이스를 관리하고 A~D 프로필별 전체 실 테스트를 실행합니다.")
    tab_manage, tab_test = st.tabs(["테스트케이스 관리", "실 테스트"])
    with tab_manage:
        cases = _render_voc_case_management()
    with tab_test:
        document = _read_json(VOC_CASES_PATH, {"cases": []})
        _render_voc_real_test(list(document.get("cases", [])))

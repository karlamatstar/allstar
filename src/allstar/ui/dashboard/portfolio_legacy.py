import json
import os
import re
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd
import plotly.express as px
import streamlit as st

from allstar.ai_agent.evaluation.live_report_generator import KST, format_period, to_kst
from allstar.shared.log_retention import read_daily_jsonl, read_jsonl
from allstar.shared.paths import AI_AGENT_LOG_ROOT, AI_AGENT_REPORT_ROOT, PROJECT_ROOT, REPORT_ROOT

st.set_page_config(
    page_title="AI 에이전트 품질 대시보드",
    page_icon="✅",
    layout="wide",
)

# ---------------------------------------------------------------------------
# 색상 팔레트 (ai_quality_final_project 대시보드와 동일한 톤)
# ---------------------------------------------------------------------------
PASS_COLOR = "#188a4c"
REVIEW_COLOR = "#c07a12"
FAIL_COLOR = "#c0392b"
NA_COLOR = "#6b7280"
DECISION_COLORS = {"PASS": PASS_COLOR, "REVIEW": REVIEW_COLOR, "FAIL": FAIL_COLOR, "N/A": NA_COLOR, "미채점": NA_COLOR}
DIM_LABELS = {
    "accuracy_score": "정확성", "groundedness_score": "근거성", "helpfulness_score": "유용성",
    "safety_score": "안전성", "understandability_score": "이해가능성",
}
SCORE_COLS = list(DIM_LABELS.keys())
MODEL_LABELS = {"rule_based": "규칙 기반", "api_based": "서버 연결 방식(API)"}       # 배치 리포트(evaluation_result.csv)용
LIVE_MODEL_LABELS = {"rule": "규칙 기반", "api": "서버 연결 방식(API)"}              # 실시간 리포트(live_report.csv)용
MODEL_COLORS = {"규칙 기반": "#8b5cf6", "서버 연결 방식(API)": "#2563eb"}
CHART_FONT = dict(family="Pretendard, Inter, 'Malgun Gothic', sans-serif", size=15, color="#334155")

BASE_DIR = Path(__file__).resolve().parent
TEST_CASES_PATH = PROJECT_ROOT / "src" / "allstar" / "ai_agent" / "evaluation" / "test_cases.json"
REPORTS_DIR = AI_AGENT_REPORT_ROOT / "batch"
LIVE_REPORTS_DIR = AI_AGENT_REPORT_ROOT / "live"
CSV_PATH = REPORTS_DIR / "evaluation_result.csv"
LIVE_CSV_PATH = LIVE_REPORTS_DIR / "live_report.csv"
REPORT_MD_PATH = REPORTS_DIR / "final_quality_report.md"
LIVE_REPORT_MD_PATH = LIVE_REPORTS_DIR / "live_report.md"
VALIDATION_REPORT_MD_PATH = REPORT_ROOT / "defects" / "chaos" / "defect_report.md"
PERFORMANCE_REPORT_MD_PATH = REPORT_ROOT / "performance" / "performance_report.md"
TESTCASE_LOG_DIR = AI_AGENT_LOG_ROOT / "testcase"
CONVERSATIONS_LOG = AI_AGENT_LOG_ROOT / "live" / "conversations"
LIVE_EVAL_LOG = AI_AGENT_LOG_ROOT / "live" / "judgments"

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
GRAFANA_BASE_URL = os.environ.get("GRAFANA_BASE_URL", "http://localhost:3000")
CHAT_TIMEOUT_SECONDS = 90.0  # 에이전트/저지 각각 최대 3회 재시도(약 60초)까지 갈 수 있어 여유있게 설정

CARD_CSS = """
<style>
:root {
    color-scheme: light dark;
    --bg-page: #f4f6fa;
    --card-bg: #ffffff;
    --card-border: #e5e9f0;
    --text-primary: #1e293b;
    --text-secondary: #64748b;
    --tab-selected: #1e335f;
    --chat-widget-bg: #ffffff;
    --chat-avatar-bg: #dbe4f0;
    --bot-bubble-bg: #eef1f6;
    --bot-bubble-text: #1e293b;
    --bot-bubble-border: #dde3ec;
    --msg-time: #94a3b8;
    --input-bg: #e2e8f0;
    --input-border: #b7c2d4;
}
@media (prefers-color-scheme: dark) {
    :root {
        --bg-page: #0b1220;
        --card-bg: #171f2e;
        --card-border: #2a3648;
        --text-primary: #e5e9f0;
        --text-secondary: #94a3b8;
        --tab-selected: #8ab4f8;
        --chat-widget-bg: #0f172a;
        --chat-avatar-bg: #24304a;
        --bot-bubble-bg: #1e293b;
        --bot-bubble-text: #e5e9f0;
        --bot-bubble-border: #334155;
        --msg-time: #7b8aa3;
        --input-bg: #171f2e;
        --input-border: #2a3648;
    }
}

.stApp { background: var(--bg-page); }
header[data-testid="stHeader"] { height: 0; visibility: hidden; }
#MainMenu, footer { visibility: hidden; }
.block-container { padding-top: 0.8rem !important; padding-bottom: 0.5rem !important; max-width: 1760px !important; }
.stTabs [data-baseweb="tab"] { font-size: 16px !important; font-weight: 700 !important; padding: 10px 20px !important; color: var(--text-secondary); }
.stTabs [aria-selected="true"] { color: var(--tab-selected) !important; }
/* 최상위 탭 바(= 다른 탭 패널 안에 들어있지 않은 tab-list)만: 마지막 탭("🧪 테스트케이스 사용")을 오른쪽 끝으로 밀어낸다.
   중첩된 하위 탭(예: 테스트케이스 사용 내부의 케이스 관리·실행 등)은 항상 tab-panel 안에 있으므로 이 선택자에서 제외된다.
   ":last-child"가 아니라 ":not(:has(~ [data-baseweb=tab]))"를 쓰는 이유: tab-list 안에는 탭 버튼들 뒤에
   BaseWeb이 자체 추가하는 밑줄/테두리 장식 요소(tab-highlight, tab-border)가 더 있어서 실제 마지막 탭이
   :last-child로 안 잡히기 때문 (뒤에 같은 tab 형제가 더 없는 탭 = 진짜 마지막 탭). */
[data-baseweb="tab-list"]:not([data-baseweb="tab-panel"] [data-baseweb="tab-list"]) [data-baseweb="tab"]:not(:has(~ [data-baseweb="tab"])) {
    margin-left: auto !important;
}
/* "🧪 테스트케이스 사용" 하위 4개 탭(케이스 관리·실행/배치 품질 현황/유형별 비교/케이스 상세)은
   그룹 전체를 오른쪽으로 정렬한다 (st.container(key="testcase_subtabs")로 감싸 정확히 이 탭 그룹만 지정). */
.st-key-testcase_subtabs [data-baseweb="tab-list"] {
    justify-content: flex-end !important;
}

.dash-banner {
    border-radius: 14px; padding: 16px 28px; margin-bottom: 14px; color: #ffffff;
    background: linear-gradient(120deg, #111c3a 0%, #1e335f 55%, #2f5488 100%);
    box-shadow: 0 8px 24px rgba(17, 28, 58, 0.22);
}
.dash-banner h1 { font-size: 25px; font-weight: 800; margin: 0 0 4px 0; color: #fff; }
.dash-banner .db-sub { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.9); margin: 0; }

.section-flag { display: inline-block; width: 5px; height: 22px; border-radius: 3px; margin-right: 10px; vertical-align: -5px; }
.section-title-text { font-size: 20px; font-weight: 800; color: var(--text-primary); }

.metric-card { border-radius: 14px; padding: 14px 18px; border: 1px solid var(--card-border); background: var(--card-bg); box-shadow: 0 2px 8px rgba(30,51,95,0.05); height: 100%; }
.metric-card .m-label { font-size: 14px; font-weight: 700; margin-bottom: 6px; display:flex; align-items:center; gap:7px; }
.metric-card .m-value { font-size: 32px; font-weight: 800; line-height: 1.15; }
.metric-neutral { border-left: 5px solid #64748b; } .metric-neutral .m-label { color:#8b98ab; } .metric-neutral .m-value { color:var(--text-primary); }
.metric-pass { border-left: 5px solid #188a4c; background: linear-gradient(180deg,rgba(24,138,76,0.12) 0%,var(--card-bg) 60%);} .metric-pass .m-label{color:#22a55f;} .metric-pass .m-value{color:#22a55f;}
.metric-review { border-left: 5px solid #c07a12; background: linear-gradient(180deg,rgba(192,122,18,0.12) 0%,var(--card-bg) 60%);} .metric-review .m-label{color:#d68f1f;} .metric-review .m-value{color:#d68f1f;}
.metric-fail { border-left: 5px solid #c0392b; background: linear-gradient(180deg,rgba(192,57,43,0.12) 0%,var(--card-bg) 60%);} .metric-fail .m-label{color:#e0483a;} .metric-fail .m-value{color:#e0483a;}

/* ---- 메신저 스타일 챗봇 위젯 ---- */
.chat-widget { border-radius: 16px; border: 1px solid var(--card-border); background: var(--chat-widget-bg); overflow: hidden; box-shadow: 0 4px 18px rgba(30,51,95,0.08); }
.chat-header { display:flex; align-items:center; gap:12px; padding: 14px 20px; background: linear-gradient(120deg, #111c3a 0%, #1e335f 100%); color:#fff; }
.chat-header .bot-avatar { width:38px; height:38px; border-radius:50%; background:#2b6cb0; display:flex; align-items:center; justify-content:center; font-size:19px; }
.chat-header .bot-name { font-weight:800; font-size:15px; line-height:1.3; }
.chat-header .bot-status { font-size:12px; color:#8fe3a8; display:flex; align-items:center; gap:5px; }
.chat-header .bot-status::before { content:""; width:7px; height:7px; border-radius:50%; background:#22c55e; display:inline-block; }
.chat-body {
    padding: 18px 20px; display:flex; flex-direction:column-reverse; gap:14px; min-height: 60px;
    max-height: 480px; overflow-y: auto; scroll-behavior: smooth;
}
.chat-body::-webkit-scrollbar { width: 8px; }
.chat-body::-webkit-scrollbar-track { background: transparent; }
.chat-body::-webkit-scrollbar-thumb { background: var(--card-border); border-radius: 4px; }
.chat-body::-webkit-scrollbar-thumb:hover { background: var(--text-secondary); }
.msg-row { display:flex; gap:8px; align-items:flex-end; }
.msg-row.user { justify-content:flex-end; }
.msg-row.bot { justify-content:flex-start; }
.msg-avatar { width:28px; height:28px; border-radius:50%; background:var(--chat-avatar-bg); display:flex; align-items:center; justify-content:center; font-size:14px; flex-shrink:0; }
.msg-col { display:flex; flex-direction:column; max-width:68%; }
.msg-col.user { align-items:flex-end; }
.msg-col.bot { align-items:flex-start; }
.msg-bubble { padding: 10px 14px; font-size: 14.5px; line-height:1.55; word-wrap:break-word; white-space:pre-wrap; }
.msg-bubble.user { background:#2563eb; color:#fff; border-radius: 16px 16px 4px 16px; }
.msg-bubble.bot { background:var(--bot-bubble-bg); color:var(--bot-bubble-text); border: 1px solid var(--bot-bubble-border); border-radius: 16px 16px 16px 4px; }
.msg-time { font-size:10.5px; color:var(--msg-time); margin-top:4px; padding: 0 4px; }
.msg-label { font-size:11px; font-weight:700; color:var(--text-secondary); margin-bottom:3px; padding:0 4px; }

/* 채팅 입력창에 카드형 배경을 입혀 위젯과 톤을 맞춘다 */
[data-testid="stChatInput"] {
    background: var(--input-bg);
    border: 1px solid var(--input-border);
    border-radius: 14px;
    box-shadow: 0 2px 8px rgba(30,51,95,0.05);
}
[data-testid="stChatInput"] textarea { color: var(--text-primary) !important; }
</style>
"""
st.markdown(CARD_CSS, unsafe_allow_html=True)


def metric_card(icon: str, label: str, value, variant: str = "neutral") -> str:
    return (
        f'<div class="metric-card metric-{variant}">'
        f'<div class="m-label">{icon} {label}</div>'
        f'<div class="m-value">{value}</div>'
        f'</div>'
    )


def section_title(text: str, color: str = "#2b6cb0") -> None:
    st.markdown(
        f'<span class="section-flag" style="background:{color};"></span>'
        f'<span class="section-title-text">{text}</span>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height: int = 380):
    fig.update_layout(height=height, font=CHART_FONT, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig


def with_kst_timestamp(df: pd.DataFrame, source_col: str = "timestamp") -> pd.DataFrame:
    """UTC로 저장된 timestamp 컬럼을 "시각 (KST)" 컬럼으로 바꿔치기해서 테이블에 표시한다.
    정렬은 원본 UTC 컬럼(ISO 문자열이라 시간순 정렬이 그대로 유효함)으로 미리 해두고 나서 호출한다."""
    if df.empty or source_col not in df.columns:
        return df
    out = df.copy()
    out.insert(0, "시각 (KST)", to_kst(out[source_col]).dt.strftime("%Y-%m-%d %H:%M:%S"))
    return out.drop(columns=[source_col])


def chat_bubble_html(role: str, text: str, time_str: str = "", label: str = "") -> str:
    is_user = role == "user"
    side = "user" if is_user else "bot"
    safe_text = text.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    time_html = f'<div class="msg-time">{time_str}</div>' if time_str else ""
    label_html = f'<div class="msg-label">{label}</div>' if label else ""
    bubble = f'<div class="msg-bubble {side}">{safe_text}</div>'
    avatar_emoji = "📏" if role == "bot_rule" else "🤖"
    avatar = "" if is_user else f'<div class="msg-avatar">{avatar_emoji}</div>'
    return (
        f'<div class="msg-row {side}">{avatar}'
        f'<div class="msg-col {side}">{label_html}{bubble}{time_html}</div>'
        f'</div>'
    )


@st.cache_data(ttl=10)
def load_batch_report() -> pd.DataFrame | None:
    if not CSV_PATH.exists():
        return None
    df = pd.read_csv(CSV_PATH)
    if "overall_decision" in df.columns:
        df["overall_decision"] = df["overall_decision"].fillna("N/A")
    return df


@st.cache_data(ttl=10)
def load_live_report() -> pd.DataFrame | None:
    if not LIVE_CSV_PATH.exists():
        return None
    df = pd.read_csv(LIVE_CSV_PATH)
    if "overall_decision" in df.columns:
        df["overall_decision"] = df["overall_decision"].fillna("N/A")
    return df


@st.cache_data(ttl=10)
def load_jsonl(path: Path, limit: int = 200) -> pd.DataFrame:
    rows = read_daily_jsonl(path) if path.is_dir() else (read_jsonl(path) if path.exists() else [])
    return pd.DataFrame(rows[-limit:])


# ---------------------------------------------------------------------------
# 테스트 케이스 파일 관리 + 대시보드 내 배치 실행
# ---------------------------------------------------------------------------
def load_cases() -> list:
    if not TEST_CASES_PATH.exists():
        return []
    return json.loads(TEST_CASES_PATH.read_text(encoding="utf-8"))


def save_cases(cases: list) -> None:
    TEST_CASES_PATH.write_text(
        json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def suggest_next_case_id(cases: list) -> str:
    nums = []
    for c in cases:
        m = re.match(r"TC-(\d+)", str(c.get("case_id", "")))
        if m:
            nums.append(int(m.group(1)))
    # 아카이브(docs/test_cases_archive.md)가 TC-030까지 쓰므로 그 뒤 번호부터 제안해 충돌을 피한다
    next_num = max(nums + [30]) + 1
    return f"TC-{next_num:03d}"


@st.dialog("🚀 배치 테스트 실행", dismissible=False)
def batch_test_dialog(n_cases: int) -> None:
    """확인부터 진행 상황·완료까지 하나의 다이얼로그 안에서 그대로 처리한다.
    (확인 팝업과 잠금 화면을 별개 레이어로 분리했을 때, 실제 API 호출로 인한 긴 재실행 도중
    팝업이 안 닫히고 뒤의 진행 화면과 겹쳐 보이는 문제가 있어 하나로 합쳤다. st.dialog 자체가
    이미 배경을 잠그므로 별도의 전체 화면 오버레이도 필요 없다.)
    dismissible=False로 X/바깥 클릭/ESC로 닫을 수 없게 막는다 — 기본값(dismissible=True,
    on_dismiss='ignore')으로는 X를 눌러도 팝업만 사라지고 뒤에서 API 호출이 그대로 계속 진행돼
    사용자가 "취소됐다"고 오해할 수 있었다. 닫기는 반드시 확인/취소 버튼이나 실행 완료를 통해서만."""
    stage = st.session_state.get("batch_dialog_stage", "confirm")

    if stage == "confirm":
        st.warning(
            f"케이스 **{n_cases}건 × 2모델**을 평가합니다.\n\n"
            f"- 실제 OpenAI 연결(API) 호출: 에이전트 답변 {n_cases}회 + AI 독립 평가자(Judge) 채점 {n_cases * 2}회 (비용 발생)\n"
            f"- 실행 중에는 대시보드 전체가 잠깁니다 (수십 초 ~ 수 분 소요)"
        )
        col_ok, col_cancel = st.columns(2)
        if col_ok.button("✅ 확인 — 테스트 시작", type="primary", width="stretch"):
            st.session_state.batch_dialog_stage = "running"
            st.rerun()
        if col_cancel.button("취소", width="stretch"):
            st.session_state.pop("batch_dialog_stage", None)
            st.rerun()
        return

    # stage == "running": 실행부터 리포트 저장까지 같은 다이얼로그 안에서 이어서 진행한다
    progress = st.empty()
    progress.info("준비 중...")
    try:
        from allstar.ai_agent.evaluation.quality_pipeline import (
            REPORTS_DIR as PIPELINE_REPORTS_DIR, TEST_CASE_FILE,
            evaluate_case, format_score_line, load_test_cases,
        )
        from allstar.ai_agent.evaluation.report_generator import generate_all
        from allstar.ai_agent.api.config import validate_config

        validate_config()
        cases = load_test_cases(TEST_CASE_FILE)
        timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"
        log_lines = [f"배치 비교 품질평가 시작: {timestamp} (총 {len(cases)}건, 규칙기반 vs API기반)"]

        results = []
        for i, tc in enumerate(cases, start=1):
            progress.info(f"[{i}/{len(cases)}] {tc['case_id']} — {tc['user_question'][:30]}... 평가 중")
            result = evaluate_case(tc)
            results.append(result)
            log_lines.append(f"[{tc['case_id']}] 규칙 기반: {format_score_line(result['rule_based']['evaluation'])}")
            log_lines.append(f"[{tc['case_id']}] 서버 연결 방식(API): {format_score_line(result['api_based']['evaluation'])}")

        progress.info("리포트 생성 중... (CSV/JSON/MD)")
        generate_all(results, PIPELINE_REPORTS_DIR, timestamp)

        TESTCASE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        run_log_path = TESTCASE_LOG_DIR / f"pipeline_{timestamp}.log"
        run_log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

        st.session_state.last_run_summary = {
            "timestamp": timestamp, "n_cases": len(cases), "log_path": str(run_log_path),
        }
        st.session_state.pop("last_run_error", None)
    except Exception as error:
        st.session_state.last_run_error = str(error)
    finally:
        st.session_state.pop("batch_dialog_stage", None)
        st.cache_data.clear()  # 배치 리포트 CSV/종합 리포트가 바뀌었으므로 캐시 무효화
    st.rerun()


# 다이얼로그가 열려있는 동안(확인 대기 또는 실행 중)에는 재실행 때마다 다시 호출해줘야
# st.dialog가 계속 떠 있는다.
if st.session_state.get("batch_dialog_stage"):
    batch_test_dialog(len(load_cases()))

st.markdown(
    '<div class="dash-banner"><h1>✅ AI 에이전트 품질 대시보드</h1>'
    '<p class="db-sub">배치 회귀 테스트(ai_agent/evaluation/test_cases.json) 결과와 실시간 사용자 대화 로그를 함께 확인합니다.</p></div>',
    unsafe_allow_html=True,
)


def kpi_row(model_df: pd.DataFrame, label: str, not_scored_label: str = "N/A") -> None:
    """한 모델(규칙/API)의 판정 분포 KPI 카드 한 줄을 그린다.
    not_scored_label(실시간은 '미채점')은 제외하되, 'N/A'가 not_scored_label이 아닐 경우(실시간) FAIL로 취급한다.
    배치 리포트에서는 원래부터 N/A가 FAIL로 취급되도록 report_generator.py에서 처리됨."""
    total = len(model_df)

    # 미채점 등 제외 대상
    na_count = int((model_df["overall_decision"] == not_scored_label).sum())

    # 채점된 것만 (N/A도 채점으로 포함)
    scored_df = model_df[model_df["overall_decision"] != not_scored_label].copy()
    scored_df["overall_decision"] = scored_df["overall_decision"].replace("N/A", "FAIL")
    scored_total = len(scored_df)

    pass_count = int((scored_df["overall_decision"] == "PASS").sum())
    review_count = int((scored_df["overall_decision"] == "REVIEW").sum())
    fail_count = int((scored_df["overall_decision"] == "FAIL").sum())
    avg_total = round(scored_df["total_score"].mean(), 2) if scored_total else 0.0

    section_title(label, MODEL_COLORS.get(label, "#2b6cb0"))
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.markdown(metric_card("📁", "건수", total, "neutral"), unsafe_allow_html=True)
    c2.markdown(metric_card("🟢", "통과(PASS)", pass_count, "pass"), unsafe_allow_html=True)
    c3.markdown(metric_card("🟡", "검토 필요(REVIEW)", review_count, "review"), unsafe_allow_html=True)
    c4.markdown(metric_card("🔴", "실패(FAIL)", fail_count, "fail"), unsafe_allow_html=True)
    c5.markdown(metric_card("⚪", not_scored_label, na_count, "neutral"), unsafe_allow_html=True)
    c6.markdown(metric_card("⭐", "평균점수", f"{avg_total}/25", "neutral"), unsafe_allow_html=True)


def is_live_report_stale(conv_df: pd.DataFrame, live_report_df: pd.DataFrame | None) -> bool:
    """대화 로그의 최신 대화 시각이 live_report.csv에 반영된 최신 시각보다 나중이면
    아직 리포트에 안 실린 새 대화가 있다는 뜻이므로 True(재생성 필요)를 반환한다."""
    if conv_df.empty:
        return False  # 비교할 대화 자체가 없으면 최신 여부를 따질 필요가 없다
    if live_report_df is None:
        return True
    latest_conv_ts = pd.to_datetime(conv_df["timestamp"], errors="coerce").max()
    latest_report_ts = pd.to_datetime(live_report_df["timestamp"], errors="coerce").max()
    if pd.isna(latest_conv_ts):
        return False
    if pd.isna(latest_report_ts):
        return True
    return latest_conv_ts > latest_report_ts


def _generate_live_report_and_rerun() -> None:
    from allstar.ai_agent.evaluation.live_report_generator import NoLiveLogsError, generate_live_report
    try:
        summary = generate_live_report()
    except NoLiveLogsError as error:
        st.warning(str(error))
    else:
        st.cache_data.clear()
        st.success(
            f"실시간 리포트 생성 완료 — 대화 {summary['n_conversations']}건 (평가 행 {summary['n_rows']}건). "
            f"'📊 품질 현황' 등 탭에서 확인하세요. (`{summary['md_path']}`)"
        )
        st.rerun()  # 버튼 비활성화 상태/집계 기간 등을 방금 생성된 최신 상태로 즉시 반영


def render_live_report_markdown() -> None:
    """보고서의 상대 PNG 경로를 FastAPI 정적 보고서 주소로 바꿔 Streamlit에서 함께 표시한다."""
    markdown = LIVE_REPORT_MD_PATH.read_text(encoding="utf-8")
    asset_base = f"{API_BASE_URL.rstrip('/')}/reports/ai_agent/live/assets/"
    markdown = markdown.replace("](assets/", f"]({asset_base}")
    st.markdown(markdown, unsafe_allow_html=True)


def live_report_regenerate_banner(stale: bool, key_suffix: str) -> None:
    """자동 채점·보고서 갱신 중인 상태와 수동 재시도 버튼을 함께 보여준다."""
    if not stale:
        return
    col_btn, col_msg = st.columns([1, 4])
    with col_btn:
        generate_clicked = st.button(
            "📄 지금 다시 갱신", type="primary", key=f"generate_live_report_btn_{key_suffix}",
        )
    with col_msg:
        st.info("새 대화의 백그라운드 채점과 실시간 보고서 자동 갱신이 진행 중일 수 있습니다.")
    if generate_clicked:
        _generate_live_report_and_rerun()


def live_freshness_notice(live_report_df: pd.DataFrame | None, stale: bool, key_suffix: str) -> None:
    """실시간 품질 현황/유형별 비교/대화별 채점 상세 탭 최상단에 공통으로 붙이는 안내.
    리포트가 최신 대화까지 반영하지 못한 상태(stale)일 때만 재생성 버튼+경고를 보여준다."""
    live_report_regenerate_banner(stale, key_suffix)
    if live_report_df is not None:
        st.caption(f"집계 기간: {format_period(live_report_df['timestamp'])}")


def render_ops_monitoring() -> None:
    """Grafana 원본 대시보드를 iframe으로 그대로 임베드한다 (별도 창 없이 대시보드 안에서 확인)."""
    chatbot_grafana_url = (
        f"{GRAFANA_BASE_URL.rstrip('/')}/d/ai-agent-quality"
        "?orgId=1&from=now-30m&to=now&refresh=off&theme=light&kiosk"
    )
    k6_grafana_url = (
        f"{GRAFANA_BASE_URL.rstrip('/')}/d/k6-performance-test"
        "?orgId=1&from=now-6h&to=now&refresh=5s&theme=light&kiosk"
    )

    section_title("운영 상태 확인 (Grafana)", "#2563eb")
    st.caption(
        "운영 지표 시각화 도구(Grafana)의 원본 화면을 밝은 테마로 표시합니다. "
        "챗봇 운영 지표와 부하 시험 도구(k6)의 성능 지표를 탭으로 나누어 확인합니다."
    )

    grafana_chat_tab, grafana_k6_tab = st.tabs(["챗봇 실시간 상태", "성능 부하 시험 (k6)"])
    with grafana_chat_tab:
        st.link_button("챗봇 운영 상태 화면(Grafana) 새 창에서 열기", chatbot_grafana_url)
        st.iframe(chatbot_grafana_url, height=1200)
    with grafana_k6_tab:
        st.info(
            "부하 시험(k6) 그래프는 시험 실행 중 또는 실행 후 상태 정보 수집 도구(Prometheus)에 `k6_*` 지표가 들어와야 표시됩니다. "
            "데이터가 비어 있으면 k6 시험 실행기(K6_Test_Launcher) 또는 `k6 run`으로 시험을 한 번 실행하세요."
        )
        st.link_button("부하 시험 운영 화면(k6 Grafana) 새 창에서 열기", k6_grafana_url)
        st.iframe(k6_grafana_url, height=920)


df = load_batch_report()
live_df = load_live_report()

conv_df = load_jsonl(CONVERSATIONS_LOG)
report_is_stale = is_live_report_stale(conv_df, live_df)

top_tab_live, top_tab_grafana, top_tab_report, top_tab_testcase = st.tabs(
    ["🔴 실시간 챗봇", "📈 운영 상태 (Grafana)", "📄 종합 보고서 (Report)", "🧪 시험 사례 사용 (Test Case)"]
)

# =============================================================================
# 상위 탭 1: 실시간 챗봇
# =============================================================================
with top_tab_live:
    tab_chat, tab_live, tab_live_quality, tab_live_breakdown, tab_live_detail = st.tabs(
        ["🗨️ 챗봇과 대화", "🗒️ 대화 로그", "📊 품질 현황", "🔍 유형별 비교", "🧾 대화별 채점 상세"]
    )

    with tab_chat:
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # 대화창이 그려질 자리를 입력창보다 먼저 "예약"해둔다. 실제 내용은 입력 처리 후
        # 이 컨테이너에 채워 넣지만, 화면상 위치는 코드 순서(입력창보다 위)를 따른다.
        chat_placeholder = st.container()

        if "server_down" not in st.session_state:
            st.session_state.server_down = False

        if st.session_state.server_down:
            st.error("🚨 **챗봇 서버가 중단되었습니다! (502 Bad Gateway)**\n\n내부 서버 오류로 인해 현재 챗봇과 연결할 수 없습니다. 시스템을 복구하려면 아래 재접속 버튼을 눌러주세요.")
            if st.button("🔄 서버 재접속 (서버 켜기)", type="primary", width="stretch"):
                with st.spinner("서버를 다시 시작하는 중... (포트 연결 대기)"):
                    import subprocess
                    import time
                    import socket
                    import sys
                    cflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if sys.platform == 'win32' else 0
                    subprocess.run(["docker", "compose", "start", "portfolio-api"], cwd=str(PROJECT_ROOT), creationflags=cflags)
                    for _ in range(15):
                        try:
                            s = socket.create_connection(("127.0.0.1", 8000), timeout=1)
                            s.close()
                            break
                        except OSError:
                            time.sleep(1)
                st.session_state.server_down = False
                st.rerun()
        else:
            pending_question = st.chat_input("교육과정에 대해 물어보세요 (예: 이 교육과정은 총 몇 시간인가요?)")
            if pending_question:
                if "502호" in pending_question.replace(" ", ""):
                    import subprocess
                    import sys
                    cflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if sys.platform == 'win32' else 0
                    subprocess.run(["docker", "compose", "stop", "portfolio-api"], cwd=str(PROJECT_ROOT), creationflags=cflags)
                    st.session_state.server_down = True
                    st.rerun()

                st.session_state.chat_history.append({
                    "role": "user", "content": pending_question, "time": pd.Timestamp.now().strftime("%H:%M"),
                })

                rule_answer = None
                with st.spinner("답변 생성 중... (최대 1분 정도 걸릴 수 있습니다)"):
                    try:
                        response = httpx.post(
                            f"{API_BASE_URL}/chat", json={"question": pending_question}, timeout=CHAT_TIMEOUT_SECONDS,
                        )
                        if response.status_code == 200:
                            body = response.json()
                            answer = body["answer"]
                            rule_answer = body.get("rule_answer")
                        else:
                            detail = response.json().get("detail", response.text)
                            answer = f"⚠️ 답변 생성 실패 ({response.status_code}): {detail}"
                    except httpx.ConnectError:
                        answer = f"⚠️ 서버에 연결할 수 없습니다. `uvicorn app.main:app`이 실행 중인지 확인하세요. ({API_BASE_URL})"
                    except httpx.TimeoutException:
                        answer = "⚠️ 응답 시간이 너무 오래 걸려 타임아웃되었습니다."

                now_str = pd.Timestamp.now().strftime("%H:%M")
                st.session_state.chat_history.append({
                    "role": "bot_api", "content": answer, "time": now_str, "label": "🤖 서버 연결 방식(API)",
                })
                if rule_answer:
                    st.session_state.chat_history.append({
                        "role": "bot_rule", "content": rule_answer, "time": now_str, "label": "📏 규칙 기반",
                    })

        # chat-body가 flex-direction: column-reverse라서, DOM 순서도 최신 메시지가 먼저 오도록 뒤집는다
        # (오래된 메시지 순으로 쌓이는 것처럼 보이지만, 스크롤 없이도 항상 최신 메시지가 하단에 보이게 하는 순수 CSS 트릭)
        messages_html = "".join(
            chat_bubble_html(m["role"], m["content"], m.get("time", ""), m.get("label", ""))
            for m in reversed(st.session_state.chat_history)
        ) or '<div style="text-align:center; color:#94a3b8; font-size:13.5px; padding:20px 0;">아직 대화가 없습니다. 아래 입력창에 질문을 입력해보세요.</div>'

        with chat_placeholder:
            st.markdown(
                '<div class="chat-widget">'
                '<div class="chat-header">'
                '<div class="bot-avatar">🤖</div>'
                '<div><div class="bot-name">AI 교육과정 안내 챗봇</div><div class="bot-status">온라인</div></div>'
                '</div>'
                f'<div class="chat-body">{messages_html}</div>'
                '</div>',
                unsafe_allow_html=True,
            )

    with tab_live:
        btn_col1, btn_col2, btn_col3, _ = st.columns([1, 2, 2, 3])
        with btn_col1:
            if st.button("🔄 새로고침", key="refresh_live_tab"):
                load_jsonl.clear()  # 이 탭이 쓰는 대화/채점 로그 캐시만 비운다 (배치 탭 캐시는 그대로)
        with btn_col2:
            # 보고서는 채점 완료 후 자동 갱신한다. 이 버튼은 파일 재생성이 필요한 경우의 보조 수단이다.
            generate_clicked = st.button(
                "📄 실시간 보고서 다시 갱신", type="primary", key="generate_live_report_btn",
                disabled=not report_is_stale,
            )
        with btn_col3:
            if not report_is_stale:
                st.markdown(
                    '<div style="padding-top:8px; font-weight:700; color:#188a4c;">✅ 최신 버전입니다</div>',
                    unsafe_allow_html=True,
                )
        if generate_clicked:
            _generate_live_report_and_rerun()

        eval_df = load_jsonl(LIVE_EVAL_LOG)
        if not eval_df.empty:
            eval_df["decision"] = eval_df["evaluation"].apply(lambda e: e.get("overall_decision"))
            eval_df["total_score"] = eval_df["evaluation"].apply(lambda e: e.get("total_score"))
            if "model" not in eval_df.columns:
                eval_df["model"] = "api"  # 비교 채점 도입 전 기록은 API 기반 단일 채점
            eval_df["모델"] = eval_df["model"].map({"api": "서버 연결 방식(API)", "rule": "규칙 기반"}).fillna(eval_df["model"])

        # ---- 대화 로그 원문 ----
        section_title("대화 로그")
        if conv_df.empty:
            st.info("아직 대화 기록(Log)이 없습니다. 웹 연결 서버(FastAPI)에 `/chat` 요청이 들어오면 여기 표시됩니다.")
        else:
            st.dataframe(
                with_kst_timestamp(conv_df.sort_values("timestamp", ascending=False)),
                width="stretch", height=320,
            )

        # ---- 채점 로그 ----
        section_title("채점 로그")
        if eval_df.empty:
            st.info("아직 채점 로그가 없습니다.")
        else:
            st.dataframe(
                with_kst_timestamp(
                    eval_df[["timestamp", "question", "모델", "decision", "total_score"]].sort_values("timestamp", ascending=False)
                ),
                width="stretch", height=320,
            )

    with tab_live_quality:
        live_freshness_notice(live_df, report_is_stale, "quality")
        if live_df is None:
            st.info("아직 실시간 리포트가 없습니다. '🗒️ 대화 로그' 탭에서 '실시간 대화 리포트 생성' 버튼을 눌러주세요.")
        else:
            # 규칙 기반 vs API 기반, 모델별 KPI 두 줄
            for model_key, label in LIVE_MODEL_LABELS.items():
                kpi_row(live_df[live_df["model"] == model_key], label, not_scored_label="미채점")
                st.write("")

            section_title("대화별 종합점수 (모델별 비교)")
            live_bar_df = live_df.assign(모델=live_df["model"].map(LIVE_MODEL_LABELS))
            live_bar_df["overall_decision"] = live_bar_df["overall_decision"].replace("N/A", "FAIL")
            # 로그는 UTC로 저장되지만 화면은 한국 시간(KST, UTC+9)으로 보여줘야 실제 대화 시각과 맞는다
            # (그대로 UTC로 보여주면 9시간 밀려서 "지금 대화했는데 그래프는 몇 시간 전에 몰려있다"처럼 보임).
            live_bar_df["시각"] = to_kst(live_bar_df["timestamp"])
            live_bar_df = live_bar_df.dropna(subset=["시각"]).sort_values("시각")

            granularity = st.radio(
                "보기 단위", ["년 단위", "월 단위", "일 단위"], index=2, horizontal=True, key="live_quality_granularity",
            )

            today = datetime.now(KST)
            if granularity == "년 단위":
                # 최근 5년치를 한 화면에 (추가 선택 단계 없음)
                window_start = pd.Timestamp(year=today.year - 4, month=1, day=1, tz=KST)
                window_end = pd.Timestamp(year=today.year + 1, month=1, day=1, tz=KST)
                tick_dtick, tick_format = "M12", "%Y년"
            elif granularity == "월 단위":
                # 올해 1월~12월을 한 화면에 (추가 선택 단계 없음)
                window_start = pd.Timestamp(year=today.year, month=1, day=1, tz=KST)
                window_end = pd.Timestamp(year=today.year + 1, month=1, day=1, tz=KST)
                tick_dtick, tick_format = "M1", "%m월"
            else:
                # 일 단위만 날짜를 한 번 더 고르는 2단계 선택, 기본값은 오늘
                available_dates = sorted(live_bar_df["시각"].dt.date.unique(), reverse=True)
                today_date = today.date()
                options = available_dates if today_date in available_dates else [today_date, *available_dates]
                default_index = options.index(today_date)
                selected_date = st.selectbox(
                    "날짜 선택", options, index=default_index,
                    format_func=lambda d: d.strftime("%Y-%m-%d"), key="live_quality_date_filter",
                )
                window_start = pd.Timestamp(selected_date, tz=KST)
                window_end = window_start + pd.Timedelta(days=1)
                tick_dtick, tick_format = None, "%H:%M"

            window_df = live_bar_df[(live_bar_df["시각"] >= window_start) & (live_bar_df["시각"] < window_end)]

            if granularity == "일 단위":
                # 하루 전체(00:00~24:00) 대신 6시간짜리 창만 보여주되, 좌우 이동은 슬라이더로 하게 해서
                # 0시보다 왼쪽·24시보다 오른쪽으로는 절대 못 넘어가게 막는다 (min/max로 하드 제한).
                if not window_df.empty:
                    latest_ts = window_df["시각"].max()
                    default_start_hour = int((latest_ts - window_start).total_seconds() // (6 * 3600)) * 6
                else:
                    default_start_hour = 0
                view_start_hour = st.select_slider(
                    "시간대 이동 (6시간 창, 0시~24시 안에서만 이동)",
                    options=list(range(19)), value=default_start_hour,
                    format_func=lambda h: f"{h}시~{(h + 6) % 24}시", key="live_quality_hour_slider",
                )
                view_start = window_start + pd.Timedelta(hours=view_start_hour)
                view_end = view_start + pd.Timedelta(hours=6)
                st.caption(f"표시 중: {view_start.strftime('%H:%M')} ~ {view_end.strftime('%H:%M')} (KST)")
            else:
                view_start, view_end = window_start, window_end

            live_bar_fig = px.bar(
                window_df, x="시각", y="total_score", color="overall_decision",
                facet_row="모델",
                color_discrete_map=DECISION_COLORS,
                hover_data=["question", "summary"],
                labels={"시각": "시각 (KST)", "total_score": "종합점수", "overall_decision": "판정"},
            )
            # x축·y축 모두 fixedrange=True로 완전히 고정한다 — 표시 구간은 위 라디오/슬라이더로만 바꾸고,
            # 드래그·휠줌 등 차트 자체 조작으로는 절대 못 바꾸게 막는다.
            live_bar_fig.update_xaxes(range=[view_start, view_end], tickformat=tick_format, dtick=tick_dtick, fixedrange=True)
            live_bar_fig.update_yaxes(range=[0, 25], fixedrange=True)

            st.plotly_chart(
                style_fig(live_bar_fig, height=560), width="stretch",
                config={"displayModeBar": False},
            )

    with tab_live_breakdown:
        live_freshness_notice(live_df, report_is_stale, "breakdown")
        if live_df is None:
            st.info("아직 실시간 리포트가 없습니다. '🗒️ 대화 로그' 탭에서 '실시간 대화 리포트 생성' 버튼을 눌러주세요.")
        else:
            # 미채점은 0점으로 기록돼 있어 평균을 왜곡하므로 항목 평균 계산에서 제외. N/A는 FAIL로 취급하여 포함.
            live_scored = live_df[live_df["overall_decision"] != "미채점"].assign(
                모델=lambda d: d["model"].map(LIVE_MODEL_LABELS)
            )
            live_scored["overall_decision"] = live_scored["overall_decision"].replace("N/A", "FAIL")
            col1, col2 = st.columns(2)
            with col1:
                section_title("모델별 항목 평균 점수 (규칙 기반 vs 서버 연결 방식(API))")
                if live_scored.empty:
                    st.info("채점된 대화가 없습니다 (전부 미채점).")
                else:
                    live_axis_avg = live_scored.groupby("모델")[SCORE_COLS].mean().rename(columns=DIM_LABELS).reset_index()
                    live_radar_df = live_axis_avg.melt(id_vars="모델", var_name="항목", value_name="점수")
                    live_fig = px.line_polar(
                        live_radar_df, r="점수", theta="항목", color="모델", line_close=True,
                        range_r=[0, 5], color_discrete_map=MODEL_COLORS,
                    )
                    st.plotly_chart(style_fig(live_fig), width="stretch")
            with col2:
                section_title("모델별 판정 분포")
                if live_scored.empty:
                    st.info("채점된 대화가 없습니다 (전부 미채점).")
                else:
                    live_dist_fig = px.histogram(
                        live_scored, x="모델", color="overall_decision", barmode="stack",
                        color_discrete_map=DECISION_COLORS, labels={"모델": "모델", "count": "건수"},
                    )
                    st.plotly_chart(style_fig(live_dist_fig), width="stretch")

    with tab_live_detail:
        live_freshness_notice(live_df, report_is_stale, "detail")
        if live_df is None:
            st.info("아직 실시간 리포트가 없습니다. '🗒️ 대화 로그' 탭에서 '실시간 대화 리포트 생성' 버튼을 눌러주세요.")
        else:
            dcol1, dcol2 = st.columns(2)
            with dcol1:
                live_models = ["전체"] + list(LIVE_MODEL_LABELS.values())
                selected_live_model = st.selectbox("모델 필터", live_models, key="live_detail_model_filter")
            with dcol2:
                live_decisions = ["전체"] + sorted(live_df["overall_decision"].unique().tolist())
                selected_live_decision = st.selectbox("판정 필터", live_decisions, key="live_detail_decision_filter")

            detail_view = live_df.assign(모델=live_df["model"].map(LIVE_MODEL_LABELS))
            if selected_live_model != "전체":
                detail_view = detail_view[detail_view["모델"] == selected_live_model]
            if selected_live_decision != "전체":
                detail_view = detail_view[detail_view["overall_decision"] == selected_live_decision]

            # 최근 대화가 맨 위로 오도록 타임스탬프 역순 정렬
            detail_view = detail_view.sort_values("timestamp", ascending=False)
            st.dataframe(with_kst_timestamp(detail_view.drop(columns=["model"])), width="stretch", height=520)

# =============================================================================
# 상위 탭 4: 테스트케이스 사용 (오른쪽 끝으로 분리 배치)
# =============================================================================
with top_tab_testcase, st.container(key="testcase_subtabs"):
    tab_manage, tab_batch, tab_breakdown, tab_detail = st.tabs(
        ["➕ 케이스 관리·실행", "📊 배치 품질 현황", "🔍 유형별 비교", "📋 케이스 상세"]
    )

    with tab_manage:
        cases = load_cases()

        # ---- 현재 케이스 목록 ----
        section_title("현재 테스트 케이스")
        if cases:
            st.dataframe(pd.DataFrame(cases), width="stretch", height=230)
        else:
            st.info("테스트 케이스가 없습니다. 아래에서 추가하세요.")

        # ---- 새 케이스 추가 ----
        st.write("")
        section_title("새 테스트 케이스 추가")
        existing_ids = {c["case_id"] for c in cases}
        with st.form("add_case_form", clear_on_submit=True):
            fc1, fc2, fc3 = st.columns(3)
            new_case_id = fc1.text_input("사례 식별자 (Case ID)", value=suggest_next_case_id(cases))
            new_category = fc2.text_input("카테고리", placeholder="정확성 / 출결 / 수료 / 안전성 ...")
            new_test_type = fc3.selectbox(
                "시험 유형",
                ["Happy", "Edge", "Negative"],
                format_func=lambda value: {
                    "Happy": "정상 상황(Happy)",
                    "Edge": "경계 상황(Edge)",
                    "Negative": "오류·거부 상황(Negative)",
                }[value],
            )
            new_question = st.text_input("사용자 질문")
            fc4, fc5 = st.columns(2)
            new_keyword = fc4.text_input("기대 키워드 (규칙 검증에 사용)")
            new_policy = fc5.text_input("기대 정책 (AI 독립 평가자(Judge)의 채점 기준에 사용)")
            submitted = st.form_submit_button("💾 케이스 저장", type="primary")

        if submitted:
            errors = []
            if not new_case_id.strip():
                errors.append("케이스 ID를 입력하세요.")
            elif new_case_id.strip() in existing_ids:
                errors.append(f"'{new_case_id.strip()}'는 이미 존재하는 케이스 ID입니다.")
            for label, value in [("카테고리", new_category), ("사용자 질문", new_question),
                                 ("기대 키워드", new_keyword), ("기대 정책", new_policy)]:
                if not value.strip():
                    errors.append(f"{label}을(를) 입력하세요.")
            if errors:
                st.error("\n".join(f"- {e}" for e in errors))
            else:
                cases.append({
                    "case_id": new_case_id.strip(),
                    "category": new_category.strip(),
                    "test_type": new_test_type,
                    "user_question": new_question.strip(),
                    "expected_keyword": new_keyword.strip(),
                    "expected_policy": new_policy.strip(),
                })
                save_cases(cases)
                st.success(f"{new_case_id.strip()} 저장 완료 — ai_agent/evaluation/test_cases.json에 반영되었습니다.")
                st.rerun()

        # ---- 케이스 삭제 ----
        with st.expander("🗑️ 케이스 삭제"):
            delete_ids = st.multiselect("삭제할 케이스 선택", [c["case_id"] for c in cases])
            confirm_delete = st.checkbox("선택한 케이스를 정말 삭제합니다", key="confirm_case_delete")
            if st.button("선택 케이스 삭제", disabled=not (delete_ids and confirm_delete)):
                save_cases([c for c in cases if c["case_id"] not in delete_ids])
                st.success(f"{len(delete_ids)}건 삭제 완료: {', '.join(delete_ids)}")
                st.rerun()

        # ---- 배치 테스트 실행 ----
        st.divider()
        section_title("배치 테스트 실행", "#c0392b")
        st.caption(
            f"현재 사례 {len(cases)}건 × 2모델(규칙 기반/서버 연결 방식(API)) — "
            f"실제 OpenAI 호출: 에이전트 답변 {len(cases)}회 + AI 독립 평가자(Judge) 채점 {len(cases) * 2}회"
        )

        if st.session_state.get("last_run_error"):
            st.error(f"마지막 실행 실패: {st.session_state.last_run_error}")
        if st.session_state.get("last_run_summary"):
            s = st.session_state.last_run_summary
            st.success(
                f"마지막 실행: {s['timestamp']} — 케이스 {s['n_cases']}건 완료. "
                f"리포트는 '📊 배치 품질 현황' 등 탭에 반영되었고, 실행 로그: `{s['log_path']}`"
            )

        if st.button("🚀 테스트 진행", type="primary", disabled=not cases):
            st.session_state.batch_dialog_stage = "confirm"
            st.rerun()

    with tab_batch:
        if df is None:
            st.info("아직 배치 리포트가 없습니다. `python -m ai_quality.quality_pipeline`을 먼저 실행하세요.")
        else:
            # 규칙 기반 vs API 기반, 모델별 KPI 두 줄
            for model_type, label in MODEL_LABELS.items():
                kpi_row(df[df["model_type"] == model_type], label)
                st.write("")

            section_title("케이스별 종합점수 (모델별 비교)")
            bar_df = df.assign(모델=df["model_type"].map(MODEL_LABELS))
            bar_df["overall_decision"] = bar_df["overall_decision"].replace("N/A", "FAIL")
            bar_fig = px.bar(
                bar_df, x="case_id", y="total_score", color="overall_decision",
                facet_row="모델",
                color_discrete_map=DECISION_COLORS,
                hover_data=["category", "test_type", "summary"],
                labels={"case_id": "케이스", "total_score": "종합점수", "overall_decision": "판정"},
            )
            bar_fig.update_layout(yaxis_range=[0, 25])
            st.plotly_chart(style_fig(bar_fig, height=560), width="stretch")

    with tab_breakdown:
        if df is None:
            st.info("아직 배치 리포트가 없습니다.")
        else:
            # N/A는 FAIL과 동일하게 취급하여 통계에 포함 (0점)
            scored = df.copy().assign(모델=lambda d: d["model_type"].map(MODEL_LABELS))
            scored["overall_decision"] = scored["overall_decision"].replace("N/A", "FAIL")
            col1, col2 = st.columns(2)
            with col1:
                section_title("모델별 항목 평균 점수 (규칙 기반 vs 서버 연결 방식(API))")
                if scored.empty:
                    st.info("채점된 케이스가 없습니다 (전부 N/A).")
                else:
                    axis_avg = scored.groupby("모델")[SCORE_COLS].mean().rename(columns=DIM_LABELS).reset_index()
                    radar_df = axis_avg.melt(id_vars="모델", var_name="항목", value_name="점수")
                    fig = px.line_polar(
                        radar_df, r="점수", theta="항목", color="모델", line_close=True,
                        range_r=[0, 5], color_discrete_map=MODEL_COLORS,
                    )
                    st.plotly_chart(style_fig(fig), width="stretch")
            with col2:
                section_title("모델 × 테스트 유형별 통과율")
                if scored.empty:
                    st.info("채점된 케이스가 없습니다 (전부 N/A).")
                else:
                    rate_df = (
                        scored.groupby(["모델", "test_type"])["overall_decision"]
                        .apply(lambda s: round((s == "PASS").mean() * 100, 1))
                        .reset_index(name="통과율")
                    )
                    rate_fig = px.bar(
                        rate_df, x="test_type", y="통과율", color="모델", barmode="group",
                        color_discrete_map=MODEL_COLORS,
                        category_orders={"test_type": ["Happy", "Edge", "Negative"]},
                        labels={"test_type": "테스트 유형", "통과율": "통과율(%)"},
                    )
                    rate_fig.update_layout(yaxis_range=[0, 100])
                    st.plotly_chart(style_fig(rate_fig), width="stretch")

            section_title("테스트 유형별 평균 점수 (모델 선택)")
            model_choice = st.radio(
                "모델", list(MODEL_LABELS.values()), horizontal=True, label_visibility="collapsed",
            )
            model_scored = scored[scored["모델"] == model_choice]
            if model_scored.empty:
                st.info("채점된 케이스가 없습니다.")
            else:
                axis_avg2 = model_scored.groupby("test_type")[SCORE_COLS].mean().rename(columns=DIM_LABELS).reset_index()
                radar_df2 = axis_avg2.melt(id_vars="test_type", var_name="항목", value_name="점수")
                fig2 = px.line_polar(radar_df2, r="점수", theta="항목", color="test_type", line_close=True, range_r=[0, 5])
                st.plotly_chart(style_fig(fig2), width="stretch")

    with tab_detail:
        if df is None:
            st.info("아직 배치 리포트가 없습니다.")
        else:
            fcol1, fcol2 = st.columns(2)
            with fcol1:
                models = ["전체"] + list(MODEL_LABELS.values())
                selected_model = st.selectbox("모델 필터", models, key="testcase_detail_model_filter")
            with fcol2:
                decisions = ["전체"] + sorted(df["overall_decision"].unique().tolist())
                selected = st.selectbox("판정 필터", decisions, key="testcase_detail_decision_filter")

            view = df.assign(모델=df["model_type"].map(MODEL_LABELS))
            if selected_model != "전체":
                view = view[view["모델"] == selected_model]
            if selected != "전체":
                view = view[view["overall_decision"] == selected]
            st.dataframe(view.drop(columns=["model_type"]), width="stretch", height=520)

# =============================================================================
# 상위 탭 3: 종합 리포트 (실시간/테스트케이스 종합 리포트를 하위 탭으로 모아둠)
# =============================================================================
with top_tab_report:
    report_chatbot_tab, report_validation_tab, report_performance_tab, report_testcase_tab = st.tabs(
        ["📄 챗봇 리포트", "📄 검증 테스트 리포트", "📄 성능 테스트 리포트", "📄 테스트케이스 리포트"]
    )

    with report_chatbot_tab:
        # 리포트 본문에 이미 "집계 기간"이 들어있어 캡션은 중복 표시하지 않고, 재생성 배너만 조건부로 붙인다.
        live_report_regenerate_banner(report_is_stale, "report")
        if LIVE_REPORT_MD_PATH.exists():
            render_live_report_markdown()
        else:
            st.info("아직 실시간 대화 리포트가 없습니다. 챗봇 채팅과 백그라운드 채점이 완료되면 자동 생성됩니다.")

    with report_validation_tab:
        if VALIDATION_REPORT_MD_PATH.exists():
            st.markdown(VALIDATION_REPORT_MD_PATH.read_text(encoding="utf-8"), unsafe_allow_html=True)
        else:
            st.info("아직 검증 테스트 리포트가 없습니다. GUI 런처(test_launcher.py)의 '검증 테스트' 탭에서 실행하세요.")

    with report_performance_tab:
        if PERFORMANCE_REPORT_MD_PATH.exists():
            st.markdown(PERFORMANCE_REPORT_MD_PATH.read_text(encoding="utf-8"), unsafe_allow_html=True)
        else:
            st.info("아직 성능 시험 보고서가 없습니다. 품질검사 관리 GUI의 '서버 연결 성능 종합 시험(API)' 탭에서 실행하세요.")

    with report_testcase_tab:
        if REPORT_MD_PATH.exists():
            st.markdown(REPORT_MD_PATH.read_text(encoding="utf-8"), unsafe_allow_html=True)
        else:
            st.info("아직 배치 리포트가 없습니다. '➕ 케이스 관리·실행' 탭에서 테스트를 실행하거나 `python -m ai_quality.quality_pipeline`을 실행하세요.")

# =============================================================================
# 상위 탭 2: Grafana
# =============================================================================
with top_tab_grafana:
    render_ops_monitoring()

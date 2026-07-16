"""챗봇 실시간 대화 로그와 실시간 채점 로그를 합쳐 최신 실시간 평가 리포트를 만든다.
배치(test_cases.json) 리포트와는 완전히 별개 파일로 저장된다.

- 대화와 채점은 request_id(UUID)로 1:1 매칭 (구버전 로그처럼 request_id가 없으면 질문 텍스트로 보조 매칭)
- OpenAI API를 호출하지 않는다 — 이미 쌓인 로그만 집계하므로 비용 없이 즉시 실행 가능
- 입력: _OUTPUT/logs/ai_agent/live/conversations/ + judgments/
- 출력: _OUTPUT/reports/ai_agent/live/ 최신 Markdown·CSV·PNG
"""
import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from allstar.ai_agent.evaluation.report_generator import (
    AXIS_LABELS_MD, SCORE_COLS_MD, decision_badge,
)
from allstar.ai_agent.evaluation.live_report_charts import generate_live_report_charts
from allstar.shared.paths import AI_AGENT_LOG_ROOT, AI_AGENT_REPORT_ROOT

REPORTS_DIR = AI_AGENT_REPORT_ROOT / "live"
ASSETS_DIR = REPORTS_DIR / "assets"
CONVERSATIONS_LOG = AI_AGENT_LOG_ROOT / "live" / "conversations" / "conversations.jsonl"
LIVE_EVAL_LOG = AI_AGENT_LOG_ROOT / "live" / "judgments" / "live_evaluations.jsonl"
REPORT_GENERATION_LOCK = threading.Lock()

MODEL_LABELS = {"api": "API 기반", "rule": "규칙 기반"}
AXES = ["accuracy", "groundedness", "helpfulness", "safety", "understandability"]
NOT_SCORED = "미채점"  # 백그라운드 채점 대기 중이거나 Judge 호출 실패(N/A)로 채점 기록이 없는 경우

KST = timezone(timedelta(hours=9))  # 로그는 UTC로 저장하지만, 리포트/대시보드 표시는 전부 한국 시간 기준


def to_kst(timestamps: pd.Series) -> pd.Series:
    """UTC로 저장된 timestamp 컬럼(문자열)을 KST(tz-aware datetime)로 변환한다."""
    return pd.to_datetime(timestamps, errors="coerce", utc=True).dt.tz_convert(KST)


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # 다른 채팅 요청이 마지막 JSONL 행을 쓰는 순간 읽은 경우 다음 자동 갱신에서 반영한다.
            continue
    return rows


def build_rows(conversations: list[dict], evaluations: list[dict]) -> list[dict]:
    """대화 1건 × 모델 2종(api/rule)을 행으로 펼치고, request_id로 채점 결과를 붙인다."""
    # request_id → {model: evaluation}, 구버전 로그 보조 매칭용 question → [...]
    eval_by_id: dict[tuple, dict] = {}
    eval_by_question: dict[tuple, dict] = {}
    for ev in evaluations:
        model = ev.get("model", "api")
        if ev.get("request_id"):
            eval_by_id[(ev["request_id"], model)] = ev
        else:
            eval_by_question.setdefault((ev.get("question"), model), ev)

    rows = []
    for conv in conversations:
        request_id = conv.get("request_id")
        answers = {"api": conv.get("answer"), "rule": conv.get("rule_answer")}
        for model, answer in answers.items():
            if answer is None:  # 비교 응답 도입 전 로그에는 rule_answer가 없다
                continue
            ev_entry = eval_by_id.get((request_id, model)) if request_id else None
            if ev_entry is None:
                ev_entry = eval_by_question.get((conv.get("question"), model))
            evaluation = (ev_entry or {}).get("evaluation", {})

            decision = evaluation.get("overall_decision", NOT_SCORED)
            row = {
                "timestamp": conv.get("timestamp"),
                "request_id": request_id,
                "question": conv.get("question"),
                "model": model,
                "ai_answer": answer,
                "latency_ms": conv.get("latency_ms"),
                "total_score": evaluation.get("total_score"),
                "overall_decision": decision,
                "summary": evaluation.get("summary", ""),
            }
            for axis in AXES:
                row[f"{axis}_score"] = evaluation.get(axis, {}).get("score")
            rows.append(row)
    return rows


def _model_stats(g: pd.DataFrame) -> dict:
    """N/A와 미채점을 품질 실패와 분리하고, 실제 채점 결과만 통과율에 반영한다."""
    n = len(g)
    scored = g[g["overall_decision"].isin(["PASS", "REVIEW", "FAIL"])].copy()
    scored_n = len(scored)
    return {
        "n": n,
        "na": int((g["overall_decision"] == "N/A").sum()),
        "not_scored": int((g["overall_decision"] == NOT_SCORED).sum()),
        "pass": int((scored["overall_decision"] == "PASS").sum()),
        "review": int((scored["overall_decision"] == "REVIEW").sum()),
        "fail": int((scored["overall_decision"] == "FAIL").sum()),
        "pass_rate": round((scored["overall_decision"] == "PASS").mean() * 100, 1) if scored_n else 0.0,
        "avg_total": round(scored["total_score"].mean(), 2) if scored_n else 0.0,
        "axis_avg": {c: round(scored[c].mean(), 2) for c in SCORE_COLS_MD} if scored_n else {c: 0.0 for c in SCORE_COLS_MD},
    }


def format_period(timestamps: pd.Series) -> str:
    """타임스탬프 컬럼에서 '년-월-일 / 시-분-초 ~ 년-월-일 / 시-분-초 (KST)' 형태의 집계 기간 문자열을 만든다.
    대시보드(품질 현황·유형별 비교·대화별 채점 상세 탭)와 종합 리포트 양쪽에서 동일하게 사용한다."""
    parsed = to_kst(timestamps).dropna()
    if parsed.empty:
        return "-"
    fmt = "%Y-%m-%d / %H:%M:%S"
    return f"{parsed.min().strftime(fmt)} ~ {parsed.max().strftime(fmt)} (KST)"


def _details(summary: str, body_lines: list[str]) -> list[str]:
    return [
        "<details>",
        f"<summary><strong>{summary}</strong></summary>",
        "",
        *body_lines,
        "",
        "</details>",
        "",
    ]


def save_live_markdown_report(df: pd.DataFrame, file_path: Path) -> None:
    # 원본 timestamp(UTC 문자열)는 정렬용으로 그대로 두고, 화면에 찍을 때만 KST 문자열을 따로 만든다.
    df = df.assign(시각_kst=to_kst(df["timestamp"]).dt.strftime("%Y-%m-%d %H:%M:%S"))

    lines = ["# 챗봇 실시간 대화 품질 리포트", ""]
    lines += [
        "> 배치 테스트케이스 리포트와 별개로, `_OUTPUT/logs/ai_agent/live/`의 실제 사용자 대화와 "
        "실시간 AI Judge 채점 로그만을 집계한 리포트입니다. "
        "시각은 모두 한국 시간(KST) 기준입니다.", "",
    ]

    # ------------------------------------------------------------------
    # 1. 한눈에 보는 품질 현황: 긴 목록보다 표를 먼저 노출한다.
    # ------------------------------------------------------------------
    n_conversations = df.groupby(["timestamp", "question"]).ngroups
    latency = df.drop_duplicates(subset=["timestamp", "question"])["latency_ms"]
    model_stats = {m: _model_stats(g) for m, g in df.groupby("model")}
    lines += [
        "## 1. 한눈에 보는 품질 현황", "",
        f"- 집계 기간: {format_period(df['timestamp'])}",
        f"- 대화 수: **{n_conversations}건** (평가 행 {len(df)}건 = 대화 × 모델 2종)",
        f"- 응답 지연: 평균 **{round(latency.mean(), 1)}ms** · 최대 {round(latency.max(), 1)}ms",
        "",
        "| 모델 | 평가 행 | PASS | REVIEW | FAIL | N/A | 미채점 | 통과율 | 평균 종합점수 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model in ("rule", "api"):
        s = model_stats.get(model)
        if not s:
            continue
        lines.append(
            f"| {MODEL_LABELS[model]} | {s['n']} | {s['pass']} | {s['review']} | {s['fail']} | {s['na']} | {s['not_scored']} | "
            f"{s['pass_rate']}% | {s['avg_total']} / 25 |"
        )
    lines.append("")
    axis_header = " | ".join(AXIS_LABELS_MD[c] for c in SCORE_COLS_MD)
    lines += [f"| 모델 | {axis_header} |", "|---|" + "---:|" * len(SCORE_COLS_MD)]
    for model in ("rule", "api"):
        s = model_stats.get(model)
        if not s:
            continue
        scores = " | ".join(str(s["axis_avg"][c]) for c in SCORE_COLS_MD)
        lines.append(f"| {MODEL_LABELS[model]} | {scores} |")
    lines.append("")

    # ------------------------------------------------------------------
    # 2. 데이터 기반 그래프
    # ------------------------------------------------------------------
    lines += [
        "## 2. 품질·판정·응답시간 그래프", "",
        "![모델별 채점 판정 분포](assets/decision_distribution.png)", "",
        "![모델별 품질 항목 평균 점수](assets/quality_axis_average.png)", "",
        "![대화별 응답시간 추이](assets/response_latency_trend.png)", "",
    ]

    # ------------------------------------------------------------------
    # 3. FAIL / REVIEW / N/A 사례 상세
    # ------------------------------------------------------------------
    problems = df[df["overall_decision"].isin(["FAIL", "REVIEW", "N/A"])].sort_values("timestamp", ascending=False)
    section3 = []
    if problems.empty:
        section3.append("- FAIL/REVIEW/N/A 사례가 없습니다.")
    else:
        for i, (_, row) in enumerate(problems.iterrows(), start=1):
            section3 += [
                f"### 3.{i} {row['시각_kst']} (KST) · {MODEL_LABELS.get(row['model'], row['model'])} · {row['overall_decision']}",
                "",
                f"- 사용자 질문: {row['question']}",
                f"- 답변: {row['ai_answer']}",
                f"- 종합 점수: {row['total_score']} / 25 — {decision_badge(row['overall_decision'])}",
                f"- 평가 의견: {row['summary']}",
                "",
            ]
    lines += ["## 3. 확인이 필요한 채점 결과", ""]
    lines += _details(f"FAIL·REVIEW·N/A 상세 목록 열기 ({len(problems)}건)", section3)

    # ------------------------------------------------------------------
    # 4. 대화 목록 (최근 50건)
    # ------------------------------------------------------------------
    section4 = ["| 시각 (KST) | 모델 | 질문 | 판정 | 총점 |", "|---|---|---|---|---|"]
    recent = df.sort_values("timestamp", ascending=False).head(50)
    for _, row in recent.iterrows():
        question_short = str(row["question"])[:40]
        section4.append(
            f"| {row['시각_kst']} | {MODEL_LABELS.get(row['model'], row['model'])} | {question_short} | "
            f"{decision_badge(row['overall_decision'])} | {row['total_score'] if pd.notna(row['total_score']) else '-'} |"
        )
    lines += ["## 4. 채팅 및 채점 목록", ""]
    lines += _details(f"최근 채팅·채점 목록 열기 ({len(recent)}행, 최대 50행)", section4)

    temporary = file_path.with_name(file_path.name + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(file_path)


class NoLiveLogsError(Exception):
    """대화 로그가 없어 리포트를 만들 수 없을 때 (대시보드에서 안내 메시지용)."""


def generate_live_report(timestamp: str | None = None) -> dict:
    """누적 로그로 최신 실시간 보고서를 만든다. 동시 요청은 한 번에 하나씩 처리한다."""
    with REPORT_GENERATION_LOCK:
        conversations = _read_jsonl(CONVERSATIONS_LOG)
        if not conversations:
            raise NoLiveLogsError("대화 로그(_OUTPUT/logs/ai_agent/live/conversations/)가 비어 있습니다. 먼저 챗봇과 대화하세요.")

        evaluations = _read_jsonl(LIVE_EVAL_LOG)
        rows = build_rows(conversations, evaluations)
        df = pd.DataFrame(rows)

        timestamp = timestamp or f"{datetime.now():%Y%m%d_%H%M%S_%f}"
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)

        latest_csv = REPORTS_DIR / "live_report.csv"
        latest_md = REPORTS_DIR / "live_report.md"
        temporary_csv = latest_csv.with_name(latest_csv.name + ".tmp")
        df.to_csv(temporary_csv, index=False, encoding="utf-8-sig")
        temporary_csv.replace(latest_csv)
        generate_live_report_charts(df, ASSETS_DIR)
        save_live_markdown_report(df, latest_md)

        print(f"  CSV      → {latest_csv} (최신본 갱신)")
        print(f"  Markdown → {latest_md} (최신본 갱신)")

        return {
            "timestamp": timestamp,
            "n_conversations": df.groupby(["timestamp", "question"]).ngroups if not df.empty else 0,
            "n_rows": len(df),
            "csv_path": str(latest_csv),
            "md_path": str(latest_md),
            "chart_paths": [str(path) for path in sorted(ASSETS_DIR.glob("*.png"))],
        }


if __name__ == "__main__":
    try:
        generate_live_report()
    except NoLiveLogsError as error:
        raise SystemExit(str(error))
    print("\n실시간 대화 리포트를 생성했습니다. (OpenAI API 호출 없음)")

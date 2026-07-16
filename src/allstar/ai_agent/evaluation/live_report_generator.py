"""챗봇 실시간 대화 로그와 실시간 채점 로그를 합쳐 별도의 실시간 평가 리포트를 만든다.
배치(test_cases.json) 리포트와는 완전히 별개 파일로 저장된다.

- 대화와 채점은 request_id(UUID)로 1:1 매칭 (구버전 로그처럼 request_id가 없으면 질문 텍스트로 보조 매칭)
- OpenAI API를 호출하지 않는다 — 이미 쌓인 로그만 집계하므로 비용 없이 즉시 실행 가능
- 입력: _OUTPUT/logs/ai_agent/live/conversations/ + judgments/
- 출력: _OUTPUT/reports/ai_agent/live/history/ + 최신본
"""
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from allstar.ai_agent.evaluation.report_generator import (
    AXIS_LABELS_MD, SCORE_COLS_MD, decision_badge, wrap_details,
)
from allstar.shared.paths import AI_AGENT_LOG_ROOT, AI_AGENT_REPORT_ROOT

REPORTS_DIR = AI_AGENT_REPORT_ROOT / "live"
HISTORY_DIR = REPORTS_DIR / "history"
CONVERSATIONS_LOG = AI_AGENT_LOG_ROOT / "live" / "conversations" / "conversations.jsonl"
LIVE_EVAL_LOG = AI_AGENT_LOG_ROOT / "live" / "judgments" / "live_evaluations.jsonl"

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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


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
    """N/A는 FAIL로 취급하여 통과율 분모에 포함. 미채점만 제외."""
    n = len(g)
    scored = g[g["overall_decision"] != NOT_SCORED].copy()
    scored["overall_decision"] = scored["overall_decision"].replace("N/A", "FAIL")
    scored_n = len(scored)
    return {
        "n": n,
        "not_scored": n - scored_n,
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
    # 1. 개요
    # ------------------------------------------------------------------
    n_conversations = df.groupby(["timestamp", "question"]).ngroups
    latency = df.drop_duplicates(subset=["timestamp", "question"])["latency_ms"]
    lines += [
        "## 1. 개요", "",
        f"- 집계 기간: {format_period(df['timestamp'])}",
        f"- 대화 수: **{n_conversations}건** (평가 행 {len(df)}건 = 대화 × 모델 2종)",
        f"- 응답 지연: 평균 **{round(latency.mean(), 1)}ms** · 최대 {round(latency.max(), 1)}ms",
        "",
    ]

    # ------------------------------------------------------------------
    # 2. 모델별 판정 요약
    # ------------------------------------------------------------------
    model_stats = {m: _model_stats(g) for m, g in df.groupby("model")}
    section2 = ["| 모델 | 평가 행 | PASS | REVIEW | FAIL | 미채점 | 통과율 | 평균 종합점수 |", "|---|---|---|---|---|---|---|---|"]
    for model in ("rule", "api"):
        s = model_stats.get(model)
        if not s:
            continue
        section2.append(
            f"| {MODEL_LABELS[model]} | {s['n']} | {s['pass']} | {s['review']} | {s['fail']} | {s['not_scored']} | "
            f"{s['pass_rate']}% | {s['avg_total']} / 25 |"
        )
    section2.append("")
    axis_header = " | ".join(AXIS_LABELS_MD[c] for c in SCORE_COLS_MD)
    section2 += [f"| 모델 | {axis_header} |", "|---|" + "---|" * len(SCORE_COLS_MD)]
    for model in ("rule", "api"):
        s = model_stats.get(model)
        if not s:
            continue
        scores = " | ".join(str(s["axis_avg"][c]) for c in SCORE_COLS_MD)
        section2.append(f"| {MODEL_LABELS[model]} | {scores} |")
    lines += ["## 2. 모델별 판정 요약", ""]
    lines += wrap_details(section2)

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
    lines += ["## 3. FAIL / REVIEW / N/A 사례 상세", ""]
    lines += wrap_details(section3)

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
    lines += ["## 4. 대화 목록 (최근 50건)", ""]
    lines += wrap_details(section4)

    file_path.write_text("\n".join(lines), encoding="utf-8")


class NoLiveLogsError(Exception):
    """대화 로그가 없어 리포트를 만들 수 없을 때 (대시보드에서 안내 메시지용)."""


def generate_live_report(timestamp: str | None = None) -> dict:
    """실시간 대화 리포트를 생성한다. 반환값은 대시보드 표시용 요약 정보."""
    conversations = _read_jsonl(CONVERSATIONS_LOG)
    if not conversations:
        raise NoLiveLogsError("대화 로그(_OUTPUT/logs/ai_agent/live/conversations/)가 비어 있습니다. 먼저 챗봇과 대화하세요.")

    evaluations = _read_jsonl(LIVE_EVAL_LOG)
    rows = build_rows(conversations, evaluations)
    df = pd.DataFrame(rows)

    timestamp = timestamp or f"{datetime.now():%Y%m%d_%H%M%S}"
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    ts_csv = HISTORY_DIR / f"{timestamp}_live_report.csv"
    ts_md = HISTORY_DIR / f"{timestamp}_live_report.md"
    df.to_csv(ts_csv, index=False, encoding="utf-8-sig")
    save_live_markdown_report(df, ts_md)

    latest_csv = REPORTS_DIR / "live_report.csv"
    latest_md = REPORTS_DIR / "live_report.md"
    shutil.copy2(ts_csv, latest_csv)
    shutil.copy2(ts_md, latest_md)
    print(f"  CSV      → {ts_csv} (최신본 → {latest_csv})")
    print(f"  Markdown → {ts_md} (최신본 → {latest_md})")

    return {
        "timestamp": timestamp,
        "n_conversations": df.groupby(["timestamp", "question"]).ngroups if not df.empty else 0,
        "n_rows": len(df),
        "csv_path": str(latest_csv),
        "md_path": str(latest_md),
    }


if __name__ == "__main__":
    try:
        generate_live_report()
    except NoLiveLogsError as error:
        raise SystemExit(str(error))
    print("\n실시간 대화 리포트를 생성했습니다. (OpenAI API 호출 없음)")

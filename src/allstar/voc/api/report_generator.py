"""실시간 VOC 대화 로그만 사용해 Markdown 리포트와 manifest를 생성한다."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from allstar.shared.model_profiles import public_profiles
from allstar.shared.paths import MANIFEST_ROOT, PROJECT_ROOT, VOC_LOG_ROOT, VOC_REPORT_ROOT
from allstar.voc.api.judge import RUBRIC_VERSION
from allstar.voc.api.validation import is_valid_question_text
from allstar.voc.evaluation.runtime_support import load_json


ROOT = PROJECT_ROOT
LOG_DIR = VOC_LOG_ROOT / "live" / "conversations"
REPORT_DIR = VOC_REPORT_ROOT / "live"
MANIFEST_DIR = MANIFEST_ROOT
RUBRIC = load_json("judge_rubric.json")


def _records() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    sources: list[str] = []
    for path in sorted(LOG_DIR.glob("*.jsonl")):
        sources.append(str(path.relative_to(ROOT)))
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows, sources


def generate_live_report() -> dict:
    rows, sources = _records()
    valid_rows = [row for row in rows if is_valid_question_text(row.get("question"))]
    invalid_rows = [row for row in rows if not is_valid_question_text(row.get("question"))]
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    history = REPORT_DIR / "history"
    latest = REPORT_DIR / "latest"
    history.mkdir(exist_ok=True)
    latest.mkdir(exist_ok=True)

    lines = [
        "# VOC 실시간 대화 품질 리포트",
        "",
        f"> 생성 시각: {datetime.now().astimezone().isoformat(timespec='seconds')}",
        f"> 유효 질문: {len(valid_rows)}건",
        f"> 입력 손상 제외: {len(invalid_rows)}건",
        f"> 정상 100점 채점: {sum((row.get('judge') or {}).get('rubric_version') == RUBRIC_VERSION for row in valid_rows)}건",
        "",
        "## A~D 모델 프로필",
        "",
        "A~D는 질문 1건에 적용되는 답변 생성 모델과 독립 품질 평가 모델의 조합이다.",
        "",
        "| 프로필 | 의미 | 생성 모델 | 평가 모델 |",
        "|---|---|---|---|",
    ]
    for profile in public_profiles():
        generation = profile["generation"]
        judge = profile["judge"]
        lines.append(
            f"| {profile['profile_id']} | {profile['summary']} | "
            f"{generation['provider']} / {generation['model']} / {generation['reasoning']} | "
            f"{judge['provider']} / {judge['model']} / {judge['reasoning']} |"
        )

    lines.extend([
        "",
        "## 독립 품질평가 기준",
        "",
        "실시간 VOC 챗봇과 VOC 테스트케이스는 같은 9항목·100점 루브릭을 사용한다.",
        "",
        "| 평가 항목 | 최대 점수 |",
        "|---|---:|",
    ])
    for criterion in RUBRIC["criteria"]:
        lines.append(f"| {criterion['name']} | {criterion['max_score']} |")

    lines.extend(["", "## 질문별 결과 요약", ""])
    if not valid_rows:
        lines.append("아직 저장된 실시간 질문이 없다.")
    for index, row in enumerate(valid_rows, 1):
        profile = row.get("profile", {})
        generation = profile.get("generation", {})
        judge = profile.get("judge", {})
        result = row.get("result") or {}
        score = row.get("judge") or {}
        is_current_score = score.get("rubric_version") == RUBRIC_VERSION
        display_total = score.get("total", "N/A") if is_current_score else "N/A"
        display_verdict = score.get("verdict", "N/A") if is_current_score else "N/A"
        lines.extend([
            f"### {index}. {row.get('question', '')}",
            "",
            f"- 요청 ID: `{row.get('request_id', '')}`",
            f"- 사용 프로필: **{row.get('profile_id', '')}** · {profile.get('title', '')}",
            f"- 생성: `{generation.get('provider', '')} / {generation.get('model', '')} / {generation.get('reasoning', '')}`",
            f"- 평가: `{judge.get('provider', '')} / {judge.get('model', '')} / {judge.get('reasoning', '')}`",
            f"- 상태: `{row.get('status', '')}`",
            f"- 처리시간: `{row.get('elapsed_seconds', 0)}초`",
            f"- Judge: `{display_total} / {display_verdict}`",
            "",
            result.get("answer") or result.get("policy") or result.get("summary") or "결과 없음",
            "",
        ])
        if is_current_score:
            scores = score.get("scores") or {}
            reasons = score.get("reasons") or {}
            lines.extend([
                "| 평가 항목 | 점수 | 근거 |",
                "|---|---:|---|",
            ])
            for criterion in RUBRIC["criteria"]:
                name = criterion["name"]
                value = scores.get(name, "N/A")
                reason = str(reasons.get(name, "")).replace("|", "\\|") or "-"
                lines.append(f"| {name} | {value}/{criterion['max_score']} | {reason} |")
            lines.extend(["", f"- 종합 근거: {score.get('rationale') or '-'}", ""])
        elif score:
            lines.extend([
                "> 이 대화는 이전 4항목·20점 스키마로 채점되어 100점 품질 통계에서 제외한다.",
                "",
            ])

    if invalid_rows:
        lines.extend([
            "## 무효 입력 기록",
            "",
            "> 원본 로그는 보존하되 문자 인코딩이 손상된 질문은 품질 통계와 질문별 결과에서 제외한다.",
            "",
            "| 요청 ID | 수신 질문 | 처리 |",
            "|---|---|---|",
        ])
        for row in invalid_rows:
            question = str(row.get("question", "")).replace("|", "\\|")
            lines.append(f"| `{row.get('request_id', '')}` | {question} | 통계 제외 |")

    content = "\n".join(lines).rstrip() + "\n"
    history_path = history / f"voc_live_report_{run_id}.md"
    latest_path = latest / "voc_live_report.md"
    history_path.write_text(content, encoding="utf-8")
    latest_path.write_text(content, encoding="utf-8")

    manifest = {
        "schema_version": 2,
        "report_type": "voc_live",
        "run_id": run_id,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "record_count": len(rows),
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "scored_count": sum((row.get("judge") or {}).get("rubric_version") == RUBRIC_VERSION for row in valid_rows),
        "profiles": sorted({row.get("profile_id") for row in valid_rows if row.get("profile_id")}),
        "sources": sources,
        "outputs": [str(history_path.relative_to(ROOT)), str(latest_path.relative_to(ROOT))],
    }
    manifest_path = MANIFEST_DIR / f"voc_live_{run_id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(latest_path), "history": str(history_path), "manifest": str(manifest_path)}

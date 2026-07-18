"""실시간 VOC 대화 로그로 요약표·그래프·접힌 상세 목록 보고서를 생성한다."""

from __future__ import annotations

import json
import shutil
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from allstar.shared.model_profiles import public_profiles
from allstar.shared.log_retention import daily_log_paths, read_jsonl
from allstar.shared.paths import MANIFEST_ROOT, PROJECT_ROOT, VOC_LOG_ROOT, VOC_REPORT_ROOT
from allstar.voc.api.judge import RUBRIC_VERSION
from allstar.voc.api.live_report_charts import generate_voc_live_report_charts
from allstar.voc.api.validation import is_valid_question_text
from allstar.voc.evaluation.runtime_support import load_json


ROOT = PROJECT_ROOT
LOG_DIR = VOC_LOG_ROOT / "live" / "conversations"
REPORT_DIR = VOC_REPORT_ROOT / "live"
MANIFEST_DIR = MANIFEST_ROOT
RUBRIC = load_json("judge_rubric.json")
KST = timezone(timedelta(hours=9))
PROFILE_SNAPSHOTS = {profile["profile_id"]: profile for profile in public_profiles()}


def _records() -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    sources: list[str] = []
    for path in daily_log_paths(LOG_DIR):
        sources.append(str(path.relative_to(ROOT)))
        rows.extend(read_jsonl(path, tolerate_invalid=False))
    return rows, sources


def _number(value) -> float | None:
    try:
        if value in (None, "", "N/A"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _timestamp(value) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(KST)


def _time_text(row: dict) -> str:
    parsed = _timestamp(row.get("finished_at") or row.get("timestamp"))
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else "-"


def _period(rows: list[dict]) -> str:
    times = [_timestamp(row.get("finished_at") or row.get("timestamp")) for row in rows]
    times = [value for value in times if value is not None]
    if not times:
        return "-"
    return f"{min(times):%Y-%m-%d / %H:%M:%S} ~ {max(times):%Y-%m-%d / %H:%M:%S} (KST)"


def _current_score(row: dict) -> dict | None:
    score = row.get("judge") or {}
    return score if score.get("rubric_version") == RUBRIC_VERSION else None


def _verdict(row: dict) -> str:
    score = _current_score(row)
    return str(score.get("verdict") or "N/A") if score else "N/A"


def _verdict_group(row: dict) -> str:
    score = _current_score(row)
    if score is None:
        return "na"
    verdict = _verdict(row)
    if score.get("immediate_hold") or "보류" in verdict:
        return "hold"
    if verdict.startswith("조건부"):
        return "conditional"
    if "개선" in verdict:
        return "improve"
    if verdict == "배포 가능":
        return "deployable"
    return "na"


def _verdict_badge(verdict: str) -> str:
    if verdict == "배포 가능":
        background, foreground = "#15803d", "#ffffff"
    elif verdict.startswith("조건부"):
        background, foreground = "#eab308", "#3f2d03"
    elif "개선" in verdict:
        background, foreground = "#ea580c", "#ffffff"
    elif "보류" in verdict:
        background, foreground = "#dc2626", "#ffffff"
    else:
        background, foreground = "#64748b", "#ffffff"
    return (
        f'<span style="display:inline-block;background:{background};color:{foreground};padding:3px 12px;'
        f'border-radius:999px;font-weight:700;font-size:0.95em;">{verdict}</span>'
    )


def _details(summary: str, body_lines: list[str]) -> list[str]:
    return ["<details>", f"<summary><strong>{summary}</strong></summary>", "", *body_lines, "", "</details>", ""]


def _markdown_cell(value, limit: int | None = None) -> str:
    text = str(value or "-").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text or "-"


def _score_text(value) -> str:
    number = _number(value)
    if number is None:
        return "N/A"
    return f"{number:.0f}" if number.is_integer() else f"{number:.1f}"


def _needs_attention(row: dict) -> bool:
    score = _current_score(row)
    if score is None:
        return True
    total = _number(score.get("total"))
    return bool(score.get("immediate_hold")) or total is None or total < 90 or _verdict(row) != "배포 가능"


def _profile_stats(rows: list[dict], profile_id: str) -> dict:
    profile_rows = [row for row in rows if row.get("profile_id") == profile_id]
    groups = [_verdict_group(row) for row in profile_rows]
    scored = [_current_score(row) for row in profile_rows]
    scored = [score for score in scored if score is not None and _number(score.get("total")) is not None]
    totals = [_number(score.get("total")) for score in scored]
    durations = [_number(row.get("elapsed_seconds")) for row in profile_rows]
    durations = [value for value in durations if value is not None]
    deployable = groups.count("deployable")
    return {
        "n": len(profile_rows),
        "scored": len(scored),
        "deployable": deployable,
        "conditional": groups.count("conditional"),
        "improve": groups.count("improve"),
        "hold": groups.count("hold"),
        "na": groups.count("na"),
        "deployable_rate": round(deployable / len(scored) * 100, 1) if scored else 0.0,
        "average_total": round(statistics.mean(totals), 1) if totals else None,
        "average_duration": round(statistics.mean(durations), 2) if durations else None,
    }


def _chart_target(file_path: Path, chart_paths: dict[str, Path], key: str) -> str:
    return chart_paths[key].relative_to(file_path.parent).as_posix()


def _detail_lines(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    for index, row in enumerate(rows, start=1):
        profile_id = str(row.get("profile_id") or "-")
        profile = row.get("profile") or PROFILE_SNAPSHOTS.get(profile_id, {})
        generation = profile.get("generation") or {}
        judge_model = profile.get("judge") or {}
        result = row.get("result") or {}
        score = _current_score(row)
        verdict = _verdict(row)
        lines.extend([
            f"### 3.{index} {_time_text(row)} (KST) · 프로필 {profile_id} · {verdict}",
            "",
            f"- 질문: {row.get('question') or '-'}",
            f"- 답변: {result.get('answer') or result.get('policy') or result.get('summary') or '결과 없음'}",
            f"- 프로필: **{profile_id} · {profile.get('title') or '-'}**",
            f"- 생성 모델: `{generation.get('provider', '-')} / {generation.get('model', '-')} / {generation.get('reasoning', '-')}`",
            f"- 평가 모델: `{judge_model.get('provider', '-')} / {judge_model.get('model', '-')} / {judge_model.get('reasoning', '-')}`",
            f"- 처리 상태·시간: `{row.get('status') or '-'} / {_score_text(row.get('elapsed_seconds'))}초`",
            f"- 종합 점수·판정: **{_score_text(score.get('total') if score else None)} / 100** · {_verdict_badge(verdict)}",
            "",
        ])
        if score:
            scores = score.get("scores") or {}
            reasons = score.get("reasons") or {}
            lines.extend(["| 평가 항목 | 점수 | 근거 |", "|---|---:|---|"])
            for criterion in RUBRIC["criteria"]:
                name = criterion["name"]
                lines.append(
                    f"| {name} | {_score_text(scores.get(name))}/{criterion['max_score']} | "
                    f"{_markdown_cell(reasons.get(name))} |"
                )
            lines.extend([
                "",
                f"- 종합 근거: {score.get('rationale') or '-'}",
            ])
            if score.get("immediate_hold"):
                lines.append(f"- 즉시 보류 사유: {score.get('hold_reason') or '-'}")
            lines.append("")
        else:
            error = row.get("error") or result.get("error") or "정상 100점 채점 결과가 없습니다."
            lines.extend([f"> 확인 사유: {_markdown_cell(error)}", ""])
    return lines


def _report_content(
    valid_rows: list[dict],
    invalid_rows: list[dict],
    file_path: Path,
    chart_paths: dict[str, Path],
    generated_at: datetime,
) -> str:
    scored_rows = [row for row in valid_rows if _current_score(row)]
    durations = [_number(row.get("elapsed_seconds")) for row in valid_rows]
    durations = [value for value in durations if value is not None]
    profiles = list(PROFILE_SNAPSHOTS.values())

    guide = [
        "### A~D 모델 프로필",
        "",
        "| 프로필 | 의미 | 생성 모델 | 평가 모델 |",
        "|---|---|---|---|",
    ]
    for profile in profiles:
        generation = profile["generation"]
        judge = profile["judge"]
        guide.append(
            f"| {profile['profile_id']} · {profile['title']} | {profile['summary']} | "
            f"{generation['provider']} / {generation['model']} / {generation['reasoning']} | "
            f"{judge['provider']} / {judge['model']} / {judge['reasoning']} |"
        )
    guide.extend(["", "### 독립 품질평가 기준", "", "| 평가 항목 | 최대 점수 |", "|---|---:|"])
    for criterion in RUBRIC["criteria"]:
        guide.append(f"| {criterion['name']} | {criterion['max_score']} |")
    guide.extend([
        "",
        "판정 기준: 90점 이상 배포 가능 / 80~89점 조건부 배포 / 70~79점 주요 개선 필요 / 69점 이하 배포 보류 / 즉시 보류 조건은 점수와 무관하게 배포 보류(즉시)",
        "",
    ])

    lines = [
        "# VOC 실시간 대화 품질 리포트",
        "",
        "> 실제 VOC 챗봇 대화와 A~D 독립 Judge 결과를 집계한 최신 보고서입니다. "
        "시각은 한국 시간(KST), 품질 평가는 9항목·100점 기준입니다.",
        "",
        "## 1. 모델 프로필과 품질평가 기준",
        "",
        *guide,
        "## 2. 한눈에 보는 품질 현황",
        "",
        f"- 생성 시각: {generated_at:%Y-%m-%d %H:%M:%S} (KST)",
        f"- 집계 기간: {_period(valid_rows)}",
        f"- 유효 대화: **{len(valid_rows)}건** · 정상 100점 채점: **{len(scored_rows)}건** · 입력 손상 제외: {len(invalid_rows)}건",
        f"- 전체 평균 처리시간: **{round(statistics.mean(durations), 2) if durations else 0.0}초**",
        "",
        "| 모델 프로필 | 대화 | 정상 채점 | 배포 가능 | 조건부 배포 | 주요 개선 | 배포 보류 | N/A·미채점 | 배포 가능률 | 평균 총점 | 평균 처리시간 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for profile in profiles:
        profile_id = profile["profile_id"]
        stats = _profile_stats(valid_rows, profile_id)
        lines.append(
            f"| {profile_id} · {profile['title']} | {stats['n']} | {stats['scored']} | {stats['deployable']} | "
            f"{stats['conditional']} | {stats['improve']} | {stats['hold']} | {stats['na']} | "
            f"{stats['deployable_rate']}% | {_score_text(stats['average_total'])} / 100 | "
            f"{_score_text(stats['average_duration'])}초 |"
        )

    lines.extend(["", "### 품질 항목별 A~D 평균점수", "", "| 평가 항목 | 최대 | A | B | C | D |", "|---|---:|---:|---:|---:|---:|"])
    for criterion in RUBRIC["criteria"]:
        name = criterion["name"]
        profile_values = []
        for profile in profiles:
            values = [
                _number((_current_score(row).get("scores") or {}).get(name))
                for row in valid_rows
                if row.get("profile_id") == profile["profile_id"] and _current_score(row)
            ]
            values = [value for value in values if value is not None]
            profile_values.append(_score_text(statistics.mean(values) if values else None))
        lines.append(f"| {name} | {criterion['max_score']} | " + " | ".join(profile_values) + " |")

    lines.extend([
        "",
        "## 3. 품질·판정·처리시간 그래프",
        "",
        f"![A~D 프로필별 품질 판정 분포]({_chart_target(file_path, chart_paths, 'decisions')})",
        "",
        f"![A~D 프로필별 품질 항목 평균 달성률]({_chart_target(file_path, chart_paths, 'criteria')})",
        "",
        "평가 항목 그래프의 C1~C9는 위 품질 항목별 평균점수 표의 순서를 따릅니다.",
        "",
        f"![A~D 프로필별 평균 처리시간]({_chart_target(file_path, chart_paths, 'durations')})",
        "",
    ])

    attention = sorted([row for row in valid_rows if _needs_attention(row)], key=lambda row: _timestamp(row.get("finished_at") or row.get("timestamp")) or datetime.min.replace(tzinfo=KST), reverse=True)
    attention_body = _detail_lines(attention) if attention else ["- 확인이 필요한 90점 미만·N/A·실패 결과가 없습니다."]
    lines.extend(["## 4. 확인이 필요한 채점 결과", ""])
    lines.extend(_details(f"90점 미만·N/A·실패 상세 목록 열기 ({len(attention)}건)", attention_body))

    recent = sorted(valid_rows, key=lambda row: _timestamp(row.get("finished_at") or row.get("timestamp")) or datetime.min.replace(tzinfo=KST), reverse=True)[:50]
    recent_body = ["| 시각 (KST) | 모델 프로필 | 질문 | 판정 | 총점 |", "|---|---|---|---|---:|"]
    for row in recent:
        profile_id = str(row.get("profile_id") or "-")
        profile = row.get("profile") or PROFILE_SNAPSHOTS.get(profile_id, {})
        score = _current_score(row)
        recent_body.append(
            f"| {_time_text(row)} | {profile_id} · {_markdown_cell(profile.get('title'))} | "
            f"{_markdown_cell(row.get('question'), 60)} | {_verdict_badge(_verdict(row))} | "
            f"{_score_text(score.get('total') if score else None)} |"
        )
    if not recent:
        recent_body.append("| - | - | 저장된 유효 대화가 없습니다 | N/A | N/A |")
    lines.extend(["## 5. 채팅 및 채점 목록", ""])
    lines.extend(_details(f"최근 채팅·채점 목록 열기 ({len(recent)}행, 최대 50행)", recent_body))

    if invalid_rows:
        invalid_body = [
            "> 원본 로그는 보존하지만 문자 인코딩이 손상된 질문은 품질 통계와 채팅·채점 목록에서 제외합니다.",
            "",
            "| 수신 질문 | 처리 |",
            "|---|---|",
        ]
        for row in invalid_rows:
            invalid_body.append(f"| {_markdown_cell(row.get('question'))} | 통계 제외 |")
        lines.extend(["## 6. 무효 입력 기록", ""])
        lines.extend(_details(f"통계 제외 입력 열기 ({len(invalid_rows)}건)", invalid_body))

    return "\n".join(lines).rstrip() + "\n"


def _write_atomic(path: Path, content: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def generate_live_report() -> dict:
    rows, sources = _records()
    valid_rows = [row for row in rows if is_valid_question_text(row.get("question"))]
    invalid_rows = [row for row in rows if not is_valid_question_text(row.get("question"))]
    generated_at = datetime.now(KST)
    run_id = generated_at.strftime("%Y%m%d_%H%M%S_%f")

    history_dir = REPORT_DIR / "history"
    latest_dir = REPORT_DIR / "latest"
    history_assets = history_dir / "assets" / run_id
    latest_assets = latest_dir / "assets"
    for directory in (history_dir, latest_dir, MANIFEST_DIR, history_assets, latest_assets):
        directory.mkdir(parents=True, exist_ok=True)

    history_path = history_dir / f"voc_live_report_{run_id}.md"
    latest_path = latest_dir / "voc_live_report.md"
    history_charts = generate_voc_live_report_charts(valid_rows, RUBRIC, history_assets)
    latest_charts: dict[str, Path] = {}
    for key, source in history_charts.items():
        target = latest_assets / source.name
        shutil.copy2(source, target)
        latest_charts[key] = target

    _write_atomic(history_path, _report_content(valid_rows, invalid_rows, history_path, history_charts, generated_at))
    _write_atomic(latest_path, _report_content(valid_rows, invalid_rows, latest_path, latest_charts, generated_at))

    output_paths = [history_path, latest_path, *history_charts.values(), *latest_charts.values()]
    manifest = {
        "schema_version": 3,
        "report_type": "voc_live",
        "run_id": run_id,
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "record_count": len(rows),
        "valid_count": len(valid_rows),
        "invalid_count": len(invalid_rows),
        "scored_count": sum(_current_score(row) is not None for row in valid_rows),
        "attention_count": sum(_needs_attention(row) for row in valid_rows),
        "profiles": sorted({row.get("profile_id") for row in valid_rows if row.get("profile_id")}),
        "sources": sources,
        "outputs": [str(path.relative_to(ROOT)) for path in output_paths],
    }
    manifest_path = MANIFEST_DIR / f"voc_live_{run_id}.json"
    _write_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {
        "report": str(latest_path),
        "history": str(history_path),
        "manifest": str(manifest_path),
        "charts": [str(path) for path in latest_charts.values()],
    }

"""VOC 실시간 대화 보고서용 A~D 품질·판정·처리시간 그래프."""

from __future__ import annotations

import statistics
from pathlib import Path

from allstar.shared.model_profiles import public_profiles
from allstar.voc.api.judge import RUBRIC_VERSION
from allstar.voc.evaluation.report_charts import _bar_chart, _grouped_bar_chart, _number


PROFILE_IDS = tuple(profile["profile_id"] for profile in public_profiles())
DECISION_LABELS = ("배포 가능", "조건부", "개선 필요", "배포 보류", "N/A")


def _current_score(row: dict) -> dict | None:
    score = row.get("judge") or {}
    return score if score.get("rubric_version") == RUBRIC_VERSION else None


def _decision_label(row: dict) -> str:
    score = _current_score(row)
    if score is None:
        return "N/A"
    verdict = str(score.get("verdict") or "")
    if score.get("immediate_hold") or "보류" in verdict:
        return "배포 보류"
    if verdict.startswith("조건부"):
        return "조건부"
    if "개선" in verdict:
        return "개선 필요"
    if verdict == "배포 가능":
        return "배포 가능"
    return "N/A"


def generate_voc_live_report_charts(rows: list[dict], rubric: dict, assets_dir: Path) -> dict[str, Path]:
    """누적 VOC 실시간 로그에서 최신 보고서용 PNG 세 개를 생성한다."""
    assets_dir.mkdir(parents=True, exist_ok=True)

    decision_path = assets_dir / "profile_decision_distribution.png"
    decision_series = []
    for profile_id in PROFILE_IDS:
        profile_rows = [row for row in rows if row.get("profile_id") == profile_id]
        decision_series.append(
            (profile_id, [float(sum(_decision_label(row) == label for row in profile_rows)) for label in DECISION_LABELS])
        )
    _grouped_bar_chart(
        decision_path,
        "A~D 프로필별 품질 판정 분포",
        list(DECISION_LABELS),
        decision_series,
        suffix="건",
        integer_axis=True,
    )

    criteria = rubric.get("criteria", [])
    criteria_path = assets_dir / "profile_quality_axis_average.png"
    criteria_series = []
    for profile_id in PROFILE_IDS:
        profile_rows = [row for row in rows if row.get("profile_id") == profile_id and _current_score(row)]
        rates: list[float | None] = []
        for criterion in criteria:
            name = criterion["name"]
            maximum = _number(criterion.get("max_score"))
            values = [_number((_current_score(row).get("scores") or {}).get(name)) for row in profile_rows]
            values = [value for value in values if value is not None]
            rates.append(statistics.mean(values) / maximum * 100 if values and maximum else None)
        criteria_series.append((profile_id, rates))
    _grouped_bar_chart(
        criteria_path,
        "A~D 프로필별 품질 항목 평균 달성률",
        [f"C{index}" for index in range(1, len(criteria) + 1)],
        criteria_series,
        suffix="%",
        maximum=100,
    )

    duration_path = assets_dir / "profile_average_duration.png"
    average_durations: list[float | None] = []
    for profile_id in PROFILE_IDS:
        durations = [_number(row.get("elapsed_seconds")) for row in rows if row.get("profile_id") == profile_id]
        durations = [duration for duration in durations if duration is not None]
        average_durations.append(statistics.mean(durations) if durations else None)
    _bar_chart(
        duration_path,
        "A~D 프로필별 평균 처리시간",
        list(PROFILE_IDS),
        average_durations,
        suffix="초",
        subtitle="유효한 실시간 VOC 대화 기준",
    )

    return {"decisions": decision_path, "criteria": criteria_path, "durations": duration_path}

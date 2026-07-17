"""AI 에이전트 테스트케이스 비교 보고서용 데이터 기반 PNG 그래프."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from allstar.ai_agent.evaluation.live_report_charts import _grouped_bar_chart


MODEL_SPECS = (
    ("rule_based", "규칙 기반 챗봇"),
    ("api_based", "API 기반 챗봇"),
)
DECISION_ORDER = ("PASS", "REVIEW", "FAIL", "N/A")
AXIS_SPECS = (
    ("accuracy_score", "정확성"),
    ("groundedness_score", "근거성"),
    ("helpfulness_score", "유용성"),
    ("safety_score", "안전성"),
    ("understandability_score", "이해가능성"),
)


def _numeric(value) -> float | None:
    try:
        return float(value) if pd.notna(value) else None
    except (TypeError, ValueError):
        return None


def generate_batch_report_charts(rows: pd.DataFrame, assets_dir: Path) -> dict[str, Path]:
    """케이스·품질항목·판정분포 비교 그래프 세 개를 생성한다."""
    assets_dir.mkdir(parents=True, exist_ok=True)

    case_ids = rows["case_id"].drop_duplicates().astype(str).tolist()
    score_series = []
    for model_type, label in MODEL_SPECS:
        model_rows = rows[rows["model_type"] == model_type].set_index("case_id")
        values = []
        for case_id in case_ids:
            if case_id not in model_rows.index:
                values.append(None)
                continue
            model_row = model_rows.loc[case_id]
            if isinstance(model_row, pd.DataFrame):
                model_row = model_row.iloc[-1]
            values.append(None if model_row["overall_decision"] == "N/A" else _numeric(model_row["total_score"]))
        score_series.append((label, values))
    score_path = assets_dir / "case_score_comparison.png"
    _grouped_bar_chart(
        score_path,
        "테스트케이스별 품질 총점 비교",
        case_ids,
        score_series,
        maximum=25,
        subtitle="규칙 기반과 API 기반 결과 · 25점 만점 · N/A는 점수에서 제외",
    )

    scored = rows[rows["overall_decision"].isin(["PASS", "REVIEW", "FAIL"])]
    axis_series = []
    for model_type, label in MODEL_SPECS:
        model_rows = scored[scored["model_type"] == model_type]
        values = []
        for column, _axis_label in AXIS_SPECS:
            numeric = pd.to_numeric(model_rows[column], errors="coerce").dropna()
            values.append(float(numeric.mean()) if not numeric.empty else None)
        axis_series.append((label, values))
    axis_path = assets_dir / "quality_axis_average.png"
    _grouped_bar_chart(
        axis_path,
        "모델별 품질 항목 평균점수",
        [label for _column, label in AXIS_SPECS],
        axis_series,
        maximum=5,
        subtitle="채점 가능한 결과만 집계 · 항목별 5점 만점",
    )

    decision_series = []
    for model_type, label in MODEL_SPECS:
        model_rows = rows[rows["model_type"] == model_type]
        decision_series.append(
            (label, [float(model_rows["overall_decision"].eq(decision).sum()) for decision in DECISION_ORDER])
        )
    decision_max = max((value for _label, values in decision_series for value in values), default=0.0)
    decision_path = assets_dir / "decision_distribution.png"
    _grouped_bar_chart(
        decision_path,
        "모델별 품질 판정 분포",
        list(DECISION_ORDER),
        decision_series,
        maximum=max(5.0, decision_max * 1.15),
        subtitle="N/A는 품질 실패와 분리해 표시",
    )

    return {"scores": score_path, "axes": axis_path, "decisions": decision_path}

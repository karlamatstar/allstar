"""누적된 VOC Judge 실행 로그로 프로필 정식 보고서를 다시 생성한다."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from allstar.shared.model_profiles import ModelProfile
from allstar.voc.evaluation import llm_judge


@contextmanager
def _report_environment(profile: ModelProfile, run_id: str):
    updates = {
        "CROSS_VALIDATION_EXPERIMENT": profile.profile_id,
        "GENERATION_PROVIDER": profile.generation.provider,
        "JUDGE_PROVIDER": profile.judge.provider,
        "VOC_REPORT_RUN_ID": run_id,
        "ALLSTAR_VOC_PROFILE_SNAPSHOT": json.dumps(profile.snapshot(), ensure_ascii=False),
    }
    previous = {key: os.environ.get(key) for key in updates}
    os.environ.update(updates)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def rebuild_profile_report_from_log(log_path: Path, report_dir: Path, profile: ModelProfile) -> dict:
    """Judge JSON 로그의 전체 사례 결과로 CSV·JSON·Markdown·그래프를 재생성한다."""
    data = json.loads(log_path.read_text(encoding="utf-8"))
    rows = data.get("case_results") or []
    if not rows:
        raise ValueError(f"보고서로 변환할 사례 결과가 없습니다: {log_path}")
    rubric = llm_judge.load_json("judge_rubric.json")
    criteria_names = [criterion["name"] for criterion in rubric["criteria"]]
    previous_report_dir = llm_judge.ACTIVE_REPORTS_DIR
    try:
        llm_judge.ACTIVE_REPORTS_DIR = report_dir.resolve()
        with _report_environment(profile, str(data.get("run_id") or log_path.stem)):
            llm_judge._write_reports(rows, criteria_names, rubric)
    finally:
        llm_judge.ACTIVE_REPORTS_DIR = previous_report_dir
    return {
        "run_id": data.get("run_id"),
        "status": data.get("status"),
        "case_ids": [row.get("case_id") for row in rows],
        "source_log": str(log_path),
        "report": str(report_dir / "quality_score_report.md"),
    }

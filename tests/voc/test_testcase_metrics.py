from __future__ import annotations

import json
from pathlib import Path

import pytest

from allstar.voc.api.testcase_metrics import VocTestcaseReportCollector, classify_case_result


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


@pytest.mark.parametrize(
    ("row", "expected"),
    [
        ({"total": 95, "verdict": "배포 가능"}, "PASS"),
        ({"total": 85, "verdict": "조건부 배포 가능"}, "REVIEW"),
        ({"total": 75, "verdict": "주요 개선 필요"}, "FAIL"),
        ({"total": "N/A", "verdict": "미평가(API 실패)"}, "N/A"),
        ({"total": "", "verdict": "PASS (예외처리)"}, "PASS"),
    ],
)
def test_classify_case_result(row: dict, expected: str):
    assert classify_case_result(row) == expected


def test_collector_converts_existing_profile_report_to_metrics(tmp_path: Path):
    report_root = tmp_path / "reports"
    rubric = tmp_path / "judge_rubric.json"
    _write(
        rubric,
        {
            "criteria": [
                {"name": "정확성", "max_score": 20},
                {"name": "안전성", "max_score": 10},
            ]
        },
    )
    _write(
        report_root / "c" / "llm_judge_result.json",
        {
            "generated_at": "2026-07-17T14:31:07+09:00",
            "cases": [
                {
                    "case_id": "TC-01",
                    "total": 90,
                    "verdict": "배포 가능",
                    "total_seconds": 12,
                    "정확성": 18,
                    "안전성": 8,
                },
                {
                    "case_id": "TC-02",
                    "total": 80,
                    "verdict": "조건부 배포 가능",
                    "total_seconds": 18,
                    "정확성": 14,
                    "안전성": 6,
                },
                {
                    "case_id": "TC-03",
                    "total": "N/A",
                    "verdict": "미평가(API 실패)",
                    "total_seconds": 5,
                    "정확성": "",
                    "안전성": "",
                },
            ],
        },
    )

    families = {family.name: family for family in VocTestcaseReportCollector(report_root, rubric).collect()}

    def values(name: str) -> dict[tuple[str, ...], float]:
        return {tuple(sample.labels.values()): sample.value for sample in families[name].samples}

    assert values("voc_testcase_latest_average_score") == {("C",): 85.0}
    assert values("voc_testcase_latest_cases_total") == {("C",): 3}
    assert values("voc_testcase_latest_case_results") == {
        ("C", "PASS"): 1,
        ("C", "REVIEW"): 1,
        ("C", "FAIL"): 0,
        ("C", "N/A"): 1,
    }
    assert values("voc_testcase_latest_duration_seconds") == {("C",): 35.0}
    assert values("voc_testcase_latest_case_average_duration_seconds") == {("C",): pytest.approx(35 / 3)}
    assert values("voc_testcase_latest_criterion_achievement_percent") == {
        ("C", "정확성"): 80.0,
        ("C", "안전성"): 70.0,
    }
    assert values("voc_testcase_latest_case_score") == {
        ("C", "TC-01", "PASS"): 90.0,
        ("C", "TC-02", "REVIEW"): 80.0,
    }


def test_collector_ignores_missing_or_broken_reports(tmp_path: Path):
    report_root = tmp_path / "reports"
    broken = report_root / "a" / "llm_judge_result.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{writing", encoding="utf-8")
    rubric = tmp_path / "judge_rubric.json"
    _write(rubric, {"criteria": []})

    families = list(VocTestcaseReportCollector(report_root, rubric).collect())

    assert all(not family.samples for family in families)

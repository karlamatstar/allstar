import json

import pandas as pd

from allstar.ai_agent.evaluation.report_generator import _decision_stats, generate_all


def test_na_is_separate_from_fail_and_excluded_from_rate_and_average():
    def row(decision, total, score):
        return {
            "overall_decision": decision,
            "total_score": total,
            "accuracy_score": score,
            "groundedness_score": score,
            "helpfulness_score": score,
            "safety_score": score,
            "understandability_score": score,
        }

    rows = pd.DataFrame(
        [
            row("PASS", 20, 4),
            row("FAIL", 10, 2),
            row("N/A", 0, 0),
        ]
    )

    stats = _decision_stats(rows)

    assert stats["pass"] == 1
    assert stats["fail"] == 1
    assert stats["na"] == 1
    assert stats["pass_rate"] == 50.0
    assert stats["avg_total"] == 15.0


def _evaluation(score: int, decision: str) -> dict:
    return {
        "accuracy": {"score": score, "reason": "정확성"},
        "groundedness": {"score": score, "reason": "근거성"},
        "helpfulness": {"score": score, "reason": "유용성"},
        "safety": {"score": score, "reason": "안전성"},
        "understandability": {"score": score, "reason": "이해가능성"},
        "total_score": score * 5,
        "overall_decision": decision,
        "summary": "평가 요약",
    }


def _result(case_id: str, rule_score: int, api_score: int) -> dict:
    return {
        "case_id": case_id,
        "category": "정확성",
        "test_type": "Happy",
        "user_question": f"{case_id} 질문",
        "rule_based": {
            "answer": "규칙 답변",
            "rule_validation": {"rule_status": "PASS"},
            "evaluation": _evaluation(rule_score, "PASS"),
        },
        "api_based": {
            "answer": "API 답변",
            "rule_validation": {"rule_status": "PASS"},
            "evaluation": _evaluation(api_score, "PASS" if api_score >= 4 else "REVIEW"),
        },
    }


def test_generate_all_creates_latest_and_history_quality_charts(tmp_path):
    results = [_result("TC-001", 4, 5), _result("TC-002", 3, 4)]

    generate_all(results, tmp_path, "test_run")

    chart_names = {
        "case_score_comparison.png",
        "quality_axis_average.png",
        "decision_distribution.png",
    }
    for assets in (tmp_path / "assets", tmp_path / "history" / "assets" / "test_run"):
        assert {path.name for path in assets.glob("*.png")} == chart_names
        assert all(path.read_bytes().startswith(b"\x89PNG") for path in assets.glob("*.png"))

    latest = (tmp_path / "final_quality_report.md").read_text(encoding="utf-8")
    history = (tmp_path / "history" / "test_run_final_quality_report.md").read_text(encoding="utf-8")
    assert "## 3. 품질 결과 그래프" in latest
    assert "assets/case_score_comparison.png" in latest
    assert "assets/test_run/case_score_comparison.png" in history
    assert len(json.loads((tmp_path / "evaluation_result.json").read_text(encoding="utf-8"))) == 2

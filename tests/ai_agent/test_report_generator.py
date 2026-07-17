import pandas as pd

from allstar.ai_agent.evaluation.report_generator import _decision_stats


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

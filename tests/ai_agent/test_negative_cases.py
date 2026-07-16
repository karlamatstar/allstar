"""실제 API를 호출해 적대적/부정 테스트케이스(test_type=Negative)에 대한 안전 응답을 검증합니다."""
import pytest

from allstar.ai_agent.api.service_agent import get_answer_from_api_agent
from allstar.ai_agent.evaluation.quality_pipeline import TEST_CASE_FILE, load_test_cases
from allstar.ai_agent.evaluation.rule_validator import validate_by_rules

NEGATIVE_CASES = [tc for tc in load_test_cases(TEST_CASE_FILE) if tc["test_type"] == "Negative"]


@pytest.mark.parametrize("tc", NEGATIVE_CASES, ids=[tc["case_id"] for tc in NEGATIVE_CASES])
def test_negative_case_is_handled_safely(tc):
    answer = get_answer_from_api_agent(tc["user_question"])
    rule_result = validate_by_rules(tc["user_question"], answer, tc["expected_keyword"])

    assert answer.strip() != ""
    assert rule_result["keyword_found"], (
        f"[{tc['case_id']}] 기대 키워드 '{tc['expected_keyword']}'가 답변에 없음: {answer}"
    )

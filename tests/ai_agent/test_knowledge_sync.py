"""AI 답변 모델과 독립 채점 모델의 지식 원본 동기화를 검증한다."""

from allstar.ai_agent.api.judge_agent import _format_knowledge_base
from allstar.ai_agent.api.knowledge_base import COURSE_KNOWLEDGE, format_course_knowledge
from allstar.ai_agent.api.service_agent import SYSTEM_PROMPT


def test_api_prompt_automatically_contains_every_knowledge_value():
    for value in COURSE_KNOWLEDGE.values():
        assert str(value) in SYSTEM_PROMPT


def test_answer_and_judge_models_receive_the_same_knowledge_text():
    formatted = format_course_knowledge()
    assert formatted in SYSTEM_PROMPT
    assert _format_knowledge_base() == formatted


def test_drop_out_policy_is_available_to_api_answer_model():
    assert "중도 포기·재합류 정책" in SYSTEM_PROMPT
    assert COURSE_KNOWLEDGE["drop_out_policy"] in SYSTEM_PROMPT

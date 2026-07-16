"""규칙(키워드 매칭) 기반 에이전트. ai_quality_final_project의 rule_based_agent를 이식한 것으로,
배치 품질 비교 평가와 실시간 /chat 비교 응답에서 API 기반 에이전트의 대조군으로 사용된다.
외부 API를 호출하지 않으므로 지연/실패 없이 항상 즉시 응답한다."""
from allstar.ai_agent.api.knowledge_base import COURSE_KNOWLEDGE


def get_answer_from_rule_based_agent(user_question: str) -> str:
    # 띄어쓰기 방어: 모든 공백을 제거하여 단순 띄어쓰기 차이로 인한 미인식 방지
    question = user_question.strip().replace(" ", "")

    # 의도적으로 오타 방어는 구현하지 않음 (예: "출선률")

    # 복합 키워드 (가장 먼저 체크)
    if "교육시간" in question and ("수료" in question or "함께알려" in question):
        return (
            f"교육시간은 총 {COURSE_KNOWLEDGE['total_hours']}시간입니다. "
            f"수료를 위해서는 {COURSE_KNOWLEDGE['completion_rule']}"
        )

    # 단일 키워드 매핑 딕셔너리
    keyword_mapping = {
        ("총몇시간", "교육시간"): f"{COURSE_KNOWLEDGE['course_name']}은 총 {COURSE_KNOWLEDGE['total_hours']}시간으로 구성되어 있습니다.",
        ("지각",): COURSE_KNOWLEDGE["attendance_rule"],
        ("수료", "출석률"): f"{COURSE_KNOWLEDGE['completion_rule']} 또한 {COURSE_KNOWLEDGE['project_rule']}",
        ("취업", "이력서", "면접"): COURSE_KNOWLEDGE["support_rule"],
        ("날씨",): "죄송합니다. 저는 교육과정 안내 챗봇이므로 실시간 날씨 정보는 확인할 수 없습니다.",
        ("혼내는방법", "괴롭히는방법"): "죄송합니다. 다른 사람을 위협하거나 괴롭히는 행동에 대해서는 도와드릴 수 없습니다. 갈등 상황이라면 대화나 담당자 상담을 권합니다.",
        # 새롭게 추가된 지식베이스 매핑
        ("커리큘럼", "배우는내용", "어떤과목", "알고리즘", "파이썬", "QA", "품질"): COURSE_KNOWLEDGE["curriculum_details"],
        ("평가", "시험", "커트라인", "재시험"): COURSE_KNOWLEDGE["evaluation_criteria"],
        ("컴퓨터", "장비", "교재", "지원", "지급"): COURSE_KNOWLEDGE["equipment_support"],
        ("휴일", "공휴일", "주말", "보충수업"): COURSE_KNOWLEDGE["holiday_rule"],
        ("중도포기", "하차", "중도합류"): COURSE_KNOWLEDGE["drop_out_policy"],
    }

    for keywords, answer in keyword_mapping.items():
        if any(kw in question for kw in keywords):
            return answer

    return (
        "죄송합니다. 제공된 교육과정 안내 정보에서 해당 내용을 확인할 수 없습니다. "
        "운영 담당자에게 문의해 주세요."
    )

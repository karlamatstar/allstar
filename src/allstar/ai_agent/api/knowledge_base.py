COURSE_KNOWLEDGE = {
    "course_name": "AI 기반 SW 테스터 및 품질관리 실무 과정",
    "total_hours": 320,
    "attendance_rule": "지각 3회는 결석 1일로 처리됩니다.",
    "completion_rule": "전체 훈련시간의 80퍼센트 이상 출석해야 수료할 수 있습니다.",
    "project_rule": "최종 프로젝트 결과물과 발표 평가를 완료해야 합니다.",
    "support_rule": "취업 상담, 이력서 첨삭, 모의면접 지원을 제공합니다.",
    "schedule_rule": "세부 수업 일정은 운영 상황에 따라 일부 조정될 수 있습니다.",
    "curriculum_details": "본 과정은 파이썬 기초, 알고리즘, 데이터 분석, 그리고 AI QA 실무 프로젝트로 구성됩니다.",
    "evaluation_criteria": "단위 평가 통과 기준은 60점 이상이며, 미달 시 1회의 재시험 기회가 부여됩니다.",
    "equipment_support": "모든 훈련생에게 실습용 컴퓨터가 지급되며, 교재가 지원됩니다.",
    "holiday_rule": "법정 공휴일은 휴강이며, 주말에는 별도의 보충 수업이 진행되지 않습니다.",
    "drop_out_policy": "수강 시작 후 하차는 할 수 있으나, 다시 중도 합류는 불가능합니다."
}


COURSE_KNOWLEDGE_LABELS = {
    "course_name": "과정명",
    "total_hours": "총 교육시간",
    "attendance_rule": "출결 규정",
    "completion_rule": "수료 기준",
    "project_rule": "프로젝트 기준",
    "support_rule": "취업지원 안내",
    "schedule_rule": "수업 일정",
    "curriculum_details": "커리큘럼",
    "evaluation_criteria": "평가 기준",
    "equipment_support": "장비·교재 지원",
    "holiday_rule": "휴일·주말 수업",
    "drop_out_policy": "중도 포기·재합류 정책",
}


def format_course_knowledge() -> str:
    """지식 원본 전체를 API 답변·채점 모델이 공유할 안내문으로 변환한다.

    새 항목이 ``COURSE_KNOWLEDGE``에 추가되면 별도의 프롬프트 수정 없이
    자동으로 포함된다. 사람이 읽는 이름이 아직 없으면 내부 키를 그대로 써서
    지식 자체가 누락되는 것보다 안전하게 동작한다.
    """
    lines = []
    for key, value in COURSE_KNOWLEDGE.items():
        label = COURSE_KNOWLEDGE_LABELS.get(key, key)
        suffix = "시간" if key == "total_hours" else ""
        lines.append(f"- {label}: {value}{suffix}")
    return "\n".join(lines)

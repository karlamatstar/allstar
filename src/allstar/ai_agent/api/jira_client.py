import httpx
import logging
from allstar.ai_agent.api.config import (
    JIRA_URL, JIRA_USER, JIRA_API_TOKEN,
    JIRA_PROJECT_KEY, JIRA_EPIC_KEY, JIRA_SPRINT_ID
)

logger = logging.getLogger(__name__)

def create_jira_issue_for_question(
    request_id: str,
    timestamp: str,
    question: str,
    api_eval: dict,
    rule_eval: dict,
    answer_model: str,
    judge_model: str
) -> None:
    """
    챗봇 평가 결과가 FAIL/REVIEW일 경우 Jira에 버그 티켓을 생성하고 스프린트에 할당합니다.
    """
    if not all([JIRA_URL, JIRA_USER, JIRA_API_TOKEN]):
        logger.warning("Jira 환경 변수가 설정되지 않았습니다. Jira 티켓 생성을 건너뜁니다.")
        return

    # Determine priority
    has_fail = (api_eval.get("overall_decision") == "FAIL") or (rule_eval.get("overall_decision") == "FAIL")
    priority_name = "High" if has_fail else "Medium"

    # Format description
    description = f"다음 질문에 대한 챗봇 답변 채점 결과 품질 이상이 발견되었습니다.\n\n"
    description += f"*요청 ID*: {request_id}\n*질문 시간*: {timestamp}\n*질문*: {question}\n\n"

    description += f"[API 기반 챗봇 답변 (답변 모델: {answer_model}, 채점 모델: {judge_model})]\n"
    description += f"* 결과: {api_eval.get('overall_decision')} (총점: {api_eval.get('total_score')}점)\n"
    description += f"* 의견: {api_eval.get('reason')}\n\n"

    description += f"[규칙 기반 챗봇 답변 (답변 모델: Rule-based, 채점 모델: {judge_model})]\n"
    description += f"* 결과: {rule_eval.get('overall_decision')} (총점: {rule_eval.get('total_score')}점)\n"
    description += f"* 의견: {rule_eval.get('reason')}\n"

    payload = {
        "fields": {
            "project": {"key": JIRA_PROJECT_KEY},
            "issuetype": {"name": "Bug"},
            "priority": {"name": priority_name},
            "summary": f"[품질 이상] 챗봇 질문 확인: {question[:30]}...",
            "description": description
        }
    }

    # Add Epic link if provided
    if JIRA_EPIC_KEY:
        # Note: Depending on Jira version/settings, the epic field might be different (e.g., customfield_10014)
        # However, for Jira Cloud next-gen or using 'parent', we can try 'parent':
        payload["fields"]["parent"] = {"key": JIRA_EPIC_KEY}

    auth = (JIRA_USER, JIRA_API_TOKEN)
    headers = {"Content-Type": "application/json"}

    try:
        # Create Issue
        url = f"{JIRA_URL}/rest/api/2/issue"
        response = httpx.post(url, json=payload, auth=auth, headers=headers, timeout=10.0)

        if response.status_code == 201:
            issue_key = response.json().get("key")
            logger.info(f"✅ Jira 이슈 생성 성공: {issue_key}")

            # Assign to sprint
            if JIRA_SPRINT_ID and issue_key:
                sprint_url = f"{JIRA_URL}/rest/agile/1.0/sprint/{JIRA_SPRINT_ID}/issue"
                sprint_payload = {"issues": [issue_key]}
                sprint_resp = httpx.post(sprint_url, json=sprint_payload, auth=auth, headers=headers, timeout=10.0)
                if sprint_resp.status_code == 204 or sprint_resp.status_code == 200:
                    logger.info(f"✅ Jira 스프린트 할당 성공: {issue_key} -> Sprint {JIRA_SPRINT_ID}")
                else:
                    logger.warning(f"Jira 스프린트 할당 실패: {sprint_resp.text}")
        else:
            logger.error(f"❌ Jira 이슈 생성 실패: {response.text}")

    except Exception as e:
        logger.error(f"Jira API 호출 중 오류 발생: {str(e)}")

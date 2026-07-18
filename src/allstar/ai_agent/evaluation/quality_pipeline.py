"""배치 품질 회귀 파이프라인 — 케이스마다 규칙 기반/API 기반 두 에이전트의 답변을 받아
동일한 규칙 검증 + AI Judge 루브릭으로 채점해 비교한다 (ai_quality_final_project의 비교 평가 방식).
API 호출 실패는 FAIL이 아닌 N/A(채점 불가)로 분리 집계한다."""
import json
from datetime import datetime
from pathlib import Path

from allstar.ai_agent.api.config import validate_config
from allstar.ai_agent.api.judge_agent import JudgeUnavailableError, get_evaluation_from_openai
from allstar.ai_agent.api.rule_based_agent import get_answer_from_rule_based_agent
from allstar.ai_agent.api.service_agent import ApiAgentUnavailableError, get_answer_from_api_agent
from allstar.ai_agent.evaluation.report_generator import generate_all
from allstar.ai_agent.evaluation.rule_validator import validate_by_rules
from allstar.shared.paths import AI_AGENT_LOG_ROOT, AI_AGENT_REPORT_ROOT, MANIFEST_ROOT, PROJECT_ROOT

EVALUATION_DIR = Path(__file__).resolve().parent
TEST_CASE_FILE = EVALUATION_DIR / "test_cases.json"
REPORTS_DIR = AI_AGENT_REPORT_ROOT / "batch"
TESTCASE_LOG_DIR = AI_AGENT_LOG_ROOT / "testcase"
MANIFEST_DIR = MANIFEST_ROOT

MODEL_LABELS = {"rule_based": "규칙 기반", "api_based": "API 기반"}


def load_test_cases(file_path: Path) -> list:
    return json.loads(file_path.read_text(encoding="utf-8"))


def create_error_evaluation(error: Exception, stage: str, decision: str = "FAIL") -> dict:
    reason = f"{stage} 실패"
    return {
        "accuracy":          {"score": 0, "reason": reason},
        "groundedness":      {"score": 0, "reason": reason},
        "helpfulness":       {"score": 0, "reason": reason},
        "safety":            {"score": 0, "reason": reason},
        "understandability": {"score": 0, "reason": reason},
        "total_score": 0,
        "overall_decision": decision,
        "summary": f"{reason}: {error}",
    }


def format_score_line(evaluation: dict) -> str:
    return (
        f"{evaluation['overall_decision']} "
        f"[정확성 {evaluation['accuracy']['score']} | "
        f"근거성 {evaluation['groundedness']['score']} | "
        f"유용성 {evaluation['helpfulness']['score']} | "
        f"안전성 {evaluation['safety']['score']} | "
        f"이해성 {evaluation['understandability']['score']} | "
        f"합계 {evaluation['total_score']}/25]"
    )


def unavailable_result(error: Exception, stage: str) -> dict:
    """답변 생성 자체가 실패한 모델의 결과 골격 (규칙 검증도 불가하므로 함께 N/A)."""
    return {
        "answer": f"[답변 생성 실패: {error}]",
        "rule_validation": {
            "keyword_found": False, "rule_status": "N/A",
            "rule_reason": "답변 생성에 실패하여 규칙 검증을 수행할 수 없습니다.",
        },
        "evaluation": create_error_evaluation(error, stage, decision="N/A"),
    }


def evaluate_answer(tc: dict, answer: str, agent_label: str) -> dict:
    """생성된 답변 하나를 규칙 검증 + AI Judge로 채점한다."""
    rule_validation = validate_by_rules(tc["user_question"], answer, tc["expected_keyword"])
    try:
        evaluation = get_evaluation_from_openai(
            user_question=tc["user_question"], ai_answer=answer,
            expected_policy=tc["expected_policy"], agent_label=agent_label,
        )
    except JudgeUnavailableError as error:
        evaluation = create_error_evaluation(error, "저지 에이전트 API 호출", decision="N/A")
    except Exception as error:
        evaluation = create_error_evaluation(error, "평가 API 호출")

    return {"answer": answer, "rule_validation": rule_validation, "evaluation": evaluation}


def evaluate_case(tc: dict) -> dict:
    """케이스 하나를 규칙 기반/API 기반 두 에이전트로 답변받아 각각 채점한다."""
    user_question = tc["user_question"]

    # 규칙 기반 에이전트는 로컬 키워드 매칭이라 항상 즉시 답변한다
    rule_based_answer = get_answer_from_rule_based_agent(user_question)
    rule_based = evaluate_answer(tc, rule_based_answer, agent_label="배치-규칙기반")

    try:
        api_based_answer = get_answer_from_api_agent(user_question)
    except ApiAgentUnavailableError as error:
        api_based = unavailable_result(error, "에이전트 답변 생성")
    else:
        api_based = evaluate_answer(tc, api_based_answer, agent_label="배치-API기반")

    return {
        "case_id": tc["case_id"], "category": tc["category"], "test_type": tc["test_type"],
        "user_question": user_question,
        "rule_based": rule_based,
        "api_based": api_based,
    }


def run_pipeline(test_cases: list, timestamp: str) -> list:
    validate_config()
    results = []

    print(f"\n{'='*50}\n  AI 챗봇 비교 품질평가 파이프라인 시작 (총 {len(test_cases)}개, 규칙기반 vs API기반)\n{'='*50}\n")

    for tc in test_cases:
        print(f"\n[{tc['case_id']}] 테스트 시작")
        result = evaluate_case(tc)
        print(f"  규칙 기반: {format_score_line(result['rule_based']['evaluation'])}")
        print(f"  API 기반: {format_score_line(result['api_based']['evaluation'])}")
        results.append(result)

    print(f"\n{'='*50}\n  리포트 생성 중...\n{'='*50}")
    TESTCASE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    source_log = TESTCASE_LOG_DIR / f"ai_agent_batch_{timestamp}.json"
    source_log.write_text(
        json.dumps({
            "schema_version": 1,
            "run_id": timestamp,
            "test_case_count": len(results),
            "results": results,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    generate_all(results, REPORTS_DIR, timestamp)
    manifest = {
        "schema_version": 1,
        "report_type": "ai_agent_batch",
        "run_id": timestamp,
        "source": str(source_log.relative_to(PROJECT_ROOT)),
        "outputs": [
            str((REPORTS_DIR / "evaluation_result.json").relative_to(PROJECT_ROOT)),
            str((REPORTS_DIR / "evaluation_result.csv").relative_to(PROJECT_ROOT)),
            str((REPORTS_DIR / "final_quality_report.md").relative_to(PROJECT_ROOT)),
        ],
    }
    (MANIFEST_DIR / f"ai_agent_batch_{timestamp}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        from allstar.ai_agent.evaluation.log_retention import archive_old_batch_logs

        archive_old_batch_logs(TESTCASE_LOG_DIR, MANIFEST_DIR)
    except Exception as error:
        print(f"이전 AI 테스트케이스 로그 자동 압축 실패: {error}")
    print("  파이프라인 완료\n")
    return results


if __name__ == "__main__":
    timestamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    run_pipeline(load_test_cases(TEST_CASE_FILE), timestamp)

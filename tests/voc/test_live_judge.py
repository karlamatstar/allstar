"""외부 API 없이 실시간 VOC Judge가 공통 100점 계약을 사용하는지 확인한다."""

import json

from allstar.voc.api import judge
from allstar.voc.evaluation.judge_prompt import build_judge_prompt, parse_judge_response
from allstar.voc.evaluation.runtime_support import load_json


def test_live_analysis_contains_all_pipeline_artifacts():
    analysis = judge._analysis_text({
        "intent_json": '{"filters":["가입"]}',
        "trace": "Retriever:count=3",
        "summary": "요약 결과",
        "eval_json": '{"winner":"A"}',
        "summary_critic_json": '{"need_refine":false}',
        "policy": "개선안",
    }, 3.25)
    for expected in ("가입", "Retriever:count=3", "요약 결과", "winner", "need_refine", "개선안", "3.25초"):
        assert expected in analysis


def test_live_judge_prompt_and_parser_use_nine_criteria_and_100_points():
    rubric = load_json("judge_rubric.json")
    prompt = build_judge_prompt("가입 불편 분석", "6단계 분석 결과", rubric)
    assert "합계 100점" in prompt
    assert "reasons" in prompt
    assert all(criterion["name"] in prompt for criterion in rubric["criteria"])

    raw = json.dumps({
        "scores": {criterion["name"]: criterion["max_score"] for criterion in rubric["criteria"]},
        "reasons": {criterion["name"]: "정상" for criterion in rubric["criteria"]},
        "immediate_hold": False,
        "hold_reason": "",
        "rationale": "전체 단계가 정상적으로 연결됨",
    }, ensure_ascii=False)
    parsed = parse_judge_response(raw, rubric)
    assert parsed["total"] == 100
    assert len(parsed["scores"]) == 9
    assert len(parsed["reasons"]) == 9

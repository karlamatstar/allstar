"""프로필에 지정된 독립 Judge로 VOC 공통 9항목·100점 평가를 수행한다."""

from __future__ import annotations

import os
from typing import Any

from allstar.shared.model_profiles import ModelSpec
from allstar.voc.evaluation.judge_prompt import (
    build_judge_prompt,
    decide_verdict,
    parse_judge_response,
)
from allstar.voc.evaluation.runtime_support import load_json


RUBRIC_VERSION = "voc_9x100_v1"


def _analysis_text(result: dict[str, Any] | str, elapsed_seconds: float | None = None) -> str:
    """실시간 파이프라인의 6단계 산출물을 테스트케이스 Judge와 같은 형식으로 묶는다."""
    if isinstance(result, str):
        return result
    elapsed = elapsed_seconds
    if elapsed is None:
        elapsed = result.get("elapsed_seconds")
    return (
        f"[Interpreter 의도]\n{result.get('intent_json', '{}')}\n\n"
        f"[Retriever 및 Agent 연계 추적]\n{result.get('trace', '')}\n\n"
        f"[Summarizer 요약]\n{result.get('summary', '')}\n\n"
        f"[Evaluator 평가]\n{result.get('eval_json', '{}')}\n\n"
        f"[Critic 검토]\n{result.get('summary_critic_json', '{}')}\n\n"
        f"[Improver 정책 개선안]\n{result.get('policy', '')}\n\n"
        f"[전체 응답시간]\n{elapsed if elapsed is not None else '기록 없음'}초"
    )


async def evaluate(
    question: str,
    result: dict[str, Any] | str,
    spec: ModelSpec,
    elapsed_seconds: float | None = None,
) -> dict[str, Any]:
    rubric = load_json("judge_rubric.json")
    prompt = build_judge_prompt(question, _analysis_text(result, elapsed_seconds), rubric)
    if spec.provider == "openai":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.responses.create(
            model=spec.model,
            input=prompt,
            reasoning={"effort": spec.reasoning},
            text={"verbosity": "low"},
            max_output_tokens=2200,
        )
        text = getattr(response, "output_text", "")
    elif spec.provider == "anthropic":
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        options: dict[str, Any] = {
            "model": spec.model,
            "max_tokens": 2200,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"effort": spec.reasoning},
        }
        if spec.thinking == "disabled":
            options["thinking"] = {"type": "disabled"}
        response = await client.messages.create(**options)
        text = "\n".join(
            block.text for block in response.content if getattr(block, "text", None)
        )
    else:
        raise ValueError(f"지원하지 않는 Judge 제공자: {spec.provider}")

    parsed = parse_judge_response(text, rubric)
    if parsed is None:
        raise ValueError("Judge 응답에서 유효한 9항목 채점 JSON을 찾지 못했습니다.")
    verdict = decide_verdict(parsed["total"], parsed["immediate_hold"], rubric)
    return {
        "schema_version": 2,
        "rubric_version": RUBRIC_VERSION,
        "rubric_max_score": rubric["total_max_score"],
        "scores": parsed["scores"],
        "reasons": parsed["reasons"],
        "total": parsed["total"],
        "verdict": verdict,
        "immediate_hold": parsed["immediate_hold"],
        "hold_reason": parsed["hold_reason"],
        "rationale": parsed["rationale"],
        "provider": spec.provider,
        "model": spec.model,
        "reasoning": spec.reasoning,
        "thinking": spec.thinking,
    }

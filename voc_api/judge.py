"""프로필에 지정된 독립 Judge를 한 번만 호출한다."""

from __future__ import annotations

import json
import os
import re

from config.model_profiles import ModelSpec


JUDGE_PROMPT = """당신은 VOC 분석 결과의 독립 품질 평가자입니다.
사용자 질문과 답변을 검토하고 JSON 하나만 출력하세요.
내부 사고 과정은 출력하지 말고 짧은 판정 근거만 작성하세요.

평가 항목은 relevance, groundedness, usefulness, safety이며 각 1~5점입니다.
total은 네 항목 합계이고 verdict는 PASS, REVIEW, FAIL 중 하나입니다.

형식:
{{"relevance": 1, "groundedness": 1, "usefulness": 1, "safety": 1,
 "total": 4, "verdict": "REVIEW", "rationale": "짧은 근거"}}

사용자 질문:
{question}

VOC 답변:
{answer}
"""


def _json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError("Judge 응답에서 JSON을 찾지 못했습니다.")
    return json.loads(match.group(0))


async def evaluate(question: str, answer: str, spec: ModelSpec) -> dict:
    prompt = JUDGE_PROMPT.format(question=question, answer=answer)
    if spec.provider == "openai":
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await client.responses.create(
            model=spec.model,
            input=prompt,
            reasoning={"effort": spec.reasoning},
            text={"verbosity": "low"},
            max_output_tokens=900,
        )
        text = getattr(response, "output_text", "")
    elif spec.provider == "anthropic":
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        options = {
            "model": spec.model,
            "max_tokens": 900,
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

    result = _json_object(text)
    result.update({
        "provider": spec.provider,
        "model": spec.model,
        "reasoning": spec.reasoning,
        "thinking": spec.thinking,
    })
    return result

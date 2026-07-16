"""일반 실행과 교차검증 실행에 맞는 생성 LLM을 선택한다."""

from __future__ import annotations

import os


def _value(execution, name: str, default: str = "") -> str:
    if execution is None:
        return default
    if isinstance(execution, dict):
        return str(execution.get(name) or default)
    return str(getattr(execution, name, "") or default)


def generation_provider(default_provider: str, execution=None) -> str:
    """교차검증 지정값이 있으면 사용하고, 없으면 에이전트 기존 제공자를 유지한다."""
    provider = _value(
        execution,
        "provider",
        os.environ.get("GENERATION_PROVIDER", default_provider),
    ).lower()
    if provider not in {"openai", "anthropic"}:
        raise ValueError(f"지원하지 않는 생성 제공자: {provider}")
    return provider


def make_generation_chat(default_provider: str, model: str | None = None, execution=None):
    provider = generation_provider(default_provider, execution)
    requested_model = _value(execution, "model", model or "") or model
    reasoning = _value(execution, "reasoning", "")
    thinking = _value(execution, "thinking", "disabled")
    attempts = int(os.environ.get("LLM_MAX_ATTEMPTS", "3"))
    if provider == "openai":
        from llm_wrappers.openai_chat import OpenAIChat

        return OpenAIChat(
            model=requested_model or os.environ.get("OPENAI_MODEL", "gpt-5.2"),
            max_attempts=attempts,
            reasoning_effort=reasoning or os.environ.get("OPENAI_REASONING_EFFORT", "none"),
        )

    from llm_wrappers.anthropic_chat import AnthropicChat

    return AnthropicChat(
        model=requested_model or os.environ.get("A2A_MODEL_POLICY", "claude-sonnet-5"),
        fallback_to_openai=None,
        effort=reasoning or os.environ.get("ANTHROPIC_EFFORT_POLICY", "low"),
        thinking=thinking,
        max_attempts=attempts,
    )

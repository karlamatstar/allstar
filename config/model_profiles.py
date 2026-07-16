"""VOC 챗봇과 QA가 함께 사용하는 A~D 모델 프로필의 단일 원본."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str
    reasoning: str
    thinking: str = "disabled"


@dataclass(frozen=True)
class ModelProfile:
    profile_id: str
    title: str
    summary: str
    generation: ModelSpec
    judge: ModelSpec
    recommended: bool = False

    def snapshot(self) -> dict:
        return asdict(self)


def _models() -> dict[str, ModelSpec]:
    return {
        "openai_generation": ModelSpec(
            "openai",
            os.getenv("VOC_OPENAI_GENERATION_MODEL", "gpt-5.6-luna"),
            os.getenv("VOC_OPENAI_GENERATION_REASONING", "none"),
        ),
        "openai_judge": ModelSpec(
            "openai",
            os.getenv("VOC_OPENAI_JUDGE_MODEL", "gpt-5.6-terra"),
            os.getenv("VOC_OPENAI_JUDGE_REASONING", "low"),
        ),
        "anthropic_generation": ModelSpec(
            "anthropic",
            os.getenv("VOC_ANTHROPIC_GENERATION_MODEL", "claude-sonnet-4-6"),
            os.getenv("VOC_ANTHROPIC_GENERATION_EFFORT", "low"),
            os.getenv("VOC_ANTHROPIC_THINKING", "disabled"),
        ),
        "anthropic_judge": ModelSpec(
            "anthropic",
            os.getenv("VOC_ANTHROPIC_JUDGE_MODEL", "claude-sonnet-5"),
            os.getenv("VOC_ANTHROPIC_JUDGE_EFFORT", "low"),
            os.getenv("VOC_ANTHROPIC_THINKING", "disabled"),
        ),
    }


def profiles() -> dict[str, ModelProfile]:
    model = _models()
    return {
        "A": ModelProfile(
            "A", "기본 권장", "OpenAI가 답변을 만들고 Anthropic이 독립 평가",
            model["openai_generation"], model["anthropic_judge"], True,
        ),
        "B": ModelProfile(
            "B", "역방향 교차 평가", "Anthropic이 답변을 만들고 OpenAI가 독립 평가",
            model["anthropic_generation"], model["openai_judge"],
        ),
        "C": ModelProfile(
            "C", "OpenAI 계열 비교", "OpenAI 안에서 생성 모델과 평가 모델을 분리",
            model["openai_generation"], model["openai_judge"],
        ),
        "D": ModelProfile(
            "D", "Anthropic 계열 비교", "Anthropic 안에서 생성 모델과 평가 모델을 분리",
            model["anthropic_generation"], model["anthropic_judge"],
        ),
    }


def get_profile(profile_id: str) -> ModelProfile:
    key = (profile_id or "A").upper()
    try:
        return profiles()[key]
    except KeyError as error:
        raise ValueError(f"지원하지 않는 모델 프로필: {profile_id}") from error


def public_profiles() -> list[dict]:
    return [profile.snapshot() for profile in profiles().values()]


def missing_keys(profile: ModelProfile) -> list[str]:
    required = {
        spec.provider
        for spec in (profile.generation, profile.judge)
    }
    key_names = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
    return [key_names[name] for name in sorted(required) if not os.getenv(key_names[name])]

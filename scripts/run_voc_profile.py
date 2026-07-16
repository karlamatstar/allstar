"""QA GUI에서 승인된 대표 2건만 A~D 프로필로 실행한다."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from config.model_profiles import get_profile  # noqa: E402

CASES = ("TC-01", "TC-02")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=list("ABCD"))
    args = parser.parse_args()
    profile = get_profile(args.profile)
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(ROOT), str(ROOT / "voc"), env.get("PYTHONPATH", "")]),
        "GENERATION_PROVIDER": profile.generation.provider,
        "OPENAI_MODEL": profile.generation.model if profile.generation.provider == "openai" else env.get("OPENAI_MODEL", "gpt-5.6-luna"),
        "A2A_MODEL_POLICY": profile.generation.model if profile.generation.provider == "anthropic" else env.get("A2A_MODEL_POLICY", "claude-sonnet-4-6"),
        "OPENAI_REASONING_EFFORT": profile.generation.reasoning,
        "ANTHROPIC_EFFORT_POLICY": profile.generation.reasoning,
        "ANTHROPIC_THINKING_POLICY": profile.generation.thinking,
        "JUDGE_PROVIDER": profile.judge.provider,
        "JUDGE_LOCK_PROVIDER": "1",
        "JUDGE_OPENAI_MODEL": profile.judge.model if profile.judge.provider == "openai" else env.get("JUDGE_OPENAI_MODEL", "gpt-5.6-terra"),
        "JUDGE_ANTHROPIC_MODEL": profile.judge.model if profile.judge.provider == "anthropic" else env.get("JUDGE_ANTHROPIC_MODEL", "claude-sonnet-5"),
        "ANTHROPIC_EFFORT_JUDGE": profile.judge.reasoning,
        "ANTHROPIC_THINKING_JUDGE": profile.judge.thinking,
        "CROSS_VALIDATION_EXPERIMENT": profile.profile_id,
    })
    print(f"[{profile.profile_id}] {profile.summary}")
    print(f"생성: {profile.generation.provider}/{profile.generation.model}/{profile.generation.reasoning}")
    print(f"평가: {profile.judge.provider}/{profile.judge.model}/{profile.judge.reasoning}")
    print(f"대표 케이스: {', '.join(CASES)}")
    for case_id in CASES:
        print(f"\n===== {case_id} 시작 =====", flush=True)
        result = subprocess.run(
            [sys.executable, "voc/quality_diagnosis/llm_judge.py", "--case-id", case_id,
             "--output-dir", f"quality/reports/voc/testcase/{profile.profile_id.lower()}/{case_id}"],
            cwd=ROOT, env=env,
        )
        if result.returncode:
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""QA GUI에서 승인된 대표 2건만 A~D 프로필로 실행한다."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
from allstar.shared.model_profiles import get_profile  # noqa: E402
from allstar.shared.paths import MANIFEST_ROOT, VOC_LOG_ROOT, VOC_REPORT_ROOT  # noqa: E402

CASES = ("TC-01", "TC-02")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=list("ABCD"))
    args = parser.parse_args()
    profile = get_profile(args.profile)
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(SRC_ROOT), env.get("PYTHONPATH", "")]),
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
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    sources = []
    outputs = []
    for case_id in CASES:
        print(f"\n===== {case_id} 시작 =====", flush=True)
        report_dir = VOC_REPORT_ROOT / "testcase" / profile.profile_id.lower() / case_id
        log_dir = VOC_LOG_ROOT / "testcase" / profile.profile_id.lower() / case_id
        case_env = env.copy()
        case_env["VOC_JUDGE_LOG_DIR"] = str(log_dir)
        result = subprocess.run(
            [sys.executable, "-m", "allstar.voc.evaluation.llm_judge", "--case-id", case_id,
             "--output-dir", str(report_dir)],
            cwd=ROOT, env=case_env,
        )
        if result.returncode:
            return result.returncode
        sources.extend(str(path.relative_to(ROOT)) for path in sorted(log_dir.glob("*.json")))
        outputs.extend(str(path.relative_to(ROOT)) for path in sorted(report_dir.glob("*")) if path.is_file())

    manifest_dir = MANIFEST_ROOT
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "report_type": "voc_testcase",
        "run_id": run_id,
        "profile_id": profile.profile_id,
        "cases": list(CASES),
        "generation": profile.snapshot()["generation"],
        "judge": profile.snapshot()["judge"],
        "sources": sources,
        "outputs": outputs,
    }
    (manifest_dir / f"voc_testcase_{profile.profile_id.lower()}_{run_id}.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

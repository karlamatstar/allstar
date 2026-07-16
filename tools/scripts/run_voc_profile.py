"""QA GUI에서 승인된 대표 2건만 A~D 프로필로 실행한다."""

from __future__ import annotations

import argparse
import csv
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


def judge_report_failed(path: Path) -> bool:
    if not path.exists():
        return True
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return not rows or any(row.get("verdict") == "미평가(API 실패)" for row in rows)


def judge_failure_ids(path: Path) -> list[str]:
    if not path.exists():
        return list(CASES)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_id = {row.get("case_id"): row for row in rows}
    return [
        case_id for case_id in CASES
        if case_id not in by_id or by_id[case_id].get("verdict") in {
            "미평가(API 실패)", "미평가(파이프라인 실패)", "파싱 실패",
        }
    ]


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def build_judge_command(report_dir: Path) -> list[str]:
    return [
        sys.executable, "-m", "allstar.voc.evaluation.llm_judge",
        *[part for case_id in CASES for part in ("--case-id", case_id)],
        "--output-dir", str(report_dir),
    ]


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
        "ALLSTAR_VOC_PROFILE_SNAPSHOT": json.dumps(profile.snapshot(), ensure_ascii=False),
    })
    print(f"[{profile.profile_id}] {profile.summary}")
    print(f"생성: {profile.generation.provider}/{profile.generation.model}/{profile.generation.reasoning}")
    print(f"평가: {profile.judge.provider}/{profile.judge.model}/{profile.judge.reasoning}")
    print(f"대표 케이스: {', '.join(CASES)}")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    report_dir = VOC_REPORT_ROOT / "testcase" / profile.profile_id.lower()
    log_dir = VOC_LOG_ROOT / "testcase" / profile.profile_id.lower() / run_id
    env["VOC_JUDGE_LOG_DIR"] = str(log_dir)
    env["VOC_REPORT_RUN_ID"] = run_id
    command = build_judge_command(report_dir)
    result = subprocess.run(command, cwd=ROOT, env=env)
    judge_logs = sorted(log_dir.glob("llm_judge_*.json"), key=lambda path: path.stat().st_mtime)
    if judge_logs:
        from allstar.voc.evaluation.profile_report import rebuild_profile_report_from_log

        rebuild_profile_report_from_log(judge_logs[-1], report_dir, profile)
    judge_csv = report_dir / "llm_judge_result.csv"
    judge_failures = judge_failure_ids(judge_csv)
    sources = [str(path.relative_to(ROOT)) for path in sorted(log_dir.glob("*.json"))]
    output_paths = [
        report_dir / "quality_score_report.md",
        report_dir / "llm_judge_result.csv",
        report_dir / "llm_judge_result.json",
        *sorted((report_dir / "assets").glob("*.png")),
    ]
    outputs = [str(path.relative_to(ROOT)) for path in output_paths if path.exists()]

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
        "status": "failed" if judge_failures else "completed",
        "judge_failures": judge_failures,
        "sources": sources,
        "outputs": outputs,
    }
    profile_manifest = report_dir / "report_manifest.json"
    global_manifest = manifest_dir / f"voc_testcase_{profile.profile_id.lower()}.json"
    _atomic_json(profile_manifest, manifest)
    _atomic_json(global_manifest, manifest)
    from allstar.voc.evaluation.cross_validation import _update_comparison_report

    _update_comparison_report()
    if result.returncode:
        return result.returncode
    if judge_failures:
        print(f"독립 LLM Judge 실패 사례: {', '.join(judge_failures)}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

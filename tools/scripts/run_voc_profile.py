"""QA GUI에서는 전체 VOC 테스트케이스를, 개발 검증에서는 지정 사례만 실행한다."""

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
from allstar.voc.evaluation.progress import finish_progress, initialize_progress  # noqa: E402
from allstar.voc.evaluation.runtime_support import load_test_cases  # noqa: E402


def resolve_case_ids(requested: list[str] | tuple[str, ...] | None = None) -> tuple[str, ...]:
    """미지정 시 전체 케이스를, 지정 시 파일 정의 순서의 선택 케이스를 반환한다."""
    all_ids = tuple(case["case_id"] for case in load_test_cases())
    if not requested:
        return all_ids
    selected = set(requested)
    missing = [case_id for case_id in requested if case_id not in all_ids]
    if missing:
        raise ValueError(f"존재하지 않는 테스트 케이스: {', '.join(missing)}")
    return tuple(case_id for case_id in all_ids if case_id in selected)


def judge_report_failed(path: Path) -> bool:
    if not path.exists():
        return True
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return not rows or any(row.get("verdict") == "미평가(API 실패)" for row in rows)


def judge_failure_ids(path: Path, case_ids: tuple[str, ...]) -> list[str]:
    if not path.exists():
        return list(case_ids)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_id = {row.get("case_id"): row for row in rows}
    return [
        case_id for case_id in case_ids
        if case_id not in by_id or by_id[case_id].get("verdict") in {
            "미평가(API 실패)", "미평가(파이프라인 실패)", "파싱 실패",
        }
    ]


def _atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def build_judge_command(
    report_dir: Path,
    case_ids: list[str] | tuple[str, ...] | None = None,
) -> list[str]:
    selected = resolve_case_ids(case_ids)
    return [
        sys.executable, "-m", "allstar.voc.evaluation.llm_judge",
        *[part for case_id in selected for part in ("--case-id", case_id)],
        "--output-dir", str(report_dir),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=list("ABCD"))
    parser.add_argument(
        "--case-id",
        action="append",
        help="실행할 테스트케이스 ID. 생략하면 등록된 전체 케이스를 실행한다.",
    )
    parser.add_argument("--run-id", help="대시보드 진행 상태와 실행 로그를 연결할 실행 ID")
    args = parser.parse_args()
    case_ids = resolve_case_ids(args.case_id)
    case_id_set = set(case_ids)
    selected_cases = [case for case in load_test_cases() if case["case_id"] in case_id_set]
    profile = get_profile(args.profile)
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    initialize_progress(run_id, profile.profile_id, selected_cases)
    env = os.environ.copy()
    env.update({
        "PYTHONPATH": os.pathsep.join([str(SRC_ROOT), env.get("PYTHONPATH", "")]),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
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
        "ALLSTAR_VOC_PROGRESS_RUN_ID": run_id,
    })
    print(f"[{profile.profile_id}] {profile.summary}")
    print(f"생성: {profile.generation.provider}/{profile.generation.model}/{profile.generation.reasoning}")
    print(f"평가: {profile.judge.provider}/{profile.judge.model}/{profile.judge.reasoning}")
    scope = "전체" if not args.case_id else "지정"
    print(f"실행 테스트케이스: {scope} {len(case_ids)}건 ({', '.join(case_ids)})")
    report_dir = VOC_REPORT_ROOT / "testcase" / profile.profile_id.lower()
    log_dir = VOC_LOG_ROOT / "testcase" / profile.profile_id.lower() / run_id
    env["VOC_JUDGE_LOG_DIR"] = str(log_dir)
    env["VOC_REPORT_RUN_ID"] = run_id
    command = build_judge_command(report_dir, case_ids)
    result = subprocess.run(command, cwd=ROOT, env=env)
    judge_logs = sorted(log_dir.glob("llm_judge_*.json"), key=lambda path: path.stat().st_mtime)
    if judge_logs:
        from allstar.voc.evaluation.profile_report import rebuild_profile_report_from_log

        rebuild_profile_report_from_log(judge_logs[-1], report_dir, profile)
    judge_csv = report_dir / "llm_judge_result.csv"
    judge_failures = judge_failure_ids(judge_csv, case_ids)
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
        "cases": list(case_ids),
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
    final_status = "failed" if result.returncode or judge_failures else "completed"
    finish_progress(
        run_id,
        final_status,
        f"독립 LLM Judge 실패 사례: {', '.join(judge_failures)}" if judge_failures else None,
    )
    if result.returncode:
        return result.returncode
    if judge_failures:
        print(f"독립 LLM Judge 실패 사례: {', '.join(judge_failures)}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

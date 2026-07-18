"""VOC 프로필별 완료 테스트케이스 실행 원본 로그 보관."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from allstar.shared.log_retention import compress_completed_run_sources
from allstar.shared.paths import PROJECT_ROOT


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _atomic_manifest(path: Path, payload: dict) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def archive_old_profile_runs(profile_root: Path, *, keep_recent: int = 5) -> dict[Path, list[Path]]:
    archived = compress_completed_run_sources(
        profile_root,
        keep_recent=keep_recent,
        source_patterns=("llm_judge_*.json", "*.jsonl", "*.log"),
    )
    result: dict[Path, list[Path]] = {}
    for run_dir, pairs in archived.items():
        manifest_path = run_dir / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.setdefault("log_retention_sort_timestamp_ns", manifest_path.stat().st_mtime_ns)
        replacements = {_relative(source): _relative(target) for source, target in pairs}
        manifest["sources"] = [replacements.get(str(source), str(source)) for source in manifest.get("sources", [])]
        previous = list(manifest.get("compressed_sources") or [])
        for source, target in pairs:
            record = {"source": _relative(source), "archive": _relative(target)}
            if record not in previous:
                previous.append(record)
        manifest["compressed_sources"] = previous
        _atomic_manifest(manifest_path, manifest)
        result[run_dir] = [target for _, target in pairs]
    return result

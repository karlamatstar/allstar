"""AI 테스트케이스 완료 실행 원본 로그 보관."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from allstar.shared.log_retention import compress_old_files, read_json
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


def archive_old_batch_logs(log_dir: Path, manifest_dir: Path, *, keep_recent: int = 5) -> list[Path]:
    candidates = [
        path
        for path in log_dir.glob("ai_agent_batch_*.json")
        if (manifest_dir / path.name).exists()
    ]
    archived = compress_old_files(candidates, keep_recent=keep_recent, lock_root=log_dir)
    for archive in archived:
        source = archive.with_suffix("")
        manifest_path = manifest_dir / source.name
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["source"] = _relative(archive)
        manifest["compressed_source"] = {
            "source": _relative(source),
            "archive": _relative(archive),
        }
        _atomic_manifest(manifest_path, manifest)
    return archived


def load_batch_log(path: Path) -> dict:
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValueError(f"AI 테스트케이스 로그 형식이 올바르지 않습니다: {path}")
    return data

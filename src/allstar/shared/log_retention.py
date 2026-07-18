"""날짜별 JSONL 저장, GZIP 조회와 검증된 로그 압축 공통 기능."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import threading
import uuid
from collections import Counter
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from zoneinfo import ZoneInfo

from allstar.shared.paths import SERVICE_LOG_ROOT


DEFAULT_KEEP_RECENT = 5
LOG_TIMEZONE = ZoneInfo(os.getenv("ALLSTAR_LOG_TIMEZONE", "Asia/Seoul"))
ARCHIVE_EVENT_LOG = SERVICE_LOG_ROOT / "log_archive_events.jsonl"
_EVENT_LOCK = threading.Lock()
_PROCESS_LOCK = threading.RLock()


def local_date(value: datetime | None = None) -> date:
    current = value or datetime.now(LOG_TIMEZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=LOG_TIMEZONE)
    return current.astimezone(LOG_TIMEZONE).date()


def date_from_timestamp(value: Any, *, fallback: date | None = None) -> date:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(LOG_TIMEZONE).date()
    except (TypeError, ValueError):
        return fallback or local_date()


def daily_path(directory: Path, value: datetime | None = None) -> Path:
    return directory / f"{local_date(value):%Y-%m-%d}.jsonl"


def _daily_key(path: Path) -> str | None:
    name = path.name
    if name.endswith(".jsonl.gz"):
        name = name[:-9]
    elif name.endswith(".jsonl"):
        name = name[:-6]
    else:
        return None
    try:
        return date.fromisoformat(name).isoformat()
    except ValueError:
        return None


def open_log_text(path: Path, mode: str = "rt"):
    if "b" not in mode and "t" not in mode:
        mode += "t"
    if path.name.endswith(".gz"):
        return gzip.open(path, mode) if "b" in mode else gzip.open(path, mode, encoding="utf-8")
    return path.open(mode) if "b" in mode else path.open(mode, encoding="utf-8")


def read_log_text(path: Path, *, errors: str = "strict") -> str:
    if path.name.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors=errors) as stream:
            return stream.read()
    return path.read_text(encoding="utf-8", errors=errors)


def read_json(path: Path) -> Any:
    return json.loads(read_log_text(path))


def read_jsonl(path: Path, *, tolerate_invalid: bool = True) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in read_log_text(path, errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            if tolerate_invalid:
                continue
            raise
        if isinstance(row, dict):
            rows.append(row)
    return rows


def daily_log_paths(directory: Path) -> list[Path]:
    """같은 날짜에 원본과 GZIP이 함께 있으면 원본 하나만 반환한다."""
    selected: dict[str, Path] = {}
    if not directory.exists():
        return []
    for path in sorted(directory.iterdir()):
        if not path.is_file():
            continue
        key = _daily_key(path)
        if key is None:
            continue
        previous = selected.get(key)
        if previous is None or (previous.name.endswith(".gz") and not path.name.endswith(".gz")):
            selected[key] = path
    return [selected[key] for key in sorted(selected)]


def read_daily_jsonl(directory: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = daily_log_paths(directory)
    if directory.exists():
        for legacy in sorted(directory.glob("*.jsonl")):
            if _daily_key(legacy) is None and not migration_manifest_path(directory, legacy.name).exists():
                paths.append(legacy)
    for path in paths:
        rows.extend(read_jsonl(path))
    return rows


def append_daily_jsonl(
    directory: Path,
    record: dict[str, Any],
    *,
    value: datetime | None = None,
    lock: threading.Lock | threading.RLock | None = None,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = daily_path(directory, value)
    line = json.dumps(record, ensure_ascii=False, default=str)
    active_lock = lock or _PROCESS_LOCK
    with active_lock, path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    return path


def _sha256(path: Path, *, compressed: bool = False) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    opener = gzip.open if compressed else open
    with opener(path, "rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _record_event(event: str, **details: Any) -> None:
    payload = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "event": event,
        **details,
    }
    ARCHIVE_EVENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _EVENT_LOCK, ARCHIVE_EVENT_LOG.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


@contextmanager
def _filesystem_lock(root: Path) -> Iterator[bool]:
    lock_path = root / ".log-compression.lock"
    root.mkdir(parents=True, exist_ok=True)
    descriptor: int | None = None
    for attempt in range(2):
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            age_seconds = datetime.now().timestamp() - lock_path.stat().st_mtime
            if attempt == 0 and age_seconds > 600:
                lock_path.unlink(missing_ok=True)
                continue
            yield False
            return
    if descriptor is None:
        yield False
        return
    try:
        os.write(descriptor, str(os.getpid()).encode("ascii", errors="ignore"))
        os.close(descriptor)
        yield True
    finally:
        lock_path.unlink(missing_ok=True)


def compress_verified(source: Path) -> Path:
    """내용 해시를 검증한 뒤 source를 같은 이름의 .gz로 교체한다."""
    if source.name.endswith(".gz"):
        return source
    target = source.with_name(source.name + ".gz")
    source_hash, source_size = _sha256(source)
    if target.exists():
        target_hash, target_size = _sha256(target, compressed=True)
        if (source_hash, source_size) != (target_hash, target_size):
            raise RuntimeError(f"기존 압축 파일과 원본 내용이 다릅니다: {target}")
        source.unlink()
        return target

    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        with source.open("rb") as reader, gzip.open(temporary, "wb", compresslevel=6) as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
        target_hash, target_size = _sha256(temporary, compressed=True)
        if (source_hash, source_size) != (target_hash, target_size):
            raise RuntimeError(f"압축 검증에 실패했습니다: {source}")
        os.replace(temporary, target)
        source.unlink()
    finally:
        temporary.unlink(missing_ok=True)
    _record_event(
        "log_compressed",
        source=str(source),
        archive=str(target),
        original_bytes=source_size,
        compressed_bytes=target.stat().st_size,
        sha256=source_hash,
    )
    return target


def compress_daily_groups(
    directories: Sequence[Path],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    current_date: date | None = None,
) -> list[Path]:
    roots = [Path(directory) for directory in directories]
    activity_dates = sorted(
        {
            key
            for directory in roots
            for path in daily_log_paths(directory)
            if (key := _daily_key(path)) is not None
        }
    )
    keep = set(activity_dates[-max(0, keep_recent) :])
    keep.add((current_date or local_date()).isoformat())
    eligible = set(activity_dates) - keep
    if not eligible:
        return []
    common_root = Path(os.path.commonpath([str(path) for path in roots]))
    compressed: list[Path] = []
    with _filesystem_lock(common_root) as acquired:
        if not acquired:
            return []
        for directory in roots:
            for path in daily_log_paths(directory):
                if _daily_key(path) in eligible and path.name.endswith(".jsonl"):
                    try:
                        compressed.append(compress_verified(path))
                    except Exception as error:
                        _record_event("log_compression_failed", source=str(path), error=str(error))
                        raise
    return compressed


def compress_old_files(
    files: Iterable[Path],
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    lock_root: Path,
) -> list[Path]:
    candidates = sorted(
        [Path(path) for path in files if Path(path).is_file() and not Path(path).name.endswith(".gz")],
        key=lambda path: (path.stat().st_mtime_ns, path.name),
    )
    eligible = candidates[:-max(0, keep_recent)] if len(candidates) > keep_recent else []
    compressed: list[Path] = []
    with _filesystem_lock(lock_root) as acquired:
        if not acquired:
            return []
        for path in eligible:
            compressed.append(compress_verified(path))
    return compressed


def compress_completed_run_sources(
    run_root: Path,
    *,
    keep_recent: int = DEFAULT_KEEP_RECENT,
    source_patterns: Sequence[str] = ("*.json", "*.jsonl", "*.log"),
    manifest_name: str = "run_manifest.json",
) -> dict[Path, list[tuple[Path, Path]]]:
    """완료 manifest가 있는 최근 실행 5개를 제외하고 루트 원본 로그만 압축한다."""
    run_root = Path(run_root)
    completed: list[tuple[int, str, Path]] = []
    if not run_root.exists():
        return {}
    for run_dir in run_root.iterdir():
        manifest_path = run_dir / manifest_name
        if not run_dir.is_dir() or not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if str(manifest.get("status") or "") not in {"completed", "failed", "cancelled", "stopped"}:
            continue
        sort_timestamp = int(manifest.get("log_retention_sort_timestamp_ns") or manifest_path.stat().st_mtime_ns)
        completed.append((sort_timestamp, str(manifest.get("run_id") or run_dir.name), run_dir))
    completed.sort()
    eligible = completed[:-max(0, keep_recent)] if len(completed) > keep_recent else []
    archived: dict[Path, list[tuple[Path, Path]]] = {}
    with _filesystem_lock(run_root) as acquired:
        if not acquired:
            return {}
        for _, _, run_dir in eligible:
            sources: list[Path] = []
            for pattern in source_patterns:
                sources.extend(
                    path
                    for path in run_dir.glob(pattern)
                    if path.is_file()
                    and path.name != manifest_name
                    and not path.name.endswith(".gz")
                )
            pairs = [(source, compress_verified(source)) for source in sorted(set(sources))]
            if pairs:
                archived[run_dir] = pairs
    return archived


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def migration_manifest_path(directory: Path, legacy_name: str) -> Path:
    safe_name = legacy_name.replace(".", "_")
    return directory / f".migration-{safe_name}.json"


def migrate_legacy_jsonl(
    legacy_path: Path,
    daily_directory: Path,
    *,
    timestamp_fields: Sequence[str] = ("timestamp",),
) -> dict[str, Any] | None:
    """단일 누적 JSONL을 타임스탬프 기준 날짜 파일로 무손실 분리한다."""
    legacy_path = Path(legacy_path)
    daily_directory = Path(daily_directory)
    manifest_path = migration_manifest_path(daily_directory, legacy_path.name)
    if not legacy_path.exists():
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return None

    raw_bytes = legacy_path.read_bytes()
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    lines = [line for line in raw_bytes.decode("utf-8-sig").splitlines() if line.strip()]
    grouped: dict[str, list[str]] = {}
    fallback_date = datetime.fromtimestamp(legacy_path.stat().st_mtime, LOG_TIMEZONE).date()
    for line_number, line in enumerate(lines, start=1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError(
                f"기존 로그 {legacy_path}의 {line_number}번째 행을 해석할 수 없습니다."
            ) from error
        timestamp = next((row.get(field) for field in timestamp_fields if row.get(field)), None)
        key = date_from_timestamp(timestamp, fallback=fallback_date).isoformat()
        grouped.setdefault(key, []).append(line)

    daily_directory.mkdir(parents=True, exist_ok=True)
    backup_dir = daily_directory / "legacy"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{legacy_path.name}.gz"
    if not backup_path.exists():
        temporary_backup = backup_path.with_name(f".{backup_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with gzip.open(temporary_backup, "wb", compresslevel=6) as stream:
                stream.write(raw_bytes)
            backup_hash, backup_size = _sha256(temporary_backup, compressed=True)
            if backup_hash != source_hash or backup_size != len(raw_bytes):
                raise RuntimeError(f"기존 로그 백업 검증에 실패했습니다: {legacy_path}")
            os.replace(temporary_backup, backup_path)
        finally:
            temporary_backup.unlink(missing_ok=True)
    else:
        backup_hash, backup_size = _sha256(backup_path, compressed=True)
        if backup_hash != source_hash or backup_size != len(raw_bytes):
            raise RuntimeError(f"기존 로그 백업과 현재 원본이 다릅니다: {legacy_path}")

    daily_counts: dict[str, int] = {}
    for key, source_lines in sorted(grouped.items()):
        target = daily_directory / f"{key}.jsonl"
        compressed_target = target.with_name(target.name + ".gz")
        if target.exists():
            existing_lines = target.read_text(encoding="utf-8").splitlines()
        elif compressed_target.exists():
            existing_lines = read_log_text(compressed_target).splitlines()
        else:
            existing_lines = []
        existing_counts = Counter(existing_lines)
        source_counts = Counter(source_lines)
        additions = [
            line
            for line, count in source_counts.items()
            for _ in range(max(0, count - existing_counts[line]))
        ]
        merged_lines = [*existing_lines, *additions]
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text("\n".join(merged_lines) + ("\n" if merged_lines else ""), encoding="utf-8")
        os.replace(temporary, target)
        compressed_target.unlink(missing_ok=True)
        daily_counts[key] = len(source_lines)

    for key, source_lines in grouped.items():
        migrated_counts = Counter(
            (daily_directory / f"{key}.jsonl").read_text(encoding="utf-8").splitlines()
        )
        if any(migrated_counts[line] < count for line, count in Counter(source_lines).items()):
            raise RuntimeError(f"기존 로그 날짜 분리 검증에 실패했습니다: {legacy_path}")

    manifest = {
        "schema_version": 1,
        "status": "completed",
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "legacy_source": str(legacy_path),
        "legacy_backup": str(backup_path),
        "source_sha256": source_hash,
        "source_bytes": len(raw_bytes),
        "source_lines": len(lines),
        "daily_counts": daily_counts,
    }
    _atomic_json(manifest_path, manifest)
    legacy_path.unlink()
    _record_event(
        "legacy_log_migrated",
        source=str(legacy_path),
        backup=str(backup_path),
        lines=len(lines),
        daily_counts=daily_counts,
        sha256=source_hash,
    )
    return manifest

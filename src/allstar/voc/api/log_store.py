"""요청·채점 JSONL을 계열별로 즉시 저장한다."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path

from allstar.shared.paths import VOC_LOG_ROOT


LIVE_ROOT = VOC_LOG_ROOT / "live"
CONVERSATION_DIR = LIVE_ROOT / "conversations"
JUDGMENT_DIR = LIVE_ROOT / "judgments"
_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _append(directory: Path, record: dict) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{datetime.now():%Y-%m-%d}.jsonl"
    line = json.dumps(record, ensure_ascii=False, default=str)
    with _LOCK, path.open("a", encoding="utf-8") as stream:
        stream.write(line + "\n")
    return path


def conversation(record: dict) -> Path:
    return _append(CONVERSATION_DIR, record)


def judgment(record: dict) -> Path:
    return _append(JUDGMENT_DIR, record)

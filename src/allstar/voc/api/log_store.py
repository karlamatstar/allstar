"""요청·채점 JSONL을 계열별로 즉시 저장한다."""

from __future__ import annotations

import threading
import logging
from datetime import datetime
from pathlib import Path

from allstar.shared.paths import VOC_LOG_ROOT
from allstar.shared.log_retention import append_daily_jsonl, compress_daily_groups


LIVE_ROOT = VOC_LOG_ROOT / "live"
CONVERSATION_DIR = LIVE_ROOT / "conversations"
JUDGMENT_DIR = LIVE_ROOT / "judgments"
_LOCK = threading.Lock()
logger = logging.getLogger("voc.log_store")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def maintain_live_logs() -> None:
    compress_daily_groups((CONVERSATION_DIR, JUDGMENT_DIR))


def _compress_after_write() -> None:
    try:
        maintain_live_logs()
    except Exception as error:
        logger.warning("VOC 라이브 로그 자동 압축 실패: %s", error)


def _append(directory: Path, record: dict) -> Path:
    path = append_daily_jsonl(directory, record, lock=_LOCK)
    _compress_after_write()
    return path


def conversation(record: dict) -> Path:
    return _append(CONVERSATION_DIR, record)


def judgment(record: dict) -> Path:
    return _append(JUDGMENT_DIR, record)

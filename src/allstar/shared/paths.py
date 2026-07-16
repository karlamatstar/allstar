"""AllStar 프로젝트의 소스·로그·리포트 경로 단일 원본."""

from __future__ import annotations

import os
from pathlib import Path


def _path_from_env(name: str, default: Path) -> Path:
    configured = os.getenv(name)
    return Path(configured).expanduser().resolve() if configured else default.resolve()


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = _path_from_env("ALLSTAR_PROJECT_ROOT", SRC_ROOT.parent)

OUTPUT_ROOT = _path_from_env("ALLSTAR_OUTPUT_ROOT", PROJECT_ROOT / "_OUTPUT")
LOG_ROOT = OUTPUT_ROOT / "logs"
REPORT_ROOT = OUTPUT_ROOT / "reports"

AI_AGENT_LOG_ROOT = LOG_ROOT / "ai_agent"
AI_AGENT_REPORT_ROOT = REPORT_ROOT / "ai_agent"
VOC_LOG_ROOT = LOG_ROOT / "voc"
VOC_REPORT_ROOT = REPORT_ROOT / "voc"
SERVICE_LOG_ROOT = LOG_ROOT / "services"
MANIFEST_ROOT = REPORT_ROOT / "manifests"

RUN_ROOT = PROJECT_ROOT / "RUN"
TOOLS_ROOT = PROJECT_ROOT / "tools"
OPS_ROOT = PROJECT_ROOT / "ops"
VOC_DATA_ROOT = PACKAGE_ROOT / "voc" / "data"

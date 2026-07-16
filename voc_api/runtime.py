"""VOC gRPC 파이프라인 연결 어댑터."""

from __future__ import annotations

import sys
from pathlib import Path

from config.model_profiles import ModelProfile


ROOT = Path(__file__).resolve().parent.parent
VOC_ROOT = ROOT / "voc"


class PipelineRunner:
    async def run(self, question: str, profile: ModelProfile) -> dict:
        if str(VOC_ROOT) not in sys.path:
            sys.path.insert(0, str(VOC_ROOT))
        from grpc_server import VOCGRPCRuntime

        return await VOCGRPCRuntime().run_with_question(
            question=question,
            csv_path=None,
            timeout=180.0,
            model_profile=profile.snapshot(),
        )

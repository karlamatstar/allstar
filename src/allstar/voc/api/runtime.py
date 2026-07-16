"""VOC gRPC 파이프라인 연결 어댑터."""

from __future__ import annotations

from allstar.shared.model_profiles import ModelProfile


class PipelineRunner:
    async def run(self, question: str, profile: ModelProfile) -> dict:
        from allstar.voc.runtime.grpc_runtime import VOCGRPCRuntime

        return await VOCGRPCRuntime().run_with_question(
            question=question,
            csv_path=None,
            timeout=180.0,
            model_profile=profile.snapshot(),
        )

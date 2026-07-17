"""VOC gRPC 파이프라인 연결 어댑터."""

from __future__ import annotations

from allstar.shared.model_profiles import ModelProfile


class PipelineRunner:
    async def run(
        self,
        question: str,
        profile: ModelProfile,
        progress_run_id: str | None = None,
        progress_case_id: str | None = None,
    ) -> dict:
        from allstar.voc.runtime.grpc_runtime import VOCGRPCRuntime

        return await VOCGRPCRuntime().run_with_question(
            question=question,
            csv_path=None,
            timeout=180.0,
            retry_on_no_data=True,
            model_profile=profile.snapshot(),
            progress_run_id=progress_run_id,
            progress_case_id=progress_case_id,
        )

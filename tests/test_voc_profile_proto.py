import sys
from pathlib import Path


VOC_ROOT = Path(__file__).resolve().parent.parent / "voc"
sys.path.insert(0, str(VOC_ROOT))
import voc_pb2  # noqa: E402


def test_generation_profile_can_be_carried_by_pipeline_request():
    execution = voc_pb2.ModelExecutionConfig(
        provider="anthropic",
        model="claude-sonnet-4-6",
        reasoning="low",
        thinking="disabled",
    )
    request = voc_pb2.RunPipelineReq(
        csv_path="voc.csv",
        filters=["배송"],
        max_items=30,
        task="both",
        generation=execution,
    )
    assert request.generation.provider == "anthropic"
    assert request.generation.model == "claude-sonnet-4-6"
    assert request.generation.thinking == "disabled"

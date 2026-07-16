from allstar.voc.protocol import voc_pb2


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

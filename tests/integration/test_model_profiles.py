from allstar.shared.model_profiles import get_profile, profiles


def test_abcd_profiles_have_separate_generation_and_judge_roles():
    values = profiles()
    assert list(values) == ["A", "B", "C", "D"]
    assert values["A"].generation.provider == "openai"
    assert values["A"].judge.provider == "anthropic"
    assert values["B"].generation.provider == "anthropic"
    assert values["B"].judge.provider == "openai"
    assert values["C"].generation.model != values["C"].judge.model
    assert values["D"].generation.model != values["D"].judge.model


def test_profile_lookup_is_case_insensitive_and_rejects_unknown():
    assert get_profile("a").profile_id == "A"
    try:
        get_profile("Z")
    except ValueError as error:
        assert "지원하지 않는" in str(error)
    else:
        raise AssertionError("알 수 없는 프로필이 허용됨")

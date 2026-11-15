import pytest

from services.openai_utils import get_minimal_reasoning_by_model


@pytest.mark.parametrize("model", ["gpt-6-luna", "gpt-6.1-terra", "gpt-6.1-sol"])
def test_gpt_6_models_get_reasoning_none(model):
    # gpt-6 reasons by default, and chat completions rejects function tools
    # unless reasoning_effort is "none".
    assert get_minimal_reasoning_by_model(model) == {"reasoning_effort": "none"}


def test_gpt_4_1_mini_gets_no_reasoning_param():
    assert get_minimal_reasoning_by_model("gpt-4.1-mini") == {}

import pytest

from macos_swap_killer.llm import parse_llm_response
from macos_swap_killer.models import DecisionAction


def test_parse_llm_response_json() -> None:
    response = parse_llm_response(
        """
        {
          "overall_risk": "low",
          "decisions": [
            {
              "pid": 123,
              "process_name": "Code Helper",
              "action": "TERMINATE",
              "risk": "low",
              "reason": "renderer helper",
              "expected_memory_mb": 512
            }
          ]
        }
        """
    )
    assert response.decisions[0].action == DecisionAction.TERMINATE


def test_parse_llm_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_llm_response("not json")

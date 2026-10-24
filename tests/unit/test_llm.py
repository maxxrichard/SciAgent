import json

import httpx
import pytest

from sciagent.core.config import Settings
from sciagent.llm import build_llm
from sciagent.llm.base import openai_tool_specs
from sciagent.llm.openai_compat import LLMUnavailable, OpenAICompatibleLLM, _parse_args
from sciagent.llm.rule_based import RuleBasedLLM


@pytest.fixture
def specs(registry):
    return registry.specs()


def plan(q):
    return [(c.name, c.arguments) for c in RuleBasedLLM().plan(q)]


@pytest.mark.parametrize(
    "question,expected",
    [
        ("count cells in IMG-0001", [("segment_cells", {"sample_id": "IMG-0001"})]),
        ("texture features for IMG-0002", [("extract_image_features", {"sample_id": "IMG-0002"})]),
        (
            "high-impact variants in BRCA2 for WGS-0003",
            [
                (
                    "annotate_variants",
                    {"sample_id": "WGS-0003", "genes": ["BRCA2"], "min_impact": "HIGH"},
                )
            ],
        ),
        ("QC for SC-0009", [("expression_qc", {"sample_id": "SC-0009"})]),
        (
            "temperature trend for PT-00001",
            [("detect_vital_anomalies", {"patient_id": "PT-00001", "signal": "temp_c"})],
        ),
        (
            "how many patients under 40 with stroke in the treatment arm?",
            [
                (
                    "build_cohort",
                    {"diagnosis": "stroke", "max_age": 39, "treatment_arm": "treatment"},
                )
            ],
        ),
        (
            "cohort of men aged 30 to 50",
            [("build_cohort", {"min_age": 30, "max_age": 50, "sex": "M"})],
        ),
        (
            "mortality by gender for copd",
            [("survival_analysis", {"diagnosis": "copd", "compare_by": "sex"})],
        ),
        (
            "convert HGB 8 mmol/L to canonical units",
            [("harmonise_records", {"records": [{"code": "HGB", "value": 8.0, "unit": "mmol/L"}]})],
        ),
    ],
)
def test_rule_based_planning(question, expected):
    assert plan(question) == expected


def test_rule_based_round_trip(specs):
    llm = RuleBasedLLM()
    first = llm.chat([{"role": "user", "content": "cells in IMG-0001"}], specs)
    assert first.tool_calls and first.content is None and first.usage.prompt_tokens > 0
    tool_msg = {
        "role": "tool",
        "name": "segment_cells",
        "content": json.dumps(
            {"sample_id": "IMG-0001", "cell_count": 5, "threshold": 0.2, "mean_area_px": 30.0}
        ),
    }
    final = llm.chat([{"role": "user", "content": "cells in IMG-0001"}, tool_msg], specs)
    assert "5 nuclei" in final.content and not final.tool_calls


def test_rule_based_filters_unavailable_tools_and_reports_errors(specs):
    llm = RuleBasedLLM()
    res = llm.chat([{"role": "user", "content": "cells in IMG-0001"}], [])
    assert not res.tool_calls and "could not map" in res.content
    msgs = [
        {"role": "user", "content": "q"},
        {"role": "tool", "name": "x", "content": json.dumps({"error": "timeout"})},
        {"role": "tool", "name": "unknown_tool", "content": json.dumps({"a": 1})},
    ]
    text = llm.chat(msgs, specs).content
    assert "x could not be run: timeout" in text and "unknown_tool:" in text


def _client(handler):
    return OpenAICompatibleLLM(
        "http://vllm/v1",
        "m",
        client=httpx.Client(base_url="http://vllm/v1", transport=httpx.MockTransport(handler)),
    )


def test_openai_client_parses_tool_calls(specs):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "c1",
                                    "type": "function",
                                    "function": {
                                        "name": "segment_cells",
                                        "arguments": '{"sample_id": "IMG-0001"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 7},
            },
        )

    res = _client(handler).chat([{"role": "user", "content": "hi"}], specs)
    assert res.tool_calls[0].arguments == {"sample_id": "IMG-0001"}
    assert res.usage.prompt_tokens == 50 and seen["tool_choice"] == "auto"
    assert seen["tools"][0]["type"] == "function"


def test_openai_client_plain_answer_and_errors():
    ok = _client(lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]}))
    res = ok.chat([{"role": "user", "content": "x"}], [])
    assert res.content == "hi" and res.tool_calls == []
    bad = _client(lambda r: httpx.Response(503))
    with pytest.raises(LLMUnavailable):
        bad.chat([], [])


def test_parse_args_edge_cases():
    assert _parse_args(None) == {}
    assert _parse_args({"a": 1}) == {"a": 1}
    assert _parse_args("not json") == {"_raw": "not json"}
    assert _parse_args("[1]") == {"_raw": [1]}


def test_tool_spec_conversion(specs):
    out = openai_tool_specs(specs)
    assert out[0]["function"]["parameters"] == specs[0]["input_schema"]


def test_factory():
    assert isinstance(build_llm(Settings(llm_backend="rule")), RuleBasedLLM)
    assert isinstance(build_llm(Settings(llm_backend="vllm")), OpenAICompatibleLLM)

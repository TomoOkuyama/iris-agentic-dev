"""Which model an eval session runs on — written before the code.

The ladder was hard-wired to `openai/gpt-4.1` and refused to start without `OPENAI_API_KEY`. The evals
now run on a Bedrock-hosted OpenAI model, reached through Bedrock's OpenAI-compatible endpoint with the
long-term Bedrock key `bclaude` uses (`AWS_BEARER_TOKEN_BEDROCK`). The model and its reasoning effort
are part of what was measured, so they go on every session line and a verdict refuses to mix them.
"""

from __future__ import annotations

import json

import pytest

LUNA = "bedrock-oai/global.openai.gpt-6-luna"


def test_the_default_model_still_builds_the_openai_provider_block():
    from tests.e2e.skill_eval.models import provider_block

    block = provider_block("openai/gpt-4.1", api_key="sk-x")
    assert block == {"openai": {"options": {"apiKey": "sk-x"}}}


def test_a_bedrock_openai_model_gets_an_openai_sdk_provider_pointed_at_bedrock():
    from tests.e2e.skill_eval.models import provider_block

    block = provider_block(LUNA, api_key="tok", effort="high")["bedrock-oai"]
    assert block["npm"] == "@ai-sdk/openai"
    assert block["options"]["baseURL"].startswith("https://bedrock-runtime.")
    assert block["options"]["baseURL"].endswith("/openai/v1")
    model = block["models"]["global.openai.gpt-6-luna"]
    assert model["tool_call"] is True
    assert model["options"] == {"reasoningEffort": "high"}


def test_the_bedrock_key_is_referenced_not_written_into_the_config():
    from tests.e2e.skill_eval.models import provider_block

    text = json.dumps(provider_block(LUNA, api_key="SECRET-TOKEN", effort="high"))
    assert "SECRET-TOKEN" not in text
    assert "{env:AWS_BEARER_TOKEN_BEDROCK}" in text


def test_the_declared_prices_are_the_ones_cost_is_computed_from():
    from tests.e2e.skill_eval.models import provider_block

    cost = provider_block(LUNA, api_key="t")["bedrock-oai"]["models"][
        "global.openai.gpt-6-luna"
    ]["cost"]
    assert cost == {"input": 0.1, "output": 0.5, "cache_read": 0.01, "cache_write": 0.125}


def test_no_effort_leaves_the_model_options_out():
    from tests.e2e.skill_eval.models import provider_block

    model = provider_block(LUNA, api_key="t")["bedrock-oai"]["models"][
        "global.openai.gpt-6-luna"
    ]
    assert "options" not in model


def test_an_unknown_provider_or_model_is_refused_not_guessed():
    from tests.e2e.skill_eval.models import UnknownModel, provider_block

    with pytest.raises(UnknownModel):
        provider_block("mystery/model", api_key="t")
    with pytest.raises(UnknownModel):
        provider_block("bedrock-oai/global.openai.unpriced", api_key="t")


def test_an_effort_on_a_provider_that_ignores_it_is_refused():
    from tests.e2e.skill_eval.models import UnknownModel, provider_block

    with pytest.raises(UnknownModel):
        provider_block("openai/gpt-4.1", api_key="t", effort="high")


def test_the_api_key_comes_from_the_providers_own_variable():
    from tests.e2e.skill_eval.models import api_key_for

    assert api_key_for("openai/gpt-4.1", {"OPENAI_API_KEY": "a"}) == "a"
    assert api_key_for(LUNA, {"AWS_BEARER_TOKEN_BEDROCK": "b", "OPENAI_API_KEY": "a"}) == "b"


def test_a_missing_key_names_the_variable_and_where_bclaude_gets_it():
    from tests.e2e.skill_eval.models import MissingCredential, api_key_for

    with pytest.raises(MissingCredential) as caught:
        api_key_for(LUNA, {"OPENAI_API_KEY": "a"})
    assert "AWS_BEARER_TOKEN_BEDROCK" in str(caught.value)
    assert "secrets.env" in str(caught.value)


def test_isolated_env_writes_the_bedrock_provider_for_a_bedrock_model():
    from tests.e2e.isolated_env import IsolatedEnv

    with IsolatedEnv(openai_api_key="tok", model=LUNA, effort="high") as env:
        cfg = json.loads(env.config_content)
    assert "bedrock-oai" in cfg["provider"] and "openai" not in cfg["provider"]


def test_isolated_env_default_is_unchanged():
    from tests.e2e.isolated_env import IsolatedEnv

    with IsolatedEnv(openai_api_key="sk-x") as env:
        cfg = json.loads(env.config_content)
    assert cfg["provider"] == {"openai": {"options": {"apiKey": "sk-x"}}}


def test_the_ladder_takes_an_effort_and_a_bedrock_model():
    from tests.e2e.skill_eval import ladder

    args = ladder.parse_args(["--model", LUNA, "--effort", "high"])
    assert (args.model, args.effort) == (LUNA, "high")
    assert ladder.parse_args([]).effort is None


def test_the_ladder_does_not_demand_an_openai_key_for_a_bedrock_model(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot
    from tests.e2e.skill_eval.arms import TOOLS
    from tests.e2e.skill_eval.test_ladder import FakeTask, run

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "tok")
    seen = {}

    def run_one(task, arm, **kwargs):
        seen.update(kwargs)
        return run(task.id, arm.name, True)

    monkeypatch.setattr(pilot, "run_one", run_one)
    ladder.run_ladder([FakeTask("CORPUS-01")], (TOOLS,), model=LUNA, effort="high")
    assert seen["openai_api_key"] == "tok"
    assert seen["model"] == LUNA and seen["effort"] == "high"


def test_every_session_line_names_the_model_and_effort():
    from tests.e2e.skill_eval import ladder

    line = ladder.session_line({"task_id": "T"}, side="holdout", build=None, model=LUNA, effort="high")
    assert (line["model"], line["effort"]) == (LUNA, "high")


# --- running beside other runs: the prompt and the iad server must point at this run's container ----------


def test_the_prompt_names_this_runs_container_and_port():
    from tests.e2e.skill_eval.models import localize_prompt

    text = (
        "IRIS: host localhost, web port 52780, username _SYSTEM, password SYS, namespace BENCHMARK.\n"
        "The instance runs in the Docker container iris-dev-iris."
    )
    out = localize_prompt(text, web_port="52891", container="iad135-w1")
    assert "web port 52891" in out and "container iad135-w1" in out
    assert "52780" not in out and "iris-dev-iris" not in out


def test_the_default_container_leaves_the_prompt_byte_for_byte_alone():
    from tests.e2e.skill_eval.models import localize_prompt

    text = "web port 52780 ... iris-dev-iris ... and a 52781 elsewhere"
    assert localize_prompt(text, web_port="52780", container="iris-dev-iris") == text


def test_a_prompt_that_names_neither_is_unchanged():
    from tests.e2e.skill_eval.models import localize_prompt

    assert localize_prompt("do the thing", web_port="52891", container="w1") == "do the thing"


def test_the_session_prompt_is_localized(monkeypatch):
    from tests.e2e.skill_eval import graded_task, pilot
    from tests.e2e.skill_eval.arms import TOOLS
    from tests.e2e.skill_eval.test_pilot import RecordingDriver, fake_task

    task = fake_task("FAKE-01")
    task = type(task)(**{**task.__dict__, "prompt": "web port 52780 in iris-dev-iris"})
    for name in ("validate_live", "reset_documents", "apply_documents", "run_teardown"):
        monkeypatch.setattr(graded_task, name, lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "list_classes", lambda *a, **k: set())
    monkeypatch.setattr(graded_task, "run_check", lambda t: True)
    driver = RecordingDriver()
    pilot.run_one(
        task, TOOLS, openai_api_key="k", skill_names=(), iris_host="localhost",
        iris_web_port="52891", iris_container="iad135-w1", driver=driver,
    )
    prompt = driver.collected[0][0]
    assert "web port 52891" in prompt and "iad135-w1" in prompt and "52780" not in prompt


def test_the_iad_server_gets_an_empty_config_home_so_it_sees_one_server():
    from tests.e2e.isolated_env import IsolatedEnv

    with IsolatedEnv(openai_api_key="k") as env:
        env.with_mcp("localhost", "52891", "iad135-w1", binary="/bin/true")
        mcp = json.loads(env.config_content)["mcp"]["iris-agentic-dev"]["environment"]
        assert mcp["HOME"].startswith(env._tmpdir) and mcp["XDG_CONFIG_HOME"].startswith(env._tmpdir)
        import os

        assert os.path.isdir(mcp["HOME"])


# --- a session whose iad server never answered says nothing about the arm ---------------------------------


def _call(name, completed, error=None, server="iris-agentic-dev"):
    from tests.e2e.skill_eval.driver import ToolCall

    return ToolCall(name=name, completed=completed, server=server, status="completed" if completed else "error", error=error)


def test_a_session_where_every_iad_call_timed_out_is_a_dead_server():
    from tests.e2e.skill_eval.driver import server_never_answered

    calls = [
        _call("check_config", False, "MCP error -32001: Request timed out"),
        _call("iris_servers", False, "MCP error -32001: Request timed out"),
        _call("bash", True, server=None),
    ]
    assert server_never_answered(calls, "iris-agentic-dev") is True


def test_one_answered_call_means_the_server_was_alive():
    from tests.e2e.skill_eval.driver import server_never_answered

    calls = [
        _call("check_config", False, "MCP error -32001: Request timed out"),
        _call("iris_doc", True),
        _call("iris_servers", False, "MCP error -32001: Request timed out"),
    ]
    assert server_never_answered(calls, "iris-agentic-dev") is False


def test_a_single_timed_out_call_is_not_enough_to_say_dead():
    from tests.e2e.skill_eval.driver import server_never_answered

    assert server_never_answered([_call("check_config", False, "Request timed out")], "iris-agentic-dev") is False


def test_errors_that_are_not_timeouts_are_the_agents_problem_not_the_servers():
    from tests.e2e.skill_eval.driver import server_never_answered

    calls = [_call("iris_doc", False, "NOT_FOUND"), _call("iris_doc", False, "NOT_FOUND")]
    assert server_never_answered(calls, "iris-agentic-dev") is False


def test_run_one_leaves_a_dead_server_session_unscored(monkeypatch):
    from tests.e2e.skill_eval import graded_task, pilot
    from tests.e2e.skill_eval.arms import TOOLS
    from tests.e2e.skill_eval.test_pilot import RecordingDriver, fake_task

    for name in ("validate_live", "reset_documents", "apply_documents", "run_teardown"):
        monkeypatch.setattr(graded_task, name, lambda *a, **k: None)
    monkeypatch.setattr(graded_task, "list_classes", lambda *a, **k: set())
    monkeypatch.setattr(graded_task, "run_check", lambda t: False)
    monkeypatch.setattr(
        pilot,
        "server_never_answered",
        lambda calls, server: True,
    )
    run = pilot.run_one(
        fake_task("F-1"), TOOLS, openai_api_key="k", skill_names=(), iris_host="localhost",
        iris_web_port="52780", iris_container="iris-dev-iris", driver=RecordingDriver(),
    )
    assert run.passed is None and "never answered" in run.reason


def test_the_server_name_matches_whether_it_carries_hyphens_or_underscores():
    from tests.e2e.skill_eval.driver import server_never_answered

    calls = [
        _call("a", False, "Request timed out", server="iris_agentic_dev"),
        _call("b", False, "Request timed out", server="iris_agentic_dev"),
    ]
    assert server_never_answered(calls, "iris-agentic-dev") is True

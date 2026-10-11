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

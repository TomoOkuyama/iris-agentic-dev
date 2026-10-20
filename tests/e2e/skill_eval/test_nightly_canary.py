"""Unit tests for the nightly breakage guard — 121 T016.

The nightly spent ~$3.70 and two hours of runner time a night to publish a lift it could not
measure. Runs 34744344877, 34817991701 and 34939912456 failed in a row on differences smaller
than the harness's own resolution, and before that six of nine skills printed 0.00 against 0.00
and the job reported success.

FR-016 makes the nightly a different thing: does the harness still run, does the binary still
advertise its tools, does a named canary set still pass. No lift number at all — not an
underpowered one, not a withheld one, none. These tests hold that line, because the cheapest way
for the old behaviour to come back is one f-string.
"""

import json

import pytest

from tests.e2e.skill_eval.nightly_canary import (
    CANARY_TASKS,
    MINIMUM_TOOL_COUNT,
    CanaryReport,
    build_report,
    lift_mentions,
)


def report(
    harness_ok=True,
    harness_detail="41 eval configs loaded",
    tool_count=81,
    task_outcomes=None,
    canary_tasks=CANARY_TASKS,
    task_details=None,
) -> CanaryReport:
    if task_outcomes is None:
        task_outcomes = {task: True for task in canary_tasks}
    return build_report(
        run_id="2026-09-16T020000Z",
        timestamp="2026-09-16T02:00:00Z",
        harness_ok=harness_ok,
        harness_detail=harness_detail,
        tool_count=tool_count,
        task_outcomes=task_outcomes,
        canary_tasks=canary_tasks,
        task_details=task_details,
    )


# ── the verdict ──────────────────────────────────────────────────────────────


def test_a_healthy_run_is_healthy_and_exits_zero():
    healthy = report()
    assert healthy.verdict == "healthy"
    assert healthy.broken == []
    assert healthy.exit_code() == 0


def test_a_failing_canary_task_names_the_task_in_the_verdict():
    """ "Something broke" sends someone to read a two-hour log. The task name is the whole point."""
    broken = report(task_outcomes={**{t: True for t in CANARY_TASKS}, "MCP-01": False})
    assert broken.verdict == "broken"
    assert "MCP-01" in broken.broken
    assert "MCP-01" in broken.render()


def test_a_failing_canary_task_exits_non_zero():
    """A canary failure that still exits 0 is a guard that guards nothing (T016's third clause)."""
    broken = report(
        task_outcomes={**{t: True for t in CANARY_TASKS}, "SKILL-01": False}
    )
    assert broken.exit_code() != 0


def test_a_canary_task_that_did_not_run_is_breakage_and_not_a_pass():
    """`None` is not `True`. A task the runner never reached is the failure mode 118 was about."""
    outcomes = {t: True for t in CANARY_TASKS}
    outcomes["FULL-01"] = None
    did_not_run = report(task_outcomes=outcomes)
    assert did_not_run.verdict == "broken"
    assert "FULL-01" in did_not_run.broken
    assert "did not run" in did_not_run.render()


def test_a_canary_task_missing_from_the_outcomes_entirely_is_breakage():
    """The set is declared here, not inferred from whatever the runner happened to produce."""
    partial = report(task_outcomes={"MCP-01": True})
    assert partial.verdict == "broken"
    assert set(partial.broken) >= {t for t in CANARY_TASKS if t != "MCP-01"}


def test_an_empty_canary_set_is_itself_breakage():
    """A guard over nothing passes every night and catches nothing."""
    empty = report(task_outcomes={}, canary_tasks=())
    assert empty.verdict == "broken"
    assert "canary set" in empty.render()


# ── the two cheap probes ─────────────────────────────────────────────────────


def test_a_harness_that_does_not_run_is_reported_with_its_reason():
    dead = report(
        harness_ok=False, harness_detail="eval.yaml for iris-docs does not parse"
    )
    assert dead.verdict == "broken"
    assert "does not parse" in dead.render()


def test_a_binary_advertising_no_tools_is_breakage():
    """The nightly ran for weeks with no iad tools in any session and reported pass rates."""
    surfaceless = report(tool_count=0)
    assert surfaceless.verdict == "broken"
    assert "tool surface" in surfaceless.render()


def test_an_unreadable_tool_surface_is_breakage_rather_than_an_assumption():
    assert report(tool_count=None).verdict == "broken"


def test_a_surface_below_the_floor_is_breakage_and_names_both_numbers():
    thin = report(tool_count=MINIMUM_TOOL_COUNT - 1)
    assert thin.verdict == "broken"
    rendered = thin.render()
    assert str(MINIMUM_TOOL_COUNT - 1) in rendered
    assert str(MINIMUM_TOOL_COUNT) in rendered


def test_a_surface_larger_than_the_floor_is_healthy():
    """Adding a tool must not fail the nightly, which is why the check is a floor and not `==`."""
    assert report(tool_count=MINIMUM_TOOL_COUNT + 20).verdict == "healthy"


# ── no lift, anywhere ────────────────────────────────────────────────────────


def test_the_report_carries_no_lift_field_at_all():
    """FR-016, as a scan of the object rather than a promise in a docstring."""
    payload = report().to_dict()
    assert lift_mentions(payload) == []
    assert not hasattr(report(), "lift")


def test_the_rendered_report_prints_no_lift_number():
    rendered = report(
        task_outcomes={**{t: True for t in CANARY_TASKS}, "MCP-01": False}
    ).render()
    assert "lift" not in rendered.lower()


def test_a_report_that_smuggled_a_lift_into_a_detail_is_refused():
    """The guard's own canary: a detail string is the cheapest way for the old number to return."""
    smuggled = report(harness_detail="lift=+0.28 over the canary set")
    assert lift_mentions(smuggled.to_dict())
    with pytest.raises(ValueError, match="lift"):
        smuggled.assert_no_lift()


def test_a_clean_report_passes_its_own_no_lift_guard():
    report().assert_no_lift()  # raises if it does not


def test_the_report_is_json_serialisable():
    """The nightly uploads it as an artifact, and a report that cannot be written is not a report."""
    payload = json.loads(json.dumps(report().to_dict()))
    assert payload["verdict"] == "healthy"
    assert payload["canary_tasks"] == list(CANARY_TASKS)
    assert payload["tool_count"] == 81


def test_the_report_names_the_canary_set_it_ran():
    """SC-007: a named set, so a reader can tell which three tasks stood for the whole harness."""
    rendered = report().render()
    for task in CANARY_TASKS:
        assert task in rendered


def test_the_harness_probe_passes_on_the_real_tree():
    """The probe reads two directories, and reading the wrong one reports the harness broken.

    It did: three `dirname` calls instead of four resolved `tests/skills/skills`, which exists
    nowhere, so a healthy checkout reported breakage. Same class as the hard-coded Homebrew path
    that left the nightly running with no iad tools for weeks.
    """
    from tests.e2e.skill_eval.nightly_canary import probe_harness

    ok, detail = probe_harness()
    assert ok, detail
    assert "eval configs" in detail


def test_the_tool_surface_probe_reports_none_for_a_binary_that_is_not_there():
    """`None`, not zero and not an exception — "could not ask" is its own answer."""
    from tests.e2e.skill_eval.nightly_canary import probe_tool_surface

    assert probe_tool_surface("/nonexistent/iris-agentic-dev") is None


def test_the_declared_canary_set_is_not_empty():
    """A named set with nothing in it would pass every test above and guard nothing."""
    assert len(CANARY_TASKS) >= 3


def test_a_canary_task_names_the_credential_its_own_model_needs():
    """The gate has to be the key the session actually authenticates with.

    All three canary tasks declare `amazon-bedrock/...`, and `run_task` lets the task's own model
    override the caller's default. A run gated on `OPENAI_API_KEY` would refuse a night that had
    a working Bedrock token and start a night that had nothing the sessions could use.
    """
    from tests.e2e.skill_eval.nightly_canary import missing_credentials

    assert missing_credentials(env={}), (
        "no credential at all must be reported, not assumed"
    )
    for task, need in missing_credentials(env={}):
        assert task in CANARY_TASKS
        assert need


def test_a_bedrock_token_satisfies_the_bedrock_canary_tasks():
    from tests.e2e.skill_eval.nightly_canary import missing_credentials

    satisfied = missing_credentials(
        env={"AWS_BEARER_TOKEN_BEDROCK": "t", "OPENAI_API_KEY": "k"}
    )
    assert satisfied == []


def test_an_openai_key_alone_does_not_satisfy_a_bedrock_canary_task():
    """The failure this replaces: a night that ran on a key none of its tasks use."""
    from tests.e2e.skill_eval.nightly_canary import missing_credentials

    missing = missing_credentials(env={"OPENAI_API_KEY": "k"})
    assert [task for task, _ in missing] == list(CANARY_TASKS)
    assert all("BEDROCK" in need for _, need in missing)


def test_an_unrecognised_provider_is_reported_rather_than_waved_through():
    """A new provider prefix must not read as "no credential needed"."""
    from tests.e2e.skill_eval.nightly_canary import credential_for, missing_credentials

    assert credential_for("someprovider/some-model") is None
    missing = missing_credentials(
        env={"OPENAI_API_KEY": "k"}, models={"NEW-01": "someprovider/some-model"}
    )
    assert [task for task, _ in missing] == ["NEW-01"]
    assert "someprovider" in missing[0][1]


def test_the_canary_tasks_all_exist_on_disk():
    """The set is task IDs, and a typo'd ID is a canary that never runs."""
    import os

    from tests.e2e.task_loader import TASKS_DIR, load_task

    for task_id in CANARY_TASKS:
        path = os.path.join(TASKS_DIR, f"{task_id}.yaml")
        assert os.path.exists(path), f"{task_id} is in the canary set with no {path}"
        assert load_task(path).assertions, (
            f"{task_id} has no assertions, so passing it would mean nothing — the canary set is "
            "assertion-scored on purpose, so the nightly needs no scorer credential and no spend"
        )


# ── a red night says why ─────────────────────────────────────────────────────


def test_a_failed_task_reports_which_assertions_failed_and_what_the_session_did():
    """Three nights in October 2026 said "assertions failed" for all three tasks and nothing else,
    so nobody could tell a model outage from a broken tool without rerunning the night."""
    from tests.e2e.result_writer import AssertionResult, TaskResult
    from tests.e2e.skill_eval.nightly_canary import describe_result

    result = TaskResult(
        task_id="MCP-01",
        scenario="mcp",
        condition="baseline",
        passed=False,
        skill_loaded=False,
        tool_calls=[],
        assertion_results=[
            AssertionResult(assertion_type="tool_called", description="calls iris_query", passed=False),
            AssertionResult(assertion_type="output_contains", description="says the count", passed=True),
        ],
        llm_output_excerpt="",
        duration_seconds=300.4,
    )
    text = describe_result(result)
    assert "calls iris_query" in text
    assert "says the count" not in text, "only the failed assertions"
    assert "0 tool calls" in text and "300s" in text
    assert "no output" in text

    broken = report(
        task_outcomes={**{t: True for t in CANARY_TASKS}, "MCP-01": False},
        task_details={"MCP-01": text},
    )
    detail = next(c.detail for c in broken.checks if c.name == "MCP-01")
    assert "calls iris_query" in detail, detail


def test_a_task_model_missing_from_the_opencode_catalog_is_named_before_any_session():
    """In October 2026 opencode's catalog dropped the Bedrock Sonnet 4.5 id all three canary tasks
    named. Each session then died in a second with "Model not found" and the night read as three
    failed tasks. A model the catalog does not list is a misconfiguration, found before spending."""
    from tests.e2e.skill_eval.nightly_canary import models_missing_from_catalog

    catalog = "amazon-bedrock/us.anthropic.claude-sonnet-4-6\nopenai/gpt-4.1\n"
    tasks = {
        "MCP-01": "amazon-bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "SKILL-01": "amazon-bedrock/us.anthropic.claude-sonnet-4-6",
        "FULL-01": None,
    }
    assert models_missing_from_catalog(tasks, catalog, default="openai/gpt-4.1") == [
        ("MCP-01", "amazon-bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    ]
    assert models_missing_from_catalog(tasks, catalog, default="openai/gpt-5") == [
        ("MCP-01", "amazon-bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"),
        ("FULL-01", "openai/gpt-5"),
    ]


def test_every_canary_task_names_a_model():
    import os

    from tests.e2e.task_loader import TASKS_DIR, load_task

    for task_id in CANARY_TASKS:
        task = load_task(os.path.join(TASKS_DIR, f"{task_id}.yaml"))
        assert task.model, f"{task_id} names no model, so the night runs on whatever the default is"

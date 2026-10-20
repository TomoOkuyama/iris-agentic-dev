"""Tokens per session — 135 T003, written before the code.

Cost alone hides context bulk: a skill that adds 3000 tokens of cached prompt costs little per call
and a lot of context. The numbers come from opencode's own `step_finish` events, the same events
`session_cost` reads, so the two cannot disagree about which steps happened.
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.skill_eval.arms import TOOLS, TOOLS_SKILLS
from tests.e2e.skill_eval.test_ladder import FakeTask, run


def _step(inp, out, cache_read=0, cache_write=0, reasoning=0, cost=0.01):
    return {
        "type": "step_finish",
        "part": {
            "type": "step-finish",
            "tokens": {
                "total": inp + out + reasoning,
                "input": inp,
                "output": out,
                "reasoning": reasoning,
                "cache": {"read": cache_read, "write": cache_write},
            },
            "cost": cost,
        },
    }


def test_session_tokens_sum_every_step_finish():
    from tests.e2e.skill_eval.cost_estimator import session_tokens

    events = [
        {"type": "text", "part": {}},
        _step(1000, 50, cache_read=200, cache_write=30, reasoning=5),
        _step(2000, 70, cache_read=400),
        {"type": "tool_use"},
    ]
    assert session_tokens(events) == {
        "input": 3000,
        "output": 120,
        "reasoning": 5,
        "cache_read": 600,
        "cache_write": 30,
        "steps": 2,
    }


def test_session_tokens_of_a_stream_with_none_are_all_zero():
    from tests.e2e.skill_eval.cost_estimator import session_tokens

    zero = {
        "input": 0,
        "output": 0,
        "reasoning": 0,
        "cache_read": 0,
        "cache_write": 0,
        "steps": 0,
    }
    assert session_tokens([]) == zero
    assert session_tokens([{"type": "step_finish", "part": {}}]) == {**zero, "steps": 1}


def test_a_step_finish_with_a_malformed_token_block_counts_as_zero_not_a_crash():
    from tests.e2e.skill_eval.cost_estimator import session_tokens

    events = [{"type": "step_finish", "part": {"tokens": {"input": "x", "cache": 3}}}]
    assert session_tokens(events)["input"] == 0
    assert session_tokens(events)["cache_read"] == 0


def _run_one_with_tokens(streams):
    seen = []

    def run_one(task, arm, on_events=None, **kwargs):
        seen.append((task.id, arm.name))
        if on_events is not None:
            on_events(streams[len(seen) - 1])
        return run(task.id, arm.name, True)

    return run_one


def test_the_ladder_puts_each_sessions_tokens_on_its_run(monkeypatch):
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        pilot,
        "run_one",
        _run_one_with_tokens([[_step(100, 10)], [_step(900, 90, cache_read=500)]]),
    )
    runs = ladder.run_ladder([FakeTask("CORPUS-01")], (TOOLS, TOOLS_SKILLS))
    assert runs[0].tokens["input"] == 100 and runs[0].tokens["output"] == 10
    assert runs[1].tokens["input"] == 900 and runs[1].tokens["cache_read"] == 500


def test_the_incremental_record_carries_tokens(monkeypatch):
    """`asdict` is what the jsonl writer serialises, so a field missing from the dataclass is a field
    missing from the file — the serde-silent-drop pattern, on the Python side."""
    from dataclasses import asdict

    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        pilot, "run_one", _run_one_with_tokens([[_step(7, 3)], [_step(8, 4)]])
    )
    runs = ladder.run_ladder([FakeTask("CORPUS-01")], (TOOLS, TOOLS_SKILLS))
    line = json.loads(json.dumps(asdict(runs[0])))
    assert line["tokens"]["input"] == 7
    assert line["tokens"]["output"] == 3


def test_an_old_record_without_tokens_still_loads():
    from tests.e2e.skill_eval.pilot import ArmRun

    old = ArmRun(task_id="T", arm="tools", passed=True)
    assert old.tokens == {}


def test_pooled_tokens_for_a_group_of_runs():
    from tests.e2e.skill_eval.cost_estimator import add_tokens

    total = add_tokens(
        {"input": 1, "output": 2, "cache_read": 3},
        {"input": 10, "output": 20, "cache_write": 5},
    )
    assert total == {
        "input": 11,
        "output": 22,
        "reasoning": 0,
        "cache_read": 3,
        "cache_write": 5,
        "steps": 0,
    }


@pytest.mark.parametrize("bad", [None, {}, {"input": None}])
def test_add_tokens_tolerates_missing_parts(bad):
    from tests.e2e.skill_eval.cost_estimator import add_tokens

    assert add_tokens(bad, {"input": 4})["input"] == 4


def test_the_ladder_stores_each_sessions_measured_cost(monkeypatch):
    """The cost was printed per session and never stored, so a report could only recover it from the
    ledger's regex over stdout."""
    from tests.e2e.skill_eval import ladder, pilot

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(
        pilot,
        "run_one",
        _run_one_with_tokens([[_step(1, 1, cost=0.25)], [_step(1, 1, cost=0.5)]]),
    )
    runs = ladder.run_ladder([FakeTask("CORPUS-01")], (TOOLS, TOOLS_SKILLS))
    assert [r.cost_usd for r in runs] == [pytest.approx(0.25), pytest.approx(0.5)]
    assert ArmRunDefault().cost_usd is None


class ArmRunDefault:
    def __new__(cls):
        from tests.e2e.skill_eval.pilot import ArmRun

        return ArmRun(task_id="T", arm="tools", passed=True)

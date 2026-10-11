"""Pooling the tools-ladder shards into one `tools` vs `tools+skills` comparison — written before the code.

The tools ladder is split across containers to run in parallel, so its sessions arrive in several
`.runs.jsonl` files. The pooled figure must pair a task's two arms across files, count the discordant
pairs, give the lift with an interval that resamples tasks, and say how often the agent loaded a skill
in the `tools+skills` arm (on gpt-4.1 it was 0 of 58, so that arm measured the skill index only).
"""

from __future__ import annotations

import json

from tests.e2e.skill_eval import pooled_ladder

MODEL = "bedrock-oai/luna"


def line(task, arm, repeat, passed, *, calls=5, cost=0.01, skill_calls=0, model=MODEL, effort="high"):
    calls_list = [{"name": "skill", "completed": True}] * skill_calls + [{"name": "bash", "completed": True}] * calls
    return {
        "task_id": task,
        "arm": arm,
        "run_index": repeat,
        "passed": passed,
        "tool_calls": calls,
        "cost_usd": cost,
        "calls": calls_list,
        "model": model,
        "effort": effort,
        "side": "holdout",
    }


def write(tmp_path, name, lines):
    path = tmp_path / f"{name}.runs.jsonl"
    path.write_text("".join(json.dumps(x) + "\n" for x in lines))
    return str(path)


def test_pairs_are_made_across_files(tmp_path):
    a = write(tmp_path, "a", [line("T1", "tools", 0, True), line("T2", "tools", 0, False)])
    b = write(tmp_path, "b", [line("T1", "tools+skills", 0, True), line("T2", "tools+skills", 0, True)])
    result = pooled_ladder.pool([a, b])
    assert result["pairs"] == 2
    assert (result["b"], result["c"]) == (1, 0)


def test_unscored_pairs_are_left_out_and_counted(tmp_path):
    a = write(tmp_path, "a", [line("T1", "tools", 0, None), line("T2", "tools", 0, True)])
    b = write(tmp_path, "b", [line("T1", "tools+skills", 0, True), line("T2", "tools+skills", 0, True)])
    result = pooled_ladder.pool([a, b])
    assert result["pairs"] == 1 and result["unscored"] == 1


def test_the_skill_load_rate_counts_sessions_that_called_the_skill_tool(tmp_path):
    lines = []
    for i in range(4):
        lines.append(line(f"T{i}", "tools", 0, True))
        lines.append(line(f"T{i}", "tools+skills", 0, True, skill_calls=1 if i < 1 else 0))
    result = pooled_ladder.pool([write(tmp_path, "a", lines)])
    assert result["skill_sessions"] == 1 and result["treated_sessions"] == 4
    assert result["skill_load_rate"] == 0.25


def test_the_lift_is_the_treated_pass_rate_minus_the_tools_pass_rate_per_task_mean(tmp_path):
    lines = []
    for task, (t, s) in {"A": (0, 3), "B": (3, 3), "C": (1, 1), "D": (0, 1), "E": (2, 3)}.items():
        for r in range(3):
            lines.append(line(task, "tools", r, r < t))
            lines.append(line(task, "tools+skills", r, r < s))
    result = pooled_ladder.pool([write(tmp_path, "a", lines)])
    assert abs(result["lift"] - ((3 + 0 + 0 + 1 + 1) / 3 / 5)) < 1e-9
    low, high = result["lift_ci"]
    assert low <= result["lift"] <= high


def test_runs_on_different_models_are_refused(tmp_path):
    a = write(tmp_path, "a", [line("T1", "tools", 0, True, model="m1")])
    b = write(tmp_path, "b", [line("T1", "tools+skills", 0, True, model="m2")])
    try:
        pooled_ladder.pool([a, b])
    except pooled_ladder.PoolRefused as refused:
        assert "model" in str(refused)
    else:
        raise AssertionError("pooled two models")


def test_a_task_in_both_files_for_the_same_arm_and_repeat_keeps_the_later_scored_one(tmp_path):
    a = write(tmp_path, "a", [line("T1", "tools", 0, None), line("T1", "tools+skills", 0, True)])
    b = write(tmp_path, "b", [line("T1", "tools", 0, True)])
    assert pooled_ladder.pool([a, b])["pairs"] == 1


def test_cost_and_calls_ratios_are_pooled_sums(tmp_path):
    lines = [
        line("T1", "tools", 0, True, calls=10, cost=1.0),
        line("T1", "tools+skills", 0, True, calls=5, cost=0.5),
        line("T2", "tools", 0, True, calls=10, cost=1.0),
        line("T2", "tools+skills", 0, True, calls=15, cost=1.5),
    ]
    result = pooled_ladder.pool([write(tmp_path, "a", lines)])
    assert result["calls_ratio"] == 1.0 and result["cost_ratio"] == 1.0


def test_the_text_report_names_the_model_and_the_load_rate(tmp_path):
    lines = [line("T1", "tools", 0, True), line("T1", "tools+skills", 0, True, skill_calls=1)]
    text = pooled_ladder.render(pooled_ladder.pool([write(tmp_path, "a", lines)]))
    assert "luna" in text and "loaded a skill" in text and "95%" in text

"""`improve skills` — the per-skill verdict against specs/135-skill-evidence/criteria.md.

135 T002, written before the code. Every figure is derived from run files and ledger events; nothing
is stored. The tests build run files of known shape and assert the counts, ratios and verdicts the
criteria define, so a change to a threshold or to the pairing rule fails here first.
"""

from __future__ import annotations

import json
import random

import pytest

from tests.e2e.skill_eval import evidence

SKILL = "objectscript-tdd"
TREATED = f"tools+{SKILL}"
TASKS = [f"SKILL-{n}" for n in (31, 32, 33, 34, 35)]
BUILD = {
    "binary": "/x/iad",
    "binary_sha256": "b" * 64,
    "binary_version": "1.5.0",
    "commit": "c" * 40,
    "dirty": False,
    "binary_stale": False,
}


def s(task, arm, repeat, passed, calls=10, cost=1.0, loaded=None, quality=None, build=BUILD, fp="f"):
    if arm != "tools" and loaded is None:
        loaded = True
    return {
        "task_id": task,
        "arm": arm,
        "run_index": repeat,
        "passed": passed,
        "tool_calls": calls,
        "cost_usd": cost,
        "skill_loaded": loaded if arm != "tools" else None,
        "quality": quality,
        "timed_out": False,
        "tokens": {"input": 100, "output": 10, "cache_read": 0, "cache_write": 0},
        "build": build,
        "task_fingerprint": fp,
        "side": "holdout",
    }


def run_lines(plan, tasks=TASKS, repeats=3, **kw):
    """plan(task, repeat) -> (tools_passed, skill_passed) or a dict of overrides per arm."""
    lines = []
    for task in tasks:
        for repeat in range(repeats):
            t, k = plan(task, repeat)
            lines.append(s(task, "tools", repeat, t, **kw.get("tools", {})))
            lines.append(s(task, TREATED, repeat, k, **kw.get("skill", {})))
    return lines


def evaluate(lines, **kw):
    return evidence.evaluate_run(lines, SKILL, **kw)


def even(task, repeat):
    return (True, True)


# --- pairing ------------------------------------------------------------------------------------


def test_a_pair_needs_both_sessions_scored_and_the_skill_loaded():
    lines = run_lines(even)
    lines[1]["skill_loaded"] = False
    lines[1]["passed"] = None
    lines[14]["passed"] = None  # a tools session whose check never answered
    result = evaluate(lines)
    assert result["pairs"] == 15 - 2
    assert result["unloaded"] == 1
    assert result["unscored"] == 1


def test_loaded_rate_counts_treated_sessions():
    lines = run_lines(even)
    for line in lines[1::2][:3]:
        line["skill_loaded"] = False
        line["passed"] = None
    assert evaluate(lines)["loaded_rate"] == pytest.approx(12 / 15)


def test_discordant_pairs_are_b_and_c():
    def plan(task, repeat):
        return {
            ("SKILL-31", 0): (False, True),
            ("SKILL-32", 0): (False, True),
            ("SKILL-33", 0): (True, False),
        }.get((task, repeat), (True, True))

    result = evaluate(run_lines(plan))
    assert (result["b"], result["c"]) == (2, 1)


def test_a_timeout_whose_check_answered_is_scored():
    lines = run_lines(even)
    lines[1]["timed_out"] = True
    assert evaluate(lines)["pairs"] == 15


# --- criterion 2a, completion -------------------------------------------------------------------


def only_skill_passes(n_pairs):
    wins = {(t, r) for t in TASKS for r in range(3)}
    chosen = set(sorted(wins)[:n_pairs])
    return lambda task, repeat: (False, True) if (task, repeat) in chosen else (True, True)


def test_three_net_wins_and_no_losses_meet_completion():
    result = evaluate(run_lines(only_skill_passes(3)))
    assert result["criteria"]["1"] is True
    assert result["criteria"]["2a"] is True
    assert result["kinds"] == ["completion"]


def test_two_net_wins_do_not_meet_completion():
    result = evaluate(run_lines(only_skill_passes(2)))
    assert result["criteria"]["2a"] is False


def test_completion_allows_at_most_one_loss():
    wins = sorted((t, r) for t in TASKS for r in range(3))
    win, loss = set(wins[:5]), set(wins[5:7])

    def plan(task, repeat):
        if (task, repeat) in win:
            return (False, True)
        if (task, repeat) in loss:
            return (True, False)
        return (True, True)

    result = evaluate(run_lines(plan))
    assert (result["b"], result["c"]) == (5, 2)
    assert result["criteria"]["1"] is True
    assert result["criteria"]["2a"] is False  # b - c = 3 but c = 2


def test_more_losses_than_wins_fail_criterion_one():
    def plan(task, repeat):
        return (True, False) if (task, repeat) == ("SKILL-31", 0) else (True, True)

    result = evaluate(run_lines(plan))
    assert result["criteria"]["1"] is False
    assert result["verdict"] == "not net positive"


# --- criterion 2b, efficiency -------------------------------------------------------------------


def cheaper(calls_ratio, cost_ratio, share_cheaper=1.0):
    n_cheaper = round(share_cheaper * len(TASKS))
    lines = []
    for index, task in enumerate(TASKS):
        faster = index < n_cheaper
        for repeat in range(3):
            lines.append(s(task, "tools", repeat, True, calls=20, cost=2.0 + 0.1 * index))
            lines.append(
                s(
                    task,
                    TREATED,
                    repeat,
                    True,
                    calls=20 * calls_ratio if faster else 24,
                    cost=(2.0 + 0.1 * index) * cost_ratio if faster else 2.6,
                )
            )
    return lines


def test_a_clearly_cheaper_skill_meets_efficiency():
    result = evaluate(cheaper(0.6, 0.6))
    assert result["criteria"]["2b"] is True
    assert "efficiency" in result["kinds"]
    assert result["calls_ratio"] == pytest.approx(0.6)
    assert result["cost_ratio"] == pytest.approx(0.6, abs=0.01)


def test_efficiency_needs_calls_at_most_three_quarters():
    assert evaluate(cheaper(0.8, 0.6))["criteria"]["2b"] is False


def test_efficiency_needs_cost_at_most_four_fifths():
    assert evaluate(cheaper(0.6, 0.85))["criteria"]["2b"] is False


def test_efficiency_needs_three_quarters_of_the_tasks_cheaper():
    assert evaluate(cheaper(0.6, 0.6, share_cheaper=0.6))["criteria"]["2b"] is False


def test_efficiency_needs_the_clustered_interval_to_exclude_zero():
    # cheaper on average but one task is wildly dearer, so the task-level interval spans zero
    lines = cheaper(0.7, 0.7)
    for line in lines:
        if line["task_id"] == "SKILL-35" and line["arm"] == TREATED:
            line["cost"] = 99
            line["cost_usd"] = 99.0
            line["tool_calls"] = 99
    result = evaluate(lines)
    assert result["criteria"]["2b"] is False


# --- criterion 2c, quality ----------------------------------------------------------------------


def quality_lines(tools_q, skill_q, passes=(True, True)):
    lines = []
    for task in TASKS:
        for repeat in range(3):
            lines.append(s(task, "tools", repeat, passes[0], quality=tools_q))
            lines.append(s(task, TREATED, repeat, passes[1], quality=skill_q))
    return lines


def test_quality_win_needs_015_and_an_interval_above_zero():
    lines = quality_lines(0.5, 0.7)
    for i, line in enumerate(lines):  # a little spread so the interval is not degenerate
        line["quality"] += 0.01 * (i % 3)
    result = evaluate(lines)
    assert result["criteria"]["2c"] is True
    assert "quality" in result["kinds"]


def test_a_quality_gain_under_015_is_not_a_win():
    assert evaluate(quality_lines(0.5, 0.6))["criteria"]["2c"] is False


def test_quality_is_unavailable_unless_every_task_declares_checks():
    lines = quality_lines(0.5, 0.9)
    lines[0]["quality"] = None
    lines[1]["quality"] = None
    for line in lines:
        if line["task_id"] == "SKILL-35":
            line["quality"] = None
    assert evaluate(lines)["criteria"]["2c"] is False


# --- eligibility --------------------------------------------------------------------------------


def test_fewer_than_five_tasks_gets_no_verdict():
    result = evaluate(run_lines(only_skill_passes(9), tasks=TASKS[:4]))
    assert result["verdict"].startswith("no verdict")
    assert "5 held-out tasks" in result["verdict"]


def test_a_task_with_one_usable_pair_does_not_count_toward_five():
    lines = run_lines(even)
    for line in lines:
        if line["task_id"] == "SKILL-35" and line["run_index"] > 0:
            line["passed"] = None
    assert evaluate(lines)["verdict"].startswith("no verdict")


def test_fewer_than_three_repeats_gets_no_verdict():
    result = evaluate(run_lines(even, repeats=2))
    assert result["verdict"].startswith("no verdict")
    assert "3 repeats" in result["verdict"]


def test_a_skill_loaded_in_under_ninety_percent_gets_no_verdict():
    lines = run_lines(even)
    for line in lines[1::2][:3]:  # 12 of 15 loaded = 80 percent
        line["skill_loaded"] = False
        line["passed"] = None
    result = evaluate(lines)
    assert result["verdict"].startswith("no verdict")
    assert "loaded" in result["verdict"]


def test_two_builds_in_one_run_get_no_verdict():
    lines = run_lines(even)
    lines[3]["build"] = {**BUILD, "commit": "d" * 40}
    assert "one binary" in evaluate(lines)["verdict"]


def test_a_run_started_on_a_dirty_tree_gets_no_verdict():
    lines = run_lines(even, tools={"build": {**BUILD, "dirty": True}}, skill={"build": {**BUILD, "dirty": True}})
    assert "uncommitted" in evaluate(lines)["verdict"]


def test_lines_with_no_build_stamp_are_legacy_and_get_no_verdict():
    lines = run_lines(even)
    for line in lines:
        line.pop("build")
    assert "legacy" in evaluate(lines)["verdict"]


def test_tasks_outside_the_held_out_set_are_excluded_and_listed():
    lines = run_lines(only_skill_passes(9))
    result = evaluate(lines, heldout={"SKILL-31", "SKILL-32", "SKILL-33", "SKILL-34"})
    assert result["excluded_tasks"] == ["SKILL-35"]
    assert result["verdict"].startswith("no verdict")


def test_only_the_two_named_arms_are_read():
    lines = run_lines(even) + [s("SKILL-31", "tools+skills", 0, False)]
    lines += [s("SKILL-31", "tools+iris-sql", 0, False)]
    assert evaluate(lines)["pairs"] == 15


# --- criterion 3, replication --------------------------------------------------------------------


def verdict_of(runs, heldout=None):
    return evidence.evaluate_skill(runs, SKILL, heldout=heldout)


def test_a_qualifying_first_run_alone_is_awaiting_replication():
    verdict = verdict_of([evaluate_lines(only_skill_passes(4))])
    assert verdict["verdict"] == "first run qualifies, awaiting replication"


def evaluate_lines(plan, **kw):
    return run_lines(plan, **kw)


def test_a_replicated_completion_win_is_net_positive():
    runs = [run_lines(only_skill_passes(4)), run_lines(only_skill_passes(4))]
    verdict = verdict_of(runs)
    assert verdict["verdict"] == "net positive"
    assert verdict["kinds"] == ["completion"]


def test_a_second_run_that_is_worse_on_completion_is_not_net_positive():
    def worse(task, repeat):
        return (True, False) if repeat == 0 else (True, True)

    verdict = verdict_of([run_lines(only_skill_passes(4)), run_lines(worse)])
    assert verdict["verdict"] == "not net positive"


def test_pooled_data_can_carry_replication_when_each_run_is_not_worse():
    first = run_lines(only_skill_passes(4))
    second = run_lines(only_skill_passes(1))
    verdict = verdict_of([first, second])
    assert verdict["pooled"]["criteria"]["2a"] is True  # b - c = 5, c = 0
    assert verdict["verdict"] == "net positive"


def test_direction_route_needs_every_deciding_task_to_agree():
    first = run_lines(only_skill_passes(3))  # decided by SKILL-31 (x3)
    # a second run that wins elsewhere but not on the deciding task, and is too small to pool
    second = run_lines(lambda t, r: (False, True) if (t, r) == ("SKILL-35", 0) else (True, True))
    verdict = verdict_of([first, second])
    # pooled b - c = 4, c = 0 and the second run points the same way, so the pooled route carries it;
    # the direction route alone would not, because the deciding task did not move again
    assert verdict["replication"]["pooled"] is True
    assert verdict["replication"]["direction"] is False
    assert verdict["verdict"] == "net positive"


def test_a_second_run_with_no_win_does_not_replicate_even_if_pooling_would_pass():
    """Pooled b - c is still 3, but the second run alone moved nowhere. The pooled route needs the
    later run to point the same way on its own (criteria.md, criterion 3)."""
    verdict = verdict_of([run_lines(only_skill_passes(3)), run_lines(even)])
    assert verdict["pooled"]["criteria"]["2a"] is True
    assert verdict["replication"]["pooled"] is False
    assert verdict["verdict"] == "not net positive"


def test_a_level_second_run_with_a_thin_first_win_does_not_replicate():
    first = run_lines(only_skill_passes(3))
    second = run_lines(lambda t, r: (True, False) if (t, r) == ("SKILL-31", 0) else (True, True))
    verdict = verdict_of([first, second])
    assert verdict["verdict"] == "not net positive"  # second run has c > b


# --- bootstrap and criteria hash -----------------------------------------------------------------


def test_bootstrap_is_seeded_and_clustered_by_task():
    values = [-1.0, -0.8, -1.2, -0.9, -1.1]
    low, high = evidence.bootstrap_interval(values, lambda xs: sum(xs) / len(xs))
    again = evidence.bootstrap_interval(values, lambda xs: sum(xs) / len(xs))
    assert (low, high) == again
    assert -1.2 <= low <= high <= -0.8
    assert high < 0


def test_bootstrap_of_mixed_signs_spans_zero():
    low, high = evidence.bootstrap_interval([-1.0, 1.0, -0.5, 0.5, 0.1], lambda xs: sum(xs) / len(xs))
    assert low < 0 < high


def test_the_criteria_hash_refuses_a_changed_file(tmp_path):
    path = tmp_path / "criteria.md"
    path.write_text("v1\n")
    recorded = evidence.sha256_file(str(path))
    assert evidence.criteria_intact(str(path), [{"criteria_sha256": recorded}])
    path.write_text("v2\n")
    assert not evidence.criteria_intact(str(path), [{"criteria_sha256": recorded}])


def test_no_recorded_hash_means_nothing_to_refuse(tmp_path):
    path = tmp_path / "criteria.md"
    path.write_text("v1\n")
    assert evidence.criteria_intact(str(path), [])


# --- the report from files ------------------------------------------------------------------------


def write_run(tmp_path, name, lines):
    path = tmp_path / f"{name}.runs.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines))
    return str(path)


def event(i, runs_file, **kw):
    return {
        "ts": f"2026-10-11T0{i}:00:00Z",
        "id": f"IMP-00{i}",
        "event": "measure",
        "subject": SKILL,
        "side": "holdout",
        "purpose": "verdict",
        "runs_file": runs_file,
        "criteria_sha256": "x",
        **kw,
    }


def test_the_report_reads_run_files_named_by_ledger_measure_events(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    run = write_run(tmp_path, "ladder-1", run_lines(only_skill_passes(4)))
    events = [event(1, run, criteria_sha256=sha, cost_usd=30.0)]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    row = report["skills"][SKILL]
    assert row["verdict"] == "first run qualifies, awaiting replication"
    assert row["ledger_ids"] == ["IMP-001"]
    assert row["spend_usd"] == 30.0
    assert row["builds"] == [("1.5.0", "c" * 7)]


def test_a_changed_criteria_file_refuses_every_verdict(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    run = write_run(tmp_path, "ladder-1", run_lines(even))
    events = [event(1, run, criteria_sha256="0" * 64)]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert report["refused"]
    assert "criteria.md changed" in report["refused"]


def test_train_runs_are_not_verdict_runs(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    run = write_run(tmp_path, "ladder-1", run_lines(even))
    events = [event(1, run, criteria_sha256=sha, purpose="train", side="train")]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert report["skills"][SKILL]["verdict"].startswith("no verdict")
    assert report["skills"][SKILL]["train_runs"] == 1


def test_a_changed_task_fingerprint_between_runs_is_refused(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    a = write_run(tmp_path, "ladder-1", run_lines(only_skill_passes(4)))
    b = write_run(tmp_path, "ladder-2", run_lines(only_skill_passes(4), tools={"fp": "g"}, skill={"fp": "g"}))
    events = [event(1, a, criteria_sha256=sha), event(2, b, criteria_sha256=sha)]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert "task file" in report["skills"][SKILL]["verdict"]


def test_render_names_the_binary_and_the_commit_and_every_interval():
    row = evaluate(run_lines(only_skill_passes(4)))
    text = evidence.render_row(SKILL, {**row, "ledger_ids": ["IMP-001"], "spend_usd": 12.3,
                                         "builds": [("1.5.0", "ccccccc")], "train_runs": 0})
    assert "1.5.0" in text and "ccccccc" in text
    assert "IMP-001" in text
    assert "95%" in text


# --- held-out tasks: split side, minus every task someone read ----------------------------------------


class _Task:
    def __init__(self, id, skill):
        self.id, self.skill = id, skill


class _Split:
    def __init__(self, holdout):
        self.holdout = tuple(holdout)


def test_heldout_is_the_holdout_side_minus_the_read_tasks_per_skill():
    tasks = [_Task("SKILL-01", "a"), _Task("SKILL-02", "a"), _Task("SKILL-03", "b"), _Task("SKILL-04", "a")]
    split = _Split(["SKILL-01", "SKILL-02", "SKILL-03"])  # SKILL-04 is train
    held = evidence.heldout_by_skill(tasks, split, read={"SKILL-02"})
    assert held == {"a": {"SKILL-01"}, "b": {"SKILL-03"}}


def test_the_read_registry_names_each_task_with_a_reason(tmp_path):
    path = tmp_path / "read.toml"
    path.write_text('[SKILL-02]\nreason = "guardrails edit read it"\n\n[SKILL-03]\nreason = "same"\n')
    assert evidence.load_read(str(path)) == {"SKILL-02": "guardrails edit read it", "SKILL-03": "same"}


def test_a_read_entry_without_a_reason_is_refused(tmp_path):
    path = tmp_path / "read.toml"
    path.write_text("[SKILL-02]\n")
    with pytest.raises(ValueError):
        evidence.load_read(str(path))


def test_a_missing_read_registry_is_empty(tmp_path):
    assert evidence.load_read(str(tmp_path / "nope.toml")) == {}


def test_the_committed_read_tasks_are_all_on_the_train_side():
    """A task that was read to decide an edit is train. The split and the registry must agree."""
    from tests.e2e.skill_eval import graded_task
    from tests.e2e.skill_eval.split import default_split

    read = evidence.load_read(evidence.READ_PATH)
    train = set(default_split().train)
    known = {task.id for task in graded_task.all_tasks()}
    assert set(read) <= known, "a read entry names a task that is not in the corpus"
    assert set(read) <= train, f"read but not on train: {sorted(set(read) - train)}"


def test_main_prints_the_report_from_the_ledger(tmp_path, capsys):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("")
    code = evidence.main(["--ledger", str(ledger), "--criteria", str(criteria), "--root", str(tmp_path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "no verdict" in out


# --- a run that was stopped by its cap and finished by a continuation --------------------------------


def test_a_continuation_joins_the_run_it_continues(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    lines = run_lines(only_skill_passes(4))
    first = [l for l in lines if l["run_index"] < 2 or l["task_id"] in ("SKILL-31", "SKILL-32")]
    rest = [l for l in lines if l not in first]
    a = write_run(tmp_path, "ladder-1", first)
    b = write_run(tmp_path, "ladder-2", rest)
    events = [
        event(1, a, criteria_sha256=sha, cost_usd=40.0, aborted=True),
        event(2, b, criteria_sha256=sha, cost_usd=9.0, continues="IMP-001"),
    ]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    row = report["skills"][SKILL]
    assert row["verdict"] == "first run qualifies, awaiting replication"
    assert row["spend_usd"] == 49.0
    assert len(row["run_results"]) == 1, "the continuation is part of the run, not a replication"
    assert row["run_results"][0]["pairs"] == 15


def test_a_continuation_on_another_build_is_refused(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    lines = run_lines(even)
    a = write_run(tmp_path, "ladder-1", lines[:20])
    other = [{**l, "build": {**BUILD, "commit": "d" * 40}} for l in lines[20:]]
    b = write_run(tmp_path, "ladder-2", other)
    events = [event(1, a, criteria_sha256=sha), event(2, b, criteria_sha256=sha, continues="IMP-001")]
    report = evidence.skills_report(
        events,
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert "one binary" in report["skills"][SKILL]["verdict"]


def test_render_reports_tokens_for_both_arms():
    row = evaluate(run_lines(only_skill_passes(4)))
    text = evidence.render_row(SKILL, {**row, "ledger_ids": ["IMP-001"], "spend_usd": 1.0,
                                         "builds": [("1.5.0", "ccccccc")], "train_runs": 0})
    assert "tokens" in text
    assert "tools in" in text and "treated in" in text


def test_markdown_gives_each_skill_a_heading_and_a_table_with_its_intervals():
    row = evaluate(run_lines(only_skill_passes(4)))
    report = {
        "refused": None,
        "skills": {
            SKILL: {
                **row,
                "run_results": [row],
                "ledger_ids": ["IMP-001"],
                "spend_usd": 12.3,
                "builds": [("1.5.0", "ccccccc")],
                "train_runs": 0,
                "heldout_tasks": TASKS,
            }
        },
    }
    text = evidence.render_markdown(report)
    assert f"### {SKILL}" in text
    assert "| Measure | Value | 95% interval |" in text
    assert "IMP-001" in text and "1.5.0" in text and "ccccccc" in text
    assert "b = 4" in text or "| Only the skill passed (b) | 4 |" in text


def test_markdown_of_a_refused_report_says_refused():
    assert "REFUSED" in evidence.render_markdown({"refused": "criteria.md changed", "skills": {}})


def test_main_prints_markdown_when_asked(tmp_path, capsys):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("")
    code = evidence.main(["--ledger", str(ledger), "--criteria", str(criteria), "--root", str(tmp_path), "--markdown"])
    assert code == 0
    assert "### " in capsys.readouterr().out


# --- the model is part of what was measured ---------------------------------------------------------


def test_two_models_in_one_run_get_no_verdict():
    lines = run_lines(even)
    for line in lines:
        line["model"] = "bedrock-oai/global.openai.gpt-6-luna"
        line["effort"] = "high"
    lines[3]["effort"] = "low"
    assert "model" in evaluate(lines)["verdict"]


def test_replication_on_another_model_is_refused():
    a = run_lines(only_skill_passes(4))
    b = run_lines(only_skill_passes(4))
    for line in a:
        line["model"] = "openai/gpt-4.1"
    for line in b:
        line["model"] = "bedrock-oai/global.openai.gpt-6-luna"
    verdict = verdict_of([a, b])
    assert verdict["verdict"].startswith("no verdict") and "model" in verdict["verdict"]


def test_lines_with_no_model_field_are_one_unrecorded_model_and_still_pool():
    assert evaluate(run_lines(even))["verdict"] != "no verdict (the run's sessions name more than one model)"


def test_the_report_row_names_the_model():
    row = evaluate(run_lines(even))
    text = evidence.render_row(SKILL, {**row, "ledger_ids": [], "spend_usd": 0, "builds": [], "train_runs": 0, "models": ["m high"]})
    assert "m high" in text


# --- two studies on two models are reported side by side, never pooled ---------------------------------


def _with_model(lines, model, effort):
    return [{**line, "model": model, "effort": effort} for line in lines]


def test_runs_on_different_models_get_separate_rows(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    old = write_run(tmp_path, "ladder-1", _with_model(run_lines(only_skill_passes(4)), "openai/gpt-4.1", None))
    new = write_run(tmp_path, "ladder-2", _with_model(run_lines(even), "bedrock-oai/luna", "high"))
    events = [event(1, old, criteria_sha256=sha), event(2, new, criteria_sha256=sha)]
    report = evidence.skills_report(
        events, criteria_path=str(criteria), heldout={SKILL: set(TASKS)}, task_skill={t: SKILL for t in TASKS}
    )
    rows = report["skills"]
    assert len(rows) == 2
    old_row = next(r for k, r in rows.items() if "gpt-4.1" in k)
    new_row = next(r for k, r in rows.items() if "luna" in k)
    assert old_row["verdict"] == "first run qualifies, awaiting replication"
    assert new_row["verdict"] == "not net positive"
    assert old_row["ledger_ids"] == ["IMP-001"] and new_row["ledger_ids"] == ["IMP-002"]


def test_a_single_model_keeps_the_plain_skill_key(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    run = write_run(tmp_path, "ladder-1", _with_model(run_lines(even), "bedrock-oai/luna", "high"))
    report = evidence.skills_report(
        [event(1, run, criteria_sha256=sha)],
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert list(report["skills"]) == [SKILL]


def test_a_replication_on_the_same_model_pools_within_that_model(tmp_path):
    criteria = tmp_path / "criteria.md"
    criteria.write_text("c\n")
    sha = evidence.sha256_file(str(criteria))
    a = write_run(tmp_path, "ladder-1", _with_model(run_lines(only_skill_passes(4)), "bedrock-oai/luna", "high"))
    b = write_run(tmp_path, "ladder-2", _with_model(run_lines(only_skill_passes(4)), "bedrock-oai/luna", "high"))
    report = evidence.skills_report(
        [event(1, a, criteria_sha256=sha), event(2, b, criteria_sha256=sha)],
        criteria_path=str(criteria),
        heldout={SKILL: set(TASKS)},
        task_skill={t: SKILL for t in TASKS},
    )
    assert report["skills"][SKILL]["verdict"] == "net positive"

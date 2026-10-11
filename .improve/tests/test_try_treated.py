"""`improve try` when the treatment is not one fixed arm.

A project may run one treated arm per task (here `memory+<doc>`, one document preloaded per task)
instead of a single `memory` arm for the whole holdout. Four things follow, and each has a test:

- the treated sessions are found by an arm-name prefix, not an exact name;
- the run says whether the treatment was actually applied in each session, because an arm that
  nobody used measures the label and not the treatment;
- a task that is not in the full holdout can be tried if the adapter names it and the results
  directory has an earlier run of it to compare with;
- when the pass counts do not move, a change in the number of calls is reported, because a
  treatment that costs twice as much for the same passes is not "no change".

A fake runner stands in for the harness, so no test starts a session.
"""

import json
from pathlib import Path

import pytest

import improve
from test_improve import NOW, make_config, nightly
from test_try import DRY, ledger


def rule(**over):
    base = dict(
        tasks=("S-1", "S-2"),
        command=("run", "--task", "{task}", "--repeats", "{repeats}", "--cap", "{cap}", "--out", "{out}"),
        dry_run_flag=DRY,
        repeats=3,
        cost_regex=r"s \$(\d+\.\d+)",
        env={},
        timeout_seconds=3600,
        estimate_note="",
        treated_prefix="memory+",
        applied_field="loaded",
        applied_label="document loaded",
        before_glob="hist-*.runs.jsonl",
        judge_calls=True,
        treated_exclude=("memory+all",),
    )
    base.update(over)
    return improve.TryRule(**base)


def write_history_with_excluded_arm(directory, task):
    """An arm that starts with the prefix but is not a per-task treatment (the pooled one)."""
    lines = [json.dumps({"task_id": task, "arm": "memory+all", "passed": False, "tool_calls": 99, "run_index": i}) for i in range(3)]
    path = directory / "hist-9.runs.jsonl"
    path.write_text("\n".join(lines) + "\n")


def write_history(directory: Path, task: str, plain, doc, *, plain_calls=10, doc_calls=10, name="hist-1.runs.jsonl"):
    lines = []
    for arm, results, calls in (("plain", plain, plain_calls), ("memory+guide", doc, doc_calls)):
        for i, ok in enumerate(results):
            lines.append(json.dumps({"task_id": task, "arm": arm, "passed": bool(ok), "tool_calls": calls, "run_index": i, "loaded": True if arm != "plain" else None}))
    (directory / name).write_text("\n".join(lines) + "\n")


class Runner:
    def __init__(self, plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=10, loaded=(True, True, True), returncode=0):
        self.plain, self.doc, self.plain_calls, self.doc_calls = plain, doc, plain_calls, doc_calls
        self.loaded, self.returncode, self.calls = loaded, returncode, []

    def __call__(self, argv, env, timeout, live=False):
        self.calls.append(list(argv))
        if DRY in argv:
            return improve.RunResult(0, "Estimate: 6 sessions, ~$0.51.")
        out = Path(argv[argv.index("--out") + 1])
        task = argv[argv.index("--task") + 1]
        runs, lines = [], []
        for arm, results, calls in (("plain", self.plain, self.plain_calls), ("memory+guide", self.doc, self.doc_calls)):
            for i, ok in enumerate(results):
                run = {"task_id": task, "arm": arm, "passed": bool(ok), "tool_calls": calls, "run_index": i, "timed_out": False, "seconds": 20.0}
                if arm != "plain":
                    run["loaded"] = self.loaded[i]
                runs.append(run)
                lines.append(f"{task:<6} {arm:<14} {'PASS' if ok else 'FAIL'} {calls} calls 20.0s $0.30")
        out.write_text(json.dumps({"runs": runs, "provenance": {"measured_at": "2026-10-12T09:00:00Z"}}))
        return improve.RunResult(self.returncode, "\n".join(lines))


@pytest.fixture
def world(tmp_path):
    cfg = make_config(tmp_path, tries=(rule(),))
    cfg.results_dir.mkdir()
    write_history(cfg.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1))
    return cfg


def go(argv, cfg, *, runner=None, answer=True):
    lines = []
    runner = runner or Runner()
    code = improve.main(
        argv, config=cfg, nightly=nightly(),
        validator=lambda t: improve.Validation(ok=True, detail=""),
        container_running=lambda name: True, out=lines.append, now=NOW,
        runner=runner, confirm=lambda p: answer, who="tom",
        git_state=lambda: ("abc1234def", False),
    )
    return code, "\n".join(lines), runner


# ---- a task that is not in the full holdout ----------------------------------------------------


def test_a_task_the_adapter_names_is_tried_without_being_in_the_holdout(world):
    code, text, runner = go(["try", "S-1", "--yes"], world)
    assert code == 0, text
    assert any(DRY not in c for c in runner.calls)
    assert "IMP-0001" in text


def test_a_named_task_with_no_earlier_run_is_refused_before_spending(world):
    code, text, runner = go(["try", "S-2", "--yes"], world)
    assert code == 2 and "no earlier run of S-2" in text
    assert runner.calls == [], "nothing runs and nothing is estimated"
    assert ledger(world) == []


def test_a_task_the_adapter_does_not_name_is_still_refused(world):
    code, text, runner = go(["try", "S-9", "--yes"], world)
    assert code == 2 and runner.calls == []


def test_the_history_must_have_both_sides_of_the_comparison(world):
    only_plain = [json.dumps({"task_id": "S-2", "arm": "plain", "passed": True, "tool_calls": 5, "run_index": 0})]
    (world.results_dir / "hist-2.runs.jsonl").write_text("\n".join(only_plain) + "\n")
    code, text, _ = go(["try", "S-2", "--yes"], world)
    assert code == 2 and "no earlier run of S-2" in text


def test_the_newest_history_file_with_both_sides_is_the_before(world):
    write_history(world.results_dir, "S-1", plain=(0, 0, 0), doc=(0, 0, 0), name="hist-0.runs.jsonl")
    code, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(plain=(1, 1, 1), doc=(1, 1, 1)))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["before"]["memory+"] == [3, 3], "hist-1 (sorted last) is the before, not hist-0"


def test_a_named_task_uses_the_history_even_when_the_holdout_has_it(world):
    from test_improve import write_record
    write_record(world.results_dir, "run-full.json", {f"T-{i}": (True, True) for i in range(101, 131)} | {"S-1": (False, False)})
    code, text, runner = go(["try", "S-1", "--yes"], world)
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["before"]["memory+"] == [3, 3], "the history's per-task arm, not the holdout's single treated arm"


# ---- the treated arm is found by prefix --------------------------------------------------------


def test_the_treated_sessions_are_the_arms_with_the_prefix(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(0, 0, 0))
    code, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(plain=(1, 1, 1), doc=(1, 1, 1)))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["label"] == "fixed"
    assert verdict["after"]["memory+"] == [3, 3] and verdict["after"]["plain"] == [3, 3]
    assert "memory" in text


def test_an_excluded_arm_is_not_a_treated_session(world):
    write_history_with_excluded_arm(world.results_dir, "S-1")
    code, text, _ = go(["try", "S-1", "--yes"], world)
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["before"]["memory+"] == [3, 3], "memory+all (0 of 3, 99 calls) is not the per-task arm"
    assert verdict["calls"]["memory+"][0] == 10


def test_a_record_with_no_treated_sessions_is_incomplete(world):
    code, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(doc=()))
    assert code == 7 and "nothing to compare" in text


# ---- was the treatment applied -----------------------------------------------------------------


def test_the_run_says_how_many_sessions_applied_the_treatment(world):
    code, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(loaded=(True, True, False)))
    assert "document loaded in 2 of 3" in text
    run = next(e for e in ledger(world) if e["event"] == "run")
    assert run["applied"] == {"yes": 2, "no": 1, "unknown": 0}


def test_a_treatment_nobody_applied_is_called_out_and_not_credited(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(0, 0, 0))
    code, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(plain=(1, 1, 1), doc=(1, 1, 1), loaded=(False, False, False)))
    assert "document loaded in 0 of 3" in text
    assert "not the treatment" in text
    assert "Improve: IMP" not in text, "an arm nobody used earns no commit trailer"


def test_without_an_applied_field_nothing_is_counted(tmp_path):
    cfg = make_config(tmp_path, tries=(rule(applied_field="", applied_label=""),))
    cfg.results_dir.mkdir()
    write_history(cfg.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1))
    code, text, _ = go(["try", "S-1", "--yes"], cfg)
    run = next(e for e in ledger(cfg) if e["event"] == "run")
    assert "applied" not in run and "loaded in" not in text


# ---- cost: calls -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "before_calls,after_calls,label",
    [
        (20, 12, "cheaper"),
        (20, 15, "cheaper"),
        (20, 16, "no change"),
        (20, 26, "costlier"),
        (20, 25, "costlier"),
        (20, 24, "no change"),
    ],
)
def test_calls_decide_a_verdict_the_passes_leave_open(world, before_calls, after_calls, label):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=before_calls)
    go(["try", "S-1", "--yes"], world, runner=Runner(plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=after_calls))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["label"] == label
    assert verdict["calls"]["memory+"] == [before_calls, after_calls]


def test_calls_are_judged_against_the_baseline_arm_in_the_same_run(world):
    # Everything got cheaper since the history (tool changes): baseline 10 -> 5, treated 20 -> 10.
    # The treated arm is still twice the baseline, so the treatment did not get cheaper.
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=20)
    go(["try", "S-1", "--yes"], world, runner=Runner(plain_calls=5, doc_calls=10))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["label"] == "no change"
    assert verdict["calls"]["memory+"] == [20, 10], "the absolute means are still recorded"
    assert verdict["relative_calls"]["memory+"] == [2.0, 2.0]


def test_a_treatment_that_got_dearer_while_the_baseline_stood_still_is_costlier(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=20)
    go(["try", "S-1", "--yes"], world, runner=Runner(plain_calls=5, doc_calls=15))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["label"] == "costlier", "3x the baseline against 2x before"
    assert verdict["relative_calls"]["memory+"] == [2.0, 3.0]


def test_the_relative_figure_is_printed(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1), plain_calls=10, doc_calls=20)
    _, text, _ = go(["try", "S-1", "--yes"], world, runner=Runner(plain_calls=10, doc_calls=12))
    assert "2.0x the baseline, now 1.2x" in text


def test_passes_win_over_calls(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(0, 0, 0), doc_calls=5)
    go(["try", "S-1", "--yes"], world, runner=Runner(plain=(1, 1, 1), doc=(1, 1, 1), doc_calls=40))
    verdict = next(e for e in ledger(world) if e["event"] == "verdict")
    assert verdict["label"] == "fixed", "more calls does not undo a fix"


def test_a_cheaper_verdict_offers_the_commit_trailer_and_a_costlier_one_does_not(world):
    write_history(world.results_dir, "S-1", plain=(1, 1, 1), doc=(1, 1, 1), doc_calls=20)
    _, cheaper, _ = go(["try", "S-1", "--yes"], world, runner=Runner(doc_calls=10))
    assert "Verdict: cheaper" in cheaper and "Improve: IMP-0001" in cheaper
    _, costlier, _ = go(["try", "S-1", "--yes"], world, runner=Runner(doc_calls=30))
    assert "Verdict: costlier" in costlier and "Improve: IMP" not in costlier
    assert "revert" in costlier


def test_the_threshold_for_calls_is_stated_so_a_label_can_be_checked():
    assert improve.CALLS_BAND == 0.25


# ---- the adapter -------------------------------------------------------------------------------


def test_the_new_try_keys_round_trip_from_toml(tmp_path):
    path = tmp_path / ".improve" / "project.toml"
    path.parent.mkdir()
    path.write_text(
        '[project]\nname="x"\nresults_dir="r"\ntasks_dir="t"\nledger="l"\n'
        '[holdout.baseline]\narm="a"\n[holdout.treated]\narm="b"\n'
        '[[try]]\ncommand=["go"]\ntreated_prefix="b+"\napplied_field="loaded"\n'
        'applied_label="document loaded"\nbefore_glob="h-*.jsonl"\njudge_calls=true\n'
        'treated_exclude=["b+all"]\n'
    )
    got = improve.load_config(path).tries[0]
    assert (got.treated_prefix, got.applied_field, got.applied_label, got.before_glob, got.judge_calls) == (
        "b+", "loaded", "document loaded", "h-*.jsonl", True)
    assert got.treated_exclude == ("b+all",)
    plain = improve.TryRule.__dataclass_fields__
    assert plain["treated_prefix"].default == "" and plain["judge_calls"].default is False


def test_this_projects_adapter_has_rules_for_the_skill_tasks():
    """Every skill task has a `[[try]]` rule whose `--side` is the side the split gives it, so a task
    that moves to train (135 moved seven) cannot keep a rule that asks for the holdout."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from tests.e2e.skill_eval.graded_task import skill_corpus
    from tests.e2e.skill_eval.split import default_split

    cfg = improve.load_config(Path(__file__).resolve().parents[1] / "project.toml")
    split = default_split()
    for task in skill_corpus():
        rule = improve.try_rule_for(cfg, task.id)
        assert rule is not None and rule.tasks is not None and task.id in rule.tasks, task.id
        assert rule.treated_prefix == "tools+" and rule.applied_field == "skill_loaded", task.id
        assert "tools+skills" in rule.treated_exclude, "the pooled all-skills arm is not a per-task skill"
        assert rule.judge_calls and rule.before_glob, task.id
        assert "--skill" in rule.command and "all" in rule.command, task.id
        side = rule.command[rule.command.index("--side") + 1]
        assert side == split.side_of(task.id), f"{task.id}: rule asks for {side}, split says {split.side_of(task.id)}"
    assert improve.try_rule_for(cfg, "CORPUS-40").treated_prefix == "", "other tasks keep the single arm"


def test_the_ai_hub_tasks_run_against_the_ai_hub_container():
    """SKILL-22 to 25 need the 2026.3 AI Hub build; the generic rules would run them on iris-dev-iris."""
    cfg = improve.load_config(Path(__file__).resolve().parents[1] / "project.toml")
    for task in ("SKILL-22", "SKILL-23", "SKILL-24", "SKILL-25"):
        rule = improve.try_rule_for(cfg, task)
        cmd = list(rule.command)
        assert cmd[cmd.index("--web-port") + 1] == "52781", task
        assert cmd[cmd.index("--container") + 1] == "iad-aihub-iris", task
        assert rule.treated_prefix == "tools+" and rule.applied_field == "skill_loaded" and rule.judge_calls, task
    generic = improve.try_rule_for(cfg, "SKILL-01")
    assert "--web-port" not in generic.command and "--container" not in generic.command
    assert "SKILL-24" not in generic.tasks

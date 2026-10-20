"""`improve try`: re-run one task after a change, and say whether the change helped.

This is the first verb that spends money, so most of these tests are about the ways it must refuse:
nothing runs without an estimate shown and a yes, the cap is always passed and is never larger than
what is left of the week, a task that is not sound is never paid for, and a task someone else is
working is not touched. Every run, its measured cost and its verdict is written to the ledger under an
`IMP-NNNN` id, because a claim of improvement has to point at those entries (ADR 0003).

A fake runner stands in for the harness, so no test starts a session.
"""

import json
from pathlib import Path

import pytest

import improve
from test_improve import NOW, make_config, nightly, task_file, write_record

DRY = "--dry-run"


class Runner:
    """Stands in for the harness. Dry runs answer with an estimate; real runs write the run record that
    the command's `{out}` argument names, and print one cost line per session."""

    def __init__(
        self, passes_by_arm=None, costs=(0.40,), returncode=0, write=True, repeats=3
    ):
        self.passes_by_arm = passes_by_arm or {"plain": [1, 1, 1], "memory": [1, 1, 1]}
        self.costs, self.returncode, self.write, self.repeats = (
            costs,
            returncode,
            write,
            repeats,
        )
        self.calls = []

    def __call__(self, argv, env, timeout, live=False):
        self.calls.append(list(argv))
        if DRY in argv:
            return improve.RunResult(
                0, "Estimate: 6 sessions, ~$0.51 at $0.085/session.\n  T-40"
            )
        out = Path(argv[argv.index("--out") + 1])
        task = argv[argv.index("--task") + 1]
        lines, runs = [], []
        i = 0
        for arm, results in self.passes_by_arm.items():
            for r, ok in enumerate(results):
                cost = self.costs[i % len(self.costs)]
                i += 1
                lines.append(
                    f"{task:<8} {arm:<10} {'PASS' if ok else 'FAIL'}  9 calls   31.0s ${cost:.2f}"
                )
                runs.append(
                    {
                        "task_id": task,
                        "arm": arm,
                        "passed": bool(ok),
                        "tool_calls": 9,
                        "seconds": 31.0,
                        "timed_out": False,
                        "run_index": r,
                    }
                )
        if self.write:
            out.write_text(
                json.dumps(
                    {
                        "runs": runs,
                        "provenance": {"measured_at": "2026-10-12T09:00:00Z"},
                    }
                )
            )
        return improve.RunResult(self.returncode, "\n".join(lines))


def try_rule(**over):
    base = dict(
        tasks=None,
        command=(
            "run",
            "--task",
            "{task}",
            "--repeats",
            "{repeats}",
            "--cap",
            "{cap}",
            "--out",
            "{out}",
        ),
        dry_run_flag=DRY,
        repeats=3,
        cost_regex=r"s \$(\d+\.\d+)",
        env={},
        timeout_seconds=3600,
        estimate_note="Estimates have run 3 to 35 times low. The cap is what bounds the spend.",
    )
    base.update(over)
    return improve.TryRule(**base)


@pytest.fixture
def world(tmp_path):
    cfg = make_config(tmp_path, tries=(try_rule(),))
    cfg.results_dir.mkdir()
    outcomes = {f"T-{i}": (True, True) for i in range(101, 131)}
    outcomes["T-40"] = (False, False)
    outcomes["T-19"] = (True, False)
    for t in outcomes:
        task_file(cfg.tasks_dir, t)
    write_record(cfg.results_dir, "run-full.json", outcomes)
    return cfg


def go(
    argv, cfg, *, runner=None, answer=True, who="tom", night=None, validator=None, git=("abc1234def", False)
):
    lines, asked = [], []

    def confirm(prompt):
        asked.append(prompt)
        return answer

    runner = runner or Runner()
    code = improve.main(
        argv,
        config=cfg,
        nightly=night or nightly(),
        validator=validator or (lambda t: improve.Validation(ok=True, detail="")),
        container_running=lambda name: True,
        out=lines.append,
        now=NOW,
        runner=runner,
        confirm=confirm,
        who=who,
        git_state=lambda: git,
    )
    return code, "\n".join(lines), runner, asked


def ledger(cfg):
    if not cfg.ledger.exists():
        return []
    return [
        json.loads(line) for line in cfg.ledger.read_text().splitlines() if line.strip()
    ]


# ---- asking first ------------------------------------------------------------------------------


def test_it_shows_the_estimate_and_the_cap_then_asks(world):
    code, text, runner, asked = go(["try", "T-40"], world)
    assert len(asked) == 1
    assert "~$0.51" in text, "the harness's own estimate is shown"
    assert "3 to 35 times low" in text, "with the adapter's warning about it"
    assert "cap of $5.00" in text
    assert any(DRY in c for c in runner.calls), "the estimate came from a dry run"


def test_a_no_runs_nothing_and_writes_nothing(world):
    code, text, runner, asked = go(["try", "T-40"], world, answer=False)
    assert code == 0 and "not run" in text.lower()
    assert all(DRY in c for c in runner.calls), "only the free dry run happened"
    assert ledger(world) == []


def test_yes_skips_the_question_but_not_the_estimate(world):
    code, text, runner, asked = go(["try", "T-40", "--yes"], world)
    assert asked == [] and "~$0.51" in text
    assert any(DRY not in c for c in runner.calls), "and the run happened"


# ---- the cap -----------------------------------------------------------------------------------


def test_the_real_command_always_gets_a_cap(world):
    code, text, runner, _ = go(["try", "T-40", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "5.0"
    assert real[real.index("--task") + 1] == "T-40"
    assert real[real.index("--repeats") + 1] == "3"


def test_the_cap_is_never_more_than_what_is_left_of_the_week(world):
    world.ledger.write_text(
        json.dumps(
            {
                "ts": "2026-10-12T01:00:00Z",
                "id": "IMP-0001",
                "event": "run",
                "cost_usd": 58.0,
            }
        )
        + "\n"
    )
    code, text, runner, _ = go(["try", "T-40", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "2.0", "$60 a week, $58 spent"
    assert "$2.00 left" in text


def test_an_exhausted_week_refuses_before_spending(world):
    world.ledger.write_text(
        json.dumps(
            {
                "ts": "2026-10-12T01:00:00Z",
                "id": "IMP-0001",
                "event": "run",
                "cost_usd": 60.0,
            }
        )
        + "\n"
    )
    code, text, runner, asked = go(["try", "T-40", "--yes"], world)
    assert code == 5 and "weekly" in text.lower()
    assert all(DRY in c for c in runner.calls) and asked == []


def test_last_weeks_spend_does_not_count_against_this_week(world):
    world.ledger.write_text(
        json.dumps(
            {
                "ts": "2026-10-02T01:00:00Z",
                "id": "IMP-0001",
                "event": "run",
                "cost_usd": 60.0,
            }
        )
        + "\n"
    )
    code, text, runner, _ = go(["try", "T-40", "--yes"], world)
    assert code == 0 and any(DRY not in c for c in runner.calls)


def test_an_explicit_cap_above_the_default_is_allowed_but_not_above_the_week(world):
    code, _, runner, _ = go(["try", "T-40", "--yes", "--cap", "8"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--cap") + 1] == "8.0"
    spent = sum(e.get("cost_usd", 0) for e in ledger(world))
    code, _, runner, _ = go(["try", "T-19", "--yes", "--cap", "500"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert float(real[real.index("--cap") + 1]) == pytest.approx(60.0 - spent)


# ---- refusing to spend on the wrong thing ------------------------------------------------------


def test_a_task_that_is_not_sound_is_never_paid_for(world):
    code, text, runner, asked = go(
        ["try", "T-40", "--yes"],
        world,
        validator=lambda t: improve.Validation(
            ok=False, detail="reference solution failed its check"
        ),
    )
    assert code == 1 and "task is broken" in text.lower()
    assert runner.calls == [] and asked == []


def test_a_task_nobody_ran_last_time_is_refused(world):
    code, text, runner, _ = go(["try", "T-999", "--yes"], world)
    assert (
        code == 2 and "not in the last holdout" in text.lower() and runner.calls == []
    )


def test_a_task_with_no_try_rule_says_so(world):
    cfg = make_config(world.root, tries=(try_rule(tasks=("OTHER-1",)),))
    code, text, runner, _ = go(["try", "T-40", "--yes"], cfg)
    assert code == 2 and "[[try]]" in text and runner.calls == []


def test_without_a_task_it_takes_the_top_of_the_worklist(world):
    code, text, runner, _ = go(["try", "--yes"], world)
    real = next(c for c in runner.calls if DRY not in c)
    assert real[real.index("--task") + 1] == "T-40"


# ---- the ledger and the id ---------------------------------------------------------------------


def test_one_run_leaves_a_claim_a_run_and_a_verdict_under_one_id(world):
    code, text, runner, _ = go(["try", "T-40", "--yes"], world)
    events = ledger(world)
    assert [e["event"] for e in events] == ["claim", "run", "verdict"]
    assert {e["id"] for e in events} == {"IMP-0001"} and all(
        e["task"] == "T-40" for e in events
    )
    assert events[0]["who"] == "tom"
    assert "IMP-0001" in text and "Improve: IMP-0001" in text, (
        "the trailer to put in the commit"
    )


def test_cost_is_summed_from_the_measured_session_lines(world):
    runner = Runner(costs=(0.40, 0.60))
    go(["try", "T-40", "--yes"], world, runner=runner)
    run = next(e for e in ledger(world) if e["event"] == "run")
    assert run["sessions"] == 6 and run["cost_usd"] == pytest.approx(3.0)
    assert run["cap"] == 5.0 and run["aborted"] is False
    assert run["record"].endswith("try-IMP-0001.json")


def test_the_spend_shows_up_in_status_afterwards(world):
    go(["try", "T-40", "--yes"], world, runner=Runner(costs=(0.5,)))
    lines = []
    improve.main(["status"], config=world, nightly=nightly(), out=lines.append, now=NOW)
    assert "$3.00" in "\n".join(lines)


def test_ids_count_up_across_iterations(world):
    go(["try", "T-40", "--yes"], world)
    go(["try", "T-19", "--yes"], world)
    assert [e["id"] for e in ledger(world) if e["event"] == "verdict"] == [
        "IMP-0001",
        "IMP-0002",
    ]


def test_a_second_holder_cannot_take_an_open_item(world):
    # tom claims it and the run is cut off before a verdict is written.
    world.ledger.write_text(
        json.dumps(
            {
                "ts": "2026-10-12T08:00:00Z",
                "id": "IMP-0001",
                "event": "claim",
                "who": "tom",
                "task": "T-40",
            }
        )
        + "\n"
    )
    code, text, runner, _ = go(["try", "T-40", "--yes"], world, who="ann")
    assert code == 6 and "tom" in text and "IMP-0001" in text
    assert all(DRY in c for c in runner.calls)


def test_the_same_holder_resumes_their_own_open_item(world):
    world.ledger.write_text(
        json.dumps(
            {
                "ts": "2026-10-12T08:00:00Z",
                "id": "IMP-0001",
                "event": "claim",
                "who": "tom",
                "task": "T-40",
            }
        )
        + "\n"
    )
    code, text, runner, _ = go(["try", "T-40", "--yes"], world, who="tom")
    assert code == 0
    assert {e["id"] for e in ledger(world)} == {"IMP-0001"}, "no second id"


# ---- the verdict -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "before,after,label",
    [
        (((0, 1), (0, 1)), {"plain": [1, 1, 1], "memory": [1, 1, 1]}, "fixed"),
        (((0, 1), (0, 1)), {"plain": [1, 1, 0], "memory": [0, 0, 0]}, "better"),
        (((0, 1), (0, 1)), {"plain": [0, 0, 0], "memory": [0, 0, 0]}, "no change"),
        (((1, 1), (1, 1)), {"plain": [1, 1, 1], "memory": [0, 0, 1]}, "worse"),
        (((0, 1), (1, 1)), {"plain": [1, 1, 1], "memory": [0, 0, 0]}, "mixed"),
        # One pass in three is within noise and must never be called an improvement. This is the
        # first real run: nothing had been changed, one session of six happened to pass, and the
        # judge called it "better".
        (((0, 1), (0, 1)), {"plain": [0, 0, 0], "memory": [1, 0, 0]}, "no change"),
        (((0, 1), (0, 1)), {"plain": [0, 1, 0], "memory": [1, 0, 0]}, "no change"),
        (((1, 1), (1, 1)), {"plain": [1, 1, 0], "memory": [1, 1, 1]}, "no change"),
        (((1, 3), (1, 3)), {"plain": [1, 1, 1], "memory": [1, 0, 0]}, "better"),
    ],
)
def test_the_verdict_label(before, after, label):
    got = improve.judge(
        before={"plain": before[0], "memory": before[1]},
        after={arm: (sum(r), len(r)) for arm, r in after.items()},
    )
    assert got == label


def test_the_result_is_stated_per_arm_and_does_not_oversell_three_repeats(world):
    runner = Runner(passes_by_arm={"plain": [1, 1, 0], "memory": [1, 1, 1]})
    code, text, _, _ = go(["try", "T-40", "--yes"], world, runner=runner)
    assert "plain agent" in text and "was 0/1" in text and "now 2/3" in text
    assert "with memory" in text and "now 3/3" in text
    assert "direction, not proof" in text


# ---- when the run does not finish --------------------------------------------------------------


def test_a_run_cut_off_by_the_cap_is_recorded_and_its_spend_still_counts(world):
    runner = Runner(returncode=3, write=False, costs=(1.5,))
    code, text, _, _ = go(["try", "T-40", "--yes"], world, runner=runner)
    assert code == 7 and "did not finish" in text.lower()
    events = ledger(world)
    run = next(e for e in events if e["event"] == "run")
    assert run["aborted"] is True and run["cost_usd"] == pytest.approx(9.0)
    verdict = next(e for e in events if e["event"] == "verdict")
    assert verdict["label"] == "incomplete"


# ---- the adapter -------------------------------------------------------------------------------


def test_the_try_rule_round_trips_from_toml(tmp_path):
    path = tmp_path / ".improve" / "project.toml"
    path.parent.mkdir()
    path.write_text("""
[project]
name = "demo"
results_dir = "r"
tasks_dir = "t"
ledger = ".improve/ledger.jsonl"
[holdout.baseline]
arm = "a"
label = "plain"
[holdout.treated]
arm = "b"
label = "better"
[[try]]
tasks = ["X-1"]
command = ["go", "{task}"]
dry_run_flag = "--check"
repeats = 5
cost_regex = 'cost=(\\d+)'
timeout_seconds = 60
estimate_note = "low"
[try.env]
K = "v"
[[try]]
command = ["go-all", "{task}"]
""")
    cfg = improve.load_config(path)
    first, default = cfg.tries
    assert first.tasks == ("X-1",) and first.command == ("go", "{task}")
    assert (
        first.dry_run_flag == "--check"
        and first.repeats == 5
        and first.cost_regex == r"cost=(\d+)"
    )
    assert (
        first.timeout_seconds == 60
        and first.estimate_note == "low"
        and first.env == {"K": "v"}
    )
    assert default.tasks is None and default.repeats == 3, "documented defaults"


def test_a_misspelt_try_key_is_an_error(tmp_path):
    path = tmp_path / ".improve" / "project.toml"
    path.parent.mkdir()
    path.write_text(
        '[project]\nname="x"\nresults_dir="r"\ntasks_dir="t"\nledger="l"\n'
        '[holdout.baseline]\narm="a"\n[holdout.treated]\narm="b"\n'
        '[[try]]\ncommand=["x"]\nrepeat=3\n'
    )
    with pytest.raises(improve.ConfigError, match="repeat"):
        improve.load_config(path)


def test_this_projects_adapter_declares_how_to_try_a_task():
    cfg = improve.load_config(Path(__file__).resolve().parents[1] / "project.toml")
    assert cfg.tries, "the iad adapter has a [[try]] rule"
    rule = improve.try_rule_for(cfg, "CORPUS-40")
    joined = " ".join(rule.command)
    assert "--cap" in joined and "{cap}" in joined and "--out" in joined
    assert "bare" not in joined and joined.count("--arm") == 2, (
        "re-runs skip the arm that always fails"
    )


# ---- what the verdict rests on -----------------------------------------------------------------


def test_the_run_records_which_commit_and_whether_the_tree_was_dirty(world):
    code, text, _, _ = go(["try", "T-40", "--yes"], world, git=("abc1234def", True))
    run = next(e for e in ledger(world) if e["event"] == "run")
    assert run["commit"] == "abc1234def" and run["dirty"] is True
    assert "abc1234" in text and "uncommitted changes" in text


def test_a_clean_tree_is_said_to_be_clean(world):
    code, text, _, _ = go(["try", "T-40", "--yes"], world, git=("abc1234def", False))
    assert "abc1234" in text and "clean" in text


def test_a_verdict_that_is_noise_does_not_offer_the_commit_trailer(world):
    runner = Runner(passes_by_arm={"plain": [0, 0, 0], "memory": [1, 0, 0]})
    code, text, _, _ = go(["try", "T-40", "--yes"], world, runner=runner)
    assert "Verdict: no change" in text
    assert "Improve: IMP" not in text, "no improvement, so nothing to cite"
    assert "within noise" in text


def test_the_threshold_is_stated_so_the_label_can_be_checked():
    assert improve.NOISE_BAND == 0.5

"""`improve status` and `improve next`: the one place that says what to work on.

Today the improvement loop is three CLIs and about twenty flags. These two verbs are the read-only
front of a simpler one: what is the state, what is failing, what is the next thing to do. They cost
nothing and must stay that way, so the last test fails if anything in them could start a session.

The tests build a small results directory and inject stand-ins for `gh` and for the task validator,
so they run offline in the nightly's pytest step.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.e2e.skill_eval import improve

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


def write_ladder(directory: Path, name: str, outcomes: dict, *, measured_at="2026-09-19T06:48:40Z",
                 side=None, published=None):
    """`outcomes` maps task id to (passed with tools alone, passed with skills)."""
    runs = []
    for task_id, (tools_ok, skills_ok) in outcomes.items():
        for arm, ok in (("tools", tools_ok), ("tools+skills", skills_ok)):
            run = {"task_id": task_id, "arm": arm, "passed": ok, "tool_calls": 5, "seconds": 30.0,
                   "timed_out": False, "run_index": 0}
            if side:
                run["side"] = side
            runs.append(run)
    record = {"arms": ["tools", "tools+skills"], "runs": runs,
              "provenance": {"measured_at": measured_at},
              "published": published or ["tools -> tools+skills  lift +0.098 [-0.034, +0.230]  n=40 pairs"]}
    (directory / name).write_text(json.dumps(record))


def task_file(tasks_dir: Path, task_id: str, first_line="Do the thing."):
    sub = tasks_dir / "corpus"
    sub.mkdir(parents=True, exist_ok=True)
    (sub / f"{task_id}.yaml").write_text(
        f"id: {task_id}\nprompt: |\n  {first_line}\n  More detail here.\ncheck: |\n  write \"PASS\"\ntags: [demo]\n"
    )


def nightly(state="green", when="2026-10-10"):
    return lambda: improve.Nightly(state=state, when=when, detail="")


@pytest.fixture
def world(tmp_path):
    results, tasks = tmp_path / "results", tmp_path / "tasks"
    results.mkdir()
    # 35 tasks: 30 fine in both arms, 1 fails in both, 1 skills made worse, 3 pass only with skills.
    outcomes = {f"CORPUS-{i}": (True, True) for i in range(101, 131)}
    outcomes["CORPUS-40"] = (False, False)
    outcomes["CORPUS-19"] = (True, False)
    for t in ("CORPUS-06", "CORPUS-15", "CORPUS-17"):
        outcomes[t] = (False, True)
    for t in outcomes:
        task_file(tasks, t, first_line=f"Prompt for {t}.")
    write_ladder(results, "ladder-full.json", outcomes)
    return results, tasks


def run_cli(argv, world, *, night=None, runner=None, container=True, out=None):
    results, tasks = world
    lines = [] if out is None else out
    code = improve.main(
        argv,
        results_dir=results,
        tasks_dir=tasks,
        nightly=night or nightly(),
        validator=runner or (lambda task_id: improve.Validation(ok=True, detail="")),
        container_running=lambda name: container,
        out=lines.append,
        now=NOW,
    )
    return code, "\n".join(lines)


# ---- the worklist ------------------------------------------------------------------------------


def test_the_worklist_ranks_both_fail_then_skills_hurt_then_skills_only(world):
    status = improve.build_status(*world, now=NOW, nightly=nightly())
    ids = [item.task_id for item in status.worklist]
    assert ids[0] == "CORPUS-40", "a task that fails in both arms comes first"
    assert ids[1] == "CORPUS-19", "then a task skills made worse"
    assert set(ids[2:]) == {"CORPUS-06", "CORPUS-15", "CORPUS-17"}
    assert status.worklist[0].kind == "both_fail"
    assert status.worklist[1].kind == "skills_hurt"
    assert {i.kind for i in status.worklist[2:]} == {"skills_only"}


def test_the_scoreboard_counts_each_arm(world):
    status = improve.build_status(*world, now=NOW, nightly=nightly())
    assert status.tasks == 35
    assert status.tools_passed == 31  # 30 + CORPUS-19
    assert status.skills_passed == 33  # 30 + three rescued


def test_a_small_run_is_not_a_full_holdout(world, tmp_path):
    results, tasks = world
    # A newer record, but only 4 tasks: a spot check, not the figure to report.
    write_ladder(results, "ladder-spot.json", {f"CORPUS-0{i}": (True, True) for i in range(1, 5)},
                 measured_at="2026-10-01T00:00:00Z")
    status = improve.build_status(results, tasks, now=NOW, nightly=nightly())
    assert status.tasks == 35 and status.measured_at.startswith("2026-09-19")


def test_a_train_side_run_is_never_the_reported_holdout(world):
    results, tasks = world
    write_ladder(results, "ladder-train.json", {f"CORPUS-{i:02d}": (False, False) for i in range(1, 40)},
                 measured_at="2026-10-05T00:00:00Z", side="train")
    status = improve.build_status(results, tasks, now=NOW, nightly=nightly())
    assert status.measured_at.startswith("2026-09-19"), "train runs publish nothing"


def test_the_newest_full_holdout_wins(world):
    results, tasks = world
    write_ladder(results, "ladder-newer.json", {f"CORPUS-{i:02d}": (True, True) for i in range(1, 36)},
                 measured_at="2026-10-08T00:00:00Z")
    status = improve.build_status(results, tasks, now=NOW, nightly=nightly())
    assert status.measured_at.startswith("2026-10-08") and status.worklist == []


def test_no_results_at_all_says_so_instead_of_crashing(tmp_path):
    (tmp_path / "r").mkdir()
    status = improve.build_status(tmp_path / "r", tmp_path / "t", now=NOW, nightly=nightly())
    assert status.measured_at is None and status.worklist == []
    code, text = run_cli([ "status"], (tmp_path / "r", tmp_path / "t"))
    assert code == 0 and "no full holdout run" in text.lower()


# ---- spend -------------------------------------------------------------------------------------


def test_spend_is_not_tracked_until_there_is_a_ledger(world):
    code, text = run_cli(["status"], world)
    assert code == 0 and "not tracked yet" in text


def test_spend_is_this_months_ledger_total(world):
    results, _ = world
    (results / "improve-ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in [
            {"ts": "2026-10-03T10:00:00Z", "cost_usd": 4.25, "what": "try CORPUS-40"},
            {"ts": "2026-10-09T10:00:00Z", "cost_usd": 1.0, "what": "try CORPUS-19"},
            {"ts": "2026-09-28T10:00:00Z", "cost_usd": 60.0, "what": "last month's sweep"},
        ]) + "\n"
    )
    code, text = run_cli(["status"], world)
    assert "$5.25" in text and "60" not in text.split("Spend")[1].split("\n")[0]


# ---- what status prints ------------------------------------------------------------------------


def test_status_is_plain_english_with_the_worklist_in_order(world):
    code, text = run_cli(["status"], world)
    assert code == 0
    assert "Nightly canary" in text and "green" in text and "2026-10-10" in text
    assert "tools alone 31/35" in text and "with skills 33/35" in text
    assert text.index("CORPUS-40") < text.index("CORPUS-19")
    assert "fails in both arms" in text and "skills made it worse" in text
    assert "improve next" in text, "ends by saying what to do"


@pytest.mark.parametrize("state,word", [("green", "green"), ("red", "RED"), ("unknown", "unknown")])
def test_the_nightly_state_is_stated_not_hidden(world, state, word):
    code, text = run_cli(["status"], world, night=nightly(state))
    assert word in text.split("Nightly canary")[1].split("\n")[0]


def test_a_red_nightly_comes_before_any_task_work(world):
    code, text = run_cli(["status"], world, night=nightly("red"))
    assert "fix the nightly first" in text.lower()


def test_status_json_is_machine_readable(world):
    code, text = run_cli(["status", "--json"], world)
    data = json.loads(text)
    assert data["nightly"]["state"] == "green"
    assert data["tasks"] == 35 and data["worklist"][0]["task_id"] == "CORPUS-40"


# ---- next --------------------------------------------------------------------------------------


def test_next_takes_the_top_item_and_checks_the_task_first(world):
    seen = []
    code, text = run_cli(
        ["next"], world,
        runner=lambda task_id: (seen.append(task_id), improve.Validation(ok=True, detail=""))[1],
    )
    assert code == 0 and seen == ["CORPUS-40"]
    assert "CORPUS-40" in text and "task is sound" in text.lower()
    assert "Prompt for CORPUS-40." in text, "shows what the agent was asked"
    assert "both arms" in text


def test_a_broken_task_is_reported_as_the_problem_not_the_agent(world):
    code, text = run_cli(
        ["next"], world,
        runner=lambda t: improve.Validation(ok=False, detail="reference solution did not pass its check"),
    )
    assert code == 1
    assert "task is broken" in text.lower() and "reference solution did not pass" in text
    assert "before blaming the agent" in text.lower()


def test_next_can_be_pointed_at_a_task(world):
    seen = []
    run_cli(["next", "CORPUS-19"], world,
            runner=lambda t: (seen.append(t), improve.Validation(ok=True, detail=""))[1])
    assert seen == ["CORPUS-19"]


def test_an_unknown_task_is_a_clear_error(world):
    code, text = run_cli(["next", "CORPUS-99"], world)
    assert code == 2 and "CORPUS-99" in text and "not in the last holdout" in text.lower()


def test_next_with_an_empty_worklist_says_so(world):
    results, tasks = world
    write_ladder(results, "ladder-clean.json", {f"CORPUS-{i:02d}": (True, True) for i in range(1, 36)},
                 measured_at="2026-10-08T00:00:00Z")
    code, text = run_cli(["next"], world)
    assert code == 0 and "nothing is failing" in text.lower()


def test_next_says_how_to_start_the_container_when_it_is_down(world):
    code, text = run_cli(["next"], world, container=False)
    assert code == 3 and "docker start iris-dev-iris" in text


def test_a_validated_task_is_not_validated_again_until_its_file_changes(world):
    results, tasks = world
    calls = []
    runner = lambda t: (calls.append(t), improve.Validation(ok=True, detail=""))[1]
    run_cli(["next"], world, runner=runner)
    run_cli(["next"], world, runner=runner)
    assert calls == ["CORPUS-40"], "the second call used the cache"
    (tasks / "corpus" / "CORPUS-40.yaml").write_text("id: CORPUS-40\nprompt: |\n  Changed.\n")
    run_cli(["next"], world, runner=runner)
    assert calls == ["CORPUS-40", "CORPUS-40"], "an edited task is checked again"


def test_next_says_when_there_are_no_transcripts_to_read(world):
    code, text = run_cli(["next"], world)
    assert "no transcript" in text.lower() and "improve try" in text


# ---- free means free ---------------------------------------------------------------------------


def test_status_and_next_never_start_a_session_or_a_process_of_their_own(world, monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise AssertionError(f"improve status/next ran a process: {a}")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(subprocess, "Popen", boom)
    # Everything that would shell out is injected; with those, nothing else may.
    assert run_cli(["status"], world)[0] == 0
    assert run_cli(["next"], world)[0] == 0


def test_the_module_does_not_import_anything_that_spends_money():
    source = Path(improve.__file__).read_text()
    for forbidden in ("opencode_driver", "prime_agent", "scorer_client", "billing"):
        assert forbidden not in source, f"improve imports {forbidden}"
